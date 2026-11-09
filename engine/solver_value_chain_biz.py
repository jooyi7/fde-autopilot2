#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Solver 4 (NEW): Value-Chain Dependency Graph, Bullwhip Lead-Time Simulator,
Capital Intensity (ROIC) Portfolio Optimizer & Geopolitical Scenario Tree Engine

"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class ValueChainBusinessSolver:
    @staticmethod
    def simulate_value_chain_bottleneck_and_bullwhip(
        end_demand_shock_pct: float = 5.0,
        wafer_fab_capa_bgb: float = 20.0,
        eds_yield: float = 0.78,
        tsmc_cowos_alloc_bgb: float = 13.5,
        logic_base_die_supply_bgb: float = 14.5,
        substrate_abf_cap_bgb: float = 16.0,
        inventory_amplification_factor: float = 1.65,
    ) -> Dict[str, Any]:
        """
        [해결방안 1] 가치사슬 종속성 그래프(Dependency Graph) 및 리드타임 시차/채찍 효과(Bullwhip Effect) 시뮬레이터:
        전방 CSP 수요 변동(예: +5%)이 상위 단계(패키징 -> Fab -> 전공정 장비/소재 발주)로 전이될 때
        리드타임 시차(Time-lag)와 안전재고 심리에 의해 발주 진폭이 증폭되는 현상과,
        외부 생태계(TSMC CoWoS, Custom Base Die)에 의해 출하 상한선(Ceiling)이 막히는 병목을 정량 계산
        """
        stages = [
            {"stage_order": 1, "node": "CSP_AI_SERVER_DEMAND", "lead_time_months": 1, "shock_pct": round(end_demand_shock_pct, 2)},
            {"stage_order": 2, "node": "FABLESS_GPU_ALLOCATION", "lead_time_months": 3, "shock_pct": round(end_demand_shock_pct * (inventory_amplification_factor ** 1), 2)},
            {"stage_order": 3, "node": "FOUNDRY_COWOS_ADVANCED_PKG", "lead_time_months": 6, "shock_pct": round(end_demand_shock_pct * (inventory_amplification_factor ** 2), 2)},
            {"stage_order": 4, "node": "SK_HYNIX_HBM_FAB_WAFER_IN", "lead_time_months": 9, "shock_pct": round(end_demand_shock_pct * (inventory_amplification_factor ** 3), 2)},
            {"stage_order": 5, "node": "EUV_AND_TSV_EQUIPMENT_CAPEX_ORDER", "lead_time_months": 16, "shock_pct": round(end_demand_shock_pct * (inventory_amplification_factor ** 4), 2)},
        ]

        internal_kghd_output_bgb = wafer_fab_capa_bgb * eds_yield
        ceiling_candidates = {
            "INTERNAL_FAB_AND_EDS_YIELD": internal_kghd_output_bgb,
            "EXTERNAL_FOUNDRY_COWOS_PACKAGING": tsmc_cowos_alloc_bgb,
            "CUSTOM_LOGIC_BASE_DIE_SUPPLY": logic_base_die_supply_bgb,
            "ABF_SUBSTRATE_INTERPOSER_SUPPLY": substrate_abf_cap_bgb,
        }
        binding_node = min(ceiling_candidates, key=ceiling_candidates.get)
        effective_shippable_bgb = ceiling_candidates[binding_node]
        stranded_internal_kghd_bgb = max(0.0, internal_kghd_output_bgb - effective_shippable_bgb)

        return {
            "persona_id": "skhynix-value-chain-business-persona",
            "bullwhip_amplification_chain": stages,
            "upstream_equipment_order_swing_pct": stages[-1]["shock_pct"],
            "cumulative_pipeline_lead_time_months": 16,
            "internal_good_die_output_bgb": round(internal_kghd_output_bgb, 3),
            "effective_shippable_ceiling_bgb": round(effective_shippable_bgb, 3),
            "binding_bottleneck_node": binding_node,
            "stranded_unshipped_die_inventory_bgb": round(stranded_internal_kghd_bgb, 3),
            "ecosystem_bottleneck_constrained": binding_node != "INTERNAL_FAB_AND_EDS_YIELD",
        }

    @staticmethod
    def optimize_capex_roic_portfolio(
        total_capex_budget_musd: float = 12000.0,
        cleanroom_wafer_limit_k: float = 180.0,
        tax_rate: float = 0.22,
        wacc_pct: float = 9.5,
        product_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        [해결방안 2] Bit당 설비투자 효율(Capital Intensity) 및 다이 크기 페널티(Die Penalty)를 반영한 ROIC 최적화
        """
        default_products = [
            {
                "product": "HBM3E_12H_HBM4",
                "capex_per_k_wafer_musd": 95.0,
                "die_penalty_factor": 2.85,
                "bit_per_k_wafer_bgb": 0.52,
                "asp_usd_per_gb": 16.5,
                "op_margin_pct": 54.0,
                "max_demand_wafers_k": 75.0,
            },
            {
                "product": "DDR5_128GB_SERVER_RDIMM",
                "capex_per_k_wafer_musd": 58.0,
                "die_penalty_factor": 1.15,
                "bit_per_k_wafer_bgb": 1.30,
                "asp_usd_per_gb": 4.2,
                "op_margin_pct": 38.0,
                "max_demand_wafers_k": 80.0,
            },
            {
                "product": "ENTERPRISE_ESSD_QLC_300L",
                "capex_per_k_wafer_musd": 42.0,
                "die_penalty_factor": 1.0,
                "bit_per_k_wafer_bgb": 3.80,
                "asp_usd_per_gb": 0.95,
                "op_margin_pct": 28.0,
                "max_demand_wafers_k": 60.0,
            },
        ]
        items = product_candidates if product_candidates else default_products
        evaluated = []

        for p in items:
            capex_k = max(float(p.get("capex_per_k_wafer_musd", 50.0)), 1e-6)
            bits_k = float(p.get("bit_per_k_wafer_bgb", 1.0))
            asp = float(p.get("asp_usd_per_gb", 3.0))
            opm = float(p.get("op_margin_pct", 30.0)) / 100.0
            die_pen = float(p.get("die_penalty_factor", 1.0))

            rev_per_k = bits_k * asp * 1000.0  # MUSD per 1K wafers
            nopat_per_k = rev_per_k * opm * (1.0 - tax_rate)
            roic_pct = (nopat_per_k / capex_k) * 100.0
            eva_spread_pct = roic_pct - wacc_pct
            capital_intensity_usd_per_gb = capex_k / max(bits_k, 1e-6)

            evaluated.append({
                "product": p.get("product", "UNKNOWN"),
                "die_penalty_factor": round(die_pen, 2),
                "capital_intensity_musd_per_bgb": round(capital_intensity_usd_per_gb, 2),
                "roic_pct": round(roic_pct, 2),
                "eva_spread_vs_wacc_pct": round(eva_spread_pct, 2),
                "capex_per_k_wafer_musd": capex_k,
                "nopat_per_k_wafer_musd": round(nopat_per_k, 2),
                "max_demand_wafers_k": float(p.get("max_demand_wafers_k", 50.0)),
            })

        # Sort by ROIC descending to allocate Cleanroom & CAPEX budget greedily
        evaluated.sort(key=lambda x: x["roic_pct"], reverse=True)
        rem_capex = total_capex_budget_musd
        rem_wafers = cleanroom_wafer_limit_k
        allocations = []
        total_nopat = 0.0
        used_capex = 0.0

        for item in evaluated:
            max_by_capex = rem_capex / item["capex_per_k_wafer_musd"]
            alloc_k = min(item["max_demand_wafers_k"], rem_wafers, max_by_capex)
            alloc_k = max(0.0, alloc_k)
            capex_spent = alloc_k * item["capex_per_k_wafer_musd"]
            nopat_gen = alloc_k * item["nopat_per_k_wafer_musd"]

            rem_capex -= capex_spent
            rem_wafers -= alloc_k
            used_capex += capex_spent
            total_nopat += nopat_gen

            allocations.append({
                **item,
                "allocated_wafers_k": round(alloc_k, 2),
                "allocated_capex_musd": round(capex_spent, 2),
                "expected_nopat_musd": round(nopat_gen, 2),
            })

        portfolio_roic = (total_nopat / max(used_capex, 1e-6)) * 100.0
        return {
            "total_capex_budget_musd": total_capex_budget_musd,
            "utilized_capex_musd": round(used_capex, 2),
            "portfolio_weighted_roic_pct": round(portfolio_roic, 2),
            "wacc_hurdle_pct": wacc_pct,
            "value_created_eva_musd": round(total_nopat - (used_capex * (wacc_pct / 100.0)), 2),
            "optimal_product_allocations": allocations,
        }

    @staticmethod
    def build_geopolitical_scenario_tree(
        base_operating_profit_musd: float = 14000.0,
        china_fab_wafer_share_pct: float = 28.0,
        custom_scenarios: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        [해결방안 3] 지정학·공급망 충격에 대한 동적 시나리오 트리(Scenario Tree) 및 컨틴전시 레버 매핑
        """
        default_tree = [
            {
                "scenario_id": "SCEN-BASE",
                "name": "VEU_MAINTAINED_AND_COWOS_EXPANSION",
                "probability": 0.50,
                "op_impact_pct": 0.0,
                "contingency_lever": "Maintain Icheon/Cheongju HBM ramp-up & routine Wuxi legacy node operation",
                "mitigation_recovery_pct": 0.0,
            },
            {
                "scenario_id": "SCEN-EXPORT-TIGHT",
                "name": "CHINA_FAB_EUV_D2R_TOOL_UPGRADE_RESTRICTED",
                "probability": 0.30,
                "op_impact_pct": -14.5,
                "contingency_lever": "Swap Wuxi to specialty DDR4/LPDDR4X cash-cow & concentrate 1b/1c node migration in Icheon M16",
                "mitigation_recovery_pct": 9.5,
            },
            {
                "scenario_id": "SCEN-PKG-SHOCK",
                "name": "FOUNDRY_COWOS_BOTTLENECK_OR_TARIFF_SPIKE",
                "probability": 0.20,
                "op_impact_pct": -18.0,
                "contingency_lever": "Activate dual-OSAT (Amkor/ASE) packaging qualification & adjust HBM4 Base Die supply contract",
                "mitigation_recovery_pct": 12.0,
            },
        ]
        tree = custom_scenarios if custom_scenarios else default_tree
        evaluated_tree = []
        expected_unmitigated_op = 0.0
        expected_mitigated_op = 0.0

        for sc in tree:
            prob = float(sc.get("probability", 0.33))
            imp_pct = float(sc.get("op_impact_pct", 0.0))
            rec_pct = float(sc.get("mitigation_recovery_pct", 0.0))

            unmit_op = base_operating_profit_musd * (1.0 + imp_pct / 100.0)
            mit_op = base_operating_profit_musd * (1.0 + (imp_pct + rec_pct) / 100.0)

            expected_unmitigated_op += prob * unmit_op
            expected_mitigated_op += prob * mit_op

            evaluated_tree.append({
                "scenario_id": sc.get("scenario_id"),
                "name": sc.get("name"),
                "probability": round(prob, 3),
                "unmitigated_op_musd": round(unmit_op, 2),
                "mitigated_op_musd": round(mit_op, 2),
                "net_preserved_profit_musd": round(mit_op - unmit_op, 2),
                "contingency_lever": sc.get("contingency_lever"),
            })

        return {
            "china_fab_exposure_pct": china_fab_wafer_share_pct,
            "expected_unmitigated_op_musd": round(expected_unmitigated_op, 2),
            "expected_mitigated_op_musd": round(expected_mitigated_op, 2),
            "contingency_value_preserved_musd": round(expected_mitigated_op - expected_unmitigated_op, 2),
            "scenario_branches": evaluated_tree,
        }

    @classmethod
    def solve_all(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        vc_res = cls.simulate_value_chain_bottleneck_and_bullwhip(
            end_demand_shock_pct=float(payload.get("end_demand_shock_pct", 5.0)),
            wafer_fab_capa_bgb=float(payload.get("wafer_fab_capa_bgb", 20.0)),
            eds_yield=float(payload.get("eds_yield", 0.78)),
            tsmc_cowos_alloc_bgb=float(payload.get("tsmc_cowos_alloc_bgb", 13.5)),
            logic_base_die_supply_bgb=float(payload.get("logic_base_die_supply_bgb", 14.5)),
        )
        roic_res = cls.optimize_capex_roic_portfolio(
            total_capex_budget_musd=float(payload.get("total_capex_budget_musd", 12000.0)),
            cleanroom_wafer_limit_k=float(payload.get("cleanroom_wafer_limit_k", 180.0)),
            product_candidates=payload.get("product_candidates"),
        )
        geo_res = cls.build_geopolitical_scenario_tree(
            base_operating_profit_musd=float(payload.get("base_operating_profit_musd", 14000.0)),
            custom_scenarios=payload.get("custom_scenarios"),
        )

        status = "WARNING" if vc_res["ecosystem_bottleneck_constrained"] else "NORMAL"
        return {
            "persona_id": "skhynix-value-chain-business-persona",
            "status": status,
            "ruleId": "VCBIZ-RULE-BOTTLENECK-CHECK",
            "value_chain_and_bullwhip_analysis": vc_res,
            "capex_roic_optimization": roic_res,
            "geopolitical_scenario_tree": geo_res,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = ValueChainBusinessSolver.solve_all(payload)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
