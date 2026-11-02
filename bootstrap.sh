#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="${1:-$(cd "$REPO_DIR/.." && pwd)}"
if [ "$1" = "--workspace" ] && [ -n "$2" ]; then
    WORKSPACE_ROOT="$(cd "$2" && pwd)"
fi

echo "===================================================="
echo "🚀 [FDE-Autopilot] Initializing Codex Workspace..."
echo "===================================================="

# 1. [보안 규정 준수] git push 원천 차단 (Outbound 전송 실수 방지)
echo "[1/5] Locking git push (Outbound protection)..."
for target_git in "$REPO_DIR" "$WORKSPACE_ROOT"; do
    if git -C "$target_git" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git -C "$target_git" remote set-url --push origin no_push_allowed_by_exam_rules 2>/dev/null || true
        mkdir -p "$target_git/.git/hooks"
        cat << 'EOF' > "$target_git/.git/hooks/pre-push"
#!/usr/bin/env bash
echo "❌ [BLOCKED] 응시 규정상 외부 저장소로의 git push는 엄격히 금지되어 있습니다! (로컬 git commit만 수행하세요)"
exit 1
EOF
        chmod +x "$target_git/.git/hooks/pre-push"
    fi
done
echo " -> Git push is permanently disabled (Local git commit is enabled)."

# 2. 런타임 버전 확인
echo "[2/5] Checking Runtime Versions..."
node -v 2>/dev/null || echo "Node.js not detected"
python3 --version 2>/dev/null || echo "Python3 not detected"

# 3. AGENTS.md 및 config.toml 워크스페이스 루트 배치
echo "[3/5] Deploying AGENTS.md & config.toml to workspace root..."
if [ ! -f "$WORKSPACE_ROOT/AGENTS.md" ] && [ -f "$REPO_DIR/AGENTS.md" ]; then
    cp "$REPO_DIR/AGENTS.md" "$WORKSPACE_ROOT/AGENTS.md"
fi
if [ ! -f "$WORKSPACE_ROOT/config.toml" ] && [ -f "$REPO_DIR/config.toml" ]; then
    cp "$REPO_DIR/config.toml" "$WORKSPACE_ROOT/config.toml"
fi

# 4. 초기 워크스페이스 구조 및 데이터(CSV/JSON/DB) 자동 스캔 & 프로파일링
echo "[4/5] Scanning workspace & profiling data anomalies..."
mkdir -p "$WORKSPACE_ROOT/.autopilot"
if [ -f "$REPO_DIR/engine/workspace_inspector.py" ]; then
    python3 "$REPO_DIR/engine/workspace_inspector.py" "$WORKSPACE_ROOT" > "$WORKSPACE_ROOT/WORKSPACE_PROFILE.md"
    cp "$WORKSPACE_ROOT/WORKSPACE_PROFILE.md" "$WORKSPACE_ROOT/.autopilot/workspace_scan.md" 2>/dev/null || true
fi
if [ -f "$REPO_DIR/engine/workspace_profiler.py" ]; then
    python3 "$REPO_DIR/engine/workspace_profiler.py" --root "$WORKSPACE_ROOT" --out "$WORKSPACE_ROOT/.fde_data_profile.md"
    cp "$WORKSPACE_ROOT/.fde_data_profile.md" "$WORKSPACE_ROOT/.autopilot/workspace_profile.md" 2>/dev/null || true
fi
echo " -> Saved scan & profile reports (.fde_data_profile.md & .autopilot/workspace_profile.md)"

# 5. 제출용 문서 초안 생성 (덮어쓰기 방지)
echo "[5/5] Preparing submission document templates..."
if [ ! -f "$WORKSPACE_ROOT/SPEC.md" ] && [ -f "$REPO_DIR/docs_kit/SPEC_TEMPLATE.md" ]; then
    cp "$REPO_DIR/docs_kit/SPEC_TEMPLATE.md" "$WORKSPACE_ROOT/SPEC.md"
fi
if [ ! -f "$WORKSPACE_ROOT/SOLUTION_NOTES.md" ] && [ -f "$REPO_DIR/docs_kit/ARCHITECTURE_DECISIONS.md" ]; then
    cp "$REPO_DIR/docs_kit/ARCHITECTURE_DECISIONS.md" "$WORKSPACE_ROOT/SOLUTION_NOTES.md"
fi
if [ ! -f "$WORKSPACE_ROOT/HANDOFF.md" ] && [ -f "$REPO_DIR/docs_kit/HANDOFF_TEMPLATE.md" ]; then
    cp "$REPO_DIR/docs_kit/HANDOFF_TEMPLATE.md" "$WORKSPACE_ROOT/HANDOFF.md"
fi

echo "===================================================="
echo "✅ 세팅 완료! 에디터에서 'fde_autopilot.md'와 '.fde_data_profile.md'를 확인하세요."
echo "===================================================="
