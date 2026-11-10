#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
[Solver Type C] FDC Time-Series Sensor Anomaly, Fraud Scoring & Threshold Optimizer
- 대상 매트릭스 유형:
  * #5 이상 거래 / 어뷰징 탐지 (임계치 룰셋 엔진, 다단계 위험도 스코어링)
  * #8 설비 센서 이상 탐지 (FDC Alert) (3-Sigma UCL/LCL 초과 판정, 이동평균, 드리프트 감지)

[출제 가능한 최적화(Optimization) 문제 및 구현 방식]
  Type C에서는 시계열 센서값이나 트랜잭션 점수가 주어졌을 때 "오탐(False Alarm, 설비 불필요 정지 비용)과
  미탐(Miss, 불량 웨이퍼 유출 비용)의 총합을 최소화하는 최적 알람 임계치(Optimal Threshold)를
  어떻게 설정할 것인가"가 핵심 최적화 문제로 출제될 수 있음:
  1. Cost-Sensitive Optimal Threshold Search (베이즈 비용 최소화 & Youden's J-Statistic):
     - False Positive 비용(C_FP)과 False Negative 비용(C_FN)이 주어졌을 때 전 구간 Grid Search를 통해
       기대 손실 비용 E[Cost] = C_FP * FP(th) + C_FN * FN(th) 를 전역 최소화하는 최적 임계치(th*) 도출.
  2. Tabular CUSUM (누적합 변화점 최적화 탐지):
     - 단일 시점 3-Sigma는 통과하지만 미세하게 평균이 이동(Drift)하는 설비 이상을 가장 빠르게 감지.
================================================================================
"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: List[float]) -> float:
    if len(vals) <= 1:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))


