# 🎯 FDE Autopilot 6시간(360분) 실전 마스터 프롬프트 뱅크 (v6.1 - 11대 솔버 & 3-터미널 체계 완비)

> **📌 3-터미널 분리 세팅 (시험 시작 직후 실행)**
> - **터미널 1 (메인 에이전트)**: `codex` 실행 후 `/status` 및 `/model`에서 허용 모델(`Sol 6.1`, `Terra 5.6`, `Luna 6`, `Sol 6.0`) 선택 (**`Astra` 절대 선택 금지!**)
> - **터미널 2 (실시간 서버)**: 통합 앱 구현 후 `npm run dev` (`0.0.0.0` 바인딩) 상시 구동용
> - **터미널 3 (서브 에이전트 & Git)**: `python bootstrap.py --workspace .` 실행 -> `.fde_data_profile.md`, `.autopilot/pre_opt_diagnosis.md` 자동 생성 확인 및 매 단계 TDD 하네스 검증(`node engine/deterministic_harness.mjs`)/로컬 `git commit` 수행 (**`git push` 절대 금지!**)
>
> **💡 6시간(360분) 대회 타임라인 운영 전략**:
> - **[Phase 1: 00:00 ~ 01:00]** `bootstrap.py` 원클릭 딥 스캔 ➔ 실무자 DM 1·2차 심층 질의 ➔ 5대 대안 비교 및 `SPEC.md` 확정
> - **[Phase 2: 01:00 ~ 03:00] 🔥 [최대 투자] 결정론 코어 룰(`src/core/rules.js` & 11대 솔버 `engine/solver_*.py`) 정밀 구현 및 TDD 하네스(3초) 반복 검증**
> - **[Phase 3: 03:00 ~ 04:00]** `scaffold_app.py` 앱 생성 ➔ `npm run dev` (0.0.0.0) ➔ 3종 골든 샘플, What-If 슬라이더, 채점용 `output/result.json` Export 검증
> - **[Phase 4: 04:00 ~ 05:30]** 평가위원용 3대 문서 완성 (`SPEC.md`, `SOLUTION_NOTES.md` 5대 대안 비교표, `HANDOFF.md`)
> - **[Phase 5: 05:30 ~ 06:00]** `final_gatekeeper.py` 7대 관문 무결성 감사 통과, 전 파일 저장 및 후속 서술형 핵심 암기 제출

---

## [00:02] 실무자 에이전트(DM) 10대 심층 질문 + 5대 도메인 맞춤 질문 (1차/2차 나누어 전송)
> 우측 DM 메신저에서 `업무 담당자` 선택 후 전송 (`Shift+Enter` 줄바꿈, `Enter` 전송).
> `.fde_data_profile.md`의 **섹션 2(감지된 반도체 도메인) & 섹션 5(도메인 특화 DM 트리거)**를 반영해 질문합니다.

### [1차 질문 전송 (현재 최대 병목 · 기존 수작업 방식 · 최다 민원 · 최우선 해결 범위)]
```text
안녕하세요 담당자님! 과제 요구사항을 정확히 파악하고 현업에 꼭 맞는 통합 애플리케이션을 설계하기 위해 먼저 여쭙고 싶습니다.
1) 현재 이 업무를 처리하시면서 가장 문제가 되고 있는 병목 지점은 무엇이며, 지금까지는 이를 어떤 방식(수작업 등)으로 해결해 오셨나요?
2) 현업 사용자나 유관 부서로부터 가장 많이 들어오는 민원(불만 사항)은 무엇인가요?
3) 이번 1차 도구 도입 시 민원을 해결하기 위해 반드시 완벽히 동작해야 하는 1순위 핵심 기능과, 과감히 제외(Out-of-Scope)해도 되는 부가 기능의 경계를 알려주시면 집중하여 구현하겠습니다!
```

