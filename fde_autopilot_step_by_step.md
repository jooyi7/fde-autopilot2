# 🚀 FDE-Autopilot 실전 사용자 가이드 (Step-by-Step 마스터 버전)

이 가이드는 응시 환경(Cofa 웹 IDE)에서 어떤 도메인의 과제가 주어지더라도, 준비된 **19개의 핵심 범용 파일**을 100% 활용하여 처음부터 끝까지 막힘없이 프로젝트를 분석, 설계, 개발, 검증 및 최종 제출할 수 있도록 돕는 **통합 실행 매뉴얼**입니다.

---

## 📂 0. 전체 필수 파일 인벤토리 (총 19개 파일 점검)

작업을 시작하기 전, 도메인 편향을 모두 제거한 아래 19개의 핵심 파일이 준비되어 있는지 확인합니다.

* **루트 제어 및 규칙 (5개)**
  * `fde_autopilot.md`: 현재 보고 있는 전체 파이프라인 통합 실행 가이드
  * `AGENTS.md`: 내장 Codex CLI가 준수할 80/20 아키텍처 및 시험 규정 헌법
  * `AUDITOR_GUIDE.md`: 터미널 2번 독립 감사관(Auditor) 에이전트의 4대 검수 기준
  * `config.toml`: 허용 AI 모델(`Sol-6.1` 등), 문제 아키타입(`A~D`), `0.0.0.0` 호스트 설정
  * `bootstrap.sh`: `git push` 원천 차단, 환경 스캔, 문서 초안 배치를 한 번에 수행하는 초기화 스크립트
* **표준 문서 키트 (`docs_kit/` - 5개)**
  * `docs_kit/stakeholder_inquiry.md`: 실무자 에이전트(업무 담당자 DM) 대상 요구사항/엣지케이스 질의 가이드
  * `docs_kit/SPEC_TEMPLATE.md`: 요구사항 서면 합의서, 구현 증거 좌표, 7단계 상태 트래커 템플릿
  * `docs_kit/ARCHITECTURE_DECISIONS.md`: 80/20 설계 판단 근거, DM 협의 반영 내역, 한계점 기록 보고서
  * `docs_kit/HANDOFF_TEMPLATE.md`: 파이프라인 구조도 및 3단계 기술 리스크 분석 인수인계서 템플릿
  * `docs_kit/defense_logic_guide.md`: 후속 서술형(6문항×5분, 복붙 불가) 대비 만능 3문장 방어 논리 가이드
* **자동화 엔진 및 검증기 (`engine/` - 7개)**
  * `engine/workspace_inspector.py`: 폴더 트리, 설정 파일, 데이터셋 기본 구조 및 결측치 요약 스캐너
  * `engine/workspace_profiler.py`: 3-Sigma(UCL/LCL) 통계 임계치, 중복 키, 센티널 값(-999), DM 질문 트리거 자동 도출기
  * `engine/scaffold_app.sh`: 4대 레이어(`data`, `core`, `ai`, `components`) 및 `0.0.0.0` 바인딩 서버 뼈대 생성기
  * `engine/verify_core.mjs`: 코어 순수 함수의 정상값, 경계값(Boundary), Null 안전성 기본 단언(Assertion) 검증기
  * `engine/deterministic_harness.mjs`: 3종 골든 샘플(정상/경고/위반) + 파괴적 Null + AI 장애 Fallback 5대 시나리오 통합 하네스
  * `engine/release_gate.py`: 제출 직전 빈 문서, `localhost` 바인딩, API 키 하드코딩 적발 스크립트
  * `engine/final_gatekeeper.py`: 6대 최종 무결성 관문 점검 및 후속 서술형 대비 4대 암기 브리핑 출력기
* **범용 프롬프트 뱅크 (`prompt_bank/` - 2개)**
  * `prompt_bank/typing_guide.md`: 문제 아키타입(Type A~D) 1분 판별표 및 후속 서술형 3단 논법 타이핑 모범 답안
  * `prompt_bank/step_by_step_prompts.md`: 타임라인별 Codex CLI 복붙용 실전 프롬프트 세트

---

## ⚠️ 1. 시험 환경 필수 수칙 (가이드라인 완벽 준수)

