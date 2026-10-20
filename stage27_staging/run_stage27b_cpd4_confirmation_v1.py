#!/usr/bin/env python3
"""Run the released Stage27b three-case CPD4 GPU confirmation."""

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

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_SCRIPTS = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration\scripts")
sys.path.insert(0, str(EXTERNAL_SCRIPTS))
import stage17_relaxed_fibre_gpu_lbm_run as stage17  # noqa: E402


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path, handoff_path, output = args.config.resolve(), args.handoff.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    output.mkdir(parents=True)
    config, handoff = load(config_path), load(handoff_path)
    audit_path = Path(handoff["design_audit"]["path"])
    audit = load(audit_path)
    if not (handoff.get("passed") and audit.get("passed") and audit["authority"]["gpu_cpd4_execution"] and digest(audit_path) == handoff["design_audit"]["sha256"]):
        raise RuntimeError("independent Stage27b handoff does not authorize execution")
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and digest(Path(binding["path"])) != binding["sha256"]:
            raise RuntimeError(f"lineage mismatch: {key}")
    adapter = copy.deepcopy(config)
    adapter["lineage"]["cuda_source"] = config["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = config["lineage"]["qualified_ptx_sha256"]
    adapter["solver"]["resampled_local_field_warm_start"] = {}
    for case_id, warm in config["cpd2_reference"]["warm_starts"].items():
        adapter["solver"]["resampled_local_field_warm_start"][f"stage27b_{case_id}_cpd4"] = warm
    stage17.install_generic_mask_oracle()
    driver, gpu = stage17.create_driver(adapter, Path(config["execution"]["cuda_bin"]), int(config["execution"]["gpu_ordinal"]))
    results = []
    try:
        for ordinal, case_id in enumerate(("clean", "open", "constricted"), start=1):
            adapter["lineage"]["geometry_cpd4"] = config["geometry"]["artifacts"][case_id]["geometry"]
            specification = {"case_id": f"stage27b_{case_id}_cpd4", "stage": "STAGE27B_CPD4_SOLUTION_VERIFICATION", "cpd": 4, "acceleration_lu": float(config["solver"]["acceleration_lu"])}
            print("STAGE27B_START=" + json.dumps({"ordinal": ordinal, "total": 3, "case_id": case_id}), flush=True)
            record = stage17.run_case(driver, adapter, specification, output)
            conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
            results.append({"case_id": case_id, "solver_case_id": specification["case_id"], "conductance_proxy_lu": conductance, "steps_completed": int(record["steps_completed"]), "record_sha256": digest(output / specification["case_id"] / "record.json"), "record_passed": bool(record.get("passed") and all(record.get("checks", {}).values()))})
            print("STAGE27B_CASE=" + json.dumps(results[-1], sort_keys=True), flush=True)
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
    ratios = {row["case_id"]: row["paired_permeability_ratio"] for row in results}
    cpd2_contrast = float(cpd2["constricted"]["paired_permeability_ratio"] - cpd2["open"]["paired_permeability_ratio"])
    cpd4_contrast = ratios["constricted"] - ratios["open"]
    contrast_shift = cpd4_contrast - cpd2_contrast
    a = config["acceptance"]
    checks = {"all_three_records_passed": len(results) == 3 and all(row["record_passed"] for row in results), "finite_positive_conductance": all(math.isfinite(row["conductance_proxy_lu"]) and row["conductance_proxy_lu"] > 0 for row in results), "single_fibre_ratio_shifts": all(abs(row["cpd2_to_cpd4_ratio_shift"]) <= float(a["maximum_absolute_single_fibre_ratio_shift"]) for row in results if row["case_id"] != "clean"), "both_obstruction_signs": ratios["open"] < 1.0 and ratios["constricted"] < 1.0, "deflected_more_obstructive": ratios["constricted"] < ratios["open"], "placement_contrast_shift": abs(contrast_shift) <= float(a["maximum_absolute_placement_contrast_shift"])}
    passed = all(checks.values())
    completion = {"schema": config["schema"] + ".gpu-completion", "status": "passed_cpd4_solution_verification" if passed else "failed_cpd4_solution_verification", "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "claim_boundary": config["claim_boundary"], "config_sha256": digest(config_path), "handoff_sha256": digest(handoff_path), "runner_sha256": digest(Path(__file__).resolve()), "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu}, "case_records": {row["case_id"]: row["record_sha256"] for row in results}, "paired_results": results, "contrasts": {"cpd2_deflected_minus_open": cpd2_contrast, "cpd4_deflected_minus_open": cpd4_contrast, "cpd2_to_cpd4_contrast_shift": contrast_shift}, "checks": checks, "authority": {"independent_evaluation": True, "render": False, "concentration_design": False, "concentration_execution": False, "mobile_sand": False, "two_way_coupling": False}}
    write(output / "completion.json", completion)
    print("STAGE27B_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
    return 0 if passed else 4


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        if "--output" in sys.argv:
            out = Path(sys.argv[sys.argv.index("--output") + 1]).resolve()
            if out.exists() and not (out / "failure.json").exists():
                write(out / "failure.json", {"schema": "lbs.stage27b-cpd4.failure", "status": "failed_preserved", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "termination_reason": str(exc), "traceback": traceback.format_exc()})
        raise

