#!/usr/bin/env python3
"""
Workspace Inspector & Data Profiler
과제 시작 시 기존 코드베이스 구조와 데이터 파일(CSV, JSON, MD)의 스키마 및 이상치를 즉시 스캔합니다.
"""
import os
import sys
import json
import csv
from pathlib import Path

IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.next', '.venv', 'fde-codex-kit'}

def scan_tree(root_path: Path):
    tree_lines = []
    data_files = []
    doc_files = []
    config_files = []

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        rel_root = Path(root).relative_to(root_path)
        level = 0 if str(rel_root) == '.' else len(rel_root.parts)
        indent = "  " * level
        if str(rel_root) != '.':
            tree_lines.append(f"{indent}📂 {rel_root.name}/")
        
        for f in sorted(files):
            fpath = Path(root) / f
            rel_fpath = fpath.relative_to(root_path)
            size_kb = fpath.stat().st_size / 1024.0
            tree_lines.append(f"{indent}  📄 {f} ({size_kb:.1f} KB)")
            
            ext = fpath.suffix.lower()
            if ext in {'.csv', '.json', '.jsonl', '.tsv'}:
                if f not in {'package.json', 'package-lock.json', 'tsconfig.json'}:
                    data_files.append(rel_fpath)
            elif ext in {'.md', '.txt'}:
                doc_files.append(rel_fpath)
            elif f in {'package.json', 'requirements.txt', 'pyproject.toml'}:
                config_files.append(rel_fpath)

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

    print("## 2. Project Dependencies & Scripts")
    for cfg in config_files:
        full_cfg = target_dir / cfg
        print(f"### `{cfg}`")
        print("```")
        with open(full_cfg, 'r', encoding='utf-8', errors='replace') as fp:
            print(fp.read()[:1500])
        print("```\n")

    print("## 3. Data Assets & Anomaly Scan (EDA)")
    if not data_files:
        print("- No standalone data files (.csv, .json) detected.\n")
    for df in data_files[:10]:
        full_df = target_dir / df
        print(f"### 📊 `{df}`")
        if full_df.suffix.lower() == '.csv':
            info = inspect_csv(full_df)
        else:
            info = inspect_json(full_df)
        print("```json")
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print("```\n")

    print("## 4. Problem Statements & Docs Preview")
    for doc in doc_files:
        if doc.name in {'WORKSPACE_PROFILE.md', 'SOLUTION_NOTES.md', 'AGENTS.md'}:
            continue
        full_doc = target_dir / doc
        print(f"### 📖 `{doc}`")
        with open(full_doc, 'r', encoding='utf-8', errors='replace') as fp:
            content = fp.read()
            print(content[:2000])
            if len(content) > 2000:
                print("\n... [Truncated] ...")
        print("\n---\n")

if __name__ == "__main__":
    main()