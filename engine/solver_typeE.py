#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
[Solver Type E] Process Recipe Parameter Diff Verifier & Cpk Margin Optimizer
- 대상 매트릭스 유형:
  * #9 공정 레시피 파라미터 검증기 (작업 표준서 Golden Spec vs 실제 장비 레시피 JSON 비교,
       오차 Delta 대조, 공정 마진 부족 리스크 경고 및 파라미터 보정 권고치 산출)

[출제 가능한 최적화(Optimization) 문제 및 구현 방식]
  Type E에서는 표준 스펙(LSL, Target, USL)과 실제 장비 설정값/실측 산포가 주어졌을 때
  "장비 조작 비용(조정폭 페널티)을 최소화하면서 공정 능력 지수(Cpk >= 1.33)와
  목표 출력 특성(예: 증착 두께, 식각률)을 동시에 만족시키는 최적 레시피 보정값(Optimal Parameter Tuning)을
  어떻게 계산할 것인가"가 핵심 최적화 문제로 출제될 수 있음:
  1. Box-Constrained Recipe Centering & Cpk Maximization:
     - 각 파라미터를 허용 범위 [LSL, USL] 내에 강제(Projection)하면서 공정 마진(Cpk)을 극대화하는 목표점 산출.
  2. Constrained Linear Sensitivity Compensation (감도 행렬 기반 최소 노름 보정):
     - 여러 레시피 파라미터(온도, 압력, RF 파워)가 출력 특성(두께 편차 dy)에 미치는 감도(Sensitivity s_i)가 주어졌을 때,
       조작 제약 [LSL_i, USL_i] 하에서 최소한의 파라미터 변경(Min L2 Penalty)으로 출력 오차를 0으로 상쇄하는 최적 보정치 계산.
================================================================================
"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any


