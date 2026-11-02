# 🚀 FDE-Autopilot 실전 사용자 가이드 (Step-by-Step)

이 가이드는 응시 환경(Cofa 웹 IDE)에서 어떤 도메인의 과제가 주어지더라도 처음부터 끝까지 막힘없이 프로젝트를 분석, 설계, 개발, 검증 및 최종 제출할 수 있도록 돕는 **통합 실행 매뉴얼**입니다.

작업 중 터미널 명령어가 헷갈릴 때는 언제든 **`PLAYBOOK_CLI.md`** 파일을 열어 복사해서 사용할 수 있는 명령어 모음집(Cheat Sheet)으로 활용하세요.

---

## ⚠️ 0. 시험 환경 필수 수칙 (가이드라인 완벽 준수)
1. **Codex 실행 및 모델 설정**: 터미널에 `codex`를 입력해 실행한 뒤, `/status`로 권한을 확인하고 `/model`에서 **권장 모델(`Sol 6.1`, `Terra 5.6`, `Luna 6`, `Sol 6.0`)**을 선택합니다 (`Astra` 사용 절대 금지, 개인 API 키 사용 금지).
2. **외부 전송(`git push`) 금지 및 로컬 커밋 필수**: 외부로의 파일 전송이나 `git push`는 엄격히 금지됩니다. 반면 **로컬 `git 로그·diff`와 테스트 실행 결과는 평가에 직접 반영**되므로, 매 단계가 끝날 때마다 로컬 `git commit`을 남기세요.
3. **토큰 사용량 최적화**: 토큰 사용량이 추적되므로 Codex에게 질문할 때 원본 대용량 CSV/JSON을 통째로 읽히지 말고, 자동 생성된 요약 리포트(`.autopilot/workspace_profile.md`)만 전달하세요.
4. **에디터 저장 충돌 방지**: 터미널의 Codex가 파일을 수정했을 때 에디터에서 충돌이 뜨면 **"외부 변경 불러오기"**를 선택해 AI가 작성한 최신 코드를 유지하고, 제출 전 모든 탭이 **"저장됨"** 상태인지 확인하세요.

---

## 🏁 Step 1. 작업 환경 준비 및 데이터 자동 분석 (초기 15분)

가장 먼저 내 작업 폴더에 어떤 파일과 데이터가 들어있는지 스크립트를 통해 자동으로 파악합니다.

### 1. 과제 안내서 확인 (`README.md`)
* 루트의 과제 `README.md`를 열어 **과제 목표, 필수 구현 조건, 필수 제출 문서 파일명**을 가장 먼저 확인합니다.

### 2. 원클릭 초기 진단 실행 (`bootstrap.sh`)
* 터미널을 열고 아래 명령어를 입력합니다.
  ```bash
  bash bootstrap.sh --workspace .
  ```
* **이 명령어가 하는 일**: 내부적으로 두 개의 파이썬 분석 스크립트를 실행하여 `.autopilot/` 폴더 안에 분석 결과 보고서를 만들어 줍니다.
  * **`engine/workspace_inspector.py`**: 현재 폴더 안의 파일 목록, 문서, 데이터 파일(CSV, JSON, SQLite 등)의 위치와 용량을 스캔합니다.
  * **`engine/workspace_profiler.py`**: 발견된 데이터 파일의 컬럼명, 결측치(비어있는 값), 통계적 임계치(3-Sigma), 그리고 실무자 에이전트에게 물어봐야 할 질문 후보를 `.autopilot/workspace_profile.md` 파일로 요약해 줍니다.

### 3. 베이스라인 Git 커밋 기록
* 초기 분석이 끝났다면 첫 번째 로컬 커밋을 남깁니다.
  ```bash
  git add -A && git commit -m "chore: initial workspace scan and data profile"
  ```

---

## 🎯 Step 2. 문제 아키타입(A~D) 결정 및 실무자 DM 질문 확정

데이터와 요구사항을 확인했다면, 우리가 만들 프로그램이 어떤 문제 유형인지 정하고 우측 메신저(DM)의 **업무 담당자(실무자 에이전트)**에게 핵심 질문을 던집니다. (사용법 문의는 `Cofa Helper`, 업무 맥락 문의는 `업무 담당자`에게 구분하여 질문합니다.)

