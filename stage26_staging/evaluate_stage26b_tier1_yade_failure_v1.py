"""Independently evaluate the adaptive Stage26b Tier-1 two-fibre failure."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_tier1_yade_execution_v1.json"
RUN_ROOT = PROJECT / "stage26_runs" / "stage26b_dry_multifibre_20260814" / "qualification_01"
RUN = RUN_ROOT / "stage26b_f002_A"
PROBE = RUN_ROOT / "initial_contact_probe_01.json"
FOUR_FIBRE_RUN = RUN_ROOT / "stage26b_f004_A"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_dry_multifibre_20260814" / "tier1_yade_evaluation_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def float_value(row, name):
    return float(row[name])


def row_passes(row, acceptance):
    contacts = json.loads(row["distinct_sand_contacts_by_fibre"])
    finite_names = [
        "cell_volume_m3", "mean_effective_stress_pa_compression_positive", "unbalanced_force",
        "normalized_kinetic_energy_pV", "maximum_interobject_penetration_over_smaller_radius",
        "sand_coordination_excluding_degree_lt2_rattlers", "sand_rattler_fraction_degree_lt2_iterative",
        "rms_nonaffine_sand_displacement_over_D50", "maximum_nonaffine_sand_displacement_over_D50",
        "maximum_fibre_com_displacement_over_length", "maximum_fibre_tip_axis_rotation_degrees",
        "maximum_fibre_tip_span_relative_drift",
    ]
    checks = {
        "finite_state": all(math.isfinite(float_value(row, name)) for name in finite_names),
        "mean_stress": float_value(row, "relative_mean_stress_error") <= acceptance["maximum_relative_mean_stress_error"],
        "principal_stress": float_value(row, "maximum_principal_stress_error") <= acceptance["maximum_principal_stress_error"],
        "unbalanced_force_defined": row["unbalanced_force_defined"].lower() == "true",
        "unbalanced_force": float_value(row, "unbalanced_force") <= acceptance["maximum_unbalanced_force"],
        "normalized_kinetic_energy": float_value(row, "normalized_kinetic_energy_pV") <= acceptance["maximum_normalized_kinetic_energy_pV"],
        "sand_coordination": float_value(row, "sand_coordination_excluding_degree_lt2_rattlers") >= acceptance["minimum_sand_coordination_excluding_rattlers"],
        "sand_rattler_fraction": float_value(row, "sand_rattler_fraction_degree_lt2_iterative") <= acceptance["maximum_sand_rattler_fraction"],
        "sand_contact_retention": float_value(row, "sand_sand_contact_retention_fraction") >= acceptance["minimum_sand_sand_contact_retention_fraction"],
        "every_fibre_engaged": min(contacts) >= acceptance["minimum_distinct_terminal_sand_contacts_per_fibre"],
        "no_isolated_fibre": sum(value == 0 for value in contacts) <= acceptance["maximum_isolated_fibre_count"],
        "penetration": float_value(row, "maximum_interobject_penetration_over_smaller_radius") <= acceptance["maximum_interobject_penetration_over_smaller_radius"],
        "sand_rms_displacement": float_value(row, "rms_nonaffine_sand_displacement_over_D50") <= acceptance["maximum_rms_sand_displacement_over_D50"],
        "sand_max_displacement": float_value(row, "maximum_nonaffine_sand_displacement_over_D50") <= acceptance["maximum_sand_displacement_over_D50"],
        "cell_volume_drift": float_value(row, "cell_volume_relative_drift") <= acceptance["maximum_cell_volume_relative_drift"],
        "all_fibres_rigid": float_value(row, "maximum_fibre_tip_span_relative_drift") <= acceptance["maximum_tip_span_relative_drift"],
        "all_fibre_translations": float_value(row, "maximum_fibre_com_displacement_over_length") <= acceptance["maximum_fibre_com_displacement_over_length"],
        "all_fibre_rotations": float_value(row, "maximum_fibre_tip_axis_rotation_degrees") <= acceptance["maximum_fibre_rotation_degrees"],
        "no_intraclump_contact": int(row["intraclump_real_interaction_count"]) == 0,
    }
    return checks


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable Stage26b failure evaluation already exists")
    cfg = load_json(CONFIG)
    result_path = RUN / "result.json"
    completion_path = RUN / "completion.json"
    conditioning_path = RUN / "conditioning_history.csv"
    free_path = RUN / "free_relaxation_history.csv"
    checkpoint_path = RUN / "dry_relaxed_state.yade.gz"
    result = load_json(result_path)
    completion = load_json(completion_path)
    probe = load_json(PROBE)
    conditioning = read_csv(conditioning_path)
    free = read_csv(free_path)
    case = next(row for row in cfg["cases"] if row["case_id"] == "stage26b_f002_A")
    failed_checks = sorted(name for name, passed in result["checks"].items() if not passed)
    independent_free_checks = [row_passes(row, cfg["acceptance"]) for row in free]
    independent_pass_flags = [all(checks.values()) for checks in independent_free_checks]
    checks = {
        "config_binding": result["source_hashes"]["config"] == digest(CONFIG),
        "runner_binding": result["source_hashes"]["runner"] == digest(PROJECT / "stage26_staging" / "stage26b_yade_tier1_dry_relaxation_v1.py"),
        "placement_binding": result["source_hashes"]["placement"] == case["placement_sha256"],
        "completion_result_binding": completion["result_sha256"] == digest(result_path),
        "conditioning_history_binding": result["artifacts"]["conditioning_history_csv_sha256"] == digest(conditioning_path),
        "free_history_binding": result["artifacts"]["free_relaxation_history_csv_sha256"] == digest(free_path),
        "checkpoint_binding": result["artifacts"]["checkpoint_sha256"] == digest(checkpoint_path),
        "expected_engine": result["engine"]["yade_version"] == cfg["sources"]["expected_yade_version"],
        "exact_case": result["case"] == case,
        "probe_sources_bind": probe["source_hashes"]["config"] == digest(CONFIG) and probe["source_hashes"]["placement"] == case["placement_sha256"],
        "all_contacts_created_at_insertion": probe["passed"] is True and probe["observed_real_sand_contact_ids_by_fibre_after_one_step"] == [[133, 204], [1, 11]],
        "conditioning_protocol_complete": len(conditioning) == cfg["relaxation"]["fixed_all_fibres_conditioning_blocks"] == 60,
        "free_resource_ceiling_reached": len(free) == cfg["relaxation"]["maximum_check_blocks"] == 500,
        "no_independent_free_pass_block": not any(independent_pass_flags),
        "failure_is_only_engagement": failed_checks == ["every_fibre_engaged", "no_isolated_fibre"],
        "terminal_contacts_are_zero_and_two": result["terminal"]["distinct_sand_contacts_by_fibre"] == [0, 2],
        "first_conditioning_block_already_lost_fibre_zero": json.loads(conditioning[0]["distinct_sand_contacts_by_fibre"]) == [0, 2],
        "sand_network_recovers": result["terminal"]["sand_sand_contact_retention_fraction"] >= 1.0 and result["terminal"]["sand_coordination_excluding_degree_lt2_rattlers"] >= 3.0,
        "result_and_completion_correctly_fail": result["passed"] is False and completion["passed"] is False and result["consecutive_pass_blocks"] == 0,
        "adaptive_stop_honored": not FOUR_FIBRE_RUN.exists(),
        "no_failure_json": not (RUN / "failure.json").exists(),
    }
    if not all(checks.values()):
        raise RuntimeError("Stage26b failure evidence audit failed: " + repr(checks))
    evaluation = {
        "schema": "lbs.stage26b-tier1-yade-failure-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "verified_physical_conditioning_failure_at_two_fibres",
        "case_id": case["case_id"],
        "scientific_outcome_passed": False,
        "failure_classification": "geometry-conditioning failure: all anchors exist at insertion, then fibre 0 loses both contacts during the first fixed-conditioning block and stays isolated",
        "terminal": result["terminal"],
        "failed_acceptance_checks": failed_checks,
        "checks": checks,
        "evidence": {
            "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
            "result_path": str(result_path), "result_sha256": digest(result_path),
            "completion_path": str(completion_path), "completion_sha256": digest(completion_path),
            "probe_path": str(PROBE), "probe_sha256": digest(PROBE),
            "conditioning_history_sha256": digest(conditioning_path),
            "free_history_sha256": digest(free_path),
            "checkpoint_sha256": digest(checkpoint_path),
            "evaluator_sha256": digest(Path(__file__)),
        },
        "adaptive_decision": "Do not execute four fibres. Redesign Tier-1 placement stability before any campaign promotion.",
        "authority": {
            "four_fibre_execution_authorized": False,
            "placement_revision_design_authorized": True,
            "rerun_authorized": False,
            "eight_or_more_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "transient_two_way_coupling_authorized": False,
            "deformation_coupled_flow_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "status": evaluation["status"], "evaluation_sha256": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
