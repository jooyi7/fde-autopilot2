#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
[Solver Type B] Wafer Map Spatial Defect, Yield Loss Decomposition & Budget Optimizer
- 대상 매트릭스 유형:
  * #2 비정형 데이터 분석 & 리포트 (CSV/설문 결측치 정제, 통계 합산, 불량/불만 군집화)
  * #7 웨이퍼 맵(Wafer Map) 결함 분석 (Wafer X,Y 기반 Fail Die 비율, Ring/Scratch/Center 분류)
  * #10 수율(Yield) 손실 요인 분해 계산기 (스텝별 누적 수율 곱연산, Worst Step 병목 도출)

[출제 가능한 최적화(Optimization) 문제 및 구현 방식]
  Type B에서는 불량 분포와 스텝별 수율을 계산한 뒤 "제한된 리페어 자원이나 개선 예산을
  어디에 투입해야 수율(Yield)을 극대화할 수 있는가"를 묻는 최적화 문제가 출제될 수 있음:
  1. Yield Improvement Budget Allocation (0-1 Knapsack Dynamic Programming):
     - 각 공정 스텝별 개선 비용(Cost)과 예상 수율 향상폭(Delta Yield)이 주어졌을 때,
       총 예산(Budget) 제약 내에서 최종 누적 수율 상승분을 극대화하는 최적 개선 스텝 조합 도출.
  2. Spatial Defect Cluster Bounding & Redundancy Repair Allocation (탐욕적 커버리지 최적화):
     - 8-방향 연결 요소 탐색(BFS Connected Components)으로 불량 다이 클러스터를 군집화하고,
       제한된 스페어 리던던시(Spare Row/Col)로 복구 가능한 다이 수를 최대화.
