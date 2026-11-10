#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - Centralized Config.toml Loader & Single Source of Truth Adapter (v1.0)
워크스페이스 루트의 config.toml을 로드하여 플랫폼 설정, 최적화 타깃, 병목 임계치, 11대 솔버 파라미터를 통합 제공합니다.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import sys

try:
    import tomllib  # Python 3.11+
except ImportError:
    tomllib = None  # type: ignore


DEFAULT_CONFIG: Dict[str, Any] = {
    "agent": {
        "default_model": "Sol-6.1",
        "fallback_model": "Terra-5.6",
        "approval_mode": "auto-edit",
    },
    "project": {
        "default_type": "A",
    },
    "context": {
        "instructions_file": "AGENTS.md",
        "ignore_patterns": [
            "node_modules/**", ".git/**", "dist/**", "build/**",
            "__pycache__/**", ".autopilot/**", ".fde_data_profile.md", ".fde_audit_report.md"
        ],
    },
    "execution": {
        "default_host": "0.0.0.0",
        "timeout_seconds": 60,
    },
    "optimization": {
        "target_metric": "auto",            # "accuracy" | "speed" | "balanced" | "auto"
        "preferred_strategy": "auto",        # "exact" | "heuristic" | "sa" | "bnb" | "greedy" | "auto"
        "time_budget_seconds": 30.0,
        "accuracy_hurdle": 0.95,
        "early_stopping_patience": 5,
    },
    "bottleneck": {
        "combinatorial_exact_limit": 24,    # N > 24 조합 최적화 시 지수 폭발 방지 위해 메타휴리스틱 자동 전환
        "large_data_threshold_rows": 30000, # 행 수 > 3만 시 벡터화/스트리밍 모드
        "memory_warning_mb": 1024.0,
        "io_chunk_size": 10000,
        "enable_multiprocessing": True,
    },
    "solvers": {
        "domain_overlay": {"m3s_spec_nm": 2.0, "sampling_ratio": 0.35},
        "domain_material": {"min_cpk": 1.33, "single_vendor_cap_pct": 70.0},
        "domain_market": {"dio_spike_days": 7.0, "fine_grid_step_pct": 0.5},
        "domain_value_chain": {"wacc_pct": 8.5, "holding_cost_musd_per_bgb": 0.45},
        "domain_educator": {"default_max_hours": 40.0, "microlearning_ratio": 0.5},
        "type_a": {"pass_threshold": 80.0, "alarm_time_budget_mins": 30.0},
        "type_b": {"wafer_radius_mm": 150.0, "spare_repair_limit": 10, "min_yield_pct": 75.0},
        "type_c": {"cost_false_alarm": 10.0, "cost_missed_fault": 50.0},
        "type_d": {"available_pm_slots": 2, "default_weibull_beta": 2.5},
        "type_e": {"target_cpk": 1.33, "max_spec_margin_usage_pct": 80.0},
    },
}


def load_config(workspace_root: Optional[Path] = None) -> Dict[str, Any]:
    """config.toml을 안전하게 파싱하여 병합된 딕셔너리를 반환 (Zero-Crash Fallback)"""
    root = workspace_root or Path.cwd()
    config_path = root / "config.toml"
    if not config_path.exists():
        # 상위 디렉터리 탐색
        for parent in root.parents:
            cand = parent / "config.toml"
            if cand.exists():
                config_path = cand
                break

    if not config_path.exists():
        return dict(DEFAULT_CONFIG)

    loaded: Dict[str, Any] = {}
    if tomllib is not None:
        try:
            with open(config_path, "rb") as f:
                loaded = tomllib.load(f)
        except Exception:
            pass

    # 깊은 병합 (Deep Merge with DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    for section, sec_vals in loaded.items():
        if isinstance(sec_vals, dict) and isinstance(merged.get(section), dict):
            sub = dict(merged[section])
            sub.update(sec_vals)
            merged[section] = sub
        else:
            merged[section] = sec_vals

    return merged


def get_solver_config(solver_key: str, workspace_root: Optional[Path] = None) -> Dict[str, Any]:
    """특정 솔버 전용 설정을 추출"""
    cfg = load_config(workspace_root)
    solvers = cfg.get("solvers", {})
    return solvers.get(solver_key, {})


if __name__ == "__main__":
    cfg = load_config()
    print("✅ config.toml 로드 성공:")
    print(f"- target_metric: {cfg.get('optimization', {}).get('target_metric')}")
    print(f"- combinatorial_exact_limit: {cfg.get('bottleneck', {}).get('combinatorial_exact_limit')}")
    print(f"- solvers keys: {list(cfg.get('solvers', {}).keys())}")

