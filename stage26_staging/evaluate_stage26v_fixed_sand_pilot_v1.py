#!/usr/bin/env python3
"""Independently verify the Stage26v fixed-sand flexible-fibre pilot."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_designs" / "stage26v_216_flexible_fibre_integration_20260823" / "fixed_sand_design_01" / "config.json"
RUN = ROOT / "stage26_runs" / "stage26v_216_flexible_fibre_integration_20260823" / "fixed_sand_pilot_01"
SUP = ROOT / "stage26_supervisors" / "stage26v_216_flexible_fibre_integration_20260823" / "fixed_sand_pilot_01"
RUNNER = ROOT / "stage26_staging" / "run_stage26v_fixed_sand_flexible_pilot_v1.py"
GEOMETRY = ROOT / "stage26_runs" / "stage26v_216_flexible_fibre_integration_20260823" / "geometry_export_02" / "geometry.json"
OUT = ROOT / "stage26_evaluations" / "stage26v_216_flexible_fibre_integration_20260823" / "fixed_sand_evaluation_01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def close(a, b, atol=1e-14, rtol=1e-10):
    return math.isclose(float(a), float(b), abs_tol=atol, rel_tol=rtol)


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable evaluation {OUT}")
required = [CONFIG, RUNNER, GEOMETRY, RUN / "result.json", RUN / "completion.json",
            SUP / "launch_manifest.txt", SUP / "runner_exit_code.txt"]
if any(not path.is_file() for path in required):
    raise RuntimeError("required evidence missing")
config, result, completion = load(CONFIG), load(RUN / "result.json"), load(RUN / "completion.json")
launch = dict(line.split("=", 1) for line in (SUP / "launch_manifest.txt").read_text().splitlines() if "=" in line)
checks = {
    "supervisor_exit_zero": (SUP / "runner_exit_code.txt").read_text().strip() == "0",
    "completion_result_binding": completion["result"]["sha256"] == sha(RUN / "result.json"),
    "upstream_passed": completion.get("passed") is True and result.get("passed") is True,
    "config_binding": result["source_hashes"]["config"] == sha(CONFIG) == launch.get("config_sha256"),
    "runner_binding": result["source_hashes"]["runner"] == sha(RUNNER) == launch.get("runner_sha256") == config["source_hashes"]["runner"],
    "state_binding": result["source_hashes"]["source_state"] == config["source_hashes"]["source_state"],
    "geometry_binding": config["source_hashes"]["geometry"] == sha(GEOMETRY),
}
audits = []
records = {}
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
        "terminal_plane_binding": int(rows[-1]["nodes_beyond_classification_plane"]) == record["terminal_nodes_beyond_classification_plane"],
        "bond_integrity": record["terminal_internal_real_bond_count"] == config["fibre"]["node_count"] - 1,
        "finite_history": all(math.isfinite(float(row[key])) for row in rows for key in
                              ("time_s", "leading_node_advance_m", "maximum_node_speed_m_s",
                               "sum_contact_normal_force_n", "maximum_penetration_over_fibre_radius")),
    }
    audits.append({"case_id": case_id, "passed": all(case_checks.values()), "checks": case_checks,
                   "record_sha256": sha(record_path), "history_sha256": sha(history_path)})
    records[case_id] = record

constricted, open_case = records["constricted"], records["open"]
gates = config["gates"]
independent = {
    "finite_bond_complete": all(item["terminal_internal_real_bond_count"] == config["fibre"]["node_count"] - 1 for item in records.values()),
    "zero_load_hold_stable": all(item["maximum_hold_drift_m"] <= gates["maximum_hold_drift_m"] for item in records.values()),
    "fixed_sand_exact": all(item["maximum_fixed_sand_displacement_m"] == 0.0 for item in records.values()),
    "penetration_guard": all(item["maximum_penetration_over_fibre_radius"] <= gates["maximum_penetration_over_fibre_radius"] for item in records.values()),
    "open_no_contact": open_case["maximum_contact_normal_force_n"] == 0.0,
    "open_passage": open_case["terminal_nodes_beyond_classification_plane"] >= gates["minimum_open_nodes_beyond_plane"],
    "open_advance": open_case["terminal_leading_node_advance_m"] >= gates["minimum_open_advance_m"],
    "constricted_engagement": constricted["maximum_contact_normal_force_n"] > 0.0,
    "response_contrast": open_case["terminal_leading_node_advance_m"] - constricted["terminal_leading_node_advance_m"] >= gates["minimum_response_contrast_m"],
}
multi_cage = (constricted["maximum_simultaneous_distinct_contacted_sand_count"] >= 2 and
              constricted["minimum_terminal_contact_count"] >= 1 and
              constricted["terminal_nodes_beyond_classification_plane"] == 0 and
              constricted["terminal_leading_node_advance_m"] <= gates["maximum_caged_advance_m"])
classification = "multi_contact_caged" if multi_cage else (
    "contact_deflected_passage" if constricted["maximum_contact_normal_force_n"] > 0 and constricted["terminal_nodes_beyond_classification_plane"] > 0
    else "single_or_transient_obstacle_arrest" if constricted["maximum_contact_normal_force_n"] > 0 else "no_engagement")
checks["case_artifacts"] = len(audits) == 2 and all(item["passed"] for item in audits)
checks["runner_checks_reproduced"] = independent == result["checks"]
checks["classification_reproduced"] = classification == result["constricted_classification"] and multi_cage == result["multi_contact_cage_observed"]
passed = all(checks.values())
evaluation = {
    "schema": "lbs.stage26v-fixed-sand-flexible-pilot-evaluation.v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed, "status": "independently_verified" if passed else "not_qualified", "checks": checks,
    "independent_gates": independent, "case_audits": audits, "constricted_classification": classification,
    "multi_contact_cage_observed": multi_cage,
    "metrics": {"constricted_advance_m": constricted["terminal_leading_node_advance_m"],
                "open_advance_m": open_case["terminal_leading_node_advance_m"],
                "advance_contrast_m": open_case["terminal_leading_node_advance_m"] - constricted["terminal_leading_node_advance_m"],
                "constricted_maximum_contact_force_n": constricted["maximum_contact_normal_force_n"],
                "constricted_maximum_simultaneous_grains": constricted["maximum_simultaneous_distinct_contacted_sand_count"]},
    "source_bindings": {"config": {"path": str(CONFIG), "sha256": sha(CONFIG)},
                        "runner": {"path": str(RUNNER), "sha256": sha(RUNNER)},
                        "result": {"path": str(RUN / "result.json"), "sha256": sha(RUN / "result.json")},
                        "completion": {"path": str(RUN / "completion.json"), "sha256": sha(RUN / "completion.json")},
                        "geometry": {"path": str(GEOMETRY), "sha256": sha(GEOMETRY)}},
    "authority": {"render_authorized": passed, "mobile_sand_release_design_authorized": bool(passed and multi_cage),
                  "mobile_sand_execution_authorized": False, "flow_authorized": False, "permeability_claim_authorized": False},
    "claim_boundary": config["claim_boundary"],
}
OUT.mkdir(parents=True)
evaluation_path = OUT / "evaluation.json"
evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
checkpoint = {"schema": "lbs.stage26v-fixed-sand-flexible-pilot-checkpoint.v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "passed": passed, "status": evaluation["status"], "evaluation": {"path": str(evaluation_path), "sha256": sha(evaluation_path)},
              "constricted_classification": classification, "multi_contact_cage_observed": multi_cage,
              "authority": evaluation["authority"], "claim_boundary": evaluation["claim_boundary"]}
checkpoint_path = OUT / "checkpoint_manifest.json"
checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": passed, "classification": classification, "multi_contact_cage": multi_cage,
                  "evaluation": str(evaluation_path), "evaluation_sha256": sha(evaluation_path),
                  "checkpoint": str(checkpoint_path), "checkpoint_sha256": sha(checkpoint_path)}, indent=2))
raise SystemExit(0 if passed else 2)