### [2차 질문 전송 (데이터 전처리/센티널 · 경계값 등호 · 도메인 특화 기준 · 판정 책임 소재)]
> 1차 답변을 받은 뒤, `.fde_data_profile.md`에서 도출된 실제 컬럼명/이상치 및 **5대 도메인별 핵심 규칙**을 넣어 2차 질문을 전송합니다.
```text
상세히 설명해주셔서 감사합니다! 말씀해주신 맥락을 바탕으로 데이터를 코드로 정밀 스캔해보니 [특정 컬럼명]에 결측치(Null/-999 등), 중복 식별자, 특수 상태 플래그(CANCELLED/INVALID 등)가 일부 포함되어 있습니다.
1) 비정상 상태나 센티널(-999) 결측치가 있는 행은 집계 분모에서 완전히 제외할까요, 아니면 별도의 오류 상태로 분류해 화면에 노출해야 할까요? 또한 중복 식별자 발생 시 최신 타임스탬프 1건을 유지하면 될까요?
2) 임계치 판정 시 경계값 숫자와 정확히 일치할 때 이상(>=)과 초과(>) 중 어느 기준으로 판정해야 하며, [.fde_data_profile.md 섹션 5에 출력된 도메인 특화 질문 1줄 삽입] 기준은 어떻게 적용할까요?
3) 마지막으로 시스템 판정 결과에 대한 최종 책임(Accountability)과 신뢰도를 명확히 하기 위해, 화면 리포트나 감사 로그에 반드시 남겨야 할 필수 항목(적용 규칙 ID, 판정 근거 수치, 권장 SOP, 담당자 최종 승인 기록 등)이 있다면 가이드 부탁드립니다!
```

---

## [Step 1: 00:08] 5대 대안 비교(선정/거절), 책임 소재 설계 및 SPEC.md 선행 생성 (터미널 1번 Codex)
> 실무자 DM 답변을 받은 직후 **터미널 1번(메인 에이전트 Codex)** 입력창에 붙여넣으세요. (`README.md`와 실무자 DM 답변이 상충할 경우 실무자 DM 답변을 최신 기준으로 우선 적용합니다.)

