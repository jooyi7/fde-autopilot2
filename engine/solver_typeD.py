#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
[Solver Type D] Workflow State Machine, Equipment RUL & PM Schedule Optimizer
- 대상 매트릭스 유형:
  * #4 운영 백오피스 / 관리자 어드민 (상태 전이 검증, 승인/반려 우선순위)
  * #6 워크플로우 / 단계별 파이프라인 (단계별 유효성 검사, Draft->Review->Approved 강제)
  * #11 설비 유지보수(PM) & 잔여수명(RUL) 관리 (가동 시간 한계 도달 계산, 긴급 점검 D-Day 산출)

[출제 가능한 최적화(Optimization) 문제 및 구현 방식]
  Type D에서는 설비별 마모도/잔여수명과 정비창(Maintenance Slot) 제약이 주어졌을 때
  "언제 예방정비(PM)를 수행해야 라인 셧다운 손실과 정비 비용의 합이 최소가 되는가"가 출제될 수 있음:
  1. Optimal Preventive Maintenance Interval (Weibull Renewal Reward Cost Rate Minimization):
     - 예방정비 비용(C_pm)과 돌발 고장 시 셧다운 비용(C_cm >> C_pm), 와이블 형상모수(beta), 척도모수(eta)를 바탕으로
       단위 가동시간당 기대 비용 g(T) = [C_pm * R(T) + C_cm * (1 - R(T))] / integral_0^T R(u) du 를 최소화하는 최적 교체 주기 T* 산출.
  2. Maintenance Bay Slot Assignment Optimization:
     - 동시에 여러 설비가 PM 시점에 도달했을 때, 시간당 다운타임 손실이 큰 병목 설비부터 정비 슬롯을 우선 배정.
  3. Workflow Critical Path Method (CPM):
     - DAG 파이프라인에서 전체 리드타임을 결정하는 병목 경로(Critical Path)와 Slack Time 0인 태스크 식별.
================================================================================
"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple


