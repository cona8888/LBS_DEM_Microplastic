from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage34c_cpd4_first_fragmentation_geometry_20260902"
CONFIG = ROOT / "stage34_designs" / STUDY / "gpu_config_02" / "resolved_config.json"
CONFIG_COMPLETION = CONFIG.parent / "completion.json"
ORIGINAL_RELEASE_DIR = ROOT / "stage34_evaluations" / STUDY / "execution_release_03"
ORIGINAL_RELEASE = ORIGINAL_RELEASE_DIR / "release_audit.json"
ORIGINAL_HANDOFF = ORIGINAL_RELEASE_DIR / "handoff.json"
INTERRUPTION_DIR = ROOT / "stage34_evaluations" / STUDY / "interruption_audit_01"
INTERRUPTION_AUDIT = INTERRUPTION_DIR / "interruption_audit.json"
INTERRUPTION_COMPLETION = INTERRUPTION_DIR / "completion.json"
RECOVERY_RELEASE_DIR = ROOT / "stage34_evaluations" / STUDY / "recovery_release_01"
RECOVERY_RELEASE = RECOVERY_RELEASE_DIR / "release_audit.json"
RECOVERY_HANDOFF = RECOVERY_RELEASE_DIR / "handoff.json"
ORIGINAL_RUNNER = ROOT / "stage34_staging" / "run_stage34c_fragment_cpd4_gpu_v1.py"
ORIGINAL_SUPERVISOR_SCRIPT = ROOT / "stage34_staging" / "supervise_stage34c_fragment_cpd4_gpu_v2.ps1"
RECOVERY_RUNNER = ROOT / "stage34_staging" / "run_stage34c_fragment_cpd4_recovery_gpu_v1.py"
RECOVERY_SUPERVISOR_SCRIPT = ROOT / "stage34_staging" / "supervise_stage34c_fragment_cpd4_recovery_gpu_v1.ps1"
ORIGINAL_RUN = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_01"
ORIGINAL_SUPERVISOR = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_01_supervisor"
RECOVERY_RUN = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_02_recovery"
RECOVERY_SUPERVISOR = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_02_recovery_supervisor"
RECOVERY_COMPLETION = RECOVERY_RUN / "completion.json"
OUT = ROOT / "stage34_evaluations" / STUDY / "gpu_evaluation_02"

