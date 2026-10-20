#!/usr/bin/env python3
"""Independent Stage26x periodic fixed-sand pilot evaluation."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_design_02" / "config.json"
RUN = ROOT / "stage26_runs" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_pilot_02"
SUP = ROOT / "stage26_supervisors" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_pilot_02"
RUNNER = ROOT / "stage26_staging" / "run_stage26x_periodic_fixed_sand_fibre_v2.py"
NETWORK = ROOT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_04" / "network.json"
SEARCH = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "path_search_01" / "path_candidates.json"
OUT = ROOT / "stage26_evaluations" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_evaluation_01"
SCRIPT = Path(__file__).resolve()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def close(a, b):
    return math.isclose(float(a), float(b), abs_tol=1.0e-14, rel_tol=1.0e-10)


if OUT.exists():
    raise RuntimeError("immutable Stage26x evaluation exists")
required = [CONFIG, RUNNER, NETWORK, SEARCH, RUN / "result.json", RUN / "completion.json", SUP / "launch_manifest.txt", SUP / "runner_exit_code.txt"]
if any(not path.is_file() for path in required):
    raise RuntimeError("required Stage26x evidence missing")
config = load(CONFIG)
result = load(RUN / "result.json")
completion = load(RUN / "completion.json")
launch = dict(line.split("=", 1) for line in (SUP / "launch_manifest.txt").read_text(encoding="utf-8").splitlines() if "=" in line)
checks = {
    "supervisor_exit_zero": (SUP / "runner_exit_code.txt").read_text(encoding="utf-8").strip() == "0",
    "completion_result_binding": completion["result"]["sha256"] == sha(RUN / "result.json"),
    "upstream_passed": completion.get("passed") is True and result.get("passed") is True,
    "config_binding": result["source_hashes"]["config"] == sha(CONFIG) == launch.get("config_sha256"),
    "runner_binding": result["source_hashes"]["runner"] == sha(RUNNER) == launch.get("runner_sha256") == config["sources"]["runner"]["sha256"],
    "state_binding": result["source_hashes"]["source_state"] == config["sources"]["source_state"]["sha256"],
    "network_binding": config["sources"]["network"]["sha256"] == sha(NETWORK),
    "path_search_binding": config["sources"]["path_search"]["sha256"] == sha(SEARCH),
}
records = {}
case_audits = []
for aggregate in result["cases"]:
    case_id = aggregate["case_id"]
    record_path = RUN / f"{case_id}_result.json"
    history_path = RUN / f"{case_id}_history.csv"
    record = load(record_path)
    with history_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    case_checks = {
        "record_hash": aggregate["result_artifact"]["sha256"] == sha(record_path),
        "history_hash": record["history"]["sha256"] == sha(history_path),
        "history_nonempty": len(rows) >= 10,
        "terminal_advance_binding": close(rows[-1]["leading_node_advance_m"], record["terminal_leading_node_advance_m"]),
        "terminal_plane_binding": int(rows[-1]["nodes_beyond_classification_plane"]) == int(record["terminal_nodes_beyond_classification_plane"]),
        "bond_integrity": int(record["terminal_internal_real_bond_count"]) == int(config["fibre"]["node_count"]) - 1,
        "fixed_sand": float(record["maximum_fixed_sand_displacement_m"]) == 0.0,
        "fixed_cell": float(record["maximum_periodic_cell_change_m"]) == 0.0,
        "finite_history": all(math.isfinite(float(row[key])) for row in rows for key in ("time_s", "leading_node_advance_m", "maximum_node_speed_m_s", "sum_contact_normal_force_n", "maximum_penetration_over_fibre_radius")),
    }
    case_audits.append({"case_id": case_id, "passed": all(case_checks.values()), "checks": case_checks, "record_sha256": sha(record_path), "history_sha256": sha(history_path)})
    records[case_id] = record
constricted = records["constricted"]
open_case = records["open"]
gates = config["gates"]
independent = {
    "finite_bond_complete": all(item["terminal_internal_real_bond_count"] == config["fibre"]["node_count"] - 1 for item in records.values()),
    "zero_load_hold_stable": all(item["maximum_hold_drift_m"] <= gates["maximum_hold_drift_m"] for item in records.values()),
    "fixed_sand_exact": all(item["maximum_fixed_sand_displacement_m"] == 0.0 for item in records.values()),
    "fixed_periodic_cell_exact": all(item["maximum_periodic_cell_change_m"] <= 1.0e-15 for item in records.values()),
    "penetration_guard": all(item["maximum_penetration_over_fibre_radius"] <= gates["maximum_penetration_over_fibre_radius"] for item in records.values()),
    "open_no_contact": open_case["maximum_contact_normal_force_n"] == 0.0,
    "open_passage": open_case["terminal_nodes_beyond_classification_plane"] >= gates["minimum_open_nodes_beyond_plane"],
    "open_advance": open_case["terminal_leading_node_advance_m"] >= gates["minimum_open_advance_m"],
    "constricted_engagement": constricted["maximum_contact_normal_force_n"] > 0.0,
    "response_contrast": open_case["terminal_leading_node_advance_m"] - constricted["terminal_leading_node_advance_m"] >= gates["minimum_response_contrast_m"],
}
multi_cage = (
    constricted["maximum_simultaneous_distinct_contacted_sand_count"] >= 2
    and constricted["minimum_terminal_contact_count"] >= 1
    and constricted["terminal_nodes_beyond_classification_plane"] == 0
    and constricted["terminal_leading_node_advance_m"] <= gates["maximum_caged_advance_m"]
)
classification = "multi_contact_caged" if multi_cage else ("contact_deflected_passage" if constricted["maximum_contact_normal_force_n"] > 0 and constricted["terminal_nodes_beyond_classification_plane"] > 0 else "single_or_transient_obstacle_arrest" if constricted["maximum_contact_normal_force_n"] > 0 else "no_engagement")
checks["case_artifacts"] = len(case_audits) == 2 and all(item["passed"] for item in case_audits)
checks["runner_checks_reproduced"] = independent == result["checks"]
checks["classification_reproduced"] = classification == result["constricted_classification"] and multi_cage == result["multi_contact_cage_observed"]
passed = all(checks.values())
evaluation = {
    "schema": "lbs.stage26x-periodic-fixed-sand-evaluation.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "status": "independently_verified" if passed else "not_qualified",
    "checks": checks,
    "independent_gates": independent,
    "case_audits": case_audits,
    "constricted_classification": classification,
    "multi_contact_cage_observed": multi_cage,
    "metrics": {
        "constricted_advance_m": constricted["terminal_leading_node_advance_m"],
        "open_advance_m": open_case["terminal_leading_node_advance_m"],
        "advance_contrast_m": open_case["terminal_leading_node_advance_m"] - constricted["terminal_leading_node_advance_m"],
        "constricted_maximum_contact_force_n": constricted["maximum_contact_normal_force_n"],
        "constricted_maximum_simultaneous_grains": constricted["maximum_simultaneous_distinct_contacted_sand_count"],
        "minimum_periodic_throat_to_fibre_radius_ratio": load(SEARCH)["candidates"][0]["throat_to_fibre_radius_ratio"],
    },
    "source_bindings": {
        "config": {"path": str(CONFIG), "sha256": sha(CONFIG)},
        "runner": {"path": str(RUNNER), "sha256": sha(RUNNER)},
        "result": {"path": str(RUN / "result.json"), "sha256": sha(RUN / "result.json")},
        "completion": {"path": str(RUN / "completion.json"), "sha256": sha(RUN / "completion.json")},
        "network": {"path": str(NETWORK), "sha256": sha(NETWORK)},
        "path_search": {"path": str(SEARCH), "sha256": sha(SEARCH)},
        "evaluator": {"path": str(SCRIPT), "sha256": sha(SCRIPT)},
    },
    "authority": {"render_authorized": passed, "mobile_sand_release_design_authorized": bool(passed and multi_cage), "mobile_sand_execution_authorized": False, "flow_authorized": False, "permeability_claim_authorized": False},
    "claim_boundary": config["claim_boundary"],
}
OUT.mkdir(parents=True, exist_ok=False)
evaluation_path = OUT / "evaluation.json"
evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
checkpoint = {
    "schema": "lbs.stage26x-periodic-fixed-sand-checkpoint.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "status": evaluation["status"],
    "evaluation": {"path": str(evaluation_path), "sha256": sha(evaluation_path)},
    "constricted_classification": classification,
    "multi_contact_cage_observed": multi_cage,
    "authority": evaluation["authority"],
    "claim_boundary": evaluation["claim_boundary"],
}
checkpoint_path = OUT / "checkpoint_manifest.json"
checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": passed, "classification": classification, "multi_contact_cage": multi_cage, "evaluation": str(evaluation_path), "evaluation_sha256": sha(evaluation_path), "checkpoint": str(checkpoint_path), "checkpoint_sha256": sha(checkpoint_path)}, indent=2))
raise SystemExit(0 if passed else 2)