```text
먼저 AGENTS.md를 읽고 핵심 엔지니어링 원칙(80/20 분리, 메인/서브 에이전트 역할 분담)을 숙지해 줘.
아직 애플리케이션 코드는 작성하지 마. 토큰 절약을 위해 대용량 원본 데이터 파일을 직접 cat으로 읽지 말고, 서브 에이전트(workspace_profiler.py)가 생성한 .fde_data_profile.md 요약본(감지된 도메인 및 추천 레퍼런스 솔버 engine/solver_*.py 포함)과 README.md, 그리고 내가 실무자 DM으로 확인한 비즈니스 제약 조건을 바탕으로 먼저 계획을 수립하고 아래 문서들을 루트 경로에 작성(업데이트)해 줘.

1. 아키텍처 대안 5가지 제안 및 선정/거절 사유 분석 (SOLUTION_NOTES.md 또는 ARCHITECTURE_DECISIONS.md에 상세 기록):
- 이 문제를 해결할 수 있는 기술적/구조적 대안을 5가지(① 80/20 결정론 도메인 솔버 코어+AI Fallback 통합 웹앱, ② 100% LLM 단독 연산 처리, ③ 무거운 외부 DB+MSA 분리, ④ AI 없는 단순 하드코딩 스크립트, ⑤ 전처리 없는 클라이언트 원본 렌더링) 제안해 줘.
- 5가지 대안 중 가장 적합한 최선책 1가지를 선정한 구체적 이유와, 나머지 4가지 대안을 거절(기각)한 이유(수치 환각 위험, OOM, 유지보수성, 결측치 크래시 등)를 표와 함께 명확히 서술해 줘.
- 또한 시스템의 선택/판정 결과에 대한 책임(Accountability)은 누가 질 것인가에 대해 고민하여, "1차 수치/규칙 판정 무결성 책임은 결정론 코어(80%, 규칙 ID 및 편차 근거 명시)가 지고, AI(20%)는 보조 해석만 제공하며, 최종 예외 승인 책임은 감사 로그(Audit Trail)와 함께 현업 담당자에게 귀속시킨다"는 검증 및 책임 체계를 명시해 줘.

2. SPEC.md (요구사항 서면 합의서 및 실행 계획 - README.md에서 요구한 별도 기획서 파일명이 있다면 해당 파일명으로도 복사 생성):
- 현업 최대 문제점, 기존 해결 방식의 한계, 최다 민원 해결 목표
- 실무자 DM 확인 불변 규칙 (결측/센티널 -999 전처리 기준, 중복 제거 기준, 임계치 등호 >= vs > 기준, README와 상충 시 DM 기준 우선 적용 근거)
- 5대 반도체 도메인 중 이번 과제에 매핑된 레퍼런스 솔버(engine/solver_overlay.py, solver_material.py, solver_market.py, solver_value_chain_biz.py, solver_curriculum.py 중 해당 모듈)의 핵심 수리 로직 이식 계획
- 무엇부터 어떤 순서로 구현할지 9단계 순차 구현 로드맵(Step 1~2: 파서/골든샘플 ➔ Step 3~4: 코어 수치/임계치 판정 ➔ Step 5: 솔버/결과JSON ➔ Step 6: AI Fallback ➔ Step 7~8: 대시보드 UI/What-If ➔ Step 9: 게이트키퍼)과 예정 [구현 좌표: 파일명 - 함수명()] vs Out-of-Scope 범위 명시.
```
*(💡 Step 1 완료 후 **터미널 3**에서 `git add -A && git commit -m "docs: evaluate 5 alternatives, accountability rules, and complete SPEC.md"` 실행!)*

---

## [Step 2: 00:18] 통합 앱 4-Layer 스캐폴딩 & 0.0.0.0 E2E v0 관통 프롬프트 (터미널 1번 Codex)

