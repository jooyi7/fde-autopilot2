# 🛠️ AGENTS.md — Codex Main/Sub-Agent Engineering & Orchestration Constitution

이 문서는 응시 환경 내장 **Codex CLI 에이전트(메인 에이전트)**와 **독립 검증 스크립트(서브 에이전트)**가 본 워크스페이스에서 문제를 분석, 설계, 구현, 검증할 때 반드시 준수해야 하는 최상위 엔지니어링 헌법이다.

---

## 1. 메인 에이전트 & 서브 에이전트 분리 구동 체계 (3-Terminal Architecture)
환각(Hallucination)과 컨텍스트 오염을 방지하기 위해 작업 환경을 물리적으로 분리된 3개의 터미널 역할로 나누어 구동한다.
- **메인 에이전트 (Terminal #1 - `codex` CLI 오케스트레이터)**:
  - 요구사항 해석, 5가지 아키텍처 대안 도출 및 비교(1개 선정 / 4개 기각 사유 수립), 책임 소재(Accountability) 설계, 애플리케이션 코드(`src/*`) 및 문서(`SPEC.md`, `HANDOFF.md`, `SOLUTION_NOTES.md`) 작성을 총괄한다.
  - 대용량 원본 데이터를 직접 읽지 않으며, 서브 에이전트가 생성한 프로파일 리포트(`.fde_data_profile.md`)와 검증 결과만을 입력 컨텍스트로 삼는다.
- **실시간 프리뷰 서버 (Terminal #2 - `0.0.0.0` Web Server)**:
  - 통합 웹 애플리케이션을 `0.0.0.0` 호스트로 상시 구동하여 내장 Browser 도구에서 UI/UX와 3종 골든 샘플 동작을 실시간으로 검증한다.
- **서브 에이전트 워커 (Terminal #3 - Deterministic Checkers & Git Logger)**:
  - LLM의 개입 없이 100% 고정된 파이썬/노드 스크립트로 동작하는 독립 검증 및 분석 에이전트다.
  - **데이터 프로파일러 서브 에이전트 (`engine/workspace_inspector.py`, `engine/workspace_profiler.py`)**: 데이터셋의 스키마, 결측치(`Null`/`-999`), 중복 키, 3-Sigma 임계치를 결정론적으로 계산하여 메인 에이전트에 전달한다.
  - **하네스 검증 서브 에이전트 (`engine/verify_core.mjs`, `engine/deterministic_harness.mjs`)**: 메인 에이전트가 작성한 코어 로직에 정상·경계·위반·Null·AI 장애 시뮬레이션을 주입해 `PASS/FAIL`을 판정한다.
  - **최종 감사 및 게이트키퍼 서브 에이전트 (`engine/release_gate.py`, `engine/final_gatekeeper.py`)**: 요구사항 누락(Drift), 보안 위배, 미커밋 상태를 점검하고 매 단계 완료 시 **로컬 `git commit`**을 기록한다.

---

## 2. 연산과 추론의 엄격한 분리 (80/20 Architecture & Accountability)
- **Deterministic Preprocessor & Core (80% - `src/data/samples.js`, `src/core/rules.js`)**:
  - **모든 데이터 전처리(결측치·이상치·중복 분리), 수치 연산(집계, 비율, 평균, 표준편차), 임계치 판정, 상태 전이 규칙은 외부 의존성이 없는 순수 함수(Pure Function)로 구현한다.** 어떠한 기형적인 데이터가 들어와도 크래시 없이 실행 가능해야 한다.
  - LLM 호출이나 비동기 네트워크 요청을 전처리 및 코어 판정 로직 내부에 절대 섞지 않는다.
- **Structured AI Adapter (20% - `src/ai/reporter.js`)**:
  - AI 모듈은 오직 결정론 코어가 산출한 구조화된 판정 객체(`{ status, score, metrics, anomalies, ruleId }`)만을 입력으로 받는다.
  - AI의 역할은 실무자용 **상황 요약, 복합 원인 가설 제시, 권장 조치 가이드(SOP) 초안 생성**으로만 제한한다.
- **판정 책임 소재(Accountability) 명확화**:
  - 1차 산술/규칙 판정의 무결성 책임은 결정론 코어가 지며(적용된 `ruleId`와 수치 근거를 화면에 투명하게 노출), AI 요약은 보조 참고 자료임을 명시하고, 최종 의사결정 및 예외 승인 권한은 감사 로그(Audit Trail)와 함께 현업 담당자에게 귀속시킨다.

---

## 3. 엔지니어링 3대 핵심 원칙 (Core Engineering Pillars)
1. **데이터 불변성 및 단일 진실 공급원 (Single Source of Truth)**:
   - 원본 데이터셋(`raw_data`)은 절대 직접 변형(Mutate)하지 않는다. 파서(`sanitizeAndParseInput`)를 거친 정제 데이터와 이상치(`INVALID`)를 분리 보관하여 감사 추적성(Auditability)을 보장한다.
   - `README.md`와 실무자 에이전트(DM) 답변이 상충할 경우, 실무자 에이전트가 지시한 최신 비즈니스 기준을 우선 반영하고 그 근거를 주석과 문서에 명시한다.
2. **장애 격리 및 무중단 폴백 (Zero-Crash Fallback)**:
   - AI API 타임아웃, 쿼터 초과, 파싱 에러가 발생하더라도 전체 서비스나 웹 화면이 멈추면 안 된다.
   - AI 호출 실패 시 `try-catch` 블록에서 즉시 결정론 코어의 수치 데이터와 사전 정의된 정적 템플릿을 결합한 **Standard Rule-Based Report**를 0.1초 내에 반환한다.
3. **현업 유지보수성 및 직관적 UX (Config-Driven & Low Cognitive Load)**:
   - 모든 판정 임계값은 파일 최상단의 `THRESHOLD_CONFIG` 상수로 분리하여 비개발자도 즉시 수정할 수 있게 한다.
   - 화면 최상단에 **3종 골든 샘플(정상/경고/위반) 원클릭 버튼**과 명확한 색상 상태 배지, KPI 요약 카드를 배치하여 실무자의 인지 부하를 최소화한다.

---

## 4. 응시 플랫폼 런타임 및 감독 규칙 준수 (엄격 적용)
- **허용 AI 모델 및 토큰 효율화**:
  - 플랫폼에서 제한한 모델(`Astra` 사용 금지)은 절대 호출하지 않으며, 권장 모델(`Sol 6.1`, `Terra 5.6`, `Luna 6`, `Sol 6.0`)만 사용한다.
  - 토큰 사용량이 추적 및 평가에 반영되므로, 원본 대용량 데이터를 프롬프트에 통째로 주입하지 않고 서브 에이전트의 요약 프로파일(`.fde_data_profile.md`)만 컨텍스트로 주입한다.
- **보안 및 외부 전송 금지 (로컬 Git Commit 필수)**:
  - 개인 API 키나 외부 비공개 엔드포인트를 절대 코드에 포함하지 않는다.
  - 외부 파일 전송 및 **`git push`는 절대 금지**한다. 단, 작업 과정 기록(Git 로그/diff 평가)을 위해 매 단계 완료 시 **로컬 `git add -A && git commit`**을 필수적으로 수행한다.
- **서버 바인딩 및 리소스 관리**:
  - 모든 웹 서버는 반드시 `0.0.0.0` 호스트에 바인딩해야 내장 Browser 도구에서 접근할 수 있다 (`localhost` 단독 바인딩 금지).