class TypeDSolver:
    ALLOWED_TRANSITIONS = {
        "DRAFT": {"REVIEW", "CANCELLED"},
        "REVIEW": {"APPROVED", "REJECTED", "DRAFT"},
        "APPROVED": {"EXECUTED", "ARCHIVED"},
        "REJECTED": {"DRAFT", "ARCHIVED"},
        "EXECUTED": {"ARCHIVED"},
    }

    # -------------------------------------------------------------------------
    # 1. [#11 설비 PM & RUL] Weibull 기반 최적 PM 교체 주기(T*) 및 정비 슬롯 스케줄링 최적화
    # -------------------------------------------------------------------------
    @staticmethod
    def optimize_pm_and_rul(
        equipments: List[Dict[str, Any]],
        available_pm_slots: int = 2,
    ) -> Dict[str, Any]:
        evaluated = []
        for idx, eq in enumerate(equipments or []):
            if not isinstance(eq, dict):
                continue
            eq_id = str(eq.get("equip_id", f"EQ-{idx+1:02d}"))
            usage_hrs = float(eq.get("current_usage_hours", 400.0))
            max_spec_hrs = float(eq.get("max_lifetime_hours", 500.0))
            wear_pct = float(eq.get("wear_rate_pct", (usage_hrs / max(max_spec_hrs, 1.0)) * 100.0))
            daily_run_hrs = max(1.0, float(eq.get("daily_operating_hours", 20.0)))

            # Weibull 파라미터 (형상모수 beta > 1 마모 고장, 척도모수 eta)
            beta = float(eq.get("weibull_beta", 2.5))
            eta = float(eq.get("weibull_eta_hours", max_spec_hrs))
            cost_pm = float(eq.get("pm_cost", 100.0))
            cost_cm = float(eq.get("unplanned_shutdown_cost", 800.0))

            # [최적화] 수치 적분(Simpson/Trapezoidal) 기반 최적 PM 주기 T* 탐색
            best_t = max_spec_hrs
            min_cost_rate = float("inf")
            integral_r = 0.0
            dt = max(5.0, eta / 100.0)
            t = dt
            while t <= eta * 1.5:
                r_t = math.exp(-((t / max(eta, 1.0)) ** beta))
                integral_r += r_t * dt
                expected_cost = cost_pm * r_t + cost_cm * (1.0 - r_t)
                cost_rate = expected_cost / max(integral_r, 1e-6)
                if cost_rate < min_cost_rate:
                    min_cost_rate = cost_rate
                    best_t = t
                t += dt

            effective_limit = min(max_spec_hrs, best_t)
            rem_hours = max(0.0, effective_limit - usage_hrs)
            d_day = math.floor(rem_hours / daily_run_hrs)

            # 현재 시점 고장 위험도 (Failure Probability within next 24h)
            r_now = math.exp(-((usage_hrs / max(eta, 1.0)) ** beta))
            r_next = math.exp(-(((usage_hrs + daily_run_hrs) / max(eta, 1.0)) ** beta))
            cond_fail_prob = (r_now - r_next) / max(r_now, 1e-6)
            expected_delay_risk_cost = cond_fail_prob * cost_cm

            evaluated.append({
                "equip_id": eq_id,
                "current_usage_hours": round(usage_hrs, 1),
                "spec_limit_hours": round(max_spec_hrs, 1),
                "weibull_optimal_pm_interval_hours": round(best_t, 1),
                "minimized_hourly_cost_rate": round(min_cost_rate, 4),
                "wear_rate_pct": round(wear_pct, 2),
                "remaining_useful_life_hours": round(rem_hours, 1),
                "urgent_pm_d_day": int(d_day),
                "next_24h_failure_prob_pct": round(cond_fail_prob * 100.0, 2),
                "delay_risk_expected_cost": round(expected_delay_risk_cost, 2),
                "status": "URGENT_PM_REQUIRED" if (d_day <= 1 or wear_pct >= 90.0) else (
                    "PM_WARNING" if (d_day <= 3 or wear_pct >= 80.0) else "HEALTHY"
                ),
            })

        # [최적화] 정비 지연 시 기대 손실 비용(delay_risk_expected_cost)이 가장 큰 순서로 정비창 슬롯 우선 배정
        ranked = sorted(evaluated, key=lambda x: x["delay_risk_expected_cost"], reverse=True)
        assigned_now = [r["equip_id"] for r in ranked[: max(1, int(available_pm_slots))]]
        deferred = [r["equip_id"] for r in ranked[max(1, int(available_pm_slots)) :]]

        return {
            "equipment_count": len(evaluated),
            "urgent_pm_count": sum(1 for e in evaluated if e["status"] == "URGENT_PM_REQUIRED"),
            "equipment_health_list": evaluated,
            "pm_slot_schedule_optimization": {
                "optimization_method": "WEIBULL_RENEWAL_REWARD_AND_RISK_PRIORITY_DISPATCH",
                "available_pm_slots": available_pm_slots,
                "immediate_slot_assigned_equips": assigned_now,
                "next_shift_queued_equips": deferred,
            },
        }

    # -------------------------------------------------------------------------
    # 2. [#4, #6 상태 머신 & 워크플로우 파이프라인] 상태 전이 검증 및 Critical Path 분석
    # -------------------------------------------------------------------------
    @classmethod
    def validate_workflow_and_cpm(
        cls,
        transitions: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        illegal_transitions = []
        for idx, tr in enumerate(transitions or []):
            cur = str(tr.get("from_state", "DRAFT")).upper()
            nxt = str(tr.get("to_state", "REVIEW")).upper()
            has_required_fields = bool(tr.get("has_required_fields", True))
            allowed = cls.ALLOWED_TRANSITIONS.get(cur, set())
            if nxt not in allowed or not has_required_fields:
                illegal_transitions.append({
                    "index": idx,
                    "item_id": str(tr.get("item_id", f"ITEM-{idx+1:02d}")),
                    "from_state": cur,
                    "to_state": nxt,
                    "reason": "MISSING_REQUIRED_FIELDS" if not has_required_fields else f"INVALID_STATE_JUMP_{cur}_TO_{nxt}",
                })

        # CPM (Critical Path Method) 계산
        earliest_finish: Dict[str, float] = {}
        task_map: Dict[str, Dict[str, Any]] = {}
        for t in tasks or []:
            tid = str(t.get("task_id", "T1"))
            dur = float(t.get("duration_hours", 1.0))
            deps = [str(d) for d in (t.get("depends_on") or [])]
            es = max([earliest_finish.get(d, 0.0) for d in deps] + [0.0])
            ef = es + dur
            earliest_finish[tid] = ef
            task_map[tid] = {"task_id": tid, "duration_hours": dur, "es": es, "ef": ef, "depends_on": deps}

        makespan = max(earliest_finish.values()) if earliest_finish else 0.0
        critical_path = [tid for tid, info in task_map.items() if abs(info["ef"] - makespan) < 1e-6 or info["duration_hours"] >= makespan * 0.4]

        return {
            "illegal_transition_count": len(illegal_transitions),
            "illegal_transitions": illegal_transitions,
            "cpm_schedule_analysis": {
                "total_makespan_hours": round(makespan, 2),
                "critical_bottleneck_tasks": critical_path,
                "task_schedule": list(task_map.values()),
            },
        }

    @classmethod
    def auto_shape_payload(cls, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """payload 내부의 'records', 'equipments', 'tasks', 'transitions' 등에서 설비 RUL 및 워크플로우 데이터를 자동 분리/추출"""
        equips = list(payload.get("equipments") or [])
        tasks = list(payload.get("tasks") or [])
        transitions = list(payload.get("transitions") or [])

        records = payload.get("records") or payload.get("data") or payload.get("rows") or []
        if isinstance(records, list) and records:
            first_row = records[0] if isinstance(records[0], dict) else {}
            cols_lower = {str(k).strip().lower() for k in first_row.keys()}

            if not equips and any(k in cols_lower for k in ("equip_id", "equip", "equipment", "usage_hours", "wear_rate_pct", "operating_hours")):
                for idx, r in enumerate(records):
                    if not isinstance(r, dict):
                        continue
                    lmap = {str(k).strip().lower(): v for k, v in r.items()}
                    eid = lmap.get("equip_id") or lmap.get("equip") or lmap.get("equipment") or f"EQ-{idx+1:02d}"
                    u_hrs = float(lmap.get("current_usage_hours") or lmap.get("usage_hours") or lmap.get("operating_hours") or 400.0)
                    m_hrs = float(lmap.get("max_lifetime_hours") or lmap.get("lifetime_hours") or lmap.get("spec_limit_hours") or 500.0)
                    beta = float(lmap.get("weibull_beta") or lmap.get("beta") or 2.5)
                    cost_pm = float(lmap.get("pm_cost") or lmap.get("cost_pm") or 100.0)
                    cost_cm = float(lmap.get("unplanned_shutdown_cost") or lmap.get("cost_cm") or 800.0)
                    equips.append({
                        "equip_id": str(eid),
                        "current_usage_hours": u_hrs,
                        "max_lifetime_hours": m_hrs,
                        "weibull_beta": beta,
                        "pm_cost": cost_pm,
                        "unplanned_shutdown_cost": cost_cm,
                    })

            if not tasks and any(k in cols_lower for k in ("task_id", "task", "duration_hours", "duration", "depends_on", "prereq")):
                for idx, r in enumerate(records):
                    if not isinstance(r, dict):
                        continue
                    lmap = {str(k).strip().lower(): v for k, v in r.items()}
                    tid = lmap.get("task_id") or lmap.get("task") or f"T-{idx+1:02d}"
                    dur = float(lmap.get("duration_hours") or lmap.get("duration") or 1.0)
                    deps_raw = lmap.get("depends_on") or lmap.get("prereqs") or []
                    if isinstance(deps_raw, str):
                        deps = [x.strip() for x in deps_raw.split(",") if x.strip()]
                    elif isinstance(deps_raw, list):
                        deps = [str(x) for x in deps_raw]
                    else:
                        deps = []
                    tasks.append({"task_id": str(tid), "duration_hours": dur, "depends_on": deps})

        return equips, tasks, transitions

    @classmethod
    def solve(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        equips, tasks, transitions = cls.auto_shape_payload(payload)
        pm_res = cls.optimize_pm_and_rul(
            equipments=equips,
            available_pm_slots=int(payload.get("available_pm_slots", 2)),
        )
        wf_res = cls.validate_workflow_and_cpm(
            transitions=transitions,
            tasks=tasks,
        )
        has_viol = pm_res["urgent_pm_count"] > 0 or wf_res["illegal_transition_count"] > 0
        return {
            "domain": "TYPE_D_WORKFLOW_AND_PM_SCHEDULE",
            "status": "VIOLATION" if has_viol else "NORMAL",
            "ruleId": "RULE-TYPED-PM-OR-STATE-VIOLATION" if has_viol else "RULE-TYPED-PASS",
            "pm_and_rul_optimization": pm_res,
            "workflow_validation": wf_res,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        inp = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = TypeDSolver.solve(inp)
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")