#!/usr/bin/env python3
"""Independently evaluate the immutable Stage26u throat-screen bundle."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN = ROOT / "stage26_designs" / "stage26u_three_grain_throat_20260820" / "throat_design_01" / "config.json"
RUN = ROOT / "stage26_runs" / "stage26u_three_grain_throat_20260820" / "throat_01"
SUPERVISOR = ROOT / "stage26_supervisors" / "stage26u_three_grain_throat_20260820" / "throat_01"
OUT = ROOT / "stage26_evaluations" / "stage26u_three_grain_throat_20260820" / "throat_evaluation_01"
RUNNER = ROOT / "stage26_staging" / "run_stage26u_three_grain_throat_v1.py"
CONTRACT = ROOT / "stage26_staging" / "STAGE26U_THREE_GRAIN_THROAT_RESEARCH_CONTRACT.md"
STAGE26T = ROOT / "stage26_evaluations" / "stage26t_sand_fibre_contact_20260820" / "contact_evaluation_01" / "checkpoint_manifest.json"
STAGE26S = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_evaluation_03" / "checkpoint_manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def close(a, b, atol=1e-14, rtol=1e-10):
    return math.isclose(float(a), float(b), abs_tol=atol, rel_tol=rtol)


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable evaluation {OUT}")
required = [DESIGN, RUNNER, CONTRACT, STAGE26T, STAGE26S, RUN / "result.json",
            RUN / "completion.json", SUPERVISOR / "launch_manifest.txt",
            SUPERVISOR / "runner_exit_code.txt"]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise RuntimeError("missing evidence: " + ", ".join(missing))

config = load(DESIGN)
result = load(RUN / "result.json")
completion = load(RUN / "completion.json")
launch = {}
for line in (SUPERVISOR / "launch_manifest.txt").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        launch[key] = value

checks = {}
checks["supervisor_exit_zero"] = (SUPERVISOR / "runner_exit_code.txt").read_text().strip() == "0"
checks["completion_result_binding"] = completion.get("result", {}).get("sha256") == sha(RUN / "result.json")
checks["completion_passed"] = completion.get("passed") is True and result.get("passed") is True
checks["design_runner_binding"] = config["source_hashes"]["runner"] == sha(RUNNER) == result["source_hashes"]["runner"]
checks["design_config_binding"] = sha(DESIGN) == result["source_hashes"]["config"] == launch.get("config_sha256")
checks["launch_runner_binding"] = launch.get("runner_sha256") == sha(RUNNER)
checks["contract_binding"] = config["source_hashes"]["contract"] == sha(CONTRACT)
checks["stage26t_binding"] = config["source_hashes"]["stage26t_checkpoint"] == sha(STAGE26T)
checks["stage26s_binding"] = config["source_hashes"]["stage26s_checkpoint"] == sha(STAGE26S)
checks["authority_boundary"] = (
    config["authority"].get("three_grain_throat_execution_authorized") is True
    and config["authority"].get("full_216_grain_integration_authorized") is False
    and config["authority"].get("flow_authorized") is False
    and config["authority"].get("permeability_claim_authorized") is False
)

case_audits = []
records = []
for aggregate in result["cases"]:
    case_id = aggregate["case_id"]
    record_path = RUN / f"{case_id}_result.json"
    history_path = RUN / f"{case_id}_history.csv"
    case_checks = {
        "record_exists": record_path.is_file(),
        "history_exists": history_path.is_file(),
    }
    if not all(case_checks.values()):
        case_audits.append({"case_id": case_id, "checks": case_checks, "passed": False})
        continue
    record = load(record_path)
    records.append(record)
    case_checks["aggregate_record_hash"] = aggregate["result_artifact"]["sha256"] == sha(record_path)
    case_checks["history_hash"] = record["history"]["sha256"] == sha(history_path)
    case_checks["identity"] = record["case_id"] == case_id and close(
        record["throat_to_fibre_diameter_ratio"], aggregate["throat_to_fibre_diameter_ratio"])
    case_checks["analytical_aperture"] = record["analytical_throat_relative_error"] <= 1e-12
    centres = record["sphere_centres_m"]
    pair_distances = []
    for i in range(3):
        for j in range(i + 1, 3):
            pair_distances.append(math.sqrt(sum((centres[i][k] - centres[j][k]) ** 2 for k in range(3))))
    case_checks["three_spheres_tangent"] = all(close(distance, record["sand_diameter_m"]) for distance in pair_distances)
    with history_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    case_checks["history_nonempty"] = len(rows) >= 10
    case_checks["terminal_history_binding"] = bool(rows) and close(
        rows[-1]["leading_node_advance_m"], record["terminal_leading_node_advance_m"])
    case_checks["terminal_node_count_binding"] = bool(rows) and int(rows[-1]["nodes_beyond_throat"]) == int(
        record["terminal_nodes_beyond_throat"])
    case_checks["finite_history"] = all(
        math.isfinite(float(row[key]))
        for row in rows
        for key in ("time_s", "leading_node_advance_m", "maximum_node_speed_m_s",
                    "maximum_penetration_over_fibre_radius", "maximum_transverse_centreline_displacement_m")
    )
    case_checks["bond_integrity"] = record["terminal_internal_real_bond_count"] == config["fibre"]["node_count"] - 1
    case_audits.append({"case_id": case_id, "checks": case_checks, "passed": all(case_checks.values()),
                        "record_sha256": sha(record_path), "history_sha256": sha(history_path)})

by_ratio = {round(item["throat_to_fibre_diameter_ratio"], 6): item for item in records}
if {0.8, 1.0}.issubset(by_ratio) and len(records) == 3:
    low = by_ratio[0.8]
    middle = by_ratio[1.0]
    high = max(records, key=lambda item: item["throat_to_fibre_diameter_ratio"])
    gates = config["gates"]
    independent_gates = {
        "analytical_geometry": all(item["analytical_throat_relative_error"] <= 1e-12 for item in records),
        "finite_and_bond_complete": all(item["terminal_internal_real_bond_count"] == config["fibre"]["node_count"] - 1 for item in records),
        "penetration_guard": all(item["maximum_penetration_over_fibre_radius"] <= gates["maximum_penetration_over_fibre_radius"] for item in records),
        "ratio_0p8_persistent_contact": low["minimum_terminal_contact_count"] >= 1,
        "ratio_0p8_no_node_passage": low["terminal_nodes_beyond_throat"] == 0,
        "ratio_0p8_advance_bounded": low["terminal_leading_node_advance_m"] <= gates["maximum_blocked_leading_advance_m"],
        "lbs_d50_no_contact": high["maximum_recorded_contact_count"] == 0,
        "lbs_d50_node_passage": high["terminal_nodes_beyond_throat"] >= gates["minimum_passable_nodes_beyond_throat"],
        "lbs_d50_advance": high["terminal_leading_node_advance_m"] >= gates["minimum_passable_leading_advance_m"],
        "passage_contrast": high["terminal_leading_node_advance_m"] - low["terminal_leading_node_advance_m"] >= gates["minimum_passage_contrast_m"],
    }
    classifications = {
        low["case_id"]: "blocked" if independent_gates["ratio_0p8_persistent_contact"] and independent_gates["ratio_0p8_no_node_passage"] else "not_blocked",
        middle["case_id"]: "marginal_transition_observation",
        high["case_id"]: "passable" if independent_gates["lbs_d50_no_contact"] and independent_gates["lbs_d50_node_passage"] else "not_passable",
    }
else:
    independent_gates = {"complete_case_set": False}
    classifications = {}

checks["all_case_artifacts"] = len(case_audits) == 3 and all(item["passed"] for item in case_audits)
checks["runner_checks_reproduced"] = independent_gates == result.get("checks")
checks["all_mechanism_gates"] = all(independent_gates.values())
passed = all(checks.values())

evaluation = {
    "schema": "lbs.stage26u-three-grain-throat-evaluation.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "status": "independently_verified" if passed else "not_qualified",
    "checks": checks,
    "independent_gates": independent_gates,
    "classifications": classifications,
    "case_audits": case_audits,
    "source_bindings": {
        "config": {"path": str(DESIGN), "sha256": sha(DESIGN)},
        "runner": {"path": str(RUNNER), "sha256": sha(RUNNER)},
        "result": {"path": str(RUN / "result.json"), "sha256": sha(RUN / "result.json")},
        "completion": {"path": str(RUN / "completion.json"), "sha256": sha(RUN / "completion.json")},
        "stage26t_checkpoint": {"path": str(STAGE26T), "sha256": sha(STAGE26T)},
        "stage26s_checkpoint": {"path": str(STAGE26S), "sha256": sha(STAGE26S)},
    },
    "authority": {
        "render_verified_throat_screen": passed,
        "full_216_grain_integration_authorized": False,
        "flow_authorized": False,
        "permeability_claim_authorized": False,
    },
    "claim_boundary": config["claim_boundary"],
}
OUT.mkdir(parents=True)
evaluation_path = OUT / "evaluation.json"
evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
checkpoint = {
    "schema": "lbs.stage26u-three-grain-throat-checkpoint.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "status": evaluation["status"],
    "evaluation": {"path": str(evaluation_path), "sha256": sha(evaluation_path)},
    "classifications": classifications,
    "authority": evaluation["authority"],
    "claim_boundary": evaluation["claim_boundary"],
}
checkpoint_path = OUT / "checkpoint_manifest.json"
checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"evaluation": str(evaluation_path), "evaluation_sha256": sha(evaluation_path),
                  "checkpoint": str(checkpoint_path), "checkpoint_sha256": sha(checkpoint_path),
                  "passed": passed, "classifications": classifications}, indent=2))
raise SystemExit(0 if passed else 2)