```text
이제 SPEC.md와 SOLUTION_NOTES.md에 수립한 계획과 선정된 아키텍처 대안에 따라, .fde_data_profile.md에서 매핑된 도메인 레퍼런스 솔버(engine/solver_*.py)의 알고리즘과 실제 데이터 스키마를 결합하여 [STATE-3: 스캐폴딩] 및 [STATE-4: E2E v0] 단계를 진행해 줘. (기존 레거시 코드가 있다면 기존 API 엔드포인트와 테스트 호환성을 절대 깨뜨리지 마.)

1. 통합 앱 아키텍처 4대 레이어 물리적 분리 구현:
- src/data/samples.js (전처리 로더 & 골든 샘플): 어떠한 비정상 데이터(Null, 빈 문자열, NaN, 센티널 -999, INVALID 플래그, 중복 키)가 들어와도 고정 코드로 정제·분리하는 파서(sanitizeAndParseInput) 및 과제 데이터 스키마에 맞춘 3종 골든 샘플(normal, warning, violation)
- src/core/rules.js (결정론 코어 엔진): 해당 과제의 레퍼런스 도메인 솔버(engine/solver_*.py) 수리 모델, 임계치 판정, 핵심 지표 계산 및 판정 근거(ruleId, deviation) 산출을 담당하는 100% 결정론적 순수 함수(evaluateCoreRules)
  * 포토 Overlay 과제일 경우: 비선형 고차(1~3차) + 전공정 스트레스 Feed-forward APC, Edge 스마트 샘플링, Chuck/챔버 매칭 라우팅 포함
  * 소재품질 CoA 과제일 경우: Lot 간 Cpk 산포, 스펙트럼 파형 지문(Fingerprint) 유사도, 배관 체류 HVM 스트레스, Sub-tier 4M 변경 감사 포함
  * 시장전략 실적 과제일 경우: 마이크론 8월 결산 Calendarization 정규화, P×Q×Mix 분해(Mix 착시 탐지), IR 발언 vs 재고일수(DIO) 교차검증 포함
  * 경영전략 밸류체인 과제일 경우: TSMC CoWoS 패키징 상한선(Ceiling) 및 16개월 리드타임 채찍효과, 전환투자 손실(Conversion Loss) 및 LTA 반영 CAPEX ROIC 최적화, 지정학 시나리오 트리 포함
  * 반도체 산업교육 과제일 경우: Kahn 위상정렬 선수과목 DAG 검증, 12종 공정/소자 [비유 + 공학적 한계 교정] 2-Layer 설명, 목표 과목 압축 보존 및 오개념 진단 포함
  * **5대 문제 유형 과제일 경우**: Type A(알람 규정 위반 최소화), Type B(웨이퍼 불량 공간 분석 & 예산 배낭 최적화), Type C(센서 FDC 시계열 이상치 & CUSUM 비용 최적화), Type D(설비 Weibull 잔존수명 RUL & PM 스케줄링), Type E(레시피 파라미터 Golden Spec Diff & Cpk 마진 최대화)
  * **위 5대 도메인 외 미출제/범용 현업 과제일 경우 (`solver_universal.py` / `UNIVERSAL` 모드)**: ① 다변량 수치 이상치(3-Sigma/USL) 및 타겟 지표와의 피어슨 상관관계 Root-Cause Top Driver 도출, ② 예산/용량/필수과업/보안금지구역 제약 최적화 스케줄러, ③ BM25 기반 규정·SOP 문서 근거 조항(Citation ID) 검색기를 결합하여 완벽히 해결할 것.
- src/ai/reporter.js: 코어의 판정 결과를 받아 자연어 요약·권장 조치 가이드(SOP)를 생성하는 함수(generateInsightWithFallback - 에러나 타임아웃 시 0.1초 내로 코어 수치 기반 표준 안전장치 리포트를 반환하는 Fallback 필수 포함)
- src/components/Dashboard.jsx (메인 통합 UI): 화면 최상단에 평가자가 클릭 한 번으로 검증할 수 있는 3종 골든 샘플 버튼([정상 샘플 입력], [경고(임계치) 샘플 입력], [위반/오류 샘플 입력]), 실제 과제 파일 자동 로드 버튼, What-If 시뮬레이션 슬라이더, 채점용 결과 파일(output/result.json) 원클릭 Export 버튼, 핵심 KPI 요약 카드, 판정 근거(적용 규칙 ID 및 책임 구분 배지) 및 AI 리포트 뷰어를 구현해 줘. 서버 설정은 반드시 host 0.0.0.0 바인딩을 유지해 줘.
```

---

## [Step 3-A: 00:40] 결정론적 데이터 전처리/코어 정밀 구현 & 서브 에이전트 하네스 검증 (터미널 1번 Codex)

```text
[STATE-5: 중간검증]의 첫 번째 분해 작업이다. SPEC.md와 해당 도메인 솔버(engine/solver_*.py)를 다시 읽고, UI나 AI 호출부는 건드리지 말고 오직 src/data/samples.js(전처리 파서)와 src/core/rules.js(핵심 판정 모듈)의 결정론적 로직만 완벽하게 고도화해 줘.
1. 어떠한 형태의 데이터(빈 문자열 "", null, undefined, NaN, 센티널값 -999, 깨진 포맷, 빈 배열, 중복 키)가 들어와도 절대 런타임 크래시가 발생하지 않고 정상 데이터와 이상치(INVALID)를 정확히 분리하도록 전처리 로직을 완성해 줘.
2. README.md, .fde_data_profile.md, SPEC.md(실무자 DM 확인 사항 포함)에 정의된 모든 비즈니스 규칙(임계치 등호 >= vs > 여부, 중복 제거, 비정상 상태 건 분모 제외, 도메인 특화 수식)과 판정 근거(ruleId) 출력을 고정 코드로 정확히 구현해 줘.
```
*(💡 완료 직후 **터미널 3(서브 에이전트)**에서 `node engine/deterministic_harness.mjs` 및 `python3 engine/blackbox_emulator.py --verify-solvers`를 실행해 모두 PASS하는지 확인한 뒤 커밋!)*

