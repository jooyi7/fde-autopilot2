#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Solver 2: Chemical Material Quality (CoA), Spectral Fingerprint Matching,
HVM Scale-up Stress Simulation & Sub-tier 4M Genealogy Analyzer

"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np

SENTINEL_NUMBERS = {-999.0, -9999.0, 9999.0, 99999.0}


class MaterialQualitySolver:
    @staticmethod
    def sanitize_values(values: List[Any]) -> List[float]:
        clean = []
        for v in (values or []):
            if v is None:
                continue
            try:
                fv = float(v)
                if not math.isnan(fv) and not math.isinf(fv) and fv not in SENTINEL_NUMBERS:
                    clean.append(fv)
            except (ValueError, TypeError):
                continue
        return clean

    @staticmethod
    def evaluate_coa_parameter(
        values: List[Any],
        lsl: Optional[float] = None,
        usl: Optional[float] = None,
        strict_gte: bool = True,
    ) -> Dict[str, Any]:
        clean_vals = MaterialQualitySolver.sanitize_values(values)
        if not clean_vals:
            return {
                "n_samples": 0,
                "status": "INVALID_NO_VALID_SAMPLES",
                "risk_score": 100.0,
                "cpk": 0.0,
                "cp": 0.0,
                "oos_lot_indices": [],
            }

        arr = np.array(clean_vals, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 1e-6
        std = max(std, 1e-6)

        lsl_val = -math.inf if lsl is None else float(lsl)
        usl_val = math.inf if usl is None else float(usl)

        cpu = (usl_val - mean) / (3.0 * std) if usl_val != math.inf else math.inf
        cpl = (mean - lsl_val) / (3.0 * std) if lsl_val != -math.inf else math.inf
        cpk = float(min(cpu, cpl))
        cp = float((usl_val - lsl_val) / (6.0 * std)) if (lsl_val != -math.inf and usl_val != math.inf) else cpk

        if strict_gte:
            oos_indices = [int(i) for i, v in enumerate(arr) if v <= lsl_val or v >= usl_val]
        else:
            oos_indices = [int(i) for i, v in enumerate(arr) if v < lsl_val or v > usl_val]

        drift_slope = float(np.polyfit(np.arange(len(arr)), arr, 1)[0]) if len(arr) >= 3 else 0.0

        # Mother-lot sample count penalty (Lab vs HVM scale-up safeguard: need >= 3 lots)
        lot_count_penalty = 15.0 if len(arr) < 3 else 0.0

        if oos_indices:
            risk_score = 100.0
            status = "REJECT_OOS"
        elif cpk < 1.0:
            risk_score = min(98.0, 75.0 + (1.0 - cpk) * 30.0 + lot_count_penalty)
            status = "HIGH_RISK_LOW_CPK"
        elif cpk < 1.33:
            risk_score = min(85.0, 40.0 + (1.33 - cpk) * 100.0 + lot_count_penalty)
            status = "CONDITIONAL_MARGINAL_CPK"
        else:
            risk_score = max(0.0, 20.0 - (cpk - 1.33) * 15.0 + lot_count_penalty)
            status = "PASS_CAPABLE"

        return {
            "n_samples": len(arr),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "cp": round(cp, 3),
            "cpk": round(cpk, 3),
            "lot_drift_slope": round(drift_slope, 5),
            "oos_lot_indices": oos_indices,
            "risk_score": round(risk_score, 2),
            "status": status,
        }

    @staticmethod
    def analyze_spectral_fingerprint(
        reference_spectrum: Optional[List[float]],
        vendor_spectrum: Optional[List[float]],
        similarity_threshold: float = 0.985,
        unmeasured_peak_limit_pct: float = 5.0,
    ) -> Dict[str, Any]:
        """
        [해결방안 1] 성적서 합치 불량(In-Spec Excursion) 방지를 위한 화학적 지문(FT-IR/GC-MS/ICP-MS 스펙트럼) 매칭:
        CoA 요약 수치는 통과했더라도 스펙트럼 파형 내 미측정 불순물 피크(Ghost Peak)나 파형 왜곡을 검출
        """
        ref = MaterialQualitySolver.sanitize_values(reference_spectrum or [])
        ven = MaterialQualitySolver.sanitize_values(vendor_spectrum or [])
        if not ref or not ven or len(ref) != len(ven):
            return {
                "fingerprint_evaluated": False,
                "cosine_similarity": 1.0,
                "max_unmeasured_peak_deviation_pct": 0.0,
                "in_spec_excursion_flag": False,
                "fingerprint_risk_score": 0.0,
            }

        ref_arr = np.array(ref, dtype=float)
        ven_arr = np.array(ven, dtype=float)
        denom = float(np.linalg.norm(ref_arr) * np.linalg.norm(ven_arr))
        cos_sim = float(np.dot(ref_arr, ven_arr) / max(denom, 1e-12))

        ref_scale = max(float(np.max(np.abs(ref_arr))), 1e-6)
        peak_dev_pct = float(np.max(np.abs(ven_arr - ref_arr)) / ref_scale * 100.0)

        excursion_flag = (cos_sim < similarity_threshold) or (peak_dev_pct >= unmeasured_peak_limit_pct)
        fp_risk = 0.0
        if excursion_flag:
            fp_risk = min(100.0, max(50.0, (1.0 - cos_sim) * 2000.0 + peak_dev_pct * 3.5))

        return {
            "fingerprint_evaluated": True,
            "cosine_similarity": round(cos_sim, 6),
            "max_unmeasured_peak_deviation_pct": round(peak_dev_pct, 3),
            "in_spec_excursion_flag": excursion_flag,
            "fingerprint_risk_score": round(fp_risk, 2),
        }

    @staticmethod
    def evaluate_hvm_scaleup_stress(hvm_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        [해결방안 2] Lab 평가와 양산(HVM) 라인 간의 괴리 검증:
        배관 체류 시간(Pipe Residence Time), 펌프 전단 응력(Shear Stress)에 의한 파티클 증가율,
        유효기간(Shelf-life) 잔여율을 종합 평가
        """
        if not hvm_profile or not isinstance(hvm_profile, dict):
            return {
                "hvm_evaluated": False,
                "hvm_scaleup_risk_score": 0.0,
                "scaleup_bottleneck_flag": False,
            }

        res_hours = float(hvm_profile.get("pipe_residence_hours", 12.0))
        max_safe_hours = float(hvm_profile.get("max_safe_residence_hours", 24.0))
        shear_particle_growth_pct = float(hvm_profile.get("pump_shear_particle_growth_pct", 2.0))
        shelf_life_rem_days = float(hvm_profile.get("remaining_shelf_life_days", 90.0))
        min_shelf_life_days = float(hvm_profile.get("min_required_shelf_life_days", 30.0))

        risk = 0.0
        reasons = []
        if res_hours > max_safe_hours:
            risk += min(50.0, (res_hours - max_safe_hours) / max(max_safe_hours, 1.0) * 60.0)
            reasons.append("PIPE_RESIDENCE_DEGRADATION")
        if shear_particle_growth_pct >= 10.0:
            risk += min(45.0, shear_particle_growth_pct * 2.5)
            reasons.append("PUMP_SHEAR_AGGLOMERATION")
        if shelf_life_rem_days < min_shelf_life_days:
            risk += 40.0
            reasons.append("INSUFFICIENT_SHELF_LIFE")

        risk = min(100.0, risk)
        return {
            "hvm_evaluated": True,
            "pipe_residence_hours": res_hours,
            "pump_shear_particle_growth_pct": shear_particle_growth_pct,
            "remaining_shelf_life_days": shelf_life_rem_days,
            "scaleup_bottleneck_flag": risk >= 40.0,
            "scaleup_risk_reasons": reasons,
            "hvm_scaleup_risk_score": round(risk, 2),
        }

    @staticmethod
    def audit_subtier_4m_genealogy(subtier_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        [해결방안 3] 하위 공급망(Sub-tier 2·3차 원료사) 무단 4M 변경 은폐 및 계보 추적 검증
        """
        if not subtier_info or not isinstance(subtier_info, dict):
            return {
                "subtier_audited": False,
                "unapproved_4m_change_flag": False,
                "subtier_risk_score": 0.0,
            }

        unreported_4m = bool(subtier_info.get("unreported_4m_detected", False))
        origin_changed = bool(subtier_info.get("raw_material_origin_changed", False))
        pcn_approved = bool(subtier_info.get("pcn_approved", True))
        inline_drift_sigma = float(subtier_info.get("inline_metrology_drift_sigma", 0.0))

        risk = 0.0
        flags = []
        if unreported_4m:
            risk += 85.0
            flags.append("UNREPORTED_SUBTIER_4M_CHANGE")
        if origin_changed and not pcn_approved:
            risk += 60.0
            flags.append("UNAPPROVED_RAW_ORIGIN_CHANGE")
        if abs(inline_drift_sigma) >= 2.0:
            risk += min(50.0, abs(inline_drift_sigma) * 15.0)
            flags.append("SUBTIER_LOT_INLINE_DRIFT")

        risk = min(100.0, risk)
        return {
            "subtier_audited": True,
            "tier2_lot_id": str(subtier_info.get("tier2_lot_id", "T2_STD")),
            "tier3_lot_id": str(subtier_info.get("tier3_lot_id", "T3_STD")),
            "unapproved_4m_change_flag": risk >= 50.0,
            "audit_flags": flags,
            "subtier_risk_score": round(risk, 2),
        }

    @classmethod
    def compare_vendors(
        cls,
        specs: Dict[str, Dict[str, float]],
        vendors: List[Dict[str, Any]],
        reference_spectrum: Optional[List[float]] = None,
        strict_gte: bool = True,
    ) -> Dict[str, Any]:
        total_w = sum(float(s.get("weight", 1.0)) for s in (specs or {}).values()) or 1.0
        evaluations = []

        for v in (vendors or []):
            v_id = v.get("vendor_id", "UNKNOWN")
            samples = v.get("samples", {})
            param_results = {}
            weighted_coa_risk = 0.0
            has_hard_reject = False

            for pname, pspec in (specs or {}).items():
                w = float(pspec.get("weight", 1.0)) / total_w
                res = cls.evaluate_coa_parameter(
                    samples.get(pname, []),
                    lsl=pspec.get("LSL"),
                    usl=pspec.get("USL"),
                    strict_gte=strict_gte,
                )
                param_results[pname] = res
                weighted_coa_risk += res["risk_score"] * w
                if res["status"] in {"REJECT_OOS", "INVALID_NO_VALID_SAMPLES"}:
                    has_hard_reject = True

            fp_res = cls.analyze_spectral_fingerprint(
                reference_spectrum or v.get("reference_spectrum"),
                v.get("spectrum"),
            )
            hvm_res = cls.evaluate_hvm_scaleup_stress(v.get("hvm_stress_profile"))
            subtier_res = cls.audit_subtier_4m_genealogy(v.get("subtier_genealogy"))

            cost_idx = float(v.get("cost_index", 1.0))
            lead_days = float(v.get("lead_time_days", 14.0))
            supply_chain_risk = max(0.0, (lead_days - 10.0) * 1.5)

            # 종합 품질/공급망 리스크: CoA(45%) + 화학지문(20%) + HVM 스케일업(15%) + Sub-tier 4M(10%) + 리드타임(10%)
            composite_risk = (
                0.45 * weighted_coa_risk
                + 0.20 * fp_res["fingerprint_risk_score"]
                + 0.15 * hvm_res["hvm_scaleup_risk_score"]
                + 0.10 * subtier_res["subtier_risk_score"]
                + 0.10 * supply_chain_risk
            )

            if has_hard_reject or subtier_res["unapproved_4m_change_flag"] or composite_risk >= 65.0:
                decision = "REJECT"
                status_badge = "VIOLATION"
                rule_id = "MAT-RULE-REJECT"
            elif fp_res["in_spec_excursion_flag"] or hvm_res["scaleup_bottleneck_flag"] or composite_risk >= 32.0:
                decision = "CONDITIONAL_PILOT_RUN"
                status_badge = "WARNING"
                rule_id = "MAT-RULE-CONDITIONAL-QUAL"
            else:
                decision = "APPROVE_MASS_PRODUCTION"
                status_badge = "NORMAL"
                rule_id = "MAT-RULE-APPROVE"

            evaluations.append({
                "vendor_id": v_id,
                "status": status_badge,
                "ruleId": rule_id,
                "decision": decision,
                "coa_quality_risk_score": round(weighted_coa_risk, 2),
                "fingerprint_analysis": fp_res,
                "hvm_scaleup_analysis": hvm_res,
                "subtier_4m_audit": subtier_res,
                "supply_chain_risk_score": round(supply_chain_risk, 2),
                "composite_risk_score": round(composite_risk, 2),
                "cost_index": cost_idx,
                "parameters": param_results,
            })

        evaluations.sort(key=lambda x: (x["decision"] == "REJECT", x["composite_risk_score"], x["cost_index"]))
        top_status = evaluations[0]["status"] if evaluations else "VIOLATION"
        return {
            "status": top_status,
            "recommended_vendor": evaluations[0]["vendor_id"] if evaluations else None,
            "vendor_rankings": evaluations,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = MaterialQualitySolver.compare_vendors(
            specs=payload.get("specs", {}),
            vendors=payload.get("vendors", []),
            reference_spectrum=payload.get("reference_spectrum"),
            strict_gte=bool(payload.get("strict_gte", True)),
        )
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
