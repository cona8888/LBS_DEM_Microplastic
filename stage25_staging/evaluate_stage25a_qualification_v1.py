"""Independent fail-closed evaluation of the Stage25a mechanics qualification."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage25_staging" / "stage25a_mechanics_design_v1.json"
RUNNER = PROJECT / "stage25_staging" / "stage25a_yade_pure_sand_mechanics_v1.py"
LAUNCHER = PROJECT / "stage25_staging" / "launch_stage25a_qualification_v4.ps1"
RUN = PROJECT / "stage25_runs" / "stage25a_pure_sand_mechanics_20260813" / "qualification_04"
SUPERVISOR = PROJECT / "stage25_supervisors" / "stage25a_pure_sand_mechanics_20260813" / "qualification_04"
OUTPUT = PROJECT / "stage25_evaluations" / "stage25a_pure_sand_mechanics_20260813" / "evaluation_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def close(a, b, atol=1e-12, rtol=1e-9):
    return math.isclose(float(a), float(b), abs_tol=atol, rel_tol=rtol)


def row_passes(row, acceptance, target_void_ratio):
    return all([
        str(row["unbalanced_force_defined"]).lower() == "true",
        float(row["relative_mean_stress_error"]) <= acceptance["maximum_relative_mean_stress_error"],
        float(row["unbalanced_force"]) <= acceptance["maximum_unbalanced_force"],
        float(row["normalized_kinetic_energy_pV"]) <= acceptance["maximum_normalized_kinetic_energy_pV"],
        float(row["coordination_excluding_degree_lt2_rattlers"]) >= acceptance["minimum_coordination_excluding_rattlers"],
        float(row["rattler_fraction_degree_lt2_iterative"]) <= acceptance["maximum_rattler_fraction"],
        float(row["maximum_overlap_over_smaller_radius"]) <= acceptance["maximum_overlap_over_smaller_radius"],
        abs(float(row["void_ratio"]) - target_void_ratio) <= acceptance["maximum_absolute_void_ratio_difference_from_reference"],
        int(row["real_contact_count"]) > 0,
    ])


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable evaluation output already exists")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir()

    cfg = load_json(CONFIG)
    completion_path = RUN / "completion.json"
    completion = load_json(completion_path)
    launch = load_json(SUPERVISOR / "launch_manifest.json")
    status = load_json(SUPERVISOR / "status.json")
    acceptance = cfg["acceptance"]
    target_void_ratio = float(cfg["reference_state"]["void_ratio"])

    global_checks = {
        "supervisor_exit_zero": status.get("exit_code") == 0,
        "supervisor_completion_bound": status.get("completion_exists") is True,
        "supervisor_no_failure": status.get("failure_exists") is False and not (RUN / "failure.json").exists(),
        "completion_passed": completion.get("passed") is True,
        "completion_not_smoke": completion.get("smoke_mode") is False,
        "config_hash_bound": launch.get("config_sha256") == digest(CONFIG) == completion["source_hashes"]["config"],
        "runner_hash_bound": launch.get("runner_sha256") == digest(RUNNER) == completion["source_hashes"]["runner"],
        "launcher_hash_bound": launch.get("launcher_sha256") == digest(LAUNCHER),
        "stage24e_source_hash_bound": digest(Path(cfg["source"]["stage24e_evaluation"])) == cfg["source"]["stage24e_evaluation_sha256"] == completion["source_hashes"]["stage24e_evaluation"],
        "stage23a_source_hash_bound": digest(Path(cfg["source"]["stage23a_primary_preparation"])) == cfg["source"]["stage23a_primary_preparation_sha256"] == completion["source_hashes"]["stage23a_primary_preparation"],
        "promotion_boundary_preserved": completion["promotion"].get("fibre_mechanics_authorized") is False and completion["promotion"].get("flow_authorized") is False and completion["promotion"].get("deformation_coupled_flow_authorized") is False,
    }

    cases = []
    for case_id, expected_result_hash in sorted(completion["case_records"].items()):
        case_dir = RUN / case_id
        result_path = case_dir / "result.json"
        history_path = case_dir / "history.csv"
        checkpoint_path = case_dir / "load_bearing_state.yade.gz"
        result = load_json(result_path)
        terminal = result["terminal"]
        with history_path.open("r", encoding="utf-8", newline="") as stream:
            history = list(csv.DictReader(stream))
        required = int(cfg["preparation"]["required_consecutive_pass_blocks"])
        tail = history[-required:]
        recomputed = {
            "finite_state": all(math.isfinite(float(terminal[name])) for name in [
                "void_ratio", "mean_effective_stress_pa_compression_positive", "unbalanced_force",
                "normalized_kinetic_energy_pV", "maximum_overlap_over_smaller_radius",
                "coordination_excluding_degree_lt2_rattlers", "rattler_fraction_degree_lt2_iterative",
            ]),
            "particle_count_retained": len(result["particles"]) == acceptance["required_particle_count"] and len({p["body_id"] for p in result["particles"]}) == acceptance["required_particle_count"],
            "mean_stress": terminal["relative_mean_stress_error"] <= acceptance["maximum_relative_mean_stress_error"],
            "unbalanced_force_defined": terminal["unbalanced_force_defined"] is True,
            "unbalanced_force": terminal["unbalanced_force"] <= acceptance["maximum_unbalanced_force"],
            "normalized_kinetic_energy": terminal["normalized_kinetic_energy_pV"] <= acceptance["maximum_normalized_kinetic_energy_pV"],
            "coordination": terminal["coordination_excluding_degree_lt2_rattlers"] >= acceptance["minimum_coordination_excluding_rattlers"],
            "rattler_fraction": terminal["rattler_fraction_degree_lt2_iterative"] <= acceptance["maximum_rattler_fraction"],
            "overlap": terminal["maximum_overlap_over_smaller_radius"] <= acceptance["maximum_overlap_over_smaller_radius"],
            "void_ratio": abs(terminal["void_ratio"] - target_void_ratio) <= acceptance["maximum_absolute_void_ratio_difference_from_reference"],
            "real_contacts_present": terminal["real_contact_count"] > 0,
        }
        artifact_checks = {
            "result_hash": digest(result_path) == expected_result_hash,
            "history_hash": digest(history_path) == result["artifacts"]["history_csv_sha256"],
            "checkpoint_hash": digest(checkpoint_path) == result["artifacts"]["checkpoint_sha256"],
            "history_terminal_block": int(history[-1]["block"]) == int(terminal["block"]),
            "history_terminal_void_ratio": close(history[-1]["void_ratio"], terminal["void_ratio"]),
            "history_terminal_stress": close(history[-1]["mean_effective_stress_pa_compression_positive"], terminal["mean_effective_stress_pa_compression_positive"]),
            "required_consecutive_tail_passes": len(tail) == required and all(row_passes(row, acceptance, target_void_ratio) for row in tail),
            "reported_checks_match": all(result["checks"].values()) and all(recomputed.values()),
        }
        passed = result.get("passed") is True and all(recomputed.values()) and all(artifact_checks.values())
        cases.append({
            "case_id": case_id,
            "preparation_friction_coefficient": result["preparation_friction_coefficient"],
            "passed": passed,
            "terminal": terminal,
            "recomputed_checks": recomputed,
            "artifact_checks": artifact_checks,
            "result_sha256": digest(result_path),
            "history_sha256": digest(history_path),
            "checkpoint_sha256": digest(checkpoint_path),
        })

    passed_cases = [case for case in cases if case["passed"]]
    selected = min(passed_cases, key=lambda case: abs(case["terminal"]["void_ratio"] - target_void_ratio)) if passed_cases else None
    passed = all(global_checks.values()) and len(cases) == 3 and len(passed_cases) == 3 and selected is not None
    evaluation = {
        "schema": "lbs.stage25a-load-bearing-pure-sand-pilot.v1.independent-evaluation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_and_selected" if passed else "failed_closed",
        "global_checks": global_checks,
        "cases": cases,
        "selection": None if selected is None else {
            "case_id": selected["case_id"],
            "preparation_friction_coefficient": selected["preparation_friction_coefficient"],
            "basis": "Minimum absolute void-ratio difference from the reported e=0.744 reference among independently passing cases; preparation friction is not interpreted as a calibrated LBS material property.",
            "void_ratio": selected["terminal"]["void_ratio"],
            "absolute_void_ratio_difference": abs(selected["terminal"]["void_ratio"] - target_void_ratio),
            "mean_effective_stress_pa": selected["terminal"]["mean_effective_stress_pa_compression_positive"],
            "coordination_excluding_rattlers": selected["terminal"]["coordination_excluding_degree_lt2_rattlers"],
            "rattler_fraction": selected["terminal"]["rattler_fraction_degree_lt2_iterative"],
            "real_contact_count": selected["terminal"]["real_contact_count"],
            "checkpoint_sha256": selected["checkpoint_sha256"],
        },
        "evidence": {
            "completion": str(completion_path),
            "completion_sha256": digest(completion_path),
            "config_sha256": digest(CONFIG),
            "runner_sha256": digest(RUNNER),
            "launcher_sha256": digest(LAUNCHER),
            "evaluator_sha256": digest(Path(__file__)),
        },
        "promotion": {
            "pure_sand_load_bearing_checkpoint_qualified": passed,
            "selected_checkpoint_authorized_for_fibre_mechanics_design": passed,
            "fibre_execution_authorized": False,
            "flow_authorized": False,
            "deformation_coupled_flow_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    evaluation_path = OUTPUT / "evaluation.json"
    with evaluation_path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    with (OUTPUT / "case_summary.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case_id", "mu_preparation", "passed", "void_ratio", "mean_stress_pa", "unbalanced_force", "coordination_excluding_rattlers", "rattler_fraction", "real_contacts"])
        for case in cases:
            value = case["terminal"]
            writer.writerow([case["case_id"], case["preparation_friction_coefficient"], case["passed"], value["void_ratio"], value["mean_effective_stress_pa_compression_positive"], value["unbalanced_force"], value["coordination_excluding_degree_lt2_rattlers"], value["rattler_fraction_degree_lt2_iterative"], value["real_contact_count"]])
    print(json.dumps({"passed": passed, "selected_case_id": evaluation["selection"]["case_id"] if selected else None, "evaluation_sha256": digest(evaluation_path)}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
