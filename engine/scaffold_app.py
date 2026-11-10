#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine/scaffold_app.py
--------------------------------------------------------------------------------
FDE App Scaffolder (Cross-Platform Python 3.12 Engine)

[config.toml 4대 아키타입(Type A~D) 및 0.0.0.0 서버 뼈대 생성기]
- Type A: 대시보드 / 지표 모니터링 (KPI 카드, 상태 배지, 시계열 추세)
- Type B: 규칙 검증 / Diff 및 Out-of-Spec 알람 (Golden Spec vs 실측 Diff, Cpk, 임계치)
- Type C: 문서 근거 검색 / 규정 Q&A RAG (BM25 조항 인용 Citation, 권한 필터링)
- Type D: 상태 머신 / 워크플로우 & 백오피스 (DRAFT->REVIEW->APPROVED 전이, 결재/감사 로그)

config.toml의 [project].default_type 및 [execution].default_host를 기본값으로 자동 로드하며,
CLI 인자(--type, --domain, --target)로 덮어쓰기 가능합니다.
"""

from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# 중앙 설정 로더 연동
try:
    from engine.config_loader import load_config
except ImportError:
    # 직접 실행 시 sys.path 보정
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.config_loader import load_config


VITE_CONFIG_TEMPLATE = """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

function fdePythonSolverBridge() {
  return {
    name: 'fde-python-solver-bridge',
    configureServer(server) {
      // 1. /api/solve -> 11대 도메인 & 아키타입 Python 솔버 브릿지
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
            execFile(pyBin, [scriptPath, tmpIn, tmpOut], { timeout: 8000 }, (err) => {
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

      // 2. /api/export-result -> output/result.json 디스크 자동 저장
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

      // 3. /api/workspace-data -> 로컬 파일 자동 스캔 및 통합 파이프라인 연동
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
                    const lines = fs.readFileSync(full, 'utf-8').split(/\\r?\\n/).filter(Boolean);
                    if (lines.length >= 2) {
                      const headers = lines[0].split(',').map((h) => h.trim());
                      records = lines.slice(1, 201).map((ln) => {
                        const cols = ln.split(',');
                        return Object.fromEntries(headers.map((h, i) => [h, (cols[i] || '').trim()]));
                      });
                      sourceFile = f;
                    }
                  } catch (_) {}
                } else if (f.endsWith('.md') && !['AGENTS.md', 'AUDITOR_GUIDE.md', 'SPEC.md', 'HANDOFF.md', 'SOLUTION_NOTES.md'].includes(f)) {
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
            execFile(pyBin, [pipelineScript, '--workspace', root, '--out', resultFile], { timeout: 8000 }, () => {
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
    }
  };
}

export default defineConfig({
  plugins: [react(), fdePythonSolverBridge()],
  server: {
    host: '__HOST__',
    port: 5173,
    strictPort: false
  }
});
"""

INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FDE AI Expert Decision Console (Type __TYPE__)</title>
  </head>
  <body style="margin: 0; background-color: #f8fafc;">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""

MAIN_JSX_TEMPLATE = """import React from 'react';
import ReactDOM from 'react-dom/client';
import MainWorkspaceView from './components/Dashboard.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MainWorkspaceView initialArchetype="__TYPE__" />
  </React.StrictMode>
);
"""

PACKAGE_JSON_TEMPLATE = """{
  "name": "fde-mission-app",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host __HOST__ --port 5173",
    "start": "vite --host __HOST__ --port 5173",
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
"""


def scaffold(target_dir: str = ".", app_type: str = None, host: str = None, domain: str = "OVERLAY") -> dict:
    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)

    # 1. config.toml 로드
    cfg = load_config(workspace_root=target_path)
    project_cfg = cfg.get("project", {})
    exec_cfg = cfg.get("execution", {})

    resolved_type = (app_type or project_cfg.get("default_type", "A")).upper()
    resolved_host = host or exec_cfg.get("default_host", "0.0.0.0")

    archetype_names = {
        "A": "대시보드 / 실시간 지표 모니터링 (Type A: Dashboard & Metrics)",
        "B": "규칙 검증 / Diff & Out-of-Spec 알람 (Type B: Validator & Spec Diff)",
        "C": "문서 근거 검색 / 규정 Q&A RAG (Type C: Policy Retrieval & RAG)",
        "D": "상태 머신 / 워크플로우 & 백오피스 (Type D: Workflow & State Machine)",
        "E": "고차원 다목적 최적화 / 시뮬레이션 (Type E: Multi-Objective Pareto)",
    }
    archetype_desc = archetype_names.get(resolved_type, f"사용자 정의 아키타입 ({resolved_type})")

    print("=" * 64)
    print(f"🏗️ [FDE App Scaffolder v4.5] config.toml 기반 앱 생성")
    print(f"   • 대상 경로: {target_path}")
    print(f"   • 기본 아키타입: Type {resolved_type} ➔ {archetype_desc}")
    print(f"   • 서버 바인딩: {resolved_host}:5173 (0.0.0.0 상시 보장)")
    print("=" * 64)

    # 2. 4대 레이어 디렉토리 생성
    for sub in ["src/data", "src/core", "src/ai", "src/components", "public", "output"]:
        (target_path / sub).mkdir(parents=True, exist_ok=True)

    # 3. package.json
    pkg_file = target_path / "package.json"
    if not pkg_file.exists():
        pkg_content = PACKAGE_JSON_TEMPLATE.replace("__HOST__", resolved_host)
        pkg_file.write_text(pkg_content, encoding="utf-8")
        print("  ✅ package.json 생성 완료 (--host 0.0.0.0 기본 내장)")

    # 4. vite.config.js
    vite_file = target_path / "vite.config.js"
    if not vite_file.exists():
        vite_content = VITE_CONFIG_TEMPLATE.replace("__HOST__", resolved_host)
        vite_file.write_text(vite_content, encoding="utf-8")
        print("  ✅ vite.config.js 생성 완료 (0.0.0.0 바인딩 + Python 솔버 브릿지)")

    # 5. index.html
    index_file = target_path / "index.html"
    if not index_file.exists():
        index_file.write_text(INDEX_HTML_TEMPLATE.replace("__TYPE__", resolved_type), encoding="utf-8")
        print("  ✅ index.html 생성 완료")

    # 6. src/main.jsx
    main_file = target_path / "src" / "main.jsx"
    if not main_file.exists():
        main_file.write_text(MAIN_JSX_TEMPLATE.replace("__TYPE__", resolved_type), encoding="utf-8")
        print(f"  ✅ src/main.jsx 생성 완료 (기본 아키타입 Type {resolved_type} 주입)")

    # 7. JS 템플릿 복사
    script_dir = Path(__file__).resolve().parent
    template_dir = script_dir / "js_templates"

    copied_files = []
    if template_dir.exists():
        copy_map = {
            "samples.js": target_path / "src" / "data" / "samples.js",
            "rules.js": target_path / "src" / "core" / "rules.js",
            "reporter.js": target_path / "src" / "ai" / "reporter.js",
            "Dashboard.jsx": target_path / "src" / "components" / "Dashboard.jsx",
        }
        for tmpl_name, dst_path in copy_map.items():
            src_file = template_dir / tmpl_name
            if src_file.exists() and not dst_path.exists():
                shutil.copy2(src_file, dst_path)
                copied_files.append(str(dst_path.relative_to(target_path)))
                print(f"  ✅ {dst_path.relative_to(target_path)} 배치 완료")

    print("=" * 64)
    print(f"🎯 [완료] Type {resolved_type} 스캐폴딩이 성공적으로 준비되었습니다.")
    print(f"   ▶ 검증: node engine/deterministic_harness.mjs")
    print(f"   ▶ 구동: npm install && npm run dev (0.0.0.0:5173)")
    print("=" * 64)

    return {
        "status": "SUCCESS",
        "target_dir": str(target_path),
        "app_type": resolved_type,
        "archetype_desc": archetype_desc,
        "host": resolved_host,
        "copied_files": copied_files,
    }


def main():
    parser = argparse.ArgumentParser(description="FDE App Scaffolder (config.toml Type A~D Architecture)")
    parser.add_argument("--target", default=".", help="Target workspace root directory")
    parser.add_argument("--type", choices=["A", "B", "C", "D", "E"], default=None, help="Force override archetype Type (default from config.toml)")
    parser.add_argument("--host", default=None, help="Force override host (default 0.0.0.0 from config.toml)")
    parser.add_argument("--domain", default="OVERLAY", help="Default domain keyword")
    args = parser.parse_args()

    scaffold(target_dir=args.target, app_type=args.type, host=args.host, domain=args.domain)


if __name__ == "__main__":
    main()