1. **Codex 실행 및 모델 설정 (`config.toml`)**: 터미널에 `codex`를 입력해 실행한 뒤, `/status`로 권한을 확인하고 `/model`에서 **권장 모델(`Sol 6.1`, `Terra 5.6`, `Luna 6`, `Sol 6.0`)**을 선택합니다 (**`Astra` 사용 절대 금지**, 개인 API 키 사용 금지).
2. **외부 전송(`git push`) 금지 및 로컬 커밋 필수**: 외부로의 파일 전송이나 `git push`는 엄격히 금지됩니다. 반면 **로컬 `git 로그·diff`와 테스트 실행 결과는 평가에 직접 반영**되므로, 매 단계가 끝날 때마다 로컬 `git commit`을 남기세요.
3. **토큰 사용량 최적화**: 토큰 사용량이 추적되므로 Codex에게 질문할 때 원본 대용량 CSV/JSON을 통째로 읽히지 말고, 자동 생성된 요약 리포트(`.fde_data_profile.md` / `.autopilot/workspace_profile.md`)만 전달하세요.
4. **에디터 저장 충돌 방지**: 터미널의 Codex가 파일을 수정했을 때 에디터에서 충돌이 뜨면 **"외부 변경 불러오기"**를 선택해 AI가 작성한 최신 코드를 유지하고, 제출 전 모든 탭이 **"저장됨"** 상태인지 확인하세요.

---

## 🏁 Step 1. 작업 환경 초기화 및 데이터 자동 프로파일링 (00:00 ~ 00:10)

과제 시작 직후, 수동으로 파일을 열어보며 시간을 낭비하지 않고 자동화 스크립트로 워크스페이스를 해부합니다.

### 1. 과제 안내서 확인 (`README.md`)
* 루트의 과제 `README.md`를 열어 **과제 목표, 필수 구현 조건, 필수 제출 문서 파일명**을 가장 먼저 확인합니다.

### 2. 원클릭 부트스트랩 실행 (`bootstrap.sh`, `workspace_inspector.py`, `workspace_profiler.py`)
* 터미널 1번을 열고 아래 명령어를 실행합니다.
  ```bash
  bash bootstrap.sh --workspace .
  ```
* **이 명령어가 내부적으로 수행하는 5가지 작업**:
  1. `git push` 원천 차단 훅(`pre-push`)을 설치하여 실수로 인한 규정 위반을 방지합니다.
  2. 루트 경로에 **`AGENTS.md`**와 **`config.toml`**을 자동 배치합니다.
  3. **`engine/workspace_inspector.py`**를 실행해 전체 디렉터리 트리와 파일 크기를 `WORKSPACE_PROFILE.md` (및 `.autopilot/workspace_scan.md`)로 저장합니다.
  4. **`engine/workspace_profiler.py`**를 실행해 CSV/JSON/SQLite의 결측치, 중복 키, 센티널 값(-999), 수치형 3-Sigma(UCL/LCL) 통계치, 그리고 **실무자 DM 질문 트리거**를 `.fde_data_profile.md` (및 `.autopilot/workspace_profile.md`)로 자동 생성합니다.
  5. **`docs_kit/SPEC_TEMPLATE.md`**, **`docs_kit/ARCHITECTURE_DECISIONS.md`**, **`docs_kit/HANDOFF_TEMPLATE.md`**를 루트의 `SPEC.md`, `SOLUTION_NOTES.md`, `HANDOFF.md` 초안으로 복사합니다.

### 3. 베이스라인 Git 커밋 기록
* 초기 진단이 완료되면 첫 번째 로컬 체크포인트 커밋을 남깁니다.
  ```bash
  git add -A && git commit -m "chore: initial workspace scan and data profile"
  ```

---

## 🎯 Step 2. 문제 아키타입(A~D) 판별 및 실무자 DM 질문 확정 (00:10 ~ 00:20)

`.fde_data_profile.md` 리포트를 확인한 뒤, 문제 유형을 확정하고 우측 메신저(DM)의 **업무 담당자(실무자 에이전트)**에게 핵심 질문을 전송합니다. (플랫폼 사용법 문의는 `Cofa Helper`, 과제 업무 맥락 문의는 `업무 담당자`에게 구분하여 질문합니다.)

