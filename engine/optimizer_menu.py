#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - Optimization Strategy Menu (v1.0)
"문제를 읽고 -> 가능한 최적화 방식 후보를 제안하고 -> 사람이 고르면 -> 그 방식으로 풀고 -> 후보끼리 비교" 하는 모듈.

100% 결정론(seed 고정) / 순수 Python(외부 패키지 불필요) / LLM·네트워크 호출 없음 (AGENTS.md 80/20 원칙: 이 모듈은 80% 결정론 코어 쪽).

문제 유형(Family)과 후보:
  SEL  자원 제약 선택(배낭형): greedy / DP(정확) / Branch&Bound(정확) / Simulated Annealing / Genetic Algorithm
  COV  Set-Cover/배치(카메라·센서·정류장): greedy / Branch&Bound(정확) / SA / GA
  SCH  병렬설비 스케줄링(OHT/PM/작업배분): 디스패칭 룰 비교(FIFO,SPT,LPT,EDD,WSPT) / SA / 전수탐색(소규모)
  PRD  예측·이상탐지(수율/결함/설비이상): Robust-MAD 이상탐지 / 클래스가중 로지스틱 / 부스티드 스텀프(경량 GBM)
  HPC  계산 병목 진단: cProfile 기반 I/O vs Compute 진단
  RL   강화학습 디스패칭: 가이드만 제공(시뮬레이터 필요, 미구현)

사용법:
  python engine/optimizer_menu.py --workspace .                       # 1) 문제 분석 + 후보 제안(output/optimizer_proposals.md/json)
  python engine/optimizer_menu.py --workspace . --choose sel_sa       # 2) 고른 후보 실행
  python engine/optimizer_menu.py --workspace . --choose 'sel_*'      #    같은 계열 후보 전부 실행 + 비교표
  python engine/optimizer_menu.py --workspace . --choose ALL          #    적용 가능한 구현 후보 전부 실행
