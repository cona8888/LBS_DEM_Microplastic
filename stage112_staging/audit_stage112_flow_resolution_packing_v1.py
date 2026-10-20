"""Independent pre-execution audit for Stage112."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "stage112_designs/reference_flow_resolution_packing_20260915/design_01/resolved_design.json"
DESIGN_COMPLETION = DESIGN.with_name("completion.json")
RUNNER = ROOT / "stage112_staging/run_stage112_flow_resolution_packing_gpu_v1.py"
OUT = ROOT / "stage112_evaluations/reference_flow_resolution_packing_20260915/pre_execution_audit_01"


def sha(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    design, completion = read(DESIGN), read(DESIGN_COMPLETION)
    cases = design["cases"]
    checks = {
        "design_hash_bound": completion.get("design_sha256") == sha(DESIGN),
        "design_requires_audit": design.get("status") == "designed_independent_audit_required",
        "gpu_initially_disabled": design.get("authority", {}).get("gpu_execution") is False,
        "exact_three_cases": len(cases) == 3,
        "exact_seed_order": [c["packing_seed"] for c in cases] == [1, 3, 2],
        "exact_cpd_order": [c["cpd"] for c in cases] == [2, 2, 4],
        "reference_flow_only": all(c["target_physical_mean_interstitial_velocity_m_s"] == 1.0e-4 for c in cases),
        "positive_accelerations": all(c["initial_acceleration_lu"] > 0 for c in cases),
        "positive_warm_scales": all(c["warm_start"]["velocity_scale"] > 0 and c["warm_start"]["density_deviation_scale"] > 0 for c in cases),
        "finite_target_mach": all(c["target_mean_interstitial_velocity_lu"] * 3**0.5 < design["numerical_acceptance"]["maximum_mach_number"] for c in cases),
        "cpd4_minimum_can_fit": design["solver"]["maximum_steps"] >= 88000,
        "no_particle_or_campaign_authority": design["authority"]["particle_transport"] is False and design["authority"]["campaign"] is False,
        "runner_exists": RUNNER.is_file(),
        "immutable_output_required": "refusing to overwrite immutable output" in RUNNER.read_text(),
        "failure_preservation_present": "failed_preserved" in RUNNER.read_text(),
        "dynamic_geometry_binding_present": "geometry_cpd{case['cpd']}" in RUNNER.read_text(),
        "warm_start_only": "resampled_local_field_warm_start" in RUNNER.read_text(),
    }
    observed = {}
    for name, item in design["lineage"].items():
        if isinstance(item, dict) and "path" in item:
            observed[name] = sha(item["path"])
            checks["lineage_" + name] = observed[name] == item["sha256"]
    for case in cases:
        checks[case["case_id"] + "_geometry_exists"] = Path(case["geometry"]).is_file()
        checks[case["case_id"] + "_warm_bound"] = sha(case["warm_start"]["path"]) == case["warm_start"]["sha256"]
        checks[case["case_id"] + "_archive_record_bound"] = sha(case["archive_record"]["path"]) == case["archive_record"]["sha256"]
    passed = all(checks.values())
    result = {
        "schema": "matdem.stage112.flow-resolution-packing.pre-execution-audit.v1",
        "status": "stage112_gpu_execution_authorized" if passed else "stage112_gpu_execution_not_authorized",
        "passed": passed, "checks": checks, "observed_lineage_hashes": observed,
        "bindings": {"design_sha256": sha(DESIGN), "runner_sha256": sha(RUNNER),
                     "audit_source_sha256": sha(__file__)},
        "authority": {"gpu_execution": passed, "only_stage112_three_clean_cases": passed,
                      "particle_transport": False, "campaign": False},
        "claim_boundary": "Authorizes only two CPD2 packing checks and one seed-2 CPD4 clean reference-flow solve.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "handoff.json", result)
    write(OUT / "completion.json", {"status": result["status"], "passed": passed,
                                    "handoff_sha256": sha(OUT / "handoff.json")})
    print(json.dumps({"status": result["status"], "checks": len(checks)}))
    if not passed:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
