# 🚀 FDE-Autopilot 실전 사용자 가이드 (Step-by-Step)

이 가이드는 응시 환경(Cofa 웹 IDE)에서 어떤 도메인의 과제가 주어지더라도 처음부터 끝까지 막힘없이 프로젝트를 분석, 설계, 개발, 검증 및 최종 제출할 수 있도록 돕는 **통합 실행 매뉴얼**입니다.

우리가 준비한 **19개의 핵심 파일**이 각 단계마다 자연스럽게 등장하니, 적힌 순서대로만 차근차근 따라오시면 됩니다!

## 📂 시작 전 가볍게 보는 전체 파일 구성 (19개 파일)

작업을 시작하기 전, 우리 폴더 안에 어떤 도구들이 준비되어 있는지 한눈에 확인해 보세요.

* **루트 폴더 (`/`)**: 원클릭 초기 세팅 스크립트(`bootstrap.sh`), 환경 설정 파일(`config.toml`), 코딩 AI 헌법(`AGENTS.md`), 독립 감사관 기준서(`AUDITOR_GUIDE.md`), 그리고 지금 보고 계신 통합 매뉴얼(`fde_autopilot.md`)
* **`engine/` 폴더 (서브 에이전트 스크립트)**: 폴더 및 데이터 자동 분석기(`workspace_inspector.py`, `workspace_profiler.py`), 앱 뼈대 자동 생성기(`scaffold_app.sh`), 핵심 로직 테스트 도구(`verify_core.mjs`, `deterministic_harness.mjs`), 제출 전 최종 검수 도구(`release_gate.py`, `final_gatekeeper.py`)
* **`docs_kit/` 폴더**: 실무자 10대 심층 질문 가이드(`stakeholder_inquiry.md`), 기획서 템플릿(`SPEC_TEMPLATE.md`), 5대 대안 비교 및 책임 소재 보고서(`ARCHITECTURE_DECISIONS.md`), 최종 인계서 템플릿(`HANDOFF_TEMPLATE.md`), 서술형 방어 논리 가이드(`defense_logic_guide.md`)
* **`prompt_bank/` 폴더**: 문제 유형 판별 및 타이핑 모범답안(`typing_guide.md`), 단계별 복붙용 AI 프롬프트(`step_by_step_prompts.md`)

---

## 🖥️ 0. 시험 환경 필수 수칙 & 3-터미널(메인/서브 에이전트) 분리 세팅

작업이 꼬이거나 AI가 환각(Hallucination)을 일으키는 것을 막기 위해, 시작 직후 터미널 창의 `+` 버튼(또는 분할 버튼)을 눌러 **총 3개의 터미널 탭**을 역할별로 나누어 세팅합니다.

1. **터미널 1 [메인 에이전트 - Codex 조종석]**:
   * 오직 `codex` CLI만 켜두는 전용 창입니다. 과제 시작부터 끝까지 끄지 않고 자연어 지시, 5가지 아키텍처 대안 도출, 코드 생성만 담당합니다.
   * 실행 직후 `/status`로 권한을 확인하고 `/model`에서 권장 모델(`Sol 6.1`, `Terra 5.6`, `Luna 6`, `Sol 6.0`)을 선택합니다 (`Astra` 사용 절대 금지, 개인 API 키 사용 금지).
2. **터미널 2 [실시간 서버 - 화면 미리보기용]**:
   * `npm run dev` 등으로 `0.0.0.0` 웹 서버를 띄워두고 계속 켜두는 창입니다. 우측 상단 Browser 도구에서 실시간으로 화면(UI)을 확인하기 위해 절대 닫지 않습니다.
3. **터미널 3 [서브 에이전트 - 결정론적 검증 & Git 기록소]**:
   * 메인 에이전트(터미널 1)의 환각 개입 없이 객관적으로 데이터를 분석(`workspace_profiler.py`)하고, 코드를 테스트(`verify_core.mjs`, `deterministic_harness.mjs`)하며, 매 단계 로컬 `git commit`을 기록하는 검사소입니다.
   * **외부 전송(`git push`)은 절대 금지**되지만, **로컬 `git 로그·diff`와 테스트 실행 결과는 평가에 직접 반영**되므로 모든 검증과 커밋은 이 3번 터미널에서 수행합니다.
