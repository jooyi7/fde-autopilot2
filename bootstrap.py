#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bootstrap.py
--------------------------------------------------------------------------------
FDE Autopilot Bootstrap & Workspace Initializer (Cross-Platform Python 3.12)

터미널에서 다음과 같이 실행하면 주어진 README.md와 데이터를 자동으로 전수 분석합니다:
    python bootstrap.py --workspace .
    (또는 인자 없이 실행 시 현재 디렉터리 자동 인식)

[수행 단계]
1. [보안] git push 원천 차단 (로컬 commit만 허용)
2. [런타임] Python/Node 버전 확인
3. [설정] AGENTS.md 및 config.toml 배치
4. [데이터 및 문제 자동 분석]
   - README.md 및 파일 구조 분석 (WORKSPACE_PROFILE.md)
   - 데이터셋 결측치/이상치/3-Sigma 프로파일링 (.fde_data_profile.md)
   - 평가지표(정확도 vs 속도) 및 병목(알고리즘 vs HW) 사전 진단 (.autopilot/pre_opt_diagnosis.md)
   - 최적화 기법 후보 제안서 생성 (.fde_optimization_proposal.md)
   - 11대 솔버 자동 파이프라인 실행 (output/result.json)
5. [문서 템플릿] SPEC.md, SOLUTION_NOTES.md, HANDOFF.md 준비
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None, ignore_error=True):
    try:
        res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
        return res.returncode == 0, res.stdout, res.stderr
    except Exception as e:
        if not ignore_error:
            raise
        return False, "", str(e)


