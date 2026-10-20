"""Run the authorized Stage111 seed-2 clean CPD2 direct-flow validation."""
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    design_path, handoff_path, output = args.design.resolve(), args.handoff.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    design, handoff = read(design_path), read(handoff_path)
    if (design["status"] != "designed_independent_audit_required"
            or design["authority"]["gpu_execution"] is not False
            or handoff.get("status") != "stage111_gpu_execution_authorized"
            or handoff.get("passed") is not True
            or handoff["bindings"]["design_sha256"] != sha(design_path)
            or handoff["bindings"]["runner_sha256"] != sha(__file__)):
        raise RuntimeError("Stage111 design/handoff authorization failed")
    for item in design["lineage"].values():
        if isinstance(item, dict) and "path" in item and sha(item["path"]) != item["sha256"]:
            raise RuntimeError(f"lineage drift: {item['path']}")
    base = read(design["lineage"]["base_config"]["path"])
    stage27 = read(design["lineage"]["stage27_config"]["path"])
    adapter = copy.deepcopy(base)
    adapter["lineage"]["geometry_cpd2"] = design["geometry"]
    adapter["lineage"]["cuda_source"] = stage27["lineage"]["cuda_source"]["path"]
    adapter["lineage"]["qualified_ptx_sha256"] = design["lineage"]["qualified_ptx_sha256"]
    adapter["solver"].update(design["solver"])
    adapter["acceptance"].update(design["numerical_acceptance"])
    adapter["solver"].pop("local_field_warm_start", None)
    adapter["solver"].pop("exact_shifted_state_warm_start", None)
    adapter["solver"]["resampled_local_field_warm_start"] = {
        case["case_id"]: {
            "path": design["archived_field"],
            "sha256": design["lineage"]["archived_field"]["sha256"],
            "velocity_scale": case["warm_start_velocity_scale"],
            "density_deviation_scale": case["warm_start_density_deviation_scale"],
        } for case in design["cases"]
    }
    output.mkdir(parents=True, exist_ok=False)
    stage17.install_generic_mask_oracle()
    driver, build = stage17.create_driver(adapter, Path(design["execution"]["cuda_bin"]),
                                          int(design["execution"]["gpu_ordinal"]))
    records = []
    try:
        for case in design["cases"]:
            spec = {"case_id": case["case_id"], "stage": "STAGE111_FLOW_VALIDATION",
                    "cpd": 2, "acceleration_lu": case["initial_acceleration_lu"]}
            print("STAGE111_START=" + json.dumps({"case_id": case["case_id"],
                                                  "flow_factor": case["flow_factor"]}), flush=True)
            record = stage17.run_case(driver, adapter, spec, output)
            records.append(record)
            print("STAGE111_CASE=" + json.dumps({"case_id": case["case_id"],
                                                 "passed": record["passed"],
                                                 "steps": record["steps_completed"],
                                                 "wall_s": record["performance"]["wall_seconds"],
                                                 "u_superficial_lu": record["final"]["superficial_velocity_lu"]}),
                  flush=True)
    finally:
        driver.close()
    checks = {"three_records": len(records) == 3,
              "all_solver_records_passed": len(records) == 3 and all(r["passed"] for r in records),
              "no_particle_transport": all(r["stage"] == "STAGE111_FLOW_VALIDATION" for r in records),
              "increasing_achieved_velocity": all(records[i]["final"]["superficial_velocity_lu"] < records[i+1]["final"]["superficial_velocity_lu"] for i in range(2))}
    completion = {
        "schema": "matdem.stage111.flow-validation.gpu-completion.v1",
        "status": "complete_solver_passed_pending_independent_evaluation" if all(checks.values()) else "complete_solver_failed_preserved",
        "passed": all(checks.values()), "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "design_sha256": sha(design_path), "handoff_sha256": sha(handoff_path),
        "runner_sha256": sha(__file__), "checks": checks, "build": build,
        "environment": {"platform": platform.platform(), "python": sys.version},
        "case_records": {r["case_id"]: sha(output / r["case_id"] / "record.json") for r in records},
        "authority": {"independent_evaluation": True, "particle_transport": False, "campaign": False},
    }
    write(output / "completion.json", completion)
    print("STAGE111_COMPLETION=" + json.dumps(completion, sort_keys=True), flush=True)
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
