# 📋 SPEC.md — 요구사항 서면 합의서 및 9단계 순차 구현 실행서

> ⚠️ **문서명 안내:** 본 문서는 과제의 기본 요구사항 합의서이자 설계도입니다. 과제 `README.md`에서 별도의 문서명(예: `PLAN.md`, `REQUIREMENTS.md` 등)을 명시한 경우 해당 명칭으로도 복사하여 보존합니다.

---

## 1. 비즈니스 문제 정의 및 현장 병목 (Context & Pain Points)
- **현장 에피소드 및 병목**: 담당 부서에서 대량의 데이터와 복합 규격을 수작업 엑셀 및 파편화된 기준으로 검토하느라 판정 리드타임이 길어지고 휴먼 에러(누락·오판)가 발생함.
- **현재 임시 대처(Workaround)의 한계**: 수기 필터링과 사후 대조에 의존하여 실시간 이상 탐지 및 표준화된 감사 추적(Audit Trail)이 불가능함.
- **해결 과제 (Core Delta)**: **결정론적 규칙 코어(80%)**를 통한 오차 없는 실시간 1차 수치 판정과, **AI 에이전트(20%)** 기반 원인 가설·SOP 가이드 생성을 결합한 무중단 End-to-End 엔터프라이즈 솔루션 구축.

---

## 2. 정량적 성공 기준 (Quantitative Success Metrics)

| 측정 지표 | 현재 수준 (As-Is) | 목표 수준 (To-Be) | 검증 방법 |
| :--- | :--- | :--- | :--- |
| **건당 판정 소요 시간** | 수기 대조 10~15분 | **1초 이내 즉시 판정** | 상단 3종 골든 샘플 원클릭 테스트 |
| **규칙/임계치 계산 정확도** | 휴먼 에러 발생 위험 | **결정론 코어 기반 오차 0%** | `node engine/deterministic_harness.mjs` 검증 |
| **AI 장애 시 서비스 가용성** | API 장애 시 시스템 중단 | **100% 무중단 (0.1초 Fallback)** | 503 장애 유발 시 코어 기반 정적 SOP 즉시 반환 |
| **결측치 및 센티널 방어율** | 크래시 발생 가능 | **100% 격리 (0-Crash)** | `-999`, `Null`, `INVALID` 주입 시 정상 분리 |

---

## 3. 실무자(페르소나) DM 질의 서면 합의 기준 (Inquiry Baseline)
- **결측치 및 센티널(-999) 처리**: 집계 분모에서 안전하게 제외(Drop/Isolate)하고 별도의 `isolatedAnomalies` 객체로 격리 보관.
- **중복 식별자 처리**: 최신 타임스탬프 1건만 유효 레코드로 인정.
- **임계치 등호 기준**: 스펙 경계값과 정확히 일치할 때 안전 우선 원칙에 따라 이상(`>=`)으로 엄격 판정.
- **판정 책임 소재 (Accountability)**:
  - 1차 수치 및 규칙 판정 무결성 책임: **결정론 코어 (80%, 적용 ruleId 및 편차 노출)**
  - 보조 원인 해석 및 권장 SOP: **AI 어드바이저 (20%)**
  - 최종 의사결정 및 예외 승인 권한: **감사 로그(Audit Trail)와 함께 현업 엔지니어에게 귀속**

---

## 4. 9단계 순차 구현 로드맵 및 증거 좌표 (Step-by-Step Implementation)

본 프로젝트는 아래 1단계부터 9단계까지 순차적으로 구현하고 검증을 완료합니다.

### [Phase 1. 데이터 무결성 & 전처리 계층]
* [x] **Step 1: 파괴적 입력 방어 파서 구현**
  - 설명: `Null`, 빈 문자열, `NaN`, 센티널(`-999`), `INVALID` 플래그 유입 시 크래시 없이 정상치와 이상치를 분리.
  - `[구현 좌표: src/data/samples.js - sanitizeAndParseInput()]`
* [x] **Step 2: 3종 골든 샘플(정상/경고/위반) 데이터셋 확정**
  - 설명: 평가위원이 즉시 검증할 수 있는 정량적 골든 샘플 3종(`normal`, `warning`, `violation`) 구성.
  - `[구현 좌표: src/data/samples.js - DOMAIN_GOLDEN_SAMPLES]`

