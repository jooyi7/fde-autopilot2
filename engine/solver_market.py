#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Solver 3: Memory Market Strategy & Competitor Earnings Analyzer
- Fiscal Calendarization (Micron Aug FY vs SK hynix/Samsung Dec FY) & Unit Normalization
- P x Q x Mix Variance Decomposition (Separating HBM3E/DDR5 Specialty Mix from Legacy Commodity ASP)
- Qualitative IR Rhetoric vs Quantitative Financial Indicators (DIO / CAPEX / Utilization) Cross-Validator

"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class MarketStrategySolver:
    # Micron Fiscal Quarter to Calendar Quarter Mapping (Micron FY ends Aug)
    MICRON_FQ_TO_CQ = {
        "FQ1": ("CQ4_PREV", "Sep-Nov"),
        "FQ2": ("CQ1", "Dec-Feb"),
        "FQ3": ("CQ2", "Mar-May"),
        "FQ4": ("CQ3", "Jun-Aug"),
    }

    @classmethod
    def normalize_competitor_calendar_and_units(
        cls,
        competitor_records: List[Dict[str, Any]],
        krw_per_usd: float = 1380.0,
    ) -> List[Dict[str, Any]]:
        """
        [해결방안 1] 캘린더 분기(Calendarization) 정규화 및 통화/Bit 단위 단일 테이블 표준화:
        마이크론(8월 결산)과 SK하이닉스/삼성전자(12월 결산)의 분기 시점을 정렬하고,
        KRW(조 원/억 원)와 USD(B$/M$), Byte와 Bit(1 Byte = 8Gb) 단위를 표준화
        """
        normalized = []
        for rec in (competitor_records or []):
            if not isinstance(rec, dict):
                continue
            comp = str(rec.get("company", "UNKNOWN")).strip()
            raw_period = str(rec.get("reported_period", "2025-Q1")).strip().upper()
            currency = str(rec.get("currency", "USD")).strip().upper()

            # 1) Calendarization
            cal_quarter = raw_period
            alignment_note = "STANDARD_DEC_FY"
            if "MU" in comp.upper() or "MICRON" in comp.upper():
                for fq, (cq_tag, months) in cls.MICRON_FQ_TO_CQ.items():
                    if fq in raw_period:
                        cal_quarter = raw_period.replace(fq, cq_tag)
                        alignment_note = f"MICRON_SHIFTED({months})"
                        break

            # 2) Revenue & OP Currency Normalization to Million USD (MUSD)
            rev_raw = float(rec.get("revenue", 0.0) or 0.0)
            op_raw = float(rec.get("operating_profit", 0.0) or 0.0)
            if currency == "KRW_TRILLION":
                rev_musd = (rev_raw * 1_000_000.0) / max(krw_per_usd, 1.0)
                op_musd = (op_raw * 1_000_000.0) / max(krw_per_usd, 1.0)
            elif currency == "USD_BILLION":
                rev_musd = rev_raw * 1000.0
                op_musd = op_raw * 1000.0
            else:
                rev_musd = rev_raw
                op_musd = op_raw

            # 3) Bit Shipment Normalization to Billion Gb Equivalent (B_Gb)
            ship_raw = float(rec.get("shipment_volume", 0.0) or 0.0)
            ship_unit = str(rec.get("shipment_unit", "B_Gb")).strip()
            if ship_unit.upper() == "EXABYTE":
                # 1 Exabyte = 8 Billion Gb
                ship_bgb = ship_raw * 8.0
            elif ship_unit.upper() == "B_GBYTE":
                ship_bgb = ship_raw * 8.0
            else:
                ship_bgb = ship_raw

            opm_pct = (op_musd / max(rev_musd, 1e-6)) * 100.0
            blended_asp = rev_musd / max(ship_bgb, 1e-6) if ship_bgb > 0 else float(rec.get("blended_asp_usd", 0.0) or 0.0)

            normalized.append({
                "company": comp,
                "reported_period": raw_period,
                "calendarized_quarter": cal_quarter,
                "calendar_alignment_note": alignment_note,
                "revenue_musd": round(rev_musd, 2),
                "operating_profit_musd": round(op_musd, 2),
                "operating_margin_pct": round(opm_pct, 2),
                "shipment_bgb": round(ship_bgb, 3),
                "blended_asp_usd_per_gb": round(blended_asp, 4),
            })
        return normalized

    @staticmethod
    def decompose_pq_mix_variance(
        prev_period: Dict[str, float],
        curr_period: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        [해결방안 2] P x Q x Mix 분해(Variance Decomposition) 모델:
        전사 Blended ASP 상승 착시를 제거하기 위해, 매출 변동을
        1) 순수 물량 효과(Delta Q), 2) 레거시/범용 단가 효과(Delta Legacy P), 3) 고부가(HBM/DDR5) 믹스 효과(Delta Mix)로 분해
        """
        q0 = max(float(prev_period.get("total_shipment_bgb", 100.0)), 1e-6)
        q1 = max(float(curr_period.get("total_shipment_bgb", 105.0)), 1e-6)

        hbm_share0 = float(prev_period.get("hbm_bit_share_ ratio", prev_period.get("hbm_bit_share_pct", 10.0) / 100.0))
        hbm_share1 = float(curr_period.get("hbm_bit_share_ratio", curr_period.get("hbm_bit_share_pct", 18.0) / 100.0))

        p_leg0 = float(prev_period.get("legacy_asp_usd", 3.2))
        p_leg1 = float(curr_period.get("legacy_asp_usd", 2.95))
        p_hbm0 = float(prev_period.get("hbm_asp_usd", 15.0))
        p_hbm1 = float(curr_period.get("hbm_asp_usd", 16.2))

        blend_p0 = (1.0 - hbm_share0) * p_leg0 + hbm_share0 * p_hbm0
        blend_p1 = (1.0 - hbm_share1) * p_leg1 + hbm_share1 * p_hbm1

        rev0 = q0 * blend_p0
        rev1 = q1 * blend_p1
        total_delta_rev = rev1 - rev0

        # Decomposition
        volume_effect = (q1 - q0) * blend_p0
        pure_price_effect = q1 * ((1.0 - hbm_share0) * (p_leg1 - p_leg0) + hbm_share0 * (p_hbm1 - p_hbm0))
        mix_shift_effect = q1 * (hbm_share1 - hbm_share0) * (p_hbm1 - p_leg1)

        # Mix illusion check: Blended ASP rose, but Legacy ASP actually fell
        blended_asp_change_pct = ((blend_p1 - blend_p0) / max(blend_p0, 1e-6)) * 100.0
        legacy_asp_change_pct = ((p_leg1 - p_leg0) / max(p_leg0, 1e-6)) * 100.0
        mix_illusion_detected = (blended_asp_change_pct > 0.0) and (legacy_asp_change_pct < 0.0)

        return {
            "prev_blended_asp_usd": round(blend_p0, 4),
            "curr_blended_asp_usd": round(blend_p1, 4),
            "blended_asp_change_pct": round(blended_asp_change_pct, 2),
            "legacy_commodity_asp_change_pct": round(legacy_asp_change_pct, 2),
            "mix_illusion_flag": mix_illusion_detected,
            "prev_revenue_musd": round(rev0, 2),
            "curr_revenue_musd": round(rev1, 2),
            "total_revenue_variance_musd": round(total_delta_rev, 2),
            "variance_breakdown_musd": {
                "delta_volume_effect": round(volume_effect, 2),
                "delta_pure_price_effect": round(pure_price_effect, 2),
                "delta_specialty_mix_effect": round(mix_shift_effect, 2),
            },
        }

    @staticmethod
    def cross_check_ir_vs_financials(ir_audit_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        [해결방안 3] 정성적 IR 발언(어닝콜 텍스트 감성/주장)과 재무제표 선행지표(재고일수 DIO, 미집행 CAPEX, 가동률) 교차 검증:
        경영진은 '수요 강세 및 재고 정상화'를 주장하나 실제 DIO가 증가하거나 가동률/CAPEX가 역행할 경우 Red Flag 발생
        """
        results = []
        for item in (ir_audit_list or []):
            comp = str(item.get("company", "COMPETITOR"))
            sentiment_score = float(item.get("ir_bullish_sentiment_score", 0.8))  # 0.0 ~ 1.0
            prev_dio = float(item.get("prev_inventory_days_dio", 95.0))
            curr_dio = float(item.get("curr_inventory_days_dio", 112.0))
            capex_exec_rate_pct = float(item.get("capex_execution_rate_pct", 85.0))
            ar_days_delta = float(item.get("accounts_receivable_days_delta", 0.0))

            dio_delta = curr_dio - prev_dio
            contradictions = []

            if sentiment_score >= 0.7 and dio_delta >= 7.0:
                contradictions.append("BULLISH_IR_VS_RISING_INVENTORY_DIO")
            if sentiment_score >= 0.7 and capex_exec_rate_pct < 70.0:
                contradictions.append("DEMAND_OPTIMISM_VS_CAPEX_UNDEREXECUTION")
            if sentiment_score >= 0.7 and ar_days_delta >= 10.0:
                contradictions.append("CHANNEL_STUFFING_RISK_RISING_AR_DAYS")

            results.append({
                "company": comp,
                "ir_bullish_sentiment_score": round(sentiment_score, 2),
                "prev_dio_days": round(prev_dio, 1),
                "curr_dio_days": round(curr_dio, 1),
                "dio_change_days": round(dio_delta, 1),
                "red_flag_detected": len(contradictions) > 0,
                "contradiction_codes": contradictions,
            })
        return results

    @staticmethod
    def simulate_allocation_grid(
        total_wafer_capa_k: float = 150.0,
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
        competitor_records: Optional[List[Dict[str, Any]]] = None,
        pq_mix_periods: Optional[Dict[str, Dict[str, float]]] = None,
        ir_audit_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        raw_gb_per_k_wafer = 1.5
        scenarios = []
        best_scenario = None

        for pct in range(5, 55, 5):
            hbm_ratio = pct / 100.0
            hbm_wafers_k = total_wafer_capa_k * hbm_ratio
            dram_wafers_k = total_wafer_capa_k * (1.0 - hbm_ratio)

            raw_hbm_bgb = hbm_wafers_k * (raw_gb_per_k_wafer / max(hbm_die_penalty, 0.1)) * hbm_yield
            effective_hbm_bgb = min(raw_hbm_bgb, tsv_packaging_cap_bgb)
            tsv_bottleneck_loss_bgb = max(0.0, raw_hbm_bgb - effective_hbm_bgb)

            effective_dram_bgb = dram_wafers_k * raw_gb_per_k_wafer * dram_yield

            total_mkt_dram_supply = competitor_dram_supply_bgb + effective_dram_bgb
            total_mkt_hbm_supply = competitor_hbm_supply_bgb + effective_hbm_bgb

            dram_oversupply_ratio = (total_mkt_dram_supply - market_dram_demand_bgb) / max(market_dram_demand_bgb, 1e-6)
            hbm_oversupply_ratio = (total_mkt_hbm_supply - market_hbm_demand_bgb) / max(market_hbm_demand_bgb, 1e-6)

            proj_dram_asp = base_dram_asp * max(0.5, 1.0 - 1.4 * dram_oversupply_ratio)
            proj_hbm_asp = base_hbm_asp * max(0.7, 1.0 - 0.8 * hbm_oversupply_ratio)

            dram_rev = effective_dram_bgb * proj_dram_asp
            hbm_rev = effective_hbm_bgb * proj_hbm_asp
            dram_op = effective_dram_bgb * (proj_dram_asp - dram_cost_per_gb)
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

        cal_comp = MarketStrategySolver.normalize_competitor_calendar_and_units(competitor_records or [])
        pq_decomp = None
        if pq_mix_periods and "prev" in pq_mix_periods and "curr" in pq_mix_periods:
            pq_decomp = MarketStrategySolver.decompose_pq_mix_variance(pq_mix_periods["prev"], pq_mix_periods["curr"])
        ir_checks = MarketStrategySolver.cross_check_ir_vs_financials(ir_audit_records or [])

        has_ir_red_flag = any(r["red_flag_detected"] for r in ir_checks)
        has_mix_illusion = bool(pq_decomp and pq_decomp.get("mix_illusion_flag"))

        status_code = "WARNING" if (has_ir_red_flag or has_mix_illusion) else "NORMAL"
        rule_id = "MKT-RULE-IR-OR-MIX-WARN" if status_code == "WARNING" else "MKT-RULE-OPTIMAL"

        return {
            "status": status_code,
            "ruleId": rule_id,
            "optimal_strategy": best_scenario,
            "scenario_table": scenarios,
            "calendarized_competitor_benchmarks": cal_comp,
            "pq_mix_variance_decomposition": pq_decomp,
            "ir_vs_financials_cross_audit": ir_checks,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = MarketStrategySolver.simulate_allocation_grid(**payload)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
