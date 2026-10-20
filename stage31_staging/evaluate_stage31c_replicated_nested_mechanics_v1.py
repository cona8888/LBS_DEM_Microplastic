#!/usr/bin/env python3
"""Independently evaluate the completed Stage31c replicated mechanics bundle."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage31_runs/stage31c_replicated_nested_mechanics_20260826/mechanics_01"
CONFIG = ROOT / "stage31_designs/stage31c_replicated_nested_mechanics_20260826/mechanics_preflight_01/config.json"
HANDOFF = ROOT / "stage31_evaluations/stage31c_replicated_nested_mechanics_20260826/mechanics_release_01/handoff.json"
RUNNER = ROOT / "stage31_staging/run_stage31c_replicated_nested_mechanics_v1.py"
OUTPUT = ROOT / "stage31_evaluations/stage31c_replicated_nested_mechanics_20260826/mechanics_evaluation_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value) -> bool:
    return math.isfinite(float(value))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable evaluation: {OUTPUT}")
    required = [CONFIG, HANDOFF, RUNNER, RUN / "result.json", RUN / "completion.json"]
    if any(not path.is_file() for path in required):
        raise RuntimeError("mechanics bundle is incomplete")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    result = json.loads((RUN / "result.json").read_text(encoding="utf-8"))
    completion = json.loads((RUN / "completion.json").read_text(encoding="utf-8"))
    acceptance = config["acceptance"]
    case_results = []
    record_checks = []
    for record in result["case_records"]:
        path = RUN / record["path"]
        record_hash = path.is_file() and sha(path) == record["sha256"]
        case = json.loads(path.read_text(encoding="utf-8")) if record_hash else {}
        history_path = RUN / case.get("history", {}).get("path", "missing")
        history_hash = history_path.is_file() and sha(history_path) == case.get("history", {}).get("sha256")
        history_finite = False
        if history_hash:
            with history_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            history_finite = bool(rows) and all(
                finite(row[key])
                for row in rows
                for key in ("time_s", "maximum_node_displacement_m", "maximum_node_speed_m_s", "maximum_penetration_over_fibre_radius")
            )
        checks = {
            "record_hash": record_hash,
            "history_hash": history_hash,
            "history_finite": history_finite,
            "four_terminal_fibres": len(case.get("terminal_fibres", [])) == 4,
            "nested_ranks_exact": [item.get("nested_rank") for item in case.get("terminal_fibres", [])] == [1, 2, 3, 4],
            "internal_bonds_complete": all(item.get("terminal_internal_real_bond_count") == int(acceptance["required_internal_bonds_per_fibre"]) for item in case.get("terminal_fibres", [])),
            "hold_stable": case.get("maximum_hold_drift_m", math.inf) <= float(acceptance["maximum_hold_drift_m"]) and case.get("maximum_hold_speed_m_s", math.inf) <= float(acceptance["maximum_hold_speed_m_s"]),
            "fixed_sand_exact": case.get("maximum_fixed_sand_displacement_m") == 0.0,
            "fixed_cell_exact": case.get("maximum_periodic_cell_change_m", math.inf) <= float(acceptance["maximum_cell_dimension_change_m"]),
            "penetration_guard": case.get("maximum_penetration_over_fibre_radius", math.inf) <= float(acceptance["maximum_penetration_over_fibre_radius"]),
            "zero_fibre_fibre_contacts": case.get("maximum_fibre_fibre_contact_count") == 0,
            "zero_cross_fibre_node_interactions": case.get("maximum_cross_fibre_node_real_interaction_count") == 0,
            "zero_intrafibre_grid_contacts": case.get("maximum_intrafibre_contact_count") == 0,
            "separation_margin_preserved": 2.0 * case.get("maximum_terminal_displacement_m", math.inf) < float(acceptance["minimum_initial_interfibre_surface_clearance_m"]),
        }
        record_checks.append({"case_id": record["case_id"], "passed": all(checks.values()), "checks": checks})
        case_results.append(case)
    expected_pairs = {(packing, block) for packing in ("n216_s1", "n216_s2", "n216_s3") for block in ("A", "B")}
    checks = {
        "config_hash": sha(CONFIG) == handoff["bindings"]["config_sha256"] == result["source_hashes"]["config"],
        "runner_hash": sha(RUNNER) == handoff["bindings"]["runner_sha256"] == result["source_hashes"]["runner"],
        "handoff_passed": handoff.get("passed") is True and handoff["authority"].get("mechanics_execution") is True,
        "execution_completed": result.get("passed") is True and completion.get("passed") is True,
        "completion_result_hash": completion.get("result", {}).get("sha256") == sha(RUN / "result.json"),
        "six_case_records": len(case_results) == int(acceptance["required_case_count"]) == 6,
        "complete_factorial_blocks": {(case.get("packing_id"), case.get("placement_block")) for case in case_results} == expected_pairs,
        "all_case_gates": len(record_checks) == 6 and all(item["passed"] for item in record_checks),
        "no_failure_marker": not (RUN / "failure.json").exists(),
        "flow_authority_closed": not any(result["authority"].get(name, False) for name in ("gpu_flow", "permeability_claim", "mobile_sand", "coupling")),
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage31c-replicated-nested-mechanics-evaluation.v1",
        "status": "passed_six_block_nested_mechanics" if passed else "failed_six_block_nested_mechanics",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "case_checks": record_checks,
        "summary": {
            "maximum_terminal_displacement_m": max((case.get("maximum_terminal_displacement_m", math.inf) for case in case_results), default=math.inf),
            "maximum_penetration_over_fibre_radius": max((case.get("maximum_penetration_over_fibre_radius", math.inf) for case in case_results), default=math.inf),
            "minimum_initial_interfibre_surface_clearance_m": acceptance["minimum_initial_interfibre_surface_clearance_m"],
        },
        "source_hashes": {"config": sha(CONFIG), "handoff": sha(HANDOFF), "runner": sha(RUNNER), "result": sha(RUN / "result.json"), "completion": sha(RUN / "completion.json")},
        "authority": {"terminal_geometry_design": passed, "gpu_flow": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
        "decision": "The six terminal four-fibre blocks may be transformed into nested 1/2/4 terminal geometry prefixes in a separate audited stage." if passed else "Mechanics evidence is not eligible for terminal geometry construction.",
        "claim_boundary": "Fixed-sand mechanics only; no hydraulic result or permeability inference.",
    }
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "evaluation.json").write_text(json.dumps(evaluation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "status": evaluation["status"], "passed": passed, "checks": checks, "summary": evaluation["summary"]}, indent=2))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
