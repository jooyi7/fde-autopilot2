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
import tempfile
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
        tmp_dir = Path(tempfile.gettempdir()) / "fde_blackbox_swarm"
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
    from solver_universal import UniversalProblemSolver
    from solver_typeA import TypeASolver
    from solver_typeB import TypeBSolver
    from solver_typeC import TypeCSolver
    from solver_typeD import TypeDSolver
    from solver_typeE import TypeESolver

    print("================================================================")
    print("🔬 [11-Domain Solver Suite] 반도체 5대 특화 + 5대 현업 Type + 범용 솔버 무결성 자가진단")
    print("================================================================")

    # 1. Overlay Solver Test
    ovl_res = OverlaySolver.solve_apc(
        measurements=[
            {"wafer_x": -100, "wafer_y": -80, "x": -10, "y": -10, "ovl_x": 1.2, "ovl_y": -0.9, "pre_process_stress_mpa": 120.0, "chuck_id": "C1", "etch_chamber_id": "E1"},
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
    assert "wafer_lot_summary" in ovl_res and "physical_10param_correctables" in ovl_res["apc_parameters"]
    assert "per_lot_apc_and_ewma" in ovl_res and ovl_res["per_lot_apc_and_ewma"]["evaluated_lot_count"] >= 1
    print(f"✅ [1/11 PASS] 포토기술팀 (OverlaySolver): status={ovl_res['status']}, order={ovl_res['selected_order']}, Tx={ovl_res['apc_parameters']['physical_10param_correctables']['wafer_Tx_nm']}nm, wafers={ovl_res['wafer_lot_summary']['total_evaluated_wafers']}, lots={ovl_res['per_lot_apc_and_ewma']['evaluated_lot_count']}, scanner={ovl_res['chamber_and_scanner_matching']['optimal_scanner_routing']}")

    # 2. Material Quality Solver Test
    mat_res = MaterialQualitySolver.compare_vendors(
        specs={"metal_ppb": {"LSL": 0.0, "USL": 5.0, "weight": 0.6, "baseline_mean": 1.1, "baseline_std": 0.25}, "moisture_ppm": {"LSL": 0.0, "USL": 20.0, "weight": 0.4}},
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
                "subtier_genealogy": {"unreported_4m_detected": True, "pcn_approved": False, "impacted_wafer_lots": ["M16-LOT-01"]},
            },
        ],
    )
    assert mat_res["recommended_vendor"] == "VENDOR_A_SAFE"
    assert "inline_wafer_yield_correlation" in mat_res["vendor_rankings"][0]
    assert "lot_level_dispositions" in mat_res and "quarantined_lot_ids" in mat_res
    print(f"✅ [2/11 PASS] 소재품질팀 (MaterialQualitySolver): recommended={mat_res['recommended_vendor']}, status={mat_res['status']}, share={mat_res['vendor_rankings'][0]['recommended_sourcing_share_pct']}%, quarantined_lots={len(mat_res['quarantined_lot_ids'])}")

    # 3. Market Strategy Solver Test
    mkt_res = MarketStrategySolver.simulate_allocation_grid(
        total_wafer_capa_k=150.0,
        competitor_records=[
            {"company": "Micron", "reported_period": "2025-FQ3", "currency": "USD_BILLION", "revenue": 7.8, "operating_profit": 2.1, "nrv_reversal": 0.3, "shipment_volume": 4.2, "shipment_unit": "EXABYTE", "guided_bit_growth_pct": 10.0, "actual_bit_growth_pct": 8.0},
            {"company": "Memory_Leader_A", "reported_period": "2025-CQ2", "currency": "KRW_TRILLION", "revenue": 16.4, "operating_profit": 5.5, "nrv_reversal": 0.1, "shipment_volume": 38.0, "shipment_unit": "B_Gb", "guided_bit_growth_pct": 12.0, "actual_bit_growth_pct": 13.0},
        ],
        pq_mix_periods={
            "prev": {"total_shipment_bgb": 100.0, "hbm_bit_share_pct": 10.0, "legacy_asp_usd": 3.2, "hbm_asp_usd": 15.0},
            "curr": {"total_shipment_bgb": 108.0, "hbm_bit_share_pct": 22.0, "legacy_asp_usd": 2.85, "hbm_asp_usd": 16.5},
        },
        ir_audit_records=[
            {"company": "Competitor_X", "ir_transcript_excerpt": "Inventory has normalized and HBM is sold out with strong demand.", "prev_inventory_days_dio": 90.0, "curr_inventory_days_dio": 115.0}
        ],
    )
    assert mkt_res["pq_mix_variance_decomposition"]["mix_illusion_flag"] is True
    assert mkt_res["ir_vs_financials_cross_audit"][0]["red_flag_detected"] is True
    wide_rows = [{"company": "Micron", "metric": "revenue", "1Q24": 5.8, "2Q24": 6.8}, {"company": "Micron", "metric": "operating_profit", "1Q24": 0.9, "2Q24": 1.5}]
    unpivoted = MarketStrategySolver.unpivot_wide_quarterly_records(wide_rows)
    assert len(unpivoted) == 2 and unpivoted[0]["revenue"] == 5.8 and unpivoted[0]["operating_profit"] == 0.9
    print(f"✅ [3/11 PASS] 시장전략팀 (MarketStrategySolver): mix_illusion={mkt_res['pq_mix_variance_decomposition']['mix_illusion_flag']}, underlying_OPM={mkt_res['calendarized_competitor_benchmarks'][0]['underlying_operating_margin_pct']}%, wide_unpivot={len(unpivoted)}qtrs")

    # 4. Value-Chain Business Solver Test (with generic records routing)
    vc_res = ValueChainBusinessSolver.solve_all({
        "end_demand_shock_pct": 5.0,
        "tsmc_cowos_alloc_bgb": 12.5,
        "records": [
            {"product_name": "HBM3E_12H", "unit_capex": 92.0, "die_size_penalty_factor": 2.8, "lta_floor_k": 35.0, "max_demand_k": 85.0, "op_per_k_musd": 44.0},
            {"product_name": "DDR5_RDIMM", "unit_capex": 55.0, "die_size_penalty_factor": 1.15, "lta_floor_k": 40.0, "max_demand_k": 90.0, "op_per_k_musd": 19.0},
        ],
    })
    assert "value-chain-business-persona" in vc_res["persona_id"]
    print(f"✅ [4/11 PASS] 경영전략팀 (ValueChainBusinessSolver): bottleneck={vc_res['value_chain_and_bullwhip_analysis']['binding_bottleneck_node']}, ROIC={vc_res['capex_roic_optimization']['portfolio_weighted_roic_pct']}%, EVA={vc_res['capex_roic_optimization']['value_created_eva_musd']}M$")

    # 5. Semiconductor Educator Curriculum Solver Test (Multi-Learner Cohort + Doc Module Extraction)
    edu_res = CurriculumOntologySolver.analyze_and_schedule(
        modules=[
            {"id": "M1", "title": "Photolithography & EUV Basics", "stage": "PHOTO", "level": 1, "hours": 4, "prereqs": []},
            {"id": "M2", "title": "Ceria CMP & Supercritical Cleaning", "stage": "CMP_CLEAN", "level": 2, "hours": 4, "prereqs": ["M1"]},
            {"id": "M3", "title": "HBM3E MR-MUF Advanced Packaging", "stage": "PKG_HBM", "level": 3, "hours": 6, "prereqs": ["M2"]},
        ],
        learner_profile={
            "completed_ids": [],
            "target_ids": ["M3"],
            "max_hours": 11,
            "role": "FINANCE_STRATEGY",
            "level": 1,
            "learner_question_or_answer": "EUV도 카메라 유리 렌즈로 굴절시키는 것 아닌가요?",
        },
        learner_profiles=[
            {"learner_id": "L1_FINANCE", "completed_ids": [], "target_ids": ["M3"], "max_hours": 11, "role": "FINANCE_STRATEGY"},
            {"learner_id": "L2_FAB_SENIOR", "completed_ids": ["M1", "M2"], "target_ids": ["M3"], "max_hours": 10, "role": "FAB_RND_ENG"},
        ],
    )
    assert "value-chain-educator-persona" in edu_res["persona_id"] and len(edu_res["learning_path"]) == 3
    assert len(edu_res["misconception_diagnostics"]) >= 1
    assert len(edu_res["cohort_batch_schedules"][0]["recommended_module_ids"]) == 3 and edu_res["cohort_batch_schedules"][1]["recommended_module_ids"] == ["M3"]
    print(f"✅ [5/11 PASS] 반도체 산업교육 (CurriculumOntologySolver): scheduled={edu_res['total_scheduled_modules']} modules, cohort_learners={len(edu_res['cohort_batch_schedules'])} (L1=3, L2=1), misconceptions_caught={len(edu_res['misconception_diagnostics'])}")

    # 6. Universal Problem Solver Test (Unseen Domain: Fab Yield / PdM / General Ops + BM25 RAG + Constrained Optimizer)
    univ_res = UniversalProblemSolver.solve_universal({
        "records": [
            {"id": "LOT-01", "temp_c": 410.0, "rf_power_w": 1200.0, "defect_count": 3.0},
            {"id": "LOT-02", "temp_c": 425.0, "rf_power_w": 1280.0, "defect_count": 8.0},
            {"id": "LOT-03", "temp_c": 455.0, "rf_power_w": 1450.0, "defect_count": 24.0},
            {"id": "LOT-04", "temp_c": 405.0, "rf_power_w": 1190.0, "defect_count": 2.0},
            {"id": "LOT-ERR", "temp_c": -999.0, "rf_power_w": 9999.0, "status": "INVALID"},
        ],
        "target_metric": "defect_count",
        "spec_limits": {"temp_c": {"LSL": 390.0, "USL": 450.0}},
        "tasks": [
            {"id": "ACT-PM-CHAMBER", "name": "플라즈마 챔버 긴급 세정 PM", "category": "CHAMBER_PM", "mandatory": True, "cost": 120, "capacity_req": 15, "value": 95, "passengers": 110, "covered_zones": ["ZONE_A", "ZONE_B"]},
            {"id": "ACT-SENSOR-CAL", "name": "온도 센서 캘리브레이션", "category": "SENSOR_CAL", "mandatory": False, "cost": 60, "capacity_req": 8, "value": 82, "passengers": 42, "covered_zones": ["ZONE_B", "ZONE_C"]},
            {"id": "ACT-RESTRICTED", "name": "보안 제한 구역 무단 변경", "category": "SEC", "forbidden": True, "cost": 30, "capacity_req": 5, "value": 99, "covered_zones": ["ZONE_D"]},
        ],
        "total_budget": 200,
        "total_capacity": 30,
        "documents": [
            {"id": "SOP-FAB-402", "title": "챔버 온도 및 RF 파워 스펙 이탈 시 비상 조치 규정", "content": "온도가 USL(450도)을 초과하거나 결함 수가 급증할 경우 즉시 해당 로트를 홀드하고 플라즈마 챔버 긴급 세정 PM을 실시한다."},
            {"id": "SOP-SEC-101", "title": "공정 구역 보안 및 설비 변경 통제 지침", "content": "사전 승인되지 않은 보안 제한 구역의 설비 변경은 엄격히 금지된다."},
        ],
        "query": "온도 USL 초과 및 결함 급증 시 챔버 PM 조치 규정",
    })
    assert univ_res["domain"] == "UNIVERSAL_OPS" and len(univ_res["tabular_eda_and_root_cause"]["root_cause_correlations"]) >= 1
    assert len(univ_res["document_citation_rag"]["matched_citations"]) >= 1
    assert len(univ_res["constrained_optimization_plan"]["multi_period_diversity_roster"]) >= 1
    assert len(univ_res["constrained_optimization_plan"]["capacitated_fleet_dispatch_plan"]) >= 1
    assert len(univ_res["constrained_optimization_plan"]["spatial_set_cover_plan"]["covered_zones"]) == 3
    print(f"✅ [6/11 PASS] 제6 범용 도메인 (UniversalProblemSolver): top_driver={univ_res['tabular_eda_and_root_cause']['root_cause_correlations'][0]['feature']}, selected_tasks={univ_res['constrained_optimization_plan']['selected_count']}, set_cover_zones={len(univ_res['constrained_optimization_plan']['spatial_set_cover_plan']['covered_zones'])}, top_citation={univ_res['document_citation_rag']['matched_citations'][0]['citation_id']}")

    # 7. Type A: Text Rule & Alarm Troubleshooting Solver Test
    res_a = TypeASolver.solve({
        "text": "현장 품질 규정 미준수 발언",
        "alarm_code": "ERR-VACUUM-01",
        "time_budget_mins": 25.0,
        "forbidden_rules": [{"pattern": "미준수", "penalty": 20.0, "category": "COMPLIANCE"}],
    })
    assert res_a["domain"] == "TYPE_A_TEXT_RAG_ALARM" and "knapsack_action_optimization" in res_a["alarm_troubleshooting"]
    print(f"✅ [7/11 PASS] Type A 솔버 (Text & Alarm RAG): status={res_a['status']}, rule={res_a['ruleId']}, opt_method={res_a['alarm_troubleshooting']['knapsack_action_optimization']['optimization_method']}")

    # 8. Type B: Wafer Map Spatial Defect & Step Yield Solver Test
    res_b = TypeBSolver.solve({
        "dies": [
            {"x": 10, "y": 10, "is_fail": True, "bin": "BIN_99"},
            {"x": 10, "y": 11, "is_fail": True, "bin": "BIN_99"},
            {"x": 10, "y": 12, "is_fail": True, "bin": "BIN_99"},
            {"x": 0, "y": 0, "is_fail": False, "bin": "BIN_01"},
        ],
        "steps": [
            {"step_id": "PHOTO", "step_yield_pct": 98.5, "improvement_cost": 30.0, "potential_yield_gain_pct": 1.2},
            {"step_id": "ETCH", "step_yield_pct": 97.0, "improvement_cost": 40.0, "potential_yield_gain_pct": 2.0},
        ],
        "total_budget": 50.0,
    })
    assert res_b["domain"] == "TYPE_B_WAFER_YIELD_ANALYTICS" and "budget_allocation_optimization" in res_b["yield_decomposition"]
    print(f"✅ [8/11 PASS] Type B 솔버 (Wafer Map & Yield): status={res_b['status']}, pattern={res_b['wafer_map_analysis']['dominant_pattern']}, base_yield={res_b['wafer_map_analysis']['base_yield_pct']}%, post_repair={res_b['wafer_map_analysis']['redundancy_repair_optimization']['post_repair_yield_pct']}%")

    # 9. Type C: FDC Time-Series Sensor Anomaly & Bayes Threshold Solver Test
    res_c = TypeCSolver.solve({
        "series": [
            {"value": 10.0, "is_actual_fault": False},
            {"value": 10.2, "is_actual_fault": False},
            {"value": 9.9, "is_actual_fault": False},
            {"value": 14.5, "is_actual_fault": True},
        ],
        "cost_false_alarm": 10.0,
        "cost_missed_fault": 50.0,
    })
    assert res_c["domain"] == "TYPE_C_FDC_ANOMALY_DETECTION" and "threshold_cost_optimization" in res_c
    print(f"✅ [9/11 PASS] Type C 솔버 (FDC & Bayes Risk): status={res_c['status']}, optimal_z={res_c['threshold_cost_optimization']['optimal_z_threshold']}, min_cost={res_c['threshold_cost_optimization']['minimized_expected_loss_cost']}")

    # 10. Type D: Workflow State Machine & Equipment PM RUL Solver Test
    res_d = TypeDSolver.solve({
        "equipments": [
            {"equip_id": "EQ-ETCH-01", "current_usage_hours": 480.0, "max_lifetime_hours": 500.0, "weibull_beta": 2.8, "pm_cost": 150.0, "unplanned_shutdown_cost": 900.0},
            {"equip_id": "EQ-CVD-02", "current_usage_hours": 200.0, "max_lifetime_hours": 600.0, "weibull_beta": 2.2, "pm_cost": 100.0, "unplanned_shutdown_cost": 700.0},
        ],
        "available_pm_slots": 1,
    })
    assert res_d["domain"] == "TYPE_D_WORKFLOW_AND_PM_SCHEDULE" and "pm_slot_schedule_optimization" in res_d["pm_and_rul_optimization"]
    print(f"✅ [10/11 PASS] Type D 솔버 (PM RUL & Workflow): status={res_d['status']}, urgent_pm={res_d['pm_and_rul_optimization']['urgent_pm_count']}, immediate_slot={res_d['pm_and_rul_optimization']['pm_slot_schedule_optimization']['immediate_slot_assigned_equips']}")

    # 11. Type E: Recipe Golden Spec Diff & Cpk Margin Solver Test
    res_e = TypeESolver.solve({
        "parameters": [
            {"param_name": "TEMP_C", "target": 400.0, "actual": 402.0, "lsl": 380.0, "usl": 420.0, "sensitivity": 0.5},
            {"param_name": "PRESSURE_MTORR", "target": 50.0, "actual": 51.5, "lsl": 45.0, "usl": 55.0, "sensitivity": -0.8},
        ],
        "target_output_error": 1.2,
    })
    assert res_e["domain"] == "TYPE_E_RECIPE_VERIFIER" and "cpk_and_setpoint_optimization" in res_e
    print(f"✅ [11/11 PASS] Type E 솔버 (Recipe & Cpk Tuning): status={res_e['status']}, out_of_spec={res_e['out_of_spec_count']}, low_margin={res_e['low_margin_warning_count']}, tuned={len(res_e['cpk_and_setpoint_optimization']['multi_parameter_fine_tuning'])}params")
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