4. **에디터 저장 충돌 방지**: 터미널 1의 Codex가 파일을 수정했을 때 에디터에서 충돌이 뜨면 **"외부 변경 불러오기"**를 선택해 AI가 작성한 최신 코드를 유지하고, 제출 전 모든 탭이 **"저장됨"** 상태인지 확인하세요.

---

## 🏁 Step 1. 작업 환경 준비 및 서브 에이전트 데이터 자동 분석 (초기 15분)

가장 먼저 내 작업 폴더에 어떤 파일과 데이터가 들어있는지 **터미널 3(서브 에이전트)**의 파이썬 스크립트를 통해 결정론적으로 파악합니다. LLM에게 대용량 원본 데이터를 직접 읽히면 토큰이 낭비되고 환각이 발생하므로 반드시 스크립트로 먼저 스캔하세요.

### 1. 과제 안내서 확인 (`README.md`)
* 루트의 과제 `README.md`를 열어 **과제 목표, 필수 구현 조건, 필수 제출 문서 파일명**을 가장 먼저 확인합니다.

### 2. 원클릭 초기 진단 실행 (`bootstrap.sh` 👉 터미널 3에서 실행)
* **터미널 3**을 열고 아래 명령어를 입력합니다.
  ```bash
  bash bootstrap.sh --workspace .
  ```
* **이 명령어가 하는 일**: 실수로 `git push`를 하지 못하도록 차단 훅을 걸고, 내부적으로 아래 두 개의 서브 에이전트 분석 스크립트와 문서 템플릿들을 자동으로 세팅해 줍니다.
  * **`engine/workspace_inspector.py`**: 현재 폴더 안의 파일 목록, 문서, 데이터 파일(CSV, JSON, SQLite 등)의 위치와 용량을 스캔하여 `WORKSPACE_PROFILE.md`로 정리합니다.
  * **`engine/workspace_profiler.py`**: LLM이 아닌 고정 코드로 데이터의 컬럼명, 결측치(`Null`, `-999`), 중복 데이터, 통계적 임계치(3-Sigma), 그리고 실무자 에이전트에게 물어봐야 할 질문 후보를 `.fde_data_profile.md` 파일로 정확히 도출해 줍니다.
  * **문서 초안 자동 복사**: `docs_kit/` 폴더 안에 있는 `SPEC_TEMPLATE.md`, `ARCHITECTURE_DECISIONS.md`, `HANDOFF_TEMPLATE.md`를 루트 폴더에 각각 `SPEC.md`, `SOLUTION_NOTES.md`, `HANDOFF.md`라는 이름으로 미리 복사해 둡니다.

### 3. 베이스라인 Git 커밋 기록 (터미널 3)
* 초기 분석과 세팅이 끝났다면 **터미널 3**에서 첫 번째 로컬 커밋을 남깁니다.
  ```bash
  git add -A && git commit -m "chore: initial workspace scan and deterministic data profile"
  ```

---

## 🎯 Step 2. 실무자 10대 심층 질문, 5대 대안 비교 및 기획(`SPEC.md`) 확정

데이터와 요구사항을 확인했다면, 우측 메신저(DM)의 **업무 담당자(실무자 에이전트)**에게 핵심 질문을 던지고, 메인 에이전트(Codex)와 함께 5가지 설계 대안과 책임 소재를 고민하여 기획서를 확정합니다.

