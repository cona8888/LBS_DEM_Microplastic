#!/usr/bin/env python3
"""Run the released 21-case Stage31e replicated nested CPD2 GPU screen."""
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


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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
    if config.get("status") != "geometry_built_independent_audit_required" or config["authority"].get("gpu_execution") is not False:
        raise RuntimeError("configuration is not the fail-closed Stage31d geometry checkpoint")
    if not (handoff.get("passed") is True and handoff.get("status") == "stage31e_replicated_nested_cpd2_gpu_execution_authorized" and handoff["authority"].get("gpu_execution") is True):
        raise RuntimeError("independent Stage31e GPU handoff is absent")
    if handoff["bindings"]["config_sha256"] != sha(config_path) or handoff["bindings"]["runner_sha256"] != sha(runner):
        raise RuntimeError("GPU handoff hash mismatch")
    if any(config["authority"].get(name, False) for name in ("cpd4", "permeability_claim", "mobile_sand", "coupling")):
        raise RuntimeError("authority boundary exceeded")
    observed = {}
    for name, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            observed[name] = sha(path)
            if observed[name] != binding["sha256"]:
                raise RuntimeError("lineage mismatch: " + name)
    geometry_completion_path = config_path.parent / "completion.json"
    geometry_completion = load(geometry_completion_path)
    if not (geometry_completion.get("passed") and all(geometry_completion["checks"].values()) and geometry_completion["config_sha256"] == sha(config_path)):
        raise RuntimeError("geometry completion is not bound")
    for case_id, artifact in config["geometry"]["artifacts"].items():
        if sha(Path(artifact["geometry"])) != artifact["geometry_sha256"]:
            raise RuntimeError("geometry mismatch: " + case_id)
    stage27 = load(Path(config["lineage"]["stage27_solver_config"]["path"]))
    adapter = copy.deepcopy(config)
    adapter["lineage"]["cuda_source"] = stage27["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = stage27["lineage"]["qualified_ptx_sha256"]
    output.mkdir(parents=True)
    stage17.install_generic_mask_oracle()
    driver, gpu = stage17.create_driver(adapter, Path(config["execution"]["cuda_bin"]), int(config["execution"]["gpu_ordinal"]))
    schedule = sorted(config["geometry"]["cases"], key=lambda row: int(row["flow_order"]))
    records, paired, clean_conductance = [], [], {}
    try:
        for ordinal, row in enumerate(schedule, start=1):
            case_id = row["case_id"]
            geometry = config["geometry"]["artifacts"][case_id]["geometry"]
            adapter["lineage"]["geometry_cpd2"] = geometry
            spec = {
                "case_id": f"stage31e_{case_id}_cpd2",
                "stage": "STAGE31E_REPLICATED_NESTED_CPD2",
                "cpd": 2,
                "acceleration_lu": float(config["solver"]["acceleration_lu"]),
            }
            print("STAGE31E_START=" + json.dumps({"ordinal": ordinal, "total": len(schedule), "case_id": case_id}), flush=True)
            record = stage17.run_case(driver, adapter, spec, output)
            records.append(record)
            conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
            if int(row["fibre_count"]) == 0:
                clean_conductance[row["packing_id"]] = conductance
            if row["packing_id"] not in clean_conductance:
                raise RuntimeError("matched packing clean control must precede fibre cases")
            matched_clean = clean_conductance[row["packing_id"]]
            permeability_lu2 = float(config["solver"]["kinematic_viscosity_lu"]) * conductance
            permeability_m2 = permeability_lu2 * float(row["spacing_m"]) ** 2
            fluid = config["fluid"]
            conductivity = permeability_m2 * float(fluid["density_kg_m3"]) * float(fluid["gravity_m_s2"]) / float(fluid["dynamic_viscosity_pa_s"])
            result = {
                "case_id": case_id,
                "flow_order": int(row["flow_order"]),
                "packing_id": row["packing_id"],
                "placement_block": row["placement_block"],
                "fibre_count": int(row["fibre_count"]),
                "achieved_dry_mass_percent": float(row["achieved_dry_mass_percent"]),
                "solver_case_id": spec["case_id"],
                "conductance_proxy_lu": conductance,
                "matched_clean_conductance_proxy_lu": matched_clean,
                "paired_permeability_ratio": conductance / matched_clean,
                "paired_relative_permeability_change": conductance / matched_clean - 1.0,
                "intrinsic_permeability_m2": permeability_m2,
                "hydraulic_conductivity_at_20c_m_s": conductivity,
                "steps_completed": int(record["steps_completed"]),
                "record_sha256": sha(output / spec["case_id"] / "record.json"),
                "record_passed": bool(record.get("passed") and all(record.get("checks", {}).values())),
            }
            paired.append(result)
            print("STAGE31E_CASE=" + json.dumps(result, sort_keys=True), flush=True)
    finally:
        driver.close()
    clean_rows = [item for item in paired if item["fibre_count"] == 0]
    checks = {
        "twenty_one_records": len(records) == len(paired) == 21,
        "all_records_passed": len(paired) == 21 and all(item["record_passed"] for item in paired),
        "finite_positive_conductance": all(math.isfinite(item["conductance_proxy_lu"]) and item["conductance_proxy_lu"] > 0.0 for item in paired),
        "finite_positive_permeability": all(math.isfinite(item["intrinsic_permeability_m2"]) and item["intrinsic_permeability_m2"] > 0.0 for item in paired),
        "three_clean_ratios_exact": len(clean_rows) == 3 and all(item["paired_permeability_ratio"] == 1.0 for item in clean_rows),
        "frozen_flow_order": [item["flow_order"] for item in paired] == list(range(1, 22)),
        "matched_clean_available": set(clean_conductance) == {"n216_s1", "n216_s2", "n216_s3"},
        "immutable_sand_within_packing": all(len({row["sand_voxel_count"] for row in config["geometry"]["cases"] if row["packing_id"] == packing}) == 1 for packing in clean_conductance),
    }
    passed = all(checks.values())
    completion = {
        "schema": "lbs.stage31e-replicated-nested-cpd2-gpu-completion.v1",
        "status": "passed_twenty_one_case_cpd2_screen" if passed else "failed_twenty_one_case_cpd2_screen",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": config["research_question"],
        "claim_boundary": config["claim_boundary"],
        "config_sha256": sha(config_path),
        "handoff_sha256": sha(handoff_path),
        "geometry_completion_sha256": sha(geometry_completion_path),
        "runner_sha256": sha(runner),
        "lineage_hashes": observed,
        "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu},
        "case_records": {item["case_id"]: item["record_sha256"] for item in paired},
        "paired_results": paired,
        "checks": checks,
        "authority": {"independent_evaluation": True, "render": False, "cpd4": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
    }
    write(output / "completion.json", completion)
    print("STAGE31E_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
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
                write(failed / "failure.json", {"schema": "lbs.stage31e-replicated-nested-cpd2.failure.v1", "status": "failed_preserved", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "termination_reason": str(exc), "traceback": traceback.format_exc()})
        raise
