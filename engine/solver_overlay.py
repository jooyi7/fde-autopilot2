#!/usr/bin/env python3
"""
Domain Solver 1: Photolithography Overlay & APC Optimizer
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import numpy as np


class OverlaySolver:
    @staticmethod
    def build_design_matrix(records: List[Dict[str, float]], order: int = 1) -> np.ndarray:
        rows = []
        for r in records:
            X, Y = float(r.get("X", 0.0)), float(r.get("Y", 0.0))
            x, y = float(r.get("x", 0.0)), float(r.get("y", 0.0))
            # Order 1: Wafer Linear (Tx, Mx*X, -Rx*Y) + Field Linear (mx*x, -rx*y)
            feat = [1.0, X, Y, x, y]
            if order >= 2:
                feat.extend([X**2, Y**2, X * Y, x**2, y**2, x * y, X * x, Y * y])
            if order >= 3:
                feat.extend([X**3, Y**3, (X**2) * Y, X * (Y**2)])
            rows.append(feat)
        return np.array(rows, dtype=float)

    @classmethod
    def solve_apc(
        cls,
        measurements: List[Dict[str, float]],
        m3s_spec_nm: float = 2.0,
        max_order: int = 2,
        outlier_z: float = 3.5,
    ) -> Dict[str, Any]:
        if not measurements:
            raise ValueError("Empty measurements list.")

        dx_raw = np.array([float(m["dx"]) for m in measurements], dtype=float)
        dy_raw = np.array([float(m["dy"]) for m in measurements], dtype=float)

        # IQR / Z-score 기반 계측 노이즈(Flyer/Outlier) 마스킹
        zx = np.abs((dx_raw - np.mean(dx_raw)) / max(np.std(dx_raw), 1e-6))
        zy = np.abs((dy_raw - np.mean(dy_raw)) / max(np.std(dy_raw), 1e-6))
        valid_mask = (zx <= outlier_z) & (zy <= outlier_z)
        if np.sum(valid_mask) < max(6, len(measurements) // 2):
            valid_mask = np.ones(len(measurements), dtype=bool)

        clean_records = [m for m, v in zip(measurements, valid_mask) if v]
        dx_clean = dx_raw[valid_mask]
        dy_clean = dy_raw[valid_mask]

        best_result = None
        for order in range(1, max_order + 1):
            A_clean = cls.build_design_matrix(clean_records, order=order)
            A_full = cls.build_design_matrix(measurements, order=order)

            # Ridge regularization (L2) to prevent overfitting on edge shots
            lam = 1e-6 * np.eye(A_clean.shape[1])
            coeff_x = np.linalg.solve(A_clean.T @ A_clean + lam, A_clean.T @ dx_clean)
            coeff_y = np.linalg.solve(A_clean.T @ A_clean + lam, A_clean.T @ dy_clean)

            res_x = dx_raw - (A_full @ coeff_x)
            res_y = dy_raw - (A_full @ coeff_y)

            before_m3s_x = float(np.abs(np.mean(dx_raw)) + 3.0 * np.std(dx_raw))
            before_m3s_y = float(np.abs(np.mean(dy_raw)) + 3.0 * np.std(dy_raw))
            after_m3s_x = float(np.abs(np.mean(res_x)) + 3.0 * np.std(res_x))
            after_m3s_y = float(np.abs(np.mean(res_y)) + 3.0 * np.std(res_y))

            rework_flag = (after_m3s_x > m3s_spec_nm) or (after_m3s_y > m3s_spec_nm)

            shot_violations = []
            for idx, (rx, ry) in enumerate(zip(res_x, res_y)):
                radial_err = float(np.hypot(rx, ry))
                if radial_err > m3s_spec_nm:
                    shot_violations.append({
                        "shot_index": idx,
                        "X": measurements[idx].get("X"),
                        "Y": measurements[idx].get("Y"),
                        "residual_dx": round(float(rx), 4),
                        "residual_dy": round(float(ry), 4),
                        "radial_error_nm": round(radial_err, 4),
                    })

            candidate = {
                "selected_order": order,
                "outliers_filtered": int(np.sum(~valid_mask)),
                "spec_limit_nm": m3s_spec_nm,
                "disposition": "REWORK_REQUIRED" if rework_flag else "PASS_INLINE",
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
            max_order=int(payload.get("max_order", 2)),
        )
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")