#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - Advanced Workspace & Dataset Automated Profiler (v2.1 Domain-Agnostic)
과제 폴더 내 문서, 데이터셋(CSV/JSON/SQLite), 레거시 테스트 구조를 해부하여
결정론 코어(80%) 설계에 필요한 통계적 임계치(3-Sigma), 센티널 결측치(-999 등), 중복 패턴,
그리고 실무자 에이전트(DM)로 즉시 확인해야 할 엣지 케이스 질문 후보를 자동 도출합니다.
"""
import argparse
import csv
import json
import math
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "__pycache__",
    ".venv", "venv", "fde-autopilot", "fde-kit", ".fde_audit_cache"
}

SENTINEL_STRINGS = {"null", "nan", "none", "n/a", "na", "-", "undefined", "error", "err"}
SENTINEL_NUMBERS = {-999.0, -9999.0, 9999.0, 99999.0, -1.0}
STATUS_FLAG_KEYWORDS = {"CANCELLED", "CANCELED", "DISCARDED", "TEST", "DUMMY", "REJECTED", "INVALID", "HOLD", "ERROR", "FAIL"}


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


def analyze_csv(file_path: Path, dm_triggers: List[str]) -> str:
    lines = [f"### 📊 CSV 데이터셋: `{file_path.name}` (`{file_path}`)"]
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = []
            for idx, r in enumerate(reader):
                if idx >= 10000:
                    break
                rows.append(r)

        total_rows = len(rows)
        lines.append(f"- **스캔된 행 수**: {total_rows}건 | **컬럼 수**: {len(headers)}개")
        lines.append(f"- **컬럼 목록**: `{', '.join(headers)}`")

        # 범용 식별자(ID/Key) 컬럼 중복 검사
        id_cols = [h for h in headers if any(k in h.lower() for k in ("id", "key", "no", "code", "uuid", "seq", "record", "item"))]
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
    return "\n".join(lines)


def analyze_json(file_path: Path, dm_triggers: List[str]) -> str:
    lines = [f"### 🗂️ JSON 파일: `{file_path.name}` (`{file_path}`)"]
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
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
    return "\n".join(lines)


def analyze_sqlite(file_path: Path, dm_triggers: List[str]) -> str:
    lines = [f"### 🗄️ SQLite DB: `{file_path.name}` (`{file_path}`)"]
    try:
        conn = sqlite3.connect(str(file_path))
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        lines.append(f"- **테이블 목록**: `{', '.join(tables)}`")
        for t in tables:
            cnt = cur.execute(f"SELECT COUNT(*) FROM '{t}';").fetchone()[0]
            cols = [c[1] + "(" + c[2] + ")" for c in cur.execute(f"PRAGMA table_info('{t}');").fetchall()]
            lines.append(f"  - `{t}` ({cnt}행): `{', '.join(cols)}`")
        conn.close()
    except Exception as e:
        lines.append(f"- ⚠️ DB 스캔 오류: {e}")
    return "\n".join(lines)


def scan_workspace(root_dir: Path) -> str:
    report = [
        "# 🧭 FDE Autopilot 워크스페이스 & 데이터셋 자동 프로파일링 리포트 (v2.1)",
        f"- **스캔 루트**: `{root_dir}`",
        "",
        "## 1. 디렉토리 및 주요 파일 트리"
    ]

    tree_lines = []
    data_reports = []
    readme_excerpt = []
    dm_triggers: List[str] = []
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

            lower_name = fname.lower()
            if "test" in lower_name or "spec" in lower_name:
                has_existing_tests = True
            if any(k in lower_name for k in ("policy", "manual", "guide", "rule", "sop", "규정", "매뉴얼", "지침")):
                has_policy_docs = True

            if lower_name == "readme.md" and depth == 0:
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    readme_excerpt.append(content[:2500])
                except Exception:
                    pass
            elif lower_name.endswith(".csv"):
                data_reports.append(analyze_csv(fpath, dm_triggers))
            elif lower_name.endswith(".json") and lower_name not in ("package.json", "package-lock.json", "tsconfig.json"):
                data_reports.append(analyze_json(fpath, dm_triggers))
            elif lower_name.endswith((".sqlite", ".db", ".sqlite3")):
                data_reports.append(analyze_sqlite(fpath, dm_triggers))

    report.extend(tree_lines if tree_lines else ["- (파일 없음)"])

    # 범용 아키타입 자동 추천 (특정 도메인 파일명 배제)
    report.append("\n## 2. 문제 해결 아키타입(Archetype) 자동 매핑 추천")
    if data_reports:
        report.append("- 🎯 **추천 아키타입**: **Archetype A (지표 모니터링/대시보드)** 또는 **Archetype B (규칙 검증/Diff 알람)**")
        report.append("  - 로컬 데이터셋이 감지되었습니다. 앞단 `/src/core`의 정합성(결측/중복/임계치 등호)이 채점의 최우선 기준입니다.")
    elif has_policy_docs:
        report.append("- 🎯 **추천 아키타입**: **Archetype C (문서 검색 및 출처 기반 질의응답 / RAG)**")
        report.append("  - 규정/매뉴얼 문서가 감지되었습니다. 환각 차단(Out-of-domain 거절 문구) 및 정확한 조항 번호 인용(Strict Grounding)이 핵심입니다.")
    elif has_existing_tests:
        report.append("- 🎯 **추천 아키타입**: **레거시 디버깅 / Archetype B (규칙 검증 및 Diff 알람)**")
        report.append("  - 기존 테스트 코드가 감지되었습니다. 코드 수정 전 반드시 베이스라인 테스트를 먼저 실행해 로그를 남기세요.")
    else:
        report.append("- 🎯 **추천 아키타입**: **Archetype D (상태 머신 및 승인/백오피스 워크플로우)**")
        report.append("  - 상태 전이(State Machine) 및 웹 백오피스 중심 과제로 추정됩니다.")

    if readme_excerpt:
        report.append("\n## 3. 과제 README.md 핵심 발췌")
        report.append("```markdown\n" + readme_excerpt[0] + "\n```")

    report.append("\n## 4. 데이터셋 스키마·결측치·임계치(3-Sigma) 자동 분석")
    if data_reports:
        report.extend(data_reports)
    else:
        report.append("- 별도의 로컬 CSV/JSON/DB 데이터 파일이 감지되지 않았습니다.")

    report.append("\n## 5. 💬 실무자 에이전트(DM) 최우선 확인 트리거 (자동 도출)")
    if dm_triggers:
        for idx, trig in enumerate(dm_triggers, 1):
            report.append(f"{idx}. {trig}")
    else:
        report.append("1. [경계값 등호 기준] 임계값 판정 시 이상(>=)인지 초과(>)인지 확인")
        report.append("2. [핵심 산출물 우선순위] 1순위로 검증해야 할 핵심 유즈케이스와 제외 가능한 범위(Out-of-Scope) 확인")

    report.append("\n## 6. FDE 80/20 아키텍처 설계 권고 (Codex 컨텍스트 주입용)")
    report.append("- 위 데이터 스캔 결과에서 발견된 **결측치(Null/빈 문자열/센티널 수치)** 처리 로직을 `/src/data` 파서에 반드시 포함할 것.")
    report.append("- 수치형 컬럼의 **min/max 및 3-Sigma(UCL/LCL)** 값을 `/src/core`의 결정론적 임계치 상수로 활용할 것.")
    report.append("- 정상(Mean 부근), 경고(임계치 근접), 위반(임계치 초과 또는 결측/오류 포함) 3종 데이터를 `/src/data/samples.js`의 골든 샘플 프리셋으로 구성할 것.")

    return "\n".join(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root directory")
    parser.add_argument("--out", default=".fde_data_profile.md", help="Output profile markdown path")
    args = parser.parse_args()

    root_path = Path(args.root).resolve()
    result_md = scan_workspace(root_path)
    out_path = Path(args.out).resolve()
    out_path.write_text(result_md, encoding="utf-8")
    print(f"✅ [FDE Autopilot] 데이터 프로파일링 및 DM 트리거 도출 완료: {out_path}")
