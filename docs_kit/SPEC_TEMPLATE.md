# 📋 SPEC.md — 요구사항 서면 합의서 및 구현 증거 좌표

> ⚠️ **문서명 안내:** 본 템플릿은 기본 기획서(`SPEC.md`)로 사용하되, 과제 `README.md`에서 별도의 제출 문서명(예: `SOLUTION_NOTES.md`, `PLAN.md` 등)을 요구할 경우 **과제 안내의 파일명을 최우선으로 준수**하여 저장한다.

## 1. 비즈니스 문제 정의 및 현장 병목(Bottleneck)
- **현상 및 에피소드**: 현업에서 대량의 입력 데이터(또는 요청)를 수작업 및 파편화된 기준으로 검토하느라 판정 리드타임이 길어지고 휴먼 에러(누락·오판)가 발생함.
- **현재 임시 대처(Workaround)의 한계**: 수동 필터링 및 사후 확인에 의존하여 실시간 이상 감지와 표준화된 인수인계가 불가능함.
- **단 하나의 핵심 해결 과제 (Delta)**: **결정론적 규칙 코어(80%)**를 통한 오차 없는 실시간 1차 판정·수치 계산과, **AI 에이전트(20%)** 기반 원인 해석·조치 가이드 생성을 결합한 End-to-End 워크플로우 구축.

## 2. 정량적 성공 기준 (Quantitative Success Metrics)
| 측정 지표 | 현재 수준 (As-Is) | 목표 수준 (To-Be) | 검증 방법 |
| :--- | :--- | :--- | :--- |
| **건당 판정 소요 시간** | 수동 검토 10~15분 | **1초 이내 즉시 판정** | 상단 3종 골든 샘플 원클릭 테스트 |
| **규칙/임계치 계산 정확도** | 휴먼 에러 발생 가능 | **결정론 코어 기반 오차 0%** | `deterministic_harness` 3종 케이스 검증 |
| **AI 장애 시 서비스 가용성** | API 장애 시 업무 중단 | **100% 무중단 (Fallback 즉시 응답)** | LLM 에러 시 결정론 안전장치 리포트 반환 |

## 3. 범위 합의 (In-Scope vs Out-of-Scope)
### ✅ In-Scope (이번 버전 필수 구현 및 증거 좌표)
1. **3종 골든 샘플(정상/경고/위반) 원클릭 프리셋 주입기**
   - `[구현 좌표: src/data/samples.js - GOLDEN_SAMPLES]`
2. **입력 데이터 파싱 및 결측치/비정상 값 방어 정제기**
   - `[구현 좌표: src/data/parser.js - sanitizeAndParseInput()]`
3. **결정론 코어(80%) 비즈니스 규칙 판정 및 핵심 지표 산출 엔진**
   - `[구현 좌표: src/core/rules.js - evaluateCoreRules()]`
4. **AI(20%) 해석 리포트 생성기 및 무중단 Fallback 안전장치**
   - `[구현 좌표: src/ai/reporter.js - generateInsightWithFallback()]`
5. **실시간 판정 대시보드, 시각화 뷰어 및 상태 표시 UI**
   - `[구현 좌표: src/components/Dashboard.jsx - MainWorkspaceView()]`

### 🚫 Out-of-Scope (제한 시간 내 완성도를 위해 제외한 부가 기능)
- 다중 조직 SSO 로그인 및 세분화된 RBAC 권한 관리 백엔드
- 외부 레거시 시스템/DB 직접 쓰기(Write-back) 연동
- 멀티 테넌트 과금 및 장기 아카이빙 배치 서버

## 4. 7단계 진행 상태 트래커 (FDE State Machine & 로컬 Git 체크포인트)
> ⚠️ **규칙 준수:** 응시 환경에서는 외부 전송(`git push`)이 엄격히 금지되며, 작업 이력 평가를 위해 **로컬 `git commit`과 `git diff` 로그**만 기록한다.
- [x] `[STATE-1: 발굴]` 문제 맥락 파악, 데이터셋 프로파일링 및 실무자 에이전트(DM) 요구사항 확인 (`git commit -m "chore: initial workspace profiling"`)
- [x] `[STATE-2: 서면합의]` `SPEC.md` 요구사항 범위 확정 및 `AGENTS.md` 통제 원칙 수립 (`git commit -m "docs: define spec and agent constitution"`)
- [x] `[STATE-3: 스캐폴딩]` 4대 레이어(`data`, `core`, `ai`, `components`) 분리 및 베이스 구축 (`git commit -m "feat: scaffold 4-layer architecture"`)
- [x] `[STATE-4: E2E v0]` `0.0.0.0` 포트 바인딩 및 내장 Browser 도구 내 End-to-End 동작 관통 (`git commit -m "feat: e2e v0 pipeline working"`)
- [x] `[STATE-5: 중간검증]` 결정론 코어 단위 검증 루프 통과 및 AI Fallback 파이프라인 결합 (`git commit -m "test: pass deterministic core verification"`)
- [x] `[STATE-6: 수용확인/핸드오프]` `SPEC.md` 증거 좌표 매핑 완료 및 `HANDOFF.md` 작성 (`git commit -m "docs: complete handoff and architecture notes"`)
- [x] `[STATE-7: 제출의식]` 독립 감사관(Auditor) 교차 검증 및 파괴적 입력 방어 패치 완료 (`git commit -m "fix: apply edge-case guards and pass release gate"`)
