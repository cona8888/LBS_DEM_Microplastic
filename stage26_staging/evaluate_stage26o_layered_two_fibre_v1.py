"""Audit and classify Stage26o layered-pluviation Design 03."""
import csv
import hashlib
import json
import statistics
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
    config_path = ROOT / "stage26_designs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_layered_design_03" / "mixture_config.json"
    runner_path = ROOT / "stage26_staging" / "run_stage26o_layered_two_fibre_mixture_v3.py"
    run = ROOT / "stage26_runs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_layered_03"
    result_path, completion_path, history_path = run / "result.json", run / "completion.json", run / "mixture_history.csv"
    output = ROOT / "stage26_evaluations" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_layered_evaluation_03"
    if output.exists():
        raise RuntimeError("immutable layered evaluation exists")
    config, result, completion = load(config_path), load(result_path), load(completion_path)
    with history_path.open("r", newline="") as stream:
        rows = list(csv.DictReader(stream))
    contacts = [json.loads(row["distinct_sand_contacts_by_fibre"]) for row in rows]
    wall_contacts = [json.loads(row["fibre_wall_real_contact_count_by_fibre"]) for row in rows]
    energies = [float(row["normalized_kinetic_energy_weight_D50"]) for row in rows]
    unbalanced = [float(row["unbalanced_force"]) for row in rows]
    leakage = [int(row["leaked_fibre_member_count"]) for row in rows]
    positions = [json.loads(row["fibre_parent_positions_m"]) for row in rows]
    terminal = result["terminal"]
    integrity = {
        "result_binds_config": result["source_hashes"]["config"] == sha256(config_path),
        "result_binds_runner": result["source_hashes"]["runner"] == sha256(runner_path),
        "completion_binds_result": completion["result_sha256"] == sha256(result_path),
        "result_binds_history": result["artifacts"]["history_sha256"] == sha256(history_path),
        "records_complete": result["records_written"] == len(rows) == 1200,
        "no_qualified_state_expected": result["artifacts"]["state_sha256"] is None and completion["state_sha256"] is None,
    }
    numerical_health = {
        "exact_sand_count": terminal["particle_count"] == 216,
        "exact_fibre_geometry": terminal["fibre_member_count_by_fibre"] == [37, 37] and terminal["exact_fibre_member_radius_m"] == 5.0e-5,
        "no_sand_leakage": terminal["leaked_sand_particle_count"] == 0,
        "no_fibre_leakage": terminal["leaked_fibre_member_count"] == 0 and max(leakage) == 0,
        "overlap_within_gate": terminal["maximum_interobject_penetration_over_smaller_radius"] <= config["acceptance"]["maximum_penetration_over_smaller_radius"],
        "finite_terminal": all(abs(float(terminal[key])) < float("inf") for key in ("unbalanced_force", "kinetic_energy_j", "maximum_interobject_penetration_over_smaller_radius")),
    }
    tail = 200
    diagnosis = {
        "qualified": result["qualified"],
        "status": result["status"],
        "failure_class": "geometry_and_preparation_nonqualification",
        "settling_energy_gate": config["settling"]["maximum_normalized_kinetic_energy_weight_D50"],
        "terminal_normalized_kinetic_energy_weight_D50": terminal["normalized_kinetic_energy_weight_D50"],
        "last_200_energy_mean": statistics.mean(energies[-tail:]),
        "last_200_energy_min_max": [min(energies[-tail:]), max(energies[-tail:])],
        "last_200_first_half_energy_mean": statistics.mean(energies[-tail:-100]),
        "last_200_second_half_energy_mean": statistics.mean(energies[-100:]),
        "last_200_unbalanced_force_mean": statistics.mean(unbalanced[-tail:]),
        "maximum_sand_contacts_by_fibre": [max(value[index] for value in contacts) for index in range(2)],
        "blocks_at_or_above_three_contacts_by_fibre": [sum(value[index] >= 3 for value in contacts) for index in range(2)],
        "blocks_both_fibres_at_or_above_three_contacts": sum(value[0] >= 3 and value[1] >= 3 for value in contacts),
        "maximum_wall_contacts_by_fibre": [max(value[index] for value in wall_contacts) for index in range(2)],
        "terminal_parent_z_m": [value[2] for value in positions[-1]],
        "last_200_parent_z_range_m": [[min(value[index][2] for value in positions[-tail:]), max(value[index][2] for value in positions[-tail:])] for index in range(2)],
        "interpretation": "Layering improved temporary support for fibre 1 but did not cage fibre 2; persistent energy oscillation and absence of simultaneous cages make a longer dry run or relaxed gate unjustified.",
    }
    passed = all(integrity.values()) and all(numerical_health.values()) and result.get("passed") and completion.get("passed") and not result.get("qualified")
    payload = {
        "schema": "lbs.stage26o-layered-two-fibre-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "layered_preparation_nonqualification_preserved" if passed else "evaluation_failed",
        "integrity": integrity,
        "numerical_health": numerical_health,
        "diagnosis": diagnosis,
        "claim_boundary": config["claim_boundary"],
        "authority": {"another_full_mixture_run_authorized": False, "single_fibre_missing_mechanism_verification_design_authorized": passed, "flow_execution_authorized": False, "deformation_authorized": False, "production_parametric_study_authorized": False},
        "sources": {"config": {"path": str(config_path), "sha256": sha256(config_path)}, "runner": {"path": str(runner_path), "sha256": sha256(runner_path)}, "result": {"path": str(result_path), "sha256": sha256(result_path)}, "completion": {"path": str(completion_path), "sha256": sha256(completion_path)}, "history": {"path": str(history_path), "sha256": sha256(history_path)}},
        "next_action": "design_and_verify_a_single_fibre_preparation_mechanism_benchmark_before_any_another_full_mixture",
    }
    output.mkdir(parents=True)
    path = output / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation": str(path), "sha256": sha256(path)}, sort_keys=True))
    if not passed:
        raise RuntimeError("layered evaluation failed")


if __name__ == "__main__":
    main()
