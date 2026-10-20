#!/usr/bin/env python3
"""Recover Stage34C by running only the six unfinished CPD4 cases."""

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

FULL_ORDER = (
    "s34c_n216_s2_A_p4_frag2_cpd4",
    "s34c_n216_s1_A_p4_frag2_cpd4",
    "s34c_n216_s2_B_p4_frag2_cpd4",
    "s34c_n216_s2_A_p4_frag3_cpd4",
    "s34c_n216_s1_B_p4_frag2_cpd4",
    "s34c_n216_s1_B_p4_frag3_cpd4",
    "s34c_n216_s2_B_p4_frag3_cpd4",
    "s34c_n216_s1_A_p4_frag3_cpd4",
)
REUSED_ORDER = FULL_ORDER[:2]
RECOVERY_ORDER = FULL_ORDER[2:]
ARTIFACT_NAMES = ("record.json", "audit.npz", "final_fields.npz", "final_shifted_state.npz", "final_flow.vtk")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def verify_binding(item: dict, label: str) -> None:
    path = Path(item["path"])
    if not path.is_file() or sha(path) != item["sha256"]:
        raise RuntimeError(f"immutable binding mismatch: {label}")


def record_passed(record: dict) -> bool:
    return bool(record.get("passed")) and bool(record.get("checks")) and all(
        value is True for value in record["checks"].values()
    )


