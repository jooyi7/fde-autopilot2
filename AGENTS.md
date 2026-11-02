# 🛠️ AGENTS.md — Codex Engineering & Orchestration Constitution

이 문서는 응시 환경 내장 **Codex CLI 에이전트**가 본 워크스페이스에서 코드를 설계, 구현, 검증할 때 반드시 준수해야 하는 최상위 엔지니어링 규칙이다.

## 1. 연산과 추론의 엄격한 분리 (80/20 Architecture)
- **Deterministic Core (80% - `src/core/evaluator.js` 또는 `engine.py`):**
  - 모든 수치 연산(집계, 비율, 평균, 표준편차, 증감률), 임계치 판정, 정규식 파싱, 상태 전이(State Transition) 규칙은 **외부 의존성이 없는 순수 함수(Pure Function)**로 구현한다.
  - LLM 호출이나 비동기 네트워크 요청을 코어 판정 로직 내부에 절대 섞지 않는다.
- **Structured AI Adapter (20% - `src/ai/advisor.js`):**
  - AI 모듈은 오직 결정론 코어가 산출한 구조화된 판정 객체(`{ verdict, metrics, anomalies, ruleId }`)만을 입력으로 받는다.
  - AI의 역할은 실무자용 **상황 요약, 복합 원인 가설 제시, 권장 조치 가이드 초안 생성**으로만 제한한다.

## 2. 엔지니어링 3대 핵심 원칙 (Core Engineering Pillars)
1. **데이터 불변성 및 단일 진실 공급원 (Single Source of Truth):**
   - 원본 로그/데이터셋(`raw_data`)은 절대 직접 변형(Mutate)하지 않는다. 파서(`parser`)를 거친 정규화 데이터와 원본 데이터를 분리 보관하여 감사 추적성(Auditability)을 보장한다.
   - `README.md`와 실무자 에이전트(DM) 답변이 상충할 경우, 실무자 에이전트가 명확히 지시한 최신 비즈니스 기준을 우선 반영하고 그 근거를 주석과 문서에 명시한다.
2. **장애 격리 및 무중단 폴백 (Zero-Crash Fallback):**
   - AI API 타임아웃, 쿼터 초과, 파싱 에러가 발생하더라도 전체 서비스나 웹 화면이 멈추면 안 된다.
   - AI 호출 실패 시 `try-catch` 블록에서 즉시 결정론 코어의 수치 데이터와 사전 정의된 정적 템플릿을 결합한 **Standard Rule-Based Report**를 반환한다.
3. **현업 유지보수성 (Config-Driven Thresholds):**
   - 모든 판정 임계값(예: 통계 계수, 알람 트리거 조건, 허용 오차)은 코드 본문에 매직 넘버로 하드코딩하지 않고, 파일 최상단의 `THRESHOLD_CONFIG` 상수로 분리하여 비개발자도 즉시 수정할 수 있게 한다.

## 3. 응시 플랫폼 런타임 및 감독 규칙 준수 (엄격 적용)
- **허용 AI 모델 및 토큰 효율화:**
  - 플랫폼에서 제한한 모델(`Astra` 사용 금지)은 절대 호출하지 않으며, 권장 모델(`Sol 6.1`, `Terra 5.6`, `Luna 6`, `Sol 6.0`)만 사용한다 (`/status` 및 `/model`로 사전 확인).
  - 토큰 사용량이 추적 및 평가에 반영되므로, 불필요하게 전체 데이터셋이나 거대 로그를 프롬프트에 통째로 주입하지 않고 요약 프로파일(`.autopilot/workspace_profile.md`)만 컨텍스트로 주입한다.
- **보안 및 외부 전송 금지:**
  - 개인 API 키나 외부 비공개 엔드포인트를 절대 코드에 포함하지 않으며, 응시 환경에 제공된 내장 인터페이스만 사용한다.
  - 외부 파일 전송 및 **`git push`는 절대 금지**한다. 단, 작업 과정 기록(Git 로그/diff 평가)을 위해 단계별 로컬 **`git add` 및 `git commit`**은 필수적으로 수행한다.
- **서버 바인딩 및 리소스 관리:**
  - 모든 웹 서버(Express, FastAPI, Vite, Next 등)는 반드시 `0.0.0.0` 호스트에 바인딩해야 플랫폼 내장 Browser 도구에서 접근할 수 있다 (`localhost` 단독 바인딩 금지).
  - 과도한 프로세스 생성으로 인한 OOM(메모리 초과)은 구제 대상이 아니므로, 불필요한 백그라운드 워커나 무한 루프를 생성하지 않는다.

## 4. 작업 수행 루프 (Codex Execution Loop)
1. 코드를 작성하기 전 `python3 engine/workspace_inspector.py` 및 `workspace_profiler.py` 실행 결과를 먼저 확인한다.
2. 코어 로직(`src/core/*`)을 먼저 작성하고 `node engine/verify_core.mjs`로 엣지 케이스를 통과시킨 후 로컬 `git commit`을 수행한다.
3. UI 및 서버를 연결한 뒤 전용 터미널에서 `0.0.0.0`으로 구동하고 내장 Browser에서 실제 포트로 동작을 확인한다 (`git commit`).
4. 제출 전 에디터의 미저장/충돌 상태를 모두 해소하고, `python3 engine/release_gate.py`를 실행하여 누락된 필수 파일이 없는지 최종 검증한다.
