from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path


CONFIG = Path(r"C:\MATDEM_MICROPLASTIC\stage31_designs\stage31d_replicated_nested_cpd2_geometry_20260826\geometry_01\resolved_config.json")
GEOMETRY_COMPLETION = CONFIG.parent / "completion.json"
RUNNER = Path(r"C:\MATDEM_MICROPLASTIC\stage31_staging\run_stage31e_replicated_nested_cpd2_gpu_v1.py")
HANDOFF = Path(r"C:\MATDEM_MICROPLASTIC\stage31_evaluations\stage31e_replicated_nested_cpd2_gpu_20260826\gpu_release_01\handoff.json")
GEOMETRY_AUDIT = Path(r"C:\MATDEM_MICROPLASTIC\stage31_evaluations\stage31d_replicated_nested_cpd2_geometry_20260826\geometry_audit_03\geometry_audit.json")
VISUAL_AUDIT = Path(r"C:\MATDEM_MICROPLASTIC\stage31_evaluations\stage31d_replicated_nested_cpd2_geometry_20260826\visual_audit_01\visual_audit.json")
MECHANICS_EVALUATION = Path(r"C:\MATDEM_MICROPLASTIC\stage31_evaluations\stage31c_replicated_nested_mechanics_20260826\mechanics_evaluation_01\evaluation.json")
RUN_ROOT = Path(r"C:\MATDEM_MICROPLASTIC\stage31_runs\stage31e_replicated_nested_cpd2_gpu_20260826\gpu_screen_01")
SUPERVISOR = RUN_ROOT.parent / "gpu_screen_01_supervisor"
LAUNCH_MANIFEST = SUPERVISOR / "launch_manifest.json"
DEFAULT_OUTPUT = Path(r"C:\MATDEM_MICROPLASTIC\stage31_evaluations\stage31e_replicated_nested_cpd2_gpu_20260826\gpu_evaluation_01")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def close(a: float, b: float, *, rel: float = 1e-11, abs_: float = 1e-14) -> bool:
    return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=abs_)


