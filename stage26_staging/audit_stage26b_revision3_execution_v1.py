"""Audit exact Revision-3 execution configuration before generation."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26b_revision3_joint_placement_execution_v1.json"
DESIGN = ROOT / "stage26_staging/stage26b_revision3_joint_placement_design_v1.json"
REV2 = ROOT / "stage26_staging/stage26b_revision2_placement_generation_execution_v2.json"
OUTPUT = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/execution_evaluation_01/evaluation.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main():
    cfg = load(CONFIG)
    design = load(DESIGN)
    rev2 = load(REV2)
    checks = []
    failures = []

    def check(condition, label):
        checks.append({"check": label, "passed": bool(condition)})
        if not condition:
            failures.append(label)

    check(cfg["status"] == "authorized_stage26b_revision3_joint_placement_generation", "status authorizes only Revision-3 placement generation")
    for name, value in cfg["sources"].items():
        if name.endswith("_sha256"):
            continue
        check(Path(value).is_file(), f"source exists: {name}")
        check(digest(value) == cfg["sources"][name + "_sha256"], f"source hash matches: {name}")
    check(cfg["sources"]["generator_sha256"] == load(cfg["sources"]["generator_source_checkpoint"])["evidence"]["source_sha256"], "source checkpoint binds generator")
    check(load(cfg["sources"]["generator_source_checkpoint"])["passed"] is True, "generator checkpoint passed")
    check(load(cfg["sources"]["design_checkpoint"])["passed"] is True, "design checkpoint passed")

    gate_map = {
        "sand_particle_count": None,
        "real_sand_contact_count": None,
        "load_bearing_core_count": None,
        "fibre_count": "fibre_count_per_candidate",
        "members_per_fibre": "members_per_fibre",
        "member_radius_m": "member_radius_m",
        "anchor_member_indices": "anchor_member_indices",
        "target_anchor_penetration_over_member_radius": "target_anchor_penetration_over_member_radius",
        "maximum_sand_fibre_penetration_over_member_radius": "maximum_sand_fibre_penetration_over_member_radius",
        "anchor_pair_distance_m": "anchor_pair_distance_m",
        "minimum_anchor_network_degree": "minimum_anchor_network_degree",
        "preferred_anchor_network_degree": "preferred_anchor_network_degree",
        "maximum_anchor_multiplicity_across_fibres": "maximum_anchor_multiplicity_across_fibres",
        "maximum_initial_force_residual_relative": "maximum_initial_force_residual_relative",
        "maximum_initial_moment_residual_relative": "maximum_initial_moment_residual_relative",
        "minimum_initial_fibre_fibre_clearance_m": "minimum_initial_fibre_fibre_clearance_m",
        "fibres_wholly_inside_primary_cell": "fibres_wholly_inside_primary_cell",
        "zero_initial_fibre_fibre_overlap": "zero_initial_fibre_fibre_overlap"
    }
    for design_name, config_name in gate_map.items():
        if config_name is None:
            continue
        check(cfg["generator_contract"][config_name] == design["unchanged_physical_gates"][design_name], f"design physical gate unchanged: {design_name}")
        check(cfg["generator_contract"][config_name] == rev2["generator_contract"][config_name], f"Revision-2 physical gate unchanged: {config_name}")
    check(cfg["generator_contract"]["anchor_must_be_in_degree2_core"] is True, "degree-2 core anchor gate remains true")
    check(cfg["generator_contract"]["initial_distinct_sand_contacts_per_fibre"] == [2, 2], "exactly two initial contacts per fibre")
    check(cfg["generator_contract"]["maximum_trials_per_candidate"] == 400000, "legacy maximum trial ceiling unchanged")
    check(cfg["search_contract"]["maximum_proposals_per_candidate"] == 400000, "Revision-3 proposal ceiling is 400000")
    for name in ("algorithm", "analytical_tolerance_m", "maximum_proposals_per_candidate", "maximum_retained_single_fibres", "maximum_retained_placements_per_anchor_pair", "joint_pair_requires_disjoint_anchors", "joint_pair_test_after_each_retained_single", "stop_candidate_after_first_admissible_joint_pair", "preserve_every_proposal_and_rejection"):
        design_name = "revision3_search"
        check(cfg["search_contract"][name] == design[design_name][name], f"search design binds: {name}")
    check(len(cfg["candidates"]) == 12, "exactly 12 candidates")
    expected_seeds = [202608142100 + 17 * i for i in range(12)]
    check([row["seed"] for row in cfg["candidates"]] == expected_seeds, "candidate seeds exactly match frozen design")
    check([row["seed"] for row in cfg["candidates"]] == [row["seed"] for row in rev2["candidates"]], "candidate seeds exactly match Revision 2")
    check(Path(cfg["execution"]["config_path"]).resolve() == CONFIG.resolve(), "execution config path is self-binding")
    check(not Path(cfg["execution"]["output"]).exists(), "immutable execution output does not exist")
    check(cfg["execution"]["argv"] == ["python", cfg["sources"]["generator"], "--config", str(CONFIG).replace("\\", "/"), "--output", cfg["execution"]["output"]], "argv exactly binds generator, config, and output")
    check(cfg["execution"]["host_python_only"] is True and cfg["execution"]["yade_invoked"] is False, "host-Python only; YADE excluded")
    check(cfg["authority"]["placement_generation_authorized"] is True, "placement generation authorized")
    for name in ("prefilter_yade_execution_authorized", "two_fibre_free_release_authorized", "four_fibre_execution_authorized", "flow_execution_authorized", "production_parametric_study_authorized"):
        check(cfg["authority"][name] is False, f"downstream authority remains false: {name}")
    passed = not failures
    evaluation = {
        "schema": "lbs.stage26b-revision3-joint-placement-execution-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_exact_execution_audit" if passed else "failed_exact_execution_audit",
        "checks": checks,
        "failures": failures,
        "evidence": {"config_path": str(CONFIG), "config_sha256": digest(CONFIG)},
        "authority": {"placement_generation_authorized": passed, "prefilter_yade_execution_authorized": False},
        "claim_boundary": cfg["claim_boundary"]
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    OUTPUT.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(OUTPUT)}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
