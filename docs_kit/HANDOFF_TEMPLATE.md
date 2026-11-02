# 🤝 HANDOFF.md — 시스템 인수인계서 및 3단계 리스크 분석

## 1. 전체 아키텍처 및 데이터 파이프라인 흐름
```text
[사용자 입력 / 3종 골든 샘플 버튼 (정상·경고·위반)]
       │
       ▼
[1. Data Layer (src/data/)] ➔ 입력 스키마 검증, 결측치(Null/빈값) 안전 정제
       │
       ▼
[2. Deterministic Core (src/core/rules.js)] ➔ 100% 고정 수식·임계치·정규식 판정 (80% 역할)
       │
       ▼
[3. AI Interpretation Layer (src/ai/reporter.js)] ➔ 판정 근거 기반 요약·조치문 생성 (20% 역할)
       │  (※ API 에러/타임아웃 시 0.1초 내 결정론 Fallback 리포트로 자동 우회)
       ▼
[4. Presentation UI (src/components/)] ➔ 상태 배지, 수치 요약 카드, 차트/테이블 렌더링