### 1. 범용 문제 아키타입(Type A~D) 판별 (`prompt_bank/typing_guide.md`, `config.toml`)
* **`prompt_bank/typing_guide.md`의 Part 1 표**와 `.fde_data_profile.md`의 추천 결과를 대조하여 오늘 과제가 아래 **4대 소프트웨어 아키타입 중 어디에 속하는지** 결정합니다.
  * **Archetype A (지표 모니터링 및 이상 탐지 대시보드)**: 시계열/테이블 데이터의 핵심 지표(KPI) 집계 및 임계치(UCL/LCL) 이탈 탐지·필터링 시스템.
  * **Archetype B (규칙 검증 및 차분/Diff 알람 도구)**: 입력된 설정값, 로그, 데이터가 비즈니스 규칙에 맞는지 검사하고, 이전 버전/기준값과 비교(Diff)해 심각도별 알람을 띄우는 도구.
  * **Archetype C (문서 검색 및 출처/Citation 기반 질의응답)**: 규정, 매뉴얼, 가이드 문서를 검색하고, 답변 시 반드시 원본 문서의 근거 조항(Citation)을 함께 표시하며 문서 외 질문은 거절하는 도구.
  * **Archetype D (상태 머신 및 승인 백오피스 워크플로우)**: 요청 $\rightarrow$ 검토 $\rightarrow$ 승인/반려처럼 단계별로 상태(State)가 전이되고, 권한별 액션 제어 및 처리 이력(Audit Log)을 남기는 시스템.
* 결정한 타입(`A`, `B`, `C`, `D`)을 **`config.toml`**의 `default_type`에 반영합니다.

### 2. 실무자 에이전트(업무 담당자 DM)에게 요구사항 질문 (`docs_kit/stakeholder_inquiry.md`, `prompt_bank/step_by_step_prompts.md`)
* `.fde_data_profile.md`의 **5번 섹션(DM 최우선 확인 트리거)**과 **`docs_kit/stakeholder_inquiry.md`**의 3대 질문 구조(① 결측치/예외 데이터 처리 기준, ② 경계값 등호 `>=` vs `>` 및 우선순위 기준, ③ 최종 결과물 필수 포함 항목)를 확인합니다.
* **`prompt_bank/step_by_step_prompts.md`의 `[00:02]` 섹션**에 있는 1차·2차 질문 문구를 복사해 우측 DM의 **업무 담당자**에게 전송합니다 (`Enter` 전송, `Shift+Enter` 줄바꿈).
* **중요 (README와 DM 상충 해결 원칙)**: 만약 `README.md`의 설명이 모호하거나 실무자 에이전트의 답변과 상충할 경우, **실무자 에이전트의 최신 답변을 최종 기준(Ground Truth)으로 채택**하고 이를 `SPEC.md`와 `SOLUTION_NOTES.md`에 *"업무 담당자와의 DM 협의를 통해 ~기준으로 확정함"*이라고 명확히 인용합니다.

### 3. 서면 합의서(`SPEC.md`) 및 에이전트 헌법(`AGENTS.md`) 확정
* 터미널 1번에서 `codex`를 실행하고, **`prompt_bank/step_by_step_prompts.md`의 `[Step 1: 00:08]` 프롬프트**를 복사해 붙여넣습니다.
* Codex가 **`AGENTS.md`**, **`README.md`**, **`.fde_data_profile.md`**, 그리고 DM 답변을 종합하여 루트의 **`SPEC.md`**(`docs_kit/SPEC_TEMPLATE.md` 기반)를 완성하도록 합니다.
* 완료 후 로컬 커밋을 남깁니다.
  ```bash
  git add -A && git commit -m "docs: complete SPEC.md and stakeholder inquiry rules"
  ```

---

## 🏗️ Step 3. 4-Layer 스캐폴딩 및 Codex 단계별 구현 (00:20 ~ 01:10)

직접 초기 코드를 다 짜지 않고, 스크립트로 4계층 구조를 생성한 뒤 내장 **Codex CLI**에게 단계별로 구현을 위임합니다.

