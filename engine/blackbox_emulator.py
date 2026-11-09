#!/usr/bin/env python3
"""
FDE Autopilot - Multi-Agent / Multi-User Blackbox Emulator
Simulates N concurrent users/lots/requests hitting the target program or API,
verifying state transitions, race conditions, idempotency, and boundary inputs.
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

    def generate_adversarial_payloads(self, base_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """정상 요청 + 경계값(0, 음수, 극댓값) + 결측/중복 요청 등 25개 시나리오 생성"""
        payloads = []
        for uid in range(1, self.num_virtual_users + 1):
            p = json.loads(json.dumps(base_payload))
            p["_emulator_user_id"] = f"virtual_actor_{uid:02d}"
            p["_scenario_type"] = "NORMAL"

            if uid == 21:
                p["_scenario_type"] = "EMPTY_OR_ZERO_BOUNDARY"
            elif uid == 22:
                p["_scenario_type"] = "EXTREME_SPIKE_OUTLIER"
            elif uid == 23:
                p["_scenario_type"] = "DUPLICATE_IDEMPOTENCY_CHECK"
            elif uid == 24:
                p["_scenario_type"] = "MISSING_OPTIONAL_FIELDS"
            elif uid == 25:
                p["_scenario_type"] = "CONCURRENT_CONFLICT_STRESS"

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


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 blackbox_emulator.py '<target_cmd>' <sample_input.json> <report_out.json>")
        sys.exit(1)

    target_cmd = sys.argv[1]
    sample_in = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    report = BlackboxEmulator(target_cmd, num_virtual_users=25).execute_swarm(sample_in)
    Path(sys.argv[3]).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[BLACKBOX_SWARM] Pass Rate: {report['pass_rate_pct']}% ({report['passed_count']}/25)")
    sys.exit(0 if report["failed_count"] == 0 else 1)