### 1. 범용 문제 아키타입(Type A~D) 판별하기 (`prompt_bank/typing_guide.md`, `config.toml`)
* `prompt_bank/typing_guide.md` 파일의 **Part 1 판별표**와 `.fde_data_profile.md`의 추천 결과를 보고, 오늘 해결해야 할 과제가 아래 **4대 소프트웨어 아키타입 중 어디에 속하는지** 결정합니다.
  * **Archetype A (지표 모니터링 및 이상 탐지 대시보드)**: 시계열/수치 데이터를 차트와 요약 카드로 보여주고, 임계치 기반 이상 징후를 색상과 표로 필터링하는 시스템.
  * **Archetype B (규칙 검증 및 차분/Diff 알람 도구)**: 입력된 설정값, 로그, 데이터가 비즈니스 규칙에 맞는지 검사하고, 이전 버전/기준값과 무엇이 달라졌는지 비교(Diff)해 알람을 띄우는 도구.
  * **Archetype C (문서 검색 및 출처/Citation 기반 질의응답)**: 규정, 매뉴얼, 가이드 문서를 검색하고, 답변을 제시할 때 반드시 원본 문서의 근거 조항(Citation)을 함께 표시하며 문서 외 질문은 거절하는 도구.
  * **Archetype D (상태 머신 및 승인 백오피스 워크플로우)**: 요청 $\rightarrow$ 검토 $\rightarrow$ 승인/반려처럼 단계별로 상태(State)가 전이되고, 권한별 액션 제어 및 처리 이력(Audit Log)을 남기는 시스템.
* 유형을 골랐다면 **`config.toml`** 파일을 열어 `default_type = "A"` 부분에 내가 선택한 알파벳(`A`, `B`, `C`, `D`)을 적고 저장합니다.

### 2. 실무자 에이전트(업무 담당자 DM)에게 10대 심층 질문 기반으로 차례대로 물어보기 (`docs_kit/stakeholder_inquiry.md`)
* **`docs_kit/stakeholder_inquiry.md`** 파일을 열면 담당자에게 차례대로 물어볼 수 있는 **10가지 핵심 질문 리스트**(① 현재 가장 큰 병목 지점, ② 지금까지의 임시 해결 방식, ③ 현업에서 가장 많이 들어오는 민원, ④ 최우선 해결 과업, ⑤ 결측치/이상치 처리, ⑥ 중복 데이터 기준, ⑦ 경계값 등호 기준, ⑧ 다중 알람 우선순위, ⑨ 자동 판정 결과에 대한 최종 책임 소재, ⑩ 필수 출력 항목)가 준비되어 있습니다.
* 한 번에 10개를 다 보내지 말고, `prompt_bank/step_by_step_prompts.md`의 `[00:02]` 가이드처럼 **1차 질문(현재 문제점·기존 해결방식·최다 민원 파악) $\rightarrow$ 답변 확인 $\rightarrow$ 2차 질문(결측치·경계값·책임 소재 확정)** 순서로 자연스럽게 대화를 이어가세요.
* **중요 (상충 해결 원칙)**: 만약 `README.md`의 설명이 모호하거나 실무자 에이전트의 답변과 상충할 경우, 실무자 에이전트의 답변을 최종 기준(Ground Truth)으로 반영하고 제출 문서에 *"업무 담당자와의 DM 협의를 통해 ~기준으로 확정함"*이라고 명확히 인용합니다.

### 3. 5가지 대안 비교(선정/거절 이유), 책임 소재 정립 및 `SPEC.md` 작성 (`docs_kit/SPEC_TEMPLATE.md`, `docs_kit/ARCHITECTURE_DECISIONS.md`)
* **터미널 1(메인 에이전트 Codex)** 입력창에 **`prompt_bank/step_by_step_prompts.md`의 `[Step 1: 00:08]` 프롬프트**를 복사해 붙여넣습니다.
* **이 단계에서 Codex가 수행하는 핵심 사고 과정**:
  1. 코딩을 시작하기 전에 문제를 해결할 수 있는 **5가지 아키텍처/기능 대안을 먼저 제안**합니다.
  2. 그중 **가장 적합한 1가지를 선정한 이유**와 **나머지 4가지를 거절(기각)한 이유**를 명확히 분석합니다.
  3. 시스템 판정 오류 시 **최종 책임(Accountability)을 누가 질 것인가**에 대해 고민하고, *"1차 수치/규칙 필터링 책임은 결정론 코어(80%)가 지고, AI(20%)는 참고용 조언만 제공하며, 최종 승인 권한과 감사 로그(Audit Trail) 책임은 현업 담당자에게 귀속시킨다"*는 방어 논리와 검증 계획을 수립하여 `SPEC.md`와 `SOLUTION_NOTES.md`(`ARCHITECTURE_DECISIONS.md`)에 기록합니다.