### 1. 4-Layer 앱 뼈대 자동 생성 (`engine/scaffold_app.sh`)
* 터미널에 아래 명령어를 입력해 `src/data`, `src/core`, `src/ai`, `src/components` 4대 폴더와 `0.0.0.0` 바인딩이 기본 내장된 `package.json`, `vite.config.js`를 생성합니다.
  ```bash
  bash engine/scaffold_app.sh --target . --type A --stack nextjs
  ```
  *(별도 하위 폴더에 만들려면 `--target ./app`을 지정합니다.)*

### 2. E2E v0 관통 및 0.0.0.0 서버 구동 (`prompt_bank/step_by_step_prompts.md` - Step 2)
* Codex 입력창에 **`step_by_step_prompts.md`의 `[Step 2: 00:18]` 프롬프트**를 붙여넣어 4대 레이어를 연결합니다:
  1. `src/data/samples.js`: 3종 골든 샘플(`GOLDEN_SAMPLES`: 정상/경고/위반) 및 결측치 안전 파서(`sanitizeAndParseInput`)
  2. `src/core/rules.js`: 100% 결정론적 순수 함수 판정 엔진(`evaluateCoreRules`)
  3. `src/ai/reporter.js`: AI 요약 생성 및 에러/타임아웃 시 0.1초 내 결정론 리포트를 반환하는 안전장치(`generateInsightWithFallback`)
  4. `src/components/Dashboard.jsx`: 상단 3종 골든 샘플 원클릭 버튼, 핵심 지표 카드, 시각화 뷰어
* 완료 후 로컬 커밋을 수행하고, 컨텍스트가 길어졌다면 `/clear`로 토큰을 절약합니다.
  ```bash
  git add -A && git commit -m "feat: scaffold 4-layer architecture and e2e v0"
  ```

### 3. 결정론 코어 정밀 구현 및 AI/UI 결합 (`prompt_bank/step_by_step_prompts.md` - Step 3-A & 3-B)
* **`[Step 3-A: 00:40]` 프롬프트**를 Codex에 투입하여 `src/core/rules.js`에 모든 비즈니스 수식, 중복 제거, 결측치/센티널 방어 로직을 정밀하게 구현합니다.
* 이어서 **`[Step 3-B: 01:00]` 프롬프트**를 투입하여 코어 출력값을 `src/ai/reporter.js` 및 프론트엔드 UI 배지(NORMAL/WARNING/VIOLATION)와 결합하고, **`SPEC.md`의 In-Scope 항목 옆에 실제 구현된 `[구현 좌표: 파일명 - 함수명()]`을 매핑**합니다.

---

## 🔍 Step 4. 결정론 코어 검증, 내장 Browser 확인 및 독립 감사 (01:10 ~ 01:35)

구현된 코드가 엣지 케이스에서 죽지 않는지 두 개의 검증 스크립트와 내장 Browser 도구로 철저히 검증합니다.

### 1. 코어 단언 테스트 및 5대 시나리오 하네스 실행 (`engine/verify_core.mjs`, `engine/deterministic_harness.mjs`)
* 터미널에서 아래 두 명령어를 차례대로 실행합니다.
  ```bash
  node engine/verify_core.mjs
  node engine/deterministic_harness.mjs
  ```
* **검증 내용**:
  * **`verify_core.mjs`**: 수치 변환 안전성(`toSafeNumber`), 상·하한 경계값(`checkSpecLimit`), `null`/`""`/`NaN` 입력 방어를 기본 검증합니다.
  * **`deterministic_harness.mjs`**: 실제 구현된 `src/core/rules.js`와 `src/data/samples.js`를 자동으로 불러와 **① 정상 샘플, ② 경계값(Warning) 샘플, ③ 위반(Violation) 샘플, ④ 파괴적 `null` 입력 방어, ⑤ LLM API 503 장애 시 `DETERMINISTIC_FALLBACK_ENGINE` 자동 복구**까지 총 5가지 테스트가 모두 `PASS(5/5)`하는지 증명합니다.
* 통과 직후 로컬 커밋을 남깁니다.
  ```bash
  git add -A && git commit -m "test: pass verify_core and deterministic_harness 5 scenarios"
  ```

