#!/usr/bin/env python3
"""Run the released Stage29e clean plus eleven mechanics-qualified CPD2 GPU cases."""
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
    if config.get("status") != "geometry_built_independent_gpu_release_required" or config["authority"].get("gpu_execution") is not False:
        raise RuntimeError("configuration is not a fail-closed Stage29e geometry checkpoint")
    if not (handoff.get("passed") is True and handoff.get("status") == "stage29e_cpd2_gpu_execution_authorized" and handoff["authority"].get("gpu_cpd2_execution") is True):
        raise RuntimeError("independent GPU handoff absent")
    if handoff["bindings"]["config_sha256"] != sha(config_path) or handoff["bindings"]["runner_sha256"] != sha(runner):
        raise RuntimeError("handoff hash mismatch")
    if any(config["authority"].get(k, False) for k in ("cpd4", "permeability_claim", "mechanics_rerun", "mobile_sand", "two_way_coupling")):
        raise RuntimeError("authority boundary exceeded")
    observed = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"]); observed[key] = sha(path)
            if observed[key] != binding["sha256"]:
                raise RuntimeError("lineage mismatch: " + key)
    completion_path = config_path.parent / "completion.json"
    geometry_completion = load(completion_path)
    if not (geometry_completion.get("passed") and all(geometry_completion["checks"].values()) and geometry_completion["config_sha256"] == sha(config_path)):
        raise RuntimeError("geometry completion not bound")
    for cid, artifact in config["geometry"]["artifacts"].items():
        if sha(Path(artifact["geometry"])) != artifact["geometry_sha256"]:
            raise RuntimeError("geometry mismatch: " + cid)
    if sha(Path(config["clean_control"]["geometry"])) != config["clean_control"]["geometry_sha256"]:
        raise RuntimeError("clean geometry mismatch")

    output.mkdir(parents=True)
    adapter = copy.deepcopy(config)
    adapter["lineage"]["cuda_source"] = config["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = config["lineage"]["qualified_ptx_sha256"]
    stage17.install_generic_mask_oracle()
    driver, gpu = stage17.create_driver(adapter, Path(config["execution"]["cuda_bin"]), int(config["execution"]["gpu_ordinal"]))
    ordered = sorted(config["geometry"]["cases"], key=lambda x: x["run_order"])
    schedule = [{"case_id": "clean", "run_order": 0, "fibre_count": 0, "topology": "clean", "block": "clean", "geometry": config["clean_control"]["geometry"]}] + [{**row, "geometry": config["geometry"]["artifacts"][row["case_id"]]["geometry"]} for row in ordered]
    records, paired, clean_conductance = [], [], None
    try:
        for ordinal, row in enumerate(schedule, 1):
            cid = row["case_id"]
            adapter["lineage"]["geometry_cpd2"] = row["geometry"]
            spec = {"case_id": f"stage29e_{cid}_cpd2", "stage": "STAGE29E_LOW_CONCENTRATION_MECHANICS_QUALIFIED", "cpd": 2, "acceleration_lu": float(config["solver"]["acceleration_lu"])}
            print("STAGE29E_START=" + json.dumps({"ordinal": ordinal, "total": len(schedule), "case_id": cid}), flush=True)
            record = stage17.run_case(driver, adapter, spec, output); records.append(record)
            conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
            if cid == "clean": clean_conductance = conductance
            if clean_conductance is None:
                raise RuntimeError("clean must run first")
            k_lu2 = float(config["solver"]["kinematic_viscosity_lu"]) * conductance
            k_m2 = k_lu2 * float(config["geometry"]["spacing_m"]) ** 2
            fluid = config["fluid"]
            conductivity = k_m2 * float(fluid["density_kg_m3"]) * float(fluid["gravity_m_s2"]) / float(fluid["dynamic_viscosity_pa_s"])
            result = {"case_id": cid, "run_order": row["run_order"], "fibre_count": row["fibre_count"], "topology": row["topology"], "block": row["block"], "solver_case_id": spec["case_id"], "conductance_proxy_lu": conductance, "paired_clean_conductance_proxy_lu": clean_conductance, "paired_permeability_ratio": conductance / clean_conductance, "paired_relative_permeability_change": conductance / clean_conductance - 1.0, "intrinsic_permeability_m2": k_m2, "hydraulic_conductivity_at_20c_m_s": conductivity, "steps_completed": int(record["steps_completed"]), "record_sha256": sha(output / spec["case_id"] / "record.json"), "record_passed": bool(record.get("passed") and all(record.get("checks", {}).values()))}
            paired.append(result)
            print("STAGE29E_CASE=" + json.dumps(result, sort_keys=True), flush=True)
    finally:
        driver.close()
    checks = {"twelve_records": len(records) == 12 and len(paired) == 12, "all_records_passed": len(paired) == 12 and all(x["record_passed"] for x in paired), "finite_positive_conductance": all(math.isfinite(x["conductance_proxy_lu"]) and x["conductance_proxy_lu"] > 0 for x in paired), "finite_positive_permeability": all(math.isfinite(x["intrinsic_permeability_m2"]) and x["intrinsic_permeability_m2"] > 0 for x in paired), "clean_ratio_exact": paired[0]["paired_permeability_ratio"] == 1.0, "frozen_case_order": [x["run_order"] for x in paired] == list(range(12)), "immutable_sand_pairing": len({x["sand_voxel_count"] for x in config["geometry"]["cases"]}) == 1}
    passed = all(checks.values())
    completion = {"schema": config["schema"] + ".gpu-completion", "status": "passed_twelve_case_cpd2_screen" if passed else "failed_twelve_case_cpd2_screen", "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "research_question": config["research_question"], "claim_boundary": config["claim_boundary"], "config_sha256": sha(config_path), "handoff_sha256": sha(handoff_path), "geometry_completion_sha256": sha(completion_path), "runner_sha256": sha(runner), "lineage_hashes": observed, "environment": {"platform": platform.platform(), "python": sys.version, "gpu": gpu}, "case_records": {x["case_id"]: x["record_sha256"] for x in paired}, "paired_results": paired, "checks": checks, "authority": {"independent_evaluation": True, "render": False, "cpd4": False, "permeability_claim": False, "mechanics_rerun": False, "mobile_sand": False, "two_way_coupling": False}}
    write(output / "completion.json", completion)
    print("STAGE29E_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
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
                write(failed / "failure.json", {"schema": "lbs.stage29e-low-concentration-cpd2-hydraulic.v1.failure", "status": "failed_preserved", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "termination_reason": str(exc), "traceback": traceback.format_exc()})
        raise