### 1. 범용 문제 아키타입(Type A~D) 판별하기 (`prompt_bank/typing_guide.md`)
* 특정 산업 도메인에 얽매이지 않고, 오늘 해결해야 할 과제가 아래 **4대 소프트웨어 아키타입 중 어디에 속하는지** 결정합니다.
  * **Archetype A (지표 모니터링 및 이상 탐지 대시보드)**: 시계열/수치 데이터를 차트와 요약 카드로 보여주고, 임계치 기반 이상 징후를 색상과 표로 필터링하는 시스템.
  * **Archetype B (규칙 검증 및 차분/Diff 알람 도구)**: 입력된 설정값, 로그, 데이터가 비즈니스 규칙에 맞는지 검사하고, 이전 버전/기준값과 무엇이 달라졌는지 비교(Diff)해 알람을 띄우는 도구.
  * **Archetype C (문서 검색 및 출처/Citation 기반 질의응답)**: 규정, 매뉴얼, 가이드 문서를 검색하고, 답변을 제시할 때 반드시 원본 문서의 근거 조항(Citation)을 함께 표시하며 문서 외 질문은 거절하는 도구.
  * **Archetype D (상태 머신 및 승인 백오피스 워크플로우)**: 요청 $\rightarrow$ 검토 $\rightarrow$ 승인/반려처럼 단계별로 상태(State)가 전이되고, 권한별 액션 제어 및 처리 이력(Audit Log)을 남기는 시스템.

### 2. 실무자 에이전트(업무 담당자 DM)에게 요구사항 질문하기 (`docs_kit/stakeholder_inquiry.md`)
* `.autopilot/workspace_profile.md`에 도출된 질문 트리거와 `stakeholder_inquiry.md`의 범용 템플릿을 결합하여 우측 DM의 **업무 담당자**에게 2~3개의 핵심 질문(결측치 처리 기준, 경계값 등호 포함 여부, 필수 출력 항목)을 압축해 전송합니다 (`Enter` 전송, `Shift+Enter` 줄바꿈).
* **중요 (상충 해결 원칙)**: 만약 `README.md`의 설명이 모호하거나 실무자 에이전트의 답변과 상충할 경우, 실무자 에이전트의 답변을 최종 기준(Ground Truth)으로 반영하고 제출 문서에 *"업무 담당자와의 DM 협의를 통해 ~기준으로 확정함"*이라고 명확히 인용합니다.

### 3. 기획서 및 계획 문서 작성 (`config.toml`, `docs_kit/SPEC_TEMPLATE.md`)
* **`config.toml`**: 선택한 아키타입(`A`, `B`, `C`, `D`)을 설정합니다.
* **`SPEC.md` (또는 과제에서 지정한 계획 문서명)**: `docs_kit/SPEC_TEMPLATE.md`를 기반으로 핵심 기능과 예외 처리 규칙을 작성한 뒤 로컬 커밋을 남깁니다.
  ```bash
  git add -A && git commit -m "docs: complete requirement spec and stakeholder inquiry rules"
  ```

---

## 🏗️ Step 3. 앱 뼈대 자동 생성 및 Codex 단계별 코딩

직접 초기 코드를 다 짤 필요 없이, 스크립트로 앱 뼈대를 만들고 내장 **Codex CLI**에게 단계별로 작업을 위임합니다.

### 1. 앱 뼈대(Scaffold) 자동 생성 (`engine/scaffold_app.sh`)
* 터미널에 아래 명령어를 입력합니다.
  ```bash
  bash engine/scaffold_app.sh --target ./app --type A --stack nextjs
  ```
  * `--type`: `A`, `B`, `C`, `D` 중 선택
  * `--stack`: `nextjs`, `fastapi`, `vanilla` 중 과제 환경에 맞는 스택 선택

### 2. 내장 Codex CLI에게 기본 헌법 주입하기 (`AGENTS.md`)
* 터미널에서 실행 중인 **Codex** 입력창에 `AGENTS.md`의 핵심 원칙과 `.autopilot/workspace_profile.md` 요약본을 읽도록 지시합니다.
* **주의**: 우측 상단 CPU/RAM 사용량을 수시로 확인하며, Codex가 승인 대기(사용자 선택 대기) 상태인지 실행 중인지 구분하여 진행합니다.

### 3. 단계별 프롬프트로 코딩 위임 및 단계별 Git Commit (`prompt_bank/step_by_step_prompts.md`)
* 한 번에 모든 것을 시키지 말고 아래 순서대로 Codex에게 지시하며, **각 단계가 끝날 때마다 테스트 및 `git commit`**을 수행합니다.
  1. **Prompt 1 & 2 (문제 요약 및 SPEC 확정)**: 데이터 프로파일 결과를 바탕으로 `SPEC.md`를 채우게 합니다.
  2. **Prompt 3 (Core 결정론 로직 구현)**: 데이터를 읽고 계산/검증하는 `src/core` 순수 함수들을 먼저 짜게 합니다 $\rightarrow$ 검증 후 `git commit -m "feat: implement deterministic core logic"`
  3. **Prompt 4 (UI 및 End-to-End 연결)**: 사용자가 보는 화면과 3종 골든 샘플(정상/경고/위반) 버튼을 만들고 핵심 로직과 연결하게 합니다 $\rightarrow$ `git commit -m "feat: connect UI and golden samples"`
  4. **Prompt 5 (예외 방어 및 AI Fallback)**: 빈 데이터, 결측치, AI 타임아웃 발생 시에도 프로그램이 멈추지 않도록 방어 코드를 넣게 합니다 $\rightarrow$ `git commit -m "fix: add edge-case defenses and AI fallback"`

