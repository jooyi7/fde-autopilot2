#!/usr/bin/env node
/**
 * Deterministic Core Verification Harness (verify_core.mjs)
 * 코어 판정 로직이 정상값, 경계값(Boundary), 결측치(null/NaN)에서
 * 크래시 없이 일관된 결과를 반환하는지 검증합니다.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

console.log("🧪 [verify_core.mjs] Running Deterministic Core Assertions...");

export function toSafeNumber(val, fallback = null) {
  if (val === null || val === undefined || val === '') return fallback;
  const num = Number(val);
  return Number.isFinite(num) ? num : fallback;
}

export function checkSpecLimit(value, lcl = null, ucl = null) {
  const v = toSafeNumber(value, null);
  if (v === null) return { verdict: 'INVALID_DATA', deviation: 0 };
  if (ucl !== null && v > ucl) return { verdict: 'SPEC_OUT_HIGH', deviation: Number((v - ucl).toFixed(4)) };
  if (lcl !== null && v < lcl) return { verdict: 'SPEC_OUT_LOW', deviation: Number((lcl - v).toFixed(4)) };
  return { verdict: 'IN_SPEC', deviation: 0 };
}

try {
  // 1. 정상 범위
  assert.deepEqual(checkSpecLimit(50, 40, 60), { verdict: 'IN_SPEC', deviation: 0 });
  // 2. 상한 초과
  assert.deepEqual(checkSpecLimit(62.5, 40, 60), { verdict: 'SPEC_OUT_HIGH', deviation: 2.5 });
  // 3. 경계값 (Boundary = 60은 정상으로 처리되는지 확인)
  assert.deepEqual(checkSpecLimit(60, 40, 60), { verdict: 'IN_SPEC', deviation: 0 });
  // 4. 결측치 방어 (null, 빈 문자열, NaN 문자열)
  assert.deepEqual(checkSpecLimit(null, 40, 60), { verdict: 'INVALID_DATA', deviation: 0 });
  assert.deepEqual(checkSpecLimit('', 40, 60), { verdict: 'INVALID_DATA', deviation: 0 });
  assert.deepEqual(checkSpecLimit('NaN_Val', 40, 60), { verdict: 'INVALID_DATA', deviation: 0 });

  console.log("✅ [PASS] All deterministic boundary & null-safety checks passed.");
} catch (error) {
  console.error("❌ [FAIL] Core Verification Failed:", error.message);
  process.exit(1);
}

const pkgFile = path.resolve(process.cwd(), 'package.json');
if (fs.existsSync(pkgFile)) {
  const pkg = JSON.parse(fs.readFileSync(pkgFile, 'utf-8'));
  console.log(`📦 Workspace package.json scripts: ${Object.keys(pkg.scripts || {}).join(', ') || 'none'}`);
}