* 문서 생성이 완료되면 **터미널 3**에서 로컬 커밋을 남깁니다.
  ```bash
  git add -A && git commit -m "docs: evaluate 5 alternatives, accountability rules, and complete SPEC.md"
  ```

---

## 🏗️ Step 3. 통합 앱 뼈대 자동 생성 및 Codex 단계별 코딩

이제 직접 초기 코드를 다 짤 필요 없이, 스크립트로 통합 앱 뼈대를 만들고 **터미널 1의 메인 에이전트(Codex)**에게 단계별로 구현을 위임합니다.

### 1. 통합 앱 뼈대(Scaffold) 자동 생성 (`engine/scaffold_app.sh` 👉 터미널 3에서 실행)
* **터미널 3**에 아래 명령어를 입력합니다.
  ```bash
  bash engine/scaffold_app.sh --target . --type A --stack nextjs
  ```
* **이 명령어가 하는 일**: 어떤 도메인 문제든 하나의 통합 웹앱으로 구현할 수 있도록 `src/data`, `src/core`, `src/ai`, `src/components` 4대 레이어 폴더 구조와 `0.0.0.0` 바인딩이 내장된 `package.json`, `vite.config.js`를 자동으로 만들어 줍니다.

### 2. 단계별 프롬프트로 코딩 위임 및 단계별 Git Commit (`prompt_bank/step_by_step_prompts.md`)
* **터미널 1(Codex)**에 `prompt_bank/step_by_step_prompts.md`의 프롬프트를 순서대로 복사해 지시하고, 각 단계가 끝날 때마다 **터미널 3**에서 검증 및 `git commit`을 수행합니다.
  1. **Step 2 프롬프트 (4-Layer 스캐폴딩 & E2E v0 관통)**: 3종 골든 샘플(`src/data/samples.js`), 결정론 코어(`src/core/rules.js`), AI 리포터(`src/ai/reporter.js`), 대시보드 화면(`src/components/Dashboard.jsx`)을 연결합니다.
     * 곧바로 **터미널 2**에서 `npm install && npm run dev`로 `0.0.0.0` 서버를 띄우고, **터미널 3**에서 커밋합니다:
       ```bash
       git add -A && git commit -m "feat: scaffold 4-layer architecture and e2e v0"
       ```
     * *(팁: 터미널 1의 Codex 대화 로그가 길어지면 `/clear`를 입력해 토큰을 절약하세요!)*
  2. **Step 3-A 프롬프트 (전처리 파서 및 Core 결정론 로직 정밀 구현)**: 어떠한 비정상 데이터(결측치, 타입 오류, 빈 배열 등)가 들어와도 LLM이 아닌 고정 코드로 전처리하고 계산하는 `sanitizeAndParseInput()`과 `evaluateCoreRules()`를 완벽히 구현하게 합니다.
     * 구현 직후 **터미널 3**에서 검증 스크립트를 돌리고 커밋합니다:
       ```bash
       node engine/verify_core.mjs && node engine/deterministic_harness.mjs
       git add -A && git commit -m "feat: implement deterministic data preprocessor and core rules"
       ```
  3. **Step 3-B 프롬프트 (AI/UI 결합 및 SPEC 증거 좌표 매핑)**: 코어 판정 결과를 화면 배지(NORMAL/WARNING/VIOLATION) 및 AI Fallback 리포트와 연결하고, `SPEC.md`의 각 기능 옆에 실제 구현된 파일명과 함수명(`[구현 좌표: src/core/rules.js - evaluateCoreRules()]`)을 적어넣게 합니다.
     * **터미널 3**에서 커밋합니다:
       ```bash
       git add -A && git commit -m "feat: connect UI, AI fallback, and map SPEC coordinates"
       ```

---

## 🔍 Step 4. 서브 에이전트 무결성 검증 및 내장 Browser 확인

코드를 작성할 때마다 **터미널 3(서브 에이전트)**의 두 검증 스크립트와 **터미널 2 + Browser 도구**를 통해 실제 동작을 교차 검증합니다.

### 1. 핵심 로직 테스트 및 5대 시나리오 하네스 실행 (`engine/verify_core.mjs`, `engine/deterministic_harness.mjs` 👉 터미널 3)
* **터미널 3**에서 아래 두 명령어를 실행합니다.
  ```bash
  node engine/verify_core.mjs
  node engine/deterministic_harness.mjs
  ```
