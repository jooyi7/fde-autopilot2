#!/usr/bin/env python3
"""
Domain Solver 3: Memory (DRAM / HBM / NAND) Supply-Demand, CAPA & ASP Optimizer

"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import numpy as np


class MarketStrategySolver:
    @staticmethod
    def simulate_allocation_grid(
        total_wafer_capa_k: float,
        hbm_die_penalty: float = 2.8,
        hbm_yield: float = 0.65,
        dram_yield: float = 0.88,
        base_dram_asp: float = 3.5,
        base_hbm_asp: float = 16.0,
        dram_cost_per_gb: float = 1.8,
        hbm_cost_per_gb: float = 7.2,
        market_dram_demand_bgb: float = 120.0,
        market_hbm_demand_bgb: float = 18.0,
        competitor_dram_supply_bgb: float = 75.0,
        competitor_hbm_supply_bgb: float = 8.0,
        tsv_packaging_cap_bgb: float = 12.0,
    ) -> Dict[str, Any]:
        """
        Evaluates HBM wafer allocation from 5% to 50% to find profit-maximizing mix
        under TSV/CoWoS packaging bottleneck constraints.
        """
        raw_gb_per_k_wafer = 1.5  # Base Gb per 1K wafers at 100% yield
        scenarios = []
        best_scenario = None

        for pct in range(5, 55, 5):
            hbm_ratio = pct / 100.0
            hbm_wafers_k = total_wafer_capa_k * hbm_ratio
            dram_wafers_k = total_wafer_capa_k * (1.0 - hbm_ratio)

            raw_hbm_bgb = hbm_wafers_k * (raw_gb_per_k_wafer / hbm_die_penalty) * hbm_yield
            effective_hbm_bgb = min(raw_hbm_bgb, tsv_packaging_cap_bgb)
            tsv_bottleneck_loss_bgb = max(0.0, raw_hbm_bgb - effective_hbm_bgb)

            effective_dram_bgb = dram_wafers_k * raw_gb_per_k_wafer * dram_yield

            total_mkt_dram_supply = competitor_dram_supply_bgb + effective_dram_bgb
            total_mkt_hbm_supply = competitor_hbm_supply_bgb + effective_hbm_bgb

            dram_oversupply_ratio = (total_mkt_dram_supply - market_dram_demand_bgb) / max(market_dram_demand_bgb, 1e-6)
            hbm_oversupply_ratio = (total_mkt_hbm_supply - market_hbm_demand_bgb) / max(market_hbm_demand_bgb, 1e-6)

            # Price elasticity model: undersupply drives ASP up, oversupply drives ASP down
            proj_dram_asp = base_dram_asp * max(0.5, 1.0 - 1.4 * dram_oversupply_ratio)
            proj_hbm_asp = base_hbm_asp * max(0.7, 1.0 - 0.8 * hbm_oversupply_ratio)

            dram_rev = effective_dram_bgb * proj_dram_asp
            hbm_rev = effective_hbm_bgb * proj_hbm_asp
            dram_op = effective_dram_bgb * (proj_dram_asp - dram_cost_per_gb)
            # Unpackaged HBM wafers still incur wafer cost
            hbm_op = (effective_hbm_bgb * proj_hbm_asp) - (raw_hbm_bgb * hbm_cost_per_gb)
            total_op = dram_op + hbm_op

            row = {
                "hbm_wafer_share_pct": pct,
                "hbm_wafers_k": round(hbm_wafers_k, 2),
                "dram_wafers_k": round(dram_wafers_k, 2),
                "effective_hbm_output_bgb": round(effective_hbm_bgb, 2),
                "tsv_bottleneck_clipped_bgb": round(tsv_bottleneck_loss_bgb, 2),
                "effective_dram_output_bgb": round(effective_dram_bgb, 2),
                "market_dram_sufficiency_pct": round(dram_oversupply_ratio * 100.0, 2),
                "market_hbm_sufficiency_pct": round(hbm_oversupply_ratio * 100.0, 2),
                "projected_dram_asp_usd": round(proj_dram_asp, 3),
                "projected_hbm_asp_usd": round(proj_hbm_asp, 3),
                "total_revenue_musd": round(dram_rev + hbm_rev, 2),
                "total_operating_profit_musd": round(total_op, 2),
                "operating_margin_pct": round((total_op / max(dram_rev + hbm_rev, 1e-6)) * 100.0, 2),
            }
            scenarios.append(row)
            if best_scenario is None or row["total_operating_profit_musd"] > best_scenario["total_operating_profit_musd"]:
                best_scenario = row

        return {
            "optimal_strategy": best_scenario,
            "scenario_table": scenarios,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = MarketStrategySolver.simulate_allocation_grid(**payload)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")