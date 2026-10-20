#!/usr/bin/env python3
"""Independent evaluation of the Stage28b four-case CPD2 GPU pilot."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage28_runs/stage28b_two_fibre_cpd2_hydraulic_20260825/gpu_pilot_01"
COMPLETION = RUN / "completion.json"
CONFIG = ROOT / "stage28_designs/stage28b_two_fibre_cpd2_hydraulic_20260824/geometry_01/resolved_config.json"
HANDOFF = ROOT / "stage28_evaluations/stage28b_two_fibre_cpd2_hydraulic_20260824/gpu_release_audit_01/execution_handoff.json"
RUNNER = ROOT / "stage28_staging/run_stage28b_two_fibre_cpd2_gpu_v1.py"
STAGE27 = ROOT / "stage27_runs/stage27a_stage26x_mechanics_hydraulic_bridge_20260823/gpu_pilot_01/completion.json"
OUTPUT = ROOT / "stage28_evaluations/stage28b_two_fibre_cpd2_hydraulic_20260825/gpu_evaluation_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable evaluation: {OUTPUT}")
    completion, config, handoff, stage27 = map(load, (COMPLETION, CONFIG, HANDOFF, STAGE27))
    rows = {row["case_id"]: row for row in completion["paired_results"]}
    artifact_checks, record_checks = {}, {}
    names = {"audit_npz_sha256": "audit.npz", "final_fields_npz_sha256": "final_fields.npz",
             "final_flow_vtk_sha256": "final_flow.vtk", "final_shifted_state_npz_sha256": "final_shifted_state.npz"}
    for case_id, row in rows.items():
        case_dir = RUN / row["solver_case_id"]
        record_path = case_dir / "record.json"
        record = load(record_path)
        record_checks[case_id] = (sha(record_path) == row["record_sha256"]
                                  and record["passed"] and record["converged"]
                                  and all(record["checks"].values())
                                  and record["numerical_health"]["fatal_sticky_code"] == 0
                                  and record["final"]["momentum_residual_relative"] < 1e-6)
        for key, filename in names.items():
            artifact_checks[case_id + "_" + filename] = sha(case_dir / filename) == record["artifacts"][key]
    order = ["clean", "separated_open_open", "separated_open_constricted", "crossing_interaction"]
    clean27 = {row["case_id"]: row for row in stage27["paired_results"]}["clean"]
    separated_mean = 0.5 * (rows["separated_open_open"]["paired_permeability_ratio"]
                            + rows["separated_open_constricted"]["paired_permeability_ratio"])
    crossing_ratio = rows["crossing_interaction"]["paired_permeability_ratio"]
    checks = {
        "completion_passed": completion["passed"] and all(completion["checks"].values()),
        "config_handoff_runner_bound": completion["config_sha256"] == sha(CONFIG)
        and completion["handoff_sha256"] == sha(HANDOFF) and completion["runner_sha256"] == sha(RUNNER),
        "exact_four_ordered_cases": list(rows) == order,
        "all_records_independently_passed": all(record_checks.values()),
        "all_field_artifacts_bound": all(artifact_checks.values()),
        "all_cases_24000_steps": all(row["steps_completed"] == 24000 for row in rows.values()),
        "clean_reproduces_stage27_exactly": rows["clean"]["conductance_proxy_lu"] == clean27["conductance_proxy_lu"]
        and rows["clean"]["intrinsic_permeability_m2"] == clean27["intrinsic_permeability_m2"],
        "all_mixtures_reduce_permeability": all(rows[name]["paired_permeability_ratio"] < 1.0 for name in order[1:]),
        "crossing_has_largest_reduction": crossing_ratio < min(rows[name]["paired_permeability_ratio"] for name in order[1:3]),
        "authority_not_widened": completion["authority"]["cpd4"] is False
        and completion["authority"]["production_concentration_campaign"] is False
        and completion["authority"]["mobile_sand"] is False
        and completion["authority"]["two_way_coupling"] is False,
    }
    if not all(checks.values()):
        raise RuntimeError("Stage28b evaluation failed: " + ", ".join(k for k, v in checks.items() if not v))
    metrics = {
        "clean_intrinsic_permeability_m2": rows["clean"]["intrinsic_permeability_m2"],
        "relative_changes": {name: rows[name]["paired_relative_permeability_change"] for name in order[1:]},
        "relative_changes_percent": {name: 100 * rows[name]["paired_relative_permeability_change"] for name in order[1:]},
        "crossing_minus_separated_mean_ratio": crossing_ratio - separated_mean,
        "crossing_extra_reduction_vs_separated_mean_percentage_points": 100 * (crossing_ratio - separated_mean),
    }
    evaluation = {"schema": "lbs.stage28b-two-fibre-cpd2-gpu-evaluation.v1",
                  "status": "passed_cpd2_two_fibre_placement_mechanism_pilot", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                  "passed": True, "checks": checks, "record_checks": record_checks, "artifact_checks": artifact_checks,
                  "metrics": metrics,
                  "interpretation": "At fixed two-fibre mass and fixed sand, the face-adjacent crossing reduces CPD2 permeability more than either separated arrangement; this is a placement/contact mechanism result, not a concentration law.",
                  "bindings": {"completion_sha256": sha(COMPLETION), "config_sha256": sha(CONFIG),
                               "handoff_sha256": sha(HANDOFF), "runner_sha256": sha(RUNNER), "stage27_completion_sha256": sha(STAGE27)},
                  "authority": {"render": True, "bounded_cpd4_design": True, "cpd4_execution": False,
                                "production_concentration_campaign": False, "mobile_sand": False, "two_way_coupling": False},
                  "next_handoff": {"authorized": "render and design selected clean/separated-open-open/crossing CPD4 confirmation",
                                   "not_authorized": "CPD4 execution before independent release"}}
    OUTPUT.mkdir(parents=True)
    evaluation_path = OUTPUT / "evaluation.json"
    evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint = {"schema": "lbs.stage28b-two-fibre-cpd2-checkpoint.v1", "status": "cpd2_checkpoint_frozen", "passed": True,
                  "files": {str(path.relative_to(ROOT)): sha(path) for path in (COMPLETION, CONFIG, HANDOFF, RUNNER, evaluation_path)}}
    checkpoint_path = OUTPUT / "checkpoint_manifest.json"
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"evaluation": str(evaluation_path), "evaluation_sha256": sha(evaluation_path),
                      "checkpoint": str(checkpoint_path), "checkpoint_sha256": sha(checkpoint_path), "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