* **이 두 서브 에이전트 스크립트가 하는 일**:
  * **`engine/verify_core.mjs`**: 숫자 변환 안전성, 상·하한 경계값 판정, `null`이나 빈 문자열(`""`) 입력 시 크래시가 없는지 단언(Assertion) 테스트를 수행합니다.
  * **`engine/deterministic_harness.mjs`**: `src/core/rules.js`와 `src/data/samples.js`를 불러와서 **① 정상 케이스, ② 경계값(Warning) 케이스, ③ 위반(Violation) 케이스, ④ 파괴적 Null 입력 방어, ⑤ AI API 타임아웃 시 0.1초 내 결정론 Fallback 리포트 복구**까지 5가지 시나리오가 모두 `PASS(5/5)`하는지 객관적으로 증명합니다.

### 2. 내장 Browser 미리보기 검증 (터미널 2 유지 상태)
* **PORT 및 URL 연결**: **터미널 2**에 출력된 실제 포트 번호(예: `5173`, `3000` 등)를 내장 Browser 도구의 `PORT` 입력란에 넣고 새로고침(원형 화살표)을 누릅니다.
* **기능 직접 클릭**: 상단의 3종 골든 샘플 버튼(정상/경고/위반), 필터, 입력창을 직접 클릭해 상태 배지와 수치가 즉시 바뀌는지 확인합니다.

---

## 📝 Step 5. 최종 제출 문서 완성 및 독립 감사관(Auditor) 교차 검증

제출 문서는 Codex와 대화하여 작성할 수 있으며 AI 활용으로 인한 불이익이 없습니다. 단, **과제 `README.md`에서 요구한 필수 파일명**이 있다면 반드시 그 파일명으로 맞추어 저장하세요.

### 1. 인수인계서 및 5대 대안/책임 소재 보고서 완성 (`docs_kit/HANDOFF_TEMPLATE.md`, `docs_kit/ARCHITECTURE_DECISIONS.md`)
* **터미널 1(Codex)** 입력창에 **`prompt_bank/step_by_step_prompts.md`의 `[Step 4-A: 01:20]` 프롬프트**를 복사해 붙여넣습니다.
* Codex가 루트 경로의 **`HANDOFF.md`**와 **`SOLUTION_NOTES.md`**(또는 `ARCHITECTURE_DECISIONS.md`)를 실제 구현된 파일명·함수명에 맞춰 최종 완성합니다.
  * **`SOLUTION_NOTES.md` (`ARCHITECTURE_DECISIONS.md`)**: 80/20 분리 원칙, **5가지 대안 중 최선책 1개 선정 및 4개 거절 사유**, **오판 시 책임 소재(Accountability) 및 검증 체계**, 실무자 DM 협의 반영 내용을 담습니다.
  * **`HANDOFF.md` (`HANDOFF_TEMPLATE.md`)**: 데이터 파이프라인 흐름도와 함께, 사후 서술형 대비용 3단계 기술 리스크 분석(구체적 약점 지목 $\rightarrow$ 현장 파급 위험 $\rightarrow$ 정량적 검증 및 개선 계획)을 담아냅니다.

### 2. 서브 에이전트 독립 품질 감사관(Auditor) 점검 (`AUDITOR_GUIDE.md`)
* **터미널 3**에서 새로운 검증 세션으로 점검하거나, **`prompt_bank/step_by_step_prompts.md`의 `[Step 4-B: 01:30]` 프롬프트**를 사용해 `AUDITOR_GUIDE.md`의 4대 감사 기준(① 문서와 실제 코드 함수명 불일치 적발, ② 빈 값/특수문자 입력 시 크래시 방어 패치, ③ 3종 골든 샘플 동작 확인, ④ `HANDOFF.md` 리스크 분석 정밀화)을 최종 점검합니다.

---

## 🚪 Step 6. 최종 관문(Gatekeeper) 통과, 제출 및 후속 서술형 대비 (종료 10분 전)

