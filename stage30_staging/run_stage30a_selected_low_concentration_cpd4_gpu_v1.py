#!/usr/bin/env python3
"""Run the released Stage30a four-case CPD4 GPU confirmation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
EXTERNAL = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration\scripts")
sys.path.insert(0, str(EXTERNAL))
import stage17_relaxed_fibre_gpu_lbm_run as stage17  # noqa: E402

ORDER = ("clean", "s29e_f001_isolated_B", "s29e_f004_zero_contact_context_B", "s29e_f004_one_contact_context_B")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path, handoff_path, output = args.config.resolve(), args.handoff.resolve(), args.output.resolve()
    runner = Path(__file__).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    config, handoff = load(config_path), load(handoff_path)
    if config.get("status") != "cpd4_geometry_built_independent_gpu_release_required" or config["authority"].get("gpu_cpd4_execution") is not False:
        raise RuntimeError("configuration is not the frozen fail-closed Stage30a preflight")
    if not (handoff.get("passed") is True and handoff.get("status") == "stage30a_cpd4_gpu_execution_authorized" and handoff["authority"].get("gpu_cpd4_execution") is True):
        raise RuntimeError("independent Stage30a GPU handoff is absent")
    if handoff["bindings"]["config_sha256"] != sha(config_path) or handoff["bindings"]["runner_sha256"] != sha(runner):
        raise RuntimeError("handoff/config/runner hash mismatch")
    if any(config["authority"].get(k, False) for k in ("permeability_validation_claim", "mechanics_rerun", "mobile_sand", "migration", "clogging", "two_way_coupling")):
        raise RuntimeError("authority boundary exceeded")
    observed = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            observed[key] = sha(path)
            if observed[key] != binding["sha256"]:
                raise RuntimeError(f"immutable lineage mismatch: {key}")
    for case_id, binding in config["geometry"]["artifacts"].items():
        if sha(Path(binding["geometry"])) != binding["geometry_sha256"]:
            raise RuntimeError(f"geometry hash mismatch: {case_id}")
    output.mkdir(parents=True)
    adapter = copy.deepcopy(config)
    adapter["lineage"]["cuda_source"] = config["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = config["lineage"]["qualified_ptx_sha256"]
    adapter["solver"]["resampled_local_field_warm_start"] = {}
    for case_id, warm in config["cpd2_reference"]["warm_starts"].items():
        adapter["solver"]["resampled_local_field_warm_start"][f"stage30a_{case_id}_cpd4"] = warm
    stage17.install_generic_mask_oracle()
    driver, gpu = stage17.create_driver(adapter, Path(config["execution"]["cuda_bin"]), int(config["execution"]["gpu_ordinal"]))
    results = []
    try:
        for ordinal, case_id in enumerate(ORDER, start=1):
            adapter["lineage"]["geometry_cpd4"] = config["geometry"]["artifacts"][case_id]["geometry"]
            spec = {"case_id": f"stage30a_{case_id}_cpd4", "stage": "STAGE30A_SELECTED_LOW_CONCENTRATION_CPD4_SOLUTION_VERIFICATION",
                    "cpd": 4, "acceleration_lu": float(config["solver"]["acceleration_lu"])}
            print("STAGE30A_START=" + json.dumps({"ordinal": ordinal, "total": len(ORDER), "case_id": case_id}), flush=True)
            record = stage17.run_case(driver, adapter, spec, output)
            conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
            results.append({"case_id": case_id, "solver_case_id": spec["case_id"], "conductance_proxy_lu": conductance,
                            "steps_completed": int(record["steps_completed"]), "record_sha256": sha(output / spec["case_id"] / "record.json"),
                            "record_passed": bool(record.get("passed") and all(record.get("checks", {}).values()))})
            print("STAGE30A_CASE=" + json.dumps(results[-1], sort_keys=True), flush=True)
    finally:
        driver.close()
    clean = results[0]["conductance_proxy_lu"]
    spacing = float(config["geometry"]["spacing_m"])
    nu = float(config["solver"]["kinematic_viscosity_lu"])
    cpd2 = {row["case_id"]: row for row in config["cpd2_reference"]["paired_results"]}
    for row in results:
        row["paired_permeability_ratio"] = row["conductance_proxy_lu"] / clean
        row["paired_relative_permeability_change"] = row["paired_permeability_ratio"] - 1.0
        row["intrinsic_permeability_m2"] = nu * row["conductance_proxy_lu"] * spacing * spacing
        row["cpd2_ratio"] = float(cpd2[row["case_id"]]["paired_permeability_ratio"])
        row["cpd2_to_cpd4_ratio_shift"] = row["paired_permeability_ratio"] - row["cpd2_ratio"]
    by_id = {row["case_id"]: row for row in results}
    zero_id, one_id = "s29e_f004_zero_contact_context_B", "s29e_f004_one_contact_context_B"
    cpd2_contrast = float(cpd2[one_id]["paired_permeability_ratio"] - cpd2[zero_id]["paired_permeability_ratio"])
    cpd4_contrast = by_id[one_id]["paired_permeability_ratio"] - by_id[zero_id]["paired_permeability_ratio"]
    contrast_shift = cpd4_contrast - cpd2_contrast
    accepted_clean = float(config["accepted_clean_cpd4"]["conductance_proxy_lu"])
    clean_error = abs(clean - accepted_clean) / abs(accepted_clean)
    a = config["acceptance"]
    checks = {
        "all_four_records_passed": len(results) == 4 and all(row["record_passed"] for row in results),
        "finite_positive_conductance": all(math.isfinite(row["conductance_proxy_lu"]) and row["conductance_proxy_lu"] > 0 for row in results),
        "clean_reproduced": clean_error <= float(a["maximum_relative_clean_reproduction_error"]),
        "selected_ratio_shifts": all(abs(row["cpd2_to_cpd4_ratio_shift"]) <= float(a["maximum_absolute_selected_ratio_shift"]) for row in results if row["case_id"] != "clean"),
        "all_selected_obstructive": all(row["paired_permeability_ratio"] < 1.0 for row in results if row["case_id"] != "clean"),
        "zero_contact_more_obstructive": by_id[zero_id]["paired_permeability_ratio"] < by_id[one_id]["paired_permeability_ratio"],
        "four_fibre_contrast_shift_within_bound": abs(contrast_shift) <= float(a["maximum_absolute_four_fibre_contrast_shift"]),
    }
    passed = all(checks.values())
    completion = {
        "schema": config["schema"] + ".gpu-completion", "status": "passed_cpd4_solution_verification" if passed else "failed_cpd4_solution_verification",
        "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "research_question": config["research_question"],
        "claim_boundary": config["claim_boundary"], "config_sha256": sha(config_path), "handoff_sha256": sha(handoff_path),
        "runner_sha256": sha(runner), "lineage_hashes": observed, "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu},
        "case_records": {row["case_id"]: row["record_sha256"] for row in results}, "paired_results": results,
        "contrasts": {"cpd2_one_minus_zero": cpd2_contrast, "cpd4_one_minus_zero": cpd4_contrast, "cpd2_to_cpd4_contrast_shift": contrast_shift},
        "clean_reproduction_relative_error": clean_error, "checks": checks,
        "reused_stage28c_cpd4": config["reused_stage28c_cpd4"],
        "authority": {"independent_evaluation": True, "render": False, "permeability_validation_claim": False,
                      "mechanics_rerun": False, "mobile_sand": False, "migration": False, "clogging": False, "two_way_coupling": False},
    }
    write(output / "completion.json", completion)
    print("STAGE30A_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
    return 0 if passed else 4


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        if "--output" in sys.argv:
            failed = Path(sys.argv[sys.argv.index("--output") + 1]).resolve()
            if failed.exists() and not (failed / "failure.json").exists():
                write(failed / "failure.json", {"schema": "lbs.stage30a-selected-low-concentration-cpd4.v1.failure",
                "status": "failed_preserved", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "termination_reason": str(exc), "traceback": traceback.format_exc()})
        raise
