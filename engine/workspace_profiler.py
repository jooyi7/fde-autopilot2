#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - Advanced Workspace, Dataset & 5-Domain Automated Profiler (v3.0)
과제 폴더 내 문서, 데이터셋(CSV/JSON/SQLite), 레거시 테스트 구조를 해부하여
5대 반도체 현업 도메인(포토 Overlay, 소재품질 CoA, 시장전략 실적분석, 경영전략 Value-Chain, 반도체 산업교육)을
자동 감지하고, 도메인 전용 솔버(engine/solver_*.py) 매핑 및 실무자 DM 핵심 질문 트리거를 도출합니다.
"""
import argparse
import csv
import json
import math
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "__pycache__",
    ".venv", "venv", "fde-autopilot", "fde-kit", ".fde_audit_cache"
}

SENTINEL_STRINGS = {"null", "nan", "none", "n/a", "na", "-", "undefined", "error", "err"}
SENTINEL_NUMBERS = {-999.0, -9999.0, 9999.0, 99999.0, -1.0}
STATUS_FLAG_KEYWORDS = {"CANCELLED", "CANCELED", "DISCARDED", "TEST", "DUMMY", "REJECTED", "INVALID", "HOLD", "ERROR", "FAIL"}

DOMAIN_SIGNATURES = {
    "DOMAIN_1_OVERLAY": {
        "name": "Overlay 품질 및 장비 운영",
        "solver": "engine/solver_overlay.py (OverlaySolver)",
        "keywords": {"overlay", "m3s", "scanner", "chuck", "apc", "dx", "dy", "metrology", "rework", "노광", "오버레이", "포토"},
        "dm_questions": [
            "[Overlay APC & 경계값] M3S 스펙 판정 시 경계값 포함(>=) 여부와, 고차 비선형 보정(2~3차) 시 전공정(Etch/Dep) 박막 스트레스 Feed-forward 항을 기본 포함할까요?",
            "[스마트 샘플링 & 라우팅] 계측 병목 완화를 위한 최소 스마트 샘플링 비율(%)과, 스캐너 배정 시 품질(Chuck Matching Offset) 대 대기시간(Queue Time)의 가중치 기준은 무엇인가요?",
        ],
    },
    "DOMAIN_2_MATERIAL": {
        "name": "신규 소재 및 공급사 변경 검토",
        "solver": "engine/solver_material.py (MaterialQualitySolver)",
        "keywords": {"coa", "cpk", "usl", "lsl", "ppb", "vendor", "slurry", "photoresist", "precursor", "4m", "subtier", "소재", "공급사", "성적서"},
        "dm_questions": [
            "[CoA 산포 및 In-Spec 불량] 단일 스펙(LSL/USL) 통과 외에 양산 승인(Approve)을 위한 최소 Cpk 기준(예: 1.33)과 스펙트럼 지문(Fingerprint) 유사도 임계치는 무엇인가요?",
            "[HVM 스케일업 & 4M 변경] 배관 체류시간/전단응력 악화 또는 하위 2·3차 공급사(Sub-tier)의 미신고 4M 변경 감지 시 조건부 시생산(Pilot) 없이 즉시 Reject 처리할까요?",
        ],
    },
    "DOMAIN_3_MARKET_STRAT": {
        "name": "메모리 시장 및 경쟁사 실적 분석",
        "solver": "engine/solver_market.py (MarketStrategySolver)",
        "keywords": {"micron", "asp", "bit_growth", "dram", "nand", "dio", "earnings", "calendarization", "경쟁사", "실적", "시장전략", "출하량"},
        "dm_questions": [
            "[회계 분기 및 단위 표준화] 마이크론(8월 결산) 실적을 캘린더 분기(CQ)로 매핑할 때의 기준 환율(KRW/USD)과 물량 집계 단위(B_Gb vs Exabyte)를 어떻게 통일할까요?",
            "[Mix 착시 및 IR 교차검증] 전사 Blended ASP 상승 속 레거시 단가 하락(Mix 착시)이나 IR 긍정 발언 대비 재고일수(DIO) 급증이 포착될 때 WARNING 배지를 최우선 노출할까요?",
        ],
    },
    "DOMAIN_4_VALUE_CHAIN_BIZ": {
        "name": "경영전략팀 시장분석 ",
        "solver": "engine/solver_value_chain_biz.py (ValueChainBusinessSolver)",
        "keywords": {"skhynix-value-chain-business-persona", "cowos", "bullwhip", "roic", "wacc", "capital_intensity", "geopolitical", "경영전략", "밸류체인", "가치사슬"},
        "dm_questions": [
            "[생태계 병목 & 채찍효과] 내부 Fab/EDS 수율보다 외부 TSMC CoWoS 패키징 할당량이나 커스텀 베이스 다이 공급량이 낮을 때, 출하 상한선(Ceiling)과 미출하 재고 비용을 어떻게 반영할까요?",
            "[CAPEX ROIC & 지정학 시나리오] HBM3E/DDR5/eSSD 포트폴리오 배분 시 최소 WACC 허들 레이트(%)와, 대중국 장비 규제 시 우시/이천 Fab 물량 스왑 컨틴전시 발동 조건은 무엇인가요?",
        ],
    },
    "DOMAIN_5_CURRICULUM_EDU": {
        "name": "반도체 산업교육",
        "solver": "engine/solver_curriculum.py (CurriculumOntologySolver)",
        "keywords": {"skhynix-value-chain-educator-persona", "curriculum", "prereqs", "learner", "pedagogy", "analogy", "산업교육", "커리큘럼", "교육생", "선수과목"},
        "dm_questions": [
            "[선수과목 DAG & 시간 상한] 선수과목 순환 참조(Cycle) 발견 시 전체 에러 처리할지 여부와, 최대 학습 시간(max_hours) 초과 시 레벨/이수율 중 어느 기준으로 과목을 이연(Defer)할까요?",
            "[2-Layer 비유 교정 & 직무별 퀴즈] 교육생 직무(구매/재무/엔지니어)별로 비유 한계 교정(Engineering Fact Guardrail)과 4단계 비즈니스 가치 연결 스토리라인을 필수 출력 항목으로 고정할까요?",
        ],
    },
}


def compute_numeric_stats(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {}
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n if n > 1 else 0.0
    std = math.sqrt(variance)
    sorted_vals = sorted(values)
    p50 = sorted_vals[n // 2]
    p95 = sorted_vals[min(n - 1, int(n * 0.95))]
    return {
        "count": n,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(mean, 4),
        "std": round(std, 4),
        "median": round(p50, 4),
        "p95": round(p95, 4),
        "ucl_3sigma": round(mean + 3 * std, 4),
        "lcl_3sigma": round(mean - 3 * std, 4),
    }


def detect_semiconductor_domains(corpus_text: str) -> List[Tuple[str, Dict[str, Any], int]]:
    lower_corpus = corpus_text.lower()
    matched = []
    for d_key, d_info in DOMAIN_SIGNATURES.items():
        score = sum(3 if kw.startswith("skhynix-") else 1 for kw in d_info["keywords"] if kw in lower_corpus)
        if score > 0:
            matched.append((d_key, d_info, score))
    matched.sort(key=lambda x: x[2], reverse=True)
    return matched


def analyze_csv(file_path: Path, dm_triggers: List[str], token_accumulator: List[str]) -> str:
    lines = [f"### 📊 CSV 데이터셋: `{file_path.name}` (`{file_path}`)"]
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            token_accumulator.extend(headers)
            rows = []
            for idx, r in enumerate(reader):
                if idx >= 10000:
                    break
                rows.append(r)

        total_rows = len(rows)
        lines.append(f"- **스캔된 행 수**: {total_rows}건 | **컬럼 수**: {len(headers)}개")
        lines.append(f"- **컬럼 목록**: `{', '.join(headers)}`")

        id_cols = [h for h in headers if any(k in h.lower() for k in ("id", "key", "no", "code", "uuid", "seq", "record", "item", "lot", "wafer"))]
        for id_col in id_cols[:3]:
            seen = set()
            dup_cnt = 0
            for r in rows:
                v = str(r.get(id_col, "")).strip()
                if v:
                    if v in seen:
                        dup_cnt += 1
                    seen.add(v)
            if dup_cnt > 0:
                lines.append(f"- ⚠️ **중복 키 감지 (`{id_col}`)**: 총 {dup_cnt}건의 중복 식별자 발견")
                dm_triggers.append(
                    f"[중복 레코드 기준] `{file_path.name}`의 `{id_col}` 컬럼에서 {dup_cnt}건의 중복이 감지됨 -> "
                    f"실무자 에이전트(DM)로 '최신 타임스탬프 1건 유지 vs 최초 1건 유지 vs 합산' 기준 확인 필수"
                )

        col_summary = []
        for col in headers:
            null_cnt = 0
            sentinel_cnt = 0
            num_vals = []
            sample_vals = []
            detected_flags = set()

            for r in rows:
                val = r.get(col)
                if val is None or str(val).strip() == "" or str(val).strip().lower() in SENTINEL_STRINGS:
                    null_cnt += 1
                    continue

                s_val = str(val).strip()
                if s_val.upper() in STATUS_FLAG_KEYWORDS:
                    detected_flags.add(s_val.upper())

                if len(sample_vals) < 4 and s_val not in sample_vals:
                    sample_vals.append(s_val[:40])

                try:
                    f_val = float(s_val.replace(",", ""))
                    if f_val in SENTINEL_NUMBERS and ("id" not in col.lower()):
                        sentinel_cnt += 1
                    else:
                        num_vals.append(f_val)
                except ValueError:
                    pass

            if detected_flags:
                dm_triggers.append(
                    f"[비정상 상태 플래그 제외 여부] `{file_path.name}`의 `{col}` 컬럼에 `{', '.join(detected_flags)}` 상태 존재 -> "
                    f"전체 통계 집계 및 핵심 지표 계산 분모에서 완전 제외하는지 실무자 에이전트(DM) 확인 필수"
                )

            if sentinel_cnt > 0:
                dm_triggers.append(
                    f"[센티널 이상치 처리] `{file_path.name}`의 `{col}` 컬럼에 센티널 수치(-999/9999 등) {sentinel_cnt}건 존재 -> "
                    f"행 제거(Drop) vs 대체(Imputation) vs 별도 이상 상태로 분리 여부 확인 필수"
                )

            valid_non_null = max(1, total_rows - null_cnt - sentinel_cnt)
            if len(num_vals) > valid_non_null * 0.7:
                st = compute_numeric_stats(num_vals)
                col_summary.append(
                    f"  - `{col}` (수치형 | 결측 {null_cnt}건, 센티널의심 {sentinel_cnt}건): "
                    f"min={st['min']}, max={st['max']}, mean={st['mean']}, std={st['std']}, "
                    f"**3σ UCL={st['ucl_3sigma']} / LCL={st['lcl_3sigma']}**"
                )
            else:
                flag_note = f" | 🚨 특수플래그: `{list(detected_flags)}`" if detected_flags else ""
                col_summary.append(
                    f"  - `{col}` (범주/텍스트 | 결측 {null_cnt}건){flag_note}: 샘플={sample_vals}"
                )
        lines.extend(col_summary)
    except Exception as e:
        lines.append(f"- ⚠️ CSV 파싱 오류: {e}")
    return "
".join(lines)


def analyze_json(file_path: Path, dm_triggers: List[str], token_accumulator: List[str]) -> str:
    lines = [f"### 🗂️ JSON 파일: `{file_path.name}` (`{file_path}`)"]
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw_txt = f.read()
            token_accumulator.append(raw_txt[:4000])
            data = json.loads(raw_txt)
        if isinstance(data, list):
            lines.append(f"- **구조**: Array (총 {len(data)}개 요소)")
            if data and isinstance(data[0], dict):
                keys = list(data[0].keys())
                lines.append(f"- **첫 번째 객체 키**: `{', '.join(keys)}`")
                lines.append(f"- **첫 번째 샘플**: `{json.dumps(data[0], ensure_ascii=False)[:250]}`")
        elif isinstance(data, dict):
            keys = list(data.keys())
            lines.append(f"- **구조**: Object (최상위 키 {len(keys)}개: `{', '.join(keys[:15])}`)")
            for k in keys[:5]:
                v = data[k]
                if isinstance(v, list):
                    lines.append(f"  - `{k}`: Array ({len(v)}개 항목)")
                elif isinstance(v, dict):
                    lines.append(f"  - `{k}`: Object (키: {list(v.keys())[:8]})")
                else:
                    lines.append(f"  - `{k}`: {repr(v)[:80]}")
    except Exception as e:
        lines.append(f"- ⚠️ JSON 분석 생략/오류: {e}")
    return "
".join(lines)


def analyze_sqlite(file_path: Path, dm_triggers: List[str], token_accumulator: List[str]) -> str:
    lines = [f"### 🗄️ SQLite DB: `{file_path.name}` (`{file_path}`)"]
    try:
        conn = sqlite3.connect(str(file_path))
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        token_accumulator.extend(tables)
        lines.append(f"- **테이블 목록**: `{', '.join(tables)}`")
        for t in tables:
            cnt = cur.execute(f"SELECT COUNT(*) FROM '{t}';").fetchone()[0]
            cols = [c[1] + "(" + c[2] + ")" for c in cur.execute(f"PRAGMA table_info('{t}');").fetchall()]
            token_accumulator.extend([c[0] for c in cols])
            lines.append(f"  - `{t}` ({cnt}행): `{', '.join(cols)}`")
        conn.close()
    except Exception as e:
        lines.append(f"- ⚠️ DB 스캔 오류: {e}")
    return "
".join(lines)


def scan_workspace(root_dir: Path) -> str:
    report = [
        "# 🧭 FDE Autopilot 워크스페이스, 데이터셋 & 5대 반도체 도메인 자동 프로파일링 리포트 (v3.0)",
        f"- **스캔 루트**: `{root_dir}`",
        "",
        "## 1. 디렉토리 및 주요 파일 트리"
    ]

    tree_lines = []
    data_reports = []
    readme_excerpt = []
    dm_triggers: List[str] = []
    token_accumulator: List[str] = []
    has_existing_tests = False
    has_policy_docs = False

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        rel_dir = Path(dirpath).relative_to(root_dir)
        depth = 0 if str(rel_dir) == "." else len(rel_dir.parts)
        if depth > 3:
            continue

        if any(part.lower() in ("test", "tests", "__tests__") for part in rel_dir.parts):
            has_existing_tests = True

        indent = "  " * depth
        if str(rel_dir) != ".":
            tree_lines.append(f"{indent}📁 `{rel_dir.name}/`")

        for fname in sorted(filenames):
            if fname.startswith(".fde_"):
                continue
            fpath = Path(dirpath) / fname
            fsize_kb = round(fpath.stat().st_size / 1024, 1)
            tree_lines.append(f"{indent}  📄 `{fname}` ({fsize_kb} KB)")
            token_accumulator.append(fname)

            lower_name = fname.lower()
            if "test" in lower_name or "spec" in lower_name:
                has_existing_tests = True
            if any(k in lower_name for k in ("policy", "manual", "guide", "rule", "sop", "규정", "매뉴얼", "지침")):
                has_policy_docs = True

            if lower_name == "readme.md" and depth == 0:
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    readme_excerpt.append(content[:2500])
                    token_accumulator.append(content[:5000])
                except Exception:
                    pass
            elif lower_name.endswith(".csv"):
                data_reports.append(analyze_csv(fpath, dm_triggers, token_accumulator))
            elif lower_name.endswith(".json") and lower_name not in ("package.json", "package-lock.json", "tsconfig.json"):
                data_reports.append(analyze_json(fpath, dm_triggers, token_accumulator))
            elif lower_name.endswith((".sqlite", ".db", ".sqlite3")):
                data_reports.append(analyze_sqlite(fpath, dm_triggers, token_accumulator))

    report.extend(tree_lines if tree_lines else ["- (파일 없음)"])

    # 5대 반도체 현업 도메인 자동 감지
    detected_domains = detect_semiconductor_domains(" ".join(token_accumulator))
    report.append("
## 2. 🔬 SK하이닉스 5대 도메인 솔버 & 아키타입(Archetype) 자동 매핑")
    if detected_domains:
        top_key, top_info, top_score = detected_domains[0]
        report.append(f"- 🎯 **1순위 감지 도메인**: **{top_info['name']}** (매칭 점수: {top_score})")
        report.append(f"- 🛠️ **연동할 전용 레퍼런스 솔버**: `{top_info['solver']}`")
        for q in top_info["dm_questions"]:
            dm_triggers.append(q)
        if len(detected_domains) > 1:
            sub_names = ", ".join(f"{d[1]['name']}({d[2]}점)" for d in detected_domains[1:3])
            report.append(f"- ℹ️ **연관 후보 도메인**: {sub_names}")
    else:
        report.append("- ℹ️ 특정 반도체 세부 도메인 시그니처가 명시되지 않았습니다 (범용 아키타입 모드로 동작).")

    if data_reports:
        report.append("- 🏗️ **추천 UI/앱 아키타입**: **Archetype A (지표 모니터링/대시보드)** 또는 **Archetype B (규칙 검증/Diff 알람)**")
    elif has_policy_docs:
        report.append("- 🏗️ **추천 UI/앱 아키타입**: **Archetype C (문서 검색 및 출처 기반 질의응답 / RAG)**")
    elif has_existing_tests:
        report.append("- 🏗️ **추천 UI/앱 아키타입**: **레거시 디버깅 / Archetype B (규칙 검증 및 Diff 알람)**")
    else:
        report.append("- 🏗️ **추천 UI/앱 아키타입**: **Archetype D (상태 머신 및 승인/백오피스 워크플로우)**")

    if readme_excerpt:
        report.append("
## 3. 과제 README.md 핵심 발췌")
        report.append("```markdown
" + readme_excerpt[0] + "
```")

    report.append("
## 4. 데이터셋 스키마·결측치·임계치(3-Sigma) 자동 분석")
    if data_reports:
        report.extend(data_reports)
    else:
        report.append("- 별도의 로컬 CSV/JSON/DB 데이터 파일이 감지되지 않았습니다.")

    report.append("
## 5. 💬 실무자 에이전트(DM) 최우선 확인 트리거 (도메인 & 데이터 기반 자동 도출)")
    if dm_triggers:
        for idx, trig in enumerate(dm_triggers, 1):
            report.append(f"{idx}. {trig}")
    else:
        report.append("1. [경계값 등호 기준] 임계값 판정 시 이상(>=)인지 초과(>)인지 확인")
        report.append("2. [핵심 산출물 우선순위] 1순위로 검증해야 할 핵심 유즈케이스와 제외 가능한 범위(Out-of-Scope) 확인")

    report.append("
## 6. FDE 80/20 아키텍처 설계 권고 (Codex 컨텍스트 주입용)")
    report.append("- 위 데이터 스캔 결과에서 발견된 **결측치(Null/빈 문자열/센티널 수치 -999)** 처리 로직을 `/src/data` 파서에 반드시 포함할 것.")
    report.append("- 감지된 도메인 솔버(`engine/solver_*.py`)의 수리/통계 알고리즘을 `/src/core/rules.js` 결정론 코어에 100% 이식할 것.")
    report.append("- 정상(NORMAL), 경고(WARNING), 위반(VIOLATION) 3종 데이터를 `/src/data/samples.js`의 골든 샘플 프리셋으로 구성할 것.")

    return "
".join(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root directory")
    parser.add_argument("--out", default=".fde_data_profile.md", help="Output profile markdown path")
    args = parser.parse_args()

    root_path = Path(args.root).resolve()
    result_md = scan_workspace(root_path)
    out_path = Path(args.out).resolve()
    out_path.write_text(result_md, encoding="utf-8")
    print(f"✅ [FDE Autopilot] 5대 도메인 프로파일링 및 DM 트리거 도출 완료: {out_path}")