작업 시간(180분) 종료 **최소 10분 전**에는 코드 수정을 멈추고 **터미널 3**에서 최종 검수 스크립트 실행 및 제출 절차를 시작합니다.

### 1. 릴리즈 게이트 및 최종 게이트키퍼 실행 (`engine/release_gate.py`, `engine/final_gatekeeper.py` 👉 터미널 3)
* **터미널 3**에서 임시 분석 파일을 지우고 마지막 로컬 커밋을 남긴 뒤, 두 개의 최종 검수 스크립트를 실행합니다.
  ```bash
  rm -f .fde_data_profile.md .fde_audit_report.md
  git add -A && git commit -m "chore: pass final audit and prepare release"
  python3 engine/release_gate.py
  python3 engine/final_gatekeeper.py
  ```
* **이 두 스크립트가 하는 일**:
  * **`engine/release_gate.py`**: 루트 경로에 마크다운 문서가 비어있지 않은지, 코드에 `localhost` 바인딩이나 개인 API 키(`sk-...`)가 남아있지 않은지 스캔합니다.
  * **`engine/final_gatekeeper.py`**: Git 미커밋 여부, 보안 시크릿, `0.0.0.0` 바인딩, 필수 문서(`SPEC.md`, `HANDOFF.md`, `AGENTS.md`), `deterministic_harness.mjs` 통과 여부, 메모리(OOM) 상태까지 6대 관문을 종합 판정하고, **터미널 하단에 후속 서술형 대비 4문장 핵심 암기 브리핑을 출력**해 줍니다.
* 에디터 상단 탭을 모두 확인하여 저장되지 않은 변경(`●`)이나 충돌 표시가 없는지 확인하고 `Ctrl+S` (`Cmd+S`)로 완전히 저장합니다.

### 2. 후속 서술형(6문항 / 문항당 5분) 대비 핵심 키워드 암기 (`docs_kit/defense_logic_guide.md`, `prompt_bank/typing_guide.md`)
* 상단의 "제출하고 문제풀기" $\rightarrow$ "제출물 확정하고 문제풀기"를 누른 순간부터는 파일을 수정할 수 없으며, 이어지는 후속 서술형에서는 **AI 사용, 복사·붙여넣기(`Ctrl+V`), 책상 위 종이 메모지 사용이 전면 금지**됩니다 (100% 직접 타이핑 필수).
* 따라서 제출 확정 버튼을 누르기 직전, 터미널 3에 출력된 `final_gatekeeper.py` 요약본과 **`docs_kit/defense_logic_guide.md`**, **`prompt_bank/typing_guide.md` (Part 2 만점 공식)**를 눈으로 읽고 아래 4가지를 반드시 머릿속에 기억하고 넘어가세요:
  1. **내가 구현한 핵심 파일명과 함수명 3세트**:
     * 결정론 코어(80%): `src/core/rules.js` 의 `evaluateCoreRules()`
     * AI 및 Fallback 안전장치(20%): `src/ai/reporter.js` 의 `generateInsightWithFallback()`
     * 데이터 전처리 파서 및 3종 골든 샘플: `src/data/samples.js` 의 `sanitizeAndParseInput()` 및 `GOLDEN_SAMPLES`
  2. **5가지 대안 중 현재 아키텍처를 선정한 이유와 책임 소재(Accountability)**: LLM 단독 처리나 무거운 DB를 거절하고, 오판 책임을 명확히 통제하기 위해 산술 판정(80% 코어)과 해석(20% AI)을 분리했으며 최종 승인은 감사 로그와 함께 담당자에게 귀속시켰다는 점
  3. **실무자 에이전트(DM)와 협의하여 처리한 예외 기준 1개**: 결측치(`Null`/`-999`) 분리 기준 및 임계치 경계값 등호(`>=` vs `>`) 판정 기준
  4. **현재 구현의 한계점과 개선 방향 (3단 논법)**: 대용량 입력 시 단일 스레드 인메모리 순회 병목(약점) $\rightarrow$ 동시 유입 시 화면 블로킹 및 지연 위험(파급 위험) $\rightarrow$ 더미 부하 테스트로 임계치 계측 후 해시 캐싱·SQLite 영속화·Web Worker 비동기 큐 도입(검증 및 개선 계획)