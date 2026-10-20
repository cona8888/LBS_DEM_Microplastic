#!/usr/bin/env python3
"""Run the released Stage34C eight-case fixed-volume fragmentation CPD4 study."""

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
    "s34c_n216_s2_A_p4_frag2_cpd4",
    "s34c_n216_s1_A_p4_frag2_cpd4",
    "s34c_n216_s2_B_p4_frag2_cpd4",
    "s34c_n216_s2_A_p4_frag3_cpd4",
    "s34c_n216_s1_B_p4_frag2_cpd4",
    "s34c_n216_s1_B_p4_frag3_cpd4",
    "s34c_n216_s2_B_p4_frag3_cpd4",
    "s34c_n216_s1_A_p4_frag3_cpd4",
)
ARTIFACT_NAMES = ("record.json", "audit.npz", "final_fields.npz", "final_shifted_state.npz", "final_flow.vtk")


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


def verify_binding(item: dict, label: str) -> None:
    path = Path(item["path"])
    if not path.is_file() or sha(path) != item["sha256"]:
        raise RuntimeError(f"immutable binding mismatch: {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    handoff_path = args.handoff.resolve()
    output = args.output.resolve()
    runner = Path(__file__).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    config, handoff = load(config_path), load(handoff_path)
    if (config.get("status") != "fragment_cpd4_configuration_frozen_independent_gpu_release_required"
            or config["authority"].get("gpu_cpd4_execution") is not False):
        raise RuntimeError("configuration is not the frozen Stage34C preflight")
    if not (handoff.get("passed") is True
            and handoff.get("status") == "stage34c_fragment_cpd4_gpu_execution_authorized"
            and handoff["authority"].get("gpu_cpd4_execution") is True):
        raise RuntimeError("independent Stage34C GPU release is absent")
    if handoff["bindings"]["config_sha256"] != sha(config_path) or handoff["bindings"]["runner_sha256"] != sha(runner):
        raise RuntimeError("handoff/config/runner hash mismatch")
    prohibited = (
        "absolute_permeability_validation_claim", "chemical_degradation_claim", "cpd6_flow_execution",
        "mechanics_rerun", "mobile_sand", "migration", "clogging", "deformation",
        "transient_coupling", "two_way_coupling",
    )
    if any(config["authority"].get(key, False) for key in prohibited):
        raise RuntimeError("authority boundary exceeded")

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
    if configured_order != ORDER:
        raise RuntimeError("frozen run order mismatch")

    output.mkdir(parents=True)
    adapter = copy.deepcopy(config)
    adapter["lineage"]["cuda_source"] = config["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = config["lineage"]["qualified_ptx_sha256"]
    adapter["solver"]["resampled_local_field_warm_start"] = {
        case_id: {key: value for key, value in item.items() if key in ("path", "sha256", "velocity_scale", "density_deviation_scale")}
        for case_id, item in config["warm_starts"].items()
    }
    stage17.install_generic_mask_oracle()
    driver, gpu = stage17.create_driver(adapter, Path(config["execution"]["cuda_bin"]), int(config["execution"]["gpu_ordinal"]))
    case_meta = {row["case_id"]: row for row in config["geometry"]["cases"]}
    results = []
    try:
        for ordinal, case_id in enumerate(ORDER, start=1):
            adapter["lineage"]["geometry_cpd4"] = config["geometry"]["artifacts"][case_id]["path"]
            specification = {
                "case_id": case_id,
                "stage": "STAGE34C_FIXED_VOLUME_FRAGMENTATION_CPD4_PARAMETRIC_STUDY",
                "cpd": 4,
                "acceleration_lu": float(config["solver"]["acceleration_lu"]),
            }
            print("STAGE34C_START=" + json.dumps({"ordinal": ordinal, "total": len(ORDER), "case_id": case_id}), flush=True)
            record = stage17.run_case(driver, adapter, specification, output)
            case_dir = output / case_id
            artifact_hashes = {name: sha(case_dir / name) for name in ARTIFACT_NAMES}
            meta = case_meta[case_id]
            conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
            context_id = f"{meta['packing_id']}_{meta['placement_block']}"
            clean = float(config["matched_clean_controls"][context_id]["conductance_proxy_lu"])
            ratio = conductance / clean
            result = {
                "case_id": case_id, "run_order": ordinal,
                "packing_id": meta["packing_id"], "placement_block": meta["placement_block"],
                "fragments_per_parent": int(meta["fragments_per_parent"]),
                "total_fragment_count": int(meta["total_fragment_count"]),
                "conductance_proxy_lu": conductance,
                "paired_permeability_ratio": ratio,
                "paired_relative_permeability_change": ratio - 1.0,
                "intrinsic_permeability_m2_descriptive_only": float(config["solver"]["kinematic_viscosity_lu"]) * conductance * float(config["geometry"]["artifacts"][case_id]["spacing_m"]) ** 2,
                "steps_completed": int(record["steps_completed"]),
                "record_passed": bool(record.get("passed") and all(record.get("checks", {}).values())),
                "artifact_sha256": artifact_hashes,
                "warm_start_source_intact_case_id": config["warm_starts"][case_id]["source_intact_case_id"],
            }
            results.append(result)
            print("STAGE34C_CASE=" + json.dumps(result, sort_keys=True), flush=True)
    finally:
        driver.close()

    result_by_id = {row["case_id"]: row for row in results}
    contrasts = {}
    contrast_vectors = {"frag2_minus_frag1": [], "frag3_minus_frag1": [], "frag3_minus_frag2": []}
    for context_id, intact in config["intact_contexts"].items():
        packing, block = intact["packing_id"], intact["placement_block"]
        frag1 = float(intact["paired_permeability_ratio"])
        frag2_id = f"s34c_{packing}_{block}_p4_frag2_cpd4"
        frag3_id = f"s34c_{packing}_{block}_p4_frag3_cpd4"
        frag2 = float(result_by_id[frag2_id]["paired_permeability_ratio"])
        frag3 = float(result_by_id[frag3_id]["paired_permeability_ratio"])
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
    descriptive_signs = {}
    for name, values in contrast_vectors.items():
        descriptive_signs[name] = {
            "values": values,
            "positive_count": sum(value > 0 for value in values),
            "negative_count": sum(value < 0 for value in values),
            "practical_count": sum(abs(value) >= threshold for value in values),
            "monotonicity_or_sign_not_an_acceptance_gate": True,
        }

    checks = {
        "exact_eight_records": len(results) == 8,
        "all_case_records_passed": len(results) == 8 and all(row["record_passed"] for row in results),
        "all_artifacts_present_and_hashed": all(len(row["artifact_sha256"]) == len(ARTIFACT_NAMES) for row in results),
        "finite_positive_conductance_and_ratio": all(
            math.isfinite(row["conductance_proxy_lu"]) and row["conductance_proxy_lu"] > 0
            and math.isfinite(row["paired_permeability_ratio"]) and row["paired_permeability_ratio"] > 0
            for row in results
        ),
        "all_twelve_contrasts_finite": sum(len(values) for values in contrast_vectors.values()) == 12
            and all(math.isfinite(value) for values in contrast_vectors.values() for value in values),
        "monotonicity_not_gated": config["analysis"]["monotonicity_imposed"] is False,
        "no_failure_marker": not (output / "failure.json").exists(),
    }
    passed = all(checks.values())
    completion = {
        "schema": config["schema"] + ".gpu-completion",
        "status": "passed_fragment_cpd4_parametric_run_pending_independent_evaluation" if passed else "failed_fragment_cpd4_parametric_run",
        "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": config["research_question"], "claim_boundary": config["claim_boundary"],
        "config_sha256": sha(config_path), "handoff_sha256": sha(handoff_path), "runner_sha256": sha(runner),
        "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu},
        "new_case_results": results, "reused_intact_contexts": config["intact_contexts"],
        "matched_clean_controls": config["matched_clean_controls"],
        "contrasts": contrasts, "descriptive_cross_context_signs": descriptive_signs,
        "checks": checks,
        "authority": {
            "independent_evaluation": False, "render": False, "cpd6_flow_execution": False,
            "absolute_permeability_validation_claim": False, "chemical_degradation_claim": False,
            "mechanics_rerun": False, "mobile_sand": False, "migration": False,
            "clogging": False, "deformation": False, "transient_coupling": False,
            "two_way_coupling": False,
        },
    }
    write(output / "completion.json", completion)
    print("STAGE34C_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
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
                    "schema": "lbs.stage34c-fragment-cpd4-gpu.v1.failure",
                    "status": "failed_preserved", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "termination_reason": str(exc), "traceback": traceback.format_exc(),
                })
        raise
