#!/usr/bin/env python3
"""Run the frozen six-case Stage24e CPD4 static GPU-LBM confirmation."""

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

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
import stage17_relaxed_fibre_gpu_lbm_run as stage17  # noqa: E402


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path, output = args.config.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable Stage24e output: {output}")
    output.mkdir(parents=True)
    config = load(config_path)
    lineage = config["lineage"]
    lineage_keys = [key for key in lineage if not key.endswith("_sha256") and key != "qualified_ptx_sha256"]
    observed = {key: digest(ROOT / lineage[key]) for key in lineage_keys}
    if any(observed[key] != lineage[key + "_sha256"] for key in lineage_keys):
        raise RuntimeError("Stage24e immutable lineage mismatch")

    geometry_completion = load(ROOT / lineage["geometry_completion"])
    visual_audit = load(ROOT / lineage["geometry_visual_audit"])
    stage24c_completion = load(ROOT / lineage["stage24c_completion"])
    stage24c_evaluation = load(ROOT / lineage["stage24c_evaluation"])
    stage23e_evaluation = load(ROOT / lineage["stage23e_evaluation"])
    qualification = load(ROOT / lineage["stage13_qualification"])
    execution = load(ROOT / lineage["stage13_execution_manifest"])
    if not (geometry_completion.get("passed") is True and visual_audit.get("passed") is True):
        raise RuntimeError("Stage24d geometry/visual chain is not passed")
    if not (stage24c_completion.get("passed") is True and stage24c_evaluation.get("passed") is True):
        raise RuntimeError("Stage24c CPD2 chain is not passed")
    if stage24c_evaluation["source_hashes"]["completion"] != observed["stage24c_completion"]:
        raise RuntimeError("Stage24c evaluation/completion binding mismatch")
    if stage23e_evaluation.get("passed") is not True or stage23e_evaluation.get("clean_sand_baseline_freeze_authorized") is not True:
        raise RuntimeError("Stage23e CPD4 clean baseline is not frozen")
    if not (qualification.get("passed") is True and qualification.get("status") == "pass") or execution.get("status") != "evidence_complete":
        raise RuntimeError("Stage13 GPU qualification chain is incomplete")

    clean_records = {
        "n216_s1": load(ROOT / lineage["clean_s1_cpd4_record"]),
        "n216_s2": load(ROOT / lineage["clean_s2_cpd4_record"]),
    }
    clean_conductance = {}
    for packing, record in clean_records.items():
        if record.get("passed") is not True or not all(record.get("checks", {}).values()):
            raise RuntimeError(f"accepted clean CPD4 record is not passed: {packing}")
        clean_conductance[packing] = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])

    geometry_rows = {row["case_id"]: row for row in geometry_completion["cases"]}
    cpd2_rows = {row["case_id"]: row for row in stage24c_completion["paired_results"]}
    frozen_ids = stage24c_evaluation["frozen_bounded_cpd4_confirmation_subset_not_executed"]["case_ids"]
    configured_ids = [case["case_id"] for case in config["cases"]]
    if configured_ids != frozen_ids or len(configured_ids) != int(config["design"]["expected_case_count"]):
        raise RuntimeError("Stage24e configured cases differ from the frozen Stage24c subset")
    for case in config["cases"]:
        case_id = case["case_id"]
        for key in ("geometry", "geometry_audit", "cpd2_record", "cpd2_fields"):
            if digest(ROOT / case[key]) != case[key + "_sha256"]:
                raise RuntimeError(f"Stage24e selected source mismatch: {case_id} {key}")
        audit, record = load(ROOT / case["geometry_audit"]), load(ROOT / case["cpd2_record"])
        if not (audit.get("passed") is True and record.get("passed") is True and all(record.get("checks", {}).values())):
            raise RuntimeError(f"Stage24e case prerequisite is not passed: {case_id}")
        if record["artifacts"]["final_fields_npz_sha256"] != case["cpd2_fields_sha256"]:
            raise RuntimeError(f"Stage24e CPD2 fields are not bound by their record: {case_id}")
        if case_id not in geometry_rows or case_id not in cpd2_rows:
            raise RuntimeError(f"Stage24e case identity absent from prerequisite evidence: {case_id}")

    case_by_id = {case["case_id"]: case for case in config["cases"]}
    run_order = list(case_by_id)
    rng = np.random.default_rng(int(config["design"]["run_order_seed"]))
    rng.shuffle(run_order)
    adapter = copy.deepcopy(config)
    adapter["solver"]["resampled_local_field_warm_start"] = {
        case["case_id"]: {
            "path": case["cpd2_fields"],
            "sha256": case["cpd2_fields_sha256"],
            "velocity_scale": float(config["solver"]["warm_start_velocity_scale"]),
            "density_deviation_scale": float(config["solver"]["warm_start_density_deviation_scale"]),
        }
        for case in config["cases"]
    }
    stage17.install_generic_mask_oracle()
    driver, gpu_evidence = stage17.create_driver(adapter, Path(config["execution"]["cuda_bin"]), int(config["execution"]["gpu_ordinal"]))
    records = []
    try:
        for case_id in run_order:
            case = case_by_id[case_id]
            adapter["lineage"]["geometry_cpd4"] = case["geometry"]
            specification = {
                "case_id": case_id,
                "stage": "STAGE24E_LBS_F37_SELECTED_CPD4_CONFIRMATION",
                "cpd": 4,
                "acceleration_lu": float(config["solver"]["acceleration_lu"]),
            }
            record = stage17.run_case(driver, adapter, specification, output)
            records.append(record)
            print("STAGE24E_CASE=" + json.dumps(record, sort_keys=True), flush=True)
    finally:
        driver.close()

    results = {}
    for record in records:
        case = case_by_id[record["case_id"]]
        cpd2 = cpd2_rows[record["case_id"]]
        conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
        ratio4 = conductance / clean_conductance[case["packing"]]
        ratio2 = float(cpd2["paired_permeability_ratio"])
        results[record["case_id"]] = {
            "case_id": record["case_id"],
            "packing": case["packing"],
            "orientation_regime": case["orientation_regime"],
            "target_dry_mass_percent": float(case["target_dry_mass_percent"]),
            "conductance_proxy_lu": conductance,
            "paired_clean_conductance_proxy_lu": clean_conductance[case["packing"]],
            "cpd2_paired_permeability_ratio": ratio2,
            "cpd4_paired_permeability_ratio": ratio4,
            "cpd2_relative_permeability_change": ratio2 - 1.0,
            "cpd4_relative_permeability_change": ratio4 - 1.0,
            "cpd2_to_cpd4_ratio_shift": ratio4 - ratio2,
            "steps_completed": int(record["steps_completed"]),
            "record_sha256": digest(output / record["case_id"] / "record.json"),
        }

    contrasts = {}
    for name, pair in config["design"]["selected_contrasts"].items():
        low, high = pair
        cpd2 = results[high]["cpd2_paired_permeability_ratio"] - results[low]["cpd2_paired_permeability_ratio"]
        cpd4 = results[high]["cpd4_paired_permeability_ratio"] - results[low]["cpd4_paired_permeability_ratio"]
        contrasts[name] = {
            "reference_case": low,
            "comparison_case": high,
            "cpd2_contrast": cpd2,
            "cpd4_contrast": cpd4,
            "cpd2_to_cpd4_contrast_shift": cpd4 - cpd2,
            "sign_persists": cpd2 * cpd4 > 0.0,
        }

    detection_id = config["design"]["low_concentration_detection_floor_case"]
    main = [row for case_id, row in results.items() if case_id != detection_id]
    checks = {
        "all_six_records_passed": len(records) == 6 and all(record.get("passed") is True and all(record.get("checks", {}).values()) for record in records),
        "finite_positive_conductance": all(math.isfinite(row["conductance_proxy_lu"]) and row["conductance_proxy_lu"] > 0.0 for row in results.values()),
        "main_case_ratio_shifts_within_0p02": all(abs(row["cpd2_to_cpd4_ratio_shift"]) <= float(config["acceptance"]["maximum_absolute_main_case_cpd2_to_cpd4_ratio_shift"]) for row in main),
        "detection_floor_ratio_shift_within_0p01": abs(results[detection_id]["cpd2_to_cpd4_ratio_shift"]) <= float(config["acceptance"]["maximum_absolute_detection_floor_cpd2_to_cpd4_ratio_shift"]),
        "main_mixture_effect_signs_persist": all(row["cpd4_paired_permeability_ratio"] < 1.0 and row["cpd2_paired_permeability_ratio"] < 1.0 for row in main),
        "selected_contrast_shifts_within_0p02": all(abs(row["cpd2_to_cpd4_contrast_shift"]) <= float(config["acceptance"]["maximum_absolute_cpd2_to_cpd4_contrast_shift"]) for row in contrasts.values()),
        "selected_contrast_signs_persist": all(row["sign_persists"] for row in contrasts.values()),
    }
    passed = all(checks.values())
    completion = {
        "schema": config["schema"] + ".completion",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed_selected_cpd4_resolution_confirmation" if passed else "failed_selected_cpd4_resolution_confirmation",
        "passed": passed,
        "research_question": config["research_question"],
        "claim_boundary": config["claim_boundary"],
        "config_sha256": digest(config_path),
        "runner_sha256": digest(Path(__file__).resolve()),
        "lineage_hashes": observed,
        "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu_evidence},
        "run_order": run_order,
        "case_records": {record["case_id"]: digest(output / record["case_id"] / "record.json") for record in records},
        "clean_controls": {packing: {"conductance_proxy_lu": value} for packing, value in clean_conductance.items()},
        "case_results": results,
        "selected_contrasts": contrasts,
        "checks": checks,
        "decision": "A pass verifies the selected CPD2 relative-permeability directions at CPD4 within the declared numerical bounds. It does not validate physical mixed-sand behavior or authorize mechanics/coupled-flow claims.",
    }
    write_json(output / "completion.json", completion)
    print("STAGE24E_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
    return 0 if passed else 4


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        output_arg = Path(sys.argv[sys.argv.index("--output") + 1]).resolve() if "--output" in sys.argv else None
        if output_arg is not None and output_arg.exists() and not (output_arg / "failure.json").exists():
            write_json(output_arg / "failure.json", {
                "schema": "lbs.stage24e-lbs-f37-selected-cpd4-gpu.v1.failure",
                "status": "failed_preserved",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "termination_reason": str(exc),
                "traceback": traceback.format_exc(),
            })
        raise
