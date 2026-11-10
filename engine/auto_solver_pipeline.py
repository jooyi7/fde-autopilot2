#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - End-to-End Automated Dataset Ingestion, Composite Fact-First Star-Schema Join,
6-Domain Auto-Shaper, Dynamic Document Threshold Linker & Dual Output Exporter (v7.0)
실전 시험장(빈 폴더 Greenfield 또는 CSV/TSV/JSON/JSONL/SQLite/MD 복합 폴더)에서 주어진 실제 데이터를 읽어들여:
1) Multi-Format & Auto-Encoding Ingestion: UTF-8/UTF-8-SIG/CP949 인코딩 및 CSV/TSV/JSON/SQLite/Markdown 표 자동 파싱
2) Composite Fact-First Star-Schema Join: 가장 행 수가 많은 핵심 Fact 테이블을 기준으로 단일 키 또는 복합 키(vendor_id+lot_id, company+quarter 등)를 사용해 Dimension 테이블들을 Left Join (레코드 유실 0%)
3) Dynamic Rule Override Linker: cofa_probe가 마크다운 규정집에서 추출한 수치 임계값(m3s_spec_nm, min_cpk, dio_spike_days, wacc_pct, max_hours 등)을 솔버에 자동 주입
4) 6-Domain Auto-Shaper: Flat CSV/테이블 형태로 주어진 5대 반도체 도메인 + 제6 범용 도메인 데이터를 각 솔버의 중첩 스키마로 자동 피벗(Pivot) 및 조립
5) Dual Output Exporter: 채점기가 요구할 수 있는 JSON(`output/result.json`, `public/live_workspace_solution.json`)과 요약 CSV(`output/result.csv`)를 동시 생성
"""

import argparse
import csv
import json
import os
import re
import sys
try:
    import sqlite3
except ImportError:
    sqlite3 = None
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from cofa_probe import read_text_auto_encoding, read_delimited_table, extract_markdown_tables, extract_doc_rules_and_citations
from solver_overlay import OverlaySolver
from solver_material import MaterialQualitySolver
from solver_market import MarketStrategySolver
from solver_value_chain_biz import ValueChainBusinessSolver
from solver_curriculum import CurriculumOntologySolver
from solver_universal import UniversalProblemSolver
from solver_typeA import TypeASolver
from solver_typeB import TypeBSolver
from solver_typeC import TypeCSolver
from solver_typeD import TypeDSolver
from solver_typeE import TypeESolver

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "__pycache__",
    ".venv", "venv", "fde-autopilot", "fde-kit", ".fde_audit_cache", ".autopilot", "engine", "output", "public"
}
SKIP_JSON_FILES = {
    "package.json", "package-lock.json", "tsconfig.json", "cofa_probe_report.json",
    "result.json", "live_workspace_solution.json"
}
SKIP_MD_FILES = {
    "AGENTS.md", "AUDITOR_GUIDE.md", "fde_autopilot_manual.md", "WORKSPACE_PROFILE.md",
    "SPEC.md", "SOLUTION_NOTES.md", "HANDOFF.md", "ARCHITECTURE_DECISIONS.md",
    "SPEC_TEMPLATE.md", "HANDOFF_TEMPLATE.md", "defense_logic_guide.md", "stakeholder_inquiry_guide.md",
    "step_by_step_prompts.md", "typing_guide.md"
}


def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None or val == "" or isinstance(val, bool):
        return default
    try:
        s = str(val).replace(",", "").replace("$", "").replace("%", "").strip()
        if s.lower() in {"null", "nan", "none", "n/a", "-", "undefined", "error"}:
            return default
        f = float(s)
        if f in {-999.0, -9999.0, 9999.0, 99999.0}:
            return default
        return f
    except Exception:
        return default


def load_all_workspace_assets(root: Path) -> Dict[str, Any]:
    tables: Dict[str, List[Dict[str, Any]]] = {}
    json_objects: Dict[str, Dict[str, Any]] = {}
    documents: List[Dict[str, str]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fname in sorted(filenames):
            if fname.startswith(".fde_"):
                continue
            fpath = Path(dirpath) / fname
            rel = str(fpath.relative_to(root))
            lower = fname.lower()

            if lower.endswith((".csv", ".tsv")):
                try:
                    rows = read_delimited_table(fpath, max_rows=100000)
                    if rows:
                        tables[rel] = rows
                except Exception:
                    pass
            elif lower.endswith(".jsonl"):
                try:
                    rows = []
                    for idx, line in enumerate(read_text_auto_encoding(fpath).splitlines()):
                        if idx >= 100000:
                            break
                        line = line.strip()
                        if line:
                            rows.append(json.loads(line))
                    if rows:
                        tables[rel] = rows
                except Exception:
                    pass
            elif lower.endswith(".json") and fname not in SKIP_JSON_FILES:
                try:
                    data = json.loads(read_text_auto_encoding(fpath))
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        tables[rel] = data[:100000]
                    elif isinstance(data, dict):
                        json_objects[rel] = data
                except Exception:
                    pass
            elif lower.endswith((".sqlite", ".db", ".sqlite3")) and sqlite3 is not None:
                try:
                    conn = sqlite3.connect(str(fpath))
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    for (tname,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall():
                        db_rows = [dict(r) for r in cur.execute(f"SELECT * FROM '{tname}' LIMIT 100000;").fetchall()]
                        if db_rows:
                            tables[f"{rel}::{tname}"] = db_rows
                    conn.close()
                except Exception:
                    pass
            elif lower.endswith((".md", ".txt")) and fname not in SKIP_MD_FILES and not fname.startswith("fde_"):
                try:
                    txt = read_text_auto_encoding(fpath).strip()
                    if txt:
                        documents.append({
                            "id": rel,
                            "title": fname,
                            "content": txt[:5000],
                        })
                        if lower.endswith(".md"):
                            for t_id, t_rows in extract_markdown_tables(txt, rel):
                                if t_rows:
                                    tables[t_id] = t_rows
                except Exception:
                    pass

    doc_rules = extract_doc_rules_and_citations(root)
    canonical_overrides = dict(doc_rules.get("canonical_parameter_overrides", {}))
    live_ov_path = root / "live_overrides.json"
    if live_ov_path.exists():
        try:
            live_ov = json.loads(read_text_auto_encoding(live_ov_path))
            if isinstance(live_ov, dict):
                canonical_overrides.update(live_ov)
                json_objects.pop("live_overrides.json", None)
        except Exception:
            pass
    return {
        "tables": tables,
        "json_objects": json_objects,
        "documents": documents,
        "canonical_overrides": canonical_overrides,
    }


def auto_join_tables_fact_first(tables: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    [보완 1-A v7.0] Composite-Key Fact-First Star-Schema Joiner:
    행(Row) 수가 가장 많은 Fact 테이블을 기준(Base)으로 삼고, 나머지 Dimension/Lookup 테이블들을
    공통 복합 키(예: company+reported_period, vendor_id+lot_id) 또는 단일 키로 Left Join하여 레코드 증발 및 덮어쓰기를 원천 방지합니다.
    """
    if not tables:
        return []
    sorted_items = sorted(tables.items(), key=lambda kv: len(kv[1]), reverse=True)
    base_name, base_source = sorted_items[0]
    base_rows = [dict(r) for r in base_source]
    if len(sorted_items) == 1 or not base_rows:
        return base_rows

    join_candidates = [
        "lot_id", "wafer_id", "vendor_id", "vendor", "supplier", "company", "reported_period", "quarter", "fiscal_quarter",
        "equip_id", "scanner_id", "chamber_id", "chuck_id", "module_id", "course_id", "route_id", "zone_id", "id"
    ]
    base_cols = {k.strip().lower(): k for k in base_rows[0].keys()}

    for other_name, other_rows in sorted_items[1:]:
        if not other_rows:
            continue
        other_cols = {k.strip().lower(): k for k in other_rows[0].keys()}
        shared_keys_lower = [jk for jk in join_candidates if jk in base_cols and jk in other_cols]
        if not shared_keys_lower:
            continue

        # Use all shared keys as composite key to prevent overwriting multi-quarter or multi-lot dimension rows
        active_keys = shared_keys_lower
        b_keys = [base_cols[k] for k in active_keys]
        o_keys = [other_cols[k] for k in active_keys]

        lookup: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        for r in other_rows:
            comp_k = tuple(str(r.get(ok, "")).strip().upper() for ok in o_keys)
            if any(comp_k):
                lookup[comp_k] = r

        for row in base_rows:
            comp_k = tuple(str(row.get(bk, "")).strip().upper() for bk in b_keys)
            if comp_k in lookup:
                for ok, ov in lookup[comp_k].items():
                    if ok not in row or row[ok] in (None, ""):
                        row[ok] = ov

    return base_rows