### 2. 내장 Browser 미리보기 검증 (필수)
* **전용 터미널 분할/탭 생성**: `+` 버튼으로 새 터미널을 열고 웹 서버를 실행합니다 (`npm run dev` 등). 이때 서버는 반드시 **`0.0.0.0`**에 바인딩되어야 합니다 (`localhost` 단독 바인딩 금지).
* **PORT 및 URL 연결**: 플랫폼 내장 Browser 도구의 `PORT` 입력란에 터미널에 출력된 실제 포트 번호(예: `5173`, `3000`, `8000` 등)를 입력하고 새로고침(원형 화살표)을 누릅니다.
* **기능 직접 클릭**: 화면 상단의 3종 골든 샘플 버튼, 필터, 입력창을 직접 클릭하여 화면이 정상 동작하는지 확인합니다. 확인하는 동안 **서버가 실행 중인 터미널 탭은 절대 닫지 마세요.**

---

## 📝 Step 5. 최종 문서 완성 및 터미널 2번 독립 감사관(Auditor) 실행 (01:35 ~ 01:50)

제출 문서는 Codex와 대화하여 작성할 수 있으며 AI 활용으로 인한 불이익이 없습니다. 단, **과제 `README.md`에서 요구한 필수 문서 파일명**이 있다면 반드시 그 파일명으로 맞추어 저장합니다.

### 1. 인수인계서 및 설계 판단 보고서 생성 (`docs_kit/HANDOFF_TEMPLATE.md`, `docs_kit/ARCHITECTURE_DECISIONS.md`)
* Codex에 **`prompt_bank/step_by_step_prompts.md`의 `[Step 4-A: 01:20]` 프롬프트**를 투입합니다.
* **`docs_kit/HANDOFF_TEMPLATE.md`**와 **`docs_kit/ARCHITECTURE_DECISIONS.md`**를 기반으로 루트 경로에 **`HANDOFF.md`**와 **`SOLUTION_NOTES.md`**(또는 `ARCHITECTURE_DECISIONS.md`)를 완성합니다.
* 이때 문서 내부에 **실제 구현한 파일명/함수명 좌표**, **실무자 DM 협의 근거**, **3단계 기술 리스크 분석(약점 지목 $\rightarrow$ 현장 파급 위험 $\rightarrow$ 정량적 검증 및 개선 계획)**이 정확히 포함되었는지 확인합니다.

### 2. 터미널 2번 독립 감사관(Auditor) 교차 검증 (`AUDITOR_GUIDE.md`, `step_by_step_prompts.md` - Step 4-B)
* 새 터미널(2번)을 열고 `codex`를 실행한 뒤, **`prompt_bank/step_by_step_prompts.md`의 `[Step 4-B: 01:30]` 프롬프트**를 입력합니다.
* 독립 감사관 에이전트가 **`AUDITOR_GUIDE.md`의 4대 기준**(① 요구사항 및 구현 좌표 Drift 적발, ② 파괴적 입력 Fuzzing 방어 패치, ③ 3종 골든 샘플 및 Fallback 동작 확인, ④ `HANDOFF.md` 3단 리스크 정밀화)에 따라 코드를 최종 패치하고, `SPEC.md`의 7단계 체크박스를 모두 `[x]`로 완료 처리합니다.

---

## 🚪 Step 6. 최종 관문(Gatekeeper) 통과 및 후속 서술형 완벽 대비 (제출 10분 전)

작업 시간(180분) 종료 **최소 10분 전**에는 새 기능 추가를 멈추고 최종 관문 스크립트 실행 및 후속 서술형 암기에 집중합니다.

### 1. 릴리스 게이트 및 최종 게이트키퍼 실행 (`engine/release_gate.py`, `engine/final_gatekeeper.py`)
* 터미널에서 임시 스캔 파일을 정리하고 마지막 로컬 커밋을 수행한 뒤, 두 개의 게이트키퍼 스크립트를 실행합니다.
  ```bash
  rm -f .fde_data_profile.md .fde_audit_report.md
  git add -A && git commit -m "chore: complete audit and prepare final release"
  python3 engine/release_gate.py
  python3 engine/final_gatekeeper.py
  ```