---

## [Step 3-B: 01:00] AI 파이프라인/UX 고도화 & SPEC.md 증거 좌표 매핑 (터미널 1번 Codex)

```text
검증된 전처리 및 코어 판정 모듈의 출력값을 src/ai/reporter.js 및 프론트엔드 UI(src/components/Dashboard.jsx)와 완전히 결합해 줘.
1. 판정 상태(NORMAL=초록, WARNING=노랑, VIOLATION=빨강) 배지, 핵심 수치 요약 카드, 결측/이상치 분리 내역, 판정 근거 조항/수치(시스템 코어 1차 판정 근거 vs AI 보조 조언 구분 표시), AI 조치 가이드(및 Fallback 작동 여부)가 화면에서 한눈에 직관적으로 보이도록 UI/UX 완성도를 높여 줘.
2. 사용자가 버튼을 빠르게 연타하거나 잘못된 포맷을 넣었을 때 UI가 죽지 않도록 입력 방어 처리를 추가해 줘.
3. 작업 완료 후 SPEC.md 파일을 열어서 In-Scope의 각 요구사항 항목 옆에 실제로 구현된 파일 경로와 핵심 함수명(예: [구현 좌표: src/core/rules.js - evaluateCoreRules()])을 정확하게 매핑해서 업데이트해 줘.
```

---

## [Step 4-A: 01:20] HANDOFF.md 및 ARCHITECTURE_DECISIONS.md 최종 완성 (터미널 1번 Codex)

```text
이제 [STATE-6: 수용확인 및 핸드오프] 단계다. docs_kit/HANDOFF_TEMPLATE.md 및 docs_kit/ARCHITECTURE_DECISIONS.md의 구조를 참고하여 현재 우리 프로젝트의 실제 파일명과 함수명에 맞춘 HANDOFF.md와 SOLUTION_NOTES.md(또는 과제 README.md에서 요구한 제출 문서명)를 루트 경로에 최종 완성해 줘. 반드시 아래 4가지를 실제 코드와 100% 일치하게 작성해야 해:
1. 전체 아키텍처 및 데이터 흐름도 (입력 -> 결정론적 Data 정제 파서 -> Deterministic Core 80% -> AI Reporter & Fallback 20% -> 직관적 UI 렌더링)
2. 5가지 아키텍처 대안 비교표 (최선책 1개 선정 이유 및 나머지 4개 대안 거절 이유) 및 판정 결과에 대한 책임 소재(Accountability: 코어 수치 판정 근거 투명화 vs AI 보조 조언 vs 담당자 최종 승인 로그)
3. 완료된 핵심 기능, 실무자 DM 질문 반영 규칙 및 실제 코드 증거 좌표 표 (파일 경로 + 함수명 + 서브 에이전트 하네스 검증 결과)
4. 사후 서술형 문제 대비 3단계 기술 리스크 분석 (구체적 약점 파일/함수 지목 -> 현장 파급 위험 -> 더미 부하 계측 및 단기/장기 개선 계획)
```

---

## [Step 4-B: 01:30] 터미널 3번 서브 에이전트 최종 감사(Auditor & Gatekeeper) 실행
> **터미널 3(서브 에이전트)**에서 아래 검증 스크립트들을 실행합니다:
> 1) `node engine/deterministic_harness.mjs`
> 2) `python3 engine/blackbox_emulator.py --verify-solvers`
> 3) `python3 engine/final_gatekeeper.py`
