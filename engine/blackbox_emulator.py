#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDE Autopilot - Multi-Agent / Multi-User & 5-Domain Blackbox Emulator (v3.0)
1) Simulates 25 concurrent actors with real payload mutations (Null, Sentinel -999, Extreme Spikes, Duplicates)
2) Provides `--verify-solvers` mode to run automated self-tests across all 5 semiconductor domain solvers.
"""

import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List


class BlackboxEmulator:
    def __init__(self, target_cmd: str, num_virtual_users: int = 25):
        self.target_cmd = target_cmd
        self.num_virtual_users = num_virtual_users

    @staticmethod
    def _mutate_for_boundary_or_spike(obj: Any, mode: str) -> Any:
        if isinstance(obj, dict):
            mutated = {}
            for k, v in obj.items():
                if mode == "EMPTY_OR_ZERO_BOUNDARY" and isinstance(v, (int, float)):
                    mutated[k] = 0.0
                elif mode == "EXTREME_SPIKE_OUTLIER" and isinstance(v, (int, float)):
                    mutated[k] = -999.0 if "dx" in k.lower() else float(v) * 25.0
                elif mode == "MISSING_OPTIONAL_FIELDS" and k in {"samples", "measurements", "competitor_records"}:
                    mutated[k] = []
                else:
                    mutated[k] = BlackboxEmulator._mutate_for_spike_recursive(v, mode)
            return mutated
        return obj

    @staticmethod
    def _mutate_for_spike_recursive(val: Any, mode: str) -> Any:
        if isinstance(val, list) and val:
            if mode == "DUPLICATE_IDEMPOTENCY_CHECK":
                return val + [val[0]]
            return [BlackboxEmulator._mutate_for_boundary_or_spike(item, mode) for item in val]
        if isinstance(val, dict):
            return BlackboxEmulator._mutate_for_boundary_or_spike(val, mode)
        return val

    def generate_adversarial_payloads(self, base_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """정상 요청 + 경계값(0) + 센티널(-999)/극댓값 + 결측/중복 요청 등 25개 실제 변이 시나리오 생성"""
        payloads = []
        for uid in range(1, self.num_virtual_users + 1):
            p = json.loads(json.dumps(base_payload))
            scenario = "NORMAL"

            if uid == 21:
                scenario = "EMPTY_OR_ZERO_BOUNDARY"
                p = self._mutate_for_boundary_or_spike(p, scenario)
            elif uid == 22:
                scenario = "EXTREME_SPIKE_OUTLIER"
                p = self._mutate_for_boundary_or_spike(p, scenario)
            elif uid == 23:
                scenario = "DUPLICATE_IDEMPOTENCY_CHECK"
                p = self._mutate_for_spike_recursive(p, scenario)
            elif uid == 24:
                scenario = "MISSING_OPTIONAL_FIELDS"
                p = self._mutate_for_boundary_or_spike(p, scenario)
            elif uid == 25:
                scenario = "CONCURRENT_CONFLICT_STRESS"

            if isinstance(p, dict):
                p["_emulator_user_id"] = f"virtual_actor_{uid:02d}"
                p["_scenario_type"] = scenario
            payloads.append(p)
        return payloads

    def _run_single_actor(self, idx: int, payload: Dict[str, Any], tmp_dir: Path) -> Dict[str, Any]:
        in_file = tmp_dir / f"actor_{idx:02d}_in.json"
        out_file = tmp_dir / f"actor_{idx:02d}_out.json"
        in_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        cmd = f"{self.target_cmd} {in_file} {out_file}"
        t0 = time.time()
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        elapsed_ms = (time.time() - t0) * 1000.0

        state_changed = out_file.exists() and out_file.stat().st_size > 2
        output_data = None
        if state_changed:
            try:
                output_data = json.loads(out_file.read_text(encoding="utf-8"))
            except Exception:
                state_changed = False

        return {
            "actor_id": idx,
            "scenario": payload.get("_scenario_type"),
            "exit_code": proc.returncode,
            "elapsed_ms": round(elapsed_ms, 2),
            "state_verified": state_changed,
            "stderr_snippet": proc.stderr.strip()[:200] if proc.returncode != 0 else "",
            "output_keys": list(output_data.keys()) if isinstance(output_data, dict) else [],
        }

    def execute_swarm(self, base_payload: Dict[str, Any]) -> Dict[str, Any]:
        tmp_dir = Path("/tmp/fde_blackbox_swarm")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        payloads = self.generate_adversarial_payloads(base_payload)

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(self._run_single_actor, i + 1, p, tmp_dir)
                for i, p in enumerate(payloads)
            ]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        results.sort(key=lambda x: x["actor_id"])
        passed = [r for r in results if r["exit_code"] == 0 and r["state_verified"]]
        failed = [r for r in results if r["exit_code"] != 0 or not r["state_verified"]]

        return {
            "total_virtual_actors": self.num_virtual_users,
            "passed_count": len(passed),
            "failed_count": len(failed),
            "pass_rate_pct": round((len(passed) / self.num_virtual_users) * 100.0, 2),
            "failures": failed,
            "actor_logs": results,
        }


def run_five_domain_solver_selftest(engine_dir: Path) -> int:
    """5대 반도체 도메인 솔버에 대해 표준/경계/센티널 입력을 주입하여 일괄 무결성 검증"""
    sys.path.insert(0, str(engine_dir))
    from solver_overlay import OverlaySolver
    from solver_material import MaterialQualitySolver
    from solver_market import MarketStrategySolver
    from solver_value_chain_biz import ValueChainBusinessSolver
    from solver_curriculum import CurriculumOntologySolver

    print("================================================================")
    print("🔬 [5-Domain Solver Suite] 반도체 5대 현업 솔버 무결성 자가진단")
    print("================================================================")

    # 1. Overlay Solver Test
    ovl_res = OverlaySolver.solve_apc(
        measurements=[
            {"X": -100, "Y": -80, "x": -10, "y": -10, "dx": 1.2, "dy": -0.9, "pre_process_stress_mpa": 120.0, "chuck_id": "C1", "etch_chamber_id": "E1"},
            {"X": 100, "Y": -80, "x": 10, "y": -10, "dx": 1.5, "dy": -1.1, "pre_process_stress_mpa": 135.0, "chuck_id": "C1", "etch_chamber_id": "E1"},
            {"X": -100, "Y": 80, "x": -10, "y": 10, "dx": -1.1, "dy": 1.3, "pre_process_stress_mpa": -90.0, "chuck_id": "C2", "etch_chamber_id": "E2"},
            {"X": 100, "Y": 80, "x": 10, "y": 10, "dx": -1.3, "dy": 1.0, "pre_process_stress_mpa": -110.0, "chuck_id": "C2", "etch_chamber_id": "E2"},
            {"X": 0, "Y": 0, "x": 0, "y": 0, "dx": 0.2, "dy": 0.1, "pre_process_stress_mpa": 10.0, "chuck_id": "C1", "etch_chamber_id": "E1"},
            {"X": 50, "Y": 50, "x": 5, "y": 5, "dx": 0.6, "dy": -0.4, "pre_process_stress_mpa": 40.0, "chuck_id": "C1", "etch_chamber_id": "E1"},
            {"X": -50, "Y": -50, "x": -5, "y": -5, "dx": -0.5, "dy": 0.5, "pre_process_stress_mpa": -30.0, "chuck_id": "C2", "etch_chamber_id": "E2"},
            {"X": 140, "Y": 140, "x": 12, "y": 12, "dx": -999.0, "dy": 9999.0, "status": "INVALID"},  # Sentinel test
        ],
        candidate_scanners=[
            {"scanner_id": "EUV_SCANNER_01", "matching_offset_nm": 0.18, "queue_time_mins": 25},
            {"scanner_id": "EUV_SCANNER_02", "matching_offset_nm": 0.42, "queue_time_mins": 10},
        ],
    )
    assert "smart_sampling_plan" in ovl_res and "chamber_and_scanner_matching" in ovl_res
    print(f"✅ [1/5 PASS] 이천 포토기술팀 (OverlaySolver): status={ovl_res['status']}, order={ovl_res['selected_order']}, scanner={ovl_res['chamber_and_scanner_matching']['optimal_scanner_routing']}")

    # 2. Material Quality Solver Test
    mat_res = MaterialQualitySolver.compare_vendors(
        specs={"metal_ppb": {"LSL": 0.0, "USL": 5.0, "weight": 0.6}, "moisture_ppm": {"LSL": 0.0, "USL": 20.0, "weight": 0.4}},
        reference_spectrum=[1.0, 2.0, 5.0, 2.0, 1.0],
        vendors=[
            {
                "vendor_id": "VENDOR_A_SAFE",
                "cost_index": 0.92,
                "lead_time_days": 10,
                "samples": {"metal_ppb": [1.1, 1.2, 1.0, 1.1, -999.0], "moisture_ppm": [5.0, 5.2, 4.9, 5.1]},
                "spectrum": [1.0, 2.01, 4.99, 2.0, 1.0],
                "hvm_stress_profile": {"pipe_residence_hours": 10, "pump_shear_particle_growth_pct": 1.5, "remaining_shelf_life_days": 120},
                "subtier_genealogy": {"unreported_4m_detected": False, "pcn_approved": True},
            },
            {
                "vendor_id": "VENDOR_B_4M_VIOLATION",
                "cost_index": 0.80,
                "lead_time_days": 18,
                "samples": {"metal_ppb": [2.1, 2.3, 2.0, 2.2], "moisture_ppm": [8.0, 8.5, 9.0, 8.2]},
                "spectrum": [1.0, 3.8, 5.0, 2.0, 1.0],
                "subtier_genealogy": {"unreported_4m_detected": True, "pcn_approved": False},
            },
        ],
    )
    assert mat_res["recommended_vendor"] == "VENDOR_A_SAFE"
    print(f"✅ [2/5 PASS] 소재품질팀 (MaterialQualitySolver): recommended={mat_res['recommended_vendor']}, status={mat_res['status']}")

    # 3. Market Strategy Solver Test
    mkt_res = MarketStrategySolver.simulate_allocation_grid(
        total_wafer_capa_k=150.0,
        competitor_records=[
            {"company": "Micron", "reported_period": "2025-FQ3", "currency": "USD_BILLION", "revenue": 7.8, "operating_profit": 2.1, "shipment_volume": 4.2, "shipment_unit": "EXABYTE"},
            {"company": "SK hynix", "reported_period": "2025-CQ2", "currency": "KRW_TRILLION", "revenue": 16.4, "operating_profit": 5.5, "shipment_volume": 38.0, "shipment_unit": "B_Gb"},
        ],
        pq_mix_periods={
            "prev": {"total_shipment_bgb": 100.0, "hbm_bit_share_pct": 10.0, "legacy_asp_usd": 3.2, "hbm_asp_usd": 15.0},
            "curr": {"total_shipment_bgb": 108.0, "hbm_bit_share_pct": 22.0, "legacy_asp_usd": 2.85, "hbm_asp_usd": 16.5},
        },
        ir_audit_records=[
            {"company": "Competitor_X", "ir_bullish_sentiment_score": 0.85, "prev_inventory_days_dio": 90.0, "curr_inventory_days_dio": 115.0}
        ],
    )
    assert mkt_res["pq_mix_variance_decomposition"]["mix_illusion_flag"] is True
    print(f"✅ [3/5 PASS] 시장전략팀 (MarketStrategySolver): mix_illusion={mkt_res['pq_mix_variance_decomposition']['mix_illusion_flag']}, optimal_hbm_share={mkt_res['optimal_strategy']['hbm_wafer_share_pct']}%")

    # 4. Value-Chain Business Solver Test
    vc_res = ValueChainBusinessSolver.solve_all({"end_demand_shock_pct": 5.0, "tsmc_cowos_alloc_bgb": 12.5})
    assert vc_res["persona_id"] == "skhynix-value-chain-business-persona"
    print(f"✅ [4/5 PASS] 경영전략팀 (ValueChainBusinessSolver): bottleneck={vc_res['value_chain_and_bullwhip_analysis']['binding_bottleneck_node']}, ROIC={vc_res['capex_roic_optimization']['portfolio_weighted_roic_pct']}%")

    # 5. Semiconductor Educator Curriculum Solver Test
    edu_res = CurriculumOntologySolver.analyze_and_schedule(
        modules=[
            {"id": "M1", "title": "Photolithography & EUV Basics", "stage": "PHOTO", "level": 1, "hours": 4, "prereqs": []},
            {"id": "M2", "title": "HBM3E MR-MUF Advanced Packaging", "stage": "PKG_HBM", "level": 2, "hours": 6, "prereqs": ["M1"]},
        ],
        learner_profile={"completed_ids": [], "target_ids": ["M2"], "max_hours": 20, "role": "FINANCE_STRATEGY", "level": 1},
    )
    assert edu_res["persona_id"] == "skhynix-value-chain-educator-persona" and len(edu_res["learning_path"]) == 2
    print(f"✅ [5/5 PASS] 반도체 산업교육 (CurriculumOntologySolver): scheduled={edu_res['total_scheduled_modules']} modules, DAG_valid={edu_res['is_valid_dag']}")
    print("================================================================")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--verify-solvers":
        sys.exit(run_five_domain_solver_selftest(Path(__file__).resolve().parent))

    if len(sys.argv) < 4:
        print("Usage:")
        print("  1) python3 blackbox_emulator.py --verify-solvers")
        print("  2) python3 blackbox_emulator.py '<target_cmd>' <sample_input.json> <report_out.json>")
        sys.exit(1)

    target_cmd = sys.argv[1]
    sample_in = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    report = BlackboxEmulator(target_cmd, num_virtual_users=25).execute_swarm(sample_in)
    Path(sys.argv[3]).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[BLACKBOX_SWARM] Pass Rate: {report['pass_rate_pct']}% ({report['passed_count']}/25)")
    sys.exit(0 if report["failed_count"] == 0 else 1)
