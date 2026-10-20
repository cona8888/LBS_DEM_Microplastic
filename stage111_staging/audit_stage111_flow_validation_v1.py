"""Independent pre-execution audit for the Stage111 GPU flow validation."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "stage111_designs/seed2_clean_physical_re_flow_validation_20260915/design_01/resolved_design.json"
DESIGN_COMPLETION = DESIGN.with_name("completion.json")
RUNNER = ROOT / "stage111_staging/run_stage111_flow_validation_gpu_v1.py"
OUT = ROOT / "stage111_evaluations/seed2_clean_physical_re_flow_validation_20260915/pre_execution_audit_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    design, completion = read(DESIGN), read(DESIGN_COMPLETION)
    checks = {
        "design_hash_bound": completion["design_sha256"] == sha(DESIGN),
        "design_requires_audit": design["status"] == "designed_independent_audit_required",
        "gpu_initially_disabled": design["authority"]["gpu_execution"] is False,
        "one_clean_seed2_geometry": design["packing_seed"] == 2 and design["cpd"] == 2,
        "three_frozen_flows": [c["flow_factor"] for c in design["cases"]] == [0.5, 1.0, 2.0],
        "positive_increasing_accelerations": all(c["initial_acceleration_lu"] > 0 for c in design["cases"]) and all(design["cases"][i]["initial_acceleration_lu"] < design["cases"][i+1]["initial_acceleration_lu"] for i in range(2)),
        "finite_bounded_target_mach": max(c["target_mean_interstitial_velocity_lu"] * 3**0.5 for c in design["cases"]) < design["numerical_acceptance"]["maximum_mach_number"],
        "no_particle_or_campaign_authority": design["authority"]["particle_transport"] is False and design["authority"]["campaign"] is False,
        "runner_exists": RUNNER.is_file(),
        "immutable_output_required": "refusing to overwrite immutable output" in RUNNER.read_text(),
        "scaled_archive_is_only_warm_start": "resampled_local_field_warm_start" in RUNNER.read_text(),
        "failure_preservation_present": "failed_preserved" in RUNNER.read_text(),
    }
    lineage = {}
    for name, item in design["lineage"].items():
        if isinstance(item, dict) and "path" in item:
            lineage[name] = sha(item["path"])
            checks["lineage_" + name] = lineage[name] == item["sha256"]
    passed = all(checks.values())
    result = {"status": "stage111_gpu_execution_authorized" if passed else "stage111_gpu_execution_not_authorized",
              "passed": passed, "checks": checks, "observed_lineage_hashes": lineage,
              "bindings": {"design_sha256": sha(DESIGN), "runner_sha256": sha(RUNNER),
                           "audit_source_sha256": sha(__file__)},
              "authority": {"gpu_execution": passed, "only_stage111_three_clean_flow_cases": passed,
                            "particle_transport": False, "campaign": False},
              "claim_boundary": "Authorizes only three seed-2 clean CPD2 direct-flow validation cases and their independent evaluation."}
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "handoff.json", result)
    write(OUT / "completion.json", {"status": result["status"], "passed": passed,
                                    "handoff_sha256": sha(OUT / "handoff.json")})
    print(json.dumps({"status": result["status"], "checks": len(checks)}))
    if not passed:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