def result_from_record(config: dict, case_id: str, record: dict, artifacts: dict[str, str], source: str) -> dict:
    case_meta = {row["case_id"]: row for row in config["geometry"]["cases"]}[case_id]
    conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
    context_id = f"{case_meta['packing_id']}_{case_meta['placement_block']}"
    clean = float(config["matched_clean_controls"][context_id]["conductance_proxy_lu"])
    ratio = conductance / clean
    return {
        "case_id": case_id,
        "run_order": int(case_meta["run_order"]),
        "result_source": source,
        "packing_id": case_meta["packing_id"],
        "placement_block": case_meta["placement_block"],
        "fragments_per_parent": int(case_meta["fragments_per_parent"]),
        "total_fragment_count": int(case_meta["total_fragment_count"]),
        "conductance_proxy_lu": conductance,
        "paired_permeability_ratio": ratio,
        "paired_relative_permeability_change": ratio - 1.0,
        "intrinsic_permeability_m2_descriptive_only": float(config["solver"]["kinematic_viscosity_lu"])
            * conductance * float(config["geometry"]["artifacts"][case_id]["spacing_m"]) ** 2,
        "steps_completed": int(record["steps_completed"]),
        "record_passed": record_passed(record),
        "artifact_sha256": artifacts,
        "warm_start_source_intact_case_id": config["warm_starts"][case_id]["source_intact_case_id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path, handoff_path, output = args.config.resolve(), args.handoff.resolve(), args.output.resolve()
    runner = Path(__file__).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable recovery output: {output}")
    config, handoff = load(config_path), load(handoff_path)
    if config.get("status") != "fragment_cpd4_configuration_frozen_independent_gpu_release_required":
        raise RuntimeError("original frozen Stage34C configuration is invalid")
    if not (handoff.get("passed") is True
            and handoff.get("status") == "stage34c_fragment_cpd4_recovery_gpu_execution_authorized"
            and handoff.get("authority", {}).get("one_six_case_recovery_only") is True):
        raise RuntimeError("independent Stage34C recovery release is absent")
    if handoff["bindings"]["config_sha256"] != sha(config_path) or handoff["bindings"]["runner_sha256"] != sha(runner):
        raise RuntimeError("recovery handoff/config/runner hash mismatch")
    if tuple(handoff["full_order"]) != FULL_ORDER or tuple(handoff["reused_order"]) != REUSED_ORDER \
            or tuple(handoff["recovery_order"]) != RECOVERY_ORDER:
        raise RuntimeError("recovery order mismatch")

    prohibited = (
        "absolute_permeability_validation_claim", "chemical_degradation_claim", "cpd6_flow_execution",
        "mechanics_rerun", "mobile_sand", "migration", "clogging", "deformation",
        "transient_coupling", "two_way_coupling",
    )
    if any(handoff["authority"].get(key, False) for key in prohibited):
        raise RuntimeError("recovery authority boundary exceeded")
    for key, item in config["lineage"].items():
        if isinstance(item, dict) and "path" in item and "sha256" in item:
            verify_binding(item, f"lineage/{key}")
    for case_id, item in config["geometry"]["artifacts"].items():
        verify_binding(item, f"geometry/{case_id}")
    for case_id, item in config["warm_starts"].items():
        verify_binding(item, f"warm_start/{case_id}")
    for context_id, item in config["intact_contexts"].items():
        verify_binding(item["geometry"], f"intact/{context_id}/geometry")
        for name, artifact in item["artifacts"].items():
            verify_binding(artifact, f"intact/{context_id}/{name}")
    for context_id, item in config["matched_clean_controls"].items():
        for name in ("record", "geometry", "completion", "evaluation"):
            verify_binding(item[name], f"clean/{context_id}/{name}")

    configured_order = tuple(row["case_id"] for row in sorted(config["geometry"]["cases"], key=lambda row: row["run_order"]))
    if configured_order != FULL_ORDER:
        raise RuntimeError("frozen full run order mismatch")

    results: list[dict] = []
    for case_id in REUSED_ORDER:
        bundle = handoff["completed_case_bundles"][case_id]
        case_dir = Path(bundle["path"])
        actual = {}
        for name in ARTIFACT_NAMES:
            path = case_dir / name
            digest = sha(path)
            if digest != bundle["artifact_sha256"][name]:
                raise RuntimeError(f"reused artifact hash mismatch: {case_id}/{name}")
            actual[name] = digest
        results.append(result_from_record(config, case_id, load(case_dir / "record.json"), actual, "reused_interrupted_gpu_confirmation_01"))

    output.mkdir(parents=True)
    adapter = copy.deepcopy(config)
    adapter["lineage"]["cuda_source"] = config["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = config["lineage"]["qualified_ptx_sha256"]
    adapter["solver"]["resampled_local_field_warm_start"] = {
        case_id: {key: value for key, value in item.items()
                  if key in ("path", "sha256", "velocity_scale", "density_deviation_scale")}
        for case_id, item in config["warm_starts"].items()
    }
    stage17.install_generic_mask_oracle()
    driver, gpu = stage17.create_driver(adapter, Path(config["execution"]["cuda_bin"]), int(config["execution"]["gpu_ordinal"]))
    try:
        for recovery_ordinal, case_id in enumerate(RECOVERY_ORDER, start=1):
            adapter["lineage"]["geometry_cpd4"] = config["geometry"]["artifacts"][case_id]["path"]
            specification = {
                "case_id": case_id,
                "stage": "STAGE34C_FIXED_VOLUME_FRAGMENTATION_CPD4_INTERRUPTION_RECOVERY",
                "cpd": 4,
                "acceleration_lu": float(config["solver"]["acceleration_lu"]),
            }
            print("STAGE34C_RECOVERY_START=" + json.dumps({
                "recovery_ordinal": recovery_ordinal, "recovery_total": len(RECOVERY_ORDER),
                "original_run_order": FULL_ORDER.index(case_id) + 1, "case_id": case_id,
            }), flush=True)
            record = stage17.run_case(driver, adapter, specification, output)
            case_dir = output / case_id
            artifact_hashes = {name: sha(case_dir / name) for name in ARTIFACT_NAMES}
            result = result_from_record(config, case_id, record, artifact_hashes, "new_gpu_confirmation_02_recovery")
            results.append(result)
            print("STAGE34C_RECOVERY_CASE=" + json.dumps(result, sort_keys=True), flush=True)
    finally:
        driver.close()

    results.sort(key=lambda row: row["run_order"])
    result_by_id = {row["case_id"]: row for row in results}
    contrasts = {}
    contrast_vectors = {"frag2_minus_frag1": [], "frag3_minus_frag1": [], "frag3_minus_frag2": []}
    for context_id, intact in config["intact_contexts"].items():
        packing, block = intact["packing_id"], intact["placement_block"]
        frag1 = float(intact["paired_permeability_ratio"])
        frag2 = float(result_by_id[f"s34c_{packing}_{block}_p4_frag2_cpd4"]["paired_permeability_ratio"])
        frag3 = float(result_by_id[f"s34c_{packing}_{block}_p4_frag3_cpd4"]["paired_permeability_ratio"])
        row = {
            "packing_id": packing, "placement_block": block,
            "frag1_intact_ratio": frag1, "frag2_ratio": frag2, "frag3_ratio": frag3,
            "frag2_minus_frag1": frag2 - frag1,
            "frag3_minus_frag1": frag3 - frag1,
            "frag3_minus_frag2": frag3 - frag2,
        }
        contrasts[context_id] = row
        for name in contrast_vectors:
            contrast_vectors[name].append(float(row[name]))

    threshold = float(config["analysis"]["practical_selection_threshold_absolute_ratio"])
    descriptive_signs = {
        name: {
            "values": values,
            "positive_count": sum(value > 0 for value in values),
            "negative_count": sum(value < 0 for value in values),
            "practical_count": sum(abs(value) >= threshold for value in values),
            "monotonicity_or_sign_not_an_acceptance_gate": True,
        }
        for name, values in contrast_vectors.items()
    }
    checks = {
        "full_frozen_order_reconstructed": tuple(row["case_id"] for row in results) == FULL_ORDER,
        "exact_two_reused_and_six_new": sum(row["result_source"].startswith("reused") for row in results) == 2
            and sum(row["result_source"].startswith("new") for row in results) == 6,
        "all_eight_case_records_passed": len(results) == 8 and all(row["record_passed"] for row in results),
        "all_forty_artifacts_present_and_hashed": len(results) == 8
            and all(len(row["artifact_sha256"]) == len(ARTIFACT_NAMES) for row in results),
        "finite_positive_conductance_and_ratio": all(
            math.isfinite(row["conductance_proxy_lu"]) and row["conductance_proxy_lu"] > 0
            and math.isfinite(row["paired_permeability_ratio"]) and row["paired_permeability_ratio"] > 0
            for row in results
        ),
        "all_twelve_contrasts_finite": sum(len(values) for values in contrast_vectors.values()) == 12
            and all(math.isfinite(value) for values in contrast_vectors.values() for value in values),
        "monotonicity_not_gated": config["analysis"]["monotonicity_imposed"] is False,
        "no_recovery_failure_marker": not (output / "failure.json").exists(),
    }
    passed = all(checks.values())
    completion = {
        "schema": "lbs.stage34c-fragment-cpd4-gpu-recovery.v1.completion",
        "status": "passed_fragment_cpd4_recovery_pending_independent_evaluation" if passed else "failed_fragment_cpd4_recovery",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": config["research_question"], "claim_boundary": config["claim_boundary"],
        "config_sha256": sha(config_path), "handoff_sha256": sha(handoff_path), "runner_sha256": sha(runner),
        "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu},
        "case_results": results,
        "reused_original_case_count": 2, "new_recovery_case_count": 6,
        "reused_intact_contexts": config["intact_contexts"],
        "matched_clean_controls": config["matched_clean_controls"],
        "contrasts": contrasts, "descriptive_cross_context_signs": descriptive_signs,
        "checks": checks,
        "authority": {
            "independent_evaluation": passed, "render": False, "cpd6_flow_execution": False,
            "absolute_permeability_validation_claim": False, "chemical_degradation_claim": False,
            "mechanics_rerun": False, "mobile_sand": False, "migration": False,
            "clogging": False, "deformation": False, "transient_coupling": False,
            "two_way_coupling": False,
        },
    }
    write(output / "completion.json", completion)
    print("STAGE34C_RECOVERY_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
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
                    "schema": "lbs.stage34c-fragment-cpd4-gpu-recovery.v1.failure",
                    "status": "failed_preserved", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "termination_reason": str(exc), "traceback": traceback.format_exc(),
                })
        raise