def bootstrap(workspace_dir: str = "."):
    repo_dir = Path(__file__).resolve().parent
    workspace_root = Path(workspace_dir).resolve()

    print("=" * 64)
    print("🚀 [FDE-Autopilot] Initializing & Profiling Workspace...")
    print(f"   • 작업 경로: {workspace_root}")
    print("=" * 64)

    # 1. git push 차단
    print("\n[1/5] Locking git push (Outbound security protection)...")
    git_dir = workspace_root / ".git"
    if git_dir.exists() and git_dir.is_dir():
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_file = hooks_dir / "pre-push"
        hook_script = "#!/usr/bin/env bash\necho '❌ [BLOCKED] 응시 규정상 git push는 금지되어 있습니다. (로컬 commit만 수행)'\nexit 1\n"
        try:
            hook_file.write_text(hook_script, encoding="utf-8")
        except Exception:
            pass
        run_command(["git", "remote", "set-url", "--push", "origin", "no_push_allowed_by_exam_rules"], cwd=str(workspace_root))
        print("  -> Git push disabled successfully (Local commit only).")
    else:
        print("  -> No local .git repository found (Skipped push lock).")

    # 2. 런타임 확인
    print("\n[2/5] Checking Runtime Versions...")
    print(f"  -> Python: {sys.version.split()[0]}")
    ok_node, out_node, _ = run_command(["node", "-v"])
    if ok_node:
        print(f"  -> Node.js: {out_node.strip()}")
    else:
        print("  -> Node.js: not detected (Vite web server will require Node)")

    # 3. AGENTS.md & config.toml 워크스페이스 배치
    print("\n[3/5] Deploying AGENTS.md & config.toml to workspace root...")
    for cfg_name in ["AGENTS.md", "config.toml"]:
        src_cfg = repo_dir / cfg_name
        dst_cfg = workspace_root / cfg_name
        if src_cfg.exists() and not dst_cfg.exists():
            shutil.copy2(src_cfg, dst_cfg)
            print(f"  ✅ {cfg_name} 배치 완료")

    # 4. 초기 워크스페이스 구조 및 데이터(CSV/JSON/DB/README) 자동 스캔 & 프로파일링
    print("\n[4/5] Scanning workspace & profiling data anomalies...")
    autopilot_dir = workspace_root / ".autopilot"
    autopilot_dir.mkdir(parents=True, exist_ok=True)

    py_bin = sys.executable

    # 4-1. workspace_inspector.py (README.md 및 디렉터리 트리 분석)
    inspector_py = repo_dir / "engine" / "workspace_inspector.py"
    if inspector_py.exists():
        ok, out, _ = run_command([py_bin, str(inspector_py), str(workspace_root)])
        if ok and out:
            profile_md = workspace_root / "WORKSPACE_PROFILE.md"
            profile_md.write_text(out, encoding="utf-8")
            shutil.copy2(profile_md, autopilot_dir / "workspace_scan.md")
            print("  ✅ [1/5] README.md 및 파일 구조 분석 완료 -> WORKSPACE_PROFILE.md")

    # 4-2. workspace_profiler.py (데이터 결측치, -999, 3-Sigma 프로파일링)
    profiler_py = repo_dir / "engine" / "workspace_profiler.py"
    if profiler_py.exists():
        out_profile = workspace_root / ".fde_data_profile.md"
        ok, _, _ = run_command([py_bin, str(profiler_py), "--root", str(workspace_root), "--out", str(out_profile)])
        if out_profile.exists():
            shutil.copy2(out_profile, autopilot_dir / "workspace_profile.md")
            print("  ✅ [2/5] 데이터 결측치/이상치 프로파일링 완료 -> .fde_data_profile.md")

    # 4-3. pre_opt_diagnostician.py (정확도 vs 속도 & 알고리즘 vs HW 병목 사전 진단)
    diag_py = repo_dir / "engine" / "pre_opt_diagnostician.py"
    if diag_py.exists():
        run_command([py_bin, str(diag_py), "--workspace", str(workspace_root)])
        print("  ✅ [3/5] 평가지표(정확도vs속도) & 병목 사전 진단 완료 -> .autopilot/pre_opt_diagnosis.md")

    # 4-4. optimizer_menu.py (최적화 기법 후보 제안서)
    opt_py = repo_dir / "engine" / "optimizer_menu.py"
    if opt_py.exists():
        run_command([py_bin, str(opt_py), "--workspace", str(workspace_root), "--propose"])
        print("  ✅ [4/5] 최적화 기법 후보 제안서 생성 완료 -> .fde_optimization_proposal.md")

    # 4-5. auto_solver_pipeline.py (도메인 감지 및 솔버 자동 실행)
    pipeline_py = repo_dir / "engine" / "auto_solver_pipeline.py"
    if pipeline_py.exists():
        run_command([py_bin, str(pipeline_py), "--workspace", str(workspace_root)])
        print("  ✅ [5/5] 솔버 자동 파이프라인 실행 완료 -> output/result.json")

    # 5. 제출용 문서 초안 생성
    print("\n[5/5] Preparing submission document templates...")
    doc_templates = {
        "SPEC.md": "SPEC_TEMPLATE.md",
        "SOLUTION_NOTES.md": "ARCHITECTURE_DECISIONS.md",
        "HANDOFF.md": "HANDOFF_TEMPLATE.md",
    }
    for doc_name, tmpl_name in doc_templates.items():
        dst_doc = workspace_root / doc_name
        src_tmpl = repo_dir / "docs_kit" / tmpl_name
        if not dst_doc.exists() and src_tmpl.exists():
            shutil.copy2(src_tmpl, dst_doc)
            print(f"  ✅ {doc_name} 템플릿 준비 완료")

    print("\n" + "=" * 64)
    print("🎯 [완료] 워크스페이스 및 데이터 분석이 성공적으로 완료되었습니다!")
    print("   📄 생성된 분석 리포트:")
    print("      • WORKSPACE_PROFILE.md       : README.md 및 문제 구조 요약")
    print("      • .fde_data_profile.md       : 데이터셋 결측치/이상치 프로파일")
    print("      • .autopilot/pre_opt_diagnosis.md : 평가지표(정확도/속도) & 병목 진단")
    print("      • .fde_optimization_proposal.md   : 추천 최적화 방식 후보 리스트")
    print("      • output/result.json         : 1차 솔버 연산 결과")
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(description="FDE Autopilot Bootstrap (Python)")
    parser.add_argument("--workspace", default=".", help="Target workspace root (default: current directory)")
    args = parser.parse_args()

    bootstrap(workspace_dir=args.workspace)


if __name__ == "__main__":
    main()