### [Phase 2. 결정론적 수리 연산 & 코어 규칙 계층 (🔥 핵심 승부처)]
* [x] **Step 3: 도메인 특화 수식 및 통계 연산 순수 함수 구현**
  - 설명: 외부 라이브러리 없이 순수 JavaScript/Python으로 평균, 분산, Cpk, 손실함수, 최적화 목적함수 계산.
  - `[구현 좌표: src/core/rules.js - calculateMetrics()]`
* [x] **Step 4: 임계치 비교, 규칙 ID 발급 및 상태(NORMAL/WARNING/VIOLATION) 판정**
  - 설명: `THRESHOLD_CONFIG` 상수를 기반으로 조건 분기, 적용 규칙 ID(`ruleId`), 코어 점수(`score`) 도출.
  - `[구현 좌표: src/core/rules.js - evaluateCoreRules()]`
  - *(검증: `node engine/deterministic_harness.mjs` 6/6 PASS 확인)*

### [Phase 3. 백엔드 최적화 & 채점 파일 계층]
* [x] **Step 5: 11대 Python 솔버 연동 및 채점용 결과 파일 생성**
  - 설명: 문제 유형에 최적화된 알고리즘(Branch & Bound, 배낭 DP, SA 등) 실행 및 최종 결과 디스크 저장.
  - `[구현 좌표: engine/auto_solver_pipeline.py ➔ output/result.json]`

### [Phase 4. AI 어댑터 & 무중단 Fallback 계층]
* [x] **Step 6: AI 자연어 SOP 리포터 및 0.1초 Fallback 안전장치**
  - 설명: 코어 출력 객체를 기반으로 원인 가설 및 SOP 생성, 1.5초 타임아웃/오류 시 즉시 정적 템플릿 반환.
  - `[구현 좌표: src/ai/reporter.js - generateInsightWithFallback()]`

### [Phase 5. 웹 인터페이스 & 0.0.0.0 실시간 콘솔 계층]
* [x] **Step 7: 4대 아키타입(Type A~D) 뷰 및 3종 골든 샘플 원클릭 버튼 연동**
  - 설명: KPI 요약 카드, 상태 배지, 데이터 테이블 시각화 및 원클릭 프리셋 주입 버튼 연결.
  - `[구현 좌표: src/components/Dashboard.jsx - MainWorkspaceView()]`
* [x] **Step 8: What-If 제약 슬라이더 및 현업 최종 승인 감사 로그(Audit Trail) 연동**
  - 설명: 파라미터 조절 시 실시간 반응, 담당자 최종 승인 기록을 화면과 로컬 상태에 영구 보존.
  - `[구현 좌표: src/components/Dashboard.jsx - handleWhatIfChange(), handleRecordApproval()]`

### [Phase 6. 최종 감사 및 안전 제출 계층]
* [x] **Step 9: 게이트키퍼 무결성 감사 통과 및 최종 제출**
  - 설명: 보안, 0.0.0.0 포트 바인딩, 채점 파일, 3대 문서 일치 검사 통과 후 로컬 Git 커밋 완료.
  - `[구현 좌표: engine/final_gatekeeper.py - run_gatekeeper()]`

---

## 5. 범위 합의 (In-Scope vs Out-of-Scope)
### ✅ In-Scope (이번 배포 필수 포함 항목)
- 3종 골든 샘플 원클릭 검증 버튼 및 실데이터 파일 자동 로더
- 센티널(-999)/결측치 무크래시 전처리 및 3-Sigma 임계치 판정
- 채점용 표준 결과 파일(`output/result.json`) 자동 산출
- 0.1초 무중단 Fallback이 보장된 AI 어드바이저

### 🚫 Out-of-Scope (완성도를 위해 의도적으로 제외한 항목)
- 대규모 멀티테넌트 계정 관리 및 외부 사외망 API 직접 연동
- 운영체제 수준의 장기 영속 백업 데몬 (로컬 상태 및 JSON 저장으로 충분)
