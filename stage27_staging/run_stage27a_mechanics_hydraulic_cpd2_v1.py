#!/usr/bin/env python3
"""Run the immutable Stage27a clean/open/deflected CPD2 GPU-LBM pilot."""

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


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    output.mkdir(parents=True)
    config = load(config_path)
    if config.get("status") != "geometry_preflight_passed_gpu_pilot_authorized" or not config["authority"]["gpu_cpd2_pilot"]:
        raise RuntimeError("Stage27a geometry handoff does not authorize the GPU pilot")

    observed = {}
    for key, binding in config["lineage"].items():
        if not isinstance(binding, dict) or "path" not in binding:
            continue
        path = Path(binding["path"])
        observed[key] = digest(path)
        if observed[key] != binding["sha256"]:
            raise RuntimeError(f"immutable lineage mismatch: {key}")
    geometry_completion = config_path.parent / "completion.json"
    geometry = load(geometry_completion)
    if not (geometry.get("passed") and all(geometry.get("checks", {}).values())):
        raise RuntimeError("Stage27a geometry completion is not a full pass")
    for case_id, artifact in config["geometry"]["artifacts"].items():
        if digest(Path(artifact["geometry"])) != artifact["geometry_sha256"]:
            raise RuntimeError(f"geometry hash mismatch: {case_id}")

    adapter = copy.deepcopy(config)
    adapter["lineage"]["cuda_source"] = config["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = config["lineage"]["qualified_ptx_sha256"]
    stage17.install_generic_mask_oracle()
    driver, gpu = stage17.create_driver(
        adapter,
        Path(config["execution"]["cuda_bin"]),
        int(config["execution"]["gpu_ordinal"]),
    )
    records, paired = [], []
    clean_conductance = None
    roles = {row["case_id"]: row["role"] for row in config["geometry"]["cases"]}
    try:
        for ordinal, case_id in enumerate(("clean", "open", "constricted"), start=1):
            artifact = config["geometry"]["artifacts"][case_id]
            adapter["lineage"]["geometry_cpd2"] = artifact["geometry"]
            specification = {
                "case_id": f"stage27a_{case_id}_cpd2",
                "stage": "STAGE27A_STAGE26X_MECHANICS_HYDRAULIC_BRIDGE",
                "cpd": 2,
                "acceleration_lu": float(config["solver"]["acceleration_lu"]),
            }
            print("STAGE27A_START=" + json.dumps({"ordinal": ordinal, "total": 3, "case_id": case_id}), flush=True)
            record = stage17.run_case(driver, adapter, specification, output)
            records.append(record)
            conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
            if case_id == "clean":
                clean_conductance = conductance
            if clean_conductance is None:
                raise RuntimeError("clean control must execute first")
            permeability_lu2 = float(config["solver"]["kinematic_viscosity_lu"]) * conductance
            spacing = float(config["geometry"]["spacing_m"])
            permeability_m2 = permeability_lu2 * spacing * spacing
            fluid = config["fluid"]
            conductivity = permeability_m2 * float(fluid["density_kg_m3"]) * float(fluid["gravity_m_s2"]) / float(fluid["dynamic_viscosity_pa_s"])
            row = {
                "case_id": case_id,
                "solver_case_id": specification["case_id"],
                "role": roles[case_id],
                "conductance_proxy_lu": conductance,
                "paired_clean_conductance_proxy_lu": clean_conductance,
                "paired_permeability_ratio": conductance / clean_conductance,
                "paired_relative_permeability_change": conductance / clean_conductance - 1.0,
                "intrinsic_permeability_m2": permeability_m2,
                "hydraulic_conductivity_at_20c_m_s": conductivity,
                "steps_completed": int(record["steps_completed"]),
                "record_sha256": digest(output / specification["case_id"] / "record.json"),
                "record_passed": bool(record.get("passed") and all(record.get("checks", {}).values())),
            }
            paired.append(row)
            print("STAGE27A_CASE=" + json.dumps(row, sort_keys=True), flush=True)
    finally:
        driver.close()

    checks = {
        "three_records": len(records) == 3,
        "all_records_passed": len(paired) == 3 and all(row["record_passed"] for row in paired),
        "finite_positive_conductance": all(math.isfinite(row["conductance_proxy_lu"]) and row["conductance_proxy_lu"] > 0 for row in paired),
        "finite_positive_permeability": all(math.isfinite(row["intrinsic_permeability_m2"]) and row["intrinsic_permeability_m2"] > 0 for row in paired),
        "clean_ratio_exact": paired[0]["paired_permeability_ratio"] == 1.0,
        "immutable_sand_pairing": len({row["sand_voxel_count"] for row in config["geometry"]["cases"]}) == 1,
    }
    passed = all(checks.values())
    completion = {
        "schema": config["schema"] + ".gpu-completion",
        "status": "passed_three_case_cpd2_pilot" if passed else "failed_three_case_cpd2_pilot",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": config["research_question"],
        "claim_boundary": config["claim_boundary"],
        "config_sha256": digest(config_path),
        "geometry_completion_sha256": digest(geometry_completion),
        "runner_sha256": digest(Path(__file__).resolve()),
        "lineage_hashes": observed,
        "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu},
        "case_records": {row["case_id"]: row["record_sha256"] for row in paired},
        "paired_results": paired,
        "checks": checks,
        "authority": {"independent_evaluation": True, "render": False, "cpd4": False, "concentration_campaign": False, "mobile_sand": False, "two_way_coupling": False},
        "decision": "If independently verified, render the three-case mechanics-to-hydraulics contrast before considering any multi-fibre design.",
    }
    write_json(output / "completion.json", completion)
    print("STAGE27A_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
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
                write_json(failed / "failure.json", {
                    "schema": "lbs.stage27a-stage26x-mechanics-hydraulic-bridge.v1.failure",
                    "status": "failed_preserved",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "termination_reason": str(exc),
                    "traceback": traceback.format_exc(),
                })
        raise

