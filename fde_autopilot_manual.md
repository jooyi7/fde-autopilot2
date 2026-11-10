# 🚀 FDE-Autopilot v6.2 실전 사용자 바이블 (초구체적 3-Terminal 실전 행동 지침)

이 문서는 해커톤 대회장에 입장한 응시자가 **"어느 터미널에서, 어떤 파일의 프롬프트를 열어서 복사하고, 무엇을 입력해야 하는지"** 고민할 필요 없이 100% 그대로 따라 할 수 있도록 설계된 **초구체적 실전 행동 매뉴얼**입니다.

---

## 💡 핵심 워크플로우 질문에 대한 명확한 답변

> **Q. "원래 데이터 분석하고, 그 다음에 현업 책임 에이전트한테 질문하고, 그 다음에 기존에 주어진 `README.md` + 데이터 분석 정보 + 책임자가 알려준 답변을 가지고 총 계획을 짜는 게 `SPEC.md` 아닌가요?"**
> 
> **A. 네, 100% 맞습니다! 그것이 바로 엔지니어링의 정석입니다.**
> 1. **재료 1**: 과제 `README.md` (시험 문제의 공식 요구사항)
> 2. **재료 2**: 서브 에이전트가 분석한 `.fde_data_profile.md` (데이터 결측치, 센티널 -999, 3-Sigma 임계치)
> 3. **재료 3**: 현업 책임 에이전트(페르소나)의 DM 답변 (등호 기준, Cpk 허들, 예외 조치 등)
> 
> 이 **3가지 재료가 모두 모여야만 비로소 완벽한 총 실행 계획서인 `SPEC.md`와 5대 대안 비교표(`SOLUTION_NOTES.md`)가 완성**됩니다!

---

## 🖥️ 1. 시작 직후: 3개 터미널 세팅 (00:00)

웹 IDE나 에디터의 터미널 `+`(또는 분할) 버튼을 눌러 **3개의 창**을 띄우고 아래 역할을 부여합니다.

