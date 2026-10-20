#!/usr/bin/env python3
"""Run the released Stage31f seven-case selected replicated CPD4 confirmation."""

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

ORDER = (
    "s31b_n216_s2_clean",
    "s31b_n216_s1_A_f001_open",
    "s31b_n216_s1_A_f002_open",
    "s31b_n216_s1_A_f004_open",
    "s31b_n216_s1_B_f004_open",
    "s31b_n216_s2_A_f004_open",
    "s31b_n216_s2_B_f004_open",
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


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
        raise RuntimeError("configuration is not the frozen Stage31f preflight")
    if not (handoff.get("passed") is True and handoff.get("status") == "stage31f_cpd4_gpu_execution_authorized"
            and handoff["authority"].get("gpu_cpd4_execution") is True):
        raise RuntimeError("independent Stage31f GPU release is absent")
    if handoff["bindings"]["config_sha256"] != sha(config_path) or handoff["bindings"]["runner_sha256"] != sha(runner):
        raise RuntimeError("handoff/config/runner hash mismatch")
    prohibited = ("absolute_permeability_validation_claim", "mechanics_rerun", "mobile_sand", "migration",
                  "clogging", "deformation", "transient_coupling", "two_way_coupling")
    if any(config["authority"].get(key, False) for key in prohibited):
        raise RuntimeError("authority boundary exceeded")

    observed_lineage = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            observed_lineage[key] = sha(path)
            if observed_lineage[key] != binding["sha256"]:
                raise RuntimeError(f"immutable lineage mismatch: {key}")
    for case_id, binding in config["geometry"]["artifacts"].items():
        if sha(Path(binding["geometry"])) != binding["geometry_sha256"]:
            raise RuntimeError(f"geometry hash mismatch: {case_id}")
    reused = config["reused_s1_clean_cpd4"]
    for key in ("geometry", "record", "completion", "evaluation"):
        binding = reused[key]
        if sha(Path(binding["path"])) != binding["sha256"]:
            raise RuntimeError(f"reused s1 clean mismatch: {key}")

    output.mkdir(parents=True)
    adapter = copy.deepcopy(config)
    adapter["lineage"]["cuda_source"] = config["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = config["lineage"]["qualified_ptx_sha256"]
    adapter["solver"]["resampled_local_field_warm_start"] = {}
    for case_id, warm in config["cpd2_reference"]["warm_starts"].items():
        adapter["solver"]["resampled_local_field_warm_start"][f"stage31f_{case_id}_cpd4"] = warm
    stage17.install_generic_mask_oracle()
    driver, gpu = stage17.create_driver(adapter, Path(config["execution"]["cuda_bin"]), int(config["execution"]["gpu_ordinal"]))
    results = []
    case_meta = {row["case_id"]: row for row in config["geometry"]["cases"]}
    try:
        for ordinal, case_id in enumerate(ORDER, start=1):
            adapter["lineage"]["geometry_cpd4"] = config["geometry"]["artifacts"][case_id]["geometry"]
            spec = {"case_id": f"stage31f_{case_id}_cpd4",
                    "stage": "STAGE31F_SELECTED_REPLICATED_CPD4_SOLUTION_VERIFICATION",
                    "cpd": 4, "acceleration_lu": float(config["solver"]["acceleration_lu"])}
            print("STAGE31F_START=" + json.dumps({"ordinal": ordinal, "total": len(ORDER), "case_id": case_id}), flush=True)
            record = stage17.run_case(driver, adapter, spec, output)
            conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
            meta = case_meta[case_id]
            result = {
                "case_id": case_id, "solver_case_id": spec["case_id"], "packing_id": meta["packing_id"],
                "placement_block": meta["placement_block"], "fibre_count": meta["fibre_count"],
                "conductance_proxy_lu": conductance, "steps_completed": int(record["steps_completed"]),
                "record_sha256": sha(output / spec["case_id"] / "record.json"),
                "record_passed": bool(record.get("passed") and all(record.get("checks", {}).values())),
            }
            results.append(result)
            print("STAGE31F_CASE=" + json.dumps(result, sort_keys=True), flush=True)
    finally:
        driver.close()

    by_id = {row["case_id"]: row for row in results}
    clean_controls = {"n216_s1": float(reused["conductance_proxy_lu"]),
                      "n216_s2": float(by_id["s31b_n216_s2_clean"]["conductance_proxy_lu"])}
    cpd2 = {row["case_id"]: row for row in config["cpd2_reference"]["paired_results"]}
    nu = float(config["solver"]["kinematic_viscosity_lu"])
    for row in results:
        clean = clean_controls[row["packing_id"]]
        row["paired_permeability_ratio"] = row["conductance_proxy_lu"] / clean
        row["paired_relative_permeability_change"] = row["paired_permeability_ratio"] - 1.0
        row["cpd2_ratio"] = float(cpd2[row["case_id"]]["paired_permeability_ratio"])
        row["cpd2_to_cpd4_ratio_shift"] = row["paired_permeability_ratio"] - row["cpd2_ratio"]
        spacing = float(case_meta[row["case_id"]]["spacing_m"])
        row["intrinsic_permeability_m2_descriptive_only"] = nu * row["conductance_proxy_lu"] * spacing * spacing

    contrast_pairs = {
        "n216_s1": ("s31b_n216_s1_A_f004_open", "s31b_n216_s1_B_f004_open"),
        "n216_s2": ("s31b_n216_s2_A_f004_open", "s31b_n216_s2_B_f004_open"),
    }
    contrasts = {}
    for packing, (a_id, b_id) in contrast_pairs.items():
        cpd2_value = float(cpd2[b_id]["paired_permeability_ratio"] - cpd2[a_id]["paired_permeability_ratio"])
        cpd4_value = float(by_id[b_id]["paired_permeability_ratio"] - by_id[a_id]["paired_permeability_ratio"])
        contrasts[packing] = {"cpd2_B_minus_A": cpd2_value, "cpd4_B_minus_A": cpd4_value,
                              "cpd2_to_cpd4_contrast_shift": cpd4_value - cpd2_value}
    a = config["acceptance"]
    nonclean = [row for row in results if row["fibre_count"] > 0]
    checks = {
        "all_seven_records_passed": len(results) == 7 and all(row["record_passed"] for row in results),
        "finite_positive_conductance": all(math.isfinite(row["conductance_proxy_lu"]) and row["conductance_proxy_lu"] > 0 for row in results),
        "s2_clean_ratio_exact": by_id["s31b_n216_s2_clean"]["paired_permeability_ratio"] == 1.0,
        "all_selected_obstructive": all(row["paired_permeability_ratio"] < 1.0 for row in nonclean),
        "selected_ratio_shifts_within_bound": all(abs(row["cpd2_to_cpd4_ratio_shift"]) <= float(a["maximum_absolute_selected_ratio_shift"]) for row in nonclean),
        "both_block_contrast_shifts_within_bound": all(abs(value["cpd2_to_cpd4_contrast_shift"]) <= float(a["maximum_absolute_block_contrast_shift"]) for value in contrasts.values()),
        "both_block_contrast_signs_preserved": contrasts["n216_s1"]["cpd4_B_minus_A"] > 0 and contrasts["n216_s2"]["cpd4_B_minus_A"] < 0,
    }
    passed = all(checks.values())
    s1_sequence = [by_id[f"s31b_n216_s1_A_f{count:03d}_open"]["paired_permeability_ratio"] for count in (1, 2, 4)]
    completion = {
        "schema": config["schema"] + ".gpu-completion",
        "status": "passed_selected_replicated_cpd4_solution_verification" if passed else "failed_selected_replicated_cpd4_solution_verification",
        "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": config["research_question"], "claim_boundary": config["claim_boundary"],
        "config_sha256": sha(config_path), "handoff_sha256": sha(handoff_path), "runner_sha256": sha(runner),
        "lineage_hashes": observed_lineage, "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu},
        "case_records": {row["case_id"]: row["record_sha256"] for row in results},
        "paired_results": results, "matched_clean_controls": {
            "n216_s1_reused": reused, "n216_s2_new_conductance_proxy_lu": clean_controls["n216_s2"]},
        "contrasts": contrasts,
        "descriptive_only": {"s1_A_cpd4_ratios_1_2_4": s1_sequence,
                             "strictly_decreasing_observed": s1_sequence[0] > s1_sequence[1] > s1_sequence[2],
                             "monotonicity_was_not_an_acceptance_gate": True},
        "checks": checks,
        "authority": {"independent_evaluation": True, "render": False,
                      "absolute_permeability_validation_claim": False, "mechanics_rerun": False,
                      "mobile_sand": False, "migration": False, "clogging": False,
                      "deformation": False, "transient_coupling": False, "two_way_coupling": False},
    }
    write(output / "completion.json", completion)
    print("STAGE31F_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
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
                write(failed / "failure.json", {
                    "schema": "lbs.stage31f-selected-replicated-cpd4.v1.failure", "status": "failed_preserved",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "termination_reason": str(exc),
                    "traceback": traceback.format_exc(),
                })
        raise
