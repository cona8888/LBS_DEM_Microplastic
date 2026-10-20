"""Independently audit the Stage26b Tier-1 Revision-2 design artifacts."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_tier1_placement_stability_revision2_design_v1.json"
DESIGN_ROOT = PROJECT / "stage26_designs" / "stage26b_tier1_placement_stability_revision2_20260814" / "design_02"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260814" / "design_evaluation_02"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable evaluation output already exists")
    cfg = load_json(CONFIG)
    manifest_path = DESIGN_ROOT / "design_manifest.json"
    resolved_path = DESIGN_ROOT / "resolved_design.json"
    schedule_path = DESIGN_ROOT / "trial_schedule.csv"
    manifest = load_json(manifest_path)
    resolved = load_json(resolved_path)
    with schedule_path.open("r", newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    checks = {}
    checks["manifest_bindings"] = (
        manifest["resolved_design_sha256"] == digest(resolved_path)
        and manifest["trial_schedule_sha256"] == digest(schedule_path)
        and manifest["config_sha256"] == digest(CONFIG)
    )
    checks["source_bindings"] = all(
        digest(Path(text)) == cfg["sources"][key + "_sha256"]
        for key, text in cfg["sources"].items()
        if not key.endswith("_sha256")
    )
    failure = load_json(Path(cfg["sources"]["failure_checkpoint"]))
    checks["failure_signature"] = (
        failure.get("passed") is True
        and failure.get("scientific_outcome_passed") is False
        and failure["terminal_metrics"]["distinct_sand_contacts_by_fibre"] == [0, 2]
        and failure["authority"]["two_fibre_rerun_authorized"] is False
    )
    positive = load_json(Path(cfg["sources"]["positive_control_completion"]))
    negative = load_json(Path(cfg["sources"]["negative_control_completion"]))
    checks["control_evidence_semantics"] = (
        positive.get("passed") is True
        and positive.get("status") == "passed_dry_free_fibre_compatibility"
        and negative.get("passed") is False
        and negative.get("status") == "completed_no_admissible_tier1_dry_multifibre_state"
    )
    original_place = load_json(Path(cfg["sources"]["original_placement_config"]))
    original_run = load_json(Path(cfg["sources"]["original_execution_config"]))
    frozen = cfg["frozen_physics"]
    checks["physics_unchanged"] = (
        frozen["target_anchor_penetration_over_member_radius"] == original_place["search"]["target_anchor_penetration_over_member_radius"]
        and frozen["maximum_sand_fibre_penetration_over_member_radius"] == original_place["search"]["maximum_sand_fibre_penetration_over_member_radius"]
        and frozen["target_mean_effective_stress_pa"] == original_run["relaxation"]["target_mean_effective_stress_pa_compression_positive"]
        and frozen["newton_damping"] == original_run["relaxation"]["newton_damping"]
        and frozen["timestep_safety_coefficient"] == original_run["relaxation"]["timestep_safety_coefficient"]
        and frozen["plastic_young_pa"] == original_run["contacts"]["plastic_young_pa"]
        and frozen["plastic_friction_coefficient"] == original_run["contacts"]["plastic_friction_coefficient"]
        and frozen["fibre_members"] == original_run["fibre"]["members_per_fibre"]
    )
    candidate_rows = [row for row in rows if row["record_type"] == "candidate"]
    control_rows = [row for row in rows if row["record_type"] == "control"]
    expected_seeds = [
        cfg["candidate_generation"]["candidate_seed_base"] + index * cfg["candidate_generation"]["candidate_seed_stride"]
        for index in range(cfg["candidate_generation"]["candidate_count"])
    ]
    checks["predeclared_bounded_schedule"] = (
        len(rows) == 14
        and len(control_rows) == 2
        and len(candidate_rows) == 12
        and [int(row["seed"]) for row in candidate_rows] == expected_seeds
        and len({row["trial_id"] for row in rows}) == len(rows)
    )
    checks["controls_precede_candidates"] = (
        [row["trial_id"] for row in rows[:2]] == ["positive_stage26a", "negative_stage26b_failure"]
        and all(row["record_type"] == "candidate" for row in rows[2:])
    )
    generation = cfg["candidate_generation"]
    checks["screen_tightened_without_overlap_tuning"] = (
        generation["maximum_initial_normal_force_residual_relative"] == 0.05
        and generation["maximum_initial_normal_moment_residual_relative"] == 0.02
        and generation["maximum_anchor_multiplicity_across_fibres"] == 1
        and generation["anchor_in_load_bearing_core_required"] is True
        and generation["minimum_anchor_sand_network_degree"] >= 3
    )
    prefilter = cfg["prefilter"]
    checks["prefilter_is_fixed_and_bounded"] = (
        prefilter["all_fibres_fixed"] is True
        and prefilter["free_release"] is False
        and prefilter["steps_per_block"] == 500
        and prefilter["blocks"] == 10
        and prefilter["controls_must_pass_before_candidate_screen"] is True
        and prefilter["publish_all_control_and_candidate_outcomes"] is True
    )
    forbidden = [name for name, value in cfg["authority"].items() if name not in {"design_builder_execution_authorized", "design_audit_authorized"} and value]
    checks["no_physics_execution_authority"] = not forbidden
    checks["resolved_matches_config"] = (
        resolved["candidate_count"] == cfg["candidate_generation"]["candidate_count"]
        and resolved["trial_count"] == len(rows)
        and resolved["authority"] == cfg["authority"]
        and resolved["source_hashes"]["config"] == digest(CONFIG)
    )
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-tier1-placement-stability-revision2-design-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_design_audit_no_physics_execution" if passed else "failed_design_audit",
        "checks": checks,
        "design_summary": {
            "controls": 2,
            "two_fibre_candidates": 12,
            "fixed_conditioning_steps_per_trial": 5000,
            "maximum_candidate_conditioning_steps": 60000,
            "anchor_degree_minimum": generation["minimum_anchor_sand_network_degree"],
            "anchor_reuse_maximum": generation["maximum_anchor_multiplicity_across_fibres"],
            "force_residual_limit": generation["maximum_initial_normal_force_residual_relative"],
            "moment_residual_limit": generation["maximum_initial_normal_moment_residual_relative"],
        },
        "evidence": {
            "config_path": str(CONFIG),
            "config_sha256": digest(CONFIG),
            "design_manifest_path": str(manifest_path),
            "design_manifest_sha256": digest(manifest_path),
            "resolved_design_path": str(resolved_path),
            "resolved_design_sha256": digest(resolved_path),
            "trial_schedule_path": str(schedule_path),
            "trial_schedule_sha256": digest(schedule_path),
            "auditor_sha256": digest(Path(__file__)),
        },
        "authority": {
            "authorized_next_activity": "Implement and independently audit the Stage25 contact-network exporter and the fixed-conditioning prefilter source; do not execute either yet.",
            "network_export_execution_authorized": False,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(path)}, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