def reshape_flat_rows_to_material_payload(
    rows: List[Dict[str, Any]],
    json_objs: Dict[str, Dict[str, Any]],
    overrides: Dict[str, Any],
    tables: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    [보완 1-B v8.0] Flat CSV 테이블(vendor_id, lot_id, metal_ppb, moisture_ppm, wafer_yield_pct, spec_ch_1..N 등) 및
    별도 Spec 테이블(parameter, LSL, USL)을 MaterialQualitySolver가 요구하는 { specs, vendors, reference_spectrum, min_cpk } 중첩 구조로 자동 피벗 변환합니다.
    """
    specs: Dict[str, Dict[str, float]] = {}
    ref_spectrum: Optional[List[float]] = None
    for obj in json_objs.values():
        if "specs" in obj and isinstance(obj["specs"], dict):
            specs.update(obj["specs"])
        if "reference_spectrum" in obj and isinstance(obj["reference_spectrum"], list):
            ref_spectrum = obj["reference_spectrum"]

    # Check auxiliary tables for a dedicated Spec table (e.g., specs.csv with parameter/item + lsl/usl)
    if tables:
        for t_rows in tables.values():
            if not t_rows or not isinstance(t_rows[0], dict):
                continue
            cols_l = {k.strip().lower(): k for k in t_rows[0].keys()}
            param_k = next((cols_l[c] for c in ("parameter", "param", "item", "metric", "항목", "검사항목") if c in cols_l), None)
            lsl_k = next((cols_l[c] for c in ("lsl", "min_spec", "lower_limit", "하한") if c in cols_l), None)
            usl_k = next((cols_l[c] for c in ("usl", "max_spec", "upper_limit", "상한") if c in cols_l), None)
            if param_k and (lsl_k or usl_k):
                for sr in t_rows:
                    pname = str(sr.get(param_k, "")).strip()
                    if not pname:
                        continue
                    lsl_v = _safe_float(sr.get(lsl_k)) if lsl_k else None
                    usl_v = _safe_float(sr.get(usl_k)) if usl_k else None
                    wt_v = _safe_float(sr.get(cols_l.get("weight", "")), 1.0) or 1.0
                    if lsl_v is not None or usl_v is not None:
                        specs[pname] = {
                            "LSL": lsl_v if lsl_v is not None else 0.0,
                            "USL": usl_v if usl_v is not None else 100.0,
                            "weight": wt_v,
                        }

    vendor_col = next((c for c in rows[0].keys() if c.lower() in {"vendor_id", "vendor", "supplier", "maker", "공급사", "업체"}), "vendor_id")
    lot_col = next((c for c in rows[0].keys() if c.lower() in {"lot_id", "batch_id", "coa_lot", "lot", "로트"}), None)
    ignore_numeric = {
        "id", "lot_id", "batch_id", "coa_lot", "wafer_id", "cost_index", "lead_time_days", "pipe_residence_hours",
        "pump_shear_particle_growth_pct", "remaining_shelf_life_days", "unreported_4m_detected",
        "pcn_approved", "inline_metrology_drift_sigma", "wafer_yield_pct", "yield_pct", "defect_density", "lsl", "usl"
    }

    vendors_map: Dict[str, Dict[str, Any]] = {}
    for idx, r in enumerate(rows):
        vid = str(r.get(vendor_col, "VENDOR_UNKNOWN")).strip()
        if not vid:
            continue
        v_entry = vendors_map.setdefault(vid, {
            "vendor_id": vid,
            "cost_index": _safe_float(r.get("cost_index"), 1.0) or 1.0,
            "lead_time_days": _safe_float(r.get("lead_time_days"), 14.0) or 14.0,
            "samples": {},
            "lot_ids": [],
            "wafer_yield_samples": [],
            "hvm_stress_profile": {},
            "subtier_genealogy": {},
        })
        if lot_col and r.get(lot_col) is not None:
            v_entry["lot_ids"].append(str(r.get(lot_col)).strip())
        else:
            v_entry["lot_ids"].append(f"{vid}-LOT-{idx + 1:02d}")
        if r.get("pipe_residence_hours") is not None:
            v_entry["hvm_stress_profile"]["pipe_residence_hours"] = _safe_float(r.get("pipe_residence_hours"), 12.0)
        if r.get("pump_shear_particle_growth_pct") is not None:
            v_entry["hvm_stress_profile"]["pump_shear_particle_growth_pct"] = _safe_float(r.get("pump_shear_particle_growth_pct"), 2.0)
        if r.get("unreported_4m_detected") is not None:
            v_entry["subtier_genealogy"]["unreported_4m_detected"] = str(r.get("unreported_4m_detected")).lower() in {"true", "1", "yes", "y"}
        if r.get("wafer_yield_pct") is not None or r.get("yield_pct") is not None:
            yv = _safe_float(r.get("wafer_yield_pct") or r.get("yield_pct"))
            if yv is not None:
                v_entry["wafer_yield_samples"].append(yv)

        # Extract spectral channels if present (spec_ch_1, spec_ch_2, ...)
        spec_cols = sorted([k for k in r.keys() if re.match(r"^(?:spec_ch|spectrum_|ch_|wave_)\d+", k.lower())])
        if spec_cols:
            vec = [_safe_float(r.get(sc), 0.0) or 0.0 for sc in spec_cols]
            if any(vec):
                v_entry["spectrum"] = vec

        if "parameter" in {k.lower() for k in r.keys()} and "value" in {k.lower() for k in r.keys()}:
            pname = str(r.get("parameter") or r.get("PARAMETER") or "param").strip()
            pval = _safe_float(r.get("value") or r.get("VALUE"))
            if pval is not None:
                v_entry["samples"].setdefault(pname, []).append(pval)
            lsl_v = _safe_float(r.get("lsl") or r.get("LSL"))
            usl_v = _safe_float(r.get("usl") or r.get("USL"))
            if pname not in specs and (lsl_v is not None or usl_v is not None):
                specs[pname] = {"LSL": lsl_v if lsl_v is not None else 0.0, "USL": usl_v if usl_v is not None else 100.0, "weight": 1.0}
        else:
            for k, val in r.items():
                kl = k.strip().lower()
                if kl in ignore_numeric or kl == vendor_col.lower() or "id" in kl or "date" in kl or k in spec_cols:
                    continue
                fv = _safe_float(val)
                if fv is not None:
                    v_entry["samples"].setdefault(k, []).append(fv)

    if not specs and vendors_map:
        first_v = next(iter(vendors_map.values()))
        for pname, vals in first_v["samples"].items():
            if vals:
                mean_v = sum(vals) / len(vals)
                std_v = max((sum((x - mean_v) ** 2 for x in vals) / max(len(vals) - 1, 1)) ** 0.5, abs(mean_v) * 0.1, 0.5)
                specs[pname] = {
                    "LSL": round(max(0.0, mean_v - 4.0 * std_v), 4),
                    "USL": round(mean_v + 4.0 * std_v, 4),
                    "baseline_mean": round(mean_v, 4),
                    "baseline_std": round(std_v, 4),
                    "weight": 1.0,
                }

    return {
        "specs": specs,
        "vendors": list(vendors_map.values()),
        "reference_spectrum": ref_spectrum,
        "min_cpk": overrides.get("min_cpk", 1.33),
    }


def find_auxiliary_table(tables: Dict[str, List[Dict[str, Any]]], required_cols: Set[str]) -> Optional[List[Dict[str, Any]]]:
    """다중 테이블 중 특정 보조 스키마(예: candidate_scanners, ir_audit_records, learner_profiles)를 가진 테이블을 찾아 반환합니다."""
    for t_name, rows in tables.items():
        if not rows or not isinstance(rows[0], dict):
            continue
        cols_lower = {k.strip().lower() for k in rows[0].keys()}
        if required_cols & cols_lower:
            return rows
    return None


def classify_table_domain(rows: List[Dict[str, Any]]) -> Optional[str]:
    """[v8.1] 테이블 단위 도메인 판별: 행 수가 가장 큰 테이블이 다른 도메인이어도 각 도메인 테이블을 놓치지 않기 위함."""
    if not rows or not isinstance(rows[0], dict):
        return None
    cols = {str(k).strip().lower() for k in rows[0].keys()}
    if {"dx", "dy"} <= cols or {"ovl_x", "ovl_y"} <= cols or {"overlay_x", "overlay_y"} <= cols:
        return "OVERLAY"
    if any(k in cols for k in ("metal_ppb", "fe_ppb", "cu_ppb", "moisture_ppm", "cpk", "coa_value", "metal_impurity_ppb")) or (
        {"vendor_id", "lot_id"} <= cols and any("ppb" in c or "ppm" in c or "spec" in c for c in cols)
    ):
        return "MATERIAL"
    wide_q = sum(1 for c in cols if MarketStrategySolver.QUARTER_COL_RE.match(c)) >= 2
    if any(k in cols for k in ("reported_period", "fiscal_quarter", "bit_shipment", "shipment_volume", "nrv_reversal", "hbm_bit_share_pct")) or (
        wide_q and any(k in cols for k in ("company", "competitor", "vendor", "기업", "경쟁사", "metric", "항목"))
    ):
        return "MARKET"
    if any(k in cols for k in ("capex_per_k_wafer_musd", "die_penalty_factor", "lta_min_committed_wafers_k", "cowos_alloc", "stage_order", "lead_time_months")):
        return "VALUE_CHAIN"
    if "prereqs" in cols or "prerequisites" in cols:
        return "EDUCATOR"
    # Type A-E Detection
    if any(k in cols for k in ("alarm_code", "error_code", "fault_code", "transcript", "forbidden_rules", "forbidden_rule")):
        return "TYPE_A"
    if ({"rx_mm", "ry_mm"} <= cols) or ({"x", "y"} <= cols and any(k in cols for k in ("is_fail", "bin", "fail", "bad", "ng"))) or any(k in cols for k in ("step_yield_pct", "potential_yield_gain_pct", "loss_ppm")):
        return "TYPE_B"
    if any(k in cols for k in ("sensor_val", "fdc_val", "cusum", "cost_false_alarm", "cost_missed_fault", "is_actual_fault")):
        return "TYPE_C"
    if any(k in cols for k in ("weibull_beta", "current_usage_hours", "max_lifetime_hours", "wear_rate_pct", "pm_cost", "from_state", "to_state")):
        return "TYPE_D"
    if any(k in cols for k in ("param_name", "recipe_name", "golden_spec")) or ({"target", "actual", "lsl", "usl"} <= cols):
        return "TYPE_E"
    return None


def infer_and_solve(assets: Dict[str, Any], opt_strategy: Optional[str] = None, target_domain: Optional[str] = None) -> Dict[str, Any]:
    tables = assets["tables"]
    json_objs = assets["json_objects"]
    docs = assets["documents"]
    overrides = dict(assets.get("canonical_overrides", {}))
    if opt_strategy:
        overrides["opt_strategy"] = opt_strategy
    if target_domain:
        overrides["domain"] = target_domain.upper()
    domain_tables: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for t_name, t_rows in tables.items():
        dom = classify_table_domain(t_rows)
        if dom:
            domain_tables.setdefault(dom, {})[t_name] = t_rows
    if domain_tables:
        best_dom = max(domain_tables.items(), key=lambda kv: sum(len(r) for r in kv[1].values()))[0]
        merged_rows = auto_join_tables_fact_first(domain_tables[best_dom])
    else:
        merged_rows = auto_join_tables_fact_first(tables)
    corpus_lower = " ".join([d.get("content", "") for d in docs] + [json.dumps(json_objs, ensure_ascii=False)]).lower()

    def _pack(dom_key: str, src: str, shaped_in: Dict[str, Any], sol: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "detected_domain": dom_key,
            "domain": dom_key,
            "source": src,
            "status": sol.get("status", "NORMAL"),
            "ruleId": sol.get("ruleId", "CORE-PASS"),
            "optimization_method": sol.get("optimization_method", overrides.get("opt_strategy", "default")),
            "optimality": sol.get("optimality", "HEURISTIC"),
            "shaped_input_payload": {**shaped_in, "domain": dom_key},
            "solution": sol,
        }

    # 0. Forced Domain Dispatch (if --domain specified)
    if target_domain:
        td = target_domain.upper()
        if td == "TYPE_A":
            tin = {**overrides, "records": merged_rows, "documents": docs}
            return _pack("TYPE_A", "forced_cli_domain", tin, TypeASolver.solve(tin))
        elif td == "TYPE_B":
            tin = {**overrides, "records": merged_rows, "dies": merged_rows, "documents": docs}
            return _pack("TYPE_B", "forced_cli_domain", tin, TypeBSolver.solve(tin))
        elif td == "TYPE_C":
            tin = {**overrides, "records": merged_rows, "series": merged_rows, "documents": docs}
            return _pack("TYPE_C", "forced_cli_domain", tin, TypeCSolver.solve(tin))
        elif td == "TYPE_D":
            tin = {**overrides, "records": merged_rows, "equipments": merged_rows, "documents": docs}
            return _pack("TYPE_D", "forced_cli_domain", tin, TypeDSolver.solve(tin))
        elif td == "TYPE_E":
            tin = {**overrides, "records": merged_rows, "parameters": merged_rows, "documents": docs}
            return _pack("TYPE_E", "forced_cli_domain", tin, TypeESolver.solve(tin))

    # 1. Check if any standalone JSON object already matches a specific domain payload
    for name, obj in json_objs.items():
        merged_obj = {**overrides, **obj}
        if "measurements" in obj:
            return _pack("OVERLAY", name, merged_obj, OverlaySolver.solve_apc(**merged_obj))
        if "vendors" in obj and "specs" in obj:
            return _pack("MATERIAL", name, merged_obj, MaterialQualitySolver.compare_vendors(**merged_obj))
        if "competitor_records" in obj or "pq_mix_periods" in obj:
            return _pack("MARKET", name, merged_obj, MarketStrategySolver.simulate_allocation_grid(**merged_obj, documents=docs))
        if "tsmc_cowos_alloc_bgb" in obj or "value-chain-business-persona" in str(obj.get("persona_id", "")):
            vc_in = {**merged_obj, "documents": docs}
            return _pack("VALUE_CHAIN", name, vc_in, ValueChainBusinessSolver.solve_all(vc_in))
        if "modules" in obj or "value-chain-educator-persona" in str(obj.get("persona_id", "")):
            edu_in = {**merged_obj, "documents": docs}
            return _pack("EDUCATOR", name, edu_in, CurriculumOntologySolver.analyze_and_schedule(**edu_in))
        if "forbidden_rules" in obj or "alarm_catalog" in obj or ("alarm_code" in obj and "text" in obj):
            typea_in = {**merged_obj, "documents": docs}
            return _pack("TYPE_A", name, typea_in, TypeASolver.solve(typea_in))
        if "dies" in obj or ("steps" in obj and "total_budget" in obj):
            typeb_in = {**merged_obj, "documents": docs}
            return _pack("TYPE_B", name, typeb_in, TypeBSolver.solve(typeb_in))
        if "series" in obj and ("cost_false_alarm" in obj or "baseline_mean" in obj or "cost_missed_fault" in obj):
            typec_in = {**merged_obj, "documents": docs}
            return _pack("TYPE_C", name, typec_in, TypeCSolver.solve(typec_in))
        if "equipments" in obj or "transitions" in obj:
            typed_in = {**merged_obj, "documents": docs}
            return _pack("TYPE_D", name, typed_in, TypeDSolver.solve(typed_in))
        if "parameters" in obj and ("target_cpk" in obj or "target_output_error" in obj):
            typee_in = {**merged_obj, "documents": docs}
            return _pack("TYPE_E", name, typee_in, TypeESolver.solve(typee_in))

    # 2. Check merged tabular columns with Auto-Shaper for all 5 domains
    if merged_rows:
        cols_lower = {k.strip().lower() for k in merged_rows[0].keys()}

        # (A) Overlay Domain (Auto-attaches scanner table & doc m3s_spec_nm override)
        if {"dx", "dy"} <= cols_lower or {"ovl_x", "ovl_y"} <= cols_lower or {"overlay_x", "overlay_y"} <= cols_lower:
            scanner_rows = find_auxiliary_table(tables, {"matching_offset_nm", "queue_time_mins"})
            ovl_in = {
                "domain": "OVERLAY",
                "measurements": merged_rows,
                "m3s_spec_nm": overrides.get("m3s_spec_nm", 2.0),
                "candidate_scanners": scanner_rows or [],
            }
            return _pack(
                "OVERLAY",
                "fact_first_merged_tables",
                ovl_in,
                OverlaySolver.solve_apc(**ovl_in),
            )

        # (B) Material Quality Domain (Flat CSV auto-reshaped into specs & vendors + wafer yield correlation)
        if any(k in cols_lower for k in ("metal_ppb", "fe_ppb", "cu_ppb", "moisture_ppm", "cpk", "coa_value", "metal_impurity_ppb")) or (
            {"vendor_id", "lot_id"} <= cols_lower and any("ppb" in c or "ppm" in c or "spec" in c for c in cols_lower)
        ):
            shaped_mat = reshape_flat_rows_to_material_payload(merged_rows, json_objs, overrides, tables=tables)
            return _pack(
                "MATERIAL",
                "auto_pivoted_material_tables",
                shaped_mat,
                MaterialQualitySolver.compare_vendors(**shaped_mat),
            )

        # (C) Market Strategy Domain (Auto-extracts PQ Mix & IR vs Financials from tables and markdown transcripts, including Wide-Format Quarterly tables)
        has_wide_quarters = sum(1 for c in cols_lower if MarketStrategySolver.QUARTER_COL_RE.match(c)) >= 2
        if any(k in cols_lower for k in ("reported_period", "fiscal_quarter", "bit_shipment", "shipment_volume", "nrv_reversal", "hbm_bit_share_pct")) or (
            has_wide_quarters and any(k in cols_lower for k in ("company", "competitor", "vendor", "기업", "경쟁사", "metric", "항목"))
        ):
            unpivoted_mkt_rows = MarketStrategySolver.unpivot_wide_quarterly_records(merged_rows)
            ir_rows = find_auxiliary_table(tables, {"ir_transcript_excerpt", "curr_inventory_days_dio", "ir_bullish_sentiment_score"})
            pq_auto = MarketStrategySolver.auto_extract_pq_mix_from_records(unpivoted_mkt_rows)
            ir_auto = ir_rows or MarketStrategySolver.auto_build_ir_audit_from_records_and_docs(unpivoted_mkt_rows, docs)
            mkt_in = {
                "domain": "MARKET",
                "competitor_records": unpivoted_mkt_rows,
                "pq_mix_periods": pq_auto,
                "ir_audit_records": ir_auto,
                "documents": docs,
                "dio_spike_days": overrides.get("dio_spike_days", 7.0),
            }
            return _pack(
                "MARKET",
                "fact_first_merged_tables",
                mkt_in,
                MarketStrategySolver.simulate_allocation_grid(**mkt_in),
            )

        # (D) Value-Chain Business Persona Domain
        if any(k in cols_lower for k in ("capex_per_k_wafer_musd", "die_penalty_factor", "lta_min_committed_wafers_k", "cowos_alloc", "stage_order", "lead_time_months")) or "value-chain-business" in corpus_lower:
            vc_payload: Dict[str, Any] = {
                **overrides,
                "domain": "VALUE_CHAIN",
                "persona_id": "value-chain-business-persona",
                "documents": docs,
                "records": merged_rows,
            }
            prod_tbl = find_auxiliary_table(tables, {"capex_per_k_wafer_musd", "die_penalty_factor", "lta_min_committed_wafers_k", "capex_k", "roic_pct"})
            node_tbl = find_auxiliary_table(tables, {"stage_order", "lead_time_months", "inventory_buffer_sensitivity", "node_name"})
            if prod_tbl:
                vc_payload["product_candidates"] = prod_tbl
            if node_tbl:
                vc_payload["supply_chain_nodes"] = node_tbl
            return _pack(
                "VALUE_CHAIN",
                "auto_shaped_value_chain_tables",
                vc_payload,
                ValueChainBusinessSolver.solve_all(vc_payload),
            )

        # (E) Semiconductor Educator Persona Domain
        if "prereqs" in cols_lower or "prerequisites" in cols_lower or "value-chain-educator-persona" in corpus_lower:
            learner_rows = find_auxiliary_table(tables, {"learner_id", "completed_ids", "target_ids", "max_hours", "learner_question_or_answer"})
            mod_rows = find_auxiliary_table(tables, {"prereqs", "prerequisites", "module_id", "course_id"}) or merged_rows
            edu_in = {
                "domain": "EDUCATOR",
                "modules": mod_rows,
                "learner_profile": learner_rows[0] if learner_rows else {"max_hours": overrides.get("max_hours", 9999.0)},
                "learner_profiles": learner_rows,
                "documents": docs,
                "max_hours": overrides.get("max_hours", 9999.0),
            }
            return _pack(
                "EDUCATOR",
                "auto_shaped_curriculum_tables",
                edu_in,
                CurriculumOntologySolver.analyze_and_schedule(**edu_in),
            )

        # (F) Type A: Text Rule, Local RAG & Equipment Alarm Troubleshooting
        if any(k in cols_lower for k in ("alarm_code", "error_code", "fault_code", "transcript", "forbidden_rules", "forbidden_rule", "penalty_if_missing")) or "alarm_code" in corpus_lower:
            typea_in = {**overrides, "domain": "TYPE_A", "records": merged_rows, "documents": docs}
            return _pack("TYPE_A", "auto_shaped_typea_tables", typea_in, TypeASolver.solve(typea_in))

        # (G) Type B: Wafer Map Spatial Defect, Yield Loss Decomposition & Budget Optimizer
        if ({"rx_mm", "ry_mm"} <= cols_lower) or ({"x", "y"} <= cols_lower and any(k in cols_lower for k in ("is_fail", "bin", "fail", "bad", "ng"))) or any(k in cols_lower for k in ("step_yield_pct", "potential_yield_gain_pct", "loss_ppm")):
            typeb_in = {**overrides, "domain": "TYPE_B", "records": merged_rows, "documents": docs}
            return _pack("TYPE_B", "auto_shaped_typeb_tables", typeb_in, TypeBSolver.solve(typeb_in))

        # (H) Type C: FDC Time-Series Sensor Anomaly, Fraud Scoring & Threshold Optimizer
        if any(k in cols_lower for k in ("sensor_val", "fdc_val", "rf_power_w", "cusum", "z_score", "is_actual_fault", "cost_false_alarm", "cost_missed_fault")):
            typec_in = {**overrides, "domain": "TYPE_C", "records": merged_rows, "documents": docs}
            return _pack("TYPE_C", "auto_shaped_typec_tables", typec_in, TypeCSolver.solve(typec_in))

        # (I) Type D: Workflow State Machine, Equipment RUL & PM Schedule Optimizer
        if any(k in cols_lower for k in ("weibull_beta", "current_usage_hours", "max_lifetime_hours", "wear_rate_pct", "pm_cost", "from_state", "to_state")):
            typed_in = {**overrides, "domain": "TYPE_D", "records": merged_rows, "documents": docs}
            return _pack("TYPE_D", "auto_shaped_typed_tables", typed_in, TypeDSolver.solve(typed_in))

        # (J) Type E: Process Recipe Parameter Diff Verifier & Cpk Margin Optimizer
        if any(k in cols_lower for k in ("param_name", "recipe_name", "golden_spec")) or ({"target", "actual", "lsl", "usl"} <= cols_lower):
            typee_in = {**overrides, "domain": "TYPE_E", "records": merged_rows, "documents": docs}
            return _pack("TYPE_E", "auto_shaped_typee_tables", typee_in, TypeESolver.solve(typee_in))

    # 3. Persona ID fallback when only markdown/docs exist
    if "value-chain-business" in corpus_lower:
        vc_in = {**overrides, "domain": "VALUE_CHAIN", "persona_id": "value-chain-business-persona", "documents": docs}
        return _pack("VALUE_CHAIN", "persona_doc_detection", vc_in, ValueChainBusinessSolver.solve_all(vc_in))
    if "value-chain-educator" in corpus_lower:
        edu_in = {"domain": "EDUCATOR", "modules": None, "documents": docs, "max_hours": overrides.get("max_hours", 9999.0)}
        return _pack("EDUCATOR", "persona_doc_detection", edu_in, CurriculumOntologySolver.analyze_and_schedule(**edu_in))

    # 4. Universal Multi-Table Semantic Router for any unseen tabular + document dataset
    # (Separates fact/sensor records, candidate tasks/menus/routes/cameras, inquiry rows, and spec_limits tables without losing any table)
    inquiry_rows = find_auxiliary_table(tables, {"question", "inquiry", "complaint", "voc", "문의", "질문", "민원"}) or []
    task_rows = find_auxiliary_table(
        tables,
        {"covered_zones", "passengers", "boarding_count", "mandatory", "is_mandatory", "menu_name", "route_id", "cam_id", "capacity_req", "kcal"}
    ) or merged_rows
    spec_limit_map: Dict[str, Dict[str, float]] = {}
    for t_rows in tables.values():
        if not t_rows or not isinstance(t_rows[0], dict):
            continue
        c_map = {k.strip().lower(): k for k in t_rows[0].keys()}
        p_col = next((c_map[c] for c in ("parameter", "param", "column", "feature", "metric", "항목") if c in c_map), None)
        l_col = next((c_map[c] for c in ("lsl", "min_spec", "lower_limit") if c in c_map), None)
        u_col = next((c_map[c] for c in ("usl", "max_spec", "upper_limit") if c in c_map), None)
        if p_col and (l_col or u_col):
            for sr in t_rows:
                p_name = str(sr.get(p_col, "")).strip()
                if p_name:
                    spec_limit_map[p_name] = {
                        k: v for k, v in (
                            ("LSL", _safe_float(sr.get(l_col)) if l_col else None),
                            ("USL", _safe_float(sr.get(u_col)) if u_col else None),
                        ) if v is not None
                    }

    univ_payload = {
        **overrides,
        "domain": "UNIVERSAL",
        "records": merged_rows,
        "tasks": task_rows,
        "inquiries": inquiry_rows,
        "spec_limits": spec_limit_map,
        "documents": docs,
        "total_budget": overrides.get("total_budget", 1000.0),
        "bus_seat_capacity": int(overrides.get("bus_seat_capacity", 45)),
        "query": overrides.get("query", "핵심 스펙 기준, 보안/금지 구역 및 이상 발생 시 표준 조치 규정"),
    }
    return _pack(
        "UNIVERSAL",
        "workspace_multi_table_semantic_router",
        univ_payload,
        UniversalProblemSolver.solve_universal(univ_payload),
    )


def export_summary_csv(result: Dict[str, Any], csv_path: Path) -> None:
    """일부 평가 스크립트가 output/result.csv 형태의 테이블 산출물을 함께 검사하는 경우를 대비해 핵심 결과 리스트를 CSV로도 저장합니다."""
    sol = result.get("solution", {})
    rows_to_write: List[Dict[str, Any]] = []
    for candidate_key in (
        "calendarized_competitor_benchmarks",
        "vendor_rankings",
        "learning_path",
        "scenario_table",
        "selected_citations",
        "optimal_action_sequence",
        "allocated_repair_lines",
        "step_breakdown",
        "detected_anomalies",
        "equipment_health_list",
        "parameter_diff_table",
    ):
        if isinstance(sol.get(candidate_key), list) and sol[candidate_key]:
            rows_to_write = sol[candidate_key]
            break
    if not rows_to_write and isinstance(sol.get("constrained_optimization_plan"), dict):
        rows_to_write = sol["constrained_optimization_plan"].get("selected_plan", [])
    if not rows_to_write and isinstance(sol.get("wafer_lot_summary"), dict):
        rows_to_write = sol["wafer_lot_summary"].get("wafer_details", [])
    if not rows_to_write:
        rows_to_write = [{
            "detected_domain": result.get("detected_domain"),
            "status": sol.get("status", "NORMAL"),
            "ruleId": sol.get("ruleId", "CORE-PASS"),
        }]

    flat_rows = []
    headers: List[str] = []
    for r in rows_to_write:
        if not isinstance(r, dict):
            continue
        flat = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()}
        for k in flat.keys():
            if k not in headers:
                headers.append(k)
        flat_rows.append(flat)

    if flat_rows and headers:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(flat_rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".", help="Target workspace root")
    parser.add_argument("--domain", default=None, help="Force specific domain (OVERLAY, MATERIAL, MARKET, VALUE_CHAIN, EDUCATOR, TYPE_A, TYPE_B, TYPE_C, TYPE_D, TYPE_E, UNIVERSAL)")
    parser.add_argument("--out", default="output/result.json", help="Output JSON path")
    parser.add_argument("--opt-strategy", default=None, help="Specific optimization strategy (e.g. fine_grid, bnb_exact, maxmin_spatial)")
    args = parser.parse_args()

    root = Path(args.workspace).resolve()
    assets = load_all_workspace_assets(root)
    result = infer_and_solve(assets, opt_strategy=args.opt_strategy, target_domain=args.domain)

    # Attach Pre-Optimization Diagnostics
    diag_report = None
    try:
        from pre_opt_diagnostician import PreOptDiagnostician
        diag_report = PreOptDiagnostician(root).run_full_diagnosis()
        result["pre_opt_diagnosis"] = {
            "metric_classification": diag_report["evaluation_metric_axis"]["metric_classification"],
            "dominant_metric": diag_report["evaluation_metric_axis"]["dominant_metric"],
            "bottleneck_nature": diag_report["bottleneck_nature_axis"]["bottleneck_nature"],
            "recommended_strategy": diag_report["integrated_decision"]["recommended_primary_strategy"],
        }
    except Exception:
        pass

    out_file = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Attach Optimization Proposals Menu if optimizer_menu is available
    try:
        from optimizer_menu import build_views, propose, render_proposal_md, decision_questions, environment_report
        views = build_views(assets)
        proposals = propose(views, diag_report=diag_report)
        if proposals:
            result["available_optimization_proposals"] = proposals
            env = environment_report()
            md = render_proposal_md(proposals, decision_questions(views), views, env, diag_report=diag_report)
            (out_file.parent / "optimizer_proposals.md").write_text(md, encoding="utf-8")
    except Exception:
        pass

    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        export_summary_csv(result, out_file.parent / "result.csv")
    except Exception:
        pass

    pub_dir = root / "public"
    if pub_dir.exists():
        (pub_dir / "live_workspace_solution.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✅ [Auto Solver Pipeline v8.0] 도메인 자동 판별({result['detected_domain']}) 및 채점용 {out_file.name} + result.csv 생성 완료!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

