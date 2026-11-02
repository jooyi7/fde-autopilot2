#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$REPO_DIR/.." && pwd)"

echo "===================================================="
echo "🚀 [FDE-Autopilot] Initializing Codex Workspace..."
echo "===================================================="

# 1. [보안 규정 준수] git push 원천 차단 (Outbound 전송 실수 방지)
echo "[1/5] Locking git push (Outbound protection)..."
if git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$REPO_DIR" remote set-url --push origin no_push_allowed_by_exam_rules 2>/dev/null || true
    mkdir -p "$REPO_DIR/.git/hooks"
    cat << 'EOF' > "$REPO_DIR/.git/hooks/pre-push"
#!/usr/bin/env bash
echo "❌ [BLOCKED] 대회 규정상 외부 저장소로의 git push는 엄격히 금지되어 있습니다!"
exit 1
EOF
    chmod +x "$REPO_DIR/.git/hooks/pre-push"
fi
if git -C "$WORKSPACE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$WORKSPACE_ROOT" remote set-url --push origin no_push_allowed_by_exam_rules 2>/dev/null || true
fi
echo " -> Git push is permanently disabled."

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

# 4. 초기 워크스페이스 구조 및 데이터(CSV/JSON) 자동 스캔
echo "[4/5] Scanning workspace & data anomalies..."
if [ -f "$REPO_DIR/engine/workspace_inspector.py" ]; then
    python3 "$REPO_DIR/engine/workspace_inspector.py" "$WORKSPACE_ROOT" > "$WORKSPACE_ROOT/WORKSPACE_PROFILE.md"
elif [ -f "$REPO_DIR/engine/workspace_profiler.py" ]; then
    python3 "$REPO_DIR/engine/workspace_profiler.py" "$WORKSPACE_ROOT" > "$WORKSPACE_ROOT/WORKSPACE_PROFILE.md"
fi
echo " -> Saved scan report to $WORKSPACE_ROOT/WORKSPACE_PROFILE.md"

# 5. 제출용 아키텍처 문서 초안 생성 (덮어쓰기 방지)
echo "[5/5] Preparing submission document templates..."
if [ ! -f "$WORKSPACE_ROOT/SOLUTION_NOTES.md" ] && [ -f "$REPO_DIR/docs_kit/ARCHITECTURE_DECISIONS.md" ]; then
    cp "$REPO_DIR/docs_kit/ARCHITECTURE_DECISIONS.md" "$WORKSPACE_ROOT/SOLUTION_NOTES.md"
fi
if [ ! -f "$WORKSPACE_ROOT/HANDOFF.md" ] && [ -f "$REPO_DIR/docs_kit/HANDOFF_TEMPLATE.md" ]; then
    cp "$REPO_DIR/docs_kit/HANDOFF_TEMPLATE.md" "$WORKSPACE_ROOT/HANDOFF.md"
fi

echo "===================================================="
echo "✅ 세팅 완료! 에디터에서 'fde-autopilot/USER_GUIDE.md'를 여세요."
echo "===================================================="