class TypeCSolver:
    @staticmethod
    def analyze_fdc_and_optimize_threshold(
        series: List[Dict[str, Any]],
        baseline_mean: Optional[float] = None,
        baseline_std: Optional[float] = None,
        cost_false_alarm: float = 10.0,
        cost_missed_fault: float = 50.0,
    ) -> Dict[str, Any]:
        clean_pts = []
        for idx, pt in enumerate(series or []):
            if not isinstance(pt, dict):
                continue
            try:
                val = float(pt.get("value", pt.get("sensor_val", pt.get("score", 0.0))))
            except (ValueError, TypeError):
                continue
            if math.isnan(val) or math.isinf(val):
                continue
            label = pt.get("is_actual_fault", pt.get("label", None))
            clean_pts.append({
                "index": idx,
                "timestamp": str(pt.get("timestamp", f"T+{idx:03d}")),
                "value": val,
                "is_actual_fault": bool(label) if label is not None else None,
            })

        if not clean_pts:
            return {"status": "VIOLATION", "reason": "NO_VALID_SERIES"}

        vals = [p["value"] for p in clean_pts]
        mu = float(baseline_mean) if baseline_mean is not None else _mean(vals[: max(5, len(vals) // 2)])
        sigma = float(baseline_std) if (baseline_std is not None and baseline_std > 0) else max(_std(vals[: max(5, len(vals) // 2)]), 1e-4)

        ucl_3sigma = mu + 3.0 * sigma
        lcl_3sigma = mu - 3.0 * sigma

        # Tabular CUSUM (미세 드리프트 탐지: k = 0.5*sigma, h = 4.0*sigma)
        k_allowance = 0.5 * sigma
        h_decision = 4.0 * sigma
        s_pos, s_neg = 0.0, 0.0

        anomalies = []
        z_scores = []
        for i, p in enumerate(clean_pts):
            v = p["value"]
            z = abs(v - mu) / sigma
            z_scores.append(z)
            s_pos = max(0.0, s_pos + (v - mu) - k_allowance)
            s_neg = max(0.0, s_neg - (v - mu) - k_allowance)

            rule_triggered = []
            if v >= ucl_3sigma or v <= lcl_3sigma:
                rule_triggered.append("3_SIGMA_OUT_OF_CONTROL")
            if s_pos >= h_decision or s_neg >= h_decision:
                rule_triggered.append("CUSUM_DRIFT_SHIFT")

            if rule_triggered:
                anomalies.append({
                    "index": p["index"],
                    "timestamp": p["timestamp"],
                    "value": round(v, 4),
                    "z_score": round(z, 3),
                    "cusum_pos": round(s_pos, 3),
                    "cusum_neg": round(s_neg, 3),
                    "rules": rule_triggered,
                })

        # [최적화] 오탐(FP) 비용 vs 미탐(FN) 비용을 최소화하는 최적 Z-Score 임계치 탐색
        candidates = [round(1.0 + 0.1 * step, 2) for step in range(36)]  # Z = 1.0 ~ 4.5
        best_th = 3.0
        min_total_cost = float("inf")
        best_f1 = 0.0

        has_ground_truth = any(p["is_actual_fault"] is not None for p in clean_pts)
        for th in candidates:
            fp, fn, tp = 0, 0, 0
            for p, z in zip(clean_pts, z_scores):
                pred_fault = z >= th
                actual_fault = p["is_actual_fault"] if has_ground_truth else (z >= 2.8)
                if pred_fault and not actual_fault:
                    fp += 1
                elif (not pred_fault) and actual_fault:
                    fn += 1
                elif pred_fault and actual_fault:
                    tp += 1

            expected_cost = cost_false_alarm * fp + cost_missed_fault * fn
            f1 = (2.0 * tp) / max(2.0 * tp + fp + fn, 1.0)
            if expected_cost < min_total_cost:
                min_total_cost = expected_cost
                best_th = th
                best_f1 = f1

        status = "VIOLATION" if len(anomalies) > 0 else "NORMAL"
        return {
            "domain": "TYPE_C_FDC_ANOMALY_DETECTION",
            "status": status,
            "ruleId": "FDC-RULE-OOC" if status == "VIOLATION" else "FDC-RULE-PASS",
            "control_limits": {
                "center_line_mu": round(mu, 4),
                "sigma": round(sigma, 4),
                "ucl_3sigma": round(ucl_3sigma, 4),
                "lcl_3sigma": round(lcl_3sigma, 4),
            },
            "anomaly_count": len(anomalies),
            "detected_anomalies": anomalies,
            "threshold_cost_optimization": {
                "optimization_method": "BAYES_RISK_COST_MINIMIZATION_GRID_SEARCH",
                "optimality": "PROVEN_OPTIMAL_ON_GRID",
                "cost_per_false_alarm": cost_false_alarm,
                "cost_per_missed_fault": cost_missed_fault,
                "optimal_z_threshold": best_th,
                "optimal_ucl": round(mu + best_th * sigma, 4),
                "optimal_lcl": round(mu - best_th * sigma, 4),
                "minimized_expected_loss_cost": round(min_total_cost, 2),
                "f1_score_at_optimum": round(best_f1, 4),
            },
        }

    @classmethod
    def auto_shape_series(cls, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """payload 내부의 'series', 'records', 'data' 등 임의의 테이블에서 시계열/센서 데이터를 자동 추출"""
        if "series" in payload and isinstance(payload["series"], list) and payload["series"]:
            return payload["series"]
        records = payload.get("records") or payload.get("data") or payload.get("rows") or []
        if not isinstance(records, list) or not records:
            return []

        series = []
        val_candidates = ["value", "val", "sensor_val", "score", "reading", "measurement", "rf_power", "temp", "pressure", "측정값", "센서값"]
        time_candidates = ["timestamp", "time", "date", "ts", "step", "index", "시각", "시간"]
        fault_candidates = ["is_actual_fault", "fault", "is_fault", "label", "is_anomaly", "이상여부"]

        for idx, row in enumerate(records):
            if not isinstance(row, dict):
                continue
            lower_map = {str(k).strip().lower(): v for k, v in row.items()}
            v = None
            for c in val_candidates:
                if c.lower() in lower_map:
                    try:
                        v = float(lower_map[c.lower()])
                        break
                    except (ValueError, TypeError):
                        pass
            if v is None:
                continue

            ts = None
            for c in time_candidates:
                if c.lower() in lower_map:
                    ts = str(lower_map[c.lower()])
                    break

            lbl = None
            for c in fault_candidates:
                if c.lower() in lower_map:
                    raw = lower_map[c.lower()]
                    lbl = bool(raw) if raw is not None else None
                    break

            series.append({
                "index": idx,
                "timestamp": ts or f"T+{idx:03d}",
                "value": v,
                "is_actual_fault": lbl,
            })
        return series

    @classmethod
    def solve(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        series = cls.auto_shape_series(payload)
        return cls.analyze_fdc_and_optimize_threshold(
            series=series,
            baseline_mean=payload.get("baseline_mean"),
            baseline_std=payload.get("baseline_std"),
            cost_false_alarm=float(payload.get("cost_false_alarm", 10.0)),
            cost_missed_fault=float(payload.get("cost_missed_fault", 50.0)),
        )


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        inp = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = TypeCSolver.solve(inp)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")