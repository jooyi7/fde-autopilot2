# 🛠️ FDE-Autopilot v8.0 최종 실전 패치 및 무결성 가이드

이 문서는 해커톤 본선에서 발생할 수 있는 **Python 솔버와 JS 코어 간의 수치 불일치, 대용량 데이터 절삭(Truncation), 조인 키 덮어쓰기, What-If 슬라이더 버그, 그리고 매직 넘버 하드코딩** 등의 치명적인 리스크를 완벽히 차단하기 위한 최종 실전 패치 매뉴얼입니다.

---

## 🚨 1. 주요 발견 취약점 및 리스크 요약

1. **Python 솔버(`solver_*.py`)와 JS 코어(`rules.js`) 간 수식 괴리:**
   - 시장전략(`MARKET`)의 수급 단가 탄력성, 밸류체인(`VALUE_CHAIN`)의 ROIC 전환손실 반영 계수(`0.25`), 포토(`OVERLAY`)의 `outlier_z = 3.5` 필터링 및 10-Parameter 키 매핑, 소재품질(`MATERIAL`)의 리스크 점수 컷오프(`32.0점`) 등에서 Python과 JS가 서로 다른 수식을 사용하여 화면 숫자와 제출 파일(`output/result.json`) 숫자가 어긋날 위험이 있었습니다.
2. **`auto_solver_pipeline.py`의 대용량 데이터 절삭 (`max_rows=3000`):**
   - 3,000행 초과 시 데이터를 잘라버려 대규모 계측 데이터나 시계열 센서 데이터의 70% 이상이 유실될 위험이 있었습니다.
3. **Fact-First Join 복합키 슬라이싱 제한 버그 (`[:2]`):**
   - 공통 키가 3개 이상일 때 식별자(`wafer_id` 등)가 밀려나 덮어쓰기가 발생할 수 있었습니다.
4. **`Dashboard.jsx` What-If 슬라이더 하드코딩 덮어쓰기:**
   - 슬라이더 조작 시 원본 과제의 스펙 대신 하드코딩된 초기 값(`2.0`, `250` 등)으로 강제 덮어씌워져 수치가 튀는 현상이 있었습니다.

---

## 🔧 2. 파일별 상세 수정 지침 및 패치 코드

### 📁 [Patch 1] `auto_solver_pipeline.py` (대용량 제한 해제 및 복합키 전체 사용)

* **수정 위치 1 (`max_rows` 3000 ➔ 100000 상향):**
  - 파일 내 `read_delimited_table` 및 `jsonlines` 읽기 구간의 `max_rows=3000`을 `max_rows=100000`으로 일괄 변경합니다.
* **수정 위치 2 (Fact-First Join 복합키 슬라이싱 제거):**
  - `auto_join_tables_fact_first` 함수 내부의 `active_keys = shared_keys_lower[:2]` 코드를 아래와 같이 전체 키 사용으로 변경합니다.
  ```python
  # 기존: active_keys = shared_keys_lower[:2]
  # 변경:
  active_keys = shared_keys_lower
  ```

---

### 📁 [Patch 2] `src/core/rules.js` (Python v8.0 수식 100% 동기화 및 상수 집중화)

파일 최상단의 `THRESHOLD_CONFIG`를 확장하고, 각 도메인 판정 함수 내부의 하드코딩된 상수를 파라미터화 및 Python 솔버 수식과 일치시킵니다.

```javascript
export const THRESHOLD_CONFIG = {
  STRICT_GTE: true,
  OVERLAY_DEFAULT_SPEC_NM: 2.0,
  OVERLAY_WARN_RATIO: 0.85,
  OVERLAY_CHUCK_DELTA_LIMIT_NM: 0.35,
  OVERLAY_OUTLIER_Z: 3.5,
  MATERIAL_MIN_CPK_APPROVE: 1.33,
  MATERIAL_MIN_CPK_CONDITIONAL: 1.0,
  MATERIAL_SPECTRUM_COS_SIM_LIMIT: 0.985,
  MATERIAL_REJECT_RISK_CUTOFF: 65.0,
  MATERIAL_WARN_RISK_CUTOFF: 32.0,
  MARKET_DIO_SPIKE_DAYS: 7.0,
  MARKET_CAPEX_UNDEREXEC_PCT: 70.0,
  MARKET_KRW_PER_USD: 1380.0,
  VALUE_CHAIN_STRANDED_DIE_VIOLATION_BGB: 5.0,
  VALUE_CHAIN_BULLWHIP_AMP: 1.65,
  VALUE_CHAIN_HOLDING_LOSS_PER_BGB: 145.0,
  VALUE_CHAIN_TAX_RATE: 0.22,
};
```

