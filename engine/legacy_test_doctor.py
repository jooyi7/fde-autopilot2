#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - Legacy Codebase & Existing Test Contract Doctor (legacy_test_doctor.py v5.0)
과제가 빈 폴더가 아니라 '기존 레거시 코드 디버깅 + 기존 테스트(Jest/Vitest/Mocha/Pytest/Node Test) 통과' 형태로
주어졌을 때, 기존 테스트 파일들을 정밀 스캔하여:
1) 테스트가 import/호출하는 정확한 파일 경로와 함수명/클래스명
2) 테스트가 호출하는 HTTP API 엔드포인트(GET/POST /api/...)
3) 테스트가 assert/expect로 검증하는 필수 반환 JSON 키와 상태 코드
를 자동으로 추출해 `.autopilot/legacy_test_contract.md`에 정리합니다.
"""

import argparse
import os
import re
from pathlib import Path
from typing import List

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "__pycache__",
    ".venv", "venv", "fde-autopilot", "fde-kit", ".fde_audit_cache", ".autopilot", "engine"
}


def scan_existing_tests(root: Path) -> str:
    test_files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        rel_dir = Path(dirpath).relative_to(root)
        is_test_dir = any(p.lower() in {"test", "tests", "__tests__", "spec", "specs"} for p in rel_dir.parts)
        for fname in sorted(filenames):
            lower = fname.lower()
            if is_test_dir or any(tok in lower for tok in (".test.", ".spec.", "test_", "_test.py")):
                if lower.endswith((".js", ".mjs", ".ts", ".tsx", ".jsx", ".py")):
                    test_files.append(Path(dirpath) / fname)

    lines = [
        "# 🩺 레거시 테스트 및 API 계약 자동 역추적 리포트 (`legacy_test_contract.md`)",
        f"- **스캔 루트**: `{root}`",
        f"- **발견된 기존 테스트 파일 수**: {len(test_files)}개",
        "",
    ]

    if not test_files:
        lines.append("- ℹ️ 기존에 작성된 단위/통합 테스트 파일이 감지되지 않았습니다 (Greenfield 신규 구축 모드).")
        return "\n".join(lines)

    lines.append("> 🚨 **절대 주의 (Legacy Compatibility Guard)**: 아래 테스트 파일들이 요구하는 파일 경로, export 함수명, API 라우트 및 반환 키 이름을 절대 변경하거나 깨뜨리지 마십시오!")
    lines.append("")

    import_re = re.compile(r"(?:import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\)|from\s+([A-Za-z0-9_.]+)\s+import\s+([^\n]+))")
    route_re = re.compile(r"['\"](/api/[A-Za-z0-9_\-/]+)['\"]")
    expect_prop_re = re.compile(r"(?:toHaveProperty|assert\s+['\"]([A-Za-z0-9_]+)['\"]\s+in|\.([A-Za-z0-9_]+)\s*(?:===|==|!==|!=))")

    for tf in test_files[:15]:
        rel = tf.relative_to(root)
        lines.append(f"## 🧪 테스트 파일: `{rel}`")
        try:
            content = tf.read_text(encoding="utf-8", errors="ignore")
            imports = []
            for m in import_re.findall(content):
                imp = next((x for x in m if x), "")
                if imp:
                    imports.append(imp)
            routes = list(dict.fromkeys(route_re.findall(content)))
            props = list(dict.fromkeys([m[0] or m[1] for m in expect_prop_re.findall(content) if (m[0] or m[1])]))

            if imports:
                lines.append(f"- **참조/Import 대상 모듈**: `{', '.join(dict.fromkeys(imports[:10]))}`")
            if routes:
                lines.append(f"- **검증 대상 API 라우트**: `{', '.join(routes[:10])}`")
            if props:
                lines.append(f"- **검증 대상 응답 속성/필드**: `{', '.join(props[:15])}`")
            lines.append("- **테스트 코드 핵심 발췌**:")
            lines.append("```")
            lines.append(content[:1200])
            lines.append("```\n")
        except Exception as e:
            lines.append(f"- ⚠️ 읽기 실패: {e}\n")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root")
    parser.add_argument("--out", default=".autopilot/legacy_test_contract.md", help="Output markdown path")
    args = parser.parse_args()

    root_path = Path(args.root).resolve()
    report_md = scan_existing_tests(root_path)
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")
    print(f"✅ [Legacy Test Doctor v5.0] 기존 테스트 계약 스캔 완료 -> {out_path}")

