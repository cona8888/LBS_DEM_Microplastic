#!/usr/bin/env python3
"""Independently audit the immutable Stage28c three-case CPD4 result."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage28c_selected_two_fibre_cpd4_20260825"
CONFIG = ROOT / "stage28_designs" / STUDY / "geometry_01/resolved_config.json"
GEOMETRY_COMPLETION = CONFIG.parent / "completion.json"
DESIGN_AUDIT = ROOT / "stage28_evaluations" / STUDY / "design_audit_01/design_audit.json"
RELEASE_AUDIT = ROOT / "stage28_evaluations" / STUDY / "gpu_release_audit_01/audit.json"
HANDOFF = RELEASE_AUDIT.parent / "execution_handoff.json"
RUNNER = ROOT / "stage28_staging/run_stage28c_selected_two_fibre_cpd4_gpu_v1.py"
RUN = ROOT / "stage28_runs" / STUDY / "gpu_confirmation_01"
OUTPUT = ROOT / "stage28_evaluations" / STUDY / "gpu_evaluation_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def close(a: float, b: float, atol: float = 1e-14) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=atol)


def all_zero(value: object) -> bool:
    array = np.asarray(value, dtype=float)
    return bool(np.all(np.isfinite(array)) and np.all(array == 0.0))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable evaluation: {OUTPUT}")
    config, geometry, design, release, handoff = map(load, (CONFIG, GEOMETRY_COMPLETION, DESIGN_AUDIT, RELEASE_AUDIT, HANDOFF))
    completion_path = RUN / "completion.json"
    completion = load(completion_path)
    checks = {
        "completion_passed": bool(completion.get("passed")), "completion_checks_passed": all(completion.get("checks", {}).values()),
        "geometry_passed": bool(geometry.get("passed")) and all(geometry.get("checks", {}).values()),
        "design_audit_passed": bool(design.get("passed")) and all(design.get("checks", {}).values()),
        "release_audit_passed": bool(release.get("passed")) and all(release.get("checks", {}).values()),
        "config_binding": sha(CONFIG) == geometry["config_sha256"] == completion["config_sha256"] == handoff["bindings"]["config_sha256"],
        "handoff_binding": sha(HANDOFF) == completion["handoff_sha256"],
        "runner_binding": sha(RUNNER) == completion["runner_sha256"] == handoff["bindings"]["runner_sha256"],
        "qualified_gpu_binding": completion["environment"]["gpu"]["ptx_sha256"] == config["lineage"]["qualified_ptx_sha256"],
        "no_failure_artifact": not (RUN / "failure.json").exists(),
        "three_case_completion": list(completion["case_records"]) == ["clean", "crossing_interaction", "separated_open_open"] or set(completion["case_records"]) == {"clean", "separated_open_open", "crossing_interaction"},
        "authority_respected": bool(completion["authority"]["independent_evaluation"])
        and not any(completion["authority"][key] for key in ("render", "production_concentration_campaign", "mobile_sand", "two_way_coupling")),
    }
    lineage_checks = {key: sha(Path(binding["path"])) == binding["sha256"] for key, binding in config["lineage"].items()
                      if isinstance(binding, dict) and "path" in binding and "sha256" in binding}
    geometry_checks = {case: sha(Path(binding["geometry"])) == binding["geometry_sha256"]
                       and sha(Path(binding["material_vtk"])) == binding["material_vtk_sha256"]
                       for case, binding in config["geometry"]["artifacts"].items()}
    checks["lineage_hashes"] = all(lineage_checks.values())
    checks["geometry_hashes"] = all(geometry_checks.values())
    completion_rows = {row["case_id"]: row for row in completion["paired_results"]}
    cpd2_rows = {row["case_id"]: row for row in config["cpd2_reference"]["paired_results"]}
    recomputed, case_audits = {}, []
    for case_id in ("clean", "separated_open_open", "crossing_interaction"):
        row, cpd2, warm = completion_rows[case_id], cpd2_rows[case_id], config["cpd2_reference"]["warm_starts"][case_id]
        case_dir = RUN / row["solver_case_id"]
        record_path = case_dir / "record.json"
        record = load(record_path)
        files = {"audit_npz_sha256": "audit.npz", "final_fields_npz_sha256": "final_fields.npz",
                 "final_shifted_state_npz_sha256": "final_shifted_state.npz", "final_flow_vtk_sha256": "final_flow.vtk"}
        artifact_checks = {key: (case_dir / name).is_file() and sha(case_dir / name) == record["artifacts"][key] for key, name in files.items()}
        with np.load(case_dir / "audit.npz", allow_pickle=False) as audit:
            finite = all(np.all(np.isfinite(audit[name])) for name in audit.files)
            terminal_step = int(audit["step"][-1])
        conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
        clean = float(completion_rows["clean"]["conductance_proxy_lu"])
        ratio = conductance / clean
        shift = ratio - float(cpd2["paired_permeability_ratio"])
        local = {
            "record_hash": sha(record_path) == completion["case_records"][case_id] == row["record_sha256"],
            "record_passed": bool(record.get("passed") and record.get("converged")) and all(record.get("checks", {}).values()),
            "artifact_hashes": all(artifact_checks.values()), "audit_finite": finite,
            "terminal_step_binding": terminal_step == int(record["steps_completed"]) == int(row["steps_completed"]),
            "cpd4_resolution": int(record["cpd"]) == 4 and list(record["dimensions_lu"]) == [186, 186, 186],
            "warm_start_path": Path(record["initialization"]["path"]).resolve() == Path(warm["path"]).resolve(),
            "warm_start_hash": sha(Path(warm["path"])) == warm["sha256"] == record["initialization"]["sha256"],
            "warm_start_scaling": close(record["initialization"]["velocity_scale"], warm["velocity_scale"])
            and close(record["initialization"]["density_deviation_scale"], warm["density_deviation_scale"]),
            "conductance_recomputed": close(conductance, row["conductance_proxy_lu"]),
            "ratio_recomputed": close(ratio, row["paired_permeability_ratio"]), "shift_recomputed": close(shift, row["cpd2_to_cpd4_ratio_shift"]),
            "fatal_health_zero": int(record["numerical_health"]["fatal_sticky_code"]) == 0,
            "all_health_codes_zero": int(record["numerical_health"]["full_sticky_code"]) == 0 and int(record["numerical_health"]["reporting_only_sticky_code"]) == 0,
            "exact_equilibrium_closure": all(all_zero(value) for value in record["exact_equilibrium_closure"].values()),
        }
        case_audits.append({"case_id": case_id, "passed": all(local.values()), "checks": local, "artifact_checks": artifact_checks,
                            "record_sha256": sha(record_path)})
        recomputed[case_id] = {"conductance_proxy_lu": conductance, "cpd2_ratio": float(cpd2["paired_permeability_ratio"]),
                               "cpd4_ratio": ratio, "cpd2_to_cpd4_ratio_shift": shift,
                               "intrinsic_permeability_m2": float(row["intrinsic_permeability_m2"])}
    checks["all_case_audits"] = all(row["passed"] for row in case_audits)
    cpd2_contrast = recomputed["crossing_interaction"]["cpd2_ratio"] - recomputed["separated_open_open"]["cpd2_ratio"]
    cpd4_contrast = recomputed["crossing_interaction"]["cpd4_ratio"] - recomputed["separated_open_open"]["cpd4_ratio"]
    contrast_shift = cpd4_contrast - cpd2_contrast
    accepted_clean = float(config["accepted_clean_cpd4"]["conductance_proxy_lu"])
    clean_error = abs(recomputed["clean"]["conductance_proxy_lu"] - accepted_clean) / abs(accepted_clean)
    a = config["acceptance"]
    checks.update({
        "clean_reproduction": clean_error <= a["maximum_relative_clean_reproduction_error"],
        "two_fibre_ratio_shifts_within_bound": all(abs(recomputed[case]["cpd2_to_cpd4_ratio_shift"]) <= a["maximum_absolute_two_fibre_ratio_shift"] for case in ("separated_open_open", "crossing_interaction")),
        "both_obstruction_signs": recomputed["separated_open_open"]["cpd4_ratio"] < 1.0 and recomputed["crossing_interaction"]["cpd4_ratio"] < 1.0,
        "crossing_more_obstructive": recomputed["crossing_interaction"]["cpd4_ratio"] < recomputed["separated_open_open"]["cpd4_ratio"],
        "contrast_shift_within_bound": abs(contrast_shift) <= a["maximum_absolute_crossing_minus_separated_contrast_shift"],
        "completion_metrics_reproduced": close(cpd2_contrast, completion["contrasts"]["cpd2_crossing_minus_separated"])
        and close(cpd4_contrast, completion["contrasts"]["cpd4_crossing_minus_separated"])
        and close(contrast_shift, completion["contrasts"]["cpd2_to_cpd4_contrast_shift"]),
    })
    passed = all(checks.values())
    metrics = {"clean_cpd4_intrinsic_permeability_m2": recomputed["clean"]["intrinsic_permeability_m2"],
               "clean_reproduction_relative_error": clean_error,
               "separated_cpd2_ratio": recomputed["separated_open_open"]["cpd2_ratio"],
               "separated_cpd4_ratio": recomputed["separated_open_open"]["cpd4_ratio"],
               "separated_ratio_shift": recomputed["separated_open_open"]["cpd2_to_cpd4_ratio_shift"],
               "crossing_cpd2_ratio": recomputed["crossing_interaction"]["cpd2_ratio"],
               "crossing_cpd4_ratio": recomputed["crossing_interaction"]["cpd4_ratio"],
               "crossing_ratio_shift": recomputed["crossing_interaction"]["cpd2_to_cpd4_ratio_shift"],
               "cpd2_crossing_minus_separated": cpd2_contrast, "cpd4_crossing_minus_separated": cpd4_contrast,
               "contrast_shift": contrast_shift}
    OUTPUT.mkdir(parents=True)
    evaluation = {
        "schema": "lbs.stage28c-selected-two-fibre-cpd4-evaluation.v1",
        "status": "independently_verified_cpd4_solution" if passed else "independent_evaluation_failed", "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "two_fibre_separation_and_crossing_effect_solution_verified" if passed else "cpd4_solution_verification_failed",
        "claim_boundary": config["claim_boundary"], "checks": checks, "lineage_checks": lineage_checks,
        "geometry_checks": geometry_checks, "case_audits": case_audits, "metrics": metrics,
        "interpretation": "The paired two-fibre obstruction and crossing-minus-separated contrast are solution-verified at CPD4 within the frozen bounds." if passed else "The selected two-fibre result is not solution-verified at CPD4; preserve the failure and do not promote it.",
        "source_bindings": {"config": {"path": str(CONFIG), "sha256": sha(CONFIG)},
                            "geometry_completion": {"path": str(GEOMETRY_COMPLETION), "sha256": sha(GEOMETRY_COMPLETION)},
                            "design_audit": {"path": str(DESIGN_AUDIT), "sha256": sha(DESIGN_AUDIT)},
                            "release_audit": {"path": str(RELEASE_AUDIT), "sha256": sha(RELEASE_AUDIT)},
                            "handoff": {"path": str(HANDOFF), "sha256": sha(HANDOFF)},
                            "completion": {"path": str(completion_path), "sha256": sha(completion_path)},
                            "runner": {"path": str(RUNNER), "sha256": sha(RUNNER)},
                            "evaluator": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())}},
        "authority": {"render": passed, "next_concentration_design": passed, "production_concentration_execution": False,
                      "mobile_sand": False, "clogging_evolution": False, "two_way_coupling": False},
    }
    evaluation_path = OUTPUT / "evaluation.json"
    write(evaluation_path, evaluation)
    checkpoint = {"schema": evaluation["schema"] + ".checkpoint", "status": "render_and_next_design_authorized" if passed else "fail_closed",
                  "passed": passed, "evaluation": {"path": str(evaluation_path), "sha256": sha(evaluation_path)},
                  "next_handoff": {"authorized": "render and design the bounded concentration study" if passed else "none",
                                   "not_authorized": "production concentration execution, mobile sand, deformation or two-way coupling"}}
    checkpoint_path = OUTPUT / "checkpoint_manifest.json"
    write(checkpoint_path, checkpoint)
    print(json.dumps({"passed": passed, "evaluation": str(evaluation_path), "evaluation_sha256": sha(evaluation_path),
                      "checkpoint": str(checkpoint_path), "checkpoint_sha256": sha(checkpoint_path),
                      "metrics": metrics, "failed_checks": [key for key, value in checks.items() if not value]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
