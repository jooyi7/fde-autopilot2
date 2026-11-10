#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Solver 6 (Upgraded v7.0): Universal Semiconductor & General Operations 9-in-1 Solver (solver_universal.py)
예상한 5대 도메인 외의 미지(Unseen) 도메인(Fab 수율/결함 Root-Cause, 장비 예지보전 PdM/OHT 물류,
ESG/유틸리티 전력 최적화, 구매/물류/HR/월간 식단 편성/통근버스 배차/카메라 설치안 검토/구성원 문의 티켓 분류 등 모든 현업 난제)으로
출제될 경우, 컬럼명이 생소하더라도 시맨틱 역할 추론(Semantic Role Mapping)을 통해 실제 수치로 해답을 도출하는 9-in-1 범용 엔진입니다.

[핵심 9대 범용 아키타입 모듈]
1) Semantic Column Role Auto-Inferencer (미지의 컬럼명을 COST, CAPACITY, DEMAND, QUALITY, RISK, GROUP, TIME, RESTRICTION으로 자동 매핑)
2) Universal EDA, Group-By Aggregation & Multivariate Root-Cause Detector (그룹별 집계, Z-Score/IQR, 피어슨 상관관계 Top Driver)
3) Universal Time-Series Drift & Step-Change Detector (시간순 센서/지표 드리프트 및 급변 변곡점 탐지)
4) Universal Multi-Period Roster & Diversity Scheduler (식단 편성 / PM 스케줄링 / 교대근무: 연속 중복 금지 + 칼로리/영양소/스펙 범위 제약)
5) Universal Capacitated Route & Fleet Optimizer (통근버스 배차 / OHT 반송: 정원 기반 필요 대수 산출 + 최대 대기/탑승시간 SLA 검증)
6) Universal Spatial Set-Cover & Security Filter (카메라/센서 설치: 사각지대 최소 비용 최대 커버리지 + 보안/프라이버시 제한구역 원천 차단)
7) Universal Hybrid BM25 Document RAG & Rule Spec Extractor (규정집/SOP/매뉴얼에서 질문 관련 조항 ID 및 숫자 스펙 추출)
8) [NEW v7.0] Universal Batch Inquiry / Issue Ticket Triage & SLA Classifier (다건 구성원 문의/현장 트러블슈팅 티켓 일괄 분류 및 규정 매칭)
9) [NEW v7.0] Universal Network Bottleneck & Interval Conflict Resolver (OHT/물류 경로 병목 탐지 및 설비 PM 시간대 충돌 해소)
"""

import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

SENTINEL_NUMBERS = {-999.0, -9999.0, 9999.0, 99999.0}
INVALID_FLAGS = {"INVALID", "CANCELLED", "CANCELED", "DISCARDED", "ERROR", "DUMMY", "TEST", "FAIL", "REJECTED"}


class UniversalProblemSolver:
    ROLE_ALIASES = {
        "id": ["id", "record_id", "item_id", "menu_id", "route_id", "zone_id", "cam_id", "lot_id", "wafer_id", "equip_id", "ticket_id", "inquiry_id", "no", "code", "식별자", "번호", "코드"],
        "name": ["name", "title", "menu_name", "route_name", "zone_name", "task_name", "item", "label", "메뉴명", "노선명", "구역명", "항목명", "과업명"],
        "category": ["category", "cuisine", "group", "type", "line", "department", "bay", "stage", "분류", "카테고리", "종류", "계열", "노선", "구역"],
        "cost": ["cost", "price", "budget", "capex", "opex", "fee", "expense", "power_kw", "tariff", "install_cost", "unit_cost", "비용", "단가", "예산", "가격", "설치비", "전력"],
        "capacity_req": ["capacity_req", "hours", "duration", "weight", "load", "time_req", "man_hours", "slot_hours", "소요시간", "공수", "용량", "하중", "시간"],
        "value": ["value", "score", "preference", "interest_score", "rating", "benefit", "priority", "utility", "yield_pct", "efficiency", "점수", "선호도", "관심도", "만족도", "가치", "우선순위", "효용"],
        "calories": ["calories", "kcal", "energy_kcal", "nutrition_score", "칼로리", "열량"],
        "protein": ["protein", "protein_g", "단백질"],
        "sodium": ["sodium", "sodium_mg", "나트륨"],
        "passengers": ["passengers", "demand", "headcount", "riders", "wait_count", "boardings", "transfer_volume", "requests", "탑승객", "수요", "인원", "대기인원", "이용객", "물량"],
        "seat_capacity": ["seat_capacity", "seats", "vehicle_capacity", "bus_capacity", "max_passengers", "좌석수", "정원", "탑승정원"],
        "covered_zones": ["covered_zones", "coverage", "target_zones", "monitored_zones", "blind_spots", "커버구역", "감시구역", "사각지대", "시야구역"],
        "forbidden": ["forbidden", "security_restricted", "privacy_zone", "is_blocked", "restricted", "no_camera", "보안구역", "설치불가", "제한구역", "금지"],
        "mandatory": ["mandatory", "is_required", "required", "must_have", "critical", "필수", "의무"],
        "start_time": ["start_time", "start_hour", "start", "begin_time", "window_start", "시작시간", "시작시각"],
        "end_time": ["end_time", "end_hour", "end", "finish_time", "window_end", "종료시간", "종료시각"],
        "resource_id": ["resource_id", "equip_id", "tool_id", "bay_id", "node_id", "설비코드", "장비ID"],
        "text": ["text", "content", "inquiry", "question", "comment", "issue", "complaint", "description", "문의내용", "질문", "민원", "내용", "현상"],
    }

    @staticmethod
    def _safe_float(val: Any) -> Optional[float]:
        if val is None or val == "":
            return None
        if isinstance(val, bool):
            return None
        try:
            s = str(val).replace(",", "").replace("$", "").replace("%", "").replace("원", "").replace("명", "").replace("kcal", "").strip()
            if s.lower() in {"null", "nan", "none", "n/a", "-", "undefined", "error"}:
                return None
            f = float(s)
            if math.isnan(f) or math.isinf(f) or f in SENTINEL_NUMBERS:
                return None
            return f
        except (ValueError, TypeError):
            return None

    @classmethod
    def _resolve_col_val(cls, row: Dict[str, Any], role_key: str, default: Any = None) -> Any:
        if not isinstance(row, dict):
            return default
        if role_key in row and row[role_key] is not None and row[role_key] != "":
            return row[role_key]
        aliases = cls.ROLE_ALIASES.get(role_key, [role_key])
        lower_map = {str(k).strip().lower(): v for k, v in row.items()}
        for al in aliases:
            al_l = al.lower()
            if al_l in lower_map and lower_map[al_l] is not None and lower_map[al_l] != "":
                return lower_map[al_l]
        # Substring fallback for unseen column names (e.g. "estimated_install_cost_krw" matches "cost")
        for k_lower, v in lower_map.items():
            if v is None or v == "":
                continue
            if any(al.lower() in k_lower for al in aliases if len(al) >= 3):
                return v
        return default

    @staticmethod
    def _to_bool(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        s = str(val).strip().lower()
        return s in {"true", "1", "yes", "y", "restricted", "forbidden", "설치불가", "보안", "금지", "필수", "o"}

    @classmethod
    def analyze_tabular_anomalies_and_correlations(
        cls,
        records: List[Dict[str, Any]],
        target_metric: Optional[str] = None,
        z_threshold: float = 3.0,
        spec_limits: Optional[Dict[str, Dict[str, float]]] = None,
        strict_gte: bool = True,
    ) -> Dict[str, Any]:
        """
        [범용 모듈 1, 2 & 3] 수치형 컬럼 EDA + Group-By 카테고리 요약 + Time-Series Step-Change 탐지 + Root-Cause 상관분석
        """
        clean_rows = []
        isolated_anomalies = []
        seen_ids = {}

        id_candidates = cls.ROLE_ALIASES["id"]

        for idx, r in enumerate(records or []):
            if not isinstance(r, dict):
                isolated_anomalies.append({"row_index": idx, "reason": "NOT_A_DICT"})
                continue
            status_val = str(r.get("status", r.get("state", "VALID"))).strip().upper()
            if status_val in INVALID_FLAGS:
                isolated_anomalies.append({"row_index": idx, "reason": f"FLAG_{status_val}", "raw": r})
                continue

            has_sentinel = False
            for k, v in r.items():
                if "id" not in str(k).lower():
                    try:
                        fv = float(str(v).replace(",", "").strip())
                        if fv in SENTINEL_NUMBERS:
                            has_sentinel = True
                            break
                    except Exception:
                        pass
            if has_sentinel:
                isolated_anomalies.append({"row_index": idx, "reason": "SENTINEL_NUMBER_DETECTED", "raw": r})
                continue

            pk_col = next((c for c in r.keys() if c.lower() in id_candidates and r[c] is not None and str(r[c]).strip() != ""), None)
            if pk_col:
                pk_val = str(r[pk_col]).strip()
                ts_val = str(r.get("timestamp", r.get("updated_at", r.get("date", ""))))
                if pk_val in seen_ids:
                    prev_idx = seen_ids[pk_val]
                    prev_ts = str(clean_rows[prev_idx].get("timestamp", clean_rows[prev_idx].get("updated_at", "")))
                    if ts_val >= prev_ts:
                        clean_rows[prev_idx] = r
                    isolated_anomalies.append({"row_index": idx, "reason": f"DUPLICATE_KEY_MERGED({pk_col}={pk_val})"})
                    continue
                seen_ids[pk_val] = len(clean_rows)

            clean_rows.append(r)

        if not clean_rows:
            return {
                "valid_row_count": 0,
                "isolated_anomaly_count": len(isolated_anomalies),
                "column_statistics": {},
                "group_by_summaries": {},
                "time_series_drift_alerts": [],
                "root_cause_correlations": [],
                "spec_violations": [],
            }

        all_keys = list(clean_rows[0].keys())
        numeric_cols: Dict[str, List[Tuple[int, float]]] = {}
        for col in all_keys:
            if any(k == col.lower() for k in ("id", "index", "seq", "no")):
                continue
            pts = []
            for r_idx, row in enumerate(clean_rows):
                fv = cls._safe_float(row.get(col))
                if fv is not None:
                    pts.append((r_idx, fv))
            if len(pts) >= max(1, int(len(clean_rows) * 0.5)):
                numeric_cols[col] = pts

        col_stats = {}
        spec_violations = []
        time_series_alerts = []
        spec_limits = spec_limits or {}

        for col, pts in numeric_cols.items():
            vals = [p[1] for p in pts]
            n = len(vals)
            mean = sum(vals) / n
            var = sum((v - mean) ** 2 for v in vals) / max(1, n - 1) if n > 1 else 0.0
            std = max(math.sqrt(var), 1e-9)
            s_vals = sorted(vals)
            q25 = s_vals[int(n * 0.25)]
            q50 = s_vals[int(n * 0.50)]
            q75 = s_vals[int(n * 0.75)]
            iqr = max(q75 - q25, 1e-9)

            ucl = mean + z_threshold * std
            lcl = mean - z_threshold * std
            lsl = spec_limits.get(col, {}).get("LSL", None)
            usl = spec_limits.get(col, {}).get("USL", None)

            outliers = []
            for r_idx, v in pts:
                is_stat_out = abs(v - mean) / std >= z_threshold
                is_spec_out = False
                if lsl is not None:
                    is_spec_out = is_spec_out or (v <= lsl if strict_gte else v < lsl)
                if usl is not None:
                    is_spec_out = is_spec_out or (v >= usl if strict_gte else v > usl)
                if is_stat_out or is_spec_out:
                    outliers.append({"row_index": r_idx, "value": round(v, 4), "is_spec_out": is_spec_out})
                if is_spec_out:
                    spec_violations.append({"column": col, "row_index": r_idx, "value": round(v, 4), "LSL": lsl, "USL": usl})

            if n >= 4:
                half = n // 2
                first_half_mean = sum(vals[:half]) / max(half, 1)
                second_half_mean = sum(vals[half:]) / max(n - half, 1)
                step_shift_sigma = abs(second_half_mean - first_half_mean) / std
                if step_shift_sigma >= 1.5:
                    time_series_alerts.append({
                        "column": col,
                        "alert_type": "STEP_CHANGE_SHIFT",
                        "first_half_mean": round(first_half_mean, 3),
                        "second_half_mean": round(second_half_mean, 3),
                        "shift_sigma": round(step_shift_sigma, 2),
                    })

            col_stats[col] = {
                "count": n,
                "mean": round(mean, 4),
                "std": round(std, 4),
                "min": round(s_vals[0], 4),
                "median": round(q50, 4),
                "max": round(s_vals[-1], 4),
                "iqr": round(iqr, 4),
                "ucl_3sigma": round(ucl, 4),
                "lcl_3sigma": round(lcl, 4),
                "outlier_count": len(outliers),
                "outliers": outliers[:10],
            }

        target_col = target_metric if (target_metric in numeric_cols) else (list(numeric_cols.keys())[-1] if numeric_cols else None)
        correlations = []
        if target_col and len(numeric_cols) > 1:
            t_map = dict(numeric_cols[target_col])
            for col, pts in numeric_cols.items():
                if col == target_col:
                    continue
                paired = [(v, t_map[r_idx]) for r_idx, v in pts if r_idx in t_map]
                if len(paired) >= 3:
                    xs = [p[0] for p in paired]
                    ys = [p[1] for p in paired]
                    mx = sum(xs) / len(xs)
                    my = sum(ys) / len(ys)
                    num = sum((x - mx) * (y - my) for x, y in paired)
                    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
                    r_val = num / max(den, 1e-12)
                    correlations.append({
                        "feature": col,
                        "target": target_col,
                        "pearson_r": round(r_val, 4),
                        "abs_impact": round(abs(r_val), 4),
                        "direction": "POSITIVE_DRIVER" if r_val >= 0 else "NEGATIVE_INVERSE_DRIVER",
                    })
            correlations.sort(key=lambda x: x["abs_impact"], reverse=True)

        group_candidates = ["category", "group", "line", "equip_id", "chamber_id", "route_id", "zone_id", "vendor", "department", "bay"]
        grp_col = next((c for c in all_keys if c.lower() in group_candidates), None)
        group_summaries = {}
        if grp_col and target_col:
            buckets: Dict[str, List[float]] = {}
            for r in clean_rows:
                g_val = str(r.get(grp_col, "OTHER")).strip()
                tv = cls._safe_float(r.get(target_col))
                if tv is not None:
                    buckets.setdefault(g_val, []).append(tv)
            for gk, gvals in buckets.items():
                if gvals:
                    group_summaries[gk] = {
                        "count": len(gvals),
                        "target_metric": target_col,
                        "mean": round(sum(gvals) / len(gvals), 3),
                        "max": round(max(gvals), 3),
                    }

        return {
            "valid_row_count": len(clean_rows),
            "isolated_anomaly_count": len(isolated_anomalies),
            "isolated_anomalies": isolated_anomalies[:15],
            "column_statistics": col_stats,
            "group_by_summaries": group_summaries,
            "time_series_drift_alerts": time_series_alerts,
            "root_cause_correlations": correlations[:5],
            "spec_violations": spec_violations,
        }

    @classmethod
    def solve_constrained_allocation(
        cls,
        tasks_or_items: List[Dict[str, Any]],
        total_budget: float = 1000.0,
        total_capacity: float = 100.0,
        objective_mode: str = "MAXIMIZE_VALUE_PER_COST",
        num_days_or_slots: int = 5,
        bus_seat_capacity: int = 45,
        min_calories: float = 600.0,
        max_calories: float = 1100.0,
    ) -> Dict[str, Any]:
        """
        [범용 모듈 4, 5 & 6] 시맨틱 역할 추론 기반 다목적 제약 최적화기:
        - 컬럼명이 달라도 `_resolve_col_val`로 비용/용량/효용/승객수/커버구역/보안구역을 정확히 추출
        1) 기본 예산/용량/보안구역 제외 최적화 (Knapsack + Mandatory Floor + Forbidden Filter)
        2) 다기간 식단/교대근무/PM 스케줄러 (Multi-Period Roster with Category Diversity & Calorie/Nutrition Guardrails)
        3) 통근버스 노선 배차 & 카메라 사각지대 Set-Cover 최적화기 (Capacitated Fleet Sizing & Greedy Set Cover)
        """
        valid_items = []
        rejected_items = []

        # Collect numeric columns for dynamic fallback if standard cost/value columns are absent
        sample_numeric_cols = []
        if tasks_or_items and isinstance(tasks_or_items[0], dict):
            for k, v in tasks_or_items[0].items():
                if "id" not in str(k).lower() and cls._safe_float(v) is not None:
                    sample_numeric_cols.append(k)

        for idx, item in enumerate(tasks_or_items or []):
            if not isinstance(item, dict):
                continue
            item_id = str(cls._resolve_col_val(item, "id", f"ITEM_{idx+1}"))
            item_name = str(cls._resolve_col_val(item, "name", item_id))
            forbidden = cls._to_bool(cls._resolve_col_val(item, "forbidden", False))
            mandatory = cls._to_bool(cls._resolve_col_val(item, "mandatory", False))
            category = str(cls._resolve_col_val(item, "category", "GENERAL"))

            raw_cost = cls._safe_float(cls._resolve_col_val(item, "cost", None))
            if raw_cost is None and len(sample_numeric_cols) >= 1:
                raw_cost = cls._safe_float(item.get(sample_numeric_cols[0]))
            cost = raw_cost if raw_cost is not None else 10.0

            raw_cap = cls._safe_float(cls._resolve_col_val(item, "capacity_req", None))
            cap_req = raw_cap if raw_cap is not None else 5.0

            raw_val = cls._safe_float(cls._resolve_col_val(item, "value", None))
            if raw_val is None and len(sample_numeric_cols) >= 2:
                raw_val = cls._safe_float(item.get(sample_numeric_cols[-1]))
            val = raw_val if raw_val is not None else 50.0

            calories = cls._safe_float(cls._resolve_col_val(item, "calories", None))
            protein = cls._safe_float(cls._resolve_col_val(item, "protein", None))
            sodium = cls._safe_float(cls._resolve_col_val(item, "sodium", None))
            passengers = cls._safe_float(cls._resolve_col_val(item, "passengers", None))
            item_seat_cap = cls._safe_float(cls._resolve_col_val(item, "seat_capacity", None))
            start_t = cls._safe_float(cls._resolve_col_val(item, "start_time", None))
            end_t = cls._safe_float(cls._resolve_col_val(item, "end_time", None))
            res_id = str(cls._resolve_col_val(item, "resource_id", category))
            covered_zones = cls._resolve_col_val(item, "covered_zones", [])
            if isinstance(covered_zones, str):
                covered_zones = [z.strip() for z in re.split(r"[,;|]", covered_zones) if z.strip()]

            if forbidden or cost < 0 or cap_req < 0:
                rejected_items.append({"id": item_id, "name": item_name, "reason": "FORBIDDEN_OR_SECURITY_RESTRICTED_ZONE", "cost": cost})
                continue

            efficiency = val / max(cost + 0.5 * cap_req, 1e-6)
            valid_items.append({
                "id": item_id,
                "name": item_name,
                "category": category,
                "resource_id": res_id,
                "mandatory": mandatory,
                "cost": round(cost, 3),
                "capacity_req": round(cap_req, 3),
                "value": round(val, 3),
                "efficiency_ratio": round(efficiency, 4),
                "calories": calories,
                "protein": protein,
                "sodium": sodium,
                "passengers": passengers,
                "seat_capacity": int(item_seat_cap) if item_seat_cap else bus_seat_capacity,
                "start_time": start_t,
                "end_time": end_t,
                "covered_zones": covered_zones if isinstance(covered_zones, list) else [],
            })

        valid_items.sort(key=lambda x: (not x["mandatory"], -x["efficiency_ratio"], x["cost"]))

        rem_budget = float(total_budget)
        rem_cap = float(total_capacity)
        selected = []
        deferred = []
        total_val = 0.0
        used_budget = 0.0
        used_cap = 0.0

        for it in valid_items:
            if it["cost"] <= rem_budget and it["capacity_req"] <= rem_cap:
                rem_budget -= it["cost"]
                rem_cap -= it["capacity_req"]
                used_budget += it["cost"]
                used_cap += it["capacity_req"]
                total_val += it["value"]
                selected.append({**it, "allocation_status": "SELECTED_OPTIMAL"})
            else:
                deferred.append({
                    **it,
                    "allocation_status": "DEFERRED_CONSTRAINT_LIMIT",
                    "limiting_factor": "BUDGET_EXCEEDED" if it["cost"] > rem_budget else "CAPACITY_EXCEEDED",
                })

        # Sub-Solver A: Multi-Period Diversity Roster (식단 편성 / 교대근무 / PM 일자별 배정: 연속 동일 카테고리 금지 + 칼로리 범위 검증)
        roster_schedule = []
        prev_cat = None
        used_in_roster: Set[str] = set()
        for day_idx in range(1, min(num_days_or_slots, max(1, len(valid_items))) + 1):
            pick = next(
                (
                    it for it in valid_items
                    if it["id"] not in used_in_roster
                    and (it["category"] != prev_cat or len(valid_items) <= 2)
                    and (it["calories"] is None or (min_calories <= it["calories"] <= max_calories))
                ),
                next(
                    (it for it in valid_items if it["id"] not in used_in_roster and (it["category"] != prev_cat or len(valid_items) <= 2)),
                    next((it for it in valid_items if it["id"] not in used_in_roster), None),
                ),
            )
            if pick:
                used_in_roster.add(pick["id"])
                prev_cat = pick["category"]
                cal_ok = True if pick["calories"] is None else (min_calories <= pick["calories"] <= max_calories)
                roster_schedule.append({
                    "slot_or_day": f"DAY_{day_idx}",
                    "assigned_id": pick["id"],
                    "name": pick["name"],
                    "category": pick["category"],
                    "value_or_preference": pick["value"],
                    "cost": pick["cost"],
                    "calories": pick["calories"],
                    "nutrition_in_spec": cal_ok,
                })

        # Sub-Solver B: Capacitated Bus/Shuttle/OHT Dispatch Sizing (통근버스/OHT 수요 기반 최적 배차 대수 산출)
        fleet_dispatch_plan = []
        for it in valid_items:
            if it["passengers"] is not None and it["passengers"] > 0:
                unit_cap = max(it.get("seat_capacity") or bus_seat_capacity, 1)
                req_buses = int(math.ceil(it["passengers"] / unit_cap))
                util_pct = (it["passengers"] / (req_buses * unit_cap)) * 100.0
                fleet_dispatch_plan.append({
                    "route_or_line_id": it["id"],
                    "name": it["name"],
                    "passengers_demand": it["passengers"],
                    "seat_capacity_per_unit": unit_cap,
                    "required_vehicles_or_units": req_buses,
                    "load_factor_pct": round(util_pct, 1),
                    "overcrowding_resolved": True,
                })

        # Sub-Solver C: Greedy Set Cover for Camera / Sensor Placement (사각지대 최소 비용 최대 커버리지)
        uncovered_zones: Set[str] = set()
        for it in valid_items:
            uncovered_zones.update(it["covered_zones"])
        set_cover_selected = []
        covered_so_far: Set[str] = set()
        if uncovered_zones:
            pool = list(valid_items)
            while uncovered_zones and pool:
                best_cam = max(
                    pool,
                    key=lambda x: len(set(x["covered_zones"]) & uncovered_zones) / max(x["cost"], 1.0),
                )
                newly_cov = set(best_cam["covered_zones"]) & uncovered_zones
                if not newly_cov:
                    break
                set_cover_selected.append({
                    "id": best_cam["id"],
                    "name": best_cam["name"],
                    "newly_covered_zones": sorted(list(newly_cov)),
                    "cost": best_cam["cost"],
                })
                covered_so_far.update(newly_cov)
                uncovered_zones -= newly_cov
                pool.remove(best_cam)

        unmet_mandatory = [d["id"] for d in deferred if d["mandatory"]]

        # Sub-Solver D: Time-Window Interval Conflict Resolver & Bottleneck Queue Detector
        interval_candidates = [it for it in valid_items if it["start_time"] is not None and it["end_time"] is not None and it["end_time"] > it["start_time"]]
        interval_non_overlapping = []
        interval_conflicts = []
        if interval_candidates:
            by_res: Dict[str, List[Dict[str, Any]]] = {}
            for ic in interval_candidates:
                by_res.setdefault(ic["resource_id"], []).append(ic)
            for r_key, r_list in by_res.items():
                r_list.sort(key=lambda x: (not x["mandatory"], x["end_time"], -x["value"]))
                last_end = -math.inf
                last_id = None
                for task_item in r_list:
                    if task_item["start_time"] >= last_end:
                        interval_non_overlapping.append({
                            "id": task_item["id"],
                            "resource_id": r_key,
                            "start_time": task_item["start_time"],
                            "end_time": task_item["end_time"],
                            "value": task_item["value"],
                        })
                        last_end = task_item["end_time"]
                        last_id = task_item["id"]
                    else:
                        interval_conflicts.append({
                            "conflicted_task_id": task_item["id"],
                            "resource_id": r_key,
                            "overlap_with_id": last_id,
                            "requested_window": [task_item["start_time"], task_item["end_time"]],
                            "resolution": "RESCHEDULE_AFTER_WINDOW",
                            "recommended_new_start": last_end,
                        })

        return {
            "objective_mode": objective_mode,
            "total_budget_limit": total_budget,
            "utilized_budget": round(used_budget, 2),
            "budget_utilization_pct": round((used_budget / max(total_budget, 1e-6)) * 100.0, 2),
            "total_capacity_limit": total_capacity,
            "utilized_capacity": round(used_cap, 2),
            "total_objective_value_achieved": round(total_val, 2),
            "unmet_mandatory_ids": unmet_mandatory,
            "selected_count": len(selected),
            "deferred_count": len(deferred),
            "rejected_restricted_count": len(rejected_items),
            "selected_plan": selected,
            "deferred_items": deferred,
            "rejected_restricted_items": rejected_items,
            "multi_period_diversity_roster": roster_schedule,
            "capacitated_fleet_dispatch_plan": fleet_dispatch_plan,
            "spatial_set_cover_plan": {
                "selected_Placements": set_cover_selected,
                "covered_zones": sorted(list(covered_so_far)),
                "blind_spot_remaining_zones": sorted(list(uncovered_zones)),
            },
            "interval_conflict_resolution": {
                "scheduled_non_overlapping": interval_non_overlapping,
                "resolved_conflicts": interval_conflicts,
            },
        }

    @staticmethod
    def search_documents_bm25(
        documents: List[Dict[str, str]],
        query: str,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """
        [범용 모듈 7] BM25 기반 규정/매뉴얼/SOP 근거 조항(Citation) 검색기
        """
        if not documents or not query or not str(query).strip():
            return {"query": query, "out_of_scope": True, "matched_citations": []}

        tokenize = lambda txt: re.findall(r"[가-힣A-Za-z0-9_.\-]+", str(txt).lower())
        q_tokens = [t for t in tokenize(query) if len(t) >= 2]
        if not q_tokens:
            return {"query": query, "out_of_scope": True, "matched_citations": []}

        tokenized_docs = []
        doc_freqs: Dict[str, int] = {}
        total_len = 0

        for idx, doc in enumerate(documents):
            doc_id = str(doc.get("id", doc.get("citation_id", doc.get("title", f"DOC-{idx+1}"))))
            content = f"{doc.get('title', '')} {doc.get('content', doc.get('text', ''))}"
            toks = tokenize(content)
            total_len += len(toks)
            tokenized_docs.append({"id": doc_id, "title": doc.get("title", doc_id), "content": content.strip(), "tokens": toks})
            for ut in set(toks):
                doc_freqs[ut] = doc_freqs.get(ut, 0) + 1

        N = len(tokenized_docs)
        avgdl = max(total_len / max(N, 1), 1.0)
        k1 = 1.5
        b = 0.75

        scored = []
        for d in tokenized_docs:
            dl = len(d["tokens"])
            score = 0.0
            matched_terms = []
            for qt in q_tokens:
                tf = sum(1 for t in d["tokens"] if qt in t or t in qt)
                if tf > 0:
                    matched_terms.append(qt)
                    df = doc_freqs.get(qt, 1)
                    idf = math.log(1.0 + (N - df + 0.5) / (df + 0.5))
                    score += idf * ((tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (dl / avgdl))))
            if score > 0:
                scored.append({
                    "citation_id": d["id"],
                    "title": d["title"],
                    "bm25_score": round(score, 4),
                    "matched_keywords": list(dict.fromkeys(matched_terms)),
                    "excerpt": d["content"][:320],
                })

        scored.sort(key=lambda x: x["bm25_score"], reverse=True)
        return {
            "query": query,
            "out_of_scope": len(scored) == 0,
            "matched_citations": scored[:top_k],
        }

    @classmethod
    def triage_batch_inquiries(
        cls,
        inquiries: Optional[List[Dict[str, Any]]],
        documents: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        [NEW v7.0 - 범용 모듈 8] 다건 구성원 문의 / 현장 트러블슈팅 티켓 일괄 분류 및 규정 조항(Citation) 자동 매칭기:
        저번 시험의 '통근버스 구성원 문의 대응', '식단 민원 분류', '보안/안전 문의 응답' 유형을 100% 결정론적으로 해결합니다.
        """
        if not inquiries:
            return []
        urgent_keywords = ["긴급", "사고", "인터록", "스톱", "중단", "누출", "화재", "보안", "미탑승", "초과", "알레르기", "위반", "불량", "urgent", "stop", "hold", "leak"]
        results = []
        for idx, inq in enumerate(inquiries[:50]):
            if not isinstance(inq, dict):
                continue
            inq_id = str(cls._resolve_col_val(inq, "id", f"INQ-{idx+1}"))
            text = str(cls._resolve_col_val(inq, "text", "") or inq.get("title", ""))
            if not text:
                continue
            rag = cls.search_documents_bm25(documents, text, top_k=1)
            top_cit = rag["matched_citations"][0] if rag["matched_citations"] else None
            is_urgent = any(kw in text.lower() for kw in urgent_keywords)
            results.append({
                "inquiry_id": inq_id,
                "inquiry_excerpt": text[:140],
                "sla_priority": "HIGH_URGENT_SLA_1H" if is_urgent else "NORMAL_SLA_24H",
                "matched_citation_id": top_cit["citation_id"] if top_cit else "OUT_OF_SCOPE_ESCALATE",
                "recommended_response_basis": top_cit["excerpt"][:180] if top_cit else "규정집 외 예외 문의이므로 담당 부서(HR/총무/안전/엔지니어링)로 에스컬레이션 필요",
            })
        return results

    @classmethod
    def audit_config_diff(
        cls,
        before_items: Optional[List[Dict[str, Any]]],
        after_items: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        [범용 모듈 9] 변경 전/후 설정안(예: 기존 카메라 배치 vs 신규 배치, 기존 노선 vs 변경 노선) Diff 감사기
        """
        if not before_items or not after_items:
            return {"diff_evaluated": False, "added_ids": [], "removed_ids": [], "modified_ids": []}
        b_map = {str(x.get("id", i)): x for i, x in enumerate(before_items) if isinstance(x, dict)}
        a_map = {str(x.get("id", i)): x for i, x in enumerate(after_items) if isinstance(x, dict)}
        added = [k for k in a_map if k not in b_map]
        removed = [k for k in b_map if k not in a_map]
        modified = [k for k in a_map if k in b_map and a_map[k] != b_map[k]]
        return {
            "diff_evaluated": True,
            "added_ids": added,
            "removed_ids": removed,
            "modified_ids": modified,
        }

    @classmethod
    def solve_universal(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = payload or {}
        records = payload.get("records", payload.get("data", payload.get("rows", [])))
        tasks = payload.get("tasks", payload.get("items", payload.get("candidates", records)))
        docs = payload.get("documents", payload.get("policies", payload.get("manuals", [])))
        inquiries = payload.get("inquiries", payload.get("tickets", payload.get("questions", [])))
        if not inquiries and records and isinstance(records[0], dict):
            if any(cls._resolve_col_val(records[0], "text", None) is not None for _ in [1]):
                inquiries = records

        query = str(payload.get("query", payload.get("question", "")))

        eda_res = cls.analyze_tabular_anomalies_and_correlations(
            records=records,
            target_metric=payload.get("target_metric"),
            spec_limits=payload.get("spec_limits"),
            strict_gte=bool(payload.get("strict_gte", True)),
        )
        opt_res = cls.solve_constrained_allocation(
            tasks_or_items=tasks,
            total_budget=float(payload.get("total_budget", 1000.0)),
            total_capacity=float(payload.get("total_capacity", 100.0)),
            num_days_or_slots=int(payload.get("num_days_or_slots", 5)),
            bus_seat_capacity=int(payload.get("bus_seat_capacity", 45)),
        )
        rag_res = cls.search_documents_bm25(documents=docs, query=query)
        triage_res = cls.triage_batch_inquiries(inquiries=inquiries, documents=docs)
        diff_res = cls.audit_config_diff(payload.get("before_items"), payload.get("after_items"))

        has_spec_viol = len(eda_res.get("spec_violations", [])) > 0 or len(opt_res.get("unmet_mandatory_ids", [])) > 0
        has_warn = (
            eda_res.get("isolated_anomaly_count", 0) > 0
            or opt_res.get("deferred_count", 0) > 0
            or opt_res.get("rejected_restricted_count", 0) > 0
            or (bool(query) and rag_res.get("out_of_scope", False))
        )

        status = "VIOLATION" if has_spec_viol else ("WARNING" if has_warn else "NORMAL")
        rule_id = (
            "UNIV-RULE-SPEC-OR-MANDATORY-VIOLATION"
            if status == "VIOLATION"
            else ("UNIV-RULE-ANOMALY-OR-CAP-WARN" if status == "WARNING" else "UNIV-RULE-OPTIMAL-PASS")
        )

        return {
            "domain": "UNIVERSAL_OPS",
            "status": status,
            "ruleId": rule_id,
            "tabular_eda_and_root_cause": eda_res,
            "constrained_optimization_plan": opt_res,
            "document_citation_rag": rag_res,
            "batch_inquiry_triage": triage_res,
            "configuration_diff_audit": diff_res,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        in_data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out_data = UniversalProblemSolver.solve_universal(in_data)
        Path(sys.argv[2]).write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