class TypeESolver:
    @staticmethod
    def verify_and_optimize_recipe(
        parameters: List[Dict[str, Any]],
        target_output_error: float = 0.0,
        target_cpk: float = 1.33,
    ) -> Dict[str, Any]:
        if not parameters:
            return {"domain": "TYPE_E_RECIPE_VERIFIER", "status": "VIOLATION", "reason": "EMPTY_RECIPE"}

        diffs = []
        out_of_spec_count = 0
        low_margin_count = 0

        # 감도 기반 다변수 보정을 위한 벡터 수집
        sensitivities = []
        avail_up = []
        avail_down = []

        for idx, p in enumerate(parameters):
            if not isinstance(p, dict):
                continue
            pname = str(p.get("param_name", p.get("name", f"PARAM_{idx+1:02d}")))
            target = float(p.get("target", 100.0))
            lsl = float(p.get("lsl", target * 0.9))
            usl = float(p.get("usl", target * 1.1))
            actual = float(p.get("actual", target))
            sigma = max(float(p.get("sigma", (usl - lsl) / 8.0)), 1e-6)
            sens = float(p.get("sensitivity", 0.0))

            delta = actual - target
            half_tol = max((usl - lsl) / 2.0, 1e-6)
            margin_usage_pct = (abs(delta) / half_tol) * 100.0

            cpu = (usl - actual) / (3.0 * sigma)
            cpl = (actual - lsl) / (3.0 * sigma)
            cpk = min(cpu, cpl)
            optimal_cpk = (usl - lsl) / (6.0 * sigma)

            is_oos = (actual < lsl) or (actual > usl)
            is_low_margin = (not is_oos) and (cpk < target_cpk or margin_usage_pct >= 80.0)

            if is_oos:
                out_of_spec_count += 1
            elif is_low_margin:
                low_margin_count += 1

            # Box-Projection을 통한 1차 안전 보정값
            safe_margin = min(half_tol * 0.5, 3.0 * sigma * target_cpk)
            safe_lb = max(lsl, target - (half_tol - safe_margin))
            safe_ub = min(usl, target + (half_tol - safe_margin))
            clamped_val = max(safe_lb, min(safe_ub, target))

            sensitivities.append(sens)
            avail_up.append(max(0.0, safe_ub - clamped_val))
            avail_down.append(max(0.0, clamped_val - safe_lb))

            diffs.append({
                "param_name": pname,
                "unit": str(p.get("unit", "")),
                "lsl": round(lsl, 4),
                "target": round(target, 4),
                "usl": round(usl, 4),
                "actual": round(actual, 4),
                "delta_from_target": round(delta, 4),
                "spec_margin_usage_pct": round(margin_usage_pct, 2),
                "current_cpk": round(cpk, 3),
                "max_achievable_cpk_at_center": round(optimal_cpk, 3),
                "status": "OUT_OF_SPEC" if is_oos else ("LOW_MARGIN_WARN" if is_low_margin else "PASS"),
                "recommended_centered_value": round(clamped_val, 4),
                "recommended_adjustment_delta": round(clamped_val - actual, 4),
            })

        # [최적화] 다변수 감도 보정 (Box-Constrained Minimum-Norm Coordinate Tuning)
        # 공정 출력 편차(target_output_error)를 상쇄하기 위해 각 파라미터의 스펙 마진을 침해하지 않으면서
        # 감도(sensitivity) 비례로 최소한의 노름(L2 Norm) 보정량을 배분
        rem_err = float(target_output_error)
        multi_param_tuning = []
        norm_sq = sum(s * s for s in sensitivities)
        if abs(rem_err) > 1e-6 and norm_sq > 1e-9:
            for i, d in enumerate(diffs):
                s = sensitivities[i]
                if abs(s) < 1e-9:
                    continue
                raw_step = -rem_err * (s / norm_sq)
                bounded_step = max(-avail_down[i], min(avail_up[i], raw_step))
                tuned_val = d["recommended_centered_value"] + bounded_step
                rem_err += s * bounded_step
                multi_param_tuning.append({
                    "param_name": d["param_name"],
                    "sensitivity": s,
                    "tuning_step_from_center": round(bounded_step, 4),
                    "final_optimal_setpoint": round(tuned_val, 4),
                })

        status = "VIOLATION" if out_of_spec_count > 0 else ("WARNING" if low_margin_count > 0 else "NORMAL")
        return {
            "domain": "TYPE_E_RECIPE_VERIFIER",
            "status": status,
            "ruleId": "RECIPE-RULE-OOS" if out_of_spec_count > 0 else (
                "RECIPE-RULE-MARGIN-WARN" if low_margin_count > 0 else "RECIPE-RULE-PASS"
            ),
            "out_of_spec_count": out_of_spec_count,
            "low_margin_warning_count": low_margin_count,
            "parameter_diff_table": diffs,
            "cpk_and_setpoint_optimization": {
                "optimization_method": "BOX_CONSTRAINED_CPK_CENTERING_AND_MIN_NORM_SENSITIVITY_TUNING",
                "target_cpk_threshold": target_cpk,
                "initial_output_error": target_output_error,
                "residual_output_error_after_tuning": round(rem_err, 5),
                "multi_parameter_fine_tuning": multi_param_tuning,
            },
        }

    @classmethod
    def auto_shape_parameters(cls, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """payload 내부의 'parameters', 'records', 'recipe' 등 임의의 테이블에서 레시피 파라미터 데이터를 자동 추출"""
        if "parameters" in payload and isinstance(payload["parameters"], list) and payload["parameters"]:
            return payload["parameters"]
        records = payload.get("records") or payload.get("recipe") or payload.get("data") or payload.get("rows") or []
        if not isinstance(records, list) or not records:
            return []

        name_cands = ["param_name", "parameter", "name", "item", "설정항목", "파라미터", "항목"]
        target_cands = ["target", "golden_spec", "golden", "spec_target", "목표값", "기준값"]
        actual_cands = ["actual", "measured", "current", "val", "value", "실측값", "현재값"]
        lsl_cands = ["lsl", "min", "lower_limit", "하한값"]
        usl_cands = ["usl", "max", "upper_limit", "상한값"]
        sens_cands = ["sensitivity", "sens", "gain", "감도"]
        sigma_cands = ["sigma", "std", "표준편차"]

        params = []
        for idx, row in enumerate(records):
            if not isinstance(row, dict):
                continue
            lower_map = {str(k).strip().lower(): v for k, v in row.items()}

            pname = None
            for c in name_cands:
                if c.lower() in lower_map:
                    pname = str(lower_map[c.lower()])
                    break
            pname = pname or f"PARAM_{idx+1:02d}"

            def _get_float(cands, default_val=None):
                for c in cands:
                    if c.lower() in lower_map:
                        try:
                            return float(lower_map[c.lower()])
                        except (ValueError, TypeError):
                            pass
                return default_val

            tgt = _get_float(target_cands, 100.0)
            act = _get_float(actual_cands, tgt)
            lsl = _get_float(lsl_cands, tgt * 0.9 if tgt is not None else 90.0)
            usl = _get_float(usl_cands, tgt * 1.1 if tgt is not None else 110.0)
            sens = _get_float(sens_cands, 0.0)
            sig = _get_float(sigma_cands, (usl - lsl) / 8.0 if (usl and lsl) else 1.0)

            params.append({
                "param_name": pname,
                "target": tgt,
                "actual": act,
                "lsl": lsl,
                "usl": usl,
                "sensitivity": sens,
                "sigma": sig,
            })
        return params

    @classmethod
    def solve(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        params = cls.auto_shape_parameters(payload)
        return cls.verify_and_optimize_recipe(
            parameters=params,
            target_output_error=float(payload.get("target_output_error", 0.0)),
            target_cpk=float(payload.get("target_cpk", 1.33)),
        )


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        inp = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = TypeESolver.solve(inp)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")