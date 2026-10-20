#!/usr/bin/env python3
"""Independently audit the Stage27a three-case CPD2 pilot."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STUDY = "stage27a_stage26x_mechanics_hydraulic_bridge_20260823"
CONFIG = ROOT / "stage27_designs" / STUDY / "geometry_01/resolved_config.json"
GEOMETRY_COMPLETION = CONFIG.parent / "completion.json"
RUN = ROOT / "stage27_runs" / STUDY / "gpu_pilot_01"
OUTPUT = ROOT / "stage27_evaluations" / STUDY / "evaluation_01"
RUNNER = ROOT / "stage27_staging/run_stage27a_mechanics_hydraulic_cpd2_v1.py"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    config = load(CONFIG)
    geometry = load(GEOMETRY_COMPLETION)
    completion_path = RUN / "completion.json"
    completion = load(completion_path)
    checks = {
        "config_binding": digest(CONFIG) == completion["config_sha256"],
        "geometry_binding": digest(GEOMETRY_COMPLETION) == completion["geometry_completion_sha256"],
        "runner_binding": digest(RUNNER) == completion["runner_sha256"],
        "upstream_passed": bool(geometry.get("passed") and completion.get("passed")),
        "upstream_checks": all(geometry.get("checks", {}).values()) and all(completion.get("checks", {}).values()),
        "qualified_gpu": completion["environment"]["gpu"]["ptx_sha256"] == config["lineage"]["qualified_ptx_sha256"],
    }
    expected = {row["case_id"]: row for row in completion["paired_results"]}
    audits = []
    recomputed = {}
    for case_id in ("clean", "open", "constricted"):
        row = expected[case_id]
        case_dir = RUN / row["solver_case_id"]
        record_path = case_dir / "record.json"
        record = load(record_path)
        artifact_checks = {
            key: digest(case_dir / filename) == record["artifacts"][key]
            for key, filename in {
                "audit_npz_sha256": "audit.npz",
                "final_fields_npz_sha256": "final_fields.npz",
                "final_shifted_state_npz_sha256": "final_shifted_state.npz",
                "final_flow_vtk_sha256": "final_flow.vtk",
            }.items()
        }
        conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
        ratio = conductance / float(expected["clean"]["conductance_proxy_lu"])
        with np.load(case_dir / "audit.npz", allow_pickle=False) as audit:
            finite_audit = all(np.all(np.isfinite(audit[name])) for name in audit.files)
            terminal_step = int(audit["step"][-1])
        local = {
            "record_hash": digest(record_path) == completion["case_records"][case_id] == row["record_sha256"],
            "record_passed": bool(record.get("passed") and record.get("converged") and all(record.get("checks", {}).values())),
            "artifact_hashes": all(artifact_checks.values()),
            "finite_audit": finite_audit,
            "terminal_step_binding": terminal_step == int(record["steps_completed"]) == int(row["steps_completed"]),
            "conductance_recomputed": math.isclose(conductance, float(row["conductance_proxy_lu"]), rel_tol=0.0, abs_tol=1e-14),
            "ratio_recomputed": math.isclose(ratio, float(row["paired_permeability_ratio"]), rel_tol=0.0, abs_tol=1e-14),
            "fatal_health_zero": int(record["numerical_health"]["fatal_sticky_code"]) == 0,
        }
        audits.append({"case_id": case_id, "record_sha256": digest(record_path), "artifact_checks": artifact_checks, "checks": local, "passed": all(local.values())})
        recomputed[case_id] = {"conductance_proxy_lu": conductance, "paired_permeability_ratio": ratio}
    checks["all_case_audits"] = all(row["passed"] for row in audits)
    ratios = {key: recomputed[key]["paired_permeability_ratio"] for key in recomputed}
    contrast = ratios["constricted"] - ratios["open"]
    ordering = ratios["constricted"] < ratios["open"] < ratios["clean"]
    checks["obstruction_order_reproduced"] = ordering
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    evaluation = {
        "schema": "lbs.stage27a-stage26x-mechanics-hydraulic-evaluation.v1",
        "status": "independently_verified_cpd2_small_obstruction_contrast" if passed else "independent_evaluation_failed",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "cpd2_detected_small_location_dependent_obstruction" if ordering else "cpd2_obstruction_order_not_detected",
        "claim_boundary": config["claim_boundary"],
        "checks": checks,
        "case_audits": audits,
        "metrics": {
            "clean_intrinsic_permeability_m2": float(expected["clean"]["intrinsic_permeability_m2"]),
            "open_paired_ratio": ratios["open"],
            "open_relative_change_percent": 100.0 * (ratios["open"] - 1.0),
            "constricted_paired_ratio": ratios["constricted"],
            "constricted_relative_change_percent": 100.0 * (ratios["constricted"] - 1.0),
            "constricted_minus_open_ratio": contrast,
            "constricted_minus_open_percentage_points": 100.0 * contrast,
            "fibre_voxel_difference_constricted_minus_open": int(next(x for x in config["geometry"]["cases"] if x["case_id"] == "constricted")["fibre_only_voxel_count"] - next(x for x in config["geometry"]["cases"] if x["case_id"] == "open")["fibre_only_voxel_count"]),
        },
        "interpretation": "At CPD2, one contact-deflected fibre obstructs flow slightly more than the equal-volume open-path fibre. The effect is a numerical small-cell placement contrast, not yet solution-verified at CPD4 and not a concentration law.",
        "source_bindings": {
            "config": {"path": str(CONFIG), "sha256": digest(CONFIG)},
            "geometry_completion": {"path": str(GEOMETRY_COMPLETION), "sha256": digest(GEOMETRY_COMPLETION)},
            "run_completion": {"path": str(completion_path), "sha256": digest(completion_path)},
            "runner": {"path": str(RUNNER), "sha256": digest(RUNNER)},
            "evaluator": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())},
        },
        "authority": {
            "render": passed,
            "cpd4_confirmation_design": passed,
            "cpd4_execution": False,
            "concentration_campaign": False,
            "physical_permeability_validation": False,
            "mobile_sand": False,
            "two_way_coupling": False,
        },
    }
    evaluation_path = OUTPUT / "evaluation.json"
    write(evaluation_path, evaluation)
    checkpoint = {
        "schema": evaluation["schema"] + ".checkpoint",
        "status": "render_and_cpd4_design_authorized" if passed else "fail_closed",
        "passed": passed,
        "evaluation": {"path": str(evaluation_path), "sha256": digest(evaluation_path)},
        "next_handoff": {"authorized": "render the CPD2 result and design a three-case CPD4 confirmation", "not_authorized": "CPD4 execution, concentration campaign, physical permeability claim, mobile mechanics or two-way coupling"},
    }
    checkpoint_path = OUTPUT / "checkpoint_manifest.json"
    write(checkpoint_path, checkpoint)
    print(json.dumps({"passed": passed, "evaluation": str(evaluation_path), "evaluation_sha256": digest(evaluation_path), "checkpoint": str(checkpoint_path), "checkpoint_sha256": digest(checkpoint_path), "metrics": evaluation["metrics"]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())

