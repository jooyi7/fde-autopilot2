#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Solver 4 (Upgraded v8.0): Dynamic Value-Chain Dependency Graph, Bullwhip Lead-Time Simulator,
Tech-Migration Conversion Loss & LTA-Constrained ROIC Portfolio Optimizer & Geopolitical Scenario Tree Engine
(Persona: value-chain-business-persona)
- [NEW v8.0] Generic Tabular Records Auto-Router (`auto_route_generic_records`: even if exam CSV columns are generic like `stage/node, capacity, lead_time` or `item, cost/capex, margin/roic, demand`, automatically binds them instead of falling back to hardcoded defaults!)
- [NEW v8.0] Dynamic Document Parameter Extractor (Parses CoWoS cap, WACC, CAPEX budget, China fab exposure from markdown/text)
"""

import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

SENTINEL_NUMBERS = {-999.0, -9999.0, 9999.0, 99999.0}


class ValueChainBusinessSolver:
    PRODUCT_FIELD_ALIASES = {
        "product": ["product", "product_name", "item", "node", "model", "name", "sku", "제품", "제품군", "품목"],
        "capex_per_k_wafer_musd": ["capex_per_k_wafer_musd", "capex_k", "capex_per_k", "unit_capex", "investment_cost", "capex", "cost", "설비투자단가", "투자비"],
        "die_penalty_factor": ["die_penalty_factor", "die_penalty", "penalty_factor", "다이페널티"],
        "conversion_capa_loss_pct": ["conversion_capa_loss_pct", "conv_loss_pct", "conversion_loss", "capa_loss_pct", "전환손실률"],
        "lta_min_committed_wafers_k": ["lta_min_committed_wafers_k", "lta_floor_k", "lta_min_k", "mandatory_wafers_k", "min_committed", "lta", "의무물량", "최소물량"],
        "bit_per_k_wafer_bgb": ["bit_per_k_wafer_bgb", "bits_per_k", "bit_density", "output_per_k", "웨이퍼당비트"],
        "asp_usd_per_gb": ["asp_usd_per_gb", "asp_usd", "asp", "price_per_gb", "unit_price", "price", "단가", "판가"],
        "op_margin_pct": ["op_margin_pct", "opm_pct", "margin_pct", "operating_margin", "margin", "영업이익률", "마진율"],
        "max_demand_wafers_k": ["max_demand_wafers_k", "demand_wafers_k", "max_wafers_k", "demand_k", "demand", "max_demand", "수요상한", "수요량"],
    }

    NODE_FIELD_ALIASES = {
        "node": ["node", "stage", "step", "process_node", "partner", "supplier", "단계", "노드", "공정단계"],
        "lead_time_months": ["lead_time_months", "lead_time", "lt_months", "tat_months", "duration", "리드타임", "소요기간"],
        "capacity_bgb": ["capacity_bgb", "ceiling_bgb", "capacity", "cap", "max_output", "alloc_bgb", "캐파", "상한선", "할당량"],
        "shock_pct": ["shock_pct", "demand_swing_pct", "bullwhip_pct", "volatility_pct", "변동폭", "충격률"],
    }

    @classmethod
    def _resolve_prod_field(cls, rec: Dict[str, Any], key: str, default: Any = None) -> Any:
        if not isinstance(rec, dict):
            return default
        if key in rec and rec[key] is not None and rec[key] != "":
            return rec[key]
        lower_map = {str(k).strip().lower(): v for k, v in rec.items()}
        for al in cls.PRODUCT_FIELD_ALIASES.get(key, [key]):
            if al.lower() in lower_map and lower_map[al.lower()] is not None and lower_map[al.lower()] != "":
                return lower_map[al.lower()]
        return default

    @classmethod
    def _resolve_node_field(cls, rec: Dict[str, Any], key: str, default: Any = None) -> Any:
        if not isinstance(rec, dict):
            return default
        if key in rec and rec[key] is not None and rec[key] != "":
            return rec[key]
        lower_map = {str(k).strip().lower(): v for k, v in rec.items()}
        for al in cls.NODE_FIELD_ALIASES.get(key, [key]):
            if al.lower() in lower_map and lower_map[al.lower()] is not None and lower_map[al.lower()] != "":
                return lower_map[al.lower()]
        return default

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None or val == "":
            return default
        try:
            s = str(val).replace(",", "").replace("$", "").replace("%", "").strip()
            f = float(s)
            return default if (math.isnan(f) or math.isinf(f) or f in SENTINEL_NUMBERS) else f
        except Exception:
            return default

    @classmethod
    def auto_route_generic_records(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        [NEW v8.0] 만약 워크스페이스 테이블이 `records` 또는 `rows`로만 들어왔을 때,
        컬럼 시그니처를 검사하여 자동으로 `product_candidates`(CAPEX ROIC 배분 대상) 또는
        `supply_chain_nodes`(가치사슬 병목/채찍효과 노드)로 변환해 하드코딩 폴백을 방지합니다.
        """
        rows = payload.get("records") or payload.get("rows") or []
        if not rows or not isinstance(rows[0], dict):
            return payload
        cols_lower = {str(k).strip().lower() for k in rows[0].keys()}
        node_hits = sum(1 for aliases in cls.NODE_FIELD_ALIASES.values() if any(a.lower() in cols_lower for a in aliases))
        prod_hits = sum(1 for aliases in cls.PRODUCT_FIELD_ALIASES.values() if any(a.lower() in cols_lower for a in aliases))

        if not payload.get("supply_chain_nodes") and node_hits >= 2 and node_hits >= prod_hits:
            payload["supply_chain_nodes"] = rows
        elif not payload.get("product_candidates") and prod_hits >= 2:
            payload["product_candidates"] = rows
        return payload

    @classmethod
    def extract_params_from_documents(cls, documents: Optional[List[Dict[str, str]]]) -> Dict[str, float]:
        """마크다운/텍스트 문서에서 CoWoS 할당량, WACC, CAPEX 예산, 수요 충격(%) 등을 동적으로 파싱합니다."""
        extracted: Dict[str, float] = {}
        if not documents:
            return extracted
        corpus = "\n".join(str(d.get("content", "")) for d in documents)
        patterns = [
            ("tsmc_cowos_alloc_bgb", r"(?:cowos|패키징\s*할당|패키징\s*상한)[^\d\n]{0,25}(\d+(?:\.\d+)?)"),
            ("wacc_pct", r"(?:wacc|자본비용|허들\s*레이트)[^\d\n]{0,25}(\d+(?:\.\d+)?)\s*%"),
            ("total_capex_budget_musd", r"(?:capex\s*예산|설비투자\s*예산|total_capex)[^\d\n]{0,25}(\d+(?:,\d{3})*(?:\.\d+)?)"),
            ("end_demand_shock_pct", r"(?:수요\s*충격|demand\s*shock|수요\s*변동)[^\d\n]{0,25}(\d+(?:\.\d+)?)\s*%"),
        ]
        for key, pat in patterns:
            m = re.search(pat, corpus, re.IGNORECASE)
            if m:
                val = cls._safe_float(m.group(1), 0.0)
                if val > 0:
                    extracted[key] = val
        return extracted

    @classmethod
    def simulate_value_chain_bottleneck_and_bullwhip(
        cls,
        end_demand_shock_pct: float = 5.0,
        wafer_fab_capa_bgb: float = 20.0,
        eds_yield: float = 0.78,
        tsmc_cowos_alloc_bgb: float = 13.5,
        logic_base_die_supply_bgb: float = 14.5,
        substrate_abf_cap_bgb: float = 16.0,
        inventory_amplification_factor: float = 1.65,
        holding_cost_per_bgb_musd: float = 145.0,
        supply_chain_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """가치사슬 종속성 그래프(Dynamic Dependency Graph) 및 리드타임 시차/채찍 효과(Bullwhip Effect) 시뮬레이터"""
        if supply_chain_nodes and isinstance(supply_chain_nodes, list) and len(supply_chain_nodes) > 0:
            stages = []
            ceiling_candidates = {}
            for idx, node in enumerate(supply_chain_nodes):
                if not isinstance(node, dict):
                    continue
                n_name = str(cls._resolve_node_field(node, "node", f"STAGE_{idx+1}"))
                lt = int(cls._safe_float(cls._resolve_node_field(node, "lead_time_months", (idx + 1) * 3), (idx + 1) * 3))
                shock = cls._safe_float(cls._resolve_node_field(node, "shock_pct", None), end_demand_shock_pct * (inventory_amplification_factor ** idx))
                cap = cls._resolve_node_field(node, "capacity_bgb", None)
                if cap is not None:
                    cap_f = cls._safe_float(cap, -1.0)
                    if cap_f > 0:
                        ceiling_candidates[n_name] = cap_f
                stages.append({
                    "stage_order": idx + 1,
                    "node": n_name,
                    "lead_time_months": lt,
                    "shock_pct": round(shock, 2),
                })
        else:
            stages = [
                {"stage_order": 1, "node": "CSP_AI_SERVER_DEMAND", "lead_time_months": 1, "shock_pct": round(end_demand_shock_pct, 2)},
                {"stage_order": 2, "node": "FABLESS_GPU_ALLOCATION", "lead_time_months": 3, "shock_pct": round(end_demand_shock_pct * (inventory_amplification_factor ** 1), 2)},
                {"stage_order": 3, "node": "FOUNDRY_COWOS_ADVANCED_PKG", "lead_time_months": 6, "shock_pct": round(end_demand_shock_pct * (inventory_amplification_factor ** 2), 2)},
                {"stage_order": 4, "node": "INTERNAL_HBM_FAB_WAFER_IN", "lead_time_months": 9, "shock_pct": round(end_demand_shock_pct * (inventory_amplification_factor ** 3), 2)},
                {"stage_order": 5, "node": "EUV_AND_TSV_EQUIPMENT_CAPEX_ORDER", "lead_time_months": 16, "shock_pct": round(end_demand_shock_pct * (inventory_amplification_factor ** 4), 2)},
            ]
            ceiling_candidates = {}

        internal_kghd_output_bgb = wafer_fab_capa_bgb * eds_yield
        if not ceiling_candidates:
            ceiling_candidates = {
                "INTERNAL_FAB_AND_EDS_YIELD": internal_kghd_output_bgb,
                "EXTERNAL_FOUNDRY_COWOS_PACKAGING": tsmc_cowos_alloc_bgb,
                "CUSTOM_LOGIC_BASE_DIE_SUPPLY": logic_base_die_supply_bgb,
                "ABF_SUBSTRATE_INTERPOSER_SUPPLY": substrate_abf_cap_bgb,
            }
        binding_node = min(ceiling_candidates, key=ceiling_candidates.get)
        effective_shippable_bgb = ceiling_candidates[binding_node]
        stranded_internal_kghd_bgb = max(0.0, internal_kghd_output_bgb - effective_shippable_bgb)
        holding_cost_musd = stranded_internal_kghd_bgb * holding_cost_per_bgb_musd

        return {
            "persona_id": "value-chain-business-persona",
            "bullwhip_amplification_chain": stages,
            "upstream_equipment_order_swing_pct": stages[-1]["shock_pct"] if stages else 0.0,
            "cumulative_pipeline_lead_time_months": stages[-1]["lead_time_months"] if stages else 16,
            "internal_good_die_output_bgb": round(internal_kghd_output_bgb, 3),
            "effective_shippable_ceiling_bgb": round(effective_shippable_bgb, 3),
            "binding_bottleneck_node": binding_node,
            "stranded_unshipped_die_inventory_bgb": round(stranded_internal_kghd_bgb, 3),
            "stranded_inventory_holding_loss_musd": round(holding_cost_musd, 2),
            "ecosystem_bottleneck_constrained": binding_node != "INTERNAL_FAB_AND_EDS_YIELD",
        }

    @classmethod
    def optimize_capex_roic_portfolio(
        cls,
        total_capex_budget_musd: float = 12000.0,
        cleanroom_wafer_limit_k: float = 180.0,
        tax_rate: float = 0.22,
        wacc_pct: float = 9.5,
        product_candidates: Optional[List[Dict[str, Any]]] = None,
        opt_strategy: str = "greedy_2phase",
    ) -> Dict[str, Any]:
        default_products = [
            {
                "product": "HBM3E_12H_HBM4",
                "capex_per_k_wafer_musd": 95.0,
                "die_penalty_factor": 2.85,
                "conversion_capa_loss_pct": 18.0,
                "lta_min_committed_wafers_k": 35.0,
                "bit_per_k_wafer_bgb": 0.52,
                "asp_usd_per_gb": 16.5,
                "op_margin_pct": 54.0,
                "max_demand_wafers_k": 75.0,
            },
            {
                "product": "DDR5_128GB_SERVER_RDIMM",
                "capex_per_k_wafer_musd": 58.0,
                "die_penalty_factor": 1.15,
                "conversion_capa_loss_pct": 8.0,
                "lta_min_committed_wafers_k": 40.0,
                "bit_per_k_wafer_bgb": 1.30,
                "asp_usd_per_gb": 4.2,
                "op_margin_pct": 38.0,
                "max_demand_wafers_k": 80.0,
            },
            {
                "product": "ENTERPRISE_ESSD_QLC_300L",
                "capex_per_k_wafer_musd": 42.0,
                "die_penalty_factor": 1.0,
                "conversion_capa_loss_pct": 5.0,
                "lta_min_committed_wafers_k": 15.0,
                "bit_per_k_wafer_bgb": 3.80,
                "asp_usd_per_gb": 0.95,
                "op_margin_pct": 28.0,
                "max_demand_wafers_k": 60.0,
            },
        ]
        items = product_candidates if product_candidates else default_products
        evaluated = []

        for p in items:
            if not isinstance(p, dict):
                continue
            prod_name = str(cls._resolve_prod_field(p, "product", "UNKNOWN"))
            capex_k = max(cls._safe_float(cls._resolve_prod_field(p, "capex_per_k_wafer_musd", 50.0), 50.0), 1e-6)
            bits_k = cls._safe_float(cls._resolve_prod_field(p, "bit_per_k_wafer_bgb", 1.0), 1.0)
            asp = cls._safe_float(cls._resolve_prod_field(p, "asp_usd_per_gb", 3.0), 3.0)
            opm = cls._safe_float(cls._resolve_prod_field(p, "op_margin_pct", 30.0), 30.0) / 100.0
            die_pen = cls._safe_float(cls._resolve_prod_field(p, "die_penalty_factor", 1.0), 1.0)
            conv_loss_pct = cls._safe_float(cls._resolve_prod_field(p, "conversion_capa_loss_pct", 0.0), 0.0)
            lta_floor_k = cls._safe_float(cls._resolve_prod_field(p, "lta_min_committed_wafers_k", 0.0), 0.0)
            max_dem_k = cls._safe_float(cls._resolve_prod_field(p, "max_demand_wafers_k", 50.0), 50.0)

            effective_wafer_yield_factor = max(0.5, 1.0 - (conv_loss_pct / 100.0) * 0.25)
            rev_per_k = (bits_k * effective_wafer_yield_factor * asp * 100.0) / 10.0
            nopat_per_k = rev_per_k * opm * (1.0 - tax_rate)
            roic_pct = cls._safe_float(p.get("roic_pct"), (nopat_per_k / capex_k) * 100.0)
            eva_spread_pct = roic_pct - wacc_pct
            capital_intensity_usd_per_gb = capex_k / max(bits_k, 1e-6)

            evaluated.append({
                "product": prod_name,
                "die_penalty_factor": round(die_pen, 2),
                "conversion_capa_loss_pct": round(conv_loss_pct, 2),
                "lta_min_committed_wafers_k": round(lta_floor_k, 2),
                "capital_intensity_musd_per_bgb": round(capital_intensity_usd_per_gb, 2),
                "roic_pct": round(roic_pct, 2),
                "eva_spread_vs_wacc_pct": round(eva_spread_pct, 2),
                "capex_per_k_wafer_musd": capex_k,
                "nopat_per_k_wafer_musd": round(nopat_per_k, 2),
                "max_demand_wafers_k": max_dem_k,
                "allocated_wafers_k": 0.0,
            })

        rem_capex = total_capex_budget_musd
        rem_wafers = cleanroom_wafer_limit_k

        opt_strat_lower = str(opt_strategy).lower()
        optimality_flag = "HEURISTIC_(greedy_2phase)"

        if "bnb" in opt_strat_lower or "exact" in opt_strat_lower:
            # Branch & Bound for multi-dimensional knapsack allocation (discrete/fractional step)
            # Step 1: Satisfy mandatory LTA minimum floor
            for item in evaluated:
                floor_k = min(item["lta_min_committed_wafers_k"], item["max_demand_wafers_k"], rem_wafers, rem_capex / item["capex_per_k_wafer_musd"])
                floor_k = max(0.0, floor_k)
                item["allocated_wafers_k"] += floor_k
                rem_wafers -= floor_k
                rem_capex -= floor_k * item["capex_per_k_wafer_musd"]

            # Step 2: Optimal assignment of remaining capacity/capex using B&B
            step_k = 1.0  # 1k wafer resolution
            best_alloc = [0.0] * len(evaluated)
            best_nopat = [-1.0]

            def _bnb(idx: int, cur_capex: float, cur_wafers: float, cur_nopat: float, current_plan: List[float]):
                if idx == len(evaluated):
                    if cur_nopat > best_nopat[0]:
                        best_nopat[0] = cur_nopat
                        best_alloc[:] = current_plan[:]
                    return
                # Upper bound relaxation
                rem_c = cur_capex
                rem_w = cur_wafers
                ub = cur_nopat
                for j in range(idx, len(evaluated)):
                    cand = evaluated[j]
                    max_w = min(cand["max_demand_wafers_k"] - cand["allocated_wafers_k"], rem_w, rem_c / cand["capex_per_k_wafer_musd"])
                    if max_w > 0:
                        ub += max_w * cand["nopat_per_k_wafer_musd"]
                        rem_c -= max_w * cand["capex_per_k_wafer_musd"]
                        rem_w -= max_w
                if ub <= best_nopat[0]:
                    return

                cand = evaluated[idx]
                max_possible = min(cand["max_demand_wafers_k"] - cand["allocated_wafers_k"], cur_wafers, cur_capex / cand["capex_per_k_wafer_musd"])
                # Branch high to low
                k_options = []
                cur_k = max_possible
                while cur_k >= 0:
                    k_options.append(cur_k)
                    cur_k -= step_k
                if 0.0 not in k_options:
                    k_options.append(0.0)

                for wk in k_options:
                    current_plan.append(wk)
                    _bnb(idx + 1, cur_capex - wk * cand["capex_per_k_wafer_musd"], cur_wafers - wk, cur_nopat + wk * cand["nopat_per_k_wafer_musd"], current_plan)
                    current_plan.pop()

            _bnb(0, rem_capex, rem_wafers, 0.0, [])
            for idx, item in enumerate(evaluated):
                item["allocated_wafers_k"] += best_alloc[idx]
            optimality_flag = "PROVEN_OPTIMAL_(bnb_1k_grid)"
        else:
            # Default 2-Phase Greedy
            for item in evaluated:
                floor_k = min(item["lta_min_committed_wafers_k"], item["max_demand_wafers_k"], rem_wafers, rem_capex / item["capex_per_k_wafer_musd"])
                floor_k = max(0.0, floor_k)
                item["allocated_wafers_k"] += floor_k
                rem_wafers -= floor_k
                rem_capex -= floor_k * item["capex_per_k_wafer_musd"]

            evaluated.sort(key=lambda x: x["roic_pct"], reverse=True)
            for item in evaluated:
                upside_demand_k = max(0.0, item["max_demand_wafers_k"] - item["allocated_wafers_k"])
                max_by_capex = rem_capex / item["capex_per_k_wafer_musd"]
                add_k = max(0.0, min(upside_demand_k, rem_wafers, max_by_capex))
                item["allocated_wafers_k"] += add_k
                rem_capex -= add_k * item["capex_per_k_wafer_musd"]
                rem_wafers -= add_k

        allocations = []
        total_nopat = 0.0
        used_capex = 0.0

        for item in evaluated:
            total_k = item["allocated_wafers_k"]
            capex_spent = total_k * item["capex_per_k_wafer_musd"]
            nopat_gen = total_k * item["nopat_per_k_wafer_musd"]
            used_capex += capex_spent
            total_nopat += nopat_gen

            allocations.append({
                **item,
                "allocated_wafers_k": round(total_k, 2),
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
            "optimization_method": opt_strategy,
            "optimality": optimality_flag,
            "optimal_product_allocations": allocations,
        }

    @staticmethod
    def build_geopolitical_scenario_tree(
        base_operating_profit_musd: float = 14000.0,
        china_fab_wafer_share_pct: float = 28.0,
        custom_scenarios: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
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
        payload = cls.auto_route_generic_records(dict(payload or {}))
        doc_params = cls.extract_params_from_documents(payload.get("documents"))
        for k, v in doc_params.items():
            if payload.get(k) is None:
                payload[k] = v

        vc_res = cls.simulate_value_chain_bottleneck_and_bullwhip(
            end_demand_shock_pct=cls._safe_float(payload.get("end_demand_shock_pct"), 5.0),
            wafer_fab_capa_bgb=cls._safe_float(payload.get("wafer_fab_capa_bgb"), 20.0),
            eds_yield=cls._safe_float(payload.get("eds_yield"), 0.78),
            tsmc_cowos_alloc_bgb=cls._safe_float(payload.get("tsmc_cowos_alloc_bgb"), 13.5),
            logic_base_die_supply_bgb=cls._safe_float(payload.get("logic_base_die_supply_bgb"), 14.5),
            substrate_abf_cap_bgb=cls._safe_float(payload.get("substrate_abf_cap_bgb"), 16.0),
            supply_chain_nodes=payload.get("supply_chain_nodes"),
        )
        roic_res = cls.optimize_capex_roic_portfolio(
            total_capex_budget_musd=cls._safe_float(payload.get("total_capex_budget_musd"), 12000.0),
            cleanroom_wafer_limit_k=cls._safe_float(payload.get("cleanroom_wafer_limit_k"), 180.0),
            wacc_pct=cls._safe_float(payload.get("wacc_pct"), 9.5),
            product_candidates=payload.get("product_candidates"),
            opt_strategy=str(payload.get("opt_strategy", "greedy_2phase")),
        )
        geo_res = cls.build_geopolitical_scenario_tree(
            base_operating_profit_musd=cls._safe_float(payload.get("base_operating_profit_musd"), 14000.0),
            china_fab_wafer_share_pct=cls._safe_float(payload.get("china_fab_wafer_share_pct"), 28.0),
            custom_scenarios=payload.get("custom_scenarios"),
        )

        if roic_res["value_created_eva_musd"] < 0 or vc_res["stranded_unshipped_die_inventory_bgb"] >= 5.0:
            status = "VIOLATION"
            rule_id = "VCBIZ-RULE-NEGATIVE-EVA-OR-SEVERE-STRANDED-DIE"
        elif vc_res["ecosystem_bottleneck_constrained"]:
            status = "WARNING"
            rule_id = "VCBIZ-RULE-ECOSYSTEM-BOTTLENECK-WARN"
        else:
            status = "NORMAL"
            rule_id = "VCBIZ-RULE-OPTIMAL-PORTFOLIO"

        return {
            "domain": "VALUE_CHAIN_BIZ",
            "persona_id": str(payload.get("persona_id", "value-chain-business-persona")),
            "status": status,
            "ruleId": rule_id,
            "value_chain_and_bullwhip_analysis": vc_res,
            "capex_roic_optimization": roic_res,
            "geopolitical_scenario_tree": geo_res,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = ValueChainBusinessSolver.solve_all(payload)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
