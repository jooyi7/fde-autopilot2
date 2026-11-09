#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Solver 5: Semiconductor Value-Chain Ontology, 2-Layer Analogy Guardrail,
4-Step Value-Chain Storytelling & Role-Adaptive Curriculum Engine

"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Set, Optional


class CurriculumOntologySolver:
    # 핵심 반도체 공정별 2-Layer 설명(비유 + 공학적 팩트 한계 교정) 및 4단계 비즈니스 임팩트 온톨로지
    DOMAIN_PEDAGOGY_KB = {
        "PHOTO": {
            "analogy_layer": "필름 카메라로 빛을 쬐어 인화지에 밑그림을 축소 인화하는 과정에 비유할 수 있습니다.",
            "engineering_ground_truth_correction": (
                "[비유 한계 교정] 거시적 사진 인화와 달리 EUV(13.5nm 파장) 노광은 공기 및 렌즈에 빛이 흡수되므로 "
                "진공 상태에서 다층 박막 반사 거울(Bragg Reflector)을 사용하며, 회절 한계와 확률적 광자 산탄 노이즈(Stochastic Effect)를 제어해야 합니다."
            ),
            "four_step_storyline": {
                "step1_physical_limit": "미세화 한계로 기존 ArF 액침(193nm) 멀티패터닝(SAQP) 적용 시 공정 스텝 수 폭증 및 정렬 오차(Overlay) 누적",
                "step2_tech_breakthrough": "EUV 단일 노광 및 High-NA 도입, 전공정 스트레스 Feed-forward APC 정밀 보정",
                "step3_process_metric_gain": "마스크 층수 절감으로 TAT 20% 단축 및 층간 Overlay M3S 1.5nm 이하 수율 안정화",
                "step4_business_financial_impact": "1b/1c 선단 DRAM 원가 경쟁력 확보 및 HBM 베이스/코어 다이 고수율 양산으로 영업이익률 극대화",
            },
        },
        "PKG_HBM": {
            "analogy_layer": "여러 층의 아파트(DRAM 칩)를 수직으로 쌓고 층간 고속 엘리베이터(TSV)를 뚫어 한 번에 연결하는 건축에 비유됩니다.",
            "engineering_ground_truth_correction": (
                "[비유 한계 교정] 콘크리트 건물과 달리 수십 마이크로미터 두께로 갈아낸 웨이퍼(Thinning)는 열팽창계수(CTE) 차이로 인해 "
                "심각한 휨(Warpage)이 발생하며, 범프 간 미세 피치 접합 시 보이드(Void)와 열 방출 저항을 제어하는 MR-MUF 공학이 핵심입니다."
            ),
            "four_step_storyline": {
                "step1_physical_limit": "12단 이상 고적층 시 기존 TC-NCF 필름 방식은 열 방출 저하 및 가압 시 칩 휨 현상으로 수율 급락",
                "step2_tech_breakthrough": "SK하이닉스 독자 Advanced MR-MUF(액체 에폭시 보호재 주입 및 일괄 리플로우) 및 신규 방열 필러 적용",
                "step3_process_metric_gain": "열전도율 약 2배 향상, 범프 접합 공정 쓰루풋(Throughput) 3배 개선 및 보이드 결함 원천 차단",
                "step4_business_financial_impact": "글로벌 빅테크 AI 가속기향 HBM3E 시장 지배력 독점 및 전사 Blended ASP/수익성 견인",
            },
        },
        "ETCH_DEP": {
            "analogy_layer": "원하는 부분만 정교하게 조각칼로 파내고(식각), 얇은 페인트 막을 균일하게 코팅(증착)하는 작업과 유사합니다.",
            "engineering_ground_truth_correction": (
                "[비유 한계 교정] 물리적 칼질이 아니라 플라즈마 라디칼/이온의 이방성(Anisotropic) 화학·물리 반응과 원자층 단위(ALD) 표면 자기제한 반응을 이용해 "
                "수십 대 일의 고종횡비(HARC) 채널을 휘어짐(Bowing) 없이 뚫고 채워야 합니다."
            ),
            "four_step_storyline": {
                "step1_physical_limit": "300단 이상 3D NAND 및 고종횡비 DRAM 커패시터 식각 시 하부 미개구(Not-Open) 및 웨이퍼 스트레스 유발",
                "step2_tech_breakthrough": "극저온(Cryogenic) 식각 기술 및 불순물 제로(ppt급) 고순도 프리커서 ALD 균일 증착 적용",
                "step3_process_metric_gain": "식각 속도 2배 향상 및 웨이퍼 전면적 박막 두께 산포(Uniformity) 1% 이내 달성",
                "step4_business_financial_impact": "고용량 기업용 eSSD(QLC) 원가 절감 및 후속 포토 공정의 Overlay 리워크 비용 절감",
            },
        },
    }

    ROLE_SOCRATIC_QUIZZES = {
        "PROCUREMENT_MATERIAL": "만약 공급사가 원가 절감을 위해 하위 원료 정제 필터를 임의 변경(4M 미신고)하여 미량 금속 불순물이 2ppb 증가한다면, 해당 공정 수율과 당사 구매 계약 페널티 조항에 어떤 리스크가 발생하겠습니까?",
        "FINANCE_STRATEGY": "선단 공정 전환 및 HBM 적층 확대로 인해 웨이퍼당 Bit 생산량이 줄어드는 다이 페널티(Die Penalty)가 발생할 때, 이를 상쇄하기 위한 최소 판가(ASP) 프리미엄과 CAPEX ROIC 기준은 어떻게 설정해야 하겠습니까?",
        "FAB_ENGINEER": "전공정 박막 증착의 두께 비대칭이 후속 노광 공정의 웨이퍼 엣지 Overlay 잔차를 유발할 때, 단순 포토 리워크 대신 어떤 Feed-forward APC 파라미터를 연동해야 라인 스톱을 막을 수 있겠습니까?",
        "GENERAL": "이 단위 공정의 물리적 병목 해결이 SK하이닉스 최종 제품(HBM3E/DDR5)의 고객사 TCO(총소유비용) 절감과 당사 영업이익률에 어떻게 기여하는지 4단계로 설명해 보십시오.",
    }

    @classmethod
    def enrich_module_pedagogy(cls, mod: Dict[str, Any], learner_role: str = "GENERAL", learner_level: int = 1) -> Dict[str, Any]:
        stage_upper = str(mod.get("stage", "PHOTO")).upper()
        if "PKG" in stage_upper or "HBM" in stage_upper or "MUF" in stage_upper:
            kb = cls.DOMAIN_PEDAGOGY_KB["PKG_HBM"]
        elif "ETCH" in stage_upper or "DEP" in stage_upper or "CMP" in stage_upper:
            kb = cls.DOMAIN_PEDAGOGY_KB["ETCH_DEP"]
        else:
            kb = cls.DOMAIN_PEDAGOGY_KB["PHOTO"]

        role_key = learner_role.upper() if learner_role.upper() in cls.ROLE_SOCRATIC_QUIZZES else "GENERAL"
        abstraction_guide = (
            "Lv.1 입문자용: 수식 최소화, 2-Layer 비유+팩트 교정 및 재무 연결 중심"
            if learner_level <= 1
            else ("Lv.2 실무자용: 공정 파라미터(Cpk, M3S, Yield)와 밸류체인 병목 중심" if learner_level == 2 else "Lv.3 전문가용: 고차 수리 모델, 4M 변경 FMEA 및 ROIC 정량 시뮬레이션 중심")
        )

        return {
            **mod,
            "abstraction_scaffolding": abstraction_guide,
            "two_layer_explanation": {
                "layer1_intuitive_analogy": kb["analogy_layer"],
                "layer2_engineering_fact_guardrail": kb["engineering_ground_truth_correction"],
            },
            "four_step_value_chain_bridge": kb["four_step_storyline"],
            "role_specific_socratic_quiz": cls.ROLE_SOCRATIC_QUIZZES[role_key],
        }

    @classmethod
    def analyze_and_schedule(
        cls,
        modules: List[Dict[str, Any]],
        learner_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        learner_profile = learner_profile or {}
        completed: Set[str] = set(learner_profile.get("completed_ids", []))
        targets: Set[str] = set(learner_profile.get("target_ids", [m["id"] for m in modules if "id" in m]))
        max_hours = float(learner_profile.get("max_hours", 9999.0))
        learner_role = str(learner_profile.get("role", "GENERAL"))
        learner_level = int(learner_profile.get("level", 1))

        mod_map = {m["id"]: m for m in (modules or []) if isinstance(m, dict) and "id" in m}

        # 1. Backtrack from target_ids to find all required prerequisite nodes
        required_nodes: Set[str] = set()
        stack = list(targets)
        while stack:
            curr = stack.pop()
            if curr in completed or curr not in mod_map:
                continue
            if curr not in required_nodes:
                required_nodes.add(curr)
                for pre in mod_map[curr].get("prereqs", []):
                    if pre not in completed and pre in mod_map:
                        stack.append(pre)

        # 2. Kahn's Algorithm for Topological Sort on required subgraph
        in_degree = {nid: 0 for nid in required_nodes}
        adj = {nid: [] for nid in required_nodes}

        for nid in required_nodes:
            for pre in mod_map[nid].get("prereqs", []):
                if pre in required_nodes:
                    adj[pre].append(nid)
                    in_degree[nid] += 1

        queue = sorted(
            [nid for nid, deg in in_degree.items() if deg == 0],
            key=lambda x: (mod_map[x].get("level", 1), x),
        )
        ordered_ids = []

        while queue:
            curr = queue.pop(0)
            ordered_ids.append(curr)
            for nxt in adj[curr]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
                    queue.sort(key=lambda x: (mod_map[x].get("level", 1), x))

        cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
        cum_hours = 0.0
        scheduled_modules = []
        deferred_modules = []

        for nid in ordered_ids:
            m = cls.enrich_module_pedagogy(mod_map[nid], learner_role=learner_role, learner_level=learner_level)
            h = float(m.get("hours", 0.0))
            if cum_hours + h <= max_hours:
                cum_hours += h
                scheduled_modules.append(m)
            else:
                deferred_modules.append(m)

        status = "VIOLATION" if cycle_nodes else ("WARNING" if deferred_modules else "NORMAL")
        rule_id = "EDU-RULE-CYCLE-ERR" if cycle_nodes else ("EDU-RULE-TIME-CAP-WARN" if deferred_modules else "EDU-RULE-VALID-DAG")

        return {
            "persona_id": "skhynix-value-chain-educator-persona",
            "status": status,
            "ruleId": rule_id,
            "learner_role": learner_role,
            "learner_level": learner_level,
            "is_valid_dag": len(cycle_nodes) == 0,
            "cycle_detected_ids": cycle_nodes,
            "total_scheduled_modules": len(scheduled_modules),
            "total_scheduled_hours": round(cum_hours, 2),
            "budget_max_hours": max_hours,
            "learning_path": scheduled_modules,
            "deferred_due_to_time_cap": deferred_modules,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = CurriculumOntologySolver.analyze_and_schedule(
            modules=payload.get("modules", []),
            learner_profile=payload.get("learner_profile", {}),
        )
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