* **[Terminal #1] Main Agent (Codex CLI 조종석)**:
  - `codex`를 실행하고 `/model` 명령어로 권장 모델(`Sol 6.1`, `Terra 5.6`, `Luna 6` 중 택1)을 선택합니다. (*`Astra` 절대 금지*)
  - 오직 자연어 지시, 설계, 코드 작성 전용으로 사용합니다.
* **[Terminal #2] Real-time Web Server (0.0.0.0 상시 구동)**:
  - 추후 `npm run dev`로 웹 서버를 띄워두고 대회 종료까지 **절대 끄지 않는 전용 창**입니다.
* **[Terminal #3] Sub Agent Worker (결정론 스크립트 실행 & Git 전용)**:
  - LLM 개입 없는 순수 Python/Node 스크립트 실행(`bootstrap.py`, 하네스, `git commit`) 전용 창입니다.

---

## 🏃 2. 초구체적 단계별 실전 실행 가이드 (Step 1 ~ Step 6)

---

### 🚀 Step 1. [00:00 ~ 00:15] 데이터 및 과제 원클릭 자동 분석

* **실행 위치**: **`[Terminal #3]` (서브 에이전트 창)**
* **입력할 명령어**:
  ```bash
  python bootstrap.py --workspace .
  # (Linux/Mac/Git Bash 환경인 경우: bash bootstrap.sh --workspace .)
  ```
* **동작 내용**:
  1. 외부 유출 방지를 위한 `git push` 원천 차단 훅(`.git/hooks/pre-push`) 자동 설치.
  2. 워크스페이스 내 모든 CSV, JSON, MD 파일을 전수 탐색하여 아래 리포트 자동 생성:
     - `WORKSPACE_PROFILE.md`: `README.md` 요약 및 디렉터리 구조.
     - `.fde_data_profile.md`: 결측치(`Null`), 센티널(`-999`), 3-Sigma 통계 프로파일.
     - `.autopilot/pre_opt_diagnosis.md`: 평가지표(정확도 vs 속도), 병목(알고리즘 vs HW) 사전 진단.
     - `.fde_optimization_proposal.md`: 추천 최적화 기법 순위표.
     - `output/result.json`: 도메인 자동 판별 및 기준 솔버 1차 결과.
* **1차 로컬 Git 커밋 실행 (`[Terminal #3]`에서 실행)**:
  ```bash
  git add -A
  git commit -m "feat: complete workspace profiling and generate baseline result"
  ```

---

### 💬 Step 2. [00:15 ~ 00:45] 현업 책임자 DM 질의 & 총 계획서(`SPEC.md`) 작성

#### 2-1. 우측 웹 메신저에서 현업 책임 에이전트(페르소나)에게 DM 질의
* **참조할 파일**: **`docs_kit/stakeholder_inquiry_guide.md`** (또는 `prompt_bank/step_by_step_prompts.md` 라인 23~37)
* **어디에 입력?**: 플랫폼 우측 **DM 메신저 (업무 담당자 챗봇)**

* **[1차 DM 전송] (복사해서 메신저에 붙여넣기)**:
  ```text
  안녕하세요 담당자님! 현업에 실질적으로 도움이 되는 시스템을 설계하기 위해 몇 가지 여쭙습니다.
  1) 현재 이 업무에서 가장 시간이 오래 걸리거나 실수가 발생하는 최대 병목 구간은 어디이며, 지금까지는 어떤 방식(수작업 엑셀 등)으로 해결해 오셨나요?
  2) 유관 부서나 현업 실무자로부터 가장 많이 들어오는 민원(불만 사항)은 무엇인가요?
  3) 이번 1차 배포에서 반드시 100% 해결해야 하는 1순위 핵심 기능과 제외해도 되는 기능의 경계를 알려주시면 집중하여 구현하겠습니다!
  ```

* **[2차 DM 전송] (1차 답변 수신 후, `.fde_data_profile.md` 내용 반영하여 붙여넣기)**:
  ```text
  상세한 답변 감사드립니다! 데이터를 코드로 정밀 분석해 보니 일부 결측치(Null/-999)와 경계 조건이 확인되어 추가 확인 부탁드립니다.
  1) 데이터 내 결측치나 센티널(-999) 값은 전체 통계 분모에서 완전히 제외할까요, 아니면 별도 오류 상태로 화면에 분류할까요? 또한 중복 식별자 유입 시 최신 1건만 유지하면 될까요?
  2) 정상/경고/위반을 가르는 임계치 숫자와 정확히 일치할 때 이상(>=)과 초과(>) 중 어느 쪽으로 판정해야 하나요?
  3) 시스템 판정 결과에 대한 최종 책임(Accountability)을 위해 화면 리포트와 감사 로그(Audit Trail)에 반드시 남겨야 할 필수 항목(규칙 ID, 근거 수치, 권장 SOP, 담당자 승인 버튼 등)을 알려주세요!
  ```

#### 2-2. 총 계획서(`SPEC.md`) 및 5대 대안 비교표(`SOLUTION_NOTES.md`) 생성
* **참조할 파일**: **`prompt_bank/step_by_step_prompts.md`** 의 **`[Step 1: 00:08]`** 섹션
* **실행 위치**: **`[Terminal #1]` (Codex CLI 메인 에이전트)**
* **Codex에 붙여넣을 프롬프트**:
  ```text
  AGENTS.md를 읽고 핵심 원칙(80/20 분리, 3-터미널 역할)을 숙지해 줘.
  아직 src/ 코드는 작성하지 마. 토큰 절약을 위해 원본 데이터 파일을 직접 cat으로 읽지 말고, 서브 에이전트가 만든 .fde_data_profile.md 요약본과 README.md, 그리고 방금 내가 담당자 DM으로 확인한 아래 답변 내용을 결합하여 루트에 SPEC.md와 SOLUTION_NOTES.md를 작성해 줘.

  [담당자 DM 확인 내용]:
  (여기에 방금 메신저로 받은 담당자의 답변 내용을 그대로 붙여넣으세요)

  1. SOLUTION_NOTES.md (5대 아키텍처 대안 비교 및 책임 소재 설계):
     - 문제 해결 대안 5가지(① 80/20 결정론 코어+AI Fallback 웹앱, ② 100% LLM 연산 처리, ③ 무거운 외부 DB+MSA, ④ AI 없는 하드코딩 스크립트, ⑤ 클라이언트 원본 렌더링)의 장단점을 비교표로 작성.
     - 1번을 선정한 이유와 나머지 4개를 기각한 사유(환각 위험, OOM, 유지보수성 등)를 명확히 서술.
     - 책임 소재(Accountability): "1차 수치/규칙 무결성 책임은 결정론 코어(80%)가 지고, AI(20%)는 보조 요약만 제공하며, 최종 예외 승인 책임은 감사 로그와 함께 현업 담당자에게 귀속한다"고 명시.

  2. SPEC.md (요구사항 서면 합의서 및 9단계 순차 구현 실행서):
     - 문제 정의 및 기존 수작업 한계, 최다 민원 해결 목표.
     - 실무자 DM 확인 불변 규칙 (결측치 -999 전처리 기준, 중복 제거, 등호 기준).
     - 매핑된 레퍼런스 솔버(engine/solver_*.py)의 수리 알고리즘 이식 계획.
     - 1단계부터 9단계까지 순차적 구현 로드맵 (Step 1~2: 파서/골든샘플 ➔ Step 3~4: 코어 수치/임계치 판정 ➔ Step 5: 솔버/결과JSON ➔ Step 6: AI Fallback ➔ Step 7~8: 대시보드 UI/What-If ➔ Step 9: 게이트키퍼)과 예정 [구현 좌표: 파일명 - 함수명()] vs Out-of-Scope 범위.
  ```

* **2차 로컬 Git 커밋 실행 (`[Terminal #3]`에서 실행)**:
  ```bash
  git add -A
  git commit -m "docs: evaluate 5 alternatives, accountability rules, and complete SPEC.md"
  ```

---

### 🔥 Step 3. [00:45 ~ 02:45] [가장 중요한 본체] 코어 룰 정밀 코딩 & TDD 하네스 검증 (2시간 집중)

이 단계가 해커톤의 성패를 가르는 가장 핵심 코딩 구간입니다. 외부 라이브러리 없는 순수 함수(Pure Function)로 코어 규칙을 짜고, 3초짜리 하네스로 즉시 검증하며 완성합니다.

#### 3-1. 결정론 코어 로직 집중 코딩 지시
* **참조할 파일**: **`prompt_bank/step_by_step_prompts.md`** 의 **`[Step 3-A: 00:40]`** 섹션
* **실행 위치**: **`[Terminal #1]` (Codex CLI)**
* **Codex에 붙여넣을 프롬프트**:
  ```text
  SPEC.md와 매핑된 레퍼런스 솔버(engine/solver_*.py)를 기반으로, UI나 외부 네트워크 호출 없이 오직 src/data/samples.js(전처리 파서)와 src/core/rules.js(결정론 코어 엔진)의 로직만 완벽하게 구현해 줘.

  1. src/data/samples.js:
     - Null, 빈 문자열, NaN, 센티널 -999, INVALID 플래그 등 어떠한 비정상 데이터가 유입되어도 크래시 없이 분리하는 sanitizeAndParseInput() 함수 완성.
     - 과제 스키마에 맞춘 3종 골든 샘플(normal, warning, violation) 데이터 객체 작성.

  2. src/core/rules.js:
     - evaluateCoreRules(inputPayload): SPEC.md에서 확정한 임계치 상수(THRESHOLD_CONFIG), 계산 수식, 이상치 격리, 적용 규칙 ID(ruleId), 점수(score)를 산출하는 100% 순수 함수로 구현.
     - 도메인 특화 수식(포토 HOWA/Feedforward, 소재 Cpk/유사도, 시장 OPM/Mix, 밸류체인 ROIC, 교육 DAG, 범용 최적화 등)을 완벽히 이식할 것.
  ```

#### 3-2. TDD 하네스 즉시 검증 (코드 수정할 때마다 수시로 실행!)
* **실행 위치**: **`[Terminal #3]` (서브 에이전트 창)**
* **입력할 명령어 (소요 시간: 3초)**:
  ```bash
  node engine/deterministic_harness.mjs
  ```
  - **목표**: `📊 최종 하네스 성적표: 6 / 6 항목 완벽 통과` 가 뜰 때까지 `src/core/rules.js` 코드를 보강합니다.
* **최적화 솔버 연동 및 결과 파일 갱신**:
  ```bash
  python engine/auto_solver_pipeline.py --workspace .
  # output/result.json 파일이 최신 결과로 갱신되었는지 확인
  ```

* **3차 로컬 Git 커밋 실행 (`[Terminal #3]`에서 실행)**:
  ```bash
  git add -A
  git commit -m "feat: implement deterministic core rules and pass 6/6 harness"
  ```

---

### 🖥️ Step 4. [02:45 ~ 03:45] 웹 콘솔 스캐폴딩 & 0.0.0.0 실시간 프리뷰

#### 4-1. 앱 스캐폴딩 실행
* **실행 위치**: **`[Terminal #3]` (서브 에이전트 창)**
* **입력할 명령어**:
  ```bash
  python engine/scaffold_app.py
  npm install
  ```

#### 4-2. 0.0.0.0 실시간 서버 기동 (대회 종료까지 유지)
* **실행 위치**: **`[Terminal #2]` (웹 서버 전용 창으로 이동!)**
* **입력할 명령어**:
  ```bash
  npm run dev
  ```
  - `0.0.0.0:5173` 주소로 서버가 기동되며, 이 터미널은 절대 닫지 않습니다.

#### 4-3. AI 어댑터 및 대시보드 UI 연동 지시
* **참조할 파일**: **`prompt_bank/step_by_step_prompts.md`** 의 **`[Step 3-B: 01:00]`** 섹션
* **실행 위치**: **`[Terminal #1]` (Codex CLI)**
* **Codex에 붙여넣을 프롬프트**:
  ```text
  검증된 src/core/rules.js 코어와 src/ai/reporter.js, 그리고 src/components/Dashboard.jsx를 연결해 줘.
  1. src/ai/reporter.js: AI API 호출 실패나 1.5초 타임아웃 시 0.1초 내로 코어 판정 수치 기반 표준 SOP 리포트를 반환하는 generateInsightWithFallback() 구현.
  2. src/components/Dashboard.jsx:
     - 상단에 3종 골든 샘플 버튼([정상 샘플], [경고 샘플], [위반 샘플]) 클릭 시 상태 배지(NORMAL/WARNING/VIOLATION)가 즉시 바뀌도록 바인딩.
     - "📂 실제 과제 파일 자동 로드" 버튼 및 "💾 결과 JSON 파일 Export" 버튼 동작 확인.
     - What-If 제약 슬라이더로 파라미터 변경 시 코어 수치가 실시간 반응하도록 연결.
  ```

* **내장 브라우저(`http://0.0.0.0:5173`)에서 직접 눈으로 확인**:
  - 버튼 클릭 시 상태 배지 색상 변화 확인 (초록/노랑/빨강)
  - What-If 슬라이더 조작 시 수치 변화 확인
  - AI 503 장애 유발 체크박스 체크 시 0.1초 내 Fallback 리포트 복구 확인

* **4차 로컬 Git 커밋 실행 (`[Terminal #3]`에서 실행)**:
  ```bash
  git add -A
  git commit -m "feat: scaffold web console and verify 0.0.0.0 live preview"
  ```

---

### 📝 Step 5. [03:45 ~ 05:15] 평가위원용 3대 필수 문서 완성

평가위원이 채점 시 정독하는 3대 문서를 완성합니다.

* **실행 위치**: **`[Terminal #1]` (Codex CLI)**
* **Codex에 붙여넣을 프롬프트**:
  ```text
  지금까지 구현된 실제 파일 경로와 함수명을 바탕으로 루트 경로의 3대 문서를 최종 완성해 줘.

  1. SPEC.md: In-Scope 항목 옆에 실제 구현된 파일과 함수명을 [구현 좌표: 파일명 - 함수명()] 형식으로 100% 매핑.
  2. SOLUTION_NOTES.md: 5대 아키텍처 대안 비교표, 1개 선정 및 4개 기각 사유, 결정론 코어 80% / AI 20% 책임 소재(Accountability) 매트릭스를 정밀 보강.
  3. HANDOFF.md: 유지보수자를 위한 인계서 작성:
     - 0.0.0.0 서버 실행 방법 (`npm run dev`)
     - 비즈니스 임계치 수정 위치 (`src/core/rules.js` 상단 THRESHOLD_CONFIG)
     - 결정론 하네스 실행 명령어 (`node engine/deterministic_harness.mjs`)
     - [3단 리스크 분석]: 실제 구현된 파일명/함수를 지목한 기술적 한계점 3가지, 비즈니스 파급 위험, 향후 개선 계획 상세 서술.
  ```

* **5차 로컬 Git 커밋 실행 (`[Terminal #3]`에서 실행)**:
  ```bash
  git add -A
  git commit -m "docs: finalize SPEC, SOLUTION_NOTES, and HANDOFF documentation"
  ```

---

### 🛡️ Step 6. [05:15 ~ 06:00] 최종 게이트키퍼 무결성 감사 & 안전 제출

제출 직전 감점 요인을 완전히 없애기 위해 자동 게이트키퍼 검사를 돌립니다.

* **실행 위치**: **`[Terminal #3]` (서브 에이전트 창)**
* **입력할 명령어**:
  ```bash
  # 1. 11대 솔버 전수 검증 (11/11 PASS 확인)
  python engine/blackbox_emulator.py --verify-solvers

  # 2. JS 결정론 코어 하네스 (6/6 PASS 확인)
  node engine/deterministic_harness.mjs

  # 3. 최종 게이트키퍼 7대 관문 검사 (PASS: 7 | WARN: 0 | FAIL: 0 확인)
  python engine/final_gatekeeper.py .
  ```

* **최종 Git 커밋 및 상태 확인 (`[Terminal #3]`에서 실행)**:
  ```bash
  git add -A
  git commit -m "chore: final submission readiness verified by gatekeeper"
  git status
  # "nothing to commit, working tree clean" 확인!
  ```

* **제출 확인**:
  - `output/result.json` 파일 존재 확인.
  - 웹 IDE의 모든 열린 파일 탭에서 `Ctrl + S`를 눌러 저장 상태 확인 후 **최종 제출 완료!**
