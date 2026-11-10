# 🚀 FDE-Autopilot v6.1 실전 사용자 가이드 (3-Terminal & 코어 룰 집중 개발 매뉴얼)

이 가이드는 응시 환경에서 **Main Agent(Codex CLI 오케스트레이터)**와 **Sub Agent(결정론적 분석·검증 워커)**, 그리고 **0.0.0.0 웹 서버**를 분리 구동하여, 해커톤의 가장 본질인 **"내부 결정론 코어 룰(rules.js & solver) 정밀 코딩"**에 집중하고 6시간 만에 만점으로 완주하도록 설계된 실전 매뉴얼입니다.

---

## 🖥️ 1. 3-터미널 아키텍처 및 Main / Sub Agent 역할 분리

작업 시작 직후 터미널 창의 `+`(또는 분할) 버튼을 눌러 **3개의 터미널**을 띄우고 아래와 같이 역할을 엄격히 분리합니다.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🏛️ [Terminal #1] Main Agent (Codex CLI 조종석)                                │
│  • 주체: 메인 에이전트 (Codex CLI)                                           │
│  • 역할: 요구사항 해석, 코어 로직 설계, 5대 대안 비교표, 3대 문서 작성 총괄     │
│  • 원칙: 대용량 원본 데이터를 직접 읽지 않음 (토큰 고갈/환각 방지)                   │
│          Terminal #3 서브 에이전트가 생성한 요약 프로파일 리포트만 컨텍스트로 주입 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🌐 [Terminal #2] Real-time Web Server (0.0.0.0 상시 구동)                   │
│  • 역할: `npm run dev`로 0.0.0.0:5173 웹 서버를 띄워두고 대회 끝까지 절대 끄지 않음│
│  • 기능: 브라우저 도구에서 UI/UX, 3종 골든 샘플, What-If 슬라이더 실시간 프리뷰      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🧪 [Terminal #3] Sub Agent Worker (결정론적 분석·솔버·검증 & Git Logger)       │
│  • 주체: 서브 에이전트 워커 (100% 순수 Python/Node 스크립트 실행 전용 창)           │
│  • 수행: 데이터 프로파일링, 평가지표 진단, TDD 하네스 즉시 검증(3초), Git 커밋       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⏱️ 2. 실전 해커톤 6시간 현실 타임라인

> 💡 **시간 배분의 진실**: 하네스 검증 명령어 자체는 **단 3초** 만에 끝납니다. 6시간 중 가장 많은 시간(2시간)을 쏟아야 하는 진짜 본체는 **"내부 코어 규칙(`src/core/rules.js` & `engine/solver_*.py`)을 문제 요구사항에 맞게 정밀 코딩하는 것"**입니다.

| 구간 | 단계 | 소요 시간 | 주체 | 실전 핵심 과업 |
| :---: | :---: | :---: | :---: | :--- |
| **00:00 ~ 00:20** | **Step 1** | 20분 | Sub Agent (T#3) | `python bootstrap.py`로 데이터/결측치/병목 자동 분석 (5초) ➔ **1차 Git 커밋** |
| **00:20 ~ 01:00** | **Step 2** | 40분 | Main Agent (T#1) | 페르소나 DM 질의로 스펙/제약 확정 ➔ `SPEC.md` 작성 ➔ **2차 Git 커밋** |
| **01:00 ~ 03:00** | **Step 3** | **120분<br>(최대 투자)** | **개발자 &<br>Main Agent** | 🔥 **[가장 중요한 본체] 내부 코어 룰(`rules.js` & `solver`) 정밀 코딩**<br>• 문제 수식, 제약조건, 최적화 알고리즘 구현<br>• 코드 짤 때마다 **하네스(`deterministic_harness.mjs`, 3초)**로 즉시 검증하며 TDD 완성! ➔ **3차 Git 커밋** |
| **03:00 ~ 04:00** | **Step 4** | 60분 | Web Server (T#2) | `python engine/scaffold_app.py` ➔ `npm run dev` (0.0.0.0:5173)<br>• 화면 골든 샘플(정상/경고/위반), What-If 슬라이더, AI Fallback 검증 ➔ **4차 Git 커밋** |
| **04:00 ~ 05:30** | **Step 5** | 90분 | Main Agent (T#1) | 3대 필수 문서 완성 (`SPEC.md`, `SOLUTION_NOTES.md` 5대 대안 비교표, `HANDOFF.md`) ➔ **5차 Git 커밋** |
| **05:30 ~ 06:00** | **Step 6** | 30분 | Sub Agent (T#3) | `python engine/final_gatekeeper.py` 6대 관문 통과 ➔ **최종 안전 제출!** |

---

## 🏃 3. 단계별 실전 실행 가이드

### 🚀 Step 1. [Terminal #3 서브 에이전트] 데이터/문제 원클릭 자동 분석 (00:00 ~ 00:20)
* **어디서?**: **Terminal #3 (서브 에이전트 워커 창)**
* **입력할 명령어**:
  ```bash
  python bootstrap.py --workspace .
  # (Linux/Mac 환경일 경우: bash bootstrap.sh --workspace .)
  ```

* **서브 에이전트가 5초 만에 생성하는 산출물**:
  1. `WORKSPACE_PROFILE.md`: `README.md` 요약 및 프로젝트 구조.
  2. `.fde_data_profile.md`: 결측치(`Null`), 센티널(`-999`), 3-Sigma 임계치 통계.
  3. `.autopilot/pre_opt_diagnosis.md`: 목표(정확도 vs 속도) 및 병목(알고리즘 vs HW) 사전 진단.
  4. `.fde_optimization_proposal.md`: 최적화 기법 추천 후보 순위표.
  5. `output/result.json`: 도메인 자동 판별 및 기준 솔버 결과.

* **Terminal #3에서 1차 로컬 Git 커밋**:
  ```bash
  git add -A
  git commit -m "feat: complete workspace profiling and generate baseline result"
  ```

---

### 💬 Step 2. [Terminal #1 메인 에이전트] 페르소나 질의 & 기준 확정 (00:20 ~ 01:00)

#### 2-1. 우측 웹 메신저에서 페르소나 질의 (고단수 심층 질의)
* **어디에 입력?**: 플랫폼 우측 **DM 메신저 (업무 담당자 챗봇)**
* **질의 팁**: 챗봇은 일반적인 질문에는 뻔한 답만 하므로, 아래처럼 **암묵적 룰, 등호 기준, 결측치, 도메인 저격 질문**을 뾰족하게 던져 핵심 채점 기준을 캐내야 합니다.

* **[1차 DM 전송: 현장 병목 · 숨겨진 수작업 보정식 · 최다 민원 파악]**:
  ```text
  안녕하세요 담당자님! 현업에 실질적으로 도움이 되는 무결점 의사결정 시스템을 구축하기 위해 여쭙습니다.
  1) [현장 병목 및 기존 임시 대처]: 현재 이 업무에서 가장 시간이 오래 걸리거나 휴먼 에러가 빈번한 최대 병목 구간은 어디이며, 지금까지는 이를 엑셀 수동 대조나 현장 직관 등 어떤 임시 방식(Workaround)으로 처리해 오셨나요?
  2) [문서 외 암묵적 수작업 룰]: 과제 안내서에는 명시되지 않았으나, 현업 실무자분들이 당연하게 적용하고 계신 '암묵적 예외 규칙', '수율/원가 환산 계수', 또는 '경험적 안전 마진'이 있다면 알려주실 수 있나요?
  3) [최다 민원 및 1순위 범위]: 기존 결과물에 대해 현업이나 유관 부서로부터 가장 빈번하게 접수된 불만/민원 사항은 무엇이며, 이번 1차 배포에서 민원 재발을 막기 위해 '반드시 100% 완벽히 동작해야 하는 1순위 핵심 기능'과 과감히 제외(Out-of-Scope)해도 되는 부가 기능의 경계를 확정해 주시면 집중하여 구현하겠습니다!
  ```

* **[2차 DM 전송: 데이터 전처리 · 센티널(-999) · 도메인 저격 · 판정 책임 소재]**:
  > 1차 답변 수신 후, 아래 **[도메인별 1줄 저격 질문]** 중 1개를 골라 2번 항목에 넣어 전송합니다.
  ```text
  상세하고 실질적인 답변 감사드립니다! 공유해주신 내용을 바탕으로 데이터를 코드로 정밀 분석해보니 결측치, 센티널(-999), 중복 키 및 경계 조건이 확인되어 정확한 로직 구현을 위해 확인 부탁드립니다.

  1) [결측치/센티널 처리]: 데이터 내 결측치(Null, 빈 문자열)나 센티널 이상치(-999), 비정상 상태 플래그(CANCELLED, INVALID)는 전체 집계 분모에서 완전히 제외(Drop)할까요, 아니면 별도의 '이상치/격리' 배지로 분류해 화면에 보존할까요? 또한 동일 ID 중복 유입 시 최신 타임스탬프 1건만 유효 레코드로 인정하면 될까요?
  2) [도메인 핵심 특화 기준]: (★ 아래 도메인별 저격 질문 중 이번 과제에 해당하는 1줄을 복사해 여기에 붙여넣으세요!)
  3) [임계치 등호 및 우선순위]: 정상(NORMAL) / 경고(WARNING) / 위반(VIOLATION)을 가르는 임계치 숫자와 실측값이 소수점까지 일치할 때, 안전 우선 원칙에 따라 이상(>=)과 초과(>) 중 어느 기준으로 판정해야 하며, 여러 규칙이 동시 위반될 때 최우선 표기할 심각도(Severity) 기준은 무엇인가요?
  4) [판정 책임 소재 및 감사 로그]: 시스템의 오판 리스크를 방지하기 위해 1차 수치/규칙 판정(80%)은 결정론 코어로 고정하되, 현업 담당자가 최종 예외 승인(Override)할 때 화면과 감사 로그(Audit Trail)에 반드시 기록해야 할 필수 항목(규칙 ID, 근거 수치, 권장 SOP, 승인자 서명 등)을 가이드 부탁드립니다!
  ```

* **🎯 [도메인별 1줄 저격 질문 모음] (2차 DM의 2번에 1줄만 쏙 복사해서 붙여넣기)**:
  - **포토 (Overlay)**: `"Overlay M3S 스펙(2.0nm) 등호 포함(>=) 여부와, 3차 고차 왜곡(HOWA) 보정 시 전공정(Etch) 박막 스트레스 Feed-forward 항을 결합할지, 그리고 계측 병목 해소를 위한 최소 스마트 샘플링 비율(35%) 및 Chuck 간 편차(0.35nm) 원인 귀속 임계치를 확정하고 싶습니다."`
  - **소재 (CoA)**: `"성적서 In-Spec 불량을 막기 위해 최소 Cpk(1.33) 외에 스펙트럼 지문 코사인 유사도(0.985)와 Baseline 이동(Welch t-test p<0.01) 기준을 적용할지, 그리고 HVM 배관 체류시간 초과 또는 하위 2·3차 원료사(Sub-tier)의 무단 4M 변경 적발 시 조건부 Pilot 없이 즉시 Reject 및 Lot 홀드 조치를 내리면 될까요?"`
  - **시장 (Market)**: `"마이크론(8월 결산 FQ)과 당사/경쟁사(12월 결산 CQ) 비교 시 Calendarization 환율 기준과, 재고자산평가손실 환입(NRV Reversal)을 제거한 Underlying OPM 산출 기준, 그리고 전사 ASP 상승 속 범용 단가가 하락하는 'Mix 착시' 및 어닝콜 낙관 발언 대비 재고일수(DIO +7일) 급증 시 경보 등급 기준을 확정하고 싶습니다."`
  - **경영 (Value Chain)**: `"전방 CSP 수요 변동 시 내부 Fab 양품 다이(KGHD) 생산량과 외부 TSMC CoWoS 패키징 할당량 중 어느 쪽을 절대 출하 상한선(Ceiling)으로 적용해야 하며, HBM/DDR5/eSSD CAPEX 배분 시 공정 전환 손실(Conversion Loss)과 고객사 LTA 의무 물량을 최우선 Hard Constraint로 둘지, 최소 WACC 허들 레이트는 얼마인가요?"`
  - **교육 (Curriculum)**: `"커리큘럼 편성 시 선수과목 순환 참조(Cycle) 발견 시 즉시 VIOLATION 차단 여부와, 가용 학습시간 초과 시 핵심 목표 과목 50% 압축 보존 기준, 그리고 교육생 오개념 방지를 위해 [1단계 직관적 비유 + 2단계 공학적 팩트 가드레일] 2-Layer 설명과 [물리한계➔공정돌파➔수율➔재무] 4단계 브릿지를 필수로 적용할까요?"`
  - **범용 / 미출제 신규 난제 (Universal)**: `"예산/정원 상한과 필수 과업(Mandatory) 또는 보안/금지 구역(Forbidden)이 충돌할 때 어느 쪽을 절대 기준(Hard Constraint)으로 우선 적용해야 하며, 시간창(Time-Window) 비충돌 스케줄링 및 로컬 규정 문서 근거 조항 ID(BM25 Citation) 중 리포트 최상단에 노출할 1순위 KPI는 무엇인가요?"`

#### 2-2. `SPEC.md` 및 `SOLUTION_NOTES.md` 생성
* **참조할 파일**: `prompt_bank/step_by_step_prompts.md` 의 `[Step 1: 00:08]` 섹션
* **실행 위치**: **`[Terminal #1]` (Codex CLI)**
* **Codex에 붙여넣을 프롬프트**:
  ```text
  AGENTS.md를 읽고 핵심 원칙(80/20 분리, 3-터미널 역할)을 숙지해 줘.
  아직 src/ 코드는 작성하지 마. 토큰 절약을 위해 원본 데이터 파일을 직접 cat으로 읽지 말고, 서브 에이전트가 만든 .fde_data_profile.md 요약본과 README.md, 그리고 방금 내가 담당자 DM으로 확인한 아래 답변 내용을 결합하여 루트에 SPEC.md와 SOLUTION_NOTES.md를 작성해 줘.

  [담당자 DM 확인 내용]:
  (여기에 방금 메신저로 받은 담당자의 답변 내용을 그대로 붙여넣으세요)

  1. SOLUTION_NOTES.md (5대 아키텍처 대안 비교 및 책임 소재 설계):
     - 문제 해결 대안 5가지의 비교표 작성 및 1개 채택 / 4개 기각 사유 서술.
     - 1차 수치 판정 무결성 책임(결정론 코어 80%), AI 보조 요약(20%), 최종 승인 권한(현업) 명시.

  2. SPEC.md (요구사항 서면 합의서 및 9단계 순차 구현 실행서):
     - 문제 정의 및 기존 수작업 한계, 최다 민원 해결 목표.
     - 실무자 DM 확인 불변 규칙 (결측치 -999 전처리 기준, 중복 제거, 등호 기준).
     - 매핑된 레퍼런스 솔버(engine/solver_*.py)의 수리 알고리즘 이식 계획.
     - 1단계부터 9단계까지 순차적 구현 로드맵 (Step 1~2: 파서/골든샘플 ➔ Step 3~4: 코어 수치/임계치 판정 ➔ Step 5: 솔버/결과JSON ➔ Step 6: AI Fallback ➔ Step 7~8: 대시보드 UI/What-If ➔ Step 9: 게이트키퍼)과 예정 [구현 좌표: 파일명 - 함수명()] vs Out-of-Scope 범위.
  ```

* **Terminal #3에서 2차 로컬 Git 커밋**:
  ```bash
  git add -A
  git commit -m "docs: finalize stakeholder requirements and update SPEC.md"
  ```

---

### 🔥 Step 3. [Terminal #1 & #3] 코어 룰 정밀 코딩 & TDD 하네스 검증 (01:00 ~ 03:00)

1. **[Terminal #1] 내부 결정론 코어 로직 집중 코딩**:
   - `prompt_bank/step_by_step_prompts.md` 의 `[Step 3-A: 00:40]` 프롬프트 사용
   ```text
   SPEC.md와 매핑된 레퍼런스 솔버(engine/solver_*.py)를 기반으로, UI나 외부 네트워크 호출 없이 오직 src/data/samples.js(전처리 파서)와 src/core/rules.js(결정론 코어 엔진)의 로직만 완벽하게 구현해 줘.

   1. src/data/samples.js:
      - Null, 빈 문자열, NaN, 센티널 -999, INVALID 플래그 등 어떠한 비정상 데이터가 유입되어도 크래시 없이 분리하는 sanitizeAndParseInput() 함수 완성.
      - 과제 스키마에 맞춘 3종 골든 샘플(normal, warning, violation) 데이터 객체 작성.

   2. src/core/rules.js:
      - evaluateCoreRules(inputPayload): SPEC.md에서 확정한 임계치 상수(THRESHOLD_CONFIG), 계산 수식, 이상치 격리, 적용 규칙 ID(ruleId), 점수(score)를 산출하는 100% 순수 함수로 구현.
      - 도메인 특화 수식을 완벽히 이식할 것.
   ```

2. **[Terminal #3] TDD 하네스 즉시 검증 (코드 한 줄 고칠 때마다 반복 실행, 3초 소요)**:
   ```bash
   node engine/deterministic_harness.mjs
   # ➔ 6 / 6 ALL PASS 확인!

   python engine/auto_solver_pipeline.py --workspace .
   # ➔ output/result.json 최종 갱신 확인!
   ```

* **Terminal #3에서 3차 로컬 Git 커밋**:
  ```bash
  git add -A
  git commit -m "feat: implement deterministic core rules and pass 6/6 harness"
  ```

---

### 🖥️ Step 4. [Terminal #2 & #3] 웹 콘솔 스캐폴딩 & 실시간 프리뷰 (03:00 ~ 04:00)

1. **Terminal #3에서 스캐폴딩 실행**:
   ```bash
   python engine/scaffold_app.py
   npm install
   ```

2. **Terminal #2에서 0.0.0.0 실시간 서버 기동 (대회 종료까지 유지)**:
   ```bash
   npm run dev
   # 0.0.0.0:5173 기동 확인 후 절대 닫지 않음
   ```

3. **Terminal #1에서 UI/AI 연동 지시**:
   - `prompt_bank/step_by_step_prompts.md` 의 `[Step 3-B: 01:00]` 프롬프트 사용
   ```text
   검증된 src/core/rules.js 코어와 src/ai/reporter.js, 그리고 src/components/Dashboard.jsx를 연결해 줘.
   1. src/ai/reporter.js: AI 호출 실패나 1.5초 타임아웃 시 0.1초 내로 코어 판정 수치 기반 표준 SOP 리포트를 반환하는 generateInsightWithFallback() 구현.
   2. src/components/Dashboard.jsx: 3종 골든 샘플 버튼, 실데이터 자동 로드 버튼, What-If 슬라이더, 결과 Export 버튼 연결.
   ```

4. **내장 브라우저(`http://0.0.0.0:5173`) 실시간 검증**:
   - 상단 `[Type A | Type B | Type C | Type D]` 아키타입 모드 전환 확인.
   - 3종 골든 샘플 원클릭 버튼 (🟢 NORMAL / 🟡 WARNING / 🔴 VIOLATION) 상태 배지 동작.
   - What-If 슬라이더 조작 시 판정 수치 실시간 변화 확인.

* **Terminal #3에서 4차 로컬 Git 커밋**:
  ```bash
  git add -A
  git commit -m "feat: scaffold web console and verify 0.0.0.0 live preview"
  ```

---

### 📝 Step 5. [Terminal #1 메인 에이전트] 평가위원용 3대 문서 완성 (04:00 ~ 05:30)
* **어디서?**: **Terminal #1 (Codex CLI 메인 에이전트)**
* **수행 내용**:
  ```text
  지금까지 구현된 실제 파일 경로와 함수명을 바탕으로 루트 경로의 3대 문서를 최종 완성해 줘.

  1. SPEC.md: In-Scope 항목 옆에 실제 구현된 파일과 함수명을 [구현 좌표: 파일명 - 함수명()] 형식으로 100% 매핑.
  2. SOLUTION_NOTES.md: 5대 아키텍처 대안 비교표, 1개 채택 및 4개 기각 사유, 결정론 코어 80% / AI 20% 책임 소재(Accountability) 매트릭스를 정밀 보강.
  3. HANDOFF.md: 유지보수자를 위한 인계서 작성 (구동법, 임계치 수정 위치, 하네스 실행법, 3단 리스크 분석).
  ```

* **Terminal #3에서 5차 로컬 Git 커밋**:
  ```bash
  git add -A
  git commit -m "docs: complete SPEC, SOLUTION_NOTES, and HANDOFF documentation"
  ```

---

### 🛡️ Step 6. [Terminal #3 서브 에이전트] 최종 게이트키퍼 감사 & 제출 (05:30 ~ 06:00)
* **어디서?**: **Terminal #3 (서브 에이전트 워커 창)**
* **입력할 명령어**:
  ```bash
  # 1. 11대 솔버 전수 검증 (11/11 PASS 확인)
  python engine/blackbox_emulator.py --verify-solvers

  # 2. JS 결정론 코어 하네스 (6/6 PASS 확인)
  node engine/deterministic_harness.mjs

  # 3. 최종 게이트키퍼 7대 관문 검사 (PASS: 7 | WARN: 0 확인)
  python engine/final_gatekeeper.py .
  ```

* **최종 Git 커밋 및 상태 확인 (`[Terminal #3]`에서 실행)**:
  ```bash
  git add -A
  git commit -m "chore: final submission readiness verified by gatekeeper"
  git status
  # "nothing to commit, working tree clean" 확인 후 안전 제출!
  ```
