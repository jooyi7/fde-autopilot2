#!/usr/bin/env python3
"""
Pre-Submission Release Gatekeeper
제출 직전 코드베이스의 치명적 감점 요인(localhost 하드코딩, 빈 문서, 문법 오류 등)을 점검합니다.
"""
import os
import re
import sys
from pathlib import Path

IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.venv', 'fde-codex-kit'}

def check_workspace(root: Path):
    warnings = []
    passed = []

    # 1. README 및 필수 문서 존재 및 분량 확인
    doc_candidates = list(root.glob("*.md"))
    if not doc_candidates:
        warnings.append("루트 경로에 마크다운(.md) 문서가 하나도 없습니다. 제출 요구사항 문서를 확인하세요.")
    else:
        for doc in doc_candidates:
            size = doc.stat().st_size
            if size < 100:
                warnings.append(f"문서 '{doc.name}'의 크기가 너무 작습니다 ({size} bytes). 내용이 비어있는지 확인하세요.")
            else:
                passed.append(f"문서 확인 완료: {doc.name} ({size} bytes)")

    # 2. 코드 내 localhost 단독 바인딩 및 API 키 하드코딩 검사
    code_exts = {'.js', '.mjs', '.ts', '.tsx', '.jsx', '.py', '.sh'}
    localhost_hits = []
    secret_hits = []

    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            fpath = Path(dirpath) / f
            if fpath.suffix.lower() in code_exts:
                try:
                    content = fpath.read_text(encoding='utf-8', errors='ignore')
                    rel = fpath.relative_to(root)
                    if re.search(r'\.listen\([^)]*["\']localhost["\']', content):
                        localhost_hits.append(str(rel))
                    if re.search(r'sk-[a-zA-Z0-9]{20,}', content):
                        secret_hits.append(str(rel))
                except Exception:
                    pass

    if localhost_hits:
        warnings.append(f"서버가 'localhost'로 바인딩된 코드가 감지되었습니다 (0.0.0.0 권장): {', '.join(localhost_hits)}")
    else:
        passed.append("서버 호스트 바인딩 검사 통과 (localhost 단독 바인딩 없음)")

    if secret_hits:
        warnings.append(f"하드코딩된 API Key 패턴(sk-...)이 감지되었습니다: {', '.join(secret_hits)}")
    else:
        passed.append("하드코딩된 API 시크릿 검사 통과")

    print("=" * 55)
    print("🛡️  FINAL RELEASE GATEKEEPER REPORT")
    print("=" * 55)
    for p in passed:
        print(f"  [OK] {p}")
    for w in warnings:
        print(f"  [WARN] ⚠️  {w}")
    print("=" * 55)

    if warnings:
        print("💡 경고 항목을 확인한 후 에디터 저장 상태(Ctrl+S)를 점검하고 제출하세요.")
    else:
        print("🎉 모든 사전 검증을 통과했습니다! 브라우저 미리보기 최종 확인 후 제출하세요.")

if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    check_workspace(target)