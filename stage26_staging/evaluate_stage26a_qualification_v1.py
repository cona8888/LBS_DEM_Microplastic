"""Independent fail-closed evaluation of Stage26a qualification_03."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26a_dry_f37_insertion_design_v1.json"
PLACEMENT = PROJECT / "stage26_placements" / "stage26a_dry_f37_insertion_20260813" / "placement_03" / "placement.json"
RUNNER = PROJECT / "stage26_staging" / "stage26a_yade_dry_f37_relaxation_v2.py"
BASE_RUNNER = PROJECT / "stage26_staging" / "stage26a_yade_dry_f37_relaxation_v1.py"
RUN = PROJECT / "stage26_runs" / "stage26a_dry_f37_insertion_20260813" / "qualification_03"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26a_dry_f37_insertion_20260813" / "evaluation_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def row_passes(row, acceptance):
    return all([
        str(row["unbalanced_force_defined"]).lower() == "true",
        float(row["relative_mean_stress_error"]) <= acceptance["maximum_relative_mean_stress_error"],
        float(row["maximum_principal_stress_error"]) <= acceptance["maximum_principal_stress_error"],
        float(row["unbalanced_force"]) <= acceptance["maximum_unbalanced_force"],
        float(row["normalized_kinetic_energy_pV"]) <= acceptance["maximum_normalized_kinetic_energy_pV"],
        float(row["sand_coordination_excluding_degree_lt2_rattlers"]) >= acceptance["minimum_sand_coordination_excluding_rattlers"],
        float(row["sand_rattler_fraction_degree_lt2_iterative"]) <= acceptance["maximum_sand_rattler_fraction"],
        int(row["distinct_sand_contacts_per_fibre"]) >= acceptance["minimum_distinct_sand_contacts_per_fibre"],
        float(row["maximum_interobject_penetration_over_smaller_radius"]) <= acceptance["maximum_interobject_penetration_over_smaller_radius"],
        float(row["rms_nonaffine_sand_displacement_over_D50"]) <= acceptance["maximum_rms_sand_displacement_over_D50"],
        float(row["maximum_nonaffine_sand_displacement_over_D50"]) <= acceptance["maximum_sand_displacement_over_D50"],
        float(row["cell_volume_relative_drift"]) <= acceptance["maximum_cell_volume_relative_drift"],
        float(row["fibre_tip_span_relative_drift"]) <= acceptance["maximum_tip_span_relative_drift"],
        float(row["fibre_com_displacement_over_length"]) <= acceptance["maximum_fibre_com_displacement_over_length"],
        float(row["fibre_tip_axis_rotation_degrees"]) <= acceptance["maximum_fibre_rotation_degrees"],
        int(row["intraclump_real_interaction_count"]) == 0,
    ])


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable evaluation output already exists")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.mkdir()
    cfg = load_json(CONFIG); placement = load_json(PLACEMENT)
    result_path = RUN / "result.json"; completion_path = RUN / "completion.json"
    result = load_json(result_path); completion = load_json(completion_path)
    conditioning_path = RUN / "conditioning_history.csv"; free_path = RUN / "free_relaxation_history.csv"; checkpoint_path = RUN / "dry_relaxed_state.yade.gz"
    conditioning = read_rows(conditioning_path); free = read_rows(free_path)
    acceptance = cfg["acceptance"]; required = cfg["relaxation"]["required_consecutive_pass_blocks"]
    particles = result["particles"]
    sand = [row for row in particles if row["phase"] == "sand"]
    fibre = [row for row in particles if row["phase"] == "fibre"]
    terminal = result["terminal"]
    source_checks = {
        "config_hash": result["source_hashes"]["config"] == digest(CONFIG) == placement["source_hashes"]["config"],
        "placement_hash": result["source_hashes"]["placement"] == digest(PLACEMENT),
        "runner_hash": result["source_hashes"]["runner"] == digest(RUNNER),
        "base_runner_hash": result["source_hashes"]["base_runner"] == digest(BASE_RUNNER),
        "stage25_checkpoint_hash": result["source_hashes"]["stage25_checkpoint"] == cfg["source"]["stage25_checkpoint_sha256"] == digest(Path(cfg["source"]["stage25_checkpoint"])),
        "stage25_manifest_hash": cfg["source"]["stage25_checkpoint_manifest_sha256"] == digest(Path(cfg["source"]["stage25_checkpoint_manifest"])),
        "stage25_evaluation_hash": cfg["source"]["stage25_evaluation_sha256"] == digest(Path(cfg["source"]["stage25_evaluation"])),
        "f37_geometry_hash": cfg["source"]["f37_geometry_review_sha256"] == digest(Path(cfg["source"]["f37_geometry_review"])),
    }
    artifact_checks = {
        "completion_result_hash": completion["result_sha256"] == digest(result_path),
        "conditioning_history_hash": result["artifacts"]["conditioning_history_csv_sha256"] == digest(conditioning_path),
        "free_history_hash": result["artifacts"]["free_relaxation_history_csv_sha256"] == digest(free_path),
        "checkpoint_hash": result["artifacts"]["checkpoint_sha256"] == digest(checkpoint_path),
        "terminal_row_bound": int(free[-1]["block"]) == terminal["block"] and math.isclose(float(free[-1]["mean_effective_stress_pa_compression_positive"]), terminal["mean_effective_stress_pa_compression_positive"], rel_tol=1e-12),
    }
    geometry_checks = {
        "placement_passed": placement.get("passed") is True,
        "placement_exactly_two_contacts": placement["initial_distinct_sand_contact_count"] == 2,
        "placement_force_balance": placement["initial_normal_force_residual_relative"] <= cfg["placement"]["maximum_initial_normal_force_residual_relative"],
        "placement_moment_balance": placement["initial_normal_moment_residual_relative"] <= cfg["placement"]["maximum_initial_normal_moment_residual_relative"],
        "sand_count": len(sand) == acceptance["required_sand_particle_count"] and len({row["body_id"] for row in sand}) == acceptance["required_sand_particle_count"],
        "fibre_count": len({row["parent_id"] for row in fibre}) == acceptance["required_fibre_count"],
        "fibre_member_count": len(fibre) == acceptance["required_fibre_member_count"],
        "checkpoint_velocities_reset": result["protocol"]["checkpoint_velocities_reset"] is True and result["initial"]["checkpoint_velocities_reset"] is True,
        "fixed_then_free_protocol": result["protocol"]["fixed_fibre_conditioning_blocks"] == cfg["relaxation"]["fixed_fibre_conditioning_blocks"] and result["protocol"]["free_fibre_relaxation_blocks"] == len(free),
    }
    terminal_checks = {
        "reported_all_checks": all(result["checks"].values()) and all(completion["checks"].values()),
        "result_and_completion_passed": result.get("passed") is True and completion.get("passed") is True,
        "five_consecutive_free_passes": len(free) >= required and all(row_passes(row, acceptance) for row in free[-required:]),
        "terminal_fibre_engaged": terminal["distinct_sand_contacts_per_fibre"] >= 2 and terminal["sand_fibre_real_contact_count"] >= 2,
        "sand_network_remains_load_bearing": terminal["sand_coordination_excluding_degree_lt2_rattlers"] >= 3.0 and terminal["sand_sand_real_contact_count"] > 0,
        "no_failure_file": not (RUN / "failure.json").exists(),
        "authority_boundary": completion["promotion"]["multi_fibre_execution_authorized"] is False and completion["promotion"]["flow_execution_authorized"] is False and completion["promotion"]["transient_two_way_coupling_authorized"] is False and completion["promotion"]["deformation_coupled_flow_authorized"] is False,
    }
    passed = all(source_checks.values()) and all(artifact_checks.values()) and all(geometry_checks.values()) and all(terminal_checks.values())
    evaluation = {
        "schema": "lbs.stage26a-dry-f37-insertion.v2.independent-evaluation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": passed,
        "status": "passed_dry_single_fibre_checkpoint" if passed else "failed_closed",
        "source_checks": source_checks, "artifact_checks": artifact_checks, "geometry_checks": geometry_checks, "terminal_checks": terminal_checks,
        "initial_placement": {"anchor_sand_body_ids": placement["anchor_sand_body_ids"], "force_residual_relative": placement["initial_normal_force_residual_relative"], "moment_residual_relative": placement["initial_normal_moment_residual_relative"], "anchor_penetration_m": -min(placement["anchor_clearances_m"])},
        "conditioning_terminal": result["conditioning_terminal"], "terminal": terminal,
        "comparison_to_stage25": {"stage25_sand_sand_contacts": 361, "stage26_sand_sand_contacts": terminal["sand_sand_real_contact_count"], "contact_count_change": terminal["sand_sand_real_contact_count"] - 361, "stage25_coordination_excluding_rattlers": 4.1257142857142854, "stage26_coordination_excluding_rattlers": terminal["sand_coordination_excluding_degree_lt2_rattlers"]},
        "evidence": {"result_sha256": digest(result_path), "completion_sha256": digest(completion_path), "checkpoint_sha256": digest(checkpoint_path), "evaluator_sha256": digest(Path(__file__))},
        "promotion": {"dry_single_fibre_checkpoint_qualified": passed, "design_of_multi_fibre_dry_qualification_authorized": passed, "multi_fibre_execution_authorized": False, "flow_execution_authorized": False, "transient_two_way_coupling_authorized": False, "deformation_coupled_flow_authorized": False},
        "claim_boundary": cfg["claim_boundary"],
    }
    evaluation_path = OUTPUT / "evaluation.json"
    with evaluation_path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False); stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(evaluation_path), "terminal_fibre_contacts": terminal["distinct_sand_contacts_per_fibre"]}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