* **두 스크립트가 보장하는 무감점 체크리스트**:
  * **`release_gate.py`**: 루트 마크다운 문서 누락/빈 파일 여부, `.listen('localhost')` 바인딩 실수, API 키 하드코딩 여부를 즉시 검사합니다.
  * **`final_gatekeeper.py`**: ① Git 미커밋 파일 및 임시 파일 오염 여부, ② 시크릿 노출 여부, ③ `0.0.0.0` 바인딩 준수 여부, ④ 필수 문서(`SPEC.md`, `HANDOFF.md`, `SOLUTION_NOTES.md`, `AGENTS.md`) 존재 여부, ⑤ `deterministic_harness.mjs` 5대 시나리오 통과 여부, ⑥ 컨테이너 메모리(OOM 방어) 상태를 종합 판정합니다.
* 마지막으로 웹 IDE 에디터 상단의 모든 열린 탭을 확인하여 미저장(`●`)이나 외부 변경 충돌이 없는지 확인하고 **`Ctrl+S` (`Cmd+S`)**를 눌러 **"저장됨"** 상태를 확인합니다.

### 2. 후속 서술형(6문항 × 5분, 복붙 불가) 핵심 암기 (`docs_kit/defense_logic_guide.md`, `prompt_bank/typing_guide.md`)
* **"제출물 확정하고 문제풀기"**를 누른 순간부터는 파일을 수정할 수 없으며, 약 5~10분의 질문 준비 대기 시간을 거쳐 **총 6문항(문항당 5분, 14:00 일괄 종료)**의 후속 서술형이 시작됩니다.
* 후속 서술형에서는 **AI 사용, 외부 창, 복사·붙여넣기(`Ctrl+V`), 책상 위 종이 메모지 사용이 전면 금지**됩니다.
* 따라서 제출 확정 버튼을 누르기 직전, 터미널에 출력된 **`final_gatekeeper.py`의 핵심 암기 브리핑**과 **`docs_kit/defense_logic_guide.md`**, **`prompt_bank/typing_guide.md` (Part 2)**를 눈으로 읽고 아래 **3가지 핵심 키워드 세트**를 머릿속에 정확히 각인하고 제출 버튼을 누르세요!
  1. **핵심 구현 좌표 3세트**:
     * 결정론 코어(80%): `src/core/rules.js` 의 `evaluateCoreRules()`
     * AI 요약 및 무중단 안전장치(20%): `src/ai/reporter.js` 의 `generateInsightWithFallback()`
     * 데이터 정제 파서 및 3종 프리셋: `src/data/samples.js` 의 `sanitizeAndParseInput()` 및 `GOLDEN_SAMPLES`
  2. **실무자 DM 확인 예외 처리 1가지**: 결측치(`Null`/`-999`)/비정상 상태 플래그 분리 기준 및 경계값 등호(`>=` vs `>`) 판정 기준
  3. **기술적 한계점 및 개선 계획 (3단 논법)**:
     * *약점 지목*: 대용량 데이터 인입 시 단일 스레드 인메모리 동기 순회 병목 및 상태 휘발성
     * *파급 위험*: 동시 다량 요청 시 브라우저 메인 스레드 블로킹 및 API 트래픽 폭주 시 상세 추론 지연
     * *검증 및 개선*: 더미 부하 스크립트로 임계치 계측 후, 단기적으로 해시 캐싱·SQLite 영속화 적용, 장기적으로 스트리밍 파서·Web Worker·비동기 큐 도입
  4. **질문의 전제가 내 실제 구현과 다를 때 (`defense_logic_guide.md` 유형 3 & `typing_guide.md` 공식 4)**:
     * 당황하지 말고 *"문항에서는 A 방식을 전제하고 있으나, 본 구현에서는 제한 시간 내 핵심 요구사항(In-Scope)의 무결성과 오차 0% 판정을 보장하기 위해 `SPEC.md`의 합의에 따라 B 방식(`src/core/rules.js` 기반 결정론 코어)으로 구현했습니다"*라고 차이를 밝힌 뒤 본인의 설계 근거와 향후 확장성을 3~4문장으로 서술하세요!