---

## 🔍 Step 4. 중간 점검, 내장 Browser 확인 및 무결성 검증

코드를 작성할 때마다 테스트 스크립트와 플랫폼 내장 **Browser 도구**를 통해 실제 동작을 검증합니다.

### 1. 핵심 로직 테스트 (`engine/verify_core.mjs`, `engine/deterministic_harness.mjs`)
* 터미널에서 핵심 로직이 정상 작동하고 항상 동일한 결정론적 결과를 내는지 검사합니다.
  ```bash
  node engine/verify_core.mjs ./app/src/core.mjs
  node engine/deterministic_harness.mjs --module ./app/src/core.mjs --input ./sample_input.json --expected ./expected_output.json
  ```

### 2. 내장 Browser 미리보기 검증 (필수)
* **전용 터미널 분할/탭 생성**: `+` 버튼으로 새 터미널을 열고 서버를 실행합니다. 이때 서버는 반드시 **`0.0.0.0`**에 바인딩해야 합니다 (`localhost` 단독 바인딩 시 Browser 미리보기 연결 불가).
* **PORT 및 URL 연결**: 내장 Browser 도구의 `PORT` 입력란에 터미널에 출력된 실제 포트 번호(예: `3000`, `5173`, `8000` 등)를 입력하고 새로고침(원형 화살표)을 누릅니다.
* **기능 직접 클릭**: 화면이 뜨면 3종 골든 샘플 버튼, 필터, 입력창을 직접 클릭해 동작을 확인합니다. 확인하는 동안 **서버가 실행 중인 터미널 탭은 절대 닫지 마세요.**

### 3. 독립 품질 감사관(Auditor) 점검 (`engine/auditor_worker.sh`, `AUDITOR_GUIDE.md`)
* 새 터미널에서 아래 명령어를 실행하여 요구사항 누락이나 런타임 에러 위험 지점을 점검합니다.
  ```bash
  bash engine/auditor_worker.sh --workspace . --app ./app
  ```

---

## 📝 Step 5. 최종 제출 문서 완성 (`SPEC.md`, `HANDOFF.md`, `ARCHITECTURE_DECISIONS.md`)

제출 문서는 Codex와 대화하여 작성할 수 있으며 AI 활용으로 인한 불이익이 없습니다. 단, **과제 `README.md`에서 요구한 필수 파일명**이 있다면 반드시 그 파일명으로 맞추어 저장하세요.

1. **`ARCHITECTURE_DECISIONS.md`**: 선택한 아키텍처 판단과 근거(실무자 DM 협의 내용 포함), 검증 결과, 남은 한계점을 명시합니다.
2. **`HANDOFF.md` (`docs_kit/HANDOFF_TEMPLATE.md`)**: 설치 및 실행 방법, 파이프라인 구조, 3단계 리스크 분석을 구체적인 파일명/함수명과 함께 기록합니다.

---

## 🚪 Step 6. 최종 관문(Gatekeeper) 통과, 제출 및 후속 서술형 대비 (종료 10분 전)

작업 시간(180분) 종료 **최소 10분 전**에는 코드 수정을 멈추고 최종 검증 및 제출 절차를 시작합니다.

### 1. 최종 게이트키퍼 실행 및 마지막 Git Commit (`engine/final_gatekeeper.sh`)
* 터미널에서 아래 명령어를 실행하여 필수 문서와 코드 상태를 종합 점검합니다.
  ```bash
  bash engine/final_gatekeeper.sh --workspace . --app ./app
  git add -A && git commit -m "chore: pass final gatekeeper before submission"
  ```
* 에디터 상단 탭을 모두 확인하여 저장되지 않은 변경(`●`)이나 충돌 표시가 없는지 확인하고 `Ctrl+S` (`Cmd+S`)로 완전히 저장합니다.

### 2. 후속 서술형(6문항 / 문항당 5분) 대비 핵심 키워드 암기 (`docs_kit/defense_logic_guide.md`)
* **"제출물 확정하고 문제풀기"**를 누른 순간부터는 파일을 수정할 수 없으며, 이어지는 후속 서술형에서는 **AI 사용 및 복사·붙여넣기가 전면 금지**됩니다 (직접 타이핑 필수).
* 따라서 제출 확정 버튼을 누르기 직전, 아래 3가지를 반드시 눈으로 읽고 기억하세요 (`defense_logic_guide.md` 참고):
  1. 내가 구현한 **핵심 코어 파일명 2개와 주요 함수명 2개**
  2. 실무자 에이전트(DM)와 협의하여 처리한 **결측치/예외 처리 기준 1개**
  3. 현재 구현의 **기술적 한계점과 향후 개선 방향 1개**
* 만약 후속 서술형 문항의 전제가 내 실제 구현과 다르다면, 당황하지 말고 **"질문의 전제와 실제 구현의 차이를 밝히고 본인이 선택한 구현 방식과 이유"**를 3~4문장으로 명확히 타이핑하여 제출하세요!