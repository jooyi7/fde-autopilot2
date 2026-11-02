#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-$(pwd)}"
cd "${TARGET_DIR}"

echo "================================================================"
echo "🏗️ [FDE App Scaffolder] 4-Layer 아키텍처 및 0.0.0.0 서버 뼈대 생성"
echo "================================================================"

# 1. 4대 레이어 디렉토리 구조 생성
mkdir -p src/data src/core src/ai src/components public

# 2. package.json 자동 생성 (0.0.0.0 바인딩 스크립트 포함)
if [ ! -f "package.json" ]; then
cat << 'EOF' > package.json
{
  "name": "fde-mission-app",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5173",
    "start": "vite --host 0.0.0.0 --port 5173",
    "build": "vite build",
    "test:harness": "node /tmp/fde-kit/engine/deterministic_harness.mjs"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.1.4"
  }
}
EOF
echo "✅ package.json 생성 완료 (--host 0.0.0.0 기본 내장)"
fi

# 3. vite.config.js 자동 생성 (0.0.0.0 호스트 강제 바인딩)
if [ ! -f "vite.config.js" ]; then
cat << 'EOF' > vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: false
  }
});
EOF
echo "✅ vite.config.js 생성 완료 (0.0.0.0 바인딩 설정)"
fi

# 4. index.html 엔트리 생성
if [ ! -f "index.html" ]; then
cat << 'EOF' > index.html
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FDE Decision & Analysis Console</title>
  </head>
  <body style="margin: 0; background-color: #f8fafc;">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
EOF
echo "✅ index.html 생성 완료"
fi

# 5. src/main.jsx 엔트리 파일 생성
if [ ! -f "src/main.jsx" ]; then
cat << 'EOF' > src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import MainWorkspaceView from './components/Dashboard.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MainWorkspaceView />
  </React.StrictMode>
);
EOF
echo "✅ src/main.jsx 엔트리 포인트 생성 완료"
fi

echo "================================================================"
echo "🎯 4대 레이어 디렉토리 및 기본 설정 준비 완료!"
echo "   실행 명령어: npm install && npm run dev"
echo "================================================================"
