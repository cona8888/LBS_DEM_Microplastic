"""Evaluate and classify the first Stage26o two-F37 joint-deposition case."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main():
    run = ROOT / "stage26_runs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_mixture_01"
    config_path = ROOT / "stage26_designs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_mixture_design_01" / "mixture_config.json"
    runner_path = ROOT / "stage26_staging" / "run_stage26o_two_fibre_mixture_v1.py"
    result_path, completion_path, history_path = run / "result.json", run / "completion.json", run / "mixture_history.csv"
    output = ROOT / "stage26_evaluations" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_mixture_evaluation_01"
    if output.exists():
        raise RuntimeError("immutable mixture evaluation exists")
    config, result, completion = load(config_path), load(result_path), load(completion_path)
    with history_path.open("r", newline="") as stream:
        rows = list(csv.DictReader(stream))
    contacts = [json.loads(row["distinct_sand_contacts_by_fibre"]) for row in rows]
    wall_contacts = [json.loads(row["fibre_wall_real_contact_count_by_fibre"]) for row in rows]
    confinement = [row for row in rows if row["phase"] == "gravity_plus_wall_confinement"]
    recent_ub = [float(row["unbalanced_force"]) for row in confinement[-100:]]
    integrity = {
        "result_binds_config": result["source_hashes"]["config"] == sha256(config_path),
        "result_binds_runner": result["source_hashes"]["runner"] == sha256(runner_path),
        "completion_binds_result": completion["result_sha256"] == sha256(result_path),
        "result_binds_history": result["artifacts"]["history_sha256"] == sha256(history_path),
        "records_complete": result["records_written"] == len(rows),
        "no_unexpected_state": result["artifacts"]["state_sha256"] is None and completion["state_sha256"] is None,
    }
    terminal = result["terminal"]
    numerical_health = {
        "finite_terminal": all(abs(float(terminal[key])) < float("inf") for key in ("mean_wall_stress_pa_compression_positive", "unbalanced_force", "kinetic_energy_j", "maximum_interobject_penetration_over_smaller_radius")),
        "stress_within_gate": terminal["relative_mean_wall_stress_error"] <= config["acceptance"]["maximum_relative_mean_wall_stress_error"] and terminal["maximum_principal_wall_stress_error"] <= config["acceptance"]["maximum_principal_wall_stress_error"],
        "overlap_within_gate": terminal["maximum_interobject_penetration_over_smaller_radius"] <= config["acceptance"]["maximum_penetration_over_smaller_radius"],
        "sand_count_exact": terminal["particle_count"] == 216,
        "no_sand_leakage": terminal["leaked_particle_count"] == 0,
        "exact_fibre_discretization": terminal["fibre_member_count_by_fibre"] == [37, 37] and terminal["exact_fibre_member_radius_m"] == 5.0e-5,
    }
    diagnosis = {
        "qualified": result["qualified"],
        "status": result["status"],
        "confinement_transition_failed": result["confinement_streak"] == 0,
        "terminal_unbalanced_force": terminal["unbalanced_force"],
        "transition_unbalanced_force_limit": config["confinement_transition"]["maximum_unbalanced_force"],
        "last_100_confinement_unbalanced_force_mean": sum(recent_ub) / len(recent_ub),
        "last_100_confinement_unbalanced_force_range": [min(recent_ub), max(recent_ub)],
        "maximum_sand_contacts_by_fibre": [max(value[index] for value in contacts) for index in range(2)],
        "blocks_at_or_above_three_contacts_by_fibre": [sum(value[index] >= 3 for value in contacts) for index in range(2)],
        "blocks_both_fibres_at_or_above_three_contacts": sum(value[0] >= 3 and value[1] >= 3 for value in contacts),
        "maximum_wall_contacts_by_fibre": [max(value[index] for value in wall_contacts) for index in range(2)],
        "terminal_sand_contacts_by_fibre": terminal["distinct_sand_contacts_by_fibre"],
        "terminal_wall_contacts_by_fibre": terminal["fibre_wall_real_contact_count_by_fibre"],
        "terminal_translation_over_D50_by_fibre": terminal["fibre_translation_over_D50_by_fibre"],
        "terminal_rotation_deg_by_fibre": terminal["fibre_rotation_deg_by_fibre"],
        "classification": "numerically_healthy_but_uncaged_mobile_fibres_and_persistent_force_imbalance",
    }
    passed = all(integrity.values()) and all(numerical_health.values()) and result["passed"] and completion["passed"] and not result["qualified"]
    payload = {
        "schema": "lbs.stage26o-two-fibre-joint-deposition-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "preserved_nonqualification_classified" if passed else "evaluation_failed",
        "integrity": integrity,
        "numerical_health": numerical_health,
        "diagnosis": diagnosis,
        "claim_boundary": config["claim_boundary"],
        "authority": {"layered_joint_deposition_redesign_authorized": passed, "heldout_execution_authorized": False, "flow_execution_authorized": False, "deformation_authorized": False, "production_parametric_study_authorized": False},
        "sources": {"config": {"path": str(config_path), "sha256": sha256(config_path)}, "runner": {"path": str(runner_path), "sha256": sha256(runner_path)}, "result": {"path": str(result_path), "sha256": sha256(result_path)}, "completion": {"path": str(completion_path), "sha256": sha256(completion_path)}, "history": {"path": str(history_path), "sha256": sha256(history_path)}},
        "next_action": "design_one_layered_joint_deposition_attempt_with_fibres_inside_the_sand_fall_zone" if passed else "stop",
    }
    output.mkdir(parents=True)
    path = output / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation": str(path), "sha256": sha256(path)}, sort_keys=True))
    if not passed:
        raise RuntimeError("mixture evaluation failed")


if __name__ == "__main__":
    main()
