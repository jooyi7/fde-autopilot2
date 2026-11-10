#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - Cofa Environment, Persona DM Bot & Semantic Schema Deep Prober (cofa_probe.py v7.0)
실전 시험장(빈 폴더 Greenfield 또는 데이터셋 제공 폴더) 시작 직후 실행하여 다음 7가지를 100% 결정론적으로 자동 탐지합니다:
1) 환경변수 내장 LLM API 엔드포인트/키/권장 모델(Sol 6.1, Terra 5.6, Luna 6 등) 자동 감지 (보안 마스킹 적용)
2) 플랫폼 내장 전문가 봇(Persona DM ID: value-chain-business-persona, value-chain-educator-persona 등) 자동 탐지 및 맞춤형 심층 인터뷰 질문지 생성
3) 비정형 규정/SOP/어닝콜/교안 문서(.md, .txt) 내 수치 임계값(Spec Limit), 금지 구역, 조항 ID(Citation) 자동 추출 + 마크다운 표(Markdown Table) 자동 파싱
4) 데이터셋(CSV/TSV/JSON/JSONL/SQLite) 인코딩(UTF-8/UTF-8-SIG/CP949) 및 구분자 자동 감지
5) 반도체 5대 도메인 + 범용 현업 도메인 표준 스키마 퍼지 매칭
6) [NEW v7.0] 미출제(Unseen) 도메인 대비 9대 시맨틱 컬럼 역할 추론기 (Semantic Column Role Auto-Inferencer: ID, TIME, GROUP, COST, CAPACITY, DEMAND, QUALITY, RISK, RESTRICTION, TEXT)
7) [NEW v7.0] 다중 테이블 복합 키(Composite Key: company+quarter, vendor_id+lot_id 등) 및 Fact-First 스타 스키마 관계 자동 발견
"""

import argparse
import csv
import json
import os
import re
try:
    import sqlite3
except ImportError:
    sqlite3 = None
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "__pycache__",
    ".venv", "venv", "fde-autopilot", "fde-kit", ".fde_audit_cache", ".autopilot", "output", "public"
}

KNOWN_PERSONA_DM_BOTS = {
    "value-chain-business-persona": {
        "team": "경영전략팀 시장분석 (밸류체인 전략)",
        "domain": "VALUE_CHAIN_BIZ",
        "solver": "engine/solver_value_chain_biz.py",
        "aliases": ["value-chain-business-persona", "value-chain-business-bot", "value-chain-business-expert"],
        "dm_interview_script": [
            "[1차 DM - 병목 상한선 & 채찍효과] 안녕하세요 경영전략팀 담당자님! 전방 CSP 수요 변동 시 내부 Fab/EDS 양품 다이(KGHD) 생산량과 외부 TSMC CoWoS 패키징 할당량/베이스 다이 공급량 중 어느 쪽을 절대 출하 상한선(Ceiling)으로 적용해야 할까요? 미출하 재고(Stranded Die) 보유 손실 단가 기준도 있다면 알려주세요.",
            "[2차 DM - CAPEX ROIC & 컨틴전시] HBM3E/HBM4, DDR5, eSSD 간 설비투자(CAPEX) 배분 시 공정 전환 손실(Conversion Loss)과 고객사 LTA 의무 물량 하한선을 최우선 Hard Constraint로 둘까요? 또한 최소 WACC 허들 레이트(%)와 지정학 규제 시 우시/이천 Fab 물량 스왑 발동 기준을 확인 부탁드립니다.",
        ],
    },
    "value-chain-educator-persona": {
        "team": "반도체 산업교육 (밸류체인 & 공정 교육)",
        "domain": "CURRICULUM_EDU",
        "solver": "engine/solver_curriculum.py",
        "aliases": ["value-chain-educator-persona", "value-chain-educator-bot", "value-chain-educator-expert"],
        "dm_interview_script": [
            "[1차 DM - 선수과목 DAG & 시간 상한] 안녕하세요 교육 담당자님! 커리큘럼 편성 시 선수과목 순환 참조(Cycle)가 발견되면 즉시 VIOLATION으로 차단할까요? 또한 교육생의 가용 학습시간(max_hours) 초과 시 핵심 목표 과목(target_ids)의 필수 선수 체인(Critical Path)을 우선 보존하고 50% 마이크로러닝 압축 모드를 적용하는 기준이 맞는지 여쭙습니다.",
            "[2차 DM - 2-Layer 비유 교정 & 직무별 평가] 비전공/신입 교육생의 오개념 방지를 위해 [1단계 직관적 비유 + 2단계 공학적 물리 한계 교정(Fact Guardrail)]과 [물리적 한계 ➔ 공정 돌파 ➔ 수율/스펙 ➔ 재무 임팩트] 4단계 스토리라인을 모든 모듈의 필수 출력 포맷으로 고정할까요?",
        ],
    },
    "market-strategy-persona": {
        "team": "반도체 시장전략팀 (메모리 시장 및 경쟁사 실적 분석)",
        "domain": "MARKET_STRATEGY",
        "solver": "engine/solver_market.py",
        "aliases": ["market-strategy-persona", "market-strategy-bot", "market-strategy-expert"],
        "dm_interview_script": [
            "[1차 DM - 캘린더 분기 & NRV 환입 보정] 안녕하세요 시장전략팀 담당자님! 마이크론(8월 결산 FQ)과 당사/경쟁사(12월 결산 CQ) 비교 시 Calendarization 매핑 기준과, 재고자산평가손실 환입(NRV Reversal)을 제거한 Underlying OPM 산출 기준을 확인하고 싶습니다.",
            "[2차 DM - P×Q×Mix 착시 & 어닝콜 교차검증] 전사 Blended ASP는 상승했으나 범용(Legacy) 단가가 하락하는 'Mix 착시'나, 경쟁사 어닝콜 낙관 발언 대비 재고일수(DIO)가 +7일 이상 급증하는 모순 포착 시 WARNING/VIOLATION 중 어느 등급으로 경보를 띄울까요?",
        ],
    },
    "material-quality-persona": {
        "team": "반도체 소재품질팀 (신규 소재 및 공급사 변경 검토)",
        "domain": "MATERIAL_QUALITY",
        "solver": "engine/solver_material.py",
        "aliases": ["material-quality-persona", "material-quality-bot", "material-quality-expert"],
        "dm_interview_script": [
            "[1차 DM - CoA Cpk & 스펙트럼 지문] 안녕하세요 소재품질팀 담당자님! 성적서(CoA) 수치만 스펙 이내이고 실제 파형에 미측정 불순물(Ghost Peak)이 섞인 In-Spec 불량을 막기 위해, 최소 Cpk(1.33) 외에 스펙트럼 코사인 유사도(0.985)와 Baseline 평균 이동(Mean Shift Z-score / Welch t-test) 기준을 어떻게 설정할까요?",
            "[2차 DM - HVM 배관 스트레스 & Sub-tier 4M] 양산 배관 체류시간 초과 또는 하위 2·3차 원료사(Sub-tier)의 PCN 미승인 4M 변경이 감지될 경우, 조건부 시생산(Pilot 15%) 없이 즉시 REJECT(VIOLATION) 및 해당 웨이퍼 로트 홀드 조치를 내리면 될까요?",
        ],
    },
    "photo-technology-persona": {
        "team": "포토기술팀 (Overlay 품질 및 장비 운영)",
        "domain": "OVERLAY_PHOTO",
        "solver": "engine/solver_overlay.py",
        "aliases": ["photo-technology-persona", "photo-technology-bot", "photo-overlay-expert", "icheon-photo-persona"],
        "dm_interview_script": [
            "[1차 DM - 고차 APC & 박막 스트레스 Feed-forward] 안녕하세요 포토기술팀 담당자님! Overlay M3S 스펙(2.0nm) 판정 시 등호 포함(>=) 여부와, 웨이퍼 엣지 고차 왜곡(3차 HOWA) 보정 시 전공정(Etch/Dep) 박막 스트레스 Feed-forward 항을 기본 결합할지 확인 부탁드립니다.",
            "[2차 DM - 스마트 샘플링 & 스캐너/척 매칭] 계측 병목(TAT) 해소를 위한 최소 스마트 샘플링 비율(예: 35%)과, 포토 Chuck 간 편차 vs 전공정 Etch 챔버 편차 원인 귀속 임계치(0.35nm / 인터록 0.65nm) 및 스캐너 라우팅 가중치 기준을 확정하고 싶습니다.",
        ],
    },
}

DOMAIN_FIELD_SYNONYMS = {
    "OVERLAY_PHOTO": {
        "X": ["X", "wafer_x", "wx", "shot_x", "die_x", "coord_x"],
        "Y": ["Y", "wafer_y", "wy", "shot_y", "die_y", "coord_y"],
        "x": ["x", "field_x", "fx", "intra_x", "site_x"],
        "y": ["y", "field_y", "fy", "intra_y", "site_y"],
        "dx": ["dx", "ovl_x", "overlay_x", "err_x", "dx_nm", "x_reg", "reg_x"],
        "dy": ["dy", "ovl_y", "overlay_y", "err_y", "dy_nm", "y_reg", "reg_y"],
        "pre_process_stress_mpa": ["pre_process_stress_mpa", "stress_mpa", "film_stress", "stress"],
        "chuck_id": ["chuck_id", "chuck", "stage_id"],
        "scanner_id": ["scanner_id", "scanner", "equip_id", "tool_id"],
        "etch_chamber_id": ["etch_chamber_id", "etch_chamber", "chamber_id"],
        "wafer_id": ["wafer_id", "wafer", "wf_id"],
        "lot_id": ["lot_id", "lot"],
    },
    "MATERIAL_QUALITY": {
        "vendor_id": ["vendor_id", "vendor", "supplier", "maker", "공급사", "업체", "업체명"],
        "lot_id": ["lot_id", "mother_lot", "batch_id", "subtier_lot", "로트"],
        "lsl": ["lsl", "lower_spec_limit", "min_spec", "하한"],
        "usl": ["usl", "upper_spec_limit", "max_spec", "상한"],
        "cpk": ["cpk", "process_capability", "공정능력"],
        "metal_ppb": ["metal_ppb", "fe_ppb", "cu_ppb", "na_ppb", "impurity_ppb", "metal_impurity_ppb", "금속불순물"],
        "moisture_ppm": ["moisture_ppm", "h2o_ppm", "moisture", "수분"],
        "pipe_residence_hours": ["pipe_residence_hours", "residence_time", "배관체류시간"],
        "wafer_yield_pct": ["wafer_yield_pct", "yield_pct", "inline_yield", "수율"],
    },
    "MARKET_STRATEGY": {
        "company": ["company", "competitor", "vendor", "firm", "기업", "경쟁사"],
        "reported_period": ["reported_period", "period", "quarter", "fiscal_quarter", "fq", "분기"],
        "revenue": ["revenue", "sales", "rev", "매출", "매출액"],
        "operating_profit": ["operating_profit", "op", "ebit", "영업이익"],
        "shipment_volume": ["shipment_volume", "bit_shipment", "shipment", "출하량"],
        "curr_inventory_days_dio": ["curr_inventory_days_dio", "dio", "inventory_days", "재고일수"],
        "hbm_bit_share_pct": ["hbm_bit_share_pct", "hbm_share_pct", "hbm_ratio", "hbm비중"],
        "legacy_asp_usd": ["legacy_asp_usd", "commodity_asp", "dram_asp", "범용단가"],
        "hbm_asp_usd": ["hbm_asp_usd", "hbm_price", "specialty_asp", "hbm단가"],
    },
    "VALUE_CHAIN_BIZ": {
        "end_demand_shock_pct": ["end_demand_shock_pct", "demand_shock", "csp_growth_pct", "수요변동"],
        "tsmc_cowos_alloc_bgb": ["tsmc_cowos_alloc_bgb", "cowos_cap", "packaging_cap", "패키징한도"],
        "total_capex_budget_musd": ["total_capex_budget_musd", "capex_budget", "설비투자예산"],
        "wacc_pct": ["wacc_pct", "wacc", "hurdle_rate", "자본비용"],
        "die_penalty_factor": ["die_penalty_factor", "die_penalty", "다이페널티"],
        "conversion_capa_loss_pct": ["conversion_capa_loss_pct", "conversion_loss", "전환손실"],
    },
    "CURRICULUM_EDU": {
        "id": ["id", "module_id", "course_id", "과목코드"],
        "title": ["title", "name", "course_name", "과목명"],
        "prereqs": ["prereqs", "prerequisites", "pre_ids", "선수과목"],
        "hours": ["hours", "duration", "duration_hours", "학습시간"],
        "level": ["level", "difficulty", "난이도"],
        "learner_id": ["learner_id", "student_id", "emp_id", "사번", "교육생"],
    },
    "UNIVERSAL_OPS": {
        "slot_or_day": ["day", "date", "slot", "shift", "period", "일자", "요일", "시간대"],
        "category_or_group": ["category", "group", "line", "route_id", "zone_id", "bay_id", "노선", "구역", "분류"],
        "demand_or_passengers": ["demand", "passengers", "headcount", "wait_count", "transfer_count", "탑승객", "수요", "인원", "반송량"],
        "capacity_or_seats": ["capacity", "seats", "limit", "max_load", "좌석수", "정원", "용량"],
        "coverage_zones": ["covered_zones", "coverage", "target_zones", "blind_spots", "커버구역", "시야각", "사각지대"],
        "calories_or_nutrition": ["calories", "kcal", "protein", "sodium", "칼로리", "단백질", "나트륨"],
        "preference_or_score": ["preference", "interest_score", "rating", "value", "score", "utility", "선호도", "관심도", "점수", "효용"],
        "forbidden_or_restricted": ["forbidden", "security_restricted", "privacy_zone", "is_blocked", "보안구역", "설치불가", "제한구역"],
    },
    "TYPE_A_TEXT_ALARM": {
        "alarm_code": ["alarm_code", "error_code", "code", "err_id", "알람코드", "에러코드"],
        "severity": ["severity", "level", "심각도"],
        "user_role": ["user_role", "role", "clearance", "직무", "권한"],
        "time_budget_mins": ["time_budget_mins", "budget_mins", "max_time", "가용시간"],
    },
    "TYPE_B_WAFER_YIELD": {
        "x": ["x", "col", "die_x"],
        "y": ["y", "row", "die_y"],
        "is_fail": ["is_fail", "fail", "bin", "불량여부"],
        "step_yield_pct": ["step_yield_pct", "step_yield", "yield_pct", "공정수율"],
        "improvement_cost": ["improvement_cost", "cost", "개선비용"],
    },
    "TYPE_C_FDC_SENSOR": {
        "value": ["value", "sensor_val", "score", "reading", "측정값", "센서값"],
        "timestamp": ["timestamp", "time", "date", "ts", "측정시각"],
        "is_actual_fault": ["is_actual_fault", "fault", "label", "실제이상"],
    },
    "TYPE_D_WORKFLOW_PM": {
        "equip_id": ["equip_id", "equip", "equipment", "설비ID", "설비코드"],
        "current_usage_hours": ["current_usage_hours", "usage_hours", "operating_hours", "가동시간"],
        "max_lifetime_hours": ["max_lifetime_hours", "spec_limit_hours", "수명한도"],
        "weibull_beta": ["weibull_beta", "beta", "형상모수"],
    },
    "TYPE_E_RECIPE_CPK": {
        "param_name": ["param_name", "parameter", "name", "설정항목", "파라미터"],
        "target": ["target", "golden_spec", "golden", "목표값"],
        "actual": ["actual", "measured", "실측값"],
        "lsl": ["lsl", "min", "하한"],
        "usl": ["usl", "max", "상한"],
        "sensitivity": ["sensitivity", "sens", "gain", "감도"],
    },
}

# 10대 시맨틱 컬럼 역할(Role) 사전 (미출제 도메인 자동 대응용)
SEMANTIC_ROLE_PATTERNS = {
    "ID_KEY": ["id", "key", "code", "no", "uuid", "seq", "lot", "wafer", "route", "zone", "menu", "item", "emp", "ticket", "코드", "번호", "식별자"],
    "TIME_SLOT": ["time", "date", "day", "month", "quarter", "period", "slot", "shift", "timestamp", "hour", "일자", "시간", "분기", "요일"],
    "GROUP_ENTITY": ["category", "group", "type", "dept", "team", "vendor", "supplier", "company", "line", "bay", "chamber", "scanner", "chuck", "cuisine", "분류", "부서", "공급사", "장비", "노선", "구역"],
    "COST_RESOURCE": ["cost", "price", "budget", "capex", "opex", "fee", "expense", "tariff", "power", "energy", "kcal", "calories", "비용", "단가", "예산", "전력", "칼로리"],
    "CAPACITY_LIMIT": ["capacity", "cap", "limit", "max", "ceiling", "seats", "alloc", "available", "quota", "정원", "용량", "한도", "상한", "좌석"],
    "DEMAND_LOAD": ["demand", "load", "passengers", "headcount", "volume", "shipment", "requests", "queue", "wait", "traffic", "수요", "탑승", "물량", "출하", "대기"],
    "QUALITY_VALUE": ["value", "score", "preference", "interest", "rating", "yield", "cpk", "roic", "opm", "profit", "revenue", "efficiency", "benefit", "점수", "선호", "수율", "이익", "매출", "효율"],
    "RISK_DEFECT": ["risk", "defect", "error", "err", "dx", "dy", "ovl", "impurity", "ppb", "ppm", "drift", "loss", "penalty", "delay", "shock", "dio", "불량", "결함", "오차", "위험", "지연", "손실"],
    "RESTRICTION_FLAG": ["forbidden", "restricted", "security", "privacy", "blocked", "mandatory", "required", "status", "flag", "unreported", "보안", "금지", "필수", "상태"],
    "TEXT_CONTENT": ["text", "content", "transcript", "question", "inquiry", "comment", "description", "note", "title", "reason", "내용", "문의", "질문", "비고", "제목"],
}


def read_text_auto_encoding(fpath: Path, max_bytes: int = 500_000) -> str:
    """UTF-8, UTF-8-SIG(BOM), CP949(EUC-KR) 인코딩을 순서대로 자동 감지하여 텍스트를 안전하게 읽습니다."""
    raw = fpath.read_bytes()[:max_bytes]
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def read_delimited_table(fpath: Path, max_rows: int = 2000) -> List[Dict[str, Any]]:
    """CSV/TSV 파일의 인코딩과 구분자(쉼표, 탭, 세미콜론, 파이프)를 자동 감지하여 Dict 리스트로 반환합니다."""
    txt = read_text_auto_encoding(fpath)
    lines = [line for line in txt.splitlines() if line.strip()]
    if not lines:
        return []
    sample_head = "\n".join(lines[:5])
    delimiter = ","
    if fpath.suffix.lower() == ".tsv" or sample_head.count("\t") > sample_head.count(","):
        delimiter = "\t"
    elif sample_head.count(";") > sample_head.count(","):
        delimiter = ";"
    elif sample_head.count("|") > sample_head.count(",") + 2:
        delimiter = "|"

    reader = csv.DictReader(lines, delimiter=delimiter)
    rows = []
    for idx, r in enumerate(reader):
        if idx >= max_rows:
            break
        clean_r = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k is not None}
        if clean_r:
            rows.append(clean_r)
    return rows


def extract_markdown_tables(md_text: str, source_name: str) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """마크다운(.md) 문서 내부에 표(| col1 | col2 |) 형태로만 주어진 기준표/데이터를 자동 파싱합니다."""
    extracted_tables: List[Tuple[str, List[Dict[str, Any]]]] = []
    blocks = re.findall(r"((?:^\s*\|.+\|\s*\n){3,})", md_text, re.MULTILINE)
    for b_idx, block in enumerate(blocks):
        raw_lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(raw_lines) < 3:
            continue
        headers = [c.strip().strip("`*_") for c in raw_lines[0].strip("|").split("|")]
        if not any(headers) or not re.match(r"^[\s|:\-]+$", raw_lines[1]):
            continue
        rows = []
        for line in raw_lines[2:]:
            if re.match(r"^[\s|:\-]+$", line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
        if rows:
            extracted_tables.append((f"{source_name}#md_table_{b_idx+1}", rows))
    return extracted_tables


def infer_semantic_column_roles(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """미출제(Unseen) 도메인에서도 컬럼명 형태소와 실제 값 분포를 결합해 10대 시맨틱 역할을 자동 추론합니다."""
    if not rows or not isinstance(rows[0], dict):
        return {}
    roles: Dict[str, str] = {}
    for col in rows[0].keys():
        cl = str(col).strip().lower()
        assigned = None
        for role, keywords in SEMANTIC_ROLE_PATTERNS.items():
            if any(kw in cl for kw in keywords):
                assigned = role
                break
        if not assigned:
            sample_vals = [str(r.get(col, "")).strip() for r in rows[:25] if r.get(col) not in (None, "")]
            num_cnt = 0
            for sv in sample_vals:
                try:
                    float(sv.replace(",", "").replace("$", "").replace("%", ""))
                    num_cnt += 1
                except Exception:
                    pass
            if sample_vals and num_cnt >= len(sample_vals) * 0.7:
                assigned = "QUALITY_VALUE"
            elif sample_vals and sum(len(sv) for sv in sample_vals) / len(sample_vals) > 35:
                assigned = "TEXT_CONTENT"
            else:
                assigned = "GROUP_ENTITY"
        roles[col] = assigned
    return roles


def probe_llm_runtime_env() -> Dict[str, Any]:
    """환경변수에서 Cofa 내장 LLM 프록시/엔드포인트/모델 설정을 안전하게 탐지 (키 값 자체는 노출 금지)"""
    env_keys = sorted(os.environ.keys())
    ai_related_vars = [
        k for k in env_keys
        if any(tok in k.upper() for tok in ("OPENAI", "ANTHROPIC", "COFA", "LLM", "AI_", "MODEL", "SOL", "TERRA", "LUNA", "PROXY", "BASE_URL", "PERSONA", "BOT"))
    ]
    base_url_candidates = [
        os.environ.get(k, "")
        for k in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "LLM_BASE_URL", "COFA_API_BASE", "AI_GATEWAY_URL")
        if os.environ.get(k)
    ]
    return {
        "detected_ai_env_var_names": ai_related_vars,
        "has_preconfigured_base_url": len(base_url_candidates) > 0,
        "base_url_preview": base_url_candidates[0][:45] + "..." if base_url_candidates else "DEFAULT_ENV_OR_LOCAL_FALLBACK",
        "allowed_models": ["Sol-6.1", "Terra-5.6", "Luna-6", "Sol-6.0"],
        "forbidden_models": ["Astra"],
    }


def detect_persona_dm_bots(root: Path) -> Dict[str, Any]:
    """워크스페이스 문서/설정/환경변수에서 플랫폼 채팅봇(Persona ID) 시그니처를 탐지하고 즉시 사용할 DM 질의 스크립트를 반환"""
    corpus = []
    for k, v in os.environ.items():
        if "PERSONA" in k.upper() or "VALUE-CHAIN" in v.upper() or "BOT" in v.upper() or "EXPERT" in v.upper() or "ROLE" in k.upper():
            corpus.append(f"{k}={v}")

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in sorted(filenames):
            if fname.lower().endswith((".md", ".txt", ".json", ".yaml", ".yml", ".toml")):
                if fname in {"fde_autopilot_manual.md", "WORKSPACE_PROFILE.md", "cofa_probe_report.json"}:
                    continue
                fpath = Path(dirpath) / fname
                try:
                    corpus.append(read_text_auto_encoding(fpath, max_bytes=16000))
                except Exception:
                    pass

    full_text = "\n".join(corpus).lower()
    matched_bots = []

    for pid, info in KNOWN_PERSONA_DM_BOTS.items():
        aliases = info.get("aliases", [pid])
        hit = any(a.lower() in full_text for a in aliases) or (info["team"].lower() in full_text)
        if hit:
            matched_bots.append({
                "persona_id": pid,
                "team": info["team"],
                "mapped_domain": info["domain"],
                "recommended_solver": info["solver"],
                "ready_to_copy_dm_questions": info["dm_interview_script"],
            })

    return {
        "detected_persona_count": len(matched_bots),
        "matched_personas": matched_bots,
        "all_supported_persona_ids": list(KNOWN_PERSONA_DM_BOTS.keys()),
    }


def extract_doc_rules_and_citations(root: Path) -> Dict[str, Any]:
    """마크다운/텍스트 문서에서 규정 조항, 숫자 스펙(nm, ppb, %, 시간, Cpk, kcal, 인승, 예산 등) 및 카노니컬 파라미터 사전을 자동 추출"""
    extracted_by_file = []
    canonical_overrides: Dict[str, float] = {}

    spec_pattern = re.compile(
        r"([가-힣A-Za-z0-9_\-\s]{2,28})\s*(?:기준|한도|스펙|임계치|상한|하한|Spec|Limit|Cpk|M3S|DIO|ROIC|WACC|칼로리|정원|예산|시간)[^\n:;]{0,20}[:=]?\s*([<>]=?\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:nm|ppb|ppm|%|시간|h|일|days|개월|배|점|MUSD|조|억|kcal|명|대|원)?)",
        re.IGNORECASE,
    )
    num_re = re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?)")

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in sorted(filenames):
            if not fname.lower().endswith((".md", ".txt")):
                continue
            if fname in {"AGENTS.md", "AUDITOR_GUIDE.md", "fde_autopilot_manual.md", "WORKSPACE_PROFILE.md", "SPEC.md", "HANDOFF.md", "SOLUTION_NOTES.md"} or fname.startswith("fde_"):
                continue
            fpath = Path(dirpath) / fname
            try:
                text = read_text_auto_encoding(fpath, max_bytes=50000)
                matches = spec_pattern.findall(text)
                if matches:
                    rule_list = []
                    for m in matches[:25]:
                        term = m[0].strip()
                        thresh_str = m[1].strip()
                        rule_list.append({"term": term, "threshold": thresh_str})
                        num_m = num_re.search(thresh_str)
                        if num_m:
                            val = float(num_m.group(1).replace(",", ""))
                            tl = (term + " " + thresh_str).lower()
                            if "m3s" in tl or ("overlay" in tl and "nm" in tl):
                                canonical_overrides["m3s_spec_nm"] = val
                            elif "cpk" in tl and 0.5 <= val <= 3.0:
                                canonical_overrides["min_cpk"] = val
                            elif "dio" in tl or "재고일수" in tl:
                                canonical_overrides["dio_spike_days"] = val
                            elif "wacc" in tl or "허들" in tl or "자본비용" in tl:
                                canonical_overrides["wacc_pct"] = val
                            elif "cowos" in tl:
                                canonical_overrides["tsmc_cowos_alloc_bgb"] = val
                            elif ("학습" in tl or "교육" in tl or "max_hours" in tl) and ("시간" in tl or "h" in tl):
                                canonical_overrides["max_hours"] = val
                            elif "정원" in tl or "좌석" in tl or "인승" in tl:
                                canonical_overrides["bus_seat_capacity"] = val
                            elif "예산" in tl or "budget" in tl:
                                canonical_overrides["total_budget"] = val
                    extracted_by_file.append({
                        "file": str(fpath.relative_to(root)),
                        "extracted_rules": rule_list,
                    })
            except Exception:
                pass
    return {
        "files_with_rules": extracted_by_file,
        "canonical_parameter_overrides": canonical_overrides,
    }


def map_dataset_columns_to_domains(root: Path) -> List[Dict[str, Any]]:
    """CSV/TSV/JSON/SQLite 파일의 실제 컬럼들을 5대 반도체 도메인 + 범용 현업 도메인 표준 필드 및 10대 시맨틱 역할과 자동 매칭"""
    mappings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            lower = fname.lower()
            rows: List[Dict[str, Any]] = []
            if lower.endswith((".csv", ".tsv")):
                try:
                    rows = read_delimited_table(fpath, max_rows=200)
                except Exception:
                    pass
            elif lower.endswith(".json") and lower not in {"package.json", "package-lock.json", "tsconfig.json", "cofa_probe_report.json", "result.json", "live_workspace_solution.json"}:
                try:
                    data = json.loads(read_text_auto_encoding(fpath))
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        rows = data[:200]
                    elif isinstance(data, dict):
                        rows = [data]
                except Exception:
                    pass
            elif lower.endswith((".sqlite", ".db", ".sqlite3")) and sqlite3 is not None:
                try:
                    conn = sqlite3.connect(str(fpath))
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    for (tname,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall():
                        db_rows = [dict(r) for r in cur.execute(f"SELECT * FROM '{tname}' LIMIT 100;").fetchall()]
                        if db_rows:
                            rows.extend(db_rows)
                    conn.close()
                except Exception:
                    pass

            if not rows or not isinstance(rows[0], dict):
                continue

            cols = list(rows[0].keys())
            lower_cols = {c.strip().lower(): c for c in cols}
            best_domain = None
            best_map = {}
            for dom, field_dict in DOMAIN_FIELD_SYNONYMS.items():
                matched_map = {}
                for std_field, aliases in field_dict.items():
                    for al in aliases:
                        if al.lower() in lower_cols:
                            matched_map[std_field] = lower_cols[al.lower()]
                            break
                if len(matched_map) > len(best_map):
                    best_map = matched_map
                    best_domain = dom

            semantic_roles = infer_semantic_column_roles(rows)
            mappings.append({
                "file": str(fpath.relative_to(root)),
                "row_sample_count": len(rows),
                "raw_columns": cols[:30],
                "inferred_domain": best_domain or "UNIVERSAL_OPS",
                "canonical_field_mapping": best_map,
                "semantic_column_roles": semantic_roles,
            })
    return mappings


def discover_and_join_relational_tables(root: Path) -> Dict[str, Any]:
    """
    [Fact-First 멀티 테이블 자동 탐색 & 복합 Foreign Key 관계형 조인기]
    워크스페이스 내 다수의 CSV/TSV/JSON 및 Markdown 표를 스캔하여 가장 행 수가 많은 Fact 테이블을 식별하고,
    단일 키 또는 복합 키(lot_id, wafer_id, vendor_id, company+quarter 등)를 자동 감지합니다.
    """
    tables: Dict[str, List[Dict[str, Any]]] = {}
    join_keys = [
        "lot_id", "wafer_id", "vendor_id", "vendor", "supplier", "company", "reported_period", "quarter",
        "equip_id", "scanner_id", "chamber_id", "chuck_id", "module_id", "course_id", "learner_id",
        "route_id", "zone_id", "menu_id", "item_id", "id", "key"
    ]

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            lower = fname.lower()
            rel = str(fpath.relative_to(root))
            if lower.endswith((".csv", ".tsv")):
                try:
                    rows = read_delimited_table(fpath, max_rows=1500)
                    if rows:
                        tables[rel] = rows
                except Exception:
                    pass
            elif lower.endswith(".json") and lower not in {"package.json", "package-lock.json", "tsconfig.json"} and "cofa_probe" not in lower:
                try:
                    data = json.loads(read_text_auto_encoding(fpath))
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        tables[rel] = data[:1500]
                except Exception:
                    pass
            elif lower.endswith(".md") and fname not in {"AGENTS.md", "AUDITOR_GUIDE.md", "fde_autopilot_manual.md", "WORKSPACE_PROFILE.md", "SPEC.md", "HANDOFF.md", "SOLUTION_NOTES.md"} and not fname.startswith("fde_"):
                try:
                    md_tables = extract_markdown_tables(read_text_auto_encoding(fpath), rel)
                    for t_id, t_rows in md_tables:
                        tables[t_id] = t_rows
                except Exception:
                    pass

    sorted_tables = sorted(tables.items(), key=lambda kv: len(kv[1]), reverse=True)
    primary_fact_table = sorted_tables[0][0] if sorted_tables else None

    detected_relations = []
    t_names = [k for k, _ in sorted_tables]
    for i in range(len(t_names)):
        for j in range(i + 1, len(t_names)):
            t1, t2 = t_names[i], t_names[j]
            cols1 = {k.lower(): k for k in tables[t1][0].keys()}
            cols2 = {k.lower(): k for k in tables[t2][0].keys()}
            shared = [jk for jk in join_keys if jk in cols1 and jk in cols2]
            if shared:
                detected_relations.append({
                    "fact_or_left_table": t1,
                    "dim_or_right_table": t2,
                    "shared_composite_join_keys": shared,
                    "left_rows": len(tables[t1]),
                    "right_rows": len(tables[t2]),
                })

    return {
        "discovered_table_count": len(tables),
        "primary_fact_table": primary_fact_table,
        "table_summaries": {k: {"row_count": len(v), "columns": list(v[0].keys())[:25]} for k, v in sorted_tables},
        "detected_foreign_key_relations": detected_relations,
    }


def run_probe(root: Path) -> Dict[str, Any]:
    doc_rules = extract_doc_rules_and_citations(root)
    return {
        "workspace_root": str(root),
        "llm_runtime_probe": probe_llm_runtime_env(),
        "persona_dm_bot_probe": detect_persona_dm_bots(root),
        "document_extracted_thresholds": doc_rules["files_with_rules"],
        "canonical_parameter_overrides": doc_rules["canonical_parameter_overrides"],
        "dataset_fuzzy_schema_mappings": map_dataset_columns_to_domains(root),
        "multi_table_relational_discovery": discover_and_join_relational_tables(root),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root")
    parser.add_argument("--workspace", dest="workspace_alias", default=None, help="Workspace root alias")
    parser.add_argument("--out", default=".autopilot/cofa_probe_report.json", help="Output JSON report")
    args = parser.parse_args()

    effective_root = args.workspace_alias or args.root
    root_path = Path(effective_root).resolve()
    report = run_probe(root_path)
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ [Cofa Probe v7.0] 환경/페르소나 챗봇/문서규칙/시맨틱 스키마/복합키 매핑 완료 -> {out_path}")
