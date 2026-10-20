"""Run the authorized Stage112 clean reference-flow verification cases."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration\scripts")
sys.path.insert(0, str(EXTERNAL))
import stage17_relaxed_fibre_gpu_lbm_run as stage17


def sha(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    design_path, handoff_path, output = args.design.resolve(), args.handoff.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    design, handoff = read(design_path), read(handoff_path)
    if (design.get("status") != "designed_independent_audit_required"
            or design.get("authority", {}).get("gpu_execution") is not False
            or handoff.get("status") != "stage112_gpu_execution_authorized"
            or handoff.get("passed") is not True
            or handoff.get("bindings", {}).get("design_sha256") != sha(design_path)
            or handoff.get("bindings", {}).get("runner_sha256") != sha(__file__)):
        raise RuntimeError("Stage112 design/handoff authorization failed")
    for item in design["lineage"].values():
        if isinstance(item, dict) and "path" in item and sha(item["path"]) != item["sha256"]:
            raise RuntimeError(f"lineage drift: {item['path']}")

    base = read(design["lineage"]["base_cpd2_config"]["path"])
    stage27 = read(design["lineage"]["stage27_config"]["path"])
    adapter = copy.deepcopy(base)
    adapter["lineage"]["cuda_source"] = stage27["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = design["lineage"]["qualified_ptx_sha256"]
    adapter["solver"].update(design["solver"])
    adapter["acceptance"].update(design["numerical_acceptance"])
    adapter["solver"].pop("local_field_warm_start", None)
    adapter["solver"].pop("exact_shifted_state_warm_start", None)
    adapter["solver"]["resampled_local_field_warm_start"] = {
        case["case_id"]: dict(case["warm_start"]) for case in design["cases"]
    }

    output.mkdir(parents=True, exist_ok=False)
    stage17.install_generic_mask_oracle()
    driver, build = stage17.create_driver(adapter, Path(design["execution"]["cuda_bin"]),
                                          int(design["execution"]["gpu_ordinal"]))
    records = []
    try:
        for case in design["cases"]:
            adapter["lineage"][f"geometry_cpd{case['cpd']}"] = case["geometry"]
            spec = {"case_id": case["case_id"], "stage": "STAGE112_FLOW_RESOLUTION_PACKING",
                    "cpd": int(case["cpd"]), "acceleration_lu": case["initial_acceleration_lu"]}
            print("STAGE112_START=" + json.dumps({"case_id": case["case_id"], "cpd": case["cpd"],
                                                   "packing_seed": case["packing_seed"]}), flush=True)
            record = stage17.run_case(driver, adapter, spec, output)
            records.append(record)
            print("STAGE112_CASE=" + json.dumps({"case_id": case["case_id"], "passed": record["passed"],
                                                  "steps": record["steps_completed"],
                                                  "wall_s": record["performance"]["wall_seconds"],
                                                  "u_superficial_lu": record["final"]["superficial_velocity_lu"]}),
                  flush=True)
    finally:
        driver.close()

    checks = {
        "three_records": len(records) == 3,
        "all_solver_records_passed": len(records) == 3 and all(r["passed"] for r in records),
        "exact_case_order": [r["case_id"] for r in records] == [c["case_id"] for c in design["cases"]],
        "cpd_pattern": [r["cpd"] for r in records] == [2, 2, 4],
        "no_particle_transport": all(r["stage"] == "STAGE112_FLOW_RESOLUTION_PACKING" for r in records),
    }
    completion = {
        "schema": "matdem.stage112.flow-resolution-packing.gpu-completion.v1",
        "status": "complete_solver_passed_pending_independent_evaluation" if all(checks.values()) else "complete_solver_failed_preserved",
        "passed": all(checks.values()), "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "design_sha256": sha(design_path), "handoff_sha256": sha(handoff_path),
        "runner_sha256": sha(__file__), "checks": checks, "build": build,
        "environment": {"platform": platform.platform(), "python": sys.version},
        "case_records": {r["case_id"]: sha(output / r["case_id"] / "record.json") for r in records},
        "authority": {"independent_evaluation": True, "particle_transport": False, "campaign": False},
    }
    write(output / "completion.json", completion)
    print("STAGE112_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
    return 0 if completion["passed"] else 4


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        if "--output" in sys.argv:
            output = Path(sys.argv[sys.argv.index("--output") + 1]).resolve()
            if output.exists() and not (output / "failure.json").exists():
                write(output / "failure.json", {"status": "failed_preserved",
                                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                                "termination_reason": str(exc),
                                                "traceback": traceback.format_exc()})
        raise