def summary(values: list[float]) -> dict:
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "n": len(values),
        "raw_ratios": values,
        "mean_ratio": mean,
        "sample_standard_deviation": sd,
        "coefficient_of_variation": sd / mean if mean else None,
        "minimum_ratio": min(values),
        "maximum_ratio": max(values),
        "mean_relative_change": mean - 1.0,
        "mean_reduction_percent": 100.0 * (1.0 - mean),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    require(not output.exists(), f"immutable output already exists: {output}")

    required = [CONFIG, GEOMETRY_COMPLETION, RUNNER, HANDOFF, GEOMETRY_AUDIT,
                VISUAL_AUDIT, MECHANICS_EVALUATION, LAUNCH_MANIFEST,
                RUN_ROOT / "completion.json"]
    for path in required:
        require(path.is_file(), f"required evidence missing: {path}")
    require(not (RUN_ROOT / "failure.json").exists(), "failure marker exists")

    config = load(CONFIG)
    geometry_completion = load(GEOMETRY_COMPLETION)
    handoff = load(HANDOFF)
    geometry_audit = load(GEOMETRY_AUDIT)
    visual_audit = load(VISUAL_AUDIT)
    mechanics_evaluation = load(MECHANICS_EVALUATION)
    launch = load(LAUNCH_MANIFEST)
    completion = load(RUN_ROOT / "completion.json")

    hashes = {
        "config": sha256(CONFIG),
        "geometry_completion": sha256(GEOMETRY_COMPLETION),
        "runner": sha256(RUNNER),
        "handoff": sha256(HANDOFF),
        "geometry_audit": sha256(GEOMETRY_AUDIT),
        "visual_audit": sha256(VISUAL_AUDIT),
        "mechanics_evaluation": sha256(MECHANICS_EVALUATION),
        "launch_manifest": sha256(LAUNCH_MANIFEST),
        "run_completion": sha256(RUN_ROOT / "completion.json"),
    }
    require(completion.get("passed") is True, "runner completion did not pass")
    require(completion.get("status") == "passed_twenty_one_case_cpd2_screen", "unexpected completion status")
    require(handoff.get("passed") is True, "handoff did not pass")
    require(geometry_completion.get("passed") is True, "geometry completion did not pass")
    require(geometry_audit.get("passed") is True, "geometry audit did not pass")
    require(visual_audit.get("passed") is True, "visual audit did not pass")
    require(mechanics_evaluation.get("passed") is True, "mechanics evaluation did not pass")

    bindings = handoff["bindings"]
    require(hashes["config"] == completion["config_sha256"] == bindings["config_sha256"] == launch["hashes"]["config"], "config binding mismatch")
    require(hashes["runner"] == completion["runner_sha256"] == bindings["runner_sha256"] == launch["hashes"]["runner"], "runner binding mismatch")
    require(hashes["handoff"] == completion["handoff_sha256"] == launch["hashes"]["handoff"], "handoff binding mismatch")
    require(hashes["geometry_completion"] == completion["geometry_completion_sha256"] == bindings["geometry_completion_sha256"], "geometry completion binding mismatch")
    require(hashes["geometry_audit"] == bindings["geometry_audit_sha256"], "geometry audit binding mismatch")
    require(hashes["visual_audit"] == bindings["visual_audit_sha256"], "visual audit binding mismatch")
    require((SUPERVISOR / "stderr.log").stat().st_size == 0, "supervisor stderr is not empty")
    require(Path(launch["output"]).resolve() == RUN_ROOT.resolve(), "launch output binding mismatch")
    require(Path(launch["arguments"][0]).resolve() == RUNNER.resolve(), "launch runner path mismatch")

    lineage_checks = {}
    for name, bound in config["lineage"].items():
        path = Path(bound["path"])
        ok = path.is_file() and sha256(path) == bound["sha256"] == completion["lineage_hashes"].get(name)
        require(ok, f"lineage mismatch: {name}")
        lineage_checks[name] = True
    require(config["lineage"]["stage31c_mechanics_evaluation"]["sha256"] == hashes["mechanics_evaluation"], "mechanics evaluation lineage mismatch")

    cases = config["geometry"]["cases"]
    paired = completion["paired_results"]
    require(len(cases) == len(paired) == len(completion["case_records"]) == 21, "expected exactly 21 cases")
    require([case["flow_order"] for case in cases] == list(range(1, 22)), "config flow order is not exact")
    require([item["flow_order"] for item in paired] == list(range(1, 22)), "result flow order is not exact")
    require([case["case_id"] for case in cases] == [item["case_id"] for item in paired], "result/config frozen order mismatch")

    acceptance = config["acceptance"]
    clean = {}
    rows = []
    artifact_map = {
        "audit_npz_sha256": "audit.npz",
        "final_fields_npz_sha256": "final_fields.npz",
        "final_flow_vtk_sha256": "final_flow.vtk",
        "final_shifted_state_npz_sha256": "final_shifted_state.npz",
    }
    for case, item in zip(cases, paired):
        case_id = case["case_id"]
        solver_dir = RUN_ROOT / item["solver_case_id"]
        record_path = solver_dir / "record.json"
        require(record_path.is_file(), f"record missing: {case_id}")
        record_hash = sha256(record_path)
        require(record_hash == item["record_sha256"] == completion["case_records"][case_id], f"record binding mismatch: {case_id}")
        record = load(record_path)
        require(record["case_id"] == item["solver_case_id"], f"solver case mismatch: {case_id}")
        require(record["stage"] == "STAGE31E_REPLICATED_NESTED_CPD2", f"stage mismatch: {case_id}")
        require(record["passed"] is True and record["converged"] is True, f"case did not pass/converge: {case_id}")
        require(all(record["checks"].values()), f"record check failed: {case_id}")
        require(record["cpd"] == 2 and record["dimensions_lu"] == [93, 93, 93], f"resolution mismatch: {case_id}")
        require(record["steps_completed"] == item["steps_completed"] == 24000, f"step mismatch: {case_id}")
        closure = record["exact_equilibrium_closure"]
        require(all(component == 0 for values in closure.values() for component in values), f"equilibrium closure failed: {case_id}")
        health = record["numerical_health"]
        final = record["final"]
        require(all(value == 0 for value in health.values()), f"sticky health code nonzero: {case_id}")
        require(final["fatal_health_code"] == final["full_health_code"] == final["reporting_only_health_code"] == 0, f"final health code nonzero: {case_id}")
        metrics = record["metrics"]
        require(metrics["mach_number"] <= acceptance["maximum_mach_number"], f"Mach gate failed: {case_id}")
        require(abs(final["mean_density"] - 1.0) <= acceptance["maximum_mean_density_drift"], f"density gate failed: {case_id}")
        require(final["momentum_residual_relative"] <= acceptance["maximum_momentum_balance_relative"], f"momentum gate failed: {case_id}")
        require(metrics["reynolds_number_diameter"] <= acceptance["maximum_reynolds_number_diameter"], f"Reynolds gate failed: {case_id}")
        require(metrics["torque_over_drag_diameter"] <= acceptance["maximum_torque_over_drag_diameter"], f"torque gate failed: {case_id}")
        require(metrics["transverse_force_over_drag"] <= acceptance["maximum_transverse_force_over_drag"], f"transverse force gate failed: {case_id}")
        for key, filename in artifact_map.items():
            artifact = solver_dir / filename
            require(artifact.is_file() and sha256(artifact) == record["artifacts"][key], f"artifact mismatch: {case_id}/{filename}")
        conductance = final["superficial_velocity_lu"] / record["acceleration_lu"]
        require(close(conductance, item["conductance_proxy_lu"]), f"conductance recomputation failed: {case_id}")
        if case["fibre_count"] == 0:
            clean[case["packing_id"]] = conductance
            require(item["placement_block"] is None and item["paired_permeability_ratio"] == 1.0, f"clean ratio mismatch: {case_id}")
        rows.append({
            "flow_order": case["flow_order"], "case_id": case_id,
            "packing_id": case["packing_id"], "placement_block": case["placement_block"],
            "fibre_count": case["fibre_count"], "achieved_dry_mass_percent": case["achieved_dry_mass_percent"],
            "conductance_proxy_lu": conductance, "paired_permeability_ratio": item["paired_permeability_ratio"],
            "relative_change": item["paired_relative_permeability_change"], "record_sha256": record_hash,
            "all_artifacts_verified": True, "all_health_gates_passed": True,
        })

    require(len(clean) == 3, "expected three clean controls")
    for row in rows:
        expected = row["conductance_proxy_lu"] / clean[row["packing_id"]]
        require(close(expected, row["paired_permeability_ratio"]), f"paired ratio recomputation failed: {row['case_id']}")

    count_summaries = {}
    packing_means = {}
    block_means = {}
    block_contrasts = {}
    monotonic_sequences = {}
    for count in (1, 2, 4):
        count_rows = [row for row in rows if row["fibre_count"] == count]
        require(len(count_rows) == 6, f"expected six ratios at count {count}")
        count_summaries[str(count)] = summary([row["paired_permeability_ratio"] for row in count_rows])
        packing_means[str(count)] = {
            packing: statistics.fmean(row["paired_permeability_ratio"] for row in count_rows if row["packing_id"] == packing)
            for packing in sorted(clean)
        }
        block_means[str(count)] = {
            block: statistics.fmean(row["paired_permeability_ratio"] for row in count_rows if row["placement_block"] == block)
            for block in ("A", "B")
        }
        block_contrasts[str(count)] = {
            packing: next(row["paired_permeability_ratio"] for row in count_rows if row["packing_id"] == packing and row["placement_block"] == "B")
                     - next(row["paired_permeability_ratio"] for row in count_rows if row["packing_id"] == packing and row["placement_block"] == "A")
            for packing in sorted(clean)
        }
    for packing in sorted(clean):
        for block in ("A", "B"):
            values = [next(row["paired_permeability_ratio"] for row in rows if row["packing_id"] == packing and row["placement_block"] == block and row["fibre_count"] == count) for count in (1, 2, 4)]
            monotonic_sequences[f"{packing}_{block}"] = {"ratios_1_2_4": values, "strictly_decreasing_observed": values[0] > values[1] > values[2]}

    output.mkdir(parents=True)
    evaluation = {
        "schema": "lbs.stage31e-replicated-nested-cpd2-independent-evaluation.v1",
        "status": "passed_replicated_nested_cpd2_screen",
        "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": config["research_question"],
        "claim_boundary": "Fixed-solid CPD2 relative-conductance screen only; no absolute permeability validation claim and no authority for CPD4 or new physics.",
        "hashes": hashes,
        "lineage_checks": lineage_checks,
        "checks": {
            "all_required_hash_bindings": True, "all_21_records_and_84_artifacts_verified": True,
            "all_cases_converged_at_24000_steps": True, "all_numerical_health_and_balance_gates": True,
            "all_exact_equilibrium_closures": True, "three_exact_matched_clean_controls": True,
            "frozen_order_exact": True, "no_failure_marker": True, "supervisor_stderr_empty": True,
        },
        "rows": rows,
        "analysis": {
            "fibre_count_treated_categorically_without_imposed_monotonicity": True,
            "count_summaries": count_summaries,
            "packing_means": packing_means,
            "placement_block_means": block_means,
            "within_packing_block_B_minus_A_contrasts": block_contrasts,
            "descriptive_monotonicity_only": monotonic_sequences,
            "clean_intrinsic_permeability_m2_descriptive_only": {
                item["packing_id"]: item["intrinsic_permeability_m2"] for item in paired if item["fibre_count"] == 0
            },
        },
        "authority": {
            "render": True, "cpd4": False, "absolute_permeability_validation_claim": False,
            "mobile_sand": False, "migration": False, "clogging": False,
            "deformation": False, "transient_coupling": False, "two_way_coupling": False,
        },
    }
    (output / "evaluation.json").write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "output": str(output), "count_summaries": count_summaries}, indent=2))


if __name__ == "__main__":
    main()
