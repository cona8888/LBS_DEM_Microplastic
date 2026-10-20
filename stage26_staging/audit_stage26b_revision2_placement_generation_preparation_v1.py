"""Audit the deterministic placement-generator preparation contract."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_placement_generation_preparation_v1.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "placement_generation_preparation_evaluation_01"


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
        raise RuntimeError("immutable preparation evaluation already exists")
    cfg = load_json(CONFIG)
    paths = {name: Path(value) for name, value in cfg["sources"].items() if not name.endswith("_sha256")}
    design = load_json(paths["design_config"])
    resolved = load_json(paths["resolved_design"])
    network_checkpoint = load_json(paths["network_export_checkpoint"])
    network = load_json(paths["network"])
    erratum = load_json(paths["core_count_erratum_checkpoint"])
    stage26a = load_json(paths["stage26a_design_config"])
    geometry = load_json(paths["f37_geometry_review"])
    with paths["trial_schedule"].open("r", newline="", encoding="utf-8") as stream:
        schedule = list(csv.DictReader(stream))
    candidates = [row for row in schedule if row["record_type"] == "candidate"]
    expected_seeds = [202608142100 + 17 * index for index in range(12)]
    template = geometry["fibre_candidates"]["f37_kinked_ar10"]
    contract = cfg["generator_contract"]
    baseline = cfg["corrected_network_baseline"]
    checks = {
        "all_source_hashes_match": all(digest(path) == cfg["sources"][name + "_sha256"] for name, path in paths.items()),
        "network_checkpoint_passed": network_checkpoint.get("passed") is True and network_checkpoint.get("status") == "frozen_verified_exact_stage25_network_export",
        "exact_network_baseline": (
            network.get("passed") is True and network["periodic"] is True
            and network["sand_particle_count"] == baseline["sand_particle_count"] == 216
            and network["sand_contact_count"] == baseline["real_sand_sand_contact_count"] == 361
            and network["core_degree_threshold"] == baseline["iterative_core_degree_threshold"] == 2
            and network["load_bearing_particle_count"] == baseline["load_bearing_core_count"] == 175
        ),
        "erratum_is_only_design_override": (
            baseline["supersedes_design_core_count_only"] == design["network_export"]["required_baseline_load_bearing_particle_count"] == resolved["network_export"]["required_baseline_load_bearing_particle_count"] == 180
            and erratum["corrected_gate"]["required_load_bearing_particle_count"] == 175
        ),
        "twelve_candidate_schedule_exact": (
            len(candidates) == 12
            and [int(row["candidate_index"]) for row in candidates] == list(range(1, 13))
            and [int(row["seed"]) for row in candidates] == expected_seeds
            and cfg["deterministic_schedule"]["candidate_ids"] == [row["trial_id"] for row in candidates]
        ),
        "f37_geometry_exact": (
            stage26a["fibre"]["template_id"] == "f37_kinked_ar10"
            and len(template["members"]) == contract["members_per_fibre"] == 37
            and stage26a["fibre"]["member_radius_m"] == contract["member_radius_m"] == 0.00005
        ),
        "anchor_and_contact_gates_match_design": (
            contract["anchor_member_indices"] == design["candidate_generation"]["anchor_member_indices"]
            and contract["anchor_pair_distance_m"] == [design["candidate_generation"]["anchor_pair_distance_minimum_m"], design["candidate_generation"]["anchor_pair_distance_maximum_m"]]
            and contract["minimum_anchor_network_degree"] == design["candidate_generation"]["minimum_anchor_sand_network_degree"]
            and contract["preferred_anchor_network_degree"] == design["candidate_generation"]["preferred_anchor_sand_network_degree"]
            and contract["initial_distinct_sand_contacts_per_fibre"] == [2, 2]
        ),
        "balance_clearance_and_budget_gates_match_design": (
            contract["maximum_initial_force_residual_relative"] == design["candidate_generation"]["maximum_initial_normal_force_residual_relative"]
            and contract["maximum_initial_moment_residual_relative"] == design["candidate_generation"]["maximum_initial_normal_moment_residual_relative"]
            and contract["minimum_initial_fibre_fibre_clearance_m"] == design["candidate_generation"]["minimum_initial_fibre_fibre_clearance_over_D50"] * design["candidate_generation"]["D50_m"]
            and contract["maximum_trials_per_candidate"] == design["candidate_generation"]["maximum_trials_per_candidate"]
            and contract["preserve_every_attempt_and_rejection"] is True
            and contract["forbid_budget_extension_after_outcome_inspection"] is True
        ),
        "future_output_is_new_and_complete": (
            not Path(cfg["immutable_output_contract"]["future_output_root"]).exists()
            and cfg["immutable_output_contract"]["per_candidate_files"] == ["placement.json", "attempts.csv.gz", "completion.json"]
            and cfg["immutable_output_contract"]["partial_or_budget_exhausted_candidates_must_be_published"] is True
            and cfg["immutable_output_contract"]["no_overwrite"] is True
        ),
        "no_generation_or_yade_authority": (
            cfg["authority"]["placement_generator_source_implementation_authorized"] is True
            and cfg["authority"]["placement_generator_source_audit_authorized"] is True
            and all(value is False for name, value in cfg["authority"].items() if name not in ("placement_generator_source_implementation_authorized", "placement_generator_source_audit_authorized"))
            and "YADE must not be imported or invoked" in contract["execution_runtime"]
        ),
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-placement-generation-preparation-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_deterministic_placement_generation_preparation" if passed else "failed_placement_generation_preparation",
        "checks": checks,
        "evidence": {
            "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
            "network_checkpoint_path": str(paths["network_export_checkpoint"]), "network_checkpoint_sha256": digest(paths["network_export_checkpoint"]),
            "network_path": str(paths["network"]), "network_sha256": digest(paths["network"]),
            "erratum_checkpoint_path": str(paths["core_count_erratum_checkpoint"]), "erratum_checkpoint_sha256": digest(paths["core_count_erratum_checkpoint"]),
            "design_checkpoint_path": str(paths["design_checkpoint"]), "design_checkpoint_sha256": digest(paths["design_checkpoint"]),
            "auditor_sha256": digest(Path(__file__)),
        },
        "authority": {
            "authorized_next_activity": "Implement and independently audit the deterministic host-Python placement generator against this contract; do not generate candidates or execute YADE yet.",
            "placement_generator_source_implementation_authorized": passed,
            "placement_generator_source_audit_authorized": passed,
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
        print(json.dumps({"failed_checks": [name for name, value in checks.items() if not value]}, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