ARTIFACT_NAMES = (
    "record.json",
    "audit.npz",
    "final_fields.npz",
    "final_flow.vtk",
    "final_shifted_state.npz",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_tree(value: object) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    return False


def all_zero(mapping: dict) -> bool:
    return all(int(value) == 0 for value in mapping.values())


def exact_closure(record: dict) -> bool:
    return all(
        int(component) == 0
        for name, vector in record["exact_equilibrium_closure"].items()
        if name.endswith("numerator_xyz")
        for component in vector
    )


def bound_file(binding: dict) -> bool:
    path = Path(binding["path"])
    return path.is_file() and sha(path) == binding["sha256"]


def sign_summary(values: list[float], practical_threshold: float) -> dict:
    positive = sum(value > 0.0 for value in values)
    negative = sum(value < 0.0 for value in values)
    zero = len(values) - positive - negative
    majority = "positive" if positive > negative else "negative" if negative > positive else "tie"
    concordant = max(positive, negative)
    return {
        "values": values,
        "positive_count": positive,
        "negative_count": negative,
        "zero_count": zero,
        "majority_sign": majority,
        "concordant_context_count": concordant,
        "context_count": len(values),
        "practical_count": sum(abs(value) >= practical_threshold for value in values),
        "practical_threshold_absolute_ratio": practical_threshold,
        "monotonicity_or_sign_not_an_acceptance_gate": True,
    }


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")

    config = load(CONFIG)
    config_completion = load(CONFIG_COMPLETION)
    original_release = load(ORIGINAL_RELEASE)
    original_handoff = load(ORIGINAL_HANDOFF)
    interruption = load(INTERRUPTION_AUDIT)
    interruption_completion = load(INTERRUPTION_COMPLETION)
    recovery_release = load(RECOVERY_RELEASE)
    recovery_handoff = load(RECOVERY_HANDOFF)
    completion = load(RECOVERY_COMPLETION)
    original_launch = load(ORIGINAL_SUPERVISOR / "launch_manifest.json")
    recovery_launch = load(RECOVERY_SUPERVISOR / "launch_manifest.json")

    config_hash = sha(CONFIG)
    original_runner_hash = sha(ORIGINAL_RUNNER)
    original_supervisor_hash = sha(ORIGINAL_SUPERVISOR_SCRIPT)
    recovery_runner_hash = sha(RECOVERY_RUNNER)
    recovery_supervisor_hash = sha(RECOVERY_SUPERVISOR_SCRIPT)
    original_handoff_hash = sha(ORIGINAL_HANDOFF)
    recovery_handoff_hash = sha(RECOVERY_HANDOFF)
    interruption_hash = sha(INTERRUPTION_AUDIT)

    order = [case["case_id"] for case in sorted(config["geometry"]["cases"], key=lambda x: x["run_order"])]
    case_meta = {case["case_id"]: case for case in config["geometry"]["cases"]}
    reused_order = list(recovery_handoff["reused_order"])
    recovery_order = list(recovery_handoff["recovery_order"])
    completion_rows = {row["case_id"]: row for row in completion["case_results"]}

    lineage_checks = {
        key: bound_file(binding)
        for key, binding in config["lineage"].items()
        if isinstance(binding, dict) and {"path", "sha256"} <= set(binding)
    }
    geometry_checks = {
        case_id: bound_file(binding)
        for case_id, binding in config["geometry"]["artifacts"].items()
    }

    clean_checks: dict[str, dict] = {}
    for context, clean in config["matched_clean_controls"].items():
        bindings = {
            name: bound_file(binding)
            for name, binding in clean.items()
            if isinstance(binding, dict) and {"path", "sha256"} <= set(binding)
        }
        record = load(Path(clean["record"]["path"]))
        conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
        checks = {
            **bindings,
            "source_record_passed": record.get("passed") is True and record.get("converged") is True,
            "source_solver_checks_true": all(record.get("checks", {}).values()),
            "source_numerical_health_zero": all_zero(record["numerical_health"]),
            "source_exact_equilibrium_closure": exact_closure(record),
            "conductance_recomputed": math.isclose(conductance, clean["conductance_proxy_lu"], rel_tol=0.0, abs_tol=1e-14),
            "source_completion_passed": load(Path(clean["completion"]["path"])).get("passed") is True,
            "source_evaluation_passed": load(Path(clean["evaluation"]["path"])).get("passed") is True,
        }
        clean_checks[context] = {"passed": all(checks.values()), "checks": checks, "conductance_proxy_lu": conductance}

    intact_checks: dict[str, dict] = {}
    intact_ratios: dict[str, float] = {}
    for context, intact in config["intact_contexts"].items():
        artifact_checks = {name: bound_file(binding) for name, binding in intact["artifacts"].items()}
        geometry_ok = bound_file(intact["geometry"])
        record = load(Path(intact["artifacts"]["record.json"]["path"]))
        conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
        clean_conductance = clean_checks[context]["conductance_proxy_lu"]
        ratio = conductance / clean_conductance
        checks = {
            "all_artifacts_hash_bound": all(artifact_checks.values()),
            "geometry_hash_bound": geometry_ok,
            "context_bound": record["case_id"] == Path(intact["artifacts"]["record.json"]["path"]).parent.name
            and intact["source_case_id"] in record["case_id"],
            "passed_and_converged": record.get("passed") is True and record.get("converged") is True,
            "all_solver_checks_true": all(record.get("checks", {}).values()),
            "numerical_health_zero": all_zero(record["numerical_health"]),
            "exact_equilibrium_closure": exact_closure(record),
            "finite_record_values": finite_tree(record),
            "positive_conductance": conductance > 0.0,
            "conductance_recomputed": math.isclose(conductance, intact["conductance_proxy_lu"], rel_tol=0.0, abs_tol=1e-14),
            "ratio_recomputed": math.isclose(ratio, intact["paired_permeability_ratio"], rel_tol=0.0, abs_tol=1e-14),
        }
        intact_checks[context] = {
            "passed": all(checks.values()),
            "checks": checks,
            "artifact_checks": artifact_checks,
            "paired_permeability_ratio": ratio,
        }
        intact_ratios[context] = ratio

    case_checks: dict[str, dict] = {}
    recomputed_rows: list[dict] = []
    artifact_count = 0
    for case_id in order:
        meta = case_meta[case_id]
        context = f"{meta['packing_id']}_{meta['placement_block']}"
        source_dir = ORIGINAL_RUN if case_id in reused_order else RECOVERY_RUN
        expected_source = (
            "reused_interrupted_gpu_confirmation_01" if case_id in reused_order
            else "new_gpu_confirmation_02_recovery"
        )
        case_dir = source_dir / case_id
        record_path = case_dir / "record.json"
        record = load(record_path)
        row = completion_rows[case_id]
        artifact_checks = {
            name: (case_dir / name).is_file()
            and sha(case_dir / name) == row["artifact_sha256"][name]
            for name in ARTIFACT_NAMES
        }
        artifact_count += sum(artifact_checks.values())
        record_artifact_checks = {
            "audit.npz": sha(case_dir / "audit.npz") == record["artifacts"]["audit_npz_sha256"],
            "final_fields.npz": sha(case_dir / "final_fields.npz") == record["artifacts"]["final_fields_npz_sha256"],
            "final_flow.vtk": sha(case_dir / "final_flow.vtk") == record["artifacts"]["final_flow_vtk_sha256"],
            "final_shifted_state.npz": sha(case_dir / "final_shifted_state.npz") == record["artifacts"]["final_shifted_state_npz_sha256"],
        }
        warm = record["initialization"]
        frozen_warm = config["warm_starts"][case_id]
        warm_path = Path(warm["path"])
        conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
        ratio = conductance / clean_checks[context]["conductance_proxy_lu"]
        checks = {
            "record_case_id_bound": record["case_id"] == case_id,
            "record_hash_bound": sha(record_path) == row["artifact_sha256"]["record.json"],
            "source_partition_bound": row["result_source"] == expected_source,
            "stage_bound": record["stage"] in {
                "STAGE34C_FIXED_VOLUME_FRAGMENTATION_CPD4_PARAMETRIC_STUDY",
                "STAGE34C_FIXED_VOLUME_FRAGMENTATION_CPD4_INTERRUPTION_RECOVERY",
            },
            "cpd4_dimensions": record["cpd"] == 4 and record["dimensions_lu"] == [186, 186, 186],
            "passed_and_converged": record.get("passed") is True and record.get("converged") is True,
            "all_solver_checks_true": all(record.get("checks", {}).values()),
            "numerical_health_zero": all_zero(record["numerical_health"])
            and all(int(record["final"][key]) == 0 for key in ("fatal_health_code", "full_health_code", "reporting_only_health_code")),
            "exact_equilibrium_closure": exact_closure(record),
            "finite_record_values": finite_tree(record),
            "positive_conductance_and_ratio": conductance > 0.0 and ratio > 0.0,
            "steps_bound": record["steps_completed"] == row["steps_completed"] == 88000,
            "momentum_balance_gate": float(record["final"]["momentum_residual_relative"]) <= float(config["acceptance"]["maximum_momentum_balance_relative"]),
            "force_balance_gates": record["checks"]["force_direction"] is True and record["checks"]["transverse_force"] is True,
            "conductance_recomputed": math.isclose(conductance, row["conductance_proxy_lu"], rel_tol=0.0, abs_tol=1e-14),
            "ratio_recomputed": math.isclose(ratio, row["paired_permeability_ratio"], rel_tol=0.0, abs_tol=1e-14),
            "warm_start_bound": warm.get("mode") == "resampled_local_equilibrium_from_verified_lower_resolution"
            and all(warm.get(key) == frozen_warm[key] for key in ("path", "sha256", "density_deviation_scale", "velocity_scale"))
            and warm_path.is_file() and sha(warm_path) == frozen_warm["sha256"]
            and frozen_warm["source_intact_case_id"] == meta["source_intact_case_id"],
            "all_completion_artifact_hashes": all(artifact_checks.values()),
            "all_record_artifact_hashes": all(record_artifact_checks.values()),
        }
        case_checks[case_id] = {
            "passed": all(checks.values()),
            "checks": checks,
            "artifact_checks": artifact_checks,
            "record_artifact_checks": record_artifact_checks,
            "source_directory": str(source_dir),
            "momentum_residual_relative": record["final"]["momentum_residual_relative"],
        }
        recomputed_rows.append({
            "run_order": meta["run_order"],
            "case_id": case_id,
            "packing_id": meta["packing_id"],
            "placement_block": meta["placement_block"],
            "context": context,
            "fragments_per_parent": meta["fragments_per_parent"],
            "total_fragment_count": meta["total_fragment_count"],
            "conductance_proxy_lu": conductance,
            "paired_permeability_ratio": ratio,
            "source": expected_source,
        })

    by_context = {context: {1: ratio} for context, ratio in intact_ratios.items()}
    for row in recomputed_rows:
        by_context[row["context"]][row["fragments_per_parent"]] = row["paired_permeability_ratio"]
    contrasts = {}
    for context in sorted(by_context):
        values = by_context[context]
        contrasts[context] = {
            "packing_id": context.rsplit("_", 1)[0],
            "placement_block": context.rsplit("_", 1)[1],
            "frag1_intact_ratio": values[1],
            "frag2_ratio": values[2],
            "frag3_ratio": values[3],
            "frag2_minus_frag1": values[2] - values[1],
            "frag3_minus_frag1": values[3] - values[1],
            "frag3_minus_frag2": values[3] - values[2],
        }

    practical_threshold = float(config["analysis"]["practical_selection_threshold_absolute_ratio"])
    cross_context_signs = {
        contrast_name: sign_summary(
            [contrasts[context][contrast_name] for context in sorted(contrasts)],
            practical_threshold,
        )
        for contrast_name in config["analysis"]["paired_contrasts"]
    }

    original_case_dirs = sorted(path.name for path in ORIGINAL_RUN.iterdir() if path.is_dir())
    recovery_case_dirs = sorted(path.name for path in RECOVERY_RUN.iterdir() if path.is_dir())
    original_reuse_hash_checks = {
        case_id: all(
            (ORIGINAL_RUN / case_id / name).is_file()
            and sha(ORIGINAL_RUN / case_id / name) == hashes[name]
            for name, hashes in [(name, recovery_handoff["completed_case_bundles"][case_id]["artifact_sha256"]) for name in ARTIFACT_NAMES]
        )
        for case_id in reused_order
    }

    original_release_checks = {
        "release_passed": original_release.get("passed") is True and original_handoff.get("passed") is True,
        "config_hash": original_handoff["bindings"]["config_sha256"] == config_hash,
        "release_audit_hash": original_handoff["bindings"]["release_audit_sha256"] == sha(ORIGINAL_RELEASE),
        "runner_hash": original_handoff["bindings"]["runner_sha256"] == original_runner_hash,
        "supervisor_hash": original_handoff["bindings"]["supervisor_sha256"] == original_supervisor_hash,
    }
    interruption_checks = {
        "audit_passed": interruption.get("passed") is True and interruption_completion.get("passed") is True,
        "status_exact": interruption.get("status") == "passed_recoverable_external_interruption",
        "two_completed_cases": len(interruption["completed_case_bundles"]) == 2,
        "next_case_bound": interruption["next_unfinished_case"] == recovery_order[0],
        "original_paths_bound": Path(interruption["original_run_output"]) == ORIGINAL_RUN
        and Path(interruption["original_supervisor_output"]) == ORIGINAL_SUPERVISOR,
    }
    recovery_release_checks = {
        "release_passed": recovery_release.get("passed") is True and recovery_handoff.get("passed") is True,
        "config_hash": recovery_handoff["bindings"]["config_sha256"] == config_hash,
        "interruption_hash": recovery_handoff["bindings"]["interruption_audit_sha256"] == interruption_hash,
        "original_handoff_hash": recovery_handoff["bindings"]["original_handoff_sha256"] == original_handoff_hash,
        "original_runner_hash": recovery_handoff["bindings"]["original_runner_sha256"] == original_runner_hash,
        "original_supervisor_hash": recovery_handoff["bindings"]["original_supervisor_sha256"] == original_supervisor_hash,
        "recovery_runner_hash": recovery_handoff["bindings"]["runner_sha256"] == recovery_runner_hash,
        "recovery_supervisor_hash": recovery_handoff["bindings"]["supervisor_sha256"] == recovery_supervisor_hash,
        "release_audit_hash": recovery_handoff["bindings"]["release_audit_sha256"] == sha(RECOVERY_RELEASE),
    }
    launch_checks = {
        "original_hashes": original_launch["hashes"] == {
            "runner": original_runner_hash,
            "config": config_hash,
            "handoff": original_handoff_hash,
            "supervisor": original_supervisor_hash,
        },
        "recovery_hashes": recovery_launch["hashes"] == {
            "runner": recovery_runner_hash,
            "config": config_hash,
            "handoff": recovery_handoff_hash,
            "supervisor": recovery_supervisor_hash,
        },
        "outputs_bound": Path(original_launch["output"]) == ORIGINAL_RUN and Path(recovery_launch["output"]) == RECOVERY_RUN,
        "recovery_never_reruns_completed": recovery_launch["recovery"]["rerun_completed_cases"] is False,
        "recovery_never_edits_original": recovery_launch["recovery"]["edit_or_overwrite_original_output"] is False,
    }
    contrast_reproduction_checks = {
        context: all(
            math.isclose(contrasts[context][key], completion["contrasts"][context][key], rel_tol=0.0, abs_tol=1e-14)
            for key in ("frag1_intact_ratio", "frag2_ratio", "frag3_ratio", "frag2_minus_frag1", "frag3_minus_frag1", "frag3_minus_frag2")
        )
        for context in contrasts
    }

    authority_false_keys = (
        "absolute_permeability_validation_claim", "chemical_degradation_claim", "clogging",
        "cpd6_flow_execution", "deformation", "mechanics_rerun", "migration",
        "mobile_sand", "transient_coupling", "two_way_coupling",
    )
    checks = {
        "config_completion_passed": config_completion.get("passed") is True,
        "original_release_chain_passed": all(original_release_checks.values()),
        "interruption_audit_chain_passed": all(interruption_checks.values()),
        "recovery_release_chain_passed": all(recovery_release_checks.values()),
        "launch_manifests_hash_bound": all(launch_checks.values()),
        "full_frozen_order_reconstructed": order == recovery_handoff["full_order"] and order == [row["case_id"] for row in completion["case_results"]],
        "exact_two_reused_six_new": len(reused_order) == 2 and len(recovery_order) == 6 and set(reused_order).isdisjoint(recovery_order) and set(order) == set(reused_order + recovery_order),
        "original_interrupted_evidence_preserved": original_case_dirs == sorted(reused_order)
        and not (ORIGINAL_RUN / "completion.json").exists() and not (ORIGINAL_RUN / "failure.json").exists(),
        "recovery_contains_only_six_new_case_directories": recovery_case_dirs == sorted(recovery_order),
        "original_reuse_hashes_bound": all(original_reuse_hash_checks.values()),
        "completion_passed": completion.get("passed") is True and all(completion["checks"].values()),
        "completion_status_exact": completion.get("status") == "passed_fragment_cpd4_recovery_pending_independent_evaluation",
        "completion_hashes_bound": completion["config_sha256"] == config_hash
        and completion["runner_sha256"] == recovery_runner_hash
        and completion["handoff_sha256"] == recovery_handoff_hash,
        "all_lineage_hashes_bound": bool(lineage_checks) and all(lineage_checks.values()),
        "all_geometry_hashes_bound": len(geometry_checks) == 8 and all(geometry_checks.values()),
        "all_clean_controls_bound": len(clean_checks) == 4 and all(item["passed"] for item in clean_checks.values()),
        "all_intact_contexts_bound": len(intact_checks) == 4 and all(item["passed"] for item in intact_checks.values()),
        "all_eight_case_bundles_pass": len(case_checks) == 8 and all(item["passed"] for item in case_checks.values()),
        "all_forty_case_artifacts_hash_bound": artifact_count == 40,
        "all_twelve_contrasts_finite": finite_tree(contrasts) and sum(3 for _ in contrasts) == 12,
        "completion_contrasts_reproduced": all(contrast_reproduction_checks.values()),
        "monotonicity_and_sign_not_gated": config["analysis"]["monotonicity_imposed"] is False
        and all(summary["monotonicity_or_sign_not_an_acceptance_gate"] for summary in cross_context_signs.values()),
        "original_stderr_empty": (ORIGINAL_SUPERVISOR / "stderr.log").stat().st_size == 0,
        "recovery_stderr_empty": (RECOVERY_SUPERVISOR / "stderr.log").stat().st_size == 0,
        "no_failure_markers": not any(ORIGINAL_RUN.rglob("failure.json"))
        and not any(ORIGINAL_SUPERVISOR.rglob("failure.json"))
        and not any(RECOVERY_RUN.rglob("failure.json"))
        and not any(RECOVERY_SUPERVISOR.rglob("failure.json")),
        "authority_boundary_preserved": all(completion["authority"].get(key) is False for key in authority_false_keys),
    }
    passed = all(checks.values())

    interpretation = (
        "Across the four matched packing/placement contexts, split-2 and split-3 effects relative to intact are sign-inconsistent. "
        "Only one of four contexts reaches the predeclared |Delta K/K0| >= 0.005 practical threshold for either split state, "
        "and no split-3-minus-split-2 contrast reaches it. Fragment count therefore does not support a universal monotonic hydraulic law in this fixed-solid, idealized geometry study."
    )
    evaluation = {
        "schema": "lbs.stage34c-fragment-cpd4-recovery-independent-evaluation.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_stage34c_fragment_cpd4_independent_evaluation" if passed else "failed_stage34c_fragment_cpd4_independent_evaluation",
        "research_question": config["research_question"],
        "checks": checks,
        "original_release_checks": original_release_checks,
        "interruption_checks": interruption_checks,
        "recovery_release_checks": recovery_release_checks,
        "launch_checks": launch_checks,
        "lineage_checks": lineage_checks,
        "geometry_checks": geometry_checks,
        "clean_control_checks": clean_checks,
        "intact_context_checks": intact_checks,
        "case_checks": case_checks,
        "case_results": recomputed_rows,
        "contrasts": contrasts,
        "cross_context_sign_concordance": cross_context_signs,
        "completion_contrast_reproduction_checks": contrast_reproduction_checks,
        "interpretation": interpretation,
        "claim_boundary": config["claim_boundary"],
        "bindings": {
            "config_sha256": config_hash,
            "config_completion_sha256": sha(CONFIG_COMPLETION),
            "original_release_sha256": sha(ORIGINAL_RELEASE),
            "original_handoff_sha256": original_handoff_hash,
            "interruption_audit_sha256": interruption_hash,
            "interruption_completion_sha256": sha(INTERRUPTION_COMPLETION),
            "recovery_release_sha256": sha(RECOVERY_RELEASE),
            "recovery_handoff_sha256": recovery_handoff_hash,
            "recovery_completion_sha256": sha(RECOVERY_COMPLETION),
            "original_runner_sha256": original_runner_hash,
            "original_supervisor_sha256": original_supervisor_hash,
            "recovery_runner_sha256": recovery_runner_hash,
            "recovery_supervisor_sha256": recovery_supervisor_hash,
        },
        "authority": {
            "rendering": passed,
            "cpd6_flow_execution": False,
            "absolute_permeability_validation_claim": False,
            "chemical_degradation_claim": False,
            "mechanics_rerun": False,
            "mobile_sand": False,
            "migration": False,
            "clogging": False,
            "deformation": False,
            "transient_coupling": False,
            "two_way_coupling": False,
        },
    }

    OUT.mkdir(parents=True)
    evaluation_path = OUT / "evaluation.json"
    evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    with (OUT / "contrasts.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(next(iter(contrasts.values())).keys()))
        writer.writeheader()
        writer.writerows(contrasts.values())
    checkpoint = {
        "schema": evaluation["schema"] + ".checkpoint",
        "passed": passed,
        "evaluation_sha256": sha(evaluation_path),
        "recovery_completion_sha256": sha(RECOVERY_COMPLETION),
        "authority": {"authorized": "render Stage34C CPD4 fragmentation evidence" if passed else "diagnosis only"},
    }
    (OUT / "checkpoint_manifest.json").write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output": str(OUT),
        "passed": passed,
        "failed_checks": [name for name, value in checks.items() if not value],
        "cross_context_sign_concordance": cross_context_signs,
    }, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
