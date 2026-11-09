#!/usr/bin/env python3
"""
Domain Solver 2: Chemical Material Quality (CoA) & Vendor Switching Risk Analyzer

"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any
import numpy as np


class MaterialQualitySolver:
    @staticmethod
    def evaluate_coa_parameter(values: List[float], lsl: float = None, usl: float = None) -> Dict[str, Any]:
        arr = np.array(values, dtype=float)
        if len(arr) == 0:
            raise ValueError("Empty sample array for CoA parameter.")

        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 1e-6
        std = max(std, 1e-6)

        lsl_val = -math.inf if lsl is None else float(lsl)
        usl_val = math.inf if usl is None else float(usl)

        cpu = (usl_val - mean) / (3.0 * std) if usl_val != math.inf else math.inf
        cpl = (mean - lsl_val) / (3.0 * std) if lsl_val != -math.inf else math.inf
        cpk = float(min(cpu, cpl))
        cp = float((usl_val - lsl_val) / (6.0 * std)) if (lsl_val != -math.inf and usl_val != math.inf) else cpk

        oos_indices = [int(i) for i, v in enumerate(arr) if v < lsl_val or v > usl_val]

        # Drift check (slope of linear fit across sequential lots)
        drift_slope = float(np.polyfit(np.arange(len(arr)), arr, 1)[0]) if len(arr) >= 3 else 0.0

        if oos_indices:
            risk_score = 100.0
            status = "REJECT_OOS"
        elif cpk < 1.0:
            risk_score = min(95.0, 75.0 + (1.0 - cpk) * 30.0)
            status = "HIGH_RISK_LOW_CPK"
        elif cpk < 1.33:
            risk_score = 40.0 + (1.33 - cpk) * 100.0
            status = "CONDITIONAL_MARGINAL_CPK"
        else:
            risk_score = max(0.0, 25.0 - (cpk - 1.33) * 15.0)
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

    @classmethod
    def compare_vendors(
        cls,
        specs: Dict[str, Dict[str, float]],
        vendors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        specs: {"metal_ppb": {"LSL": 0, "USL": 5.0, "weight": 0.5}, ...}
        vendors: [{"vendor_id": "V_NEW", "cost_index": 0.88, "lead_time_days": 14, "samples": {...}}, ...]
        """
        total_w = sum(float(s.get("weight", 1.0)) for s in specs.values()) or 1.0
        evaluations = []

        for v in vendors:
            v_id = v.get("vendor_id", "UNKNOWN")
            samples = v.get("samples", {})
            param_results = {}
            weighted_quality_risk = 0.0
            has_hard_reject = False

            for pname, pspec in specs.items():
                w = float(pspec.get("weight", 1.0)) / total_w
                res = cls.evaluate_coa_parameter(
                    samples.get(pname, []),
                    lsl=pspec.get("LSL"),
                    usl=pspec.get("USL"),
                )
                param_results[pname] = res
                weighted_quality_risk += res["risk_score"] * w
                if res["status"] == "REJECT_OOS":
                    has_hard_reject = True

            cost_idx = float(v.get("cost_index", 1.0))
            lead_days = float(v.get("lead_time_days", 14.0))
            supply_chain_risk = max(0.0, (lead_days - 10.0) * 1.5)
            composite_risk = 0.8 * weighted_quality_risk + 0.2 * supply_chain_risk

            if has_hard_reject or weighted_quality_risk >= 70.0:
                decision = "REJECT"
            elif weighted_quality_risk >= 35.0:
                decision = "CONDITIONAL_PILOT_RUN"
            else:
                decision = "APPROVE_MASS_PRODUCTION"

            evaluations.append({
                "vendor_id": v_id,
                "decision": decision,
                "quality_risk_score": round(weighted_quality_risk, 2),
                "supply_chain_risk_score": round(supply_chain_risk, 2),
                "composite_risk_score": round(composite_risk, 2),
                "cost_index": cost_idx,
                "parameters": param_results,
            })

        evaluations.sort(key=lambda x: (x["decision"] == "REJECT", x["composite_risk_score"], x["cost_index"]))
        return {
            "recommended_vendor": evaluations[0]["vendor_id"] if evaluations else None,
            "vendor_rankings": evaluations,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = MaterialQualitySolver.compare_vendors(payload.get("specs", {}), payload.get("vendors", []))
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")