================================================================================
"""

import json
import math
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Any, Tuple


class TypeBSolver:
    # -------------------------------------------------------------------------
    # 1. [#7 웨이퍼 맵 결함 분석] 공간 클러스터링(BFS) 및 Ring / Scratch / Center 판정
    # -------------------------------------------------------------------------
    @staticmethod
    def analyze_wafer_map(
        dies: List[Dict[str, Any]],
        wafer_radius: float = 150.0,
        spare_repair_limit: int = 10,
    ) -> Dict[str, Any]:
        if not dies:
            return {"total_dies": 0, "fail_dies": 0, "yield_pct": 0.0, "dominant_pattern": "NO_DATA"}

        total_dies = 0
        fail_coords: List[Tuple[int, int, float, float, str]] = []
        grid_fail_map: Dict[Tuple[int, int], Dict[str, Any]] = {}

        for d in dies:
            if not isinstance(d, dict):
                continue
            try:
                gx = int(round(float(d.get("x", d.get("X", d.get("col", 0))))))
                gy = int(round(float(d.get("y", d.get("Y", d.get("row", 0))))))
                rx = float(d.get("rx_mm", gx))
                ry = float(d.get("ry_mm", gy))
            except (ValueError, TypeError):
                continue

            total_dies += 1
            is_fail = bool(d.get("is_fail", False)) or str(d.get("status", "PASS")).upper() in {"FAIL", "BAD", "1", "NG"}
            bin_code = str(d.get("bin", "BIN_01" if not is_fail else "BIN_99"))
            if is_fail:
                fail_coords.append((gx, gy, rx, ry, bin_code))
                grid_fail_map[(gx, gy)] = {"gx": gx, "gy": gy, "rx": rx, "ry": ry, "bin": bin_code}

        fail_count = len(fail_coords)
        yield_pct = ((total_dies - fail_count) / max(total_dies, 1)) * 100.0

        if fail_count == 0:
            return {
                "total_dies": total_dies,
                "fail_dies": 0,
                "yield_pct": 100.0,
                "dominant_pattern": "CLEAN_WAFER",
                "suspected_process": "NONE",
            }

        # 반경 비율 분석 (Edge Ring vs Center Bullseye)
        max_r = max([math.hypot(c[2], c[3]) for c in fail_coords] + [1.0])
        eff_radius = wafer_radius if max_r > 30.0 else max_r
        edge_fails = sum(1 for c in fail_coords if math.hypot(c[2], c[3]) >= 0.78 * eff_radius)
        center_fails = sum(1 for c in fail_coords if math.hypot(c[2], c[3]) <= 0.32 * eff_radius)
        edge_ratio = edge_fails / fail_count
        center_ratio = center_fails / fail_count

        # 주성분 고유값 비율(Eigenvalue Ratio)로 선형 스크래치(Scratch) 여부 판정
        mx = sum(c[0] for c in fail_coords) / fail_count
        my = sum(c[1] for c in fail_coords) / fail_count
        sxx = sum((c[0] - mx) ** 2 for c in fail_coords) / fail_count
        syy = sum((c[1] - my) ** 2 for c in fail_coords) / fail_count
        sxy = sum((c[0] - mx) * (c[1] - my) for c in fail_coords) / fail_count
        trace = sxx + syy
        det = sxx * syy - sxy * sxy
        disc = math.sqrt(max(0.0, (trace / 2.0) ** 2 - det))
        lambda1 = trace / 2.0 + disc
        lambda2 = max(1e-6, trace / 2.0 - disc)
        aspect_ratio = lambda1 / lambda2

        # 8-방향 BFS 클러스터링
        visited = set()
        clusters = []
        for pt in grid_fail_map:
            if pt in visited:
                continue
            q = deque([pt])
            visited.add(pt)
            comp = []
            while q:
                cx, cy = q.popleft()
                comp.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nb = (cx + dx, cy + dy)
                        if nb in grid_fail_map and nb not in visited:
                            visited.add(nb)
                            q.append(nb)
            clusters.append(comp)
        clusters.sort(key=len, reverse=True)
        largest_cluster_size = len(clusters[0]) if clusters else 0

        # 패턴 분류 룰
        if edge_ratio >= 0.60:
            pattern = "EDGE_RING"
            process_cause = "ETCH_CHAMBER_PLASMA_EDGE_OR_SPIN_COAT_BEAD"
        elif aspect_ratio >= 8.0 and largest_cluster_size >= max(4, int(fail_count * 0.4)):
            pattern = "LINEAR_SCRATCH"
            process_cause = "CMP_SLURRY_AGGLOMERATION_OR_ROBOT_HANDLING"
        elif center_ratio >= 0.55:
            pattern = "CENTER_BULLSEYE"
            process_cause = "CVD_GAS_SHOWERHEAD_CENTER_CONCENTRATION"
        elif largest_cluster_size >= max(6, int(fail_count * 0.5)):
            pattern = "LOCAL_CLUSTER"
            process_cause = "PARTICLE_CONTAMINATION_OR_HOTSPOT"
        else:
            pattern = "RANDOM_SCATTER"
            process_cause = "BACKGROUND_DEFECT_DENSITY"

        # [최적화] Redundancy Row/Col Line Cover Optimization (Greedy Maximum Line Cover)
        # 제한된 스페어 라인(spare_repair_limit)으로 가장 많은 불량 다이를 복구하는 Row/Col 선택
        uncovered = set(grid_fail_map.keys())
        repair_lines = []
        for _ in range(max(0, int(spare_repair_limit))):
            if not uncovered:
                break
            row_counts: Dict[int, int] = {}
            col_counts: Dict[int, int] = {}
            for gx, gy in uncovered:
                col_counts[gx] = col_counts.get(gx, 0) + 1
                row_counts[gy] = row_counts.get(gy, 0) + 1
            best_row = max(row_counts.items(), key=lambda x: x[1]) if row_counts else (-1, 0)
            best_col = max(col_counts.items(), key=lambda x: x[1]) if col_counts else (-1, 0)
            if best_row[1] >= best_col[1]:
                r_idx, cnt = best_row
                repair_lines.append({"axis": "ROW", "index": r_idx, "repaired_dies": cnt})
                uncovered = {(gx, gy) for (gx, gy) in uncovered if gy != r_idx}
            else:
                c_idx, cnt = best_col
                repair_lines.append({"axis": "COL", "index": c_idx, "repaired_dies": cnt})
                uncovered = {(gx, gy) for (gx, gy) in uncovered if gx != c_idx}

        repaired_count = fail_count - len(uncovered)
        post_repair_yield = ((total_dies - len(uncovered)) / max(total_dies, 1)) * 100.0

        return {
            "total_dies": total_dies,
            "fail_dies": fail_count,
            "base_yield_pct": round(yield_pct, 2),
            "dominant_pattern": pattern,
            "suspected_process": process_cause,
            "spatial_metrics": {
                "edge_fail_ratio": round(edge_ratio, 4),
                "center_fail_ratio": round(center_ratio, 4),
                "pca_linearity_aspect_ratio": round(aspect_ratio, 3),
                "cluster_count": len(clusters),
                "largest_cluster_size": largest_cluster_size,
            },
            "redundancy_repair_optimization": {
                "optimization_method": "GREEDY_MAX_LINE_COVER",
                "spare_line_budget": spare_repair_limit,
                "repaired_die_count": repaired_count,
                "post_repair_yield_pct": round(post_repair_yield, 2),
                "allocated_repair_lines": repair_lines,
            },
        }

    # -------------------------------------------------------------------------
    # 2. [#10 수율 손실 분해 & 예산 최적화] 누적 수율 계산 + 0-1 Knapsack 예산 배분
    # -------------------------------------------------------------------------
    @staticmethod
    def optimize_yield_loss_and_budget(
        steps: List[Dict[str, Any]],
        total_budget: float = 100.0,
    ) -> Dict[str, Any]:
        if not steps:
            return {"cumulative_yield_pct": 0.0, "worst_step_id": "NONE"}

        cum_yield = 1.0
        step_breakdown = []
        worst_step = None
        min_step_yield = 2.0

        for idx, st in enumerate(steps):
            sid = str(st.get("step_id", f"STEP-{idx+1:02d}"))
            y_rate = float(st.get("step_yield_pct", 99.0)) / 100.0
            y_rate = max(0.0001, min(1.0, y_rate))
            cum_yield *= y_rate
            loss_ppm = round((1.0 - y_rate) * 1_000_000)

            cost = float(st.get("improvement_cost", 25.0))
            potential_gain_pct = float(st.get("potential_yield_gain_pct", (1.0 - y_rate) * 50.0))

            rec = {
                "step_id": sid,
                "step_name": str(st.get("step_name", sid)),
                "step_yield_pct": round(y_rate * 100.0, 3),
                "loss_ppm": loss_ppm,
                "cumulative_yield_after_step_pct": round(cum_yield * 100.0, 3),
                "improvement_cost": cost,
                "potential_yield_gain_pct": round(potential_gain_pct, 3),
            }
            step_breakdown.append(rec)
            if y_rate < min_step_yield:
                min_step_yield = y_rate
                worst_step = rec

        # [최적화] 0-1 Knapsack DP: 주어진 개선 예산(total_budget)으로 수율 향상폭 합 최대화
        B = max(1, int(round(total_budget)))
        n = len(step_breakdown)
        dp = [[0.0] * (B + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            st = step_breakdown[i - 1]
            c = max(1, int(round(st["improvement_cost"])))
            g = st["potential_yield_gain_pct"]
            for b in range(B + 1):
                dp[i][b] = dp[i - 1][b]
                if b >= c and dp[i - 1][b - c] + g > dp[i][b]:
                    dp[i][b] = dp[i - 1][b - c] + g

        selected_investments = []
        rem_b = B
        for i in range(n, 0, -1):
            if abs(dp[i][rem_b] - dp[i - 1][rem_b]) > 1e-6:
                st = step_breakdown[i - 1]
                c = max(1, int(round(st["improvement_cost"])))
                selected_investments.append({
                    "step_id": st["step_id"],
                    "cost": c,
                    "expected_yield_gain_pct": st["potential_yield_gain_pct"],
                })
                rem_b -= c
        selected_investments.reverse()

        projected_cum_yield = cum_yield
        chosen_ids = {s["step_id"] for s in selected_investments}
        for st in step_breakdown:
            base_y = st["step_yield_pct"] / 100.0
            if st["step_id"] in chosen_ids:
                new_y = min(1.0, base_y + st["potential_yield_gain_pct"] / 100.0)
                projected_cum_yield = (projected_cum_yield / base_y) * new_y

        return {
            "baseline_cumulative_yield_pct": round(cum_yield * 100.0, 3),
            "worst_bottleneck_step": worst_step,
            "step_breakdown": step_breakdown,
            "budget_allocation_optimization": {
                "optimization_method": "0_1_KNAPSACK_YIELD_MAXIMIZATION",
                "optimality": "PROVEN_OPTIMAL",
                "total_budget": B,
                "spent_budget": B - rem_b,
                "projected_cumulative_yield_pct": round(projected_cum_yield * 100.0, 3),
                "selected_steps_for_improvement": selected_investments,
            },
        }

    @classmethod
    def auto_shape_payload(cls, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """payload 내부의 'records', 'dies', 'steps' 등에서 웨이퍼 다이 좌표 및 공정 스텝 수율 데이터를 자동 분리/추출"""
        dies = list(payload.get("dies") or [])
        steps = list(payload.get("steps") or [])

        records = payload.get("records") or payload.get("data") or payload.get("rows") or []
        if isinstance(records, list) and records:
            first_row = records[0] if isinstance(records[0], dict) else {}
            cols_lower = {str(k).strip().lower() for k in first_row.keys()}
            if not dies and any(k in cols_lower for k in ("x", "gx", "col", "coord_x", "die_x")):
                for idx, r in enumerate(records):
                    if not isinstance(r, dict):
                        continue
                    lmap = {str(k).strip().lower(): v for k, v in r.items()}
                    gx = lmap.get("x") or lmap.get("gx") or lmap.get("col") or lmap.get("die_x") or 0
                    gy = lmap.get("y") or lmap.get("gy") or lmap.get("row") or lmap.get("die_y") or 0
                    fail_raw = lmap.get("is_fail") or lmap.get("fail") or lmap.get("status") or lmap.get("result") or False
                    is_f = str(fail_raw).upper() in {"TRUE", "1", "FAIL", "BAD", "NG"}
                    dies.append({
                        "x": gx,
                        "y": gy,
                        "is_fail": is_f,
                        "bin": str(lmap.get("bin", "BIN_99" if is_f else "BIN_01")),
                    })
            if not steps and any(k in cols_lower for k in ("step_id", "step_name", "step_yield_pct", "step_yield", "loss_ppm")):
                for idx, r in enumerate(records):
                    if not isinstance(r, dict):
                        continue
                    lmap = {str(k).strip().lower(): v for k, v in r.items()}
                    sid = lmap.get("step_id") or lmap.get("step") or f"STEP-{idx+1:02d}"
                    y_val = lmap.get("step_yield_pct") or lmap.get("step_yield") or lmap.get("yield_pct") or lmap.get("yield") or 99.0
                    cost = lmap.get("improvement_cost") or lmap.get("cost") or 25.0
                    gain = lmap.get("potential_yield_gain_pct") or lmap.get("potential_gain") or 1.5
                    steps.append({
                        "step_id": str(sid),
                        "step_name": str(lmap.get("step_name", sid)),
                        "step_yield_pct": float(y_val),
                        "improvement_cost": float(cost),
                        "potential_yield_gain_pct": float(gain),
                    })
        return dies, steps

    @classmethod
    def solve(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        dies, steps = cls.auto_shape_payload(payload)
        wafer_res = cls.analyze_wafer_map(
            dies=dies,
            wafer_radius=float(payload.get("wafer_radius", 150.0)),
            spare_repair_limit=int(payload.get("spare_repair_limit", 10)),
        )
        yield_res = cls.optimize_yield_loss_and_budget(
            steps=steps,
            total_budget=float(payload.get("total_budget", 100.0)),
        )

        low_yield = (wafer_res.get("base_yield_pct", 100.0) < 75.0) or (yield_res.get("baseline_cumulative_yield_pct", 100.0) < 75.0)
        return {
            "domain": "TYPE_B_WAFER_YIELD_ANALYTICS",
            "status": "VIOLATION" if low_yield else "NORMAL",
            "ruleId": "RULE-TYPEB-YIELD-HOLD" if low_yield else "RULE-TYPEB-PASS",
            "wafer_map_analysis": wafer_res,
            "yield_decomposition": yield_res,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        inp = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = TypeBSolver.solve(inp)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")