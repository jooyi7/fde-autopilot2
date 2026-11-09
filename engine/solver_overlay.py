#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Solver 1: Photolithography Overlay, Feed-forward APC, Smart Metrology Sampling & Scanner Chuck Matching

"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np

SENTINEL_VALUES = {-999.0, -9999.0, 9999.0, 99999.0}


class OverlaySolver:
    @staticmethod
    def sanitize_measurements(measurements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """결측치(Null), 센티널(-999 등), 중복 좌표(Shot/Site)를 안전하게 정제 및 분리"""
        clean_list = []
        invalid_records = []
        seen_coords = {}

        for idx, m in enumerate(measurements or []):
            if not isinstance(m, dict):
                invalid_records.append({"index": idx, "reason": "NOT_A_DICT"})
                continue

            status_flag = str(m.get("status", "VALID")).strip().upper()
            if status_flag in {"INVALID", "CANCELLED", "DISCARDED", "ERROR", "DUMMY", "TEST"}:
                invalid_records.append({"index": idx, "reason": f"FLAG_{status_flag}"})
                continue

            try:
                X = float(m.get("X", 0.0))
                Y = float(m.get("Y", 0.0))
                x = float(m.get("x", 0.0))
                y = float(m.get("y", 0.0))
                dx = float(m["dx"])
                dy = float(m["dy"])
                stress = float(m.get("pre_process_stress_mpa", 0.0) or 0.0)
                film_thick_asym = float(m.get("film_thickness_asym_nm", 0.0) or 0.0)
            except (KeyError, ValueError, TypeError):
                invalid_records.append({"index": idx, "reason": "PARSE_OR_NULL_ERROR"})
                continue

            if any(math.isnan(v) or math.isinf(v) or v in SENTINEL_VALUES for v in (X, Y, x, y, dx, dy)):
                invalid_records.append({"index": idx, "reason": "SENTINEL_OR_NAN_VALUE"})
                continue

            coord_key = (round(X, 3), round(Y, 3), round(x, 3), round(y, 3))
            rec = {
                "shot_index": idx,
                "X": X, "Y": Y, "x": x, "y": y,
                "dx": dx, "dy": dy,
                "pre_process_stress_mpa": stress,
                "film_thickness_asym_nm": film_thick_asym,
                "timestamp": str(m.get("timestamp", "")),
                "chuck_id": str(m.get("chuck_id", "CHUCK_1")),
                "scanner_id": str(m.get("scanner_id", "SCANNER_A")),
                "etch_chamber_id": str(m.get("etch_chamber_id", "ETCH_01")),
            }
            # 중복 식별자 발생 시 최신 타임스탬프(또는 마지막 레코드) 유지
            if coord_key in seen_coords:
                prev_pos = seen_coords[coord_key]
                if rec["timestamp"] >= clean_list[prev_pos]["timestamp"]:
                    clean_list[prev_pos] = rec
            else:
                seen_coords[coord_key] = len(clean_list)
                clean_list.append(rec)

        return {
            "clean_measurements": clean_list,
            "invalid_records": invalid_records,
            "valid_count": len(clean_list),
            "invalid_count": len(invalid_records),
        }

    @staticmethod
    def build_design_matrix(records: List[Dict[str, float]], order: int = 1, include_feedforward: bool = True) -> np.ndarray:
        """
        1차(10-param Linear Wafer+Field) ~ 3차(High-Order Non-linear Wafer Distortion)
        + 전공정(Etch/Dep) 박막 스트레스/비대칭 Feed-forward 보정 항 구성
        """
        rows = []
        for r in records:
            X, Y = float(r.get("X", 0.0)), float(r.get("Y", 0.0))
            x, y = float(r.get("x", 0.0)), float(r.get("y", 0.0))
            radius_sq = X**2 + Y**2
            stress = float(r.get("pre_process_stress_mpa", 0.0))
            asym = float(r.get("film_thickness_asym_nm", 0.0))

            # Order 1: Wafer Linear (Tx, Mx*X, -Rx*Y) + Field Linear (tx, mx*x, -rx*y)
            feat = [1.0, X, Y, x, y]
            if order >= 2:
                # 2nd order wafer bow/warp & intra-field terms
                feat.extend([X**2, Y**2, X * Y, x**2, y**2, x * y, X * x, Y * y])
            if order >= 3:
                # 3rd order High-Order Wafer Edge Distortion (HOWA)
                feat.extend([X**3, Y**3, (X**2) * Y, X * (Y**2), radius_sq * X, radius_sq * Y])
            if include_feedforward:
                # Feed-forward terms: Coupling between pre-process film stress and wafer edge coordinates
                feat.extend([stress * X, stress * Y, asym * X, asym * Y])
            rows.append(feat)
        return np.array(rows, dtype=float)

    @staticmethod
    def optimize_smart_sampling(
        records: List[Dict[str, Any]],
        res_x: np.ndarray,
        res_y: np.ndarray,
        target_sampling_ratio: float = 0.35,
        wafer_radius_mm: float = 150.0,
    ) -> Dict[str, Any]:
        """
        [해결방안 2] 가상 계측(Virtual Metrology) 및 AI 기반 스마트 샘플링 최적화:
        전체 샷을 다 측정하면 계측 병목(TAT 저하)이 발생하므로, 잔차 그래디언트와 웨이퍼 엣지(Edge) 취약 구역을
        우선 선택해 최소 샘플링 포인트로 최대 불량 검출력을 확보
        """
        n = len(records)
        if n == 0:
            return {"selected_shot_indices": [], "throughput_gain_pct": 0.0}

        scores = []
        for i, r in enumerate(records):
            radial_pos = math.hypot(float(r["X"]), float(r["Y"])) / max(wafer_radius_mm, 1.0)
            radial_err = math.hypot(float(res_x[i]), float(res_y[i]))
            stress_factor = abs(float(r.get("pre_process_stress_mpa", 0.0))) * 0.01
            # Edge 취약도(가중치 40%) + 잔차 크기(50%) + 전공정 스트레스(10%)
            vulnerability_score = 0.5 * radial_err + 0.4 * (radial_pos ** 2) + 0.1 * stress_factor
            scores.append((vulnerability_score, i, radial_pos, radial_err))

        scores.sort(reverse=True, key=lambda x: x[0])
        k = max(5, min(n, int(math.ceil(n * target_sampling_ratio))))
        selected = sorted([item[1] for item in scores[:k]])
        captured_err = sum(item[3] for item in scores[:k]) / max(sum(item[3] for item in scores), 1e-9)

        return {
            "total_candidate_shots": n,
            "smart_sampled_shot_count": k,
            "sampling_ratio_pct": round((k / n) * 100.0, 2),
            "estimated_defect_capture_rate_pct": round(captured_err * 100.0, 2),
            "metrology_tat_reduction_pct": round((1.0 - (k / n)) * 100.0, 2),
            "priority_measurement_shot_indices": selected,
        }

    @staticmethod
    def evaluate_chamber_and_chuck_matching(
        records: List[Dict[str, Any]],
        res_x: np.ndarray,
        res_y: np.ndarray,
        candidate_scanners: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        [해결방안 3] 챔버/척 매칭(Chamber-to-Chamber & Chuck Matching) 및 최적 스캐너 라우팅:
        포토 장비 자체 문제인지 전공정(Etch/Dep) 챔버 스트레스 편차인지 원인 귀속(Root Cause Attribution) 판별 및
        Queue Time과 Machine Matching Offset을 고려한 최적 스캐너 추천
        """
        chuck_stats: Dict[str, List[float]] = {}
        etch_stats: Dict[str, List[float]] = {}

        for i, r in enumerate(records):
            err = math.hypot(float(res_x[i]), float(res_y[i]))
            cid = r.get("chuck_id", "CHUCK_1")
            eid = r.get("etch_chamber_id", "ETCH_01")
            chuck_stats.setdefault(cid, []).append(err)
            etch_stats.setdefault(eid, []).append(err)

        chuck_summary = {k: round(float(np.mean(v) + 3 * np.std(v)), 4) for k, v in chuck_stats.items()}
        etch_summary = {k: round(float(np.mean(v) + 3 * np.std(v)), 4) for k, v in etch_stats.items()}

        chuck_delta = (max(chuck_summary.values()) - min(chuck_summary.values())) if len(chuck_summary) > 1 else 0.0
        etch_delta = (max(etch_summary.values()) - min(etch_summary.values())) if len(etch_summary) > 1 else 0.0

        if etch_delta > max(0.35, chuck_delta * 1.3):
            attribution = "PRE_PROCESS_ETCH_DEP_CHAMBER_VARIATION"
        elif chuck_delta > 0.35:
            attribution = "SCANNER_CHUCK_TO_CHUCK_MISMATCH"
        else:
            attribution = "WITHIN_NORMAL_MATCHING_TOLERANCE"

        routing_recommendations = []
        for sc in (candidate_scanners or []):
            sc_id = sc.get("scanner_id", "SCANNER_UNK")
            m_offset = float(sc.get("matching_offset_nm", 0.3))
            q_mins = float(sc.get("queue_time_mins", 30.0))
            avail = bool(sc.get("available", True))
            if not avail:
                continue
            # 품질(오프셋) 70% + TAT(대기시간) 30% 가중합 스코어 (낮을수록 우수)
            routing_cost = 0.7 * m_offset + 0.3 * (q_mins / 60.0)
            routing_recommendations.append({
                "scanner_id": sc_id,
                "matching_offset_nm": round(m_offset, 3),
                "queue_time_mins": round(q_mins, 1),
                "routing_priority_score": round(routing_cost, 4),
            })
        routing_recommendations.sort(key=lambda x: x["routing_priority_score"])

        return {
            "root_cause_attribution": attribution,
            "chuck_m3s_by_id": chuck_summary,
            "etch_chamber_m3s_by_id": etch_summary,
            "chuck_to_chuck_delta_nm": round(chuck_delta, 4),
            "etch_chamber_delta_nm": round(etch_delta, 4),
            "optimal_scanner_routing": routing_recommendations[0]["scanner_id"] if routing_recommendations else "DEFAULT_DEDICATED_SCANNER",
            "scanner_candidates_ranked": routing_recommendations,
        }

    @classmethod
    def solve_apc(
        cls,
        measurements: List[Dict[str, Any]],
        m3s_spec_nm: float = 2.0,
        max_order: int = 3,
        outlier_z: float = 3.5,
        strict_gte: bool = True,
        target_sampling_ratio: float = 0.35,
        candidate_scanners: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        sanitized = cls.sanitize_measurements(measurements)
        clean_Input = sanitized["clean_measurements"]

        if not clean_Input:
            return {
                "status": "VIOLATION",
                "ruleId": "OVL-ERR-001",
                "disposition": "HOLD_INVALID_METROLOGY_DATA",
                "reason": "No valid overlay measurement records after sanitization.",
                "sanitization_summary": sanitized,
            }

        dx_raw = np.array([float(m["dx"]) for m in clean_Input], dtype=float)
        dy_raw = np.array([float(m["dy"]) for m in clean_Input], dtype=float)

        # IQR / Z-score 기반 계측 노이즈(Flyer/Outlier) 마스킹
        zx = np.abs((dx_raw - np.mean(dx_raw)) / max(float(np.std(dx_raw)), 1e-6))
        zy = np.abs((dy_raw - np.mean(dy_raw)) / max(float(np.std(dy_raw)), 1e-6))
        valid_mask = (zx <= outlier_z) & (zy <= outlier_z)
        if np.sum(valid_mask) < max(6, len(clean_Input) // 2):
            valid_mask = np.ones(len(clean_Input), dtype=bool)

        inlier_records = [m for m, v in zip(clean_Input, valid_mask) if v]
        dx_clean = dx_raw[valid_mask]
        dy_clean = dy_raw[valid_mask]

        has_ff = any(abs(m.get("pre_process_stress_mpa", 0.0)) > 0 or abs(m.get("film_thickness_asym_nm", 0.0)) > 0 for m in clean_Input)

        best_result = None
        for order in range(1, max_order + 1):
            A_clean = cls.build_design_matrix(inlier_records, order=order, include_feedforward=has_ff)
            A_full = cls.build_design_matrix(clean_Input, order=order, include_feedforward=has_ff)

            lam = 1e-5 * np.eye(A_clean.shape[1])
            coeff_x = np.linalg.solve(A_clean.T @ A_clean + lam, A_clean.T @ dx_clean)
            coeff_y = np.linalg.solve(A_clean.T @ A_clean + lam, A_clean.T @ dy_clean)

            res_x = dx_raw - (A_full @ coeff_x)
            res_y = dy_raw - (A_full @ coeff_y)

            before_m3s_x = float(np.abs(np.mean(dx_raw)) + 3.0 * np.std(dx_raw))
            before_m3s_y = float(np.abs(np.mean(dy_raw)) + 3.0 * np.std(dy_raw))
            after_m3s_x = float(np.abs(np.mean(res_x)) + 3.0 * np.std(res_x))
            after_m3s_y = float(np.abs(np.mean(res_y)) + 3.0 * np.std(res_y))

            if strict_gte:
                rework_flag = (after_m3s_x >= m3s_spec_nm) or (after_m3s_y >= m3s_spec_nm)
            else:
                rework_flag = (after_m3s_x > m3s_spec_nm) or (after_m3s_y > m3s_spec_nm)

            warn_threshold = m3s_spec_nm * 0.85
            warn_flag = (not rework_flag) and ((after_m3s_x >= warn_threshold) or (after_m3s_y >= warn_threshold))

            shot_violations = []
            for idx, (rx, ry) in enumerate(zip(res_x, res_y)):
                radial_err = float(np.hypot(rx, ry))
                is_viol = (radial_err >= m3s_spec_nm) if strict_gte else (radial_err > m3s_spec_nm)
                if is_viol:
                    shot_violations.append({
                        "shot_index": clean_Input[idx]["shot_index"],
                        "X": clean_Input[idx]["X"],
                        "Y": clean_Input[idx]["Y"],
                        "residual_dx": round(float(rx), 4),
                        "residual_dy": round(float(ry), 4),
                        "radial_error_nm": round(radial_err, 4),
                        "is_wafer_edge_hotspot": math.hypot(clean_Input[idx]["X"], clean_Input[idx]["Y"]) >= 120.0,
                    })

            smart_sampling = cls.optimize_smart_sampling(
                clean_Input, res_x, res_y, target_sampling_ratio=target_sampling_ratio
            )
            matching_analysis = cls.evaluate_chamber_and_chuck_matching(
                clean_Input, res_x, res_y, candidate_scanners=candidate_scanners
            )

            status_code = "VIOLATION" if rework_flag else ("WARNING" if warn_flag else "NORMAL")
            rule_id = "OVL-RULE-REWORK" if rework_flag else ("OVL-RULE-WARN-85PCT" if warn_flag else "OVL-RULE-PASS")

            candidate = {
                "status": status_code,
                "ruleId": rule_id,
                "selected_order": order,
                "feedforward_stress_applied": has_ff,
                "outliers_filtered": int(np.sum(~valid_mask)),
                "invalid_records_dropped": sanitized["invalid_count"],
                "spec_limit_nm": m3s_spec_nm,
                "disposition": "REWORK_REQUIRED" if rework_flag else ("INLINE_MONITOR_WARNING" if warn_flag else "PASS_INLINE"),
                "apc_parameters": {
                    "coeff_dx": [round(float(c), 6) for c in coeff_x],
                    "coeff_dy": [round(float(c), 6) for c in coeff_y],
                },
                "metrics": {
                    "before_m3s_dx": round(before_m3s_x, 4),
                    "before_m3s_dy": round(before_m3s_y, 4),
                    "after_m3s_dx": round(after_m3s_x, 4),
                    "after_m3s_dy": round(after_m3s_y, 4),
                    "improvement_dx_pct": round((1.0 - after_m3s_x / max(before_m3s_x, 1e-9)) * 100.0, 2),
                    "improvement_dy_pct": round((1.0 - after_m3s_y / max(before_m3s_y, 1e-9)) * 100.0, 2),
                },
                "high_risk_shots": shot_violations,
                "smart_sampling_plan": smart_sampling,
                "chamber_and_scanner_matching": matching_analysis,
            }
            best_result = candidate
            if not rework_flag:
                break

        return best_result


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = OverlaySolver.solve_apc(
            measurements=payload.get("measurements", []),
            m3s_spec_nm=float(payload.get("m3s_spec_nm", 2.0)),
            max_order=int(payload.get("max_order", 3)),
            strict_gte=bool(payload.get("strict_gte", True)),
            target_sampling_ratio=float(payload.get("target_sampling_ratio", 0.35)),
            candidate_scanners=payload.get("candidate_scanners"),
        )
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
