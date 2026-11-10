#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
[Solver Type A] Text Rule Engine, Local RAG & Alarm Troubleshooting Optimizer
- 대상 매트릭스 유형:
  * #1 대화형 코칭 / 인터뷰 / 상담 (금기어/규정 위반 탐지, 감점 계산)
  * #3 문서 검색 / 규정 Q&A (RAG) (키워드 매칭, 권한 필터링, 참조 페이지 인덱싱)
  * #12 장비 알람 트러블슈팅 어시스턴트 (에러 코드 매칭, 심각도 분류, 조치 가이드)

[출제 가능한 최적화(Optimization) 문제 및 구현 방식]
  Type A에서는 텍스트/로그 매칭 이후 "어떤 근거 문서를 선택할 것인가" 또는
  "제한된 교대 시간 내에 어떤 트러블슈팅 조치를 우선 수행할 것인가"를 최적화하는 문제가 출제될 수 있음:
  1. Submodular Maximum Coverage (최대 커버리지 문서 조합 최적화):
     - 중복되는 내용을 가진 여러 매뉴얼/규정 청크 중 K개를 골라 질의 키워드 커버리지를 극대화 (Greedy Submodular Maximization, (1 - 1/e) 근사 보장).
  2. Time-Constrained Troubleshooting Action Knapsack (시간 제약 하 리스크 감소 최대화):
     - 엔지니어의 가용 조치 시간(예: 30분) 내에 복구 확률(리스크 감소량) 합을 극대화하는 체크리스트 조합 도출 (0-1 Knapsack Dynamic Programming & 가성비 Greedy).
  3. Minimum Penalty Script Rewriting (규정 위반 교정 우선순위 최적화):
     - 감점 폭이 큰 금기어/필수 누락 키워드부터 최소한의 수정으로 목표 점수(Pass Score)를 달성하는 최적 교정 순서 산출.
