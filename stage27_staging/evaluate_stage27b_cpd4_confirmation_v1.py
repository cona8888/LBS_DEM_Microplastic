#!/usr/bin/env python3
"""Independently audit the immutable Stage27b three-case CPD4 confirmation."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STUDY = "stage27b_stage26x_mechanics_hydraulic_cpd4_20260824"
CONFIG = ROOT / "stage27_designs" / STUDY / "geometry_01/resolved_config.json"
GEOMETRY_COMPLETION = CONFIG.parent / "completion.json"
DESIGN_AUDIT_DIR = ROOT / "stage27_evaluations" / STUDY / "design_audit_01"
DESIGN_AUDIT = DESIGN_AUDIT_DIR / "design_audit.json"
HANDOFF = DESIGN_AUDIT_DIR / "execution_handoff.json"
RUNNER = ROOT / "stage27_staging/run_stage27b_cpd4_confirmation_v1.py"
SUPERVISOR = ROOT / "stage27_staging/supervise_stage27b_cpd4_v1.py"
SUPERVISOR_DIR = ROOT / "stage27_supervisors" / STUDY / "gpu_confirmation_01"
LAUNCH_MANIFEST = SUPERVISOR_DIR / "launch_manifest.json"
RUN = ROOT / "stage27_runs" / STUDY / "gpu_confirmation_01"
OUTPUT = ROOT / "stage27_evaluations" / STUDY / "evaluation_01"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def close(a: float, b: float, tolerance: float = 1e-14) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tolerance)


def all_zero_nested(value: object) -> bool:
    array = np.asarray(value, dtype=float)
    return bool(np.all(np.isfinite(array)) and np.all(array == 0.0))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")

    config = load(CONFIG)
    geometry_completion = load(GEOMETRY_COMPLETION)
    design_audit = load(DESIGN_AUDIT)
    handoff = load(HANDOFF)
    launch = load(LAUNCH_MANIFEST)
    completion_path = RUN / "completion.json"
    completion = load(completion_path)

    checks = {
        "completion_passed": bool(completion.get("passed")),
        "completion_checks_passed": all(completion.get("checks", {}).values()),
        "geometry_completion_passed": bool(geometry_completion.get("passed"))
        and all(geometry_completion.get("checks", {}).values()),
        "design_audit_passed": bool(design_audit.get("passed"))
        and all(design_audit.get("checks", {}).values()),
        "handoff_passed": bool(handoff.get("passed")),
        "config_binding": digest(CONFIG)
        == geometry_completion["config_sha256"]
        == completion["config_sha256"]
        == launch["config_sha256"],
        "handoff_binding": digest(HANDOFF)
        == completion["handoff_sha256"]
        == launch["handoff_sha256"],
        "runner_binding": digest(RUNNER)
        == completion["runner_sha256"]
        == launch["runner_sha256"],
        "design_audit_binding": digest(DESIGN_AUDIT)
        == handoff["design_audit"]["sha256"],
        "qualified_gpu_binding": completion["environment"]["gpu"]["ptx_sha256"]
        == config["lineage"]["qualified_ptx_sha256"],
        "supervisor_completed": (SUPERVISOR_DIR / "status.txt").read_text(encoding="utf-8").strip()
        == "completed",
        "supervisor_stderr_empty": (SUPERVISOR_DIR / "stderr.log").stat().st_size == 0,
        "no_failure_artifact": not (RUN / "failure.json").exists()
        and not (SUPERVISOR_DIR / "failure.json").exists(),
        "three_case_completion": set(completion["case_records"])
        == {"clean", "open", "constricted"},
        "authority_respected": bool(completion["authority"]["independent_evaluation"])
        and not any(
            completion["authority"][key]
            for key in (
                "concentration_design",
                "concentration_execution",
                "mobile_sand",
                "render",
                "two_way_coupling",
            )
        ),
    }

    # Confirm every frozen source and geometry artifact still matches its declared hash.
    lineage_checks = {
        key: digest(Path(binding["path"])) == binding["sha256"]
        for key, binding in config["lineage"].items()
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding
    }
    geometry_artifact_checks = {}
    for case_id, binding in config["geometry"]["artifacts"].items():
        geometry_artifact_checks[case_id] = {
            "geometry": digest(Path(binding["geometry"])) == binding["geometry_sha256"],
            "material_vtk": digest(Path(binding["material_vtk"]))
            == binding["material_vtk_sha256"],
        }
    checks["lineage_hashes"] = all(lineage_checks.values())
    checks["geometry_artifact_hashes"] = all(
        all(case.values()) for case in geometry_artifact_checks.values()
    )

    completion_rows = {row["case_id"]: row for row in completion["paired_results"]}
    cpd2_rows = {row["case_id"]: row for row in config["cpd2_reference"]["paired_results"]}
    case_audits = []
    recomputed = {}
    for case_id in ("clean", "open", "constricted"):
        row = completion_rows[case_id]
        cpd2 = cpd2_rows[case_id]
        warm = config["cpd2_reference"]["warm_starts"][case_id]
        case_dir = RUN / row["solver_case_id"]
        record_path = case_dir / "record.json"
        record = load(record_path)
        artifact_files = {
            "audit_npz_sha256": "audit.npz",
            "final_fields_npz_sha256": "final_fields.npz",
            "final_shifted_state_npz_sha256": "final_shifted_state.npz",
            "final_flow_vtk_sha256": "final_flow.vtk",
        }
        artifact_checks = {
            key: digest(case_dir / filename) == record["artifacts"][key]
            for key, filename in artifact_files.items()
        }
        with np.load(case_dir / "audit.npz", allow_pickle=False) as audit:
            audit_finite = all(np.all(np.isfinite(audit[name])) for name in audit.files)
            terminal_step = int(audit["step"][-1])

        conductance = float(record["final"]["superficial_velocity_lu"]) / float(
            record["acceleration_lu"]
        )
        clean_conductance = float(completion_rows["clean"]["conductance_proxy_lu"])
        ratio = conductance / clean_conductance
        shift = ratio - float(cpd2["paired_permeability_ratio"])
        local = {
            "record_hash": digest(record_path)
            == completion["case_records"][case_id]
            == row["record_sha256"],
            "record_passed": bool(record.get("passed") and record.get("converged"))
            and all(record.get("checks", {}).values()),
            "artifact_hashes": all(artifact_checks.values()),
            "audit_finite": audit_finite,
            "terminal_step_binding": terminal_step
            == int(record["steps_completed"])
            == int(row["steps_completed"]),
            "cpd4_resolution": int(record["cpd"]) == 4
            and list(record["dimensions_lu"]) == [186, 186, 186],
            "warm_start_path": Path(record["initialization"]["path"]).resolve()
            == Path(warm["path"]).resolve(),
            "warm_start_hash": digest(Path(warm["path"]))
            == warm["sha256"]
            == record["initialization"]["sha256"],
            "warm_start_scaling": close(
                record["initialization"]["velocity_scale"], warm["velocity_scale"]
            )
            and close(
                record["initialization"]["density_deviation_scale"],
                warm["density_deviation_scale"],
            ),
            "conductance_recomputed": close(conductance, row["conductance_proxy_lu"]),
            "ratio_recomputed": close(ratio, row["paired_permeability_ratio"]),
            "shift_recomputed": close(shift, row["cpd2_to_cpd4_ratio_shift"]),
            "fatal_health_zero": int(record["numerical_health"]["fatal_sticky_code"]) == 0,
            "all_health_codes_zero": int(record["numerical_health"]["full_sticky_code"])
            == 0
            and int(record["numerical_health"]["reporting_only_sticky_code"]) == 0,
            "exact_equilibrium_closure": all(
                all_zero_nested(value)
                for value in record["exact_equilibrium_closure"].values()
            ),
        }
        case_audits.append(
            {
                "case_id": case_id,
                "record_sha256": digest(record_path),
                "artifact_checks": artifact_checks,
                "checks": local,
                "passed": all(local.values()),
            }
        )
        recomputed[case_id] = {
            "conductance_proxy_lu": conductance,
            "cpd2_ratio": float(cpd2["paired_permeability_ratio"]),
            "cpd4_ratio": ratio,
            "cpd2_to_cpd4_ratio_shift": shift,
            "intrinsic_permeability_m2": float(row["intrinsic_permeability_m2"]),
        }

    checks["all_case_audits"] = all(case["passed"] for case in case_audits)
    cpd2_contrast = recomputed["constricted"]["cpd2_ratio"] - recomputed["open"]["cpd2_ratio"]
    cpd4_contrast = recomputed["constricted"]["cpd4_ratio"] - recomputed["open"]["cpd4_ratio"]
    contrast_shift = cpd4_contrast - cpd2_contrast
    acceptance = config["acceptance"]
    checks.update(
        {
            "both_obstruction_signs": recomputed["open"]["cpd4_ratio"] < 1.0
            and recomputed["constricted"]["cpd4_ratio"] < 1.0,
            "deflected_more_obstructive": recomputed["constricted"]["cpd4_ratio"]
            < recomputed["open"]["cpd4_ratio"],
            "single_fibre_ratio_shifts_within_bound": all(
                abs(recomputed[case]["cpd2_to_cpd4_ratio_shift"])
                <= acceptance["maximum_absolute_single_fibre_ratio_shift"]
                for case in ("open", "constricted")
            ),
            "placement_contrast_shift_within_bound": abs(contrast_shift)
            <= acceptance["maximum_absolute_placement_contrast_shift"],
            "completion_metrics_reproduced": close(
                cpd2_contrast, completion["contrasts"]["cpd2_deflected_minus_open"]
            )
            and close(
                cpd4_contrast, completion["contrasts"]["cpd4_deflected_minus_open"]
            )
            and close(
                contrast_shift, completion["contrasts"]["cpd2_to_cpd4_contrast_shift"]
            ),
        }
    )

    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    metrics = {
        "clean_intrinsic_permeability_m2": recomputed["clean"]["intrinsic_permeability_m2"],
        "open_cpd2_ratio": recomputed["open"]["cpd2_ratio"],
        "open_cpd4_ratio": recomputed["open"]["cpd4_ratio"],
        "open_cpd2_to_cpd4_shift": recomputed["open"]["cpd2_to_cpd4_ratio_shift"],
        "open_cpd4_relative_change_percent": 100.0
        * (recomputed["open"]["cpd4_ratio"] - 1.0),
        "constricted_cpd2_ratio": recomputed["constricted"]["cpd2_ratio"],
        "constricted_cpd4_ratio": recomputed["constricted"]["cpd4_ratio"],
        "constricted_cpd2_to_cpd4_shift": recomputed["constricted"][
            "cpd2_to_cpd4_ratio_shift"
        ],
        "constricted_cpd4_relative_change_percent": 100.0
        * (recomputed["constricted"]["cpd4_ratio"] - 1.0),
        "cpd2_deflected_minus_open_ratio": cpd2_contrast,
        "cpd4_deflected_minus_open_ratio": cpd4_contrast,
        "placement_contrast_shift": contrast_shift,
        "cpd4_deflected_minus_open_percentage_points": 100.0 * cpd4_contrast,
    }
    evaluation = {
        "schema": "lbs.stage27b-stage26x-mechanics-hydraulic-cpd4-evaluation.v1",
        "status": "independently_verified_cpd4_solution" if passed else "independent_evaluation_failed",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "single_fibre_obstruction_and_placement_contrast_solution_verified"
        if passed
        else "cpd4_solution_verification_failed",
        "claim_boundary": config["claim_boundary"],
        "checks": checks,
        "lineage_checks": lineage_checks,
        "geometry_artifact_checks": geometry_artifact_checks,
        "case_audits": case_audits,
        "metrics": metrics,
        "acceptance": {
            "maximum_absolute_single_fibre_ratio_shift": acceptance[
                "maximum_absolute_single_fibre_ratio_shift"
            ],
            "maximum_absolute_placement_contrast_shift": acceptance[
                "maximum_absolute_placement_contrast_shift"
            ],
        },
        "interpretation": (
            "At CPD4, both one-fibre geometries remain slightly obstructive and the "
            "contact-deflected fibre remains more obstructive than the open-path fibre. "
            "The CPD2-to-CPD4 shifts satisfy the frozen numerical bounds. This verifies "
            "the solution for these fixed-solid single-fibre cases; it does not validate "
            "a physical concentration law or authorize mobile or two-way-coupled physics."
        ),
        "source_bindings": {
            "config": {"path": str(CONFIG), "sha256": digest(CONFIG)},
            "geometry_completion": {
                "path": str(GEOMETRY_COMPLETION),
                "sha256": digest(GEOMETRY_COMPLETION),
            },
            "design_audit": {"path": str(DESIGN_AUDIT), "sha256": digest(DESIGN_AUDIT)},
            "handoff": {"path": str(HANDOFF), "sha256": digest(HANDOFF)},
            "launch_manifest": {
                "path": str(LAUNCH_MANIFEST),
                "sha256": digest(LAUNCH_MANIFEST),
            },
            "completion": {"path": str(completion_path), "sha256": digest(completion_path)},
            "runner": {"path": str(RUNNER), "sha256": digest(RUNNER)},
            "supervisor": {"path": str(SUPERVISOR), "sha256": digest(SUPERVISOR)},
            "evaluator": {
                "path": str(Path(__file__).resolve()),
                "sha256": digest(Path(__file__).resolve()),
            },
        },
        "authority": {
            "render": passed,
            "next_concentration_design": passed,
            "concentration_execution": False,
            "absolute_permeability_validation": False,
            "mobile_sand": False,
            "clogging_evolution": False,
            "two_way_coupling": False,
        },
    }
    evaluation_path = OUTPUT / "evaluation.json"
    write(evaluation_path, evaluation)
    checkpoint = {
        "schema": evaluation["schema"] + ".checkpoint",
        "status": "render_and_next_design_authorized" if passed else "fail_closed",
        "passed": passed,
        "evaluation": {"path": str(evaluation_path), "sha256": digest(evaluation_path)},
        "next_handoff": {
            "authorized": "render the CPD2-to-CPD4 solution-verification result and design the next bounded multi-fibre concentration study"
            if passed
            else "none",
            "not_authorized": "concentration execution, absolute-permeability validation, mobile sand, clogging evolution or two-way coupling",
        },
    }
    checkpoint_path = OUTPUT / "checkpoint_manifest.json"
    write(checkpoint_path, checkpoint)
    print(
        json.dumps(
            {
                "passed": passed,
                "evaluation": str(evaluation_path),
                "evaluation_sha256": digest(evaluation_path),
                "checkpoint": str(checkpoint_path),
                "checkpoint_sha256": digest(checkpoint_path),
                "metrics": metrics,
                "failed_checks": [key for key, value in checks.items() if not value],
            },
            indent=2,
        )
    )
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
