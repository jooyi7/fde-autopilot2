#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - Pre-Optimization Diagnostician & Bottleneck Profiler (v1.0)
최적화를 시작하기 전, 다음 2대 핵심 의사결정 질문을 100% 결정론적으로 자동 진단합니다:
1) "이 문제의 평가지표가 정확도인가 속도인가?" (Accuracy/Quality vs Speed/Latency/Throughput)
2) "병목이 알고리즘(시간 복잡도 $O(2^N)$)에 있는가 하드웨어(자원/메모리/I/O 한계)에 있는가?"
"""

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from config_loader import load_config
from cofa_probe import read_text_auto_encoding, read_delimited_table

# ------------------------------------------------------------------------------
# 1. 지표(Metric) 분류 사전
# ------------------------------------------------------------------------------
SPEED_KEYWORDS = {
    "latency": 3.0, "throughput": 3.0, "fps": 3.0, "qps": 3.0, "tat": 3.0,
    "makespan": 3.0, "makespan_hours": 3.0, "response_time": 2.5, "execution_time": 2.5,
    "real_time": 2.5, "timeout": 2.0, "speed": 2.0, "delay": 2.0, "lead_time": 2.0,
    "지연시간": 3.0, "처리량": 3.0, "턴어라운드": 3.0, "소요시간": 2.5, "실시간": 2.5,
    "초당": 2.0, "대기시간": 2.0, "속도": 2.0, "납기": 2.0, "병목시간": 2.5,
}

ACCURACY_KEYWORDS = {
    "accuracy": 3.0, "f1": 3.0, "f1_score": 3.0, "auc": 3.0, "auroc": 3.0,
    "precision": 2.5, "recall": 2.5, "error_rate": 2.5, "loss": 2.5, "cost": 2.5,
    "cpk": 3.0, "yield": 3.0, "base_yield_pct": 3.0, "m3s": 3.0, "spec_limit": 2.5,
    "roic": 3.0, "eva": 3.0, "opm": 2.5, "operating_profit": 2.5, "profit": 2.0,
    "penalty": 2.0, "false_alarm": 3.0, "missed_fault": 3.0, "정확도": 3.0,
    "수율": 3.0, "공정능력": 3.0, "오차": 2.5, "손실": 2.5, "비용": 2.5,
    "이익": 2.0, "감점": 2.0, "합격선": 2.0, "품질": 2.5, "불량률": 3.0,
}


class PreOptDiagnostician:
    def __init__(self, workspace_root: Path):
        self.root = workspace_root.resolve()
        self.config = load_config(self.root)
        self.corpus_text = ""
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        self.file_sizes: Dict[str, int] = {}
        self._load_workspace_data()

    def _load_workspace_data(self) -> None:
        """문서 및 테이블 데이터를 로드하고 파일 용량을 기록"""
        ignore_dirs = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", ".autopilot", "output"}
        texts = []

        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            for fname in sorted(filenames):
                fpath = Path(dirpath) / fname
                ext = fpath.suffix.lower()
                try:
                    fsize = fpath.stat().st_size
                    self.file_sizes[str(fpath.relative_to(self.root))] = fsize
                except Exception:
                    continue

                if ext in {".md", ".txt", ".json", ".yaml", ".yml", ".toml"} and fsize < 1_000_000:
                    try:
                        content = read_text_auto_encoding(fpath, max_bytes=64_000)
                        texts.append(content)
                    except Exception:
                        pass
                elif ext in {".csv", ".tsv"} and fsize < 50_000_000:
                    try:
                        rows = read_delimited_table(fpath, max_rows=10000)
                        if rows:
                            self.tables[fname] = rows
                    except Exception:
                        pass

        self.corpus_text = " ".join(texts).lower()

    # -------------------------------------------------------------------------
    # 1. "이 문제의 평가지표가 정확도인가 속도인가?" 판정
    # -------------------------------------------------------------------------
    def evaluate_metric_target(self) -> Dict[str, Any]:
        """
        문제 지문, 문서, 데이터셋 컬럼에서 요구하는 평가지표의 성격을 분류:
        - ACCURACY_CRITICAL: F1, 수율, 비용최소화, Cpk, 오차 등 품질 지향
        - SPEED_CRITICAL: 지연시간(Latency), 처리량(Throughput), TAT 등 속도 지향
        - BALANCED_TRADE_OFF: 시간 제약 내에서 품질 최대화 (Anytime / Pareto)
        """
        user_override = self.config.get("optimization", {}).get("target_metric", "auto").lower()
        if user_override in {"accuracy", "speed", "balanced"}:
            return {
                "metric_classification": f"{user_override.upper()}_FORCED_BY_CONFIG",
                "dominant_metric": user_override.upper(),
                "accuracy_score": 100.0 if user_override == "accuracy" else 0.0,
                "speed_score": 100.0 if user_override == "speed" else 0.0,
                "reason": f"config.toml의 [optimization.target_metric = '{user_override}'] 설정에 의해 강제 지정됨.",
                "evidence": [],
            }

        # 키워드 빈도 및 가중치 매칭
        acc_hits = []
        spd_hits = []
        acc_total = 0.0
        spd_total = 0.0

        for kw, weight in ACCURACY_KEYWORDS.items():
            matches = list(re.finditer(re.escape(kw), self.corpus_text))
            if matches:
                cnt = len(matches)
                score = cnt * weight
                acc_total += score
                acc_hits.append({"keyword": kw, "count": cnt, "score": round(score, 1)})

        for kw, weight in SPEED_KEYWORDS.items():
            matches = list(re.finditer(re.escape(kw), self.corpus_text))
            if matches:
                cnt = len(matches)
                score = cnt * weight
                spd_total += score
                spd_hits.append({"keyword": kw, "count": cnt, "score": round(score, 1)})

        acc_hits.sort(key=lambda x: x["score"], reverse=True)
        spd_hits.sort(key=lambda x: x["score"], reverse=True)

        # 컬럼명에서도 탐지
        all_cols = []
        for t_rows in self.tables.values():
            if t_rows and isinstance(t_rows[0], dict):
                all_cols.extend([str(k).lower() for k in t_rows[0].keys()])
        for c in all_cols:
            if any(k in c for k in ("time", "duration", "latency", "tat", "queue")):
                spd_total += 5.0
            if any(k in c for k in ("yield", "cpk", "score", "val", "error", "loss", "cost", "m3s")):
                acc_total += 5.0

        total_score = acc_total + spd_total
        if total_score == 0:
            classification = "ACCURACY_DEFAULT"
            dominant = "ACCURACY"
            recommendation = "특정 지표가 명시되지 않았으므로 반도체/산업 기본 규칙인 정확도(수율/품질 0.1% 무결성)를 최우선 목표로 설정합니다."
        else:
            acc_ratio = acc_total / total_score
            if acc_ratio >= 0.70:
                classification = "ACCURACY_CRITICAL"
                dominant = "ACCURACY"
                recommendation = "정확도/수율/오차 최소화가 절대 지표입니다. Branch & Bound, 미세 격자 탐색, 정확 DP를 우선 채택하십시오."
            elif acc_ratio <= 0.30:
                classification = "SPEED_CRITICAL"
                dominant = "SPEED"
                recommendation = "지연시간 단축/처리량 극대화가 절대 지표입니다. Greedy 휴리스틱, 조기 종료(Early Exit), 캐싱을 적용하십시오."
            else:
                classification = "BALANCED_TRADE_OFF"
                dominant = "BALANCED"
                recommendation = "시간 제약 하에서 정확도를 극대화해야 하는 복합 과제입니다. 타임아웃 가드레일이 포함된 B&B 또는 Simulated Annealing을 권장합니다."

        return {
            "metric_classification": classification,
            "dominant_metric": dominant,
            "accuracy_score": round(acc_total, 1),
            "speed_score": round(spd_total, 1),
            "accuracy_top_keywords": acc_hits[:5],
            "speed_top_keywords": spd_hits[:5],
            "strategic_recommendation": recommendation,
        }

    # -------------------------------------------------------------------------
    # 2. "병목이 알고리즘(시간 복잡도)에 있는가 하드웨어(자원 한계)에 있는가?" 판정
    # -------------------------------------------------------------------------
    def evaluate_bottleneck_nature(self) -> Dict[str, Any]:
        """
        입력 데이터의 스케일($N, M$)과 문제 구조(조합/경로/부분집합)를 분석하여
        병목의 본질을 진단:
        - ALGORITHMIC_COMPLEXITY_BOUND: N은 작으나 탐색 공간이 지수($2^N, N!$)로 폭증 (알고리즘 최적화 필요)
        - HARDWARE_RESOURCE_BOUND: N이 수만~수십만 건 이상이거나 파일 크기가 커 메모리/I/O 병목 발생 (하드웨어/벡터화 최적화 필요)
        - COMPUTE_HEAVY_SIMULATION: 시뮬레이션 반복 횟수가 많아 수치 연산 병목 발생
        - LIGHTWEIGHT_DIRECT_SOLVABLE: 소규모 데이터로 즉시 계산 가능
        """
        combinatorial_limit = int(self.config.get("bottleneck", {}).get("combinatorial_exact_limit", 24))
        large_row_limit = int(self.config.get("bottleneck", {}).get("large_data_threshold_rows", 30000))
        memory_limit_mb = float(self.config.get("bottleneck", {}).get("memory_warning_mb", 1024.0))

        # 데이터 스케일 측정
        total_rows = sum(len(r) for r in self.tables.values())
        max_table_rows = max([len(r) for r in self.tables.values()] + [0])
        total_bytes = sum(self.file_sizes.values())
        total_mb = round(total_bytes / (1024.0 * 1024.0), 2)

        # 조합 최적화 구조 탐지 (후보 아이템 수 파악)
        candidate_item_counts = []
        for tname, rows in self.tables.items():
            if len(rows) > 0 and len(rows) <= 1000:
                first_row = rows[0]
                cols = {str(k).lower() for k in first_row.keys()}
                if ({"cost", "value"} <= cols) or ("covered_zones" in cols) or ({"proc_time"} <= cols) or ("product_name" in cols) or ("module_id" in cols):
                    candidate_item_counts.append((tname, len(rows)))

        max_comb_n = max([c[1] for c in candidate_item_counts] + [0])

        # 가벼운 마이크로 벤치마크 (I/O 파싱 속도 vs CPU 연산 속도 측정)
        t_io_start = time.perf_counter()
        _dummy_hash = sum(len(str(v)) for rows in self.tables.values() for r in rows[:100] for v in r.values())
        t_io_end = time.perf_counter()
        io_scan_ms = round((t_io_end - t_io_start) * 1000.0, 3)

        # 판정 로직
        is_hardware_bound = (total_rows >= large_row_limit) or (total_mb >= 50.0)
        is_algo_bound = False
        algo_risk_level = "LOW"
        algo_details = []

        if max_comb_n > 0:
            if max_comb_n <= 12:
                algo_risk_level = "TRIVIAL (Exact Exhaustive feasible)"
            elif max_comb_n <= combinatorial_limit:
                algo_risk_level = f"MODERATE (Branch & Bound feasible, 2^{max_comb_n} approx {2**min(max_comb_n, 30):,})"
                is_algo_bound = True
            else:
                algo_risk_level = f"CRITICAL_EXPONENTIAL_EXPLOSION (2^{max_comb_n} requires Metaheuristic / Greedy!)"
                is_algo_bound = True
            algo_details.append(f"최대 조합 후보 아이템 수 N={max_comb_n} (임계치 {combinatorial_limit})")

        # 시계열/시뮬레이션 반복 여부
        is_simulation_bound = any(k in self.corpus_text for k in ("monte carlo", "grid search", "simulation", "시나리오", "몬테카를로"))

        if is_hardware_bound and is_algo_bound:
            nature = "DUAL_COMPLEXITY_AND_HARDWARE_BOUND"
            bottleneck_summary = "데이터 행 수가 크고 동시에 조합 최적화 구조를 가집니다. 데이터 스트리밍과 메타휴리스틱(SA)을 동시 적용해야 합니다."
            opt_recipe = ["NumPy 기반 벡터화 연산", "입력 데이터 Chunking/스트리밍", "Simulated Annealing 메타휴리스틱 채택"]
        elif is_algo_bound:
            nature = "ALGORITHMIC_COMPLEXITY_BOUND"
            bottleneck_summary = f"데이터 용량은 작으나 탐색 공간이 {algo_risk_level} 수준으로 지수 폭발합니다. 알고리즘(시간 복잡도) 최적화가 필수적입니다."
            opt_recipe = [
                "Branch & Bound 조기 가지치기(Pruning) 적용",
                "동적 계획법(DP) 메모이제이션 테이블 활용",
                f"N > {combinatorial_limit} 일 경우 Simulated Annealing으로 즉시 전환"
            ]
        elif is_hardware_bound:
            nature = "HARDWARE_RESOURCE_BOUND"
            bottleneck_summary = f"행 수({total_rows:,}행) 또는 파일 크기({total_mb}MB)가 큽니다. 알고리즘보다 메모리 대역폭과 I/O 파싱이 주요 병목입니다."
            opt_recipe = [
                "CSV 전체 파싱 대신 필수 컬럼만 선택 로드",
                "int64 -> int32, float64 -> float32 메모리 다운캐스팅",
                "멀티프로세싱 병렬 파싱 (enable_multiprocessing=true)"
            ]
        elif is_simulation_bound:
            nature = "COMPUTE_HEAVY_SIMULATION_BOUND"
            bottleneck_summary = "평가 시나리오 수가 많은 연속 최적화 문제입니다. 황금분할 탐색이나 파레토 프론티어로 평가 횟수를 단축하십시오."
            opt_recipe = ["황금분할 1차원 수렴(15회 평가)", "시뮬레이션 조기 수렴(Early Convergence) 판정"]
        else:
            nature = "LIGHTWEIGHT_DIRECT_SOLVABLE"
            bottleneck_summary = "데이터와 탐색 공간이 모두 작아 하드웨어나 복잡도 병목이 없습니다. 0.1초 내 결정론적 정확해 산출이 가능합니다."
            opt_recipe = ["표준 Pure Python 솔버 직접 실행", "안전한 경계값 및 결측치 방어 검증에 집중"]

        return {
            "bottleneck_nature": nature,
            "total_rows": total_rows,
            "max_table_rows": max_table_rows,
            "total_workspace_mb": total_mb,
            "max_combinatorial_items_n": max_comb_n,
            "algorithmic_risk_level": algo_risk_level,
            "io_microbenchmark_ms": io_scan_ms,
            "bottleneck_summary": bottleneck_summary,
            "recommended_optimization_recipes": opt_recipe,
        }

    # -------------------------------------------------------------------------
    # 3. 종합 진단 및 config.toml 권고안 도출
    # -------------------------------------------------------------------------
    def run_full_diagnosis(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        metric_eval = self.evaluate_metric_target()
        bottleneck_eval = self.evaluate_bottleneck_nature()
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 최적화 아키텍처 4분면 매핑
        # [Q1: Accuracy + Algo-Bound] -> B&B, DP, Exact ILP
        # [Q2: Accuracy + Hardware-Bound] -> NumPy Vectorized Bayes, Chunked Exact
        # [Q3: Speed + Algo-Bound] -> Greedy, Simulated Annealing with Tight Iteration
        # [Q4: Speed + Hardware-Bound] -> Stream Processing, SIMD, Kernel Fusion
        dominant_metric = metric_eval["dominant_metric"]
        dominant_bottleneck = bottleneck_eval["bottleneck_nature"]

        if dominant_metric == "ACCURACY":
            recommended_strategy = "exact" if "ALGORITHMIC" in dominant_bottleneck or "LIGHTWEIGHT" in dominant_bottleneck else "vectorized_exact"
        elif dominant_metric == "SPEED":
            recommended_strategy = "greedy_fast" if "ALGORITHMIC" in dominant_bottleneck else "streaming_pipeline"
        else:
            recommended_strategy = "sa_or_anytime_bnb"

        report = {
            "workspace": ".",
            "diagnostics_elapsed_ms": elapsed_ms,
            "evaluation_metric_axis": metric_eval,
            "bottleneck_nature_axis": bottleneck_eval,
            "integrated_decision": {
                "quadrant": f"{dominant_metric} × {dominant_bottleneck}",
                "recommended_primary_strategy": recommended_strategy,
                "config_toml_recommended_settings": {
                    "optimization.target_metric": dominant_metric.lower(),
                    "optimization.preferred_strategy": "exact" if "exact" in recommended_strategy else "heuristic",
                    "bottleneck.combinatorial_exact_limit": 24 if "ALGORITHMIC" in dominant_bottleneck else 32,
                    "bottleneck.enable_multiprocessing": True if "HARDWARE" in dominant_bottleneck else False,
                },
            },
        }
        return report

    def render_markdown_report(self, report: Dict[str, Any]) -> str:
        m = report["evaluation_metric_axis"]
        b = report["bottleneck_nature_axis"]
        d = report["integrated_decision"]

        lines = [
            "# 🔬 최적화 사전 진단 리포트 (Pre-Optimization Diagnostic Report)",
            f"> 진단 일시: {time.strftime('%Y-%m-%d %H:%M:%S')} | 진단 소요: {report['diagnostics_elapsed_ms']}ms",
            "",
            "## 1. 평가지표 진단: 정확도인가 속도인가? (Accuracy vs Speed)",
            f"- **최종 판정**: `{m['metric_classification']}` (우선순위: **{m['dominant_metric']}**)",
            f"- **지표별 가중치 스코어**: 정확도/품질 지표 `{m['accuracy_score']}점` vs 속도/지연시간 지표 `{m['speed_score']}점`",
            f"- **핵심 근거 (정확도)**: " + ", ".join(f"`{k['keyword']}`({k['count']}회)" for k in m.get("accuracy_top_keywords", [])) if m.get("accuracy_top_keywords") else "- 감지된 명시 키워드 없음",
            f"- **핵심 근거 (속도)**: " + ", ".join(f"`{k['keyword']}`({k['count']}회)" for k in m.get("speed_top_keywords", [])) if m.get("speed_top_keywords") else "- 감지된 명시 키워드 없음",
            f"- **전략 가이드**: {m['strategic_recommendation']}",
            "",
            "## 2. 병목 성격 진단: 알고리즘인가 하드웨어인가? (Algorithm vs Hardware)",
            f"- **최종 판정**: `{b['bottleneck_nature']}`",
            f"- **데이터 규모**: 총 `{b['total_rows']:,}`행 / 파일 용량 `{b['total_workspace_mb']}`MB (최대 단일 테이블: `{b['max_table_rows']:,}`행)",
            f"- **조합 복잡도 위험도**: `{b['algorithmic_risk_level']}`",
            f"- **병목 분석 요약**: {b['bottleneck_summary']}",
            "- **권장 최적화 레시피**:",
        ]
        for r in b.get("recommended_optimization_recipes", []):
            lines.append(f"  * {r}")

        lines.extend([
            "",
            "## 3. 통합 최적화 의사결정 매트릭스 (Actionable Recommendation)",
            f"- **선정 4분면**: `{d['quadrant']}`",
            f"- **최우선 권장 전략**: `{d['recommended_primary_strategy']}`",
            "- **`config.toml` 자동 동기화 권장 설정**:",
            "  ```toml",
            "  [optimization]",
            f"  target_metric = \"{d['config_toml_recommended_settings']['optimization.target_metric']}\"",
            f"  preferred_strategy = \"{d['config_toml_recommended_settings']['optimization.preferred_strategy']}\"",
            "",
            "  [bottleneck]",
            f"  combinatorial_exact_limit = {d['config_toml_recommended_settings']['bottleneck.combinatorial_exact_limit']}",
            f"  enable_multiprocessing = {str(d['config_toml_recommended_settings']['bottleneck.enable_multiprocessing']).lower()}",
            "  ```",
        ])
        return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-Optimization Metric & Bottleneck Diagnostician")
    parser.add_argument("--workspace", default=".", help="Workspace root directory")
    parser.add_argument("--out", default=".autopilot/pre_opt_diagnosis_report.json", help="Output JSON path")
    args = parser.parse_args()

    root = Path(args.workspace).resolve()
    diag = PreOptDiagnostician(root)
    report = diag.run_full_diagnosis()

    out_file = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_text = diag.render_markdown_report(report)
    md_file = out_file.with_suffix(".md")
    md_file.write_text(md_text, encoding="utf-8")

    print(md_text)
    print(f"\n💾 리포트 저장 완료:\n  - JSON: {out_file}\n  - Markdown: {md_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

