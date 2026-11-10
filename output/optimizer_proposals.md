# 최적화 방식 후보 제안 (사람이 선택)

## 0. 최적화 사전 진단 결과 (Pre-Optimization Diagnostics)
- **평가지표 성격 (정확도 vs 속도)**: `BALANCED_TRADE_OFF` (지배적 지표: **BALANCED**)
  ↳ 정확도/품질 지표: `245.5점` | 속도/지연 지표: `211.5점`
  ↳ 전략 가이드: 시간 제약 하에서 정확도를 극대화해야 하는 복합 과제입니다. 타임아웃 가드레일이 포함된 B&B 또는 Simulated Annealing을 권장합니다.
- **병목 성격 (알고리즘 vs 하드웨어)**: `COMPUTE_HEAVY_SIMULATION_BOUND`
  ↳ 병목 분석: 평가 시나리오 수가 많은 연속 최적화 문제입니다. 황금분할 탐색이나 파레토 프론티어로 평가 횟수를 단축하십시오.
  ↳ 조합 위험도: `LOW` | 총 행 수: `0`행 | 파일: `1.01MB`

## 감지된 문제 구조
- 최적화 가능한 구조를 감지하지 못했습니다. 컬럼명(cost/value/zones/proc_time/label 등) 확인 또는 --label 지정.

## 후보 (fit_score 높은 순 = 추천도, 최종 선택은 사람)

## 결정이 필요한 질문

## 실행 방법
```
python engine/optimizer_menu.py --workspace . --choose sel_sa --objective max_value --budget 500
python engine/optimizer_menu.py --workspace . --choose 'sel_*'   # 계열 전체 비교
python engine/optimizer_menu.py --workspace . --choose ALL
```

## 설치된 라이브러리 (참고: 있으면 ILP/SAT/GBM 사용 가능, 이 모듈은 의존하지 않음)
numpy:O, scipy:O, pulp:X, ortools:X, z3:X, sklearn:O, lightgbm:X, catboost:X, xgboost:O, torch:O