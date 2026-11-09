#!/usr/bin/env python3
"""
Domain Solver 4: Semiconductor Value-Chain Ontology & Adaptive Curriculum Engine

"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Set


class CurriculumOntologySolver:
    @staticmethod
    def analyze_and_schedule(
        modules: List[Dict[str, Any]],
        learner_profile: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        modules: [{"id": "M1", "title": "...", "stage": "Photo", "level": 2, "hours": 4, "prereqs": ["M0"]}, ...]
        learner_profile: {"completed_ids": ["M0"], "target_ids": ["M5", "M6"], "max_hours": 40}
        """
        learner_profile = learner_profile or {}
        completed: Set[str] = set(learner_profile.get("completed_ids", []))
        targets: Set[str] = set(learner_profile.get("target_ids", [m["id"] for m in modules]))
        max_hours = float(learner_profile.get("max_hours", 9999.0))

        mod_map = {m["id"]: m for m in modules}

        # 1. Backtrack from target_ids to find all required prerequisite nodes
        required_nodes: Set[str] = set()
        stack = list(targets)
        while stack:
            curr = stack.pop()
            if curr in completed or curr not in mod_map:
                continue
            if curr not in required_nodes:
                required_nodes.add(curr)
                for pre in mod_map[curr].get("prereqs", []):
                    if pre not in completed:
                        stack.append(pre)

        # 2. Kahn's Algorithm for Topological Sort on required subgraph
        in_degree = {nid: 0 for nid in required_nodes}
        adj = {nid: [] for nid in required_nodes}

        for nid in required_nodes:
            for pre in mod_map[nid].get("prereqs", []):
                if pre in required_nodes:
                    adj[pre].append(nid)
                    in_degree[nid] += 1

        queue = sorted(
            [nid for nid, deg in in_degree.items() if deg == 0],
            key=lambda x: (mod_map[x].get("level", 1), x),
        )
        ordered_ids = []

        while queue:
            curr = queue.pop(0)
            ordered_ids.append(curr)
            for nxt in adj[curr]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
                    queue.sort(key=lambda x: (mod_map[x].get("level", 1), x))

        cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
        cum_hours = 0.0
        scheduled_modules = []
        deferred_modules = []

        for nid in ordered_ids:
            m = mod_map[nid]
            h = float(m.get("hours", 0.0))
            if cum_hours + h <= max_hours:
                cum_hours += h
                scheduled_modules.append(m)
            else:
                deferred_modules.append(m)

        return {
            "is_valid_dag": len(cycle_nodes) == 0,
            "cycle_detected_ids": cycle_nodes,
            "total_scheduled_modules": len(scheduled_modules),
            "total_scheduled_hours": round(cum_hours, 2),
            "budget_max_hours": max_hours,
            "learning_path": scheduled_modules,
            "deferred_due_to_time_cap": deferred_modules,
        }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        out = CurriculumOntologySolver.analyze_and_schedule(
            modules=payload.get("modules", []),
            learner_profile=payload.get("learner_profile", {}),
        )
        Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")