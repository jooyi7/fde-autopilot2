#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="."
STACK="nextjs"
DOMAIN="OVERLAY"

# config.toml에서 default_type 및 default_host 자동 추출 (미지정 시 fallback "A" / "0.0.0.0")
CONFIG_FILE="${TARGET_DIR}/config.toml"
APP_TYPE="A"
DEFAULT_HOST="0.0.0.0"

if [ -f "${CONFIG_FILE}" ]; then
  PARSED_TYPE=$(grep -E '^[[:space:]]*default_type[[:space:]]*=' "${CONFIG_FILE}" 2>/dev/null | head -n1 | sed -E 's/.*=[[:space:]]*["'\'']?([A-Za-z0-9_]+)["'\'']?.*/\1/' || true)
  if [ -n "${PARSED_TYPE}" ]; then
    APP_TYPE="${PARSED_TYPE^^}"
  fi
  PARSED_HOST=$(grep -E '^[[:space:]]*default_host[[:space:]]*=' "${CONFIG_FILE}" 2>/dev/null | head -n1 | sed -E 's/.*=[[:space:]]*["'\'']?([0-9.]+:)?[0-9.]+["'\'']?.*/\1/' || true)
  if [ -n "${PARSED_HOST}" ]; then
    DEFAULT_HOST="${PARSED_HOST}"
  fi
fi

# 위치 인자 및 플래그 인자(--target, --type, --stack, --domain) 모두 호환 지원
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET_DIR="$2"
      shift 2
      ;;
    --type)
      APP_TYPE="$2"
      shift 2
      ;;
    --stack)
      STACK="$2"
      shift 2
      ;;
    --domain)
      DOMAIN="$(echo "$2" | tr '[:lower:]' '[:upper:]')"
      shift 2
      ;;
    *)
      if [[ "$TARGET_DIR" == "." && ! "$1" =~ ^- ]]; then
        TARGET_DIR="$1"
      fi
      shift
      ;;
  esac
done

mkdir -p "${TARGET_DIR}"
cd "${TARGET_DIR}"

echo "================================================================"
echo "🏗️ [FDE App Scaffolder v4.0] 4-Layer 아키텍처 (Type: ${APP_TYPE}, Domain: ${DOMAIN}) 및 0.0.0.0 서버 뼈대 생성"
echo "================================================================"

# 1. 4대 레이어 디렉토리 구조 생성
mkdir -p src/data src/core src/ai src/components public

# 2. package.json 자동 생성 (0.0.0.0 바인딩 스크립트 및 상대/절대 호환 하네스 경로 포함)
if [ ! -f "package.json" ]; then
cat << EOF > package.json
{
  "name": "fde-mission-app",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5173",
    "start": "vite --host 0.0.0.0 --port 5173",
    "build": "vite build",
    "test:harness": "node engine/deterministic_harness.mjs"
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

# 3. vite.config.js 자동 생성 (0.0.0.0 호스트 강제 바인딩 + Python 5대 도메인 솔버 /api/solve 브릿지 내장)
if [ ! -f "vite.config.js" ]; then
cat << 'EOF' > vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

function fdePythonSolverBridge() {
  return {
    name: 'fde-python-solver-bridge',
    configureServer(server) {
      server.middlewares.use('/api/solve', (req, res, next) => {
        if (req.method !== 'POST') return next();
        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', () => {
          try {
            const payload = JSON.parse(body || '{}');
            const domain = String(payload.domain || 'OVERLAY').toUpperCase();
            const solverMap = {
              OVERLAY: 'solver_overlay.py',
              MATERIAL: 'solver_material.py',
              MARKET: 'solver_market.py',
              VALUE_CHAIN: 'solver_value_chain_biz.py',
              EDUCATOR: 'solver_curriculum.py',
              UNIVERSAL: 'solver_universal.py',
              TYPE_A: 'solver_typeA.py',
              TYPE_B: 'solver_typeB.py',
              TYPE_C: 'solver_typeC.py',
              TYPE_D: 'solver_typeD.py',
              TYPE_E: 'solver_typeE.py',
            };
            const scriptName = solverMap[domain] || 'solver_universal.py';
            const scriptPath = path.resolve(process.cwd(), 'engine', scriptName);
            const tmpIn = path.join(os.tmpdir(), `fde_in_${Date.now()}.json`);
            const tmpOut = path.join(os.tmpdir(), `fde_out_${Date.now()}.json`);
            fs.writeFileSync(tmpIn, JSON.stringify(payload), 'utf-8');
            const pyBin = process.platform === 'win32' ? 'python' : 'python3';
            execFile(pyBin, [scriptPath, tmpIn, tmpOut], { timeout: 5000 }, (err) => {
              res.setHeader('Content-Type', 'application/json');
              if (!err && fs.existsSync(tmpOut)) {
                res.end(fs.readFileSync(tmpOut, 'utf-8'));
              } else {
                res.end(JSON.stringify({ fallbackToJsCore: true, error: err?.message || 'Python bridge skipped' }));
              }
              try { fs.unlinkSync(tmpIn); fs.unlinkSync(tmpOut); } catch (_) {}
            });
          } catch (e) {
            res.statusCode = 400;
            res.end(JSON.stringify({ error: e.message }));
          }
        });
      });

      // Endpoint 2: /api/export-result -> writes output/result.json directly to workspace disk
      server.middlewares.use('/api/export-result', (req, res, next) => {
        if (req.method !== 'POST') return next();
        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', () => {
          try {
            const outDir = path.resolve(process.cwd(), 'output');
            fs.mkdirSync(outDir, { recursive: true });
            const outFile = path.join(outDir, 'result.json');
            fs.writeFileSync(outFile, body, 'utf-8');
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ ok: true, savedTo: outFile }));
          } catch (e) {
            res.statusCode = 500;
            res.end(JSON.stringify({ ok: false, error: e.message }));
          }
        });
      });

      // Endpoint 3: /api/workspace-data -> auto-loads local CSV/JSON/MD files and invokes auto_solver_pipeline.py
      server.middlewares.use('/api/workspace-data', (req, res, next) => {
        if (req.method !== 'GET') return next();
        try {
          const root = process.cwd();
          const pyBin = process.platform === 'win32' ? 'python' : 'python3';
          const pipelineScript = path.resolve(root, 'engine', 'auto_solver_pipeline.py');
          const resultFile = path.resolve(root, 'output', 'result.json');

          const respondFromDisk = () => {
            let pythonResult = null;
            if (fs.existsSync(resultFile)) {
              try { pythonResult = JSON.parse(fs.readFileSync(resultFile, 'utf-8')); } catch (_) {}
            }
            const rawDetected = String(pythonResult?.detected_domain || pythonResult?.domain || 'UNIVERSAL').toUpperCase();
            const detectedDomain = rawDetected === 'UNIVERSAL_OPS' ? 'UNIVERSAL' : rawDetected;

            if (pythonResult && pythonResult.shaped_input_payload) {
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({
                sourceFile: pythonResult.source || 'auto_solver_pipeline',
                detectedDomain,
                pythonResult: pythonResult.solution || pythonResult,
                payload: {
                  ...pythonResult.shaped_input_payload,
                  domain: detectedDomain,
                },
              }));
              return;
            }

            const scanDirs = [root, path.join(root, 'data'), path.join(root, 'dataset'), path.join(root, 'datasets'), path.join(root, 'input')];
            let records = [];
            let documents = [];
            let sourceFile = '';
            for (const d of scanDirs) {
              if (!fs.existsSync(d) || !fs.statSync(d).isDirectory()) continue;
              for (const f of fs.readdirSync(d)) {
                const full = path.join(d, f);
                if (!fs.statSync(full).isFile()) continue;
                if (f.endsWith('.json') && !['package.json', 'package-lock.json', 'tsconfig.json', 'result.json'].includes(f)) {
                  try {
                    const parsed = JSON.parse(fs.readFileSync(full, 'utf-8'));
                    if (Array.isArray(parsed) && parsed.length > 0 && records.length === 0) {
                      records = parsed.slice(0, 200);
                      sourceFile = f;
                    }
                  } catch (_) {}
                } else if (f.endsWith('.csv') && records.length === 0) {
                  try {
                    const lines = fs.readFileSync(full, 'utf-8').split(/\r?\n/).filter(Boolean);
                    if (lines.length >= 2) {
                      const headers = lines[0].split(',').map((h) => h.trim());
                      records = lines.slice(1, 201).map((ln) => {
                        const cols = ln.split(',');
                        return Object.fromEntries(headers.map((h, i) => [h, (cols[i] || '').trim()]));
                      });
                      sourceFile = f;
                    }
                  } catch (_) {}
                } else if (f.endsWith('.md') && !['AGENTS.md', 'AUDITOR_GUIDE.md', 'fde_autopilot_manual.md', 'SPEC.md', 'HANDOFF.md', 'SOLUTION_NOTES.md'].includes(f)) {
                  try {
                    documents.push({ id: f, title: f, content: fs.readFileSync(full, 'utf-8').slice(0, 1200) });
                  } catch (_) {}
                }
              }
            }
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({
              sourceFile: sourceFile || 'workspace_auto_scan',
              detectedDomain,
              pythonResult: pythonResult?.solution || pythonResult,
              payload: records.length > 0 || documents.length > 0
                ? { domain: detectedDomain, records, documents, query: '핵심 기준 및 조치 규정' }
                : null,
            }));
          };

          if (fs.existsSync(pipelineScript)) {
            execFile(pyBin, [pipelineScript, '--workspace', root, '--out', resultFile], { timeout: 6000 }, () => {
              respondFromDisk();
            });
          } else {
            respondFromDisk();
          }
        } catch (e) {
          res.statusCode = 500;
          res.end(JSON.stringify({ error: e.message }));
        }
      });

      // Endpoint 4: /api/ai-expert -> Real LLM Proxy Bridge (Sol-6.1 / Terra-5.6 / Luna-6) with 1.5s Hard Timeout & SOP Fallback
      server.middlewares.use('/api/ai-expert', (req, res, next) => {
        if (req.method !== 'POST') return next();
        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', async () => {
          res.setHeader('Content-Type', 'application/json');
          try {
            const payload = JSON.parse(body || '{}');
            const coreOutput = payload.coreOutput || {};
            let model = String(payload.model || process.env.DEFAULT_MODEL || 'Sol-6.1');
            if (model.toLowerCase().includes('astra')) model = 'Sol-6.1';

            const baseUrl = process.env.OPENAI_BASE_URL || process.env.OPENAI_API_BASE || process.env.LLM_BASE_URL || '';
            const apiKey = process.env.OPENAI_API_KEY || process.env.LLM_API_KEY || '';

            if (baseUrl && apiKey && typeof fetch === 'function') {
              const ctrl = new AbortController();
              const timer = setTimeout(() => ctrl.abort(), 1500);
              const llmResp = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${apiKey}`
                },
                body: JSON.stringify({
                  model,
                  temperature: 0.1,
                  max_tokens: 350,
                  messages: [
                    {
                      role: 'system',
                      content: 'You are an Enterprise & Semiconductor AI Expert. Summarize the deterministic core verdict, root cause, and SOP action concisely in Korean.'
                    },
                    {
                      role: 'user',
                      content: JSON.stringify(coreOutput).slice(0, 2000)
                    }
                  ]
                }),
                signal: ctrl.signal
              });
              clearTimeout(timer);
              if (llmResp.ok) {
                const data = await llmResp.json();
                const text = data?.choices?.[0]?.message?.content;
                if (text) {
                  res.end(JSON.stringify({
                    source: 'LIVE_COFA_LLM_GATEWAY',
                    modelUsed: model,
                    summary: text.trim()
                  }));
                  return;
                }
              }
            }
            res.end(JSON.stringify({ fallback: true, modelUsed: model }));
          } catch (e) {
            res.end(JSON.stringify({ fallback: true, error: e.message }));
          }
        });
      });
    }
  };
}

export default defineConfig({
  plugins: [react(), fdePythonSolverBridge()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: false
  }
});
EOF
echo "✅ vite.config.js 생성 완료 (0.0.0.0 바인딩 + /api/solve Python 솔버 브릿지 탑재)"
fi

# 4. index.html 엔트리 생성
if [ ! -f "index.html" ]; then
cat << 'EOF' > index.html
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FDE AI Expert Decision Console</title>
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

# 6. 5대 반도체 도메인 완제품 JS 템플릿(samples.js, rules.js, reporter.js, Dashboard.jsx) 자동 복사
TEMPLATE_DIR="${SCRIPT_DIR}/js_templates"
if [ -d "${TEMPLATE_DIR}" ]; then
  if [ ! -f "src/data/samples.js" ] && [ -f "${TEMPLATE_DIR}/samples.js" ]; then
    cp "${TEMPLATE_DIR}/samples.js" "src/data/samples.js"
    echo "✅ src/data/samples.js (5대 도메인 3종 골든 샘플 & 퍼지 스키마 파서) 배치 완료"
  fi
  if [ ! -f "src/core/rules.js" ] && [ -f "${TEMPLATE_DIR}/rules.js" ]; then
    cp "${TEMPLATE_DIR}/rules.js" "src/core/rules.js"
    echo "✅ src/core/rules.js (5대 도메인 100% 결정론 코어 엔진) 배치 완료"
  fi
  if [ ! -f "src/ai/reporter.js" ] && [ -f "${TEMPLATE_DIR}/reporter.js" ]; then
    cp "${TEMPLATE_DIR}/reporter.js" "src/ai/reporter.js"
    echo "✅ src/ai/reporter.js (권장 모델 가드레일 & 0.1초 SOP Fallback 어댑터) 배치 완료"
  fi
  if [ ! -f "src/components/Dashboard.jsx" ] && [ -f "${TEMPLATE_DIR}/Dashboard.jsx" ]; then
    cp "${TEMPLATE_DIR}/Dashboard.jsx" "src/components/Dashboard.jsx"
    echo "✅ src/components/Dashboard.jsx (Wafer Vector Map & 5대 도메인 통합 대시보드) 배치 완료"
  fi
fi

echo "================================================================"
echo "🎯 4대 레이어 디렉토리 및 5대 반도체 도메인 E2E 코드 준비 완료!"
echo "   검증 명령어: node engine/verify_core.mjs && node engine/deterministic_harness.mjs"
echo "   실행 명령어: npm install && npm run dev"
echo "================================================================"