================================================================================
"""

import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    cleaned = re.sub(r"[^0-9a-zA-Z가-힣_+-]", " ", str(text).lower())
    return [tok for tok in cleaned.split() if len(tok) >= 2]


class TypeASolver:
    FIELD_ALIASES = {
        "text": ["text", "transcript", "answer", "query", "message", "content", "input_text", "log_message"],
        "alarm_code": ["alarm_code", "error_code", "code", "err_id", "alarm_id", "fault_code"],
        "user_role": ["user_role", "role", "clearance", "permission", "access_level", "dept"],
        "time_budget_mins": ["time_budget_mins", "budget_mins", "max_time", "available_mins", "shift_remaining_mins"],
    }

    @classmethod
    def _get_val(cls, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        if key in data and data[key] is not None and data[key] != "":
            return data[key]
        aliases = cls.FIELD_ALIASES.get(key, [key])
        lower_map = {str(k).strip().lower(): v for k, v in data.items()}
        for a in aliases:
            if a.lower() in lower_map and lower_map[a.lower()] is not None and lower_map[a.lower()] != "":
                return lower_map[a.lower()]
        return default

    # -------------------------------------------------------------------------
    # 1. [#1 인터뷰/코칭] 금기어/규정 위반 탐지 및 최소 수정 패스 최적화
    # -------------------------------------------------------------------------
    @staticmethod
    def evaluate_coaching_rules(
        text: str,
        forbidden_rules: List[Dict[str, Any]],
        required_keywords: List[Dict[str, Any]],
        base_score: float = 100.0,
        pass_threshold: float = 80.0,
    ) -> Dict[str, Any]:
        violations = []
        missing_requirements = []
        current_score = float(base_score)

        for idx, rule in enumerate(forbidden_rules or []):
            pattern = str(rule.get("pattern", "")).strip()
            if not pattern:
                continue
            penalty = float(rule.get("penalty", 15.0))
            rule_id = str(rule.get("rule_id", f"FORBID-{idx+1:02d}"))
            matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
            if matches:
                total_deduct = penalty * len(matches)
                current_score -= total_deduct
                violations.append({
                    "rule_id": rule_id,
                    "pattern": pattern,
                    "match_count": len(matches),
                    "matched_phrases": list({m.group(0) for m in matches}),
                    "deducted_points": round(total_deduct, 2),
                    "category": str(rule.get("category", "POLICY_VIOLATION")),
                    "fix_suggestion": str(rule.get("replacement", "해당 표현 삭제 또는 중립 표현으로 대체")),
                })

        for idx, req in enumerate(required_keywords or []):
            kw = str(req.get("keyword", "")).strip()
            if not kw:
                continue
            penalty = float(req.get("penalty_if_missing", 10.0))
            req_id = str(req.get("req_id", f"REQ-{idx+1:02d}"))
            if not re.search(re.escape(kw), text, flags=re.IGNORECASE):
                current_score -= penalty
                missing_requirements.append({
                    "req_id": req_id,
                    "missing_keyword": kw,
                    "deducted_points": round(penalty, 2),
                    "fix_suggestion": f"필수 키워드 '{kw}' 관련 근거 문장 추가",
                })

        final_score = max(0.0, round(current_score, 2))
        deficit = max(0.0, round(pass_threshold - final_score, 2))

        # [최적화] 최소 횟수의 교정으로 합격선(pass_threshold)을 넘기는 Greedy Minimal-Edit 선택
        candidates = []
        for v in violations:
            candidates.append({
                "action_type": "REMOVE_FORBIDDEN",
                "target_id": v["rule_id"],
                "gain_points": v["deducted_points"],
                "instruction": v["fix_suggestion"],
            })
        for m in missing_requirements:
            candidates.append({
                "action_type": "ADD_REQUIRED",
                "target_id": m["req_id"],
                "gain_points": m["deducted_points"],
                "instruction": m["fix_suggestion"],
            })
        candidates.sort(key=lambda x: x["gain_points"], reverse=True)

        minimal_fix_plan = []
        recovered = 0.0
        for c in candidates:
            if recovered >= deficit and deficit > 0:
                break
            if deficit > 0:
                minimal_fix_plan.append(c)
                recovered += c["gain_points"]

        return {
            "final_score": final_score,
            "pass_threshold": pass_threshold,
            "is_passed": final_score >= pass_threshold,
            "violation_count": len(violations),
            "missing_requirement_count": len(missing_requirements),
            "violations": violations,
            "missing_requirements": missing_requirements,
            "minimal_edit_optimization": {
                "points_needed_to_pass": deficit,
                "points_recovered_by_plan": round(recovered, 2),
                "projected_score_after_fix": min(100.0, round(final_score + recovered, 2)),
                "required_edit_count": len(minimal_fix_plan),
                "priority_fix_actions": minimal_fix_plan,
            },
        }

    # -------------------------------------------------------------------------
    # 2. [#3 규정 Q&A / RAG] BM25 스코어링 + Submodular Max-Coverage 문서 선택 최적화
    # -------------------------------------------------------------------------
    @staticmethod
    def retrieve_and_optimize_rag(
        query: str,
        documents: List[Dict[str, Any]],
        user_role: str = "GENERAL",
        top_k: int = 3,
    ) -> Dict[str, Any]:
        role_hierarchy = {"PUBLIC": 0, "GENERAL": 1, "ENGINEER": 2, "MANAGER": 3, "ADMIN": 4}
        user_level = role_hierarchy.get(str(user_role).upper(), 1)

        q_tokens = _tokenize(query)
        q_set: Set[str] = set(q_tokens)

        allowed_docs = []
        blocked_doc_count = 0
        for idx, doc in enumerate(documents or []):
            if not isinstance(doc, dict):
                continue
            req_role = str(doc.get("required_role", "GENERAL")).upper()
            if role_hierarchy.get(req_role, 1) > user_level:
                blocked_doc_count += 1
                continue
            allowed_docs.append((idx, doc))

        if not allowed_docs or not q_tokens:
            return {
                "authorized_doc_count": len(allowed_docs),
                "blocked_by_permission_count": blocked_doc_count,
                "selected_citations": [],
                "query_coverage_pct": 0.0,
            }

        # BM25 계산 준비
        N = len(allowed_docs)
        doc_tokens_list: List[List[str]] = []
        df: Dict[str, int] = {}
        for _, doc in allowed_docs:
            toks = _tokenize(f"{doc.get('title', '')} {doc.get('content', '')} {doc.get('tags', '')}")
            doc_tokens_list.append(toks)
            for t in set(toks):
                df[t] = df.get(t, 0) + 1

        avgdl = sum(len(t) for t in doc_tokens_list) / max(N, 1)
        k1, b = 1.5, 0.75

        scored_docs = []
        for i, (orig_idx, doc) in enumerate(allowed_docs):
            toks = doc_tokens_list[i]
            dl = len(toks)
            tf_map: Dict[str, int] = {}
            for t in toks:
                tf_map[t] = tf_map.get(t, 0) + 1

            bm25 = 0.0
            matched_q_terms = set()
            for qt in q_set:
                tf = tf_map.get(qt, 0)
                if tf > 0:
                    matched_q_terms.add(qt)
                    n_qt = df.get(qt, 0)
                    idf = math.log(1.0 + (N - n_qt + 0.5) / (n_qt + 0.5))
                    bm25 += idf * ((tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (dl / max(avgdl, 1.0)))))

            scored_docs.append({
                "doc_id": str(doc.get("doc_id", f"DOC-{orig_idx+1:03d}")),
                "title": str(doc.get("title", "Untitled")),
                "page": int(doc.get("page", 1)),
                "bm25_score": round(bm25, 4),
                "matched_terms": matched_q_terms,
                "snippet": str(doc.get("content", ""))[:180],
            })

        # [최적화] Submodular Maximum Coverage Greedy Selection:
        # 단순히 BM25 상위 K개를 뽑으면 동일한 내용의 중복 문서가 뽑히므로,
        # 아직 커버되지 않은 질의 키워드를 가장 많이 커버하면서 BM25가 높은 문서를 순차 선택
        selected = []
        covered_terms: Set[str] = set()
        remaining = list(scored_docs)

        for _ in range(min(top_k, len(remaining))):
            best_idx = -1
            best_marginal_gain = -1.0
            for idx, cand in enumerate(remaining):
                new_terms = len(cand["matched_terms"] - covered_terms)
                marginal_score = new_terms * 2.0 + cand["bm25_score"]
                if marginal_score > best_marginal_gain:
                    best_marginal_gain = marginal_score
                    best_idx = idx
            if best_idx == -1 or best_marginal_gain <= 0.0:
                break
            chosen = remaining.pop(best_idx)
            covered_terms |= chosen["matched_terms"]
            selected.append({
                "doc_id": chosen["doc_id"],
                "title": chosen["title"],
                "page": chosen["page"],
                "bm25_score": chosen["bm25_score"],
                "matched_keywords": sorted(list(chosen["matched_terms"])),
                "snippet": chosen["snippet"],
            })

        coverage_pct = (len(covered_terms) / max(len(q_set), 1)) * 100.0
        return {
            "authorized_doc_count": len(allowed_docs),
            "blocked_by_permission_count": blocked_doc_count,
            "optimization_method": "SUBMODULAR_MAX_COVERAGE_BM25",
            "query_coverage_pct": round(coverage_pct, 2),
            "selected_citations": selected,
        }

    # -------------------------------------------------------------------------
    # 3. [#12 장비 알람 트러블슈팅] 에러 매칭 & 시간 제약 하 조치(Action) 배낭 최적화
    # -------------------------------------------------------------------------
    @staticmethod
    def optimize_alarm_troubleshooting(
        alarm_code: str,
        alarm_catalog: List[Dict[str, Any]],
        shift_logs: List[Dict[str, Any]],
        time_budget_mins: float = 30.0,
    ) -> Dict[str, Any]:
        code_norm = str(alarm_code or "").strip().upper()
        matched_spec = None
        for item in alarm_catalog or []:
            if str(item.get("alarm_code", "")).strip().upper() == code_norm:
                matched_spec = item
                break

        severity = str((matched_spec or {}).get("severity", "WARN")).upper()
        candidate_actions = list((matched_spec or {}).get("actions", []))

        # 과거 교대 근무자(Shift) 로그에서 동일 알람 성공 조치 추출 및 가중치 보정
        historical_hits = []
        for log in shift_logs or []:
            if str(log.get("alarm_code", "")).strip().upper() == code_norm:
                historical_hits.append(log)
                if not candidate_actions and log.get("action_taken"):
                    candidate_actions.append({
                        "action_id": str(log.get("log_id", "ACT-HIST")),
                        "description": str(log.get("action_taken")),
                        "est_mins": float(log.get("duration_mins", 10.0)),
                        "risk_reduction_score": float(log.get("success_rate", 0.7)) * 100.0,
                    })

        if not candidate_actions:
            candidate_actions = [
                {"action_id": "ACT-01", "description": "설비 인터록 상태 확인 및 센서 커넥터 재점검", "est_mins": 10, "risk_reduction_score": 45.0},
                {"action_id": "ACT-02", "description": "챔버 퍼지(Purge) 사이클 실행 및 진공 게이지 영점 조정", "est_mins": 15, "risk_reduction_score": 60.0},
                {"action_id": "ACT-03", "description": "소모성 파츠(O-Ring/Valve) 전면 교체", "est_mins": 40, "risk_reduction_score": 90.0},
            ]

        # [최적화] 0-1 Knapsack DP: 가용 시간(time_budget_mins) 내 리스크 감소 점수 합 최대화
        B = max(1, int(round(time_budget_mins)))
        n = len(candidate_actions)
        dp = [[0.0] * (B + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            act = candidate_actions[i - 1]
            w = max(1, int(round(float(act.get("est_mins", 10.0)))))
            v = float(act.get("risk_reduction_score", 10.0))
            for t in range(B + 1):
                dp[i][t] = dp[i - 1][t]
                if t >= w and dp[i - 1][t - w] + v > dp[i][t]:
                    dp[i][t] = dp[i - 1][t - w] + v

        # 역추적(Backtracking)으로 최적 조치 집합 추출
        chosen_actions = []
        rem_t = B
        for i in range(n, 0, -1):
            if abs(dp[i][rem_t] - dp[i - 1][rem_t]) > 1e-6:
                act = candidate_actions[i - 1]
                w = max(1, int(round(float(act.get("est_mins", 10.0)))))
                chosen_actions.append({
                    "action_id": str(act.get("action_id", f"ACT-{i:02d}")),
                    "description": str(act.get("description", "")),
                    "est_mins": w,
                    "risk_reduction_score": round(float(act.get("risk_reduction_score", 10.0)), 2),
                })
                rem_t -= w
        chosen_actions.reverse()

        total_time = sum(a["est_mins"] for a in chosen_actions)
        total_gain = sum(a["risk_reduction_score"] for a in chosen_actions)

        return {
            "alarm_code": code_norm or "UNKNOWN",
            "severity": severity,
            "equipment_interlock_required": severity in {"FATAL", "CRITICAL", "EMERGENCY"},
            "matched_historical_shift_logs": len(historical_hits),
            "knapsack_action_optimization": {
                "optimization_method": "0_1_KNAPSACK_DYNAMIC_PROGRAMMING",
                "optimality": "PROVEN_OPTIMAL",
                "time_budget_mins": B,
                "allocated_time_mins": total_time,
                "total_risk_reduction_score": round(total_gain, 2),
                "optimal_action_sequence": chosen_actions,
            },
        }

    @classmethod
    def auto_shape_payload(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """payload 내부의 'records' 등 임의의 테이블에서 알람 목록, 교대 로그, 질의 텍스트를 자동 보강"""
        shaped = dict(payload)
        records = payload.get("records") or payload.get("data") or payload.get("rows") or []
        if isinstance(records, list) and records:
            first_row = records[0] if isinstance(records[0], dict) else {}
            cols_lower = {str(k).strip().lower() for k in first_row.keys()}

            if not shaped.get("alarm_catalog") and any(k in cols_lower for k in ("alarm_code", "error_code", "code", "severity", "action")):
                catalog = []
                for idx, r in enumerate(records):
                    if not isinstance(r, dict):
                        continue
                    lmap = {str(k).strip().lower(): v for k, v in r.items()}
                    code = lmap.get("alarm_code") or lmap.get("error_code") or lmap.get("code") or f"ALM-{idx+1:02d}"
                    sev = lmap.get("severity") or lmap.get("level") or "WARN"
                    catalog.append({"alarm_code": str(code), "severity": str(sev)})
                shaped["alarm_catalog"] = catalog

            if not shaped.get("text") and any(k in cols_lower for k in ("text", "transcript", "query", "message", "inquiry", "log_message")):
                texts = []
                for r in records[:5]:
                    if not isinstance(r, dict):
                        continue
                    lmap = {str(k).strip().lower(): v for k, v in r.items()}
                    t = lmap.get("text") or lmap.get("transcript") or lmap.get("query") or lmap.get("message")
                    if t:
                        texts.append(str(t))
                if texts:
                    shaped["text"] = " ".join(texts)

        return shaped

    @classmethod
    def solve(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        shaped = cls.auto_shape_payload(payload)
        text = str(cls._get_val(shaped, "text", "") or "")
        alarm_code = str(cls._get_val(shaped, "alarm_code", "") or "")
        user_role = str(cls._get_val(shaped, "user_role", "ENGINEER") or "ENGINEER")
        time_budget = float(cls._get_val(shaped, "time_budget_mins", 30.0) or 30.0)

        coaching_res = cls.evaluate_coaching_rules(
            text=text,
            forbidden_rules=shaped.get("forbidden_rules", []),
            required_keywords=shaped.get("required_keywords", []),
            base_score=float(shaped.get("base_score", 100.0)),
            pass_threshold=float(shaped.get("pass_threshold", 80.0)),
        )
        rag_res = cls.retrieve_and_optimize_rag(
            query=text or alarm_code,
            documents=shaped.get("documents", []),
            user_role=user_role,
            top_k=int(shaped.get("top_k", 3)),
        )
        alarm_res = cls.optimize_alarm_troubleshooting(
            alarm_code=alarm_code,
            alarm_catalog=shaped.get("alarm_catalog", []),
            shift_logs=shaped.get("shift_logs", []),
            time_budget_mins=time_budget,
        )

        is_violation = (not coaching_res["is_passed"]) or alarm_res["equipment_interlock_required"]
        status = "VIOLATION" if is_violation else ("WARNING" if coaching_res["violation_count"] > 0 else "NORMAL")

        return {
            "domain": "TYPE_A_TEXT_RAG_ALARM",
            "status": status,
            "ruleId": "RULE-TYPEA-INTERLOCK" if alarm_res["equipment_interlock_required"] else (
                "RULE-TYPEA-COACH-FAIL" if not coaching_res["is_passed"] else "RULE-TYPEA-PASS"
            ),
            "coaching_evaluation": coaching_res,
            "rag_retrieval": rag_res,
            "alarm_troubleshooting": alarm_res,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        inp = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = TypeASolver.solve(inp)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")