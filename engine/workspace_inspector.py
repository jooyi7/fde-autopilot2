#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine/workspace_inspector.py
--------------------------------------------------------------------------------
Workspace Automated Inspection Engine (Cross-Platform)

과제 시작 시 시험 환경의 파일 구조, 데이터 파일(CSV, JSON), 과제 지문(README.md)을
상대 경로 기준으로 깔끔하게 스캔하여 WORKSPACE_PROFILE.md를 생성합니다.
(외부/절대 경로 하드코딩 0%, 대용량 가이드 파일 노이즈 스킵)
"""

import csv
import json
import os
import sys
from pathlib import Path

IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', 'dist', 'build', '.next', '.venv',
    'fde-codex-kit', '.autopilot', 'docs_kit', 'prompt_bank'
}

SKIP_DOC_NAMES = {
    'WORKSPACE_PROFILE.md', 'SOLUTION_NOTES.md', 'AGENTS.md', 'AUDITOR_GUIDE.md',
    'fde_autopilot_manual.md', 'SPEC.md', 'HANDOFF.md', 'SPEC_TEMPLATE.md',
    'ARCHITECTURE_DECISIONS.md', 'HANDOFF_TEMPLATE.md', 'defense_logic_guide.md',
    'stakeholder_inquiry_guide.md', 'typing_guide.md', 'step_by_step_prompts.md'
}


def scan_tree(root_path: Path):
    tree_lines = []
    data_files = []
    doc_files = []
    config_files = []

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in sorted(dirs) if d not in IGNORE_DIRS]
        rel_root = Path(root).relative_to(root_path)
        level = 0 if str(rel_root) == '.' else len(rel_root.parts)
        indent = "  " * level
        if str(rel_root) != '.':
            posix_dirname = str(rel_root.name).replace('\\', '/')
            tree_lines.append(f"{indent}📂 {posix_dirname}/")

        for f in sorted(files):
            fpath = Path(root) / f
            rel_fpath = fpath.relative_to(root_path)
            posix_rel = str(rel_fpath).replace('\\', '/')
            size_kb = fpath.stat().st_size / 1024.0
            tree_lines.append(f"{indent}  📄 {f} ({size_kb:.1f} KB)")

            ext = fpath.suffix.lower()
            if ext in {'.csv', '.json', '.jsonl', '.tsv'}:
                if f not in {'package.json', 'package-lock.json', 'tsconfig.json', 'result.json', 'cofa_probe_report.json', 'pre_opt_diagnosis_report.json', 'optimizer_proposals.json'}:
                    data_files.append(posix_rel)
            elif ext in {'.md', '.txt'}:
                if f not in SKIP_DOC_NAMES:
                    doc_files.append(posix_rel)
            elif f in {'package.json', 'requirements.txt', 'pyproject.toml', 'config.toml'}:
                config_files.append(posix_rel)

    return tree_lines, data_files, doc_files, config_files


def inspect_csv(fpath: Path):
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as fp:
            reader = csv.reader(fp)
            headers = next(reader, [])
            rows = []
            null_counts = {h: 0 for h in headers}
            total_rows = 0
            for r in reader:
                total_rows += 1
                if len(rows) < 3:
                    rows.append(r)
                for idx, val in enumerate(r):
                    if idx < len(headers) and (val.strip() == '' or val.strip().lower() in {'null', 'nan', 'none', 'na'}):
                        null_counts[headers[idx]] += 1
            return {
                "type": "CSV",
                "total_rows": total_rows,
                "columns": headers,
                "null_summary": {k: v for k, v in null_counts.items() if v > 0},
                "sample": rows[:2]
            }
    except Exception as e:
        return {"error": str(e)}


def inspect_json(fpath: Path):
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as fp:
            data = json.load(fp)
            if isinstance(data, list):
                sample = data[0] if len(data) > 0 else {}
                keys = list(sample.keys()) if isinstance(sample, dict) else ["primitive_list"]
                return {"type": "JSON_ARRAY", "count": len(data), "keys": keys, "sample": sample}
            elif isinstance(data, dict):
                return {"type": "JSON_OBJECT", "top_keys": list(data.keys())[:15]}
            return {"type": "JSON_OTHER"}
    except Exception as e:
        return {"error": str(e)}


def main():
    target_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    tree_lines, data_files, doc_files, config_files = scan_tree(target_dir)

    print("# 🔍 Workspace Automated Inspection Report\n")

    print("## 1. Directory Structure")
    print("```text")
    print("\n".join(tree_lines[:80]))
    if len(tree_lines) > 80:
        print(f"... (+{len(tree_lines) - 80} more entries)")
    print("```\n")

    print("## 2. Project Configurations")
    for cfg in config_files[:5]:
        full_cfg = target_dir / cfg
        if full_cfg.exists():
            print(f"### `{cfg}`")
            print("```")
            try:
                with open(full_cfg, 'r', encoding='utf-8', errors='replace') as fp:
                    content = fp.read()[:800]
                    print(content)
            except Exception:
                pass
            print("```\n")

    print("## 3. Data Assets & Anomaly Summary")
    if not data_files:
        print("- No standalone data files (.csv, .json) detected in root. (Will use embedded samples or auto-pipeline)\n")
    for df in data_files[:10]:
        full_df = target_dir / df
        if full_df.exists():
            print(f"### 📊 `{df}`")
            if full_df.suffix.lower() == '.csv':
                info = inspect_csv(full_df)
            else:
                info = inspect_json(full_df)
            print("```json")
            print(json.dumps(info, ensure_ascii=False, indent=2))
            print("```\n")

    print("## 4. Problem Statement & Instructions Preview")
    if not doc_files:
        print("- No specific challenge problem statement (e.g. README.md) detected. Check repository root.\n")
    for doc in doc_files[:3]:
        full_doc = target_dir / doc
        if full_doc.exists():
            print(f"### 📖 `{doc}`")
            try:
                with open(full_doc, 'r', encoding='utf-8', errors='replace') as fp:
                    content = fp.read()
                    print(content[:1500])
                    if len(content) > 1500:
                        print("\n... [Truncated for brevity] ...")
            except Exception:
                pass
            print("\n---\n")


if __name__ == "__main__":
    main()
