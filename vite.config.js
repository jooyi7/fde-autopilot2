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
    host: '0.0.0.0',
    port: 5173,
    strictPort: false
  }
});