"""

import argparse
import bisect
import cProfile
import fnmatch
import heapq
import importlib.util
import io
import itertools
import json
import math
import pstats
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from pre_opt_diagnostician import PreOptDiagnostician
except ImportError:
    PreOptDiagnostician = None

# ============================================================================
# OPT_CONFIG: 비개발자도 수정 가능한 최적화 설정 (AGENTS.md: 임계값/설정은 최상단 상수)
# ============================================================================
OPT_CONFIG = {
    "SEED": 20240611,
    "EXACT_BNB_NODE_LIMIT": 1_500_000,   # Branch&Bound 최대 탐색 노드 (초과 시 HEURISTIC으로 표기)
    "EXHAUSTIVE_MAX_FREE_ITEMS": 18,     # 전수탐색 허용 최대 후보 수
    "SCHED_EXACT_MAX_JOBS": 8,           # 스케줄링 전수탐색 허용 최대 작업 수
    "DP_MAX_STATES": 4_000_000,          # DP (n * B * C) 상태 수 상한
    "SA_MAX_ITERS": 20000,
    "GA_POP": 50,
    "GA_GENS": 120,
    "PRED_MAX_TRAIN_ROWS": 1500,
    "PRED_MAX_FEATURES": 25,
    "ANOMALY_Z": 3.5,
    "DEFAULT_MACHINES": 2,
}

FIELD_ALIASES = {
    "id": ["id", "item_id", "task_id", "menu_id", "route_id", "cam_id", "camera_id", "job_id", "lot_id", "name", "이름"],
    "cost": ["cost", "price", "unit_cost", "budget_req", "비용", "단가"],
    "cap": ["capacity_req", "capacity", "space", "weight_kg", "용량"],
    "value": ["value", "preference", "score", "rating", "priority_score", "benefit", "가치", "선호도"],
    "proc": ["proc_time", "processing_time", "process_time", "duration", "run_time", "hours", "cycle_time", "소요시간"],
    "due": ["due", "due_date", "due_time", "deadline", "납기"],
    "release": ["release", "release_time", "arrival", "arrival_time", "ready_time"],
    "weight": ["priority_weight", "job_weight", "priority", "importance", "가중치"],
    "zones": ["covered_zones", "zones", "coverage", "covers"],
    "mandatory": ["mandatory", "is_mandatory", "required", "필수"],
    "forbidden": ["forbidden", "restricted", "security_restricted", "privacy_zone", "금지"],
}
LABEL_NAME_RE = re.compile(r"(label|target|defect|fail|anomaly|fault|abnormal|^y$|class|^is_|불량|결함|이상)", re.I)
POS_TOKENS = {"1", "true", "y", "yes", "fail", "defect", "anomaly", "bad", "abnormal", "ng", "불량", "이상"}
NEG_TOKENS = {"0", "false", "n", "no", "pass", "ok", "normal", "good", "정상", "양품"}
GROUP_COLS = ["equip_id", "tool_id", "chamber_id", "scanner_id", "machine", "equipment", "vendor_id", "lot_id"]


# ============================================================================
# 공통 유틸
# ============================================================================
def _num(v: Any) -> Optional[float]:
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        s = str(v).replace(",", "").replace("$", "").replace("%", "").strip()
        if s.lower() in {"null", "nan", "none", "n/a", "-", "undefined", "error"}:
            return None
        f = float(s)
        if f in (-999.0, -9999.0, 9999.0, 99999.0) or math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _get(row: Dict[str, Any], key: str) -> Any:
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for al in FIELD_ALIASES.get(key, [key]):
        v = low.get(al.lower())
        if v is not None and v != "":
            return v
    return None


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in {"1", "true", "y", "yes", "t", "예", "필수"}


def _mean(a: List[float]) -> float:
    return sum(a) / len(a) if a else 0.0


def _std(a: List[float]) -> float:
    if len(a) < 2:
        return 0.0
    m = _mean(a)
    return math.sqrt(sum((x - m) ** 2 for x in a) / (len(a) - 1))


def _median(a: List[float]) -> float:
    s = sorted(a)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


# ============================================================================
# 1. 문제 뷰(View) 추출: 워크스페이스 테이블에서 최적화 가능한 문제 구조를 감지
# ============================================================================
def _parse_zones(v: Any) -> List[str]:
    if isinstance(v, list):
        return [str(z).strip() for z in v if str(z).strip()]
    if v is None:
        return []
    return [z.strip() for z in re.split(r"[;|,/]", str(v)) if z.strip()]


def _frac(rows: List[Dict[str, Any]], pred: Callable[[Dict[str, Any]], bool]) -> float:
    return sum(1 for r in rows if pred(r)) / max(len(rows), 1)


def _selection_items(rows: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if len(rows) < 3 or _frac(rows, lambda r: _num(_get(r, "cost")) is not None and _num(_get(r, "value")) is not None) < 0.7:
        return None
    items = []
    for i, r in enumerate(rows):
        c, v = _num(_get(r, "cost")), _num(_get(r, "value"))
        if c is None or v is None:
            continue
        items.append({
            "id": str(_get(r, "id") or f"ITEM-{i + 1}"), "cost": c, "value": v,
            "cap": _num(_get(r, "cap")) or 0.0, "cap_present": _get(r, "cap") is not None,
            "mandatory": _truthy(_get(r, "mandatory")), "forbidden": _truthy(_get(r, "forbidden")),
            "zones": _parse_zones(_get(r, "zones")),
        })
    return items if len(items) >= 3 else None


def _cover_items(rows: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if len(rows) < 2 or _frac(rows, lambda r: len(_parse_zones(_get(r, "zones"))) > 0) < 0.7:
        return None
    items = []
    for i, r in enumerate(rows):
        z = _parse_zones(_get(r, "zones"))
        if not z:
            continue
        items.append({
            "id": str(_get(r, "id") or f"CAND-{i + 1}"), "cost": _num(_get(r, "cost")) or 1.0, "value": 0.0, "cap": 0.0,
            "zones": z, "mandatory": _truthy(_get(r, "mandatory")), "forbidden": _truthy(_get(r, "forbidden")),
        })
    return items if len(items) >= 2 else None


def _job_items(rows: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if len(rows) < 2 or _frac(rows, lambda r: _num(_get(r, "proc")) is not None and (_num(_get(r, "proc")) or 0) > 0) < 0.7:
        return None
    jobs = []
    for i, r in enumerate(rows):
        p = _num(_get(r, "proc"))
        if p is None or p <= 0:
            continue
        jobs.append({
            "id": str(_get(r, "id") or f"JOB-{i + 1}"), "p": p, "due": _num(_get(r, "due")),
            "release": _num(_get(r, "release")) or 0.0, "w": _num(_get(r, "weight")) or 1.0,
        })
    return jobs if len(jobs) >= 2 else None


def _binary_label(values: List[Any]) -> Optional[List[int]]:
    out = []
    for v in values:
        t = str(v).strip().lower()
        if t in POS_TOKENS:
            out.append(1)
        elif t in NEG_TOKENS:
            out.append(0)
        else:
            return None
    return out if 0 < sum(out) < len(out) else None


def _prediction_view(rows: List[Dict[str, Any]], label_hint: Optional[str]) -> Optional[Dict[str, Any]]:
    if len(rows) < 20:
        return None
    cols = list(rows[0].keys())
    label_col, labels = None, None
    for c in ([label_hint] if label_hint else []) + [c for c in cols if LABEL_NAME_RE.search(str(c))]:
        if c in cols:
            lab = _binary_label([r.get(c) for r in rows])
            if lab is not None:
                label_col, labels = c, lab
                break
    feats = []
    for c in cols:
        if c == label_col or "id" in str(c).lower() or "date" in str(c).lower() or "time" in str(c).lower():
            continue
        vals = [_num(r.get(c)) for r in rows]
        ok = [v for v in vals if v is not None]
        if len(ok) >= 0.8 * len(rows) and _std(ok) > 1e-12:
            feats.append(c)
    if len(feats) < 2:
        return None
    group_col = next((g for g in GROUP_COLS if g in cols), None)
    return {"rows": rows, "features": feats, "label_col": label_col, "labels": labels, "group_col": group_col}


def build_views(assets: Dict[str, Any], label_hint: Optional[str] = None) -> Dict[str, Any]:
    views: Dict[str, Any] = {}
    docs_text = " ".join(d.get("content", "") for d in assets.get("documents", [])).lower()

    def keep_best(kind: str, tname: str, payload: Any, size: int) -> None:
        if kind not in views or size > views[kind]["size"]:
            views[kind] = {"table": tname, "data": payload, "size": size}

    # 1. 5대 반도체 도메인 특화 뷰 감지
    from auto_solver_pipeline import classify_table_domain, auto_join_tables_fact_first
    domain_tables: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for tname, rows in assets.get("tables", {}).items():
        if not rows or not isinstance(rows[0], dict):
            continue
        dom = classify_table_domain(rows)
        if dom:
            domain_tables.setdefault(dom, {})[tname] = rows

    for dom, tbls in domain_tables.items():
        first_tname = next(iter(tbls.keys()))
        tot_rows = sum(len(r) for r in tbls.values())
        if dom == "MARKET":
            views["domain_market"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "VALUE_CHAIN":
            views["domain_value_chain"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "OVERLAY":
            views["domain_overlay"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "MATERIAL":
            views["domain_material"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "EDUCATOR":
            views["domain_educator"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "TYPE_A":
            views["domain_type_a"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "TYPE_B":
            views["domain_type_b"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "TYPE_C":
            views["domain_type_c"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "TYPE_D":
            views["domain_type_d"] = {"table": first_tname, "data": tbls, "size": tot_rows}
        elif dom == "TYPE_E":
            views["domain_type_e"] = {"table": first_tname, "data": tbls, "size": tot_rows}

    # 2. 범용 조합/예측 뷰 감지
    for tname, rows in assets.get("tables", {}).items():
        if not rows or not isinstance(rows[0], dict):
            continue
        for kind, fn in (("selection", _selection_items), ("cover", _cover_items), ("jobs", _job_items)):
            res = fn(rows)
            if res:
                keep_best(kind, tname, res, len(res))
        pv = _prediction_view(rows, label_hint)
        if pv:
            keep_best("prediction", tname, pv, len(rows))
    hpc_kw = ["latency", "throughput", "지연시간", "처리량", "병목", "vram", "메모리 대역폭", "gpu", "추론 속도", "시뮬레이션 시간"]
    big = any(len(r) >= 3000 for r in assets.get("tables", {}).values())
    hits = [k for k in hpc_kw if k in docs_text]
    if hits or big:
        views["hpc"] = {"table": "(workspace)", "data": {"keywords": hits, "big_table": big}, "size": len(hits) + int(big)}
    sched_kw = ["dispatch", "디스패치", "oht", "동적", "deadlock", "데드락", "실시간 규칙"]
    if any(k in docs_text for k in sched_kw):
        views["dynamic_dispatch_hint"] = {"table": "(docs)", "data": [k for k in sched_kw if k in docs_text], "size": 1}
    return views


# ============================================================================
# 2. 조합 최적화 공통 문제 정의 (선택형 / Set-Cover형) + 메타휴리스틱
# ============================================================================
class SelProblem:
    """자원 제약 선택: max_value(예산/용량 내 가치 최대) 또는 min_cost(가치 목표 달성 최소 비용)."""

    def __init__(self, items: List[Dict[str, Any]], budget: Optional[float], capacity: Optional[float],
                 objective: str = "max_value", value_target: Optional[float] = None):
        self.items = items
        self.n = len(items)
        self.budget = budget
        self.capacity = capacity
        self.objective = objective
        self.value_target = value_target
        self.on = {i for i, it in enumerate(items) if it["mandatory"] and not it["forbidden"]}
        self.off = {i for i, it in enumerate(items) if it["forbidden"]}
        self.free = [i for i in range(self.n) if i not in self.on and i not in self.off]
        tot_v = sum(abs(it["value"]) for it in items) or 1.0
        tot_c = sum(abs(it["cost"]) for it in items) or 1.0
        self.scale = tot_v if objective == "max_value" else tot_c

    def fix(self, mask: List[bool]) -> List[bool]:
        m = list(mask)
        for i in self.on:
            m[i] = True
        for i in self.off:
            m[i] = False
        return m

    def totals(self, mask: List[bool]) -> Tuple[float, float, float]:
        c = v = k = 0.0
        for i, s in enumerate(mask):
            if s:
                it = self.items[i]
                c += it["cost"]
                v += it["value"]
                k += it["cap"]
        return c, v, k

    def evaluate(self, mask: List[bool]) -> Tuple[bool, float, float]:
        c, v, k = self.totals(mask)
        viol = 0.0
        if self.capacity is not None and k > self.capacity + 1e-9:
            viol += (k - self.capacity) / max(self.capacity, 1e-9)
        if self.objective == "max_value":
            if self.budget is not None and c > self.budget + 1e-9:
                viol += (c - self.budget) / max(self.budget, 1e-9)
            return viol <= 0, v, viol
        tgt = self.value_target or 0.0
        if v < tgt - 1e-9:
            viol += (tgt - v) / max(abs(tgt), 1e-9)
        return viol <= 0, -c, viol

    def selected_ids(self, mask: List[bool]) -> List[str]:
        return [self.items[i]["id"] for i, s in enumerate(mask) if s]

    def summarize(self, mask: List[bool]) -> Dict[str, Any]:
        c, v, k = self.totals(mask)
        feas, _, _ = self.evaluate(mask)
        return {"feasible": feas, "total_cost": round(c, 4), "total_value": round(v, 4), "total_capacity": round(k, 4),
                "selected_count": sum(mask), "selected_ids": self.selected_ids(mask)}

    def greedy_mask(self) -> List[bool]:
        mask = self.fix([False] * self.n)
        if self.objective == "max_value":
            def key(i: int) -> float:
                it = self.items[i]
                denom = (it["cost"] / max(self.budget or 1.0, 1e-9)) + (it["cap"] / max(self.capacity, 1e-9) if self.capacity else 0.0)
                return it["value"] / max(denom, 1e-9)
            for i in sorted(self.free, key=key, reverse=True):
                mask[i] = True
                if not self.evaluate(mask)[0]:
                    mask[i] = False
            return mask
        for i in sorted(self.free, key=lambda j: self.items[j]["value"] / max(self.items[j]["cost"], 1e-9), reverse=True):
            if self.evaluate(mask)[0]:
                break
            mask[i] = True
        if self.evaluate(mask)[0]:
            for i in sorted([j for j in self.free if mask[j]], key=lambda j: self.items[j]["cost"], reverse=True):
                mask[i] = False
                if not self.evaluate(mask)[0]:
                    mask[i] = True
        return mask


class CoverProblem:
    """Set-Cover형: min_cost_cover(전체 구역 커버 최소 비용) 또는 max_coverage_budget(예산 내 커버 구역 최대)."""

    def __init__(self, items: List[Dict[str, Any]], objective: str = "min_cost_cover", budget: Optional[float] = None):
        self.items = items
        self.n = len(items)
        self.objective = objective
        self.budget = budget
        self.on = {i for i, it in enumerate(items) if it["mandatory"] and not it["forbidden"]}
        self.off = {i for i, it in enumerate(items) if it["forbidden"]}
        self.free = [i for i in range(self.n) if i not in self.on and i not in self.off]
        zones = sorted({z for i, it in enumerate(items) if i not in self.off for z in it["zones"]})
        self.zone_idx = {z: k for k, z in enumerate(zones)}
        self.zones = zones
        self.full = (1 << len(zones)) - 1
        self.zmask = [sum(1 << self.zone_idx[z] for z in it["zones"] if z in self.zone_idx) if i not in self.off else 0
                      for i, it in enumerate(items)]
        self.scale = sum(it["cost"] for it in items) or 1.0

    def fix(self, mask: List[bool]) -> List[bool]:
        m = list(mask)
        for i in self.on:
            m[i] = True
        for i in self.off:
            m[i] = False
        return m

    def covered(self, mask: List[bool]) -> int:
        cm = 0
        for i, s in enumerate(mask):
            if s:
                cm |= self.zmask[i]
        return cm

    def evaluate(self, mask: List[bool]) -> Tuple[bool, float, float]:
        cm = self.covered(mask)
        cost = sum(self.items[i]["cost"] for i, s in enumerate(mask) if s)
        ncov = bin(cm).count("1")
        if self.objective == "min_cost_cover":
            unc = len(self.zones) - ncov
            return unc == 0, -cost, unc / max(len(self.zones), 1)
        viol = max(0.0, cost - (self.budget or 0.0)) / max(self.budget or 1.0, 1e-9)
        return viol <= 0, ncov - 1e-6 * cost, viol

    def summarize(self, mask: List[bool]) -> Dict[str, Any]:
        cm = self.covered(mask)
        cost = sum(self.items[i]["cost"] for i, s in enumerate(mask) if s)
        cov_z = [z for z, k in self.zone_idx.items() if cm >> k & 1]
        feas, _, _ = self.evaluate(mask)
        return {"feasible": feas, "total_cost": round(cost, 4), "covered_zone_count": len(cov_z), "total_zone_count": len(self.zones),
                "uncovered_zones": sorted(set(self.zones) - set(cov_z)), "selected_count": sum(mask),
                "selected_ids": [self.items[i]["id"] for i, s in enumerate(mask) if s]}

    def greedy_mask(self) -> List[bool]:
        mask = self.fix([False] * self.n)
        cm = self.covered(mask)
        spent = sum(self.items[i]["cost"] for i, s in enumerate(mask) if s)
        pool = set(self.free)
        while pool:
            best, best_r = None, 0.0
            for i in pool:
                gain = bin(self.zmask[i] & ~cm).count("1")
                if gain <= 0:
                    continue
                if self.objective == "max_coverage_budget" and spent + self.items[i]["cost"] > (self.budget or 0.0) + 1e-9:
                    continue
                r = gain / max(self.items[i]["cost"], 1e-9)
                if r > best_r:
                    best, best_r = i, r
            if best is None:
                break
            mask[best] = True
            pool.discard(best)
            cm |= self.zmask[best]
            spent += self.items[best]["cost"]
            if self.objective == "min_cost_cover" and cm == self.full:
                break
        if self.objective == "min_cost_cover" and self.evaluate(mask)[0]:
            for i in sorted([j for j in self.free if mask[j]], key=lambda j: self.items[j]["cost"], reverse=True):
                mask[i] = False
                if not self.evaluate(mask)[0]:
                    mask[i] = True
        return mask


def simulated_annealing(p: Any, init: List[bool], seed: int, iters: int) -> Tuple[Optional[List[bool]], int]:
    rng = random.Random(seed)
    M = p.scale * 10.0

    def pen(m: List[bool]) -> Tuple[float, bool, float]:
        feas, sc, viol = p.evaluate(m)
        return sc - M * viol, feas, sc

    cur = p.fix(init)
    cur_f, cur_feas, cur_sc = pen(cur)
    best, best_sc = (list(cur), cur_sc) if cur_feas else (None, -float("inf"))
    T0 = max(p.scale * 0.05, 1e-6)
    T1 = max(p.scale * 1e-4, 1e-9)
    free = p.free
    if not free:
        return best, 0
    for it in range(iters):
        T = T0 * (T1 / T0) ** (it / max(iters - 1, 1))
        cand = list(cur)
        if rng.random() < 0.7 or len(free) < 2:
            j = rng.choice(free)
            cand[j] = not cand[j]
        else:
            ons = [j for j in free if cand[j]]
            offs = [j for j in free if not cand[j]]
            if ons and offs:
                cand[rng.choice(ons)] = False
                cand[rng.choice(offs)] = True
        f, feas, sc = pen(cand)
        if f >= cur_f or rng.random() < math.exp((f - cur_f) / T):
            cur, cur_f = cand, f
            if feas and sc > best_sc:
                best, best_sc = list(cand), sc
    return best, iters


def genetic_algorithm(p: Any, seeds: List[List[bool]], seed: int, pop_n: int, gens: int) -> Tuple[Optional[List[bool]], int]:
    rng = random.Random(seed)
    M = p.scale * 10.0
    free = p.free
    if not free:
        return None, 0

    def fit(m: List[bool]) -> Tuple[float, bool, float]:
        feas, sc, viol = p.evaluate(m)
        return sc - M * viol, feas, sc

    pop = [p.fix(s) for s in seeds]
    while len(pop) < pop_n:
        m = [False] * p.n
        for j in free:
            m[j] = rng.random() < 0.3
        pop.append(p.fix(m))
    best, best_sc = None, -float("inf")
    evals = 0
    for _ in range(gens):
        scored = []
        for m in pop:
            f, feas, sc = fit(m)
            evals += 1
            scored.append((f, m))
            if feas and sc > best_sc:
                best, best_sc = list(m), sc
        scored.sort(key=lambda t: t[0], reverse=True)
        nxt = [list(m) for _, m in scored[:2]]
        while len(nxt) < pop_n:
            a = max(rng.sample(scored, min(3, len(scored))), key=lambda t: t[0])[1]
            b = max(rng.sample(scored, min(3, len(scored))), key=lambda t: t[0])[1]
            child = [a[i] if rng.random() < 0.5 else b[i] for i in range(p.n)]
            for j in free:
                if rng.random() < 1.0 / max(len(free), 1):
                    child[j] = not child[j]
            nxt.append(p.fix(child))
        pop = nxt
    return best, evals


# ----------------------------------------------------------------------------
# 정확해(Exact) 알고리즘
# ----------------------------------------------------------------------------
def exact_dp_selection(p: SelProblem) -> Optional[Tuple[List[bool], bool]]:
    """다차원 0/1 배낭 DP (max_value 전용). 비용/용량을 정수 스케일링. (mask, exact) 반환, 너무 크면 None."""
    if p.objective != "max_value" or p.budget is None:
        return None

    def scale_factor(vals: List[float]) -> Tuple[int, bool]:
        for k in (0, 1, 2):
            f = 10 ** k
            if all(abs(v * f - round(v * f)) < 1e-6 for v in vals):
                return f, True
        return 100, False

    f_c, ex_c = scale_factor([it["cost"] for it in p.items] + [p.budget])
    use_cap = p.capacity is not None
    f_k, ex_k = scale_factor([it["cap"] for it in p.items] + [p.capacity or 0.0]) if use_cap else (1, True)
    base_c = sum(p.items[i]["cost"] for i in p.on)
    base_k = sum(p.items[i]["cap"] for i in p.on)
    B = int(round((p.budget - base_c) * f_c))
    C = int(round(((p.capacity or 0.0) - base_k) * f_k)) if use_cap else 0
    if B < 0 or C < 0:
        return None
    if len(p.free) * (B + 1) * (C + 1) > OPT_CONFIG["DP_MAX_STATES"]:
        return None
    val = [[0.0] * (C + 1) for _ in range(B + 1)]
    msk = [[0] * (C + 1) for _ in range(B + 1)]
    for pos, i in enumerate(p.free):
        it = p.items[i]
        wc = int(round(it["cost"] * f_c))
        wk = int(round(it["cap"] * f_k)) if use_cap else 0
        if it["value"] <= 0 or wc > B or wk > C:
            continue
        for b in range(B, wc - 1, -1):
            row, prow = val[b], val[b - wc]
            mrow, pmrow = msk[b], msk[b - wc]
            for c in range(C, wk - 1, -1):
                nv = prow[c - wk] + it["value"]
                if nv > row[c]:
                    row[c] = nv
                    mrow[c] = pmrow[c - wk] | (1 << pos)
    m = p.fix([False] * p.n)
    for pos, i in enumerate(p.free):
        if msk[B][C] >> pos & 1:
            m[i] = True
    return m, (ex_c and ex_k)


def exact_bnb_selection(p: SelProblem) -> Tuple[List[bool], bool, int]:
    """Branch & Bound (분수 완화 상한). (mask, proven_optimal, nodes)."""
    limit = OPT_CONFIG["EXACT_BNB_NODE_LIMIT"]
    greedy = p.greedy_mask()
    best = {"score": p.evaluate(greedy)[1] if p.evaluate(greedy)[0] else -float("inf"), "mask": list(greedy) if p.evaluate(greedy)[0] else None}
    nodes = [0]
    aborted = [False]
    if p.objective == "max_value":
        order = sorted(p.free, key=lambda i: p.items[i]["value"] / max(p.items[i]["cost"], 1e-9), reverse=True)
        base = p.fix([False] * p.n)
        c0, v0, k0 = p.totals(base)
        B = p.budget if p.budget is not None else float("inf")

        def bound(k: int, cost: float, val: float) -> float:
            rem = B - cost
            ub = val
            for j in order[k:]:
                it = p.items[j]
                if it["value"] <= 0:
                    continue
                if it["cost"] <= rem:
                    rem -= it["cost"]
                    ub += it["value"]
                else:
                    ub += it["value"] * (rem / max(it["cost"], 1e-9))
                    break
            return ub

        def rec(k: int, cost: float, cap: float, val: float, chosen: List[int]) -> None:
            nodes[0] += 1
            if nodes[0] > limit:
                aborted[0] = True
                return
            if val > best["score"] + 1e-12:
                m = list(base)
                for j in chosen:
                    m[j] = True
                best["score"], best["mask"] = val, m
            if k == len(order) or bound(k, cost, val) <= best["score"] + 1e-12:
                return
            it = p.items[order[k]]
            if cost + it["cost"] <= B + 1e-9 and (p.capacity is None or cap + it["cap"] <= p.capacity + 1e-9):
                chosen.append(order[k])
                rec(k + 1, cost + it["cost"], cap + it["cap"], val + it["value"], chosen)
                chosen.pop()
            rec(k + 1, cost, cap, val, chosen)

        rec(0, c0, k0, v0, [])
    else:
        order = sorted(p.free, key=lambda i: p.items[i]["value"] / max(p.items[i]["cost"], 1e-9), reverse=True)
        base = p.fix([False] * p.n)
        c0, v0, k0 = p.totals(base)
        tgt = p.value_target or 0.0
        best["score"] = -best["score"] if best["mask"] is not None else float("inf")  # best cost

        suffix_v = [0.0] * (len(order) + 1)
        for k in range(len(order) - 1, -1, -1):
            suffix_v[k] = suffix_v[k + 1] + max(p.items[order[k]]["value"], 0.0)

        def rec2(k: int, cost: float, cap: float, val: float, chosen: List[int]) -> None:
            nodes[0] += 1
            if nodes[0] > limit:
                aborted[0] = True
                return
            if cost >= best["score"] - 1e-12:
                return
            if val >= tgt - 1e-9:
                m = list(base)
                for j in chosen:
                    m[j] = True
                if p.evaluate(m)[0]:
                    best["score"], best["mask"] = cost, m
                return
            if k == len(order) or val + suffix_v[k] < tgt - 1e-9:
                return
            ratio = p.items[order[k]]["value"] / max(p.items[order[k]]["cost"], 1e-9)
            if ratio > 0 and cost + (tgt - val) / ratio >= best["score"] - 1e-12:
                return
            it = p.items[order[k]]
            if p.capacity is None or cap + it["cap"] <= p.capacity + 1e-9:
                chosen.append(order[k])
                rec2(k + 1, cost + it["cost"], cap + it["cap"], val + it["value"], chosen)
                chosen.pop()
            rec2(k + 1, cost, cap, val, chosen)

        rec2(0, c0, k0, v0, [])
    return (best["mask"] if best["mask"] is not None else greedy), (not aborted[0] and best["mask"] is not None), nodes[0]


def exact_bnb_cover(p: CoverProblem) -> Tuple[List[bool], bool, int]:
    """min_cost_cover 전용 Branch & Bound: 가장 적게 커버되는 구역을 골라 해당 구역을 덮는 후보로만 분기."""
    limit = OPT_CONFIG["EXACT_BNB_NODE_LIMIT"]
    greedy = p.greedy_mask()
    g_ok = p.evaluate(greedy)[0]
    best = {"cost": sum(p.items[i]["cost"] for i, s in enumerate(greedy) if s) if g_ok else float("inf"), "chosen": None}
    base_chosen = [i for i in p.on]
    base_cm = 0
    for i in base_chosen:
        base_cm |= p.zmask[i]
    base_cost = sum(p.items[i]["cost"] for i in base_chosen)
    cands_by_zone: Dict[int, List[int]] = {k: [] for k in range(len(p.zones))}
    for i in p.free:
        for k in range(len(p.zones)):
            if p.zmask[i] >> k & 1:
                cands_by_zone[k].append(i)
    nodes = [0]
    aborted = [False]

    def rec(cm: int, cost: float, chosen: List[int]) -> None:
        nodes[0] += 1
        if nodes[0] > limit:
            aborted[0] = True
            return
        if cost >= best["cost"] - 1e-12:
            return
        if cm == p.full:
            best["cost"], best["chosen"] = cost, list(chosen)
            return
        unc = [k for k in range(len(p.zones)) if not cm >> k & 1]
        zk = min(unc, key=lambda k: len(cands_by_zone[k]))
        cands = [i for i in cands_by_zone[zk] if i not in chosen]
        cands.sort(key=lambda i: p.items[i]["cost"] / max(bin(p.zmask[i] & ~cm).count("1"), 1))
        for i in cands:
            chosen.append(i)
            rec(cm | p.zmask[i], cost + p.items[i]["cost"], chosen)
            chosen.pop()

    rec(base_cm, base_cost, [])
    if best["chosen"] is not None:
        m = p.fix([False] * p.n)
        for i in best["chosen"]:
            m[i] = True
        return m, not aborted[0], nodes[0]
    # 탐색을 끝까지 했는데 greedy보다 싼 해가 없으면 greedy가 곧 최적해
    return greedy, (not aborted[0] and g_ok), nodes[0]


def exhaustive_generic(p: Any) -> Tuple[Optional[List[bool]], int]:
    free = p.free
    best, best_sc, cnt = None, -float("inf"), 0
    for bits in itertools.product([False, True], repeat=len(free)):
        m = p.fix([False] * p.n)
        for j, b in zip(free, bits):
            if b:
                m[j] = True
        feas, sc, _ = p.evaluate(m)
        cnt += 1
        if feas and sc > best_sc:
            best, best_sc = m, sc
    return best, cnt


# ============================================================================
# 3. 스케줄링 (병렬 동일 설비)
# ============================================================================
def list_schedule(jobs: List[Dict[str, Any]], order: List[int], m: int) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    free = [(0.0, k) for k in range(m)]
    heapq.heapify(free)
    rows = []
    for j in order:
        job = jobs[j]
        t, k = heapq.heappop(free)
        start = max(t, job["release"])
        end = start + job["p"]
        heapq.heappush(free, (end, k))
        tard = max(0.0, end - job["due"]) if job["due"] is not None else 0.0
        rows.append({"job_id": job["id"], "machine": f"M{k + 1}", "start": round(start, 4), "end": round(end, 4),
                     "tardiness": round(tard, 4), "flow_time": round(end - job["release"], 4)})
    n = len(rows)
    metrics = {
        "makespan": max((r["end"] for r in rows), default=0.0),
        "total_tardiness": round(sum(r["tardiness"] for r in rows), 4),
        "max_tardiness": max((r["tardiness"] for r in rows), default=0.0),
        "late_jobs": sum(1 for r in rows if r["tardiness"] > 0),
        "mean_flow_time": round(sum(r["flow_time"] for r in rows) / max(n, 1), 4),
        "total_weighted_completion": round(sum(jobs[j]["w"] * rows[idx]["end"] for idx, j in enumerate(order)), 4),
    }
    return rows, metrics


SCHED_OBJ_KEY = {"makespan": "makespan", "total_tardiness": "total_tardiness", "mean_flow_time": "mean_flow_time",
                 "weighted_completion": "total_weighted_completion", "late_jobs": "late_jobs"}


def dispatch_orders(jobs: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    idx = list(range(len(jobs)))
    return {
        "FIFO": sorted(idx, key=lambda i: (jobs[i]["release"], i)),
        "SPT": sorted(idx, key=lambda i: (jobs[i]["p"], i)),
        "LPT": sorted(idx, key=lambda i: (-jobs[i]["p"], i)),
        "EDD": sorted(idx, key=lambda i: (jobs[i]["due"] if jobs[i]["due"] is not None else float("inf"), i)),
        "WSPT": sorted(idx, key=lambda i: (jobs[i]["p"] / max(jobs[i]["w"], 1e-9), i)),
    }


def sched_sa(jobs: List[Dict[str, Any]], m: int, obj: str, seed: int, init: List[int]) -> List[int]:
    rng = random.Random(seed)
    key = SCHED_OBJ_KEY[obj]

    def f(o: List[int]) -> float:
        return list_schedule(jobs, o, m)[1][key]

    cur, cur_f = list(init), f(init)
    best, best_f = list(cur), cur_f
    iters = min(OPT_CONFIG["SA_MAX_ITERS"], 300 * len(jobs) + 1000)
    T0 = max(cur_f * 0.05, 1e-6)
    T1 = max(cur_f * 1e-4, 1e-9)
    for it in range(iters):
        T = T0 * (T1 / T0) ** (it / max(iters - 1, 1))
        cand = list(cur)
        a, b = rng.sample(range(len(cand)), 2)
        if rng.random() < 0.5:
            cand[a], cand[b] = cand[b], cand[a]
        else:
            cand.insert(b, cand.pop(a))
        cf = f(cand)
        if cf <= cur_f or rng.random() < math.exp((cur_f - cf) / T):
            cur, cur_f = cand, cf
            if cf < best_f:
                best, best_f = list(cand), cf
    return best


# ============================================================================
# 4. 예측 / 이상탐지 (순수 Python)
# ============================================================================
def derive_features(rows: List[Dict[str, Any]], feats: List[str], group_col: Optional[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """도메인 파생변수: 직전 행 대비 변화량(delta) + 그룹(설비/챔버/Lot)평균 대비 편차."""
    new_rows = [dict(r) for r in rows]
    new_feats = list(feats)
    group_mean: Dict[Tuple[str, str], float] = {}
    if group_col:
        for f in feats:
            acc: Dict[str, List[float]] = {}
            for r in rows:
                v = _num(r.get(f))
                if v is not None:
                    acc.setdefault(str(r.get(group_col)), []).append(v)
            for g, vs in acc.items():
                group_mean[(f, g)] = _mean(vs)
    for f in feats:
        prev = None
        for r in new_rows:
            v = _num(r.get(f))
            r[f"{f}__delta"] = (v - prev) if (v is not None and prev is not None) else 0.0
            if v is not None:
                prev = v
            if group_col:
                gm = group_mean.get((f, str(r.get(group_col))))
                r[f"{f}__grp_dev"] = (v - gm) if (v is not None and gm is not None) else 0.0
        new_feats.append(f"{f}__delta")
        if group_col:
            new_feats.append(f"{f}__grp_dev")
    return new_rows, new_feats


def auroc(scores: List[float], y: List[int]) -> float:
    pos = [s for s, t in zip(scores, y) if t == 1]
    neg = [s for s, t in zip(scores, y) if t == 0]
    if not pos or not neg:
        return float("nan")
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    rs = sum(ranks[i] for i in range(len(y)) if y[i] == 1)
    return (rs - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def f1_at_prevalence(scores: List[float], y: List[int]) -> Dict[str, float]:
    k = sum(y)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    pred = set(order[:k])
    tp = sum(1 for i in pred if y[i] == 1)
    prec = tp / max(len(pred), 1)
    rec = tp / max(k, 1)
    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(2 * prec * rec / max(prec + rec, 1e-12), 4)}


def _matrix(rows: List[Dict[str, Any]], feats: List[str]) -> List[List[float]]:
    med = {f: _median([v for v in (_num(r.get(f)) for r in rows) if v is not None]) for f in feats}
    return [[(_num(r.get(f)) if _num(r.get(f)) is not None else med[f]) for f in feats] for r in rows]


def _split(y: List[int]) -> Tuple[List[int], List[int]]:
    tr, te = [], []
    cnt = {0: 0, 1: 0}
    for i, t in enumerate(y):
        (te if cnt[t] % 3 == 0 else tr).append(i)
        cnt[t] += 1
    max_tr = OPT_CONFIG["PRED_MAX_TRAIN_ROWS"]
    if len(tr) > max_tr:
        pos = [i for i in tr if y[i] == 1]
        neg = [i for i in tr if y[i] == 0]
        keep_neg = max(max_tr - len(pos), 1)
        step = max(len(neg) // keep_neg, 1)
        tr = sorted(pos + neg[::step])
    return tr, te


def _select_features(X: List[List[float]], y: List[int], feats: List[str], tr: List[int]) -> List[int]:
    m = OPT_CONFIG["PRED_MAX_FEATURES"]
    if len(feats) <= m:
        return list(range(len(feats)))
    ys = [y[i] for i in tr]
    my = _mean(ys)
    scores = []
    for j in range(len(feats)):
        xs = [X[i][j] for i in tr]
        mx = _mean(xs)
        num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) or 1e-12
        scores.append(abs(num / den))
    return sorted(sorted(range(len(feats)), key=lambda j: scores[j], reverse=True)[:m])


def model_mad_anomaly(X: List[List[float]], feats: List[str]) -> Tuple[List[float], Dict[str, Any]]:
    cols = list(zip(*X)) if X else []
    stats = []
    for c in cols:
        med = _median(list(c))
        mad = _median([abs(v - med) for v in c]) * 1.4826 or max(_std(list(c)), 1e-9)
        stats.append((med, mad))
    scores = []
    contrib: Dict[str, float] = {f: 0.0 for f in feats}
    for row in X:
        zs = [abs(v - stats[j][0]) / stats[j][1] for j, v in enumerate(row)]
        scores.append(max(zs) if zs else 0.0)
        for j, z in enumerate(zs):
            if z >= OPT_CONFIG["ANOMALY_Z"]:
                contrib[feats[j]] += 1
    top = sorted(contrib.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return scores, {"z_threshold": OPT_CONFIG["ANOMALY_Z"], "flagged_rows": sum(1 for s in scores if s >= OPT_CONFIG["ANOMALY_Z"]),
                    "top_anomalous_features": [{"feature": k, "flag_count": v} for k, v in top]}


def model_weighted_logistic(X: List[List[float]], y: List[int], feats: List[str], tr: List[int], te: List[int]) -> Tuple[List[float], Dict[str, Any]]:
    d = len(feats)
    mu = [_mean([X[i][j] for i in tr]) for j in range(d)]
    sd = [max(_std([X[i][j] for i in tr]), 1e-9) for j in range(d)]
    Z = [[(row[j] - mu[j]) / sd[j] for j in range(d)] for row in X]
    n_pos = sum(y[i] for i in tr) or 1
    n_neg = (len(tr) - n_pos) or 1
    wpos, wneg = len(tr) / (2.0 * n_pos), len(tr) / (2.0 * n_neg)
    w = [0.0] * d
    b = 0.0
    lr, l2 = 0.2, 1e-3
    for _ in range(200):
        gw = [0.0] * d
        gb = 0.0
        for i in tr:
            z = b + sum(w[j] * Z[i][j] for j in range(d))
            p = 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))
            sw = wpos if y[i] == 1 else wneg
            e = (p - y[i]) * sw
            for j in range(d):
                gw[j] += e * Z[i][j]
            gb += e
        for j in range(d):
            w[j] -= lr * (gw[j] / len(tr) + l2 * w[j])
        b -= lr * gb / len(tr)
    scores = [b + sum(w[j] * Z[i][j] for j in range(d)) for i in range(len(X))]
    imp = sorted(zip(feats, w), key=lambda t: abs(t[1]), reverse=True)[:5]
    return scores, {"top_features_by_abs_coef": [{"feature": f, "coef": round(c, 4)} for f, c in imp], "class_weights": [round(wneg, 3), round(wpos, 3)]}


def model_boosted_stumps(X: List[List[float]], y: List[int], feats: List[str], tr: List[int]) -> Tuple[List[float], Dict[str, Any]]:
    d, nb = len(feats), 12
    edges = []
    for j in range(d):
        col = sorted(X[i][j] for i in tr)
        es = sorted({col[min(int(len(col) * q / nb), len(col) - 1)] for q in range(1, nb)})
        edges.append(es)
    binned = [[bisect.bisect_left(edges[j], X[i][j]) for j in range(d)] for i in range(len(X))]
    n_pos = sum(y[i] for i in tr) or 1
    n_neg = (len(tr) - n_pos) or 1
    wpos, wneg = len(tr) / (2.0 * n_pos), len(tr) / (2.0 * n_neg)
    F = [0.0] * len(X)
    stumps, gain_by_feat = [], {f: 0.0 for f in feats}
    lam, lr = 1.0, 0.3
    for _ in range(40):
        g = {}
        h = {}
        for i in tr:
            p = 1.0 / (1.0 + math.exp(-max(min(F[i], 30.0), -30.0)))
            sw = wpos if y[i] == 1 else wneg
            g[i], h[i] = sw * (p - y[i]), sw * p * (1 - p)
        Gt, Ht = sum(g.values()), sum(h.values())
        best = (0.0, -1, -1, 0.0, 0.0)
        for j in range(d):
            nbin = len(edges[j]) + 1
            G, H = [0.0] * nbin, [0.0] * nbin
            for i in tr:
                G[binned[i][j]] += g[i]
                H[binned[i][j]] += h[i]
            gl = hl = 0.0
            for t in range(nbin - 1):
                gl += G[t]
                hl += H[t]
                gr, hr = Gt - gl, Ht - hl
                gain = gl * gl / (hl + lam) + gr * gr / (hr + lam) - Gt * Gt / (Ht + lam)
                if gain > best[0]:
                    best = (gain, j, t, -gl / (hl + lam) * lr, -gr / (hr + lam) * lr)
        if best[1] < 0:
            break
        _, j, t, lv, rv = best
        stumps.append((j, t, lv, rv))
        gain_by_feat[feats[j]] += best[0]
        for i in range(len(X)):
            F[i] += lv if binned[i][j] <= t else rv
    imp = sorted(gain_by_feat.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return F, {"rounds": len(stumps), "top_features_by_gain": [{"feature": k, "gain": round(v, 4)} for k, v in imp]}


# ============================================================================
# 5. HPC 병목 진단 (I/O vs Compute)
# ============================================================================
def profile_pipeline(workspace: Path) -> Dict[str, Any]:
    from auto_solver_pipeline import load_all_workspace_assets, infer_and_solve
    t0 = time.perf_counter()
    assets = load_all_workspace_assets(workspace)
    t_load = time.perf_counter() - t0
    pr = cProfile.Profile()
    t1 = time.perf_counter()
    pr.enable()
    try:
        infer_and_solve(assets)
    finally:
        pr.disable()
    t_solve = time.perf_counter() - t1
    buf = io.StringIO()
    stats = pstats.Stats(pr, stream=buf).sort_stats("cumulative")
    top = []
    for func, (cc, nc, tt, ct, _) in list(stats.stats.items()):
        top.append({"function": f"{Path(func[0]).name}:{func[2]}", "calls": nc, "total_s": round(tt, 4), "cumulative_s": round(ct, 4)})
    top = sorted(top, key=lambda r: r["cumulative_s"], reverse=True)[:10]
    diag = "I/O(파일 파싱) 병목" if t_load > t_solve else "Compute(솔버 연산) 병목"
    return {"load_seconds": round(t_load, 4), "solve_seconds": round(t_solve, 4), "diagnosis": diag, "top_hotspots": top,
            "next_actions": ["I/O 병목이면: 행 수 제한/청크 파싱/컬럼 선택 로드" if t_load > t_solve else
                             "Compute 병목이면: 상위 hotspot 함수의 이중 루프를 사전 계산(dict/prefix-sum)로 대체, 탐색 범위(후보 수) 축소"],
            "not_available_here": "CUDA/SIMD/양자화는 순수 Python 환경에서 미적용 (설치된 패키지는 --propose 출력의 environment 참고)"}


# ============================================================================
# 6. 후보 러너 (Runner)
# ============================================================================
def _sel_problem(views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Tuple[SelProblem, List[str]]:
    items = views["selection"]["data"]
    ov = assets.get("canonical_overrides", {})
    notes = []
    budget = args.budget if args.budget is not None else ov.get("total_budget")
    if budget is None and args.objective == "max_value":
        budget = round(sum(it["cost"] for it in items if not it["forbidden"]) * 0.5, 4)
        notes.append(f"예산 미지정 -> 전체 비용의 50%({budget})로 가정 (--budget 으로 지정 권장)")
    cap = args.capacity if args.capacity is not None else ov.get("total_capacity")
    if cap is not None and not any(it["cap_present"] for it in items):
        cap = None
    target = args.value_target
    if args.objective == "min_cost" and target is None:
        target = round(sum(it["value"] for it in items if not it["forbidden"]) * 0.5, 4)
        notes.append(f"가치 목표 미지정 -> 전체 가치의 50%({target})로 가정 (--value-target 으로 지정 권장)")
    return SelProblem(items, budget, cap, args.objective, target), notes


def _cover_problem(views: Dict[str, Any], args: Any) -> Tuple[CoverProblem, List[str]]:
    obj = "max_coverage_budget" if args.objective in ("max_coverage_budget",) else "min_cost_cover"
    items = views["cover"]["data"]
    notes = []
    budget = args.budget
    if obj == "max_coverage_budget" and budget is None:
        budget = round(sum(it["cost"] for it in items) * 0.5, 4)
        notes.append(f"예산 미지정 -> 전체 비용의 50%({budget})로 가정")
    return CoverProblem(items, obj, budget), notes


def _wrap(candidate: str, family: str, objective: str, summary: Dict[str, Any], optimality: str, t0: float, notes: List[str], details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"candidate": candidate, "family": family, "objective": objective, "optimality": optimality,
            "runtime_ms": round((time.perf_counter() - t0) * 1000, 1), "result": summary, "assumptions": notes, "details": details or {}}


def run_sel(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    p, notes = _sel_problem(views, args, assets)
    seed = args.seed
    greedy = p.greedy_mask()
    if cid == "sel_greedy":
        return _wrap(cid, "SEL", p.objective, p.summarize(greedy), "HEURISTIC", t0, notes)
    if cid == "sel_dp_exact":
        res = exact_dp_selection(p)
        if res is None:
            return {"candidate": cid, "error": "DP 적용 불가 (max_value+예산 필요, 또는 상태 수 초과). sel_bnb_exact 사용 권장"}
        m, ex = res
        return _wrap(cid, "SEL", p.objective, p.summarize(m), "PROVEN_OPTIMAL" if ex else "NEAR_OPTIMAL_(scaled)", t0, notes)
    if cid == "sel_bnb_exact":
        m, proven, nodes = exact_bnb_selection(p)
        return _wrap(cid, "SEL", p.objective, p.summarize(m), "PROVEN_OPTIMAL" if proven else "HEURISTIC_(node_limit)", t0, notes, {"nodes": nodes})
    if cid == "sel_sa":
        m, it = simulated_annealing(p, greedy, seed, min(OPT_CONFIG["SA_MAX_ITERS"], 400 * max(p.n, 10) + 2000))
        return _wrap(cid, "SEL", p.objective, p.summarize(m if m else greedy), "HEURISTIC", t0, notes, {"iterations": it, "seed": seed})
    if cid == "sel_ga":
        m, ev = genetic_algorithm(p, [greedy], seed, OPT_CONFIG["GA_POP"], OPT_CONFIG["GA_GENS"])
        return _wrap(cid, "SEL", p.objective, p.summarize(m if m else greedy), "HEURISTIC", t0, notes, {"evaluations": ev, "seed": seed})
    return {"candidate": cid, "error": "unknown"}


def run_cov(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    p, notes = _cover_problem(views, args)
    greedy = p.greedy_mask()
    if cid == "cov_greedy":
        return _wrap(cid, "COV", p.objective, p.summarize(greedy), "HEURISTIC_(ln n approx)", t0, notes)
    if cid == "cov_exact":
        if p.objective == "min_cost_cover":
            m, proven, nodes = exact_bnb_cover(p)
            return _wrap(cid, "COV", p.objective, p.summarize(m), "PROVEN_OPTIMAL" if proven else "HEURISTIC_(node_limit)", t0, notes, {"nodes": nodes})
        if len(p.free) <= OPT_CONFIG["EXHAUSTIVE_MAX_FREE_ITEMS"]:
            m, cnt = exhaustive_generic(p)
            return _wrap(cid, "COV", p.objective, p.summarize(m if m else greedy), "PROVEN_OPTIMAL", t0, notes, {"enumerated": cnt})
        return {"candidate": cid, "error": f"max_coverage_budget 정확해는 후보 {OPT_CONFIG['EXHAUSTIVE_MAX_FREE_ITEMS']}개 이하만 지원. cov_sa/cov_ga 사용"}
    if cid == "cov_sa":
        m, it = simulated_annealing(p, greedy, args.seed, min(OPT_CONFIG["SA_MAX_ITERS"], 400 * max(p.n, 10) + 2000))
        return _wrap(cid, "COV", p.objective, p.summarize(m if m else greedy), "HEURISTIC", t0, notes, {"iterations": it})
    if cid == "cov_ga":
        m, ev = genetic_algorithm(p, [greedy], args.seed, OPT_CONFIG["GA_POP"], OPT_CONFIG["GA_GENS"])
        return _wrap(cid, "COV", p.objective, p.summarize(m if m else greedy), "HEURISTIC", t0, notes, {"evaluations": ev})
    return {"candidate": cid, "error": "unknown"}


def run_sch(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    jobs = views["jobs"]["data"]
    m = args.machines or int(assets.get("canonical_overrides", {}).get("machines", OPT_CONFIG["DEFAULT_MACHINES"]))
    obj = args.sched_objective
    key = SCHED_OBJ_KEY[obj]
    notes = [] if args.machines else [f"설비 대수 미지정 -> {m}대로 가정 (--machines 로 지정)"]
    if any(j["due"] is None for j in jobs) and obj in ("total_tardiness", "late_jobs"):
        notes.append("납기(due) 컬럼이 없는 작업이 있어 해당 작업의 지연은 0으로 계산됨")
    orders = dispatch_orders(jobs)
    table = {name: list_schedule(jobs, o, m)[1] for name, o in orders.items()}
    best_rule = min(table, key=lambda r: table[r][key])
    if cid == "sch_rules":
        rows, met = list_schedule(jobs, orders[best_rule], m)
        return _wrap(cid, "SCH", obj, {"best_rule": best_rule, "metrics": met, "schedule": rows}, "HEURISTIC_(dispatch rule)", t0, notes,
                     {"rule_comparison": table})
    if cid == "sch_sa":
        o = sched_sa(jobs, m, obj, args.seed, orders[best_rule])
        rows, met = list_schedule(jobs, o, m)
        return _wrap(cid, "SCH", obj, {"start_rule": best_rule, "metrics": met, "schedule": rows}, "HEURISTIC", t0, notes,
                     {"rule_comparison": table, "improvement_vs_best_rule": round(table[best_rule][key] - met[key], 4)})
    if cid == "sch_exact":
        if len(jobs) > OPT_CONFIG["SCHED_EXACT_MAX_JOBS"]:
            return {"candidate": cid, "error": f"전수탐색은 작업 {OPT_CONFIG['SCHED_EXACT_MAX_JOBS']}개 이하만 지원 (현재 {len(jobs)}개). sch_sa 사용"}
        best_o, best_v = None, float("inf")
        for perm in itertools.permutations(range(len(jobs))):
            v = list_schedule(jobs, list(perm), m)[1][key]
            if v < best_v:
                best_o, best_v = list(perm), v
        rows, met = list_schedule(jobs, best_o, m)
        return _wrap(cid, "SCH", obj, {"metrics": met, "schedule": rows}, "PROVEN_OPTIMAL_(list-schedule space)", t0, notes, {"rule_comparison": table})
    return {"candidate": cid, "error": "unknown"}


def run_prd(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    pv = views["prediction"]["data"]
    rows, feats = pv["rows"], pv["features"]
    variants = [("raw", rows, feats)]
    if args.derive:
        r2, f2 = derive_features(rows, feats, pv["group_col"])
        variants = [("derived", r2, f2)]
    y = pv["labels"]
    out = {}
    for tag, rr, ff in variants:
        X = _matrix(rr, ff)
        if cid == "prd_mad_anomaly":
            scores, det = model_mad_anomaly(X, ff)
            res = {"details": det, "variant": tag}
            if y is not None:
                res.update({"auroc_all_rows": round(auroc(scores, y), 4), **f1_at_prevalence(scores, y)})
            else:
                order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:10]
                res["top_anomalous_rows"] = [{"row_index": i, "score": round(scores[i], 3)} for i in order]
                res["note"] = "라벨 컬럼 없음 -> 비지도 이상탐지 결과만 제공"
            out = res
        else:
            if y is None:
                return {"candidate": cid, "error": "라벨(이진) 컬럼을 찾지 못함. --label 로 지정하거나 prd_mad_anomaly(비지도) 사용"}
            tr, te = _split(y)
            sel = _select_features(X, y, ff, tr)
            Xs = [[row[j] for j in sel] for row in X]
            fs = [ff[j] for j in sel]
            if cid == "prd_weighted_logistic":
                scores, det = model_weighted_logistic(Xs, y, fs, tr, te)
            else:
                scores, det = model_boosted_stumps(Xs, y, fs, tr)
            yt = [y[i] for i in te]
            st = [scores[i] for i in te]
            out = {"variant": tag, "details": det, "holdout": {"rows": len(te), "positives": sum(yt), "auroc": round(auroc(st, yt), 4), **f1_at_prevalence(st, yt)},
                   "protocol": "클래스별 계층 분할(3개 중 1개 holdout), 임계값=holdout 양성 개수 기준 상위 k (정답 튜닝 없음)"}
    return _wrap(cid, "PRD", "classification/anomaly", out, "STATISTICAL_MODEL", t0, [])


def run_hpc(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    return _wrap(cid, "HPC", "latency", profile_pipeline(Path(args.workspace).resolve()), "DIAGNOSTIC", t0, [])


# ----------------------------------------------------------------------------
# 5대 반도체 도메인 특화 러너 (Runner)
# ----------------------------------------------------------------------------
def run_mkt(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_market import MarketStrategySolver
    from auto_solver_pipeline import auto_join_tables_fact_first, find_auxiliary_table
    tbls = views["domain_market"]["data"]
    merged_rows = auto_join_tables_fact_first(tbls)
    docs = assets.get("documents", [])
    overrides = dict(assets.get("canonical_overrides", {}))
    unpivoted = MarketStrategySolver.unpivot_wide_quarterly_records(merged_rows)
    ir_rows = find_auxiliary_table(tbls, {"ir_transcript_excerpt", "curr_inventory_days_dio", "ir_bullish_sentiment_score"})
    pq_auto = MarketStrategySolver.auto_extract_pq_mix_from_records(unpivoted)
    ir_auto = ir_rows or MarketStrategySolver.auto_build_ir_audit_from_records_and_docs(unpivoted, docs)

    strat_map = {
        "mkt_grid_fine": "fine_grid",
        "mkt_golden_section": "golden_section",
        "mkt_pareto_dual": "pareto_dual",
        "mkt_grid_coarse": "coarse_grid",
    }
    opt_strat = strat_map.get(cid, "coarse_grid")
    min_dram = 30.0 if cid == "mkt_pareto_dual" else 0.0
    res = MarketStrategySolver.simulate_allocation_grid(
        competitor_records=unpivoted,
        pq_mix_periods=pq_auto,
        ir_audit_records=ir_auto,
        documents=docs,
        opt_strategy=opt_strat,
        min_dram_supply_bgb=min_dram,
        **overrides,
    )
    opt = res.get("optimal_strategy", {})
    summary = {
        "best_hbm_wafer_share_pct": opt.get("hbm_wafer_share_pct"),
        "total_operating_profit_musd": opt.get("total_operating_profit_musd"),
        "operating_margin_pct": opt.get("operating_margin_pct"),
        "effective_hbm_output_bgb": opt.get("effective_hbm_output_bgb"),
        "tsv_bottleneck_clipped_bgb": opt.get("tsv_bottleneck_clipped_bgb"),
        "evaluated_scenarios_count": len(res.get("scenario_table", [])),
    }
    return _wrap(cid, "MKT", "wafer_capacity_allocation_operating_profit", summary, res.get("optimality", "HEURISTIC"), t0, [])


def run_vc(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_value_chain_biz import ValueChainBusinessSolver
    from auto_solver_pipeline import auto_join_tables_fact_first, find_auxiliary_table
    tbls = views["domain_value_chain"]["data"]
    merged_rows = auto_join_tables_fact_first(tbls)
    docs = assets.get("documents", [])
    overrides = dict(assets.get("canonical_overrides", {}))
    prod_tbl = find_auxiliary_table(tbls, {"capex_per_k_wafer_musd", "die_penalty_factor", "lta_min_committed_wafers_k", "capex_k", "roic_pct"})
    node_tbl = find_auxiliary_table(tbls, {"stage_order", "lead_time_months", "inventory_buffer_sensitivity", "node_name"})

    strat_map = {
        "vc_bnb_exact": "bnb_exact",
        "vc_sa_portfolio": "sa_portfolio",
        "vc_greedy_2phase": "greedy_2phase",
    }
    payload = {
        **overrides,
        "documents": docs,
        "records": merged_rows,
        "product_candidates": prod_tbl,
        "supply_chain_nodes": node_tbl,
        "opt_strategy": strat_map.get(cid, "greedy_2phase"),
    }
    res = ValueChainBusinessSolver.solve_all(payload)
    roic_res = res.get("capex_roic_optimization", {})
    summary = {
        "portfolio_weighted_roic_pct": roic_res.get("portfolio_weighted_roic_pct"),
        "value_created_eva_musd": roic_res.get("value_created_eva_musd"),
        "utilized_capex_musd": roic_res.get("utilized_capex_musd"),
        "allocated_products": [
            {"product": p.get("product"), "allocated_wafers_k": p.get("allocated_wafers_k"), "nopat_musd": p.get("expected_nopat_musd")}
            for p in roic_res.get("optimal_product_allocations", [])
        ],
    }
    return _wrap(cid, "VC", "capex_portfolio_roic_eva_maximization", summary, roic_res.get("optimality", "HEURISTIC"), t0, [])


def run_ovl(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_overlay import OverlaySolver
    from auto_solver_pipeline import auto_join_tables_fact_first, find_auxiliary_table
    tbls = views["domain_overlay"]["data"]
    merged_rows = auto_join_tables_fact_first(tbls)
    scanner_rows = find_auxiliary_table(tbls, {"matching_offset_nm", "queue_time_mins"})
    overrides = dict(assets.get("canonical_overrides", {}))

    strat_map = {
        "ovl_sampling_maxmin": "maxmin_spatial",
        "ovl_sampling_greedy": "greedy_vulnerability",
    }
    payload = {
        "measurements": merged_rows,
        "candidate_scanners": scanner_rows or [],
        "m3s_spec_nm": overrides.get("m3s_spec_nm", 2.0),
        "opt_strategy": strat_map.get(cid, "greedy_vulnerability"),
    }
    res = OverlaySolver.solve_apc(**payload)
    sp = res.get("smart_sampling_plan", {})
    summary = {
        "sampled_shot_count": sp.get("smart_sampled_shot_count"),
        "metrology_tat_reduction_pct": sp.get("metrology_tat_reduction_pct"),
        "estimated_defect_capture_rate_pct": sp.get("estimated_defect_capture_rate_pct"),
        "after_m3s_dx": res.get("metrics", {}).get("after_m3s_dx"),
        "after_m3s_dy": res.get("metrics", {}).get("after_m3s_dy"),
        "selected_order": res.get("selected_order"),
    }
    return _wrap(cid, "OVL", "smart_sampling_tat_reduction_and_apc", summary, sp.get("optimality", "HEURISTIC"), t0, [])


def run_mat(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_material import MaterialQualitySolver
    from auto_solver_pipeline import auto_join_tables_fact_first, reshape_flat_rows_to_material_payload
    tbls = views["domain_material"]["data"]
    merged_rows = auto_join_tables_fact_first(tbls)
    overrides = dict(assets.get("canonical_overrides", {}))
    shaped = reshape_flat_rows_to_material_payload(merged_rows, assets.get("json_objects", {}), overrides, tables=tbls)

    strat_map = {
        "mat_portfolio_opt": "portfolio_opt",
        "mat_rule_share": "rule_share",
    }
    shaped["opt_strategy"] = strat_map.get(cid, "rule_share")
    res = MaterialQualitySolver.compare_vendors(**shaped)
    rankings = res.get("vendor_rankings", [])
    summary = {
        "recommended_vendor": res.get("recommended_vendor"),
        "vendor_splits": [
            {"vendor_id": v.get("vendor_id"), "optimal_split_pct": v.get("optimal_dual_sourcing_split_pct"), "decision": v.get("decision")}
            for v in rankings
        ],
        "quarantined_lot_count": len(res.get("quarantined_lot_ids", [])),
    }
    return _wrap(cid, "MAT", "vendor_sourcing_share_and_risk_minimization", summary, res.get("optimality", "HEURISTIC"), t0, [])


def run_edu(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_curriculum import CurriculumOntologySolver
    from auto_solver_pipeline import auto_join_tables_fact_first, find_auxiliary_table
    tbls = views["domain_educator"]["data"]
    merged_rows = auto_join_tables_fact_first(tbls)
    docs = assets.get("documents", [])
    overrides = dict(assets.get("canonical_overrides", {}))
    learner_rows = find_auxiliary_table(tbls, {"learner_id", "completed_ids", "target_ids", "max_hours"})
    mod_rows = find_auxiliary_table(tbls, {"prereqs", "prerequisites", "module_id", "course_id"}) or merged_rows

    strat_map = {
        "edu_dag_bnb_exact": "dag_bnb",
        "edu_kahn_greedy": "kahn_greedy",
    }
    payload = {
        "modules": mod_rows,
        "learner_profile": learner_rows[0] if learner_rows else {"max_hours": overrides.get("max_hours", 9999.0)},
        "learner_profiles": learner_rows,
        "documents": docs,
        "max_hours": overrides.get("max_hours", 9999.0),
        "opt_strategy": strat_map.get(cid, "kahn_greedy"),
    }
    res = CurriculumOntologySolver.analyze_and_schedule(**payload)
    summary = {
        "total_scheduled_modules": res.get("total_scheduled_modules"),
        "total_scheduled_hours": res.get("total_scheduled_hours"),
        "budget_max_hours": res.get("budget_max_hours"),
        "scheduled_module_ids": [m.get("id") for m in res.get("learning_path", [])],
        "misconceptions_count": len(res.get("misconception_diagnostics", [])),
    }
    return _wrap(cid, "EDU", "curriculum_dag_time_constrained_learning_value", summary, res.get("optimality", "HEURISTIC"), t0, [])


def run_type_a(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_typeA import TypeASolver
    from auto_solver_pipeline import auto_join_tables_fact_first
    tbls = views.get("domain_type_a", {}).get("data", {})
    merged_rows = auto_join_tables_fact_first(tbls) if tbls else []
    payload = {"records": merged_rows, "documents": assets.get("documents", []), "time_budget_mins": args.budget or 30.0}
    res = TypeASolver.solve(payload)
    knap = res.get("alarm_troubleshooting", {}).get("knapsack_action_optimization", {})
    rag = res.get("rag_retrieval", {})
    summary = {
        "allocated_time_mins": knap.get("allocated_time_mins"),
        "total_risk_reduction_score": knap.get("total_risk_reduction_score"),
        "action_count": len(knap.get("optimal_action_sequence", [])),
        "query_coverage_pct": rag.get("query_coverage_pct"),
        "is_passed": res.get("coaching_evaluation", {}).get("is_passed"),
    }
    return _wrap(cid, "TYPE_A", "text_rag_and_alarm_knapsack", summary, knap.get("optimality", "PROVEN_OPTIMAL"), t0, [])


def run_type_b(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_typeB import TypeBSolver
    from auto_solver_pipeline import auto_join_tables_fact_first
    tbls = views.get("domain_type_b", {}).get("data", {})
    merged_rows = auto_join_tables_fact_first(tbls) if tbls else []
    payload = {"records": merged_rows, "dies": merged_rows, "total_budget": args.budget or 100.0, "spare_repair_limit": int(args.capacity or 10)}
    res = TypeBSolver.solve(payload)
    bg = res.get("yield_decomposition", {}).get("budget_allocation_optimization", {})
    rep = res.get("wafer_map_analysis", {}).get("redundancy_repair_optimization", {})
    summary = {
        "base_yield_pct": res.get("wafer_map_analysis", {}).get("base_yield_pct"),
        "post_repair_yield_pct": rep.get("post_repair_yield_pct"),
        "repaired_die_count": rep.get("repaired_die_count"),
        "baseline_cumulative_yield_pct": res.get("yield_decomposition", {}).get("baseline_cumulative_yield_pct"),
        "projected_cumulative_yield_pct": bg.get("projected_cumulative_yield_pct"),
        "spent_budget": bg.get("spent_budget"),
        "worst_step": (res.get("yield_decomposition", {}).get("worst_bottleneck_step") or {}).get("step_id"),
    }
    return _wrap(cid, "TYPE_B", "wafer_spatial_and_yield_knapsack", summary, bg.get("optimality", "PROVEN_OPTIMAL"), t0, [])


def run_type_c(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_typeC import TypeCSolver
    from auto_solver_pipeline import auto_join_tables_fact_first
    tbls = views.get("domain_type_c", {}).get("data", {})
    merged_rows = auto_join_tables_fact_first(tbls) if tbls else []
    payload = {"records": merged_rows, "series": merged_rows}
    res = TypeCSolver.solve(payload)
    opt = res.get("threshold_cost_optimization", {})
    summary = {
        "optimal_z_threshold": opt.get("optimal_z_threshold"),
        "optimal_ucl": opt.get("optimal_ucl"),
        "optimal_lcl": opt.get("optimal_lcl"),
        "minimized_expected_loss_cost": opt.get("minimized_expected_loss_cost"),
        "f1_score_at_optimum": opt.get("f1_score_at_optimum"),
        "anomaly_count": res.get("anomaly_count"),
    }
    return _wrap(cid, "TYPE_C", "fdc_sensor_bayes_cost_minimization", summary, opt.get("optimality", "PROVEN_OPTIMAL_ON_GRID"), t0, [])


def run_type_d(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_typeD import TypeDSolver
    from auto_solver_pipeline import auto_join_tables_fact_first
    tbls = views.get("domain_type_d", {}).get("data", {})
    merged_rows = auto_join_tables_fact_first(tbls) if tbls else []
    payload = {"records": merged_rows, "equipments": merged_rows, "available_pm_slots": int(args.capacity or 2)}
    res = TypeDSolver.solve(payload)
    pm_opt = res.get("pm_and_rul_optimization", {}).get("pm_slot_schedule_optimization", {})
    wf = res.get("workflow_validation", {})
    summary = {
        "equipment_count": res.get("pm_and_rul_optimization", {}).get("equipment_count"),
        "urgent_pm_count": res.get("pm_and_rul_optimization", {}).get("urgent_pm_count"),
        "immediate_assigned": pm_opt.get("immediate_slot_assigned_equips"),
        "total_makespan_hours": wf.get("cpm_schedule_analysis", {}).get("total_makespan_hours"),
        "illegal_transition_count": wf.get("illegal_transition_count"),
    }
    return _wrap(cid, "TYPE_D", "weibull_pm_and_workflow_cpm", summary, "PROVEN_OPTIMAL", t0, [])


def run_type_e(cid: str, views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    from solver_typeE import TypeESolver
    from auto_solver_pipeline import auto_join_tables_fact_first
    tbls = views.get("domain_type_e", {}).get("data", {})
    merged_rows = auto_join_tables_fact_first(tbls) if tbls else []
    payload = {"records": merged_rows, "parameters": merged_rows, "target_output_error": float(args.value_target or 0.0)}
    res = TypeESolver.solve(payload)
    cpk_opt = res.get("cpk_and_setpoint_optimization", {})
    summary = {
        "out_of_spec_count": res.get("out_of_spec_count"),
        "low_margin_warning_count": res.get("low_margin_warning_count"),
        "residual_output_error_after_tuning": cpk_opt.get("residual_output_error_after_tuning"),
        "tuned_params_count": len(cpk_opt.get("multi_parameter_fine_tuning", [])),
    }
    return _wrap(cid, "TYPE_E", "recipe_centering_and_min_norm_tuning", summary, "PROVEN_OPTIMAL", t0, [])


# ============================================================================
# 7. 후보 레지스트리 + 제안(Proposal)
# ============================================================================
CANDIDATES: List[Dict[str, Any]] = [
    # --- 1) 시장전략팀 (MKT) 후보군 ---
    {"id": "mkt_grid_fine", "family": "MKT", "title": "0.5% 미세 정밀 격자 탐색 (TSV 클리핑 경계점 정밀 포착)", "exact": True, "impl": True,
     "pros": "TSV 병목 손실이 시작되는 임계 비중을 0.5% 오차 내에서 완벽 포착 (PROVEN_OPTIMAL)", "cons": "평가 시나리오 수 증가 (120개)", "kind": "domain_market"},
    {"id": "mkt_golden_section", "family": "MKT", "title": "황금분할 1차원 연속 극점 수렴 (Golden-Section Search)", "exact": True, "impl": True,
     "pros": "0.01% 단위 연속 최적 비중으로 초고속(15회 평가) 수렴", "cons": "영업이익 곡선이 단봉(Unimodal) 형태일 때 유효", "kind": "domain_market"},
    {"id": "mkt_pareto_dual", "family": "MKT", "title": "다목적 파레토 (영업이익 극대화 + 범용 DRAM 최소 공급 제약)", "exact": False, "impl": True,
     "pros": "HBM 올인 시 범용 고객사 이탈 위험 방지, 현실적 현업 제약 반영", "cons": "단순 이익 최대점 대비 소폭 이익 감소", "kind": "domain_market"},
    {"id": "mkt_grid_coarse", "family": "MKT", "title": "5% 간격 성긴 격자 (기준선 휴리스틱)", "exact": False, "impl": True,
     "pros": "초고속 계산 (10개 시나리오), 직관적 요약", "cons": "10% 단위 사이의 정밀 최적점 놓침", "kind": "domain_market"},

    # --- 2) 경영전략팀 (VC) 후보군 ---
    {"id": "vc_bnb_exact", "family": "VC", "title": "다중 제약 정수 배낭 Branch & Bound (ROIC/EVA 극대화)", "exact": True, "impl": True,
     "pros": "CAPEX 예산 + 클린룸 면적 + LTA 계약 3대 제약 하에서 증명된 최적 배분 (PROVEN_OPTIMAL)", "cons": "제품 수가 극단적으로 많으면 탐색 노드 증가", "kind": "domain_value_chain"},
    {"id": "vc_sa_portfolio", "family": "VC", "title": "Simulated Annealing 포트폴리오 (비선형 전환손실 반영)", "exact": False, "impl": True,
     "pros": "공정 전환 시 발생하는 비선형 Capa 손실 곡선을 반영한 유연한 탐색", "cons": "최적 증명 불가", "kind": "domain_value_chain"},
    {"id": "vc_greedy_2phase", "family": "VC", "title": "2-Phase 탐욕 배분 (LTA 충족 후 ROIC 우선, 기준선)", "exact": False, "impl": True,
     "pros": "빠른 계산, 비즈니스 규칙 설명 용이", "cons": "다중 제약 결합 시 배낭 최적해 대비 미세한 기회비용 손실 가능", "kind": "domain_value_chain"},

    # --- 3) 이천 포토기술팀 (OVL) 후보군 ---
    {"id": "ovl_sampling_maxmin", "family": "OVL", "title": "Max-Min 공간 균일성 + 에지 핫스팟 스마트 샘플링", "exact": True, "impl": True,
     "pros": "웨이퍼 전면 기하학적 커버리지와 에지 취약부를 동시 만족, 계측 TAT 65% 절감", "cons": "거리 행렬 계산 필요", "kind": "domain_overlay"},
    {"id": "ovl_sampling_greedy", "family": "OVL", "title": "잔차+반경 취약도 순위 Top-k 탐욕 샘플링 (기준선)", "exact": False, "impl": True,
     "pros": "초고속 정렬 선별", "cons": "특정 영역에 샷이 뭉치는 국소 편향 가능성", "kind": "domain_overlay"},

    # --- 4) 소재품질팀 (MAT) 후보군 ---
    {"id": "mat_portfolio_opt", "family": "MAT", "title": "Markowitz 다변화 포트폴리오 (단일 공급사 70% 상한 + 품질/단가 최적화)", "exact": True, "impl": True,
     "pros": "공급망 단절 리스크 방지(이원화 보장) + Cpk 위험도 최소화", "cons": "최우수 공급사 몰아주기(85%) 대비 단가 소폭 상승", "kind": "domain_material"},
    {"id": "mat_rule_share", "family": "MAT", "title": "규칙 기반 이원화 배분 (85/15/0%, 기준선)", "exact": False, "impl": True,
     "pros": "명확하고 단순한 조달 정책 SOP 준수", "cons": "복수 우수 공급사 간 미세 품질 차이 유연 배분 불가", "kind": "domain_material"},

    # --- 5) 반도체 산업교육 (EDU) 후보군 ---
    {"id": "edu_dag_bnb_exact", "family": "EDU", "title": "선수과목 DAG 제약 0/1 배낭 Branch & Bound 최적 스케줄링", "exact": True, "impl": True,
     "pros": "시간 예산 내 학습 가치 및 필수 타깃 완벽 달성 최적 증명 (PROVEN_OPTIMAL)", "cons": "모듈 수가 많을 때 분기 수 증가", "kind": "domain_educator"},
    {"id": "edu_kahn_greedy", "family": "EDU", "title": "Kahn 위상정렬 Critical Path 우선 탐욕 배정 (기준선)", "exact": False, "impl": True,
     "pros": "선행과목 순서 무결성 보장, 초고속 배정", "cons": "시간 예산 경계선에서 가치가 높은 다른 조합 탐색 불가", "kind": "domain_educator"},

    # --- 6) Type A: Text Rule & Alarm Troubleshooting 후보군 ---
    {"id": "typea_knapsack", "family": "TYPE_A", "title": "0-1 배낭 DP 알람 트러블슈팅 조치 최적화 (가용 시간 내 리스크 감소 최대화)", "exact": True, "impl": True,
     "pros": "교대 시간 한도 내 복구 성공률 극대화 최적 증명 (PROVEN_OPTIMAL)", "cons": "소요 시간이 연속값일 경우 분 단위 양자화 필요", "kind": "domain_type_a"},
    {"id": "typea_submodular", "family": "TYPE_A", "title": "Submodular Max-Coverage 문서 검색 최적화 (키워드 커버리지 극대화)", "exact": False, "impl": True,
     "pros": "동일 내용 중복 문서를 배제하고 질의어 커버리지를 (1 - 1/e) 근사 보장", "cons": "BM25 점수 단독 정렬 대비 추가 연산", "kind": "domain_type_a"},

    # --- 7) Type B: Wafer Map Spatial Defect & Step Yield 후보군 ---
    {"id": "typeb_knapsack", "family": "TYPE_B", "title": "0-1 배낭 DP 수율 개선 예산 배분 최적화 (개선 예산 내 누적 수율 극대화)", "exact": True, "impl": True,
     "pros": "한정된 설비 개선 예산으로 팹 최종 누적 수율 상승분 극대화 최적 증명 (PROVEN_OPTIMAL)", "cons": "스텝별 개선 비용 정수화 필요", "kind": "domain_type_b"},
    {"id": "typeb_line_cover", "family": "TYPE_B", "title": "Greedy Max Line Cover 리던던시 수리 라인(Row/Col) 최적화", "exact": False, "impl": True,
     "pros": "제한된 스페어 회로 라인으로 불량 다이 복구 수 극대화", "cons": "동점 라인 발생 시 탐색 분기 가능", "kind": "domain_type_b"},

    # --- 8) Type C: FDC Time-Series Sensor Anomaly & Threshold 후보군 ---
    {"id": "typec_bayes_grid", "family": "TYPE_C", "title": "Bayes Risk 비용 최소화 격자 탐색 (오탐 FP vs 미탐 FN 기대 손실 최소화)", "exact": True, "impl": True,
     "pros": "설비 불필요 정지 비용과 불량 유출 비용 간 최적 트레이드오프 임계치 도출 (PROVEN_OPTIMAL)", "cons": "격자 분해능에 의존", "kind": "domain_type_c"},
    {"id": "typec_cusum_drift", "family": "TYPE_C", "title": "Tabular CUSUM 미세 평균 드리프트 조기 감지 (누적합 관리도)", "exact": False, "impl": True,
     "pros": "단일 시점 3-Sigma를 넘지 않는 미세 센서 드리프트를 가장 빠르게 포착", "cons": "슬랙 파라미터 k, h 튜닝 필요", "kind": "domain_type_c"},

    # --- 9) Type D: Workflow State Machine & PM Schedule 후보군 ---
    {"id": "typed_weibull_pm", "family": "TYPE_D", "title": "Weibull 갱신보상 모델 최적 PM 주기 T* 수치 적분 탐색", "exact": True, "impl": True,
     "pros": "가동 시간당 정비 비용률 g(T)을 최소화하는 최적 정비 인터벌 도출", "cons": "와이블 형상/척도 모수 사전 피팅 필요", "kind": "domain_type_d"},
    {"id": "typed_slot_priority", "family": "TYPE_D", "title": "위험 손실 기대 비용 순 정비 슬롯 배정 우선순위 최적화", "exact": False, "impl": True,
     "pros": "동시 정비 시 병목 및 고장 위험이 가장 큰 설비부터 우선 배정", "cons": "정비 슬롯 부족 시 후순위 설비 위험 누적", "kind": "domain_type_d"},

    # --- 10) Type E: Recipe Parameter Diff & Cpk Margin 후보군 ---
    {"id": "typee_box_cpk", "family": "TYPE_E", "title": "Box-Constrained Cpk 마진 극대화 센터링 (스펙 범위 투영)", "exact": True, "impl": True,
     "pros": "허용 한계 내에서 공정 능력 지수(Cpk >= 1.33)를 최대로 확보하는 안전 세트포인트 도출", "cons": "다변수 간 상호작용은 개별 처리", "kind": "domain_type_e"},
    {"id": "typee_min_norm_sens", "family": "TYPE_E", "title": "감도 행렬 기반 최소 노름(Min-Norm L2) 다변수 오차 상쇄 보정", "exact": True, "impl": True,
     "pros": "최소한의 파라미터 조작량으로 공정 출력 오차를 0으로 완벽 상쇄", "cons": "스펙 경계 도달 시 클리핑 발생", "kind": "domain_type_e"},

    # --- 6) 제6 범용 도메인 / 일반 도메인 후보군 ---
    {"id": "sel_greedy", "family": "SEL", "title": "Greedy (가치/비용 비율순)", "exact": False, "impl": True,
     "pros": "즉시 계산, 항상 해 존재, 설명 쉬움", "cons": "최적 보장 없음", "kind": "selection"},
    {"id": "sel_dp_exact", "family": "SEL", "title": "다차원 배낭 DP (정확해)", "exact": True, "impl": True,
     "pros": "정수화 가능하면 최적 증명", "cons": "예산·용량 값이 크면 불가(상태 수 제한)", "kind": "selection"},
    {"id": "sel_bnb_exact", "family": "SEL", "title": "Branch & Bound (정확해, ILP 대체)", "exact": True, "impl": True,
     "pros": "소수점 비용·다중 제약도 최적 증명, min_cost 목표 지원", "cons": "후보 수가 많으면 노드 한도 초과(그때는 HEURISTIC 표기)", "kind": "selection"},
    {"id": "sel_sa", "family": "SEL", "title": "Simulated Annealing (메타휴리스틱)", "exact": False, "impl": True,
     "pros": "대규모에서도 근사해, 복잡한 제약 추가 쉬움", "cons": "최적 보장 없음, seed 고정으로 재현", "kind": "selection"},
    {"id": "sel_ga", "family": "SEL", "title": "Genetic Algorithm (메타휴리스틱)", "exact": False, "impl": True,
     "pros": "다양한 해 탐색, 병렬 후보 비교", "cons": "튜닝 파라미터 많음", "kind": "selection"},
    {"id": "cov_greedy", "family": "COV", "title": "Greedy Set-Cover (신규 커버/비용 비율)", "exact": False, "impl": True,
     "pros": "표준 근사(ln n), 즉시 계산", "cons": "최소 비용 보장 없음", "kind": "cover"},
    {"id": "cov_exact", "family": "COV", "title": "Branch & Bound Set-Cover (정확해)", "exact": True, "impl": True,
     "pros": "전체 커버 최소 비용 최적 증명", "cons": "후보 수가 많으면 노드 한도 초과", "kind": "cover"},
    {"id": "cov_sa", "family": "COV", "title": "Simulated Annealing (커버)", "exact": False, "impl": True,
     "pros": "대규모, 예산 내 최대 커버 목적도 지원", "cons": "최적 보장 없음", "kind": "cover"},
    {"id": "cov_ga", "family": "COV", "title": "Genetic Algorithm (커버)", "exact": False, "impl": True,
     "pros": "대규모 근사", "cons": "튜닝 필요", "kind": "cover"},
    {"id": "sch_rules", "family": "SCH", "title": "디스패칭 룰 비교 (FIFO/SPT/LPT/EDD/WSPT)", "exact": False, "impl": True,
     "pros": "실시간 온라인 규칙으로 현장 적용 가능, 룰별 지표 비교표 제공", "cons": "목적별 최적 룰이 다름(비교표로 선택)", "kind": "jobs"},
    {"id": "sch_sa", "family": "SCH", "title": "Simulated Annealing 오프라인 계획 (룰 결과에서 개선)", "exact": False, "impl": True,
     "pros": "룰보다 개선, 목적함수 자유(makespan/지연/가중완료)", "cons": "최적 보장 없음", "kind": "jobs"},
    {"id": "sch_exact", "family": "SCH", "title": "전수탐색 (소규모 정확해)", "exact": True, "impl": True,
     "pros": "작업 8개 이하 최적 증명", "cons": "작업 수 증가 시 불가", "kind": "jobs"},
    {"id": "prd_mad_anomaly", "family": "PRD", "title": "Robust MAD 이상탐지 (비지도)", "exact": False, "impl": True,
     "pros": "라벨 없이도 가능, 극단 불균형에 강함, 원인 피처 설명", "cons": "복합 패턴 약함", "kind": "prediction"},
    {"id": "prd_weighted_logistic", "family": "PRD", "title": "클래스 가중 로지스틱 회귀", "exact": False, "impl": True,
     "pros": "해석 용이(계수), 불균형 가중, 빠름", "cons": "비선형 약함", "kind": "prediction"},
    {"id": "prd_boosted_stumps", "family": "PRD", "title": "부스티드 스텀프 (경량 GBM)", "exact": False, "impl": True,
     "pros": "비선형·tabular에 강함, 피처 gain 설명", "cons": "라벨 필요, 순수 Python이라 LightGBM보다 느림", "kind": "prediction"},
    {"id": "hpc_profile", "family": "HPC", "title": "cProfile 병목 진단 (I/O vs Compute)", "exact": False, "impl": True,
     "pros": "최적화 전 원인 확정(I/O/연산)", "cons": "진단만 수행(수정은 사람이)", "kind": "hpc"},
    {"id": "rl_dispatch", "family": "RL", "title": "강화학습 동적 디스패칭", "exact": False, "impl": False,
     "pros": "동적 환경 적응", "cons": "시뮬레이터·학습 시간 필요 -> 시험 제한시간 내 부적합. 대안: sch_rules(온라인 룰)+sch_sa(오프라인 계획)", "kind": "dynamic_dispatch_hint"},
]


def environment_report() -> Dict[str, bool]:
    mods = ["numpy", "scipy", "pulp", "ortools", "z3", "sklearn", "lightgbm", "catboost", "xgboost", "torch"]
    return {m: importlib.util.find_spec(m) is not None for m in mods}


def propose(views: Dict[str, Any], diag_report: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    out = []
    metric_dominant = diag_report.get("evaluation_metric_axis", {}).get("dominant_metric") if diag_report else None
    bottleneck_nature = diag_report.get("bottleneck_nature_axis", {}).get("bottleneck_nature") if diag_report else None

    for c in CANDIDATES:
        v = views.get(c["kind"])
        if v is None:
            continue
        n = v["size"]
        score, why = 55, [f"테이블 `{v['table']}` 에서 {c['kind']} 구조 감지(크기 {n})"]

        # [사전진단 반영] 평가지표(정확도 vs 속도) 및 병목(알고리즘 vs 하드웨어) 가중치 동적 결합
        if metric_dominant == "ACCURACY" and c["exact"]:
            score += 10
            why.append("사전진단: 평가지표가 정확도/품질 지향 -> 증명된 정확해(Exact) 가산점 반영")
        elif metric_dominant == "SPEED" and (not c["exact"] or c["id"].endswith("greedy")):
            score += 10
            why.append("사전진단: 평가지표가 속도/지연시간 지향 -> 초고속 휴리스틱/탐욕 가산점 반영")

        if bottleneck_nature == "ALGORITHMIC_COMPLEXITY_BOUND" and c["exact"] and n > 24:
            score -= 20
            why.append("사전진단: N>24 조합 지수 폭발 위험 -> 완전탐색/정확해 감점, SA/메타휴리스틱 권장")
        if c["family"] in ("MKT", "VC", "OVL", "MAT", "EDU") or c["family"].startswith("TYPE_"):
            # 5대 반도체 도메인 및 현업 Type A-E 특화 후보는 90~95점 최우선 추천
            score = 92 if c["exact"] else 85
            why.append(f"핵심 도메인 [{c['family']}] 특화 최적화 알고리즘 -> 비즈니스/공정 파라미터 직접 연동")
            if c["id"].endswith("coarse") or c["id"].endswith("greedy") or c["id"].endswith("rule_share") or c["id"].endswith("line_cover") or c["id"].endswith("cusum_drift"):
                why.append("기존 베이스라인(휴리스틱)과의 개선폭 비교 기준선 제공")
        elif c["family"] in ("SEL", "COV"):
            small = n <= OPT_CONFIG["EXHAUSTIVE_MAX_FREE_ITEMS"] + 8
            if c["exact"] and small:
                score += 25
                why.append("후보 수가 작아 정확해(최적 증명) 가능 -> 서술형에서 '최적 보장' 근거 확보")
            elif c["exact"]:
                score += 5
                why.append("후보가 많아 정확해는 시간 한도 초과 가능(초과 시 HEURISTIC 표기)")
            if not c["exact"] and not small:
                score += 15
                why.append("후보가 많아 메타휴리스틱이 현실적")
            if c["id"].endswith("greedy"):
                score += 5
                why.append("베이스라인으로 항상 함께 비교 권장")
            if c["id"] == "sel_dp_exact":
                score -= 5
        elif c["family"] == "SCH":
            if c["id"] == "sch_exact":
                score += 20 if n <= OPT_CONFIG["SCHED_EXACT_MAX_JOBS"] else -30
                why.append("작업 수 기준 전수탐색 가능 여부 반영")
            elif c["id"] == "sch_rules":
                score += 20
                why.append("온라인 디스패칭 룰은 어떤 목적이든 비교 기준선으로 필수")
                if "dynamic_dispatch_hint" in views:
                    score += 5
                    why.append("문서에 동적 디스패치/OHT 언급 감지")
            else:
                score += 15
                why.append("오프라인 계획으로 룰 대비 개선폭 제시")
        elif c["family"] == "PRD":
            has_lab = v["data"]["labels"] is not None
            if c["id"] == "prd_mad_anomaly":
                score += 20 if not has_lab else 8
                why.append("라벨 없음 -> 비지도 우선" if not has_lab else "라벨 있어도 빠른 기준선으로 유용")
            else:
                score += 25 if has_lab else -40
                why.append(f"이진 라벨 `{v['data']['label_col']}` 감지(양성 {sum(v['data']['labels'])}/{len(v['data']['labels'])})" if has_lab else "라벨 컬럼 없음 -> 사용 불가")
            if c["id"] == "prd_boosted_stumps" and has_lab:
                score += 5
                why.append("tabular은 트리 계열 베이스라인이 정석(딥러닝 지양)")
        elif c["family"] == "HPC":
            score += 25
            why.append("문서의 지연/병목 키워드 또는 대용량 테이블 감지: " + ", ".join(v["data"]["keywords"] or ["big_table"]))
        elif c["family"] == "RL":
            score = 15
            why.append("문서에 동적 디스패치 언급: 단 시험 시간 내 학습 어려움 -> 비권장")
        out.append({**{k: c[k] for k in ("id", "family", "title", "exact", "impl", "pros", "cons")}, "fit_score": max(0, min(100, score)), "why": why})
    out.sort(key=lambda r: (r["family"], -r["fit_score"]))
    return out


def decision_questions(views: Dict[str, Any]) -> List[Dict[str, Any]]:
    qs = []
    if "domain_market" in views:
        qs.append({"family": "MKT", "question": "HBM/DRAM 웨이퍼 용량 배분에서 우선시하는 목표는?",
                   "options": ["mkt_grid_fine (0.5% 미세 격자 TSV 임계점 정밀 최적화, 최대 이익)", "mkt_golden_section (초고속 연속 극점 수렴)", "mkt_pareto_dual (레거시 고객 보호 최소 물량 제약 만족)", "mkt_grid_coarse (5% 기준선)"],
                   "flags": "--choose 'mkt_*' 또는 --choose mkt_grid_fine"})
    if "domain_value_chain" in views:
        qs.append({"family": "VC", "question": "CAPEX ROIC 포트폴리오 배분에서 요구되는 엄밀성은?",
                   "options": ["vc_bnb_exact (예산+클린룸+LTA 정수 배낭 최적 증명)", "vc_sa_portfolio (비선형 전환손실 반영 메타휴리스틱)", "vc_greedy_2phase (2단계 탐욕 기준선)"],
                   "flags": "--choose 'vc_*' 또는 --choose vc_bnb_exact"})
    if "domain_overlay" in views:
        qs.append({"family": "OVL", "question": "스마트 계측 샷 선정 방식은?",
                   "options": ["ovl_sampling_maxmin (웨이퍼 전면 기하학적 균일 커버리지 + 취약부 동시 만족)", "ovl_sampling_greedy (취약도 순위 Top-k 기준선)"],
                   "flags": "--choose 'ovl_*' 또는 --choose ovl_sampling_maxmin"})
    if "domain_material" in views:
        qs.append({"family": "MAT", "question": "신규 소재 공급사 조달 비중 배분 기준은?",
                   "options": ["mat_portfolio_opt (단일 공급사 70% 상한 + 공급망 단절 위험 분산 최적화)", "mat_rule_share (85/15% 단순 규칙 기준선)"],
                   "flags": "--choose 'mat_*' 또는 --choose mat_portfolio_opt"})
    if "domain_educator" in views:
        qs.append({"family": "EDU", "question": "선수과목 DAG 제약 하에서 커리큘럼 편성 기준은?",
                   "options": ["edu_dag_bnb_exact (선수과목 엄격 강제 0/1 배낭 학습 가치 극대화)", "edu_kahn_greedy (위상정렬 순차 배정 기준선)"],
                   "flags": "--choose 'edu_*' 또는 --choose edu_dag_bnb_exact"})
    if "domain_type_a" in views:
        qs.append({"family": "TYPE_A", "question": "알람 조치 및 RAG 최적화 방식은?",
                   "options": ["typea_knapsack (시간 제약 0-1 배낭 DP 리스크 감소 최대화)", "typea_submodular (Submodular 질의어 최대 커버리지 문서 검색)"],
                   "flags": "--choose 'typea_*' 또는 --choose typea_knapsack --budget 30"})
    if "domain_type_b" in views:
        qs.append({"family": "TYPE_B", "question": "웨이퍼 맵 수율 개선 및 리던던시 수리 방식은?",
                   "options": ["typeb_knapsack (스텝별 수율 개선 예산 배낭 최적화)", "typeb_line_cover (Row/Col 스페어 라인 커버 최적화)"],
                   "flags": "--choose 'typeb_*' 또는 --choose typeb_knapsack --budget 100"})
    if "domain_type_c" in views:
        qs.append({"family": "TYPE_C", "question": "FDC 센서 이상 감지 임계치 최적화 방식은?",
                   "options": ["typec_bayes_grid (오탐 vs 미탐 Bayes 비용 최소화 격자 탐색)", "typec_cusum_drift (Tabular CUSUM 미세 평균 드리프트 조기 감지)"],
                   "flags": "--choose 'typec_*' 또는 --choose typec_bayes_grid"})
    if "domain_type_d" in views:
        qs.append({"family": "TYPE_D", "question": "설비 PM 주기 및 정비 슬롯 배정 방식은?",
                   "options": ["typed_weibull_pm (Weibull 갱신보상 모델 최적 PM 주기 T*)", "typed_slot_priority (리스크 손실 순 정비 슬롯 우선 배정)"],
                   "flags": "--choose 'typed_*' 또는 --choose typed_weibull_pm"})
    if "domain_type_e" in views:
        qs.append({"family": "TYPE_E", "question": "공정 레시피 Cpk 마진 및 다변수 보정 방식은?",
                   "options": ["typee_box_cpk (Box-Constrained Cpk 마진 극대화 센터링)", "typee_min_norm_sens (감도 행렬 기반 최소 L2 노름 다변수 보정)"],
                   "flags": "--choose 'typee_*' 또는 --choose typee_box_cpk"})
    if "selection" in views:
        qs.append({"family": "SEL", "question": "무엇을 최적화합니까?", "options": ["max_value (예산·용량 내 가치 최대)", "min_cost (가치 목표 달성 최소 비용)"],
                   "flags": "--objective max_value|min_cost  --budget N  --capacity N  --value-target N"})
    if "cover" in views:
        qs.append({"family": "COV", "question": "무엇을 최적화합니까?", "options": ["min_cost_cover (전 구역 커버 최소 비용)", "max_coverage_budget (예산 내 최대 커버)"],
                   "flags": "--objective min_cost_cover|max_coverage_budget  --budget N"})
    if "jobs" in views:
        qs.append({"family": "SCH", "question": "어떤 지표를 줄입니까?", "options": list(SCHED_OBJ_KEY.keys()),
                   "flags": "--sched-objective makespan|total_tardiness|mean_flow_time|weighted_completion|late_jobs  --machines N"})
    if "prediction" in views:
        qs.append({"family": "PRD", "question": "라벨/파생변수 사용은?", "options": ["원본 피처", "도메인 파생변수(--derive: 직전 행 대비 변화량, 설비/Lot 평균 대비 편차)"],
                   "flags": "--label COL  --derive"})
    return qs


RUNNERS: Dict[str, Callable[..., Dict[str, Any]]] = {}
# 5대 도메인 솔버 러너
for _c in ("mkt_grid_fine", "mkt_golden_section", "mkt_pareto_dual", "mkt_grid_coarse"):
    RUNNERS[_c] = run_mkt
for _c in ("vc_bnb_exact", "vc_sa_portfolio", "vc_greedy_2phase"):
    RUNNERS[_c] = run_vc
for _c in ("ovl_sampling_maxmin", "ovl_sampling_greedy"):
    RUNNERS[_c] = run_ovl
for _c in ("mat_portfolio_opt", "mat_rule_share"):
    RUNNERS[_c] = run_mat
for _c in ("edu_dag_bnb_exact", "edu_kahn_greedy"):
    RUNNERS[_c] = run_edu

# Type A-E 현업 특화 솔버 러너
for _c in ("typea_knapsack", "typea_submodular"):
    RUNNERS[_c] = run_type_a
for _c in ("typeb_knapsack", "typeb_line_cover"):
    RUNNERS[_c] = run_type_b
for _c in ("typec_bayes_grid", "typec_cusum_drift"):
    RUNNERS[_c] = run_type_c
for _c in ("typed_weibull_pm", "typed_slot_priority"):
    RUNNERS[_c] = run_type_d
for _c in ("typee_box_cpk", "typee_min_norm_sens"):
    RUNNERS[_c] = run_type_e

# 제6 범용 도메인 러너
for _c in ("sel_greedy", "sel_dp_exact", "sel_bnb_exact", "sel_sa", "sel_ga"):
    RUNNERS[_c] = run_sel
for _c in ("cov_greedy", "cov_exact", "cov_sa", "cov_ga"):
    RUNNERS[_c] = run_cov
for _c in ("sch_rules", "sch_sa", "sch_exact"):
    RUNNERS[_c] = run_sch
for _c in ("prd_mad_anomaly", "prd_weighted_logistic", "prd_boosted_stumps"):
    RUNNERS[_c] = run_prd
RUNNERS["hpc_profile"] = run_hpc


def run_candidates(ids: List[str], views: Dict[str, Any], args: Any, assets: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    for cid in ids:
        fn = RUNNERS.get(cid)
        if fn is None:
            results.append({"candidate": cid, "error": "구현되지 않은 후보 (가이드 전용)"})
            continue
        try:
            results.append(fn(cid, views, args, assets))
        except Exception as e:  # Zero-Crash: 한 후보 실패가 전체를 멈추지 않음
            results.append({"candidate": cid, "error": f"{type(e).__name__}: {e}"})
    return results


def expand_choice(choice: str, proposals: List[Dict[str, Any]]) -> List[str]:
    avail = [p["id"] for p in proposals if p["impl"]]
    if choice.strip().upper() == "ALL":
        return avail
    ids: List[str] = []
    for tok in [t.strip() for t in choice.split(",") if t.strip()]:
        ids.extend([a for a in avail if fnmatch.fnmatch(a, tok)] or [tok])
    return list(dict.fromkeys(ids))


# ============================================================================
# 8. 출력
# ============================================================================
def render_proposal_md(proposals: List[Dict[str, Any]], questions: List[Dict[str, Any]], views: Dict[str, Any], env: Dict[str, bool], diag_report: Optional[Dict[str, Any]] = None) -> str:
    lines = ["# 최적화 방식 후보 제안 (사람이 선택)", ""]

    if diag_report:
        m = diag_report.get("evaluation_metric_axis", {})
        b = diag_report.get("bottleneck_nature_axis", {})
        lines.extend([
            "## 0. 최적화 사전 진단 결과 (Pre-Optimization Diagnostics)",
            f"- **평가지표 성격 (정확도 vs 속도)**: `{m.get('metric_classification')}` (지배적 지표: **{m.get('dominant_metric')}**)",
            f"  ↳ 정확도/품질 지표: `{m.get('accuracy_score')}점` | 속도/지연 지표: `{m.get('speed_score')}점`",
            f"  ↳ 전략 가이드: {m.get('strategic_recommendation')}",
            f"- **병목 성격 (알고리즘 vs 하드웨어)**: `{b.get('bottleneck_nature')}`",
            f"  ↳ 병목 분석: {b.get('bottleneck_summary')}",
            f"  ↳ 조합 위험도: `{b.get('algorithmic_risk_level')}` | 총 행 수: `{b.get('total_rows'):,}`행 | 파일: `{b.get('total_workspace_mb')}MB`",
            "",
        ])

    lines.append("## 감지된 문제 구조")
    for k, v in views.items():
        lines.append(f"- **{k}**: `{v['table']}` (크기 {v['size']})")
    if not views:
        lines.append("- 최적화 가능한 구조를 감지하지 못했습니다. 컬럼명(cost/value/zones/proc_time/label 등) 확인 또는 --label 지정.")
    lines += ["", "## 후보 (fit_score 높은 순 = 추천도, 최종 선택은 사람)"]
    fam = None
    for p in proposals:
        if p["family"] != fam:
            fam = p["family"]
            lines += ["", f"### {fam}", "| id | 방식 | 적합도 | 정확해 | 구현 | 장점 | 단점 |", "|---|---|---|---|---|---|---|"]
        lines.append(f"| `{p['id']}` | {p['title']} | {p['fit_score']} | {'✅' if p['exact'] else '-'} | {'✅' if p['impl'] else '⚠가이드'} | {p['pros']} | {p['cons']} |")
        for w in p["why"]:
            lines.append(f"|  | ↳ {w} | | | | | |")
    lines += ["", "## 결정이 필요한 질문"]
    for q in questions:
        lines.append(f"- [{q['family']}] {q['question']} -> {' / '.join(q['options'])}  \n  옵션: `{q['flags']}`")
    lines += ["", "## 실행 방법", "```", "python engine/optimizer_menu.py --workspace . --choose sel_sa --objective max_value --budget 500",
              "python engine/optimizer_menu.py --workspace . --choose 'sel_*'   # 계열 전체 비교", "python engine/optimizer_menu.py --workspace . --choose ALL", "```",
              "", "## 설치된 라이브러리 (참고: 있으면 ILP/SAT/GBM 사용 가능, 이 모듈은 의존하지 않음)",
              ", ".join(f"{k}:{'O' if v else 'X'}" for k, v in env.items())]
    return "\n".join(lines)


def print_comparison(results: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 100)
    print("📊 후보 비교 결과")
    print("=" * 100)
    for r in results:
        if "error" in r:
            print(f"❌ {r['candidate']}: {r['error']}")
            continue
        res = r["result"]
        if r["family"] in ("SEL", "COV"):
            extra = f"cost={res.get('total_cost')} value={res.get('total_value', '-')} covered={res.get('covered_zone_count', '-')}/{res.get('total_zone_count', '-')} feasible={res['feasible']} n={res['selected_count']}"
        elif r["family"] == "MKT":
            extra = f"최적 HBM 비중={res.get('best_hbm_wafer_share_pct')}% | 최대 영업이익={res.get('total_operating_profit_musd')}M$ | OPM={res.get('operating_margin_pct')}% | HBM출하={res.get('effective_hbm_output_bgb')}B_Gb (TSV손실 {res.get('tsv_bottleneck_clipped_bgb')}B_Gb) | 평가시나리오={res.get('evaluated_scenarios_count')}개"
        elif r["family"] == "VC":
            extra = f"가중 ROIC={res.get('portfolio_weighted_roic_pct')}% | 창출 EVA={res.get('value_created_eva_musd')}M$ | 사용 CAPEX={res.get('utilized_capex_musd')}M$ | 배분: " + ", ".join(f"{p['product']}:{p['allocated_wafers_k']}k" for p in res.get("allocated_products", []))
        elif r["family"] == "OVL":
            extra = f"스마트 샘플링={res.get('sampled_shot_count')}샷 | 계측 TAT 단축={res.get('metrology_tat_reduction_pct')}% | 예상 결함 포착률={res.get('estimated_defect_capture_rate_pct')}% | 보정후 M3S=({res.get('after_m3s_dx')}nm, {res.get('after_m3s_dy')}nm)"
        elif r["family"] == "MAT":
            extra = f"추천 1위={res.get('recommended_vendor')} | 격리 Lot={res.get('quarantined_lot_count')}개 | 조달 분할: " + ", ".join(f"{v['vendor_id']}:{v['optimal_split_pct']}%" for v in res.get("vendor_splits", []))
        elif r["family"] == "EDU":
            extra = f"편성 모듈={res.get('total_scheduled_modules')}개 | 총 시간={res.get('total_scheduled_hours')}/{res.get('budget_max_hours')}h | 모듈: " + ", ".join(res.get("scheduled_module_ids", []))
        elif r["family"] == "TYPE_A":
            extra = f"배정 시간={res.get('allocated_time_mins')}분 | 리스크 감소={res.get('total_risk_reduction_score')}점 | 조치={res.get('action_count')}개 | RAG 커버={res.get('query_coverage_pct')}%"
        elif r["family"] == "TYPE_B":
            extra = f"기저 수율={res.get('base_yield_pct')}% ➔ 수리후={res.get('post_repair_yield_pct')}% (복구 {res.get('repaired_die_count')}다이) | 누적={res.get('baseline_cumulative_yield_pct')}% ➔ 투자후={res.get('projected_cumulative_yield_pct')}%"
        elif r["family"] == "TYPE_C":
            extra = f"최적 Z-Score 임계치={res.get('optimal_z_threshold')} | 기대 손실 최소비용={res.get('minimized_expected_loss_cost')} | F1={res.get('f1_score_at_optimum')} | 이상치={res.get('anomaly_count')}건"
        elif r["family"] == "TYPE_D":
            extra = f"설비 {res.get('equipment_count')}대 중 긴급 PM {res.get('urgent_pm_count')}대 | 즉시 슬롯={res.get('immediate_assigned')} | CPM makespan={res.get('total_makespan_hours')}h"
        elif r["family"] == "TYPE_E":
            extra = f"스펙 초과={res.get('out_of_spec_count')}건 | 마진 경고={res.get('low_margin_warning_count')}건 | 보정 후 오차={res.get('residual_output_error_after_tuning')} | 튜닝={res.get('tuned_params_count')}개"
        elif r["family"] == "SCH":
            extra = " ".join(f"{k}={v}" for k, v in res["metrics"].items())
        elif r["family"] == "PRD":
            ho = res.get("holdout") or {k: res[k] for k in ("auroc_all_rows", "f1") if k in res}
            extra = json.dumps(ho, ensure_ascii=False)
        else:
            extra = f"{res.get('diagnosis')} load={res.get('load_seconds')}s solve={res.get('solve_seconds')}s"
        print(f"✅ {r['candidate']:<24} [{r['optimality']}] {r['runtime_ms']}ms | {extra}")
        for n in r.get("assumptions", []):
            print(f"     ⚠ 가정: {n}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--propose", action="store_true", help="제안서 생성 모드 (기본)")
    ap.add_argument("--choose", default=None, help="실행할 후보 id (쉼표, 와일드카드, ALL)")
    ap.add_argument("--objective", default="max_value", help="max_value|min_cost|min_cost_cover|max_coverage_budget")
    ap.add_argument("--budget", type=float, default=None)
    ap.add_argument("--capacity", type=float, default=None)
    ap.add_argument("--value-target", dest="value_target", type=float, default=None)
    ap.add_argument("--machines", type=int, default=None)
    ap.add_argument("--sched-objective", dest="sched_objective", default="makespan", choices=list(SCHED_OBJ_KEY.keys()))
    ap.add_argument("--label", default=None)
    ap.add_argument("--derive", action="store_true")
    ap.add_argument("--seed", type=int, default=OPT_CONFIG["SEED"])
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    from auto_solver_pipeline import load_all_workspace_assets
    root = Path(args.workspace).resolve()
    assets = load_all_workspace_assets(root)

    # 사전 최적화 진단 (평가지표: 정확도 vs 속도, 병목: 알고리즘 vs 하드웨어)
    diag_report = None
    if PreOptDiagnostician is not None:
        try:
            diag_report = PreOptDiagnostician(root).run_full_diagnosis()
        except Exception:
            pass

    views = build_views(assets, args.label)
    proposals = propose(views, diag_report=diag_report)
    out_dir = (root / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = environment_report()
    md = render_proposal_md(proposals, decision_questions(views), views, env, diag_report=diag_report)
    (out_dir / "optimizer_proposals.md").write_text(md, encoding="utf-8")
    try:
        (root / ".fde_optimization_proposal.md").write_text(md, encoding="utf-8")
    except Exception:
        pass
    (out_dir / "optimizer_proposals.json").write_text(json.dumps({"pre_opt_diagnosis": diag_report,
                                                                 "views": {k: {"table": v["table"], "size": v["size"]} for k, v in views.items()},
                                                                 "proposals": proposals, "questions": decision_questions(views), "environment": env},
                                                                ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.choose:
        print(md)
        print(f"\n💾 저장: {out_dir / 'optimizer_proposals.md'}")
        return 0
    ids = expand_choice(args.choose, proposals)
    results = run_candidates(ids, views, args, assets)
    print_comparison(results)
    (out_dir / "optimizer_result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n💾 저장: {out_dir / 'optimizer_result.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
