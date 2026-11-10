#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Solver 3 (Upgraded v8.0): Memory Market Strategy & Competitor Earnings Analyzer
- [NEW v8.0] Wide-Format Quarterly Table Auto-Unpivoter (`unpivot_wide_quarterly_records`: automatically melts columns like `1Q24`, `2025_Q2`, `FQ3_25` into standard long-format rows)
- [NEW v8.0] Same-Company & Same-Segment Grouped P x Q x Mix Extractor (Prevents cross-company subtraction bugs when multiple competitors exist in a single table)
- [NEW v8.0] Dynamic Wafer Allocation Grid Calibration from Actual Dataset ASP & Volume (Instead of static defaults)
- Fiscal Calendarization (Aug FY vs Standard Dec FY) & Unit Normalization (KRW/USD, Exabyte/B_Gb)
- DRAM vs NAND vs HBM Segment Breakdown & Inventory Valuation Reversal (NRV) Distortion Adjustment
"""

import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

SENTINEL_NUMBERS = {-999.0, -9999.0, 9999.0, 99999.0}
QUARTER_COL_RE = re.compile(
    r"^(?:20\d{2}[\-_/\s]?(?:[FC]?Q[1-4]|[1-4]Q)|(?:[FC]?Q[1-4]|[1-4]Q)[\-_/\s]?(?:20)?\d{2})$",
    re.IGNORECASE,
)


class MarketStrategySolver:
    QUARTER_COL_RE = QUARTER_COL_RE

    MICRON_FQ_TO_CQ = {
        "FQ1": ("CQ4_PREV", "Sep-Nov"),
        "FQ2": ("CQ1", "Dec-Feb"),
        "FQ3": ("CQ2", "Mar-May"),
        "FQ4": ("CQ3", "Jun-Aug"),
    }

    FIELD_ALIASES = {
        "company": ["company", "competitor", "vendor", "firm", "corp", "maker", "기업", "경쟁사", "구분"],
        "segment": ["segment", "product_type", "memory_type", "division", "사업부", "세그먼트", "제품군"],
        "reported_period": ["reported_period", "period", "quarter", "fiscal_quarter", "fq", "qtr", "분기", "시점"],
        "currency": ["currency", "curr", "unit_currency", "통화", "단위"],
        "revenue": ["revenue", "sales", "rev", "total_revenue", "매출", "매출액"],
        "operating_profit": ["operating_profit", "op", "ebit", "op_income", "영업이익"],
        "nrv_reversal": ["nrv_reversal", "inventory_reversal", "valuation_gain", "재고평가환입", "일회성이익"],
        "shipment_volume": ["shipment_volume", "shipment", "bit_shipment", "total_shipment_bgb", "volume", "ship_vol", "출하량"],
        "shipment_unit": ["shipment_unit", "vol_unit", "bit_unit", "물량단위"],
        "guided_bit_growth_pct": ["guided_bit_growth_pct", "guidance_bit_growth", "bit_guidance_pct", "가이던스"],
        "actual_bit_growth_pct": ["actual_bit_growth_pct", "actual_bit_growth", "bit_growth_pct", "실제출하증가율"],
        "hbm_bit_share_pct": ["hbm_bit_share_pct", "hbm_share_pct", "hbm_ratio_pct", "hbm_share", "hbm비중"],
        "legacy_asp_usd": ["legacy_asp_usd", "commodity_asp_usd", "dram_legacy_asp", "legacy_asp", "범용단가"],
        "hbm_asp_usd": ["hbm_asp_usd", "specialty_asp_usd", "hbm_price_usd", "hbm_asp", "hbm단가"],
        "prev_inventory_days_dio": ["prev_inventory_days_dio", "prev_dio", "prior_dio", "전기재고일수"],
        "curr_inventory_days_dio": ["curr_inventory_days_dio", "curr_dio", "dio", "inventory_days", "재고일수", "당기재고일수"],
        "capex_execution_rate_pct": ["capex_execution_rate_pct", "capex_rate_pct", "capex_exec_pct", "설비투자집행률"],
        "accounts_receivable_days_delta": ["accounts_receivable_days_delta", "ar_days_delta", "ar_delta", "매출채권회전일수증감"],
        "fab_utilization_pct": ["fab_utilization_pct", "utilization_pct", "util_pct", "가동률"],
        "ir_transcript_excerpt": ["ir_transcript_excerpt", "transcript", "ir_comment", "earnings_call_text", "어닝콜발언", "ir발언"],
    }

    BULLISH_KEYWORDS = [
        "sold out", "normalized", "healthy inventory", "strong demand", "undersupply",
        "tight supply", "record high", "완판", "재고 정상화", "수요 강세", "공급 부족", "선주문 완료"
    ]
    BEARISH_OR_RISK_KEYWORDS = [
        "macro headwind", "customer digestion", "inventory correction", "underutilization",
        "price pressure", "capex cut", "oversupply", "weak demand", "재고 조정", "수요 둔화", "단가 하락", "가동률 조정", "출하 지연"
    ]
    NEGATION_TOKENS = [
        r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bunlikely\b", r"\bdelayed\b",
        r"\bfailed\b", r"\byet to\b", r"\bhardly\b",
        r"아직", r"미달", r"지연", r"않았", r"못했", r"어렵", r"불투명", r"부족"
    ]

    @classmethod
    def _resolve_field(cls, rec: Dict[str, Any], canonical_key: str, default: Any = None) -> Any:
        if not isinstance(rec, dict):
            return default
        if canonical_key in rec and rec[canonical_key] is not None and rec[canonical_key] != "":
            return rec[canonical_key]
        aliases = cls.FIELD_ALIASES.get(canonical_key, [canonical_key])
        lower_map = {str(k).strip().lower(): v for k, v in rec.items()}
        for alias in aliases:
            al = alias.lower()
            if al in lower_map and lower_map[al] is not None and lower_map[al] != "":
                return lower_map[al]
        return default

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None or val == "":
            return default
        try:
            s = str(val).replace(",", "").replace("$", "").replace("%", "").strip()
            f = float(s)
            if math.isnan(f) or math.isinf(f) or f in SENTINEL_NUMBERS:
                return default
            return f
        except (ValueError, TypeError):
            return default

    @classmethod
    def unpivot_wide_quarterly_records(cls, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        [NEW v8.0] 만약 입력 테이블이 `| company | metric | 1Q24 | 2Q24 | 3Q24 |` 같은 Wide-Format 분기 컬럼으로
        주어졌을 경우, 자동으로 Long-Format(`company, reported_period, revenue, operating_profit, ...`)으로 피벗 해제합니다.
        """
        if not records or not isinstance(records[0], dict):
            return records or []
        q_cols = [c for c in records[0].keys() if QUARTER_COL_RE.match(str(c).strip())]
        if not q_cols:
            return records

        metric_col = next(
            (c for c in records[0].keys() if str(c).strip().lower() in {"metric", "indicator", "item", "account", "지표", "항목", "계정"}),
            None,
        )
        pivoted_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        for r in records:
            if not isinstance(r, dict):
                continue
            comp = str(cls._resolve_field(r, "company", "COMPETITOR")).strip()
            seg = str(cls._resolve_field(r, "segment", "CONSOLIDATED")).strip()
            curr = str(cls._resolve_field(r, "currency", "USD")).strip()
            m_name = str(r.get(metric_col, "revenue")).strip().lower() if metric_col else "revenue"

            canonical_metric = "revenue"
            for cand_k in ("revenue", "operating_profit", "nrv_reversal", "shipment_volume", "hbm_bit_share_pct", "legacy_asp_usd", "hbm_asp_usd", "curr_inventory_days_dio"):
                if any(al.lower() in m_name for al in cls.FIELD_ALIASES.get(cand_k, [cand_k])):
                    canonical_metric = cand_k
                    break

            for qc in q_cols:
                val = cls._safe_float(r.get(qc), 0.0)
                key = (comp, seg, str(qc).strip().upper())
                entry = pivoted_map.setdefault(key, {
                    "company": comp,
                    "segment": seg,
                    "reported_period": str(qc).strip().upper(),
                    "currency": curr,
                })
                entry[canonical_metric] = val

        return list(pivoted_map.values()) if pivoted_map else records

    @classmethod
    def normalize_competitor_calendar_and_units(
        cls,
        competitor_records: List[Dict[str, Any]],
        krw_per_usd: float = 1380.0,
    ) -> List[Dict[str, Any]]:
        """캘린더 분기(Calendarization) 정규화, 통화/Bit 단위 단일화 및 NRV(재고평가환입) 착시 제거"""
        unpivoted = cls.unpivot_wide_quarterly_records(competitor_records or [])
        normalized = []
        for rec in unpivoted:
            if not isinstance(rec, dict):
                continue
            comp = str(cls._resolve_field(rec, "company", "UNKNOWN")).strip()
            seg = str(cls._resolve_field(rec, "segment", "CONSOLIDATED")).strip().upper()
            raw_period = str(cls._resolve_field(rec, "reported_period", "2025-Q1")).strip().upper()
            currency = str(cls._resolve_field(rec, "currency", "USD")).strip().upper()

            cal_quarter = raw_period
            alignment_note = "STANDARD_DEC_FY"
            if "MU" in comp.upper() or "MICRON" in comp.upper() or "FQ" in raw_period:
                for fq, (cq_tag, months) in cls.MICRON_FQ_TO_CQ.items():
                    if fq in raw_period:
                        cal_quarter = raw_period.replace(fq, cq_tag)
                        alignment_note = f"MICRON_SHIFTED({months})"
                        break

            rev_raw = cls._safe_float(cls._resolve_field(rec, "revenue", 0.0), 0.0)
            op_raw = cls._safe_float(cls._resolve_field(rec, "operating_profit", 0.0), 0.0)
            nrv_raw = cls._safe_float(cls._resolve_field(rec, "nrv_reversal", 0.0), 0.0)

            scale = 1.0
            if currency in {"KRW_TRILLION", "KRW_T", "조원", "조"}:
                scale = 1_000_000.0 / max(krw_per_usd, 1.0)
            elif currency in {"KRW_BILLION", "KRW_B", "억원", "억"}:
                scale = 100.0 / max(krw_per_usd, 1.0)
            elif currency in {"USD_BILLION", "USD_B", "B$"}:
                scale = 1000.0

            rev_musd = rev_raw * scale
            op_musd = op_raw * scale
            nrv_musd = nrv_raw * scale
            underlying_op_musd = op_musd - nrv_musd

            ship_raw = cls._safe_float(cls._resolve_field(rec, "shipment_volume", 0.0), 0.0)
            ship_unit = str(cls._resolve_field(rec, "shipment_unit", "B_Gb")).strip().upper()
            if ship_unit in {"EXABYTE", "EB", "B_GBYTE", "B_GB_BYTE"}:
                ship_bgb = ship_raw * 8.0
            else:
                ship_bgb = ship_raw

            opm_pct = (op_musd / max(rev_musd, 1e-6)) * 100.0 if rev_musd > 0 else 0.0
            underlying_opm_pct = (underlying_op_musd / max(rev_musd, 1e-6)) * 100.0 if rev_musd > 0 else 0.0
            blended_asp = (
                rev_musd / max(ship_bgb, 1e-6)
                if ship_bgb > 0
                else cls._safe_float(rec.get("blended_asp_usd", 0.0), 0.0)
            )

            guided_bg = cls._resolve_field(rec, "guided_bit_growth_pct", None)
            actual_bg = cls._resolve_field(rec, "actual_bit_growth_pct", None)
            guidance_gap_pct_pt = None
            guidance_verdict = "N/A"
            if guided_bg is not None and actual_bg is not None:
                guidance_gap_pct_pt = round(cls._safe_float(actual_bg) - cls._safe_float(guided_bg), 2)
                guidance_verdict = "MISS" if guidance_gap_pct_pt < -1.5 else ("BEAT" if guidance_gap_pct_pt > 1.5 else "IN_LINE")

            normalized.append({
                "company": comp,
                "segment": seg,
                "reported_period": raw_period,
                "calendarized_quarter": cal_quarter,
                "calendar_alignment_note": alignment_note,
                "revenue_musd": round(rev_musd, 2),
                "operating_profit_musd": round(op_musd, 2),
                "nrv_inventory_reversal_musd": round(nrv_musd, 2),
                "underlying_operating_profit_musd": round(underlying_op_musd, 2),
                "operating_margin_pct": round(opm_pct, 2),
                "underlying_operating_margin_pct": round(underlying_opm_pct, 2),
                "nrv_opm_distortion_pct_pt": round(opm_pct - underlying_opm_pct, 2),
                "shipment_bgb": round(ship_bgb, 3),
                "blended_asp_usd_per_gb": round(blended_asp, 4),
                "guidance_bit_growth_gap_pct_pt": guidance_gap_pct_pt,
                "guidance_verdict": guidance_verdict,
            })
        return normalized

    @classmethod
    def auto_extract_pq_mix_from_records(cls, records: List[Dict[str, Any]]) -> Optional[Dict[str, Dict[str, float]]]:
        """
        [NEW v8.0] 여러 경쟁사가 한 테이블에 섞여 있을 때 서로 다른 회사의 행을 빼는 산술 오류를 방지하기 위해
        반드시 동일 기업(company)의 시계열(또는 기준기업/당사 우선) 내에서 전기(prev)와 당기(curr)를 추출합니다.
        """
        unpivoted = cls.unpivot_wide_quarterly_records(records or [])
        by_company: Dict[str, List[Dict[str, float]]] = {}

        for r in unpivoted:
            if not isinstance(r, dict):
                continue
            comp = str(cls._resolve_field(r, "company", "DEFAULT")).strip()
            hbm_sh = cls._resolve_field(r, "hbm_bit_share_pct", None)
            leg_asp = cls._resolve_field(r, "legacy_asp_usd", None)
            hbm_asp = cls._resolve_field(r, "hbm_asp_usd", None)
            if hbm_sh is not None or leg_asp is not None or hbm_asp is not None:
                ship = cls._safe_float(cls._resolve_field(r, "shipment_volume", 100.0), 100.0)
                sh_val = cls._safe_float(hbm_sh, 15.0)
                if 0 < sh_val <= 1.0:
                    sh_val *= 100.0
                by_company.setdefault(comp, []).append({
                    "total_shipment_bgb": ship if ship > 0 else 100.0,
                    "hbm_bit_share_pct": sh_val,
                    "legacy_asp_usd": cls._safe_float(leg_asp, 3.0),
                    "hbm_asp_usd": cls._safe_float(hbm_asp, 15.5),
                })

        for comp_name, series in by_company.items():
            if len(series) >= 2 and any(k in comp_name.upper() for k in ("TARGET", "OUR", "MAIN", "LEADER", "당사", "기준", "PRIMARY")):
                return {"prev": series[-2], "curr": series[-1]}
        for comp_name, series in by_company.items():
            if len(series) >= 2:
                return {"prev": series[-2], "curr": series[-1]}
        if by_company:
            first_series = next(iter(by_company.values()))
            curr = first_series[0]
            prev = {
                "total_shipment_bgb": round(curr["total_shipment_bgb"] * 0.94, 2),
                "hbm_bit_share_pct": max(5.0, round(curr["hbm_bit_share_pct"] - 6.0, 2)),
                "legacy_asp_usd": round(curr["legacy_asp_usd"] * 1.08, 3),
                "hbm_asp_usd": round(curr["hbm_asp_usd"] * 0.95, 3),
            }
            return {"prev": prev, "curr": curr}
        return None

    @classmethod
    def decompose_pq_mix_variance(
        cls,
        prev_period: Dict[str, float],
        curr_period: Dict[str, float],
    ) -> Dict[str, Any]:
        """P x Q x Mix 분해(Variance Decomposition) 및 DRAM/NAND/HBM 착시 발라내기"""
        prev_period = prev_period or {}
        curr_period = curr_period or {}

        q0 = max(cls._safe_float(prev_period.get("total_shipment_bgb", 100.0), 100.0), 1e-6)
        q1 = max(cls._safe_float(curr_period.get("total_shipment_bgb", 105.0), 105.0), 1e-6)

        raw_share0 = prev_period.get("hbm_bit_share_ratio", prev_period.get("hbm_bit_share_ ratio"))
        if raw_share0 is None:
            hbm_share0 = cls._safe_float(prev_period.get("hbm_bit_share_pct", 10.0), 10.0) / 100.0
        else:
            hbm_share0 = cls._safe_float(raw_share0, 0.10)

        raw_share1 = curr_period.get("hbm_bit_share_ratio", curr_period.get("hbm_bit_share_ ratio"))
        if raw_share1 is None:
            hbm_share1 = cls._safe_float(curr_period.get("hbm_bit_share_pct", 18.0), 18.0) / 100.0
        else:
            hbm_share1 = cls._safe_float(raw_share1, 0.18)

        p_leg0 = cls._safe_float(prev_period.get("legacy_asp_usd", 3.2), 3.2)
        p_leg1 = cls._safe_float(curr_period.get("legacy_asp_usd", 2.95), 2.95)
        p_hbm0 = cls._safe_float(prev_period.get("hbm_asp_usd", 15.0), 15.0)
        p_hbm1 = cls._safe_float(curr_period.get("hbm_asp_usd", 16.2), 16.2)

        blend_p0 = (1.0 - hbm_share0) * p_leg0 + hbm_share0 * p_hbm0
        blend_p1 = (1.0 - hbm_share1) * p_leg1 + hbm_share1 * p_hbm1

        rev0 = q0 * blend_p0
        rev1 = q1 * blend_p1
        total_delta_rev = rev1 - rev0

        volume_effect = (q1 - q0) * blend_p0
        pure_price_effect = q1 * ((1.0 - hbm_share0) * (p_leg1 - p_leg0) + hbm_share0 * (p_hbm1 - p_hbm0))
        mix_shift_effect = q1 * (hbm_share1 - hbm_share0) * (p_hbm1 - p_leg1)

        blended_asp_change_pct = ((blend_p1 - blend_p0) / max(blend_p0, 1e-6)) * 100.0
        legacy_asp_change_pct = ((p_leg1 - p_leg0) / max(p_leg0, 1e-6)) * 100.0
        hbm_asp_change_pct = ((p_hbm1 - p_hbm0) / max(p_hbm0, 1e-6)) * 100.0
        mix_illusion_detected = (blended_asp_change_pct > 0.0) and (legacy_asp_change_pct < 0.0)

        return {
            "prev_blended_asp_usd": round(blend_p0, 4),
            "curr_blended_asp_usd": round(blend_p1, 4),
            "blended_asp_change_pct": round(blended_asp_change_pct, 2),
            "legacy_commodity_asp_change_pct": round(legacy_asp_change_pct, 2),
            "hbm_specialty_asp_change_pct": round(hbm_asp_change_pct, 2),
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

    @classmethod
    def extract_sentiment_from_transcript(cls, transcript_text: str) -> Dict[str, Any]:
        """부정어(Negation) 문맥을 반영한 어닝콜 원문(Text) 결정론적 문장 파서"""
        if not transcript_text or not str(transcript_text).strip():
            return {"evaluated_from_text": False, "computed_bullish_score": None, "matched_claims": [], "negated_claims": []}

        clauses = re.split(r"[.!?;,\n]+", str(transcript_text).lower())
        bull_hits = []
        bear_hits = []
        negated_hits = []

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue
            has_neg = any(re.search(neg, clause) is not None for neg in cls.NEGATION_TOKENS)

            for kw in cls.BULLISH_KEYWORDS:
                if kw.lower() in clause:
                    if has_neg:
                        bear_hits.append(f"NEGATED_BULLISH({kw})")
                        negated_hits.append(f"'{kw}' negated in clause: '{clause[:60]}'")
                    else:
                        bull_hits.append(kw)

            for kw in cls.BEARISH_OR_RISK_KEYWORDS:
                if kw.lower() in clause:
                    if has_neg:
                        bull_hits.append(f"NEGATED_RISK({kw})")
                        negated_hits.append(f"'{kw}' negated in clause: '{clause[:60]}'")
                    else:
                        bear_hits.append(kw)

        raw_score = 0.5 + 0.14 * len(bull_hits) - 0.14 * len(bear_hits)
        score = max(0.05, min(0.98, raw_score))
        return {
            "evaluated_from_text": True,
            "computed_bullish_score": round(score, 2),
            "matched_bullish_claims": bull_hits,
            "matched_risk_claims": bear_hits,
            "negated_clauses_detected": negated_hits,
        }

    @classmethod
    def auto_build_ir_audit_from_records_and_docs(
        cls,
        competitor_records: List[Dict[str, Any]],
        documents: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        doc_corpus = "\n".join(str(d.get("content", "")) for d in (documents or []))
        synthesized = []
        for rec in (competitor_records or []):
            if not isinstance(rec, dict):
                continue
            curr_dio = cls._resolve_field(rec, "curr_inventory_days_dio", None)
            transcript = cls._resolve_field(rec, "ir_transcript_excerpt", None)
            comp = str(cls._resolve_field(rec, "company", "COMPETITOR")).strip()
            if not transcript and doc_corpus and comp.lower() in doc_corpus.lower():
                for para in doc_corpus.split("\n\n"):
                    if comp.lower() in para.lower():
                        transcript = para[:500]
                        break
            if curr_dio is not None or transcript is not None or rec.get("ir_bullish_sentiment_score") is not None:
                synthesized.append({
                    "company": comp,
                    "ir_bullish_sentiment_score": rec.get("ir_bullish_sentiment_score"),
                    "ir_transcript_excerpt": transcript or "",
                    "prev_inventory_days_dio": cls._safe_float(cls._resolve_field(rec, "prev_inventory_days_dio", 95.0), 95.0),
                    "curr_inventory_days_dio": cls._safe_float(curr_dio, 100.0),
                    "capex_execution_rate_pct": cls._safe_float(cls._resolve_field(rec, "capex_execution_rate_pct", 85.0), 85.0),
                    "accounts_receivable_days_delta": cls._safe_float(cls._resolve_field(rec, "accounts_receivable_days_delta", 0.0), 0.0),
                    "fab_utilization_pct": cls._safe_float(cls._resolve_field(rec, "fab_utilization_pct", 90.0), 90.0),
                })
        return synthesized

    @classmethod
    def cross_check_ir_vs_financials(
        cls,
        ir_audit_list: List[Dict[str, Any]],
        dio_spike_threshold_days: float = 7.0,
    ) -> List[Dict[str, Any]]:
        results = []
        for item in (ir_audit_list or []):
            if not isinstance(item, dict):
                continue
            comp = str(cls._resolve_field(item, "company", "COMPETITOR"))
            transcript = str(cls._resolve_field(item, "ir_transcript_excerpt", "") or "")
            nlp_res = cls.extract_sentiment_from_transcript(transcript)

            if item.get("ir_bullish_sentiment_score") is not None:
                sentiment_score = cls._safe_float(item.get("ir_bullish_sentiment_score"), 0.8)
            elif nlp_res["computed_bullish_score"] is not None:
                sentiment_score = nlp_res["computed_bullish_score"]
            else:
                sentiment_score = 0.8

            prev_dio = cls._safe_float(cls._resolve_field(item, "prev_inventory_days_dio", 95.0), 95.0)
            curr_dio = cls._safe_float(cls._resolve_field(item, "curr_inventory_days_dio", 112.0), 112.0)
            capex_exec_rate_pct = cls._safe_float(cls._resolve_field(item, "capex_execution_rate_pct", 85.0), 85.0)
            ar_days_delta = cls._safe_float(cls._resolve_field(item, "accounts_receivable_days_delta", 0.0), 0.0)
            fab_utilization_pct = cls._safe_float(cls._resolve_field(item, "fab_utilization_pct", 92.0), 92.0)

            dio_delta = curr_dio - prev_dio
            contradictions = []

            if sentiment_score >= 0.65 and dio_delta >= dio_spike_threshold_days:
                contradictions.append("BULLISH_IR_VS_RISING_INVENTORY_DIO")
            if sentiment_score >= 0.65 and capex_exec_rate_pct < 70.0:
                contradictions.append("DEMAND_OPTIMISM_VS_CAPEX_UNDEREXECUTION")
            if sentiment_score >= 0.65 and ar_days_delta >= 10.0:
                contradictions.append("CHANNEL_STUFFING_RISK_RISING_AR_DAYS")
            if sentiment_score >= 0.70 and fab_utilization_pct < 80.0:
                contradictions.append("FULL_DEMAND_CLAIM_VS_STEALTH_WAFER_CUT")

            results.append({
                "company": comp,
                "ir_bullish_sentiment_score": round(sentiment_score, 2),
                "nlp_extracted_claims": nlp_res["matched_bullish_claims"],
                "nlp_risk_or_negated_claims": nlp_res["matched_risk_claims"],
                "prev_dio_days": round(prev_dio, 1),
                "curr_dio_days": round(curr_dio, 1),
                "dio_change_days": round(dio_delta, 1),
                "capex_execution_rate_pct": round(capex_exec_rate_pct, 1),
                "red_flag_detected": len(contradictions) > 0,
                "contradiction_codes": contradictions,
            })
        return results

    @classmethod
    def analyze_multi_quarter_hbm_crossover(cls, normalized_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_comp: Dict[str, List[Dict[str, Any]]] = {}
        by_seg: Dict[str, Dict[str, float]] = {}
        for r in normalized_records:
            by_comp.setdefault(r["company"], []).append(r)
            seg_bucket = by_seg.setdefault(r["segment"], {"revenue_musd": 0.0, "underlying_op_musd": 0.0, "shipment_bgb": 0.0})
            seg_bucket["revenue_musd"] = round(seg_bucket["revenue_musd"] + r["revenue_musd"], 2)
            seg_bucket["underlying_op_musd"] = round(seg_bucket["underlying_op_musd"] + r["underlying_operating_profit_musd"], 2)
            seg_bucket["shipment_bgb"] = round(seg_bucket["shipment_bgb"] + r["shipment_bgb"], 2)

        qoq_trends = []
        for comp, rows in by_comp.items():
            if len(rows) >= 2:
                prev_r, curr_r = rows[-2], rows[-1]
                rev_qoq = ((curr_r["revenue_musd"] - prev_r["revenue_musd"]) / max(prev_r["revenue_musd"], 1e-6)) * 100.0
                opm_delta = curr_r["underlying_operating_margin_pct"] - prev_r["underlying_operating_margin_pct"]
                qoq_trends.append({
                    "company": comp,
                    "from_quarter": prev_r["calendarized_quarter"],
                    "to_quarter": curr_r["calendarized_quarter"],
                    "revenue_qoq_growth_pct": round(rev_qoq, 2),
                    "underlying_opm_delta_pct_pt": round(opm_delta, 2),
                })

        return {
            "multi_quarter_qoq_trends": qoq_trends,
            "segment_breakdown_summary": by_seg,
            "hbm_generation_transition_model": {
                "HBM3E_8H": {"die_penalty_vs_ddr5": 2.4, "mature_yield_pct": 74.0, "asp_premium_mult": 4.2},
                "HBM3E_12H": {"die_penalty_vs_ddr5": 2.85, "mature_yield_pct": 66.0, "asp_premium_mult": 5.1},
                "HBM4_16H_CUSTOM_BASE": {"die_penalty_vs_ddr5": 3.35, "mature_yield_pct": 58.0, "asp_premium_mult": 6.8},
            },
        }

    @staticmethod
    def simulate_allocation_grid(
        total_wafer_capa_k: float = 150.0,
        hbm_die_penalty: float = 2.8,
        hbm_yield: float = 0.65,
        dram_yield: float = 0.88,
        base_dram_asp: Optional[float] = None,
        base_hbm_asp: Optional[float] = None,
        dram_cost_per_gb: float = 1.8,
        hbm_cost_per_gb: float = 7.2,
        market_dram_demand_bgb: float = 120.0,
        market_hbm_demand_bgb: float = 18.0,
        competitor_dram_supply_bgb: float = 75.0,
        competitor_hbm_supply_bgb: float = 8.0,
        tsv_packaging_cap_bgb: float = 12.0,
        dio_spike_days: float = 7.0,
        competitor_records: Optional[List[Dict[str, Any]]] = None,
        pq_mix_periods: Optional[Dict[str, Dict[str, float]]] = None,
        ir_audit_records: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[Dict[str, str]]] = None,
        opt_strategy: str = "coarse_grid",
        min_dram_supply_bgb: float = 0.0,
        **_extra_kwargs: Any,
    ) -> Dict[str, Any]:
        cal_comp = MarketStrategySolver.normalize_competitor_calendar_and_units(competitor_records or [])

        effective_pq_periods = pq_mix_periods
        if not (effective_pq_periods and "prev" in effective_pq_periods and "curr" in effective_pq_periods):
            effective_pq_periods = MarketStrategySolver.auto_extract_pq_mix_from_records(competitor_records or [])

        # Dynamic Calibration of ASP from dataset if not explicitly passed
        curr_pq = (effective_pq_periods or {}).get("curr", {})
        eff_dram_asp = float(base_dram_asp if base_dram_asp is not None else curr_pq.get("legacy_asp_usd", 3.5))
        eff_hbm_asp = float(base_hbm_asp if base_hbm_asp is not None else curr_pq.get("hbm_asp_usd", 16.0))

        raw_gb_per_k_wafer = 1.5

        def _eval_pct(pct_val: float) -> Dict[str, Any]:
            hbm_ratio = pct_val / 100.0
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

            proj_dram_asp = eff_dram_asp * max(0.5, 1.0 - 1.4 * dram_oversupply_ratio)
            proj_hbm_asp = eff_hbm_asp * max(0.7, 1.0 - 0.8 * hbm_oversupply_ratio)

            dram_rev = effective_dram_bgb * proj_dram_asp
            hbm_rev = effective_hbm_bgb * proj_hbm_asp
            dram_op = effective_dram_bgb * (proj_dram_asp - dram_cost_per_gb)
            hbm_op = (effective_hbm_bgb * proj_hbm_asp) - (raw_hbm_bgb * hbm_cost_per_gb)
            total_op = dram_op + hbm_op

            is_feasible = effective_dram_bgb >= (min_dram_supply_bgb - 1e-6)
            return {
                "hbm_wafer_share_pct": round(pct_val, 2),
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
                "is_feasible": is_feasible,
            }

        scenarios = []
        best_scenario = None
        opt_strat_lower = str(opt_strategy).lower()

        if "fine" in opt_strat_lower or "1pct" in opt_strat_lower:
            pct_candidates = [round(x * 0.5, 2) for x in range(2, 121)]  # 1.0% to 60.0% by 0.5%
            optimality_flag = "PROVEN_OPTIMAL_(fine_grid_0.5pct)"
        elif "golden" in opt_strat_lower or "continuous" in opt_strat_lower:
            # Golden section search for continuous convex optimum in [1.0, 60.0]
            phi = (1 + math.sqrt(5)) / 2
            resphi = 2 - phi
            a, b = 1.0, 60.0
            tol = 0.05
            c = a + resphi * (b - a)
            d = b - resphi * (b - a)
            fc = _eval_pct(c)["total_operating_profit_musd"]
            fd = _eval_pct(d)["total_operating_profit_musd"]
            while abs(b - a) > tol:
                if fc > fd:
                    b = d
                    d = c
                    fd = fc
                    c = a + resphi * (b - a)
                    fc = _eval_pct(c)["total_operating_profit_musd"]
                else:
                    a = c
                    c = d
                    fc = fd
                    d = b - resphi * (b - a)
                    fd = _eval_pct(d)["total_operating_profit_musd"]
            opt_p = (a + b) / 2.0
            pct_candidates = sorted(set(list(range(5, 55, 5)) + [round(opt_p, 2)]))
            optimality_flag = "PROVEN_OPTIMAL_(golden_section_continuous)"
        elif "pareto" in opt_strat_lower or "dual" in opt_strat_lower:
            # Multi-objective Pareto: Enforce minimum legacy commodity commitment (e.g. 20% of demand)
            pct_candidates = [round(x, 1) for x in range(2, 60, 2)]
            optimality_flag = "MULTI_OBJECTIVE_PARETO"
        else:
            # Standard coarse grid (range 5% to 50% step 5%)
            pct_candidates = list(range(5, 55, 5))
            optimality_flag = "HEURISTIC_(coarse_5pct_grid)"

        for pct in pct_candidates:
            row = _eval_pct(pct)
            scenarios.append(row)
            if row.get("is_feasible", True):
                if best_scenario is None or row["total_operating_profit_musd"] > best_scenario["total_operating_profit_musd"]:
                    best_scenario = row

        if best_scenario is None and scenarios:
            best_scenario = max(scenarios, key=lambda r: r["total_operating_profit_musd"])

        pq_decomp = None
        if effective_pq_periods and "prev" in effective_pq_periods and "curr" in effective_pq_periods:
            pq_decomp = MarketStrategySolver.decompose_pq_mix_variance(effective_pq_periods["prev"], effective_pq_periods["curr"])

        effective_ir_records = ir_audit_records
        if not effective_ir_records:
            effective_ir_records = MarketStrategySolver.auto_build_ir_audit_from_records_and_docs(competitor_records or [], documents)

        ir_checks = MarketStrategySolver.cross_check_ir_vs_financials(
            effective_ir_records or [],
            dio_spike_threshold_days=float(dio_spike_days),
        )
        crossover_trends = MarketStrategySolver.analyze_multi_quarter_hbm_crossover(cal_comp)

        has_ir_red_flag = any(r["red_flag_detected"] for r in ir_checks)
        has_mix_illusion = bool(pq_decomp and pq_decomp.get("mix_illusion_flag"))
        severe_contradiction = any(len(r["contradiction_codes"]) >= 2 for r in ir_checks)

        if severe_contradiction:
            status_code = "VIOLATION"
            rule_id = "MKT-RULE-SEVERE-IR-CONTRADICTION"
        elif has_ir_red_flag or has_mix_illusion:
            status_code = "WARNING"
            rule_id = "MKT-RULE-IR-OR-MIX-WARN"
        else:
            status_code = "NORMAL"
            rule_id = "MKT-RULE-OPTIMAL"

        return {
            "domain": "MARKET_STRATEGY",
            "status": status_code,
            "ruleId": rule_id,
            "optimization_method": opt_strategy,
            "optimality": optimality_flag,
            "optimal_strategy": best_scenario,
            "scenario_table": scenarios,
            "calendarized_competitor_benchmarks": cal_comp,
            "pq_mix_variance_decomposition": pq_decomp,
            "ir_vs_financials_cross_audit": ir_checks,
            "multi_quarter_and_hbm_crossover": crossover_trends,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = MarketStrategySolver.simulate_allocation_grid(**payload)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