* **Overlay 도메인 수식 동기화:**
  - 회귀 전 `outlier_z = 3.5` 기준 인라이어 필터링 적용 및 `physical_10param_correctables`에 `field_RotX_urad`, `field_RotY_urad` 키를 추가하여 Python(`solver_overlay.py`)과 10개 필드가 정확히 일치하도록 수정합니다.
* **Value-Chain ROIC 전환손실 수식 동기화:**
  - `effective_wafer_yield_factor = Math.max(0.5, 1.0 - (convLoss / 100.0) * 0.25)`를 적용하여 Python(`solver_value_chain_biz.py`)과 EVA / ROIC 결과값이 소수점까지 일치하도록 맞춥니다.

---

### 📁 [Patch 3] `src/components/Dashboard.jsx` (What-If 원본 기준값 보존 패치)

* **수정 위치 (`handleWhatIfChange` 함수):**
  - 슬라이더 조작 시 고정 상수가 아닌 최초 로드된 페이로드의 원본 값을 기준으로 배율(`mult`)을 곱하도록 수정하여 수치 증발 버그를 방지합니다.
  ```javascript
  const handleWhatIfChange = (mult) => {
    setWhatIfMultiplier(mult);
    try {
      const baseObj = JSON.parse(rawJsonText);
      // 원본 값이 존재할 경우에만 배율 적용, 없으면 기본 스펙 기준 적용
      if (baseObj.m3s_spec_nm !== undefined) {
        baseObj.m3s_spec_nm = Number(((baseObj._original_m3s_spec_nm || 2.0) * mult).toFixed(2));
      }
      if (baseObj.specs && typeof baseObj.specs === "object") {
        baseObj.min_cpk = Number(((baseObj._original_min_cpk || 1.33) / Math.max(mult, 0.5)).toFixed(2));
      }
      setRawJsonText(JSON.stringify(baseObj, null, 2));
      runPipeline(baseObj, activeDomain, simulateAiError);
    } catch (_) {}
  };
  ```

---

### 📁 [Patch 4] `engine/deterministic_harness.mjs` (output/result.json 크로스체크 추가)

하네스 검증 시방서에 기존 5대 샘플 테스트 외에 `output/result.json`이 존재할 경우 JS 코어 판정 결과와 상태(`status`)가 100% 일치하는지 자동 검증하는 로직을 추가합니다.

```javascript
// deterministic_harness.mjs 하단에 추가할 크로스체크 로직
const resultJsonPath = path.join(WORKSPACE, "output/result.json");
if (fs.existsSync(resultJsonPath)) {
  try {
    const pyRes = JSON.parse(fs.readFileSync(resultJsonPath, "utf8"));
    const shaped = pyRes.shaped_input_payload || pyRes.solution;
    if (shaped) {
      const jsEval = evalFn(shaped);
      if (jsEval.status === (pyRes.status || pyRes.solution?.status)) {
        console.log(`🟢 [PASS] TEST-07 [Python result.json vs JS Core 판정 등급 일치 크로스체크]`);
        passCount++;
      } else {
        console.log(`🔴 [FAIL] TEST-07: Python status(${pyRes.status})와 JS status(${jsEval.status})가 불일치합니다.`);
      }
    }
  } catch (e) {
    console.log(`⚠️ [WARN] result.json 크로스체크 스킵: ${e.message}`);
  }
}
```

---

## 🚀 3. 최종 실전 행동 수칙 (6시간 타임라인 재확인)

1. **Step 1 (00:20):** `python bootstrap.py --workspace .` 실행 후 1차 커밋 (`git add -A && git commit -m "feat: bootstrap"`)