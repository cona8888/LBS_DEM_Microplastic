"""Independently verify the complete Revision-3 joint-placement campaign."""

import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CAMPAIGN = ROOT / "stage26_placements/stage26b_revision3_joint_placement_20260816/candidate_generation_01"
CONFIG = ROOT / "stage26_staging/stage26b_revision3_joint_placement_execution_v1.json"
EXECUTION_CHECKPOINT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/execution_checkpoint_01/checkpoint_manifest.json"
DEPENDENCY_CHECKPOINT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/execution_dependency_checkpoint_01/checkpoint_manifest.json"
OUTPUT = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/campaign_evaluation_01/evaluation.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def periodic_clearance(first, second, lengths, combined_radius):
    delta = first[:, None, :] - second[None, :, :]
    delta -= np.round(delta / lengths) * lengths
    return np.linalg.norm(delta, axis=2) - combined_radius


def balance_metrics(members, first_index, last_index, sand_a, sand_b, lengths):
    centre = members.mean(axis=0)
    forces = []
    moments = []
    for member_index, sand in ((first_index, sand_a), (last_index, sand_b)):
        delta = members[member_index] - sand
        delta -= np.round(delta / lengths) * lengths
        force = delta / np.linalg.norm(delta)
        forces.append(force)
        moments.append(np.cross(members[member_index] - centre, force))
    force_scale = sum(np.linalg.norm(value) for value in forces)
    force_residual = np.linalg.norm(np.sum(forces, axis=0)) / force_scale
    lever_scale = max(np.linalg.norm(members[last_index] - members[first_index]), 1e-30) * force_scale
    moment_residual = np.linalg.norm(np.sum(moments, axis=0)) / lever_scale
    return float(force_residual), float(moment_residual)


def main():
    cfg = load(CONFIG)
    campaign = load(CAMPAIGN / "completion.json")
    execution_checkpoint = load(EXECUTION_CHECKPOINT)
    dependency_checkpoint = load(DEPENDENCY_CHECKPOINT)
    network = load(cfg["sources"]["network"])
    checks = []
    failures = []

    def check(condition, label, candidate_id=None):
        row = {"check": label, "passed": bool(condition)}
        if candidate_id is not None:
            row["candidate_id"] = candidate_id
        checks.append(row)
        if not condition:
            failures.append((candidate_id + ": " if candidate_id else "") + label)

    check(campaign.get("passed") is True, "campaign completion passed")
    check(campaign["status"] == "completed_predeclared_joint_candidate_budgets", "campaign completed predeclared budgets")
    check(execution_checkpoint.get("passed") is True, "execution checkpoint passed")
    check(execution_checkpoint["evidence"]["config_sha256"] == digest(CONFIG), "execution checkpoint binds unchanged config")
    check(dependency_checkpoint.get("passed") is True, "supplemental dependency checkpoint passed")
    for name in ("execution_checkpoint", "generator", "placement_math_helper"):
        check(digest(dependency_checkpoint["evidence"][name]) == dependency_checkpoint["evidence"][name + "_sha256"], f"post-execution dependency hash matches: {name}")
    for name, expected in campaign["source_hashes"].items():
        path = {
            "config": CONFIG,
            "network": Path(cfg["sources"]["network"]),
            "generator": Path(cfg["sources"]["generator"]),
            "design_checkpoint": Path(cfg["sources"]["design_checkpoint"]),
        }[name]
        check(digest(path) == expected, f"campaign source hash matches: {name}")

    index_path = CAMPAIGN / "candidate_index.csv"
    screen_path = CAMPAIGN / "anchor_pair_screen.csv"
    check(digest(index_path) == campaign["candidate_index_sha256"], "candidate index hash matches")
    check(digest(screen_path) == campaign["anchor_pair_screen_sha256"], "anchor-pair screen hash matches")
    with index_path.open("r", newline="", encoding="utf-8") as stream:
        index_rows = list(csv.DictReader(stream))
    check(len(index_rows) == 12 == campaign["candidate_count"], "exactly 12 indexed candidates")
    check([int(row["seed"]) for row in index_rows] == [row["seed"] for row in cfg["candidates"]], "index seeds preserve predeclared order")

    particles = network["particles"]
    sand_centres = np.asarray([row["position_m"] for row in particles], dtype=float)
    sand_radii = np.asarray([row["radius_m"] for row in particles], dtype=float)
    lengths = np.asarray([network["cell_hsize_m"][i][i] for i in range(3)], dtype=float)
    contract = cfg["generator_contract"]
    member_radius = float(contract["member_radius_m"])
    target_penetration = contract["target_anchor_penetration_over_member_radius"] * member_radius
    maximum_penetration = contract["maximum_sand_fibre_penetration_over_member_radius"] * member_radius
    first_member, last_member = contract["anchor_member_indices"]

    with screen_path.open("r", newline="", encoding="utf-8") as stream:
        screen_rows = list(csv.DictReader(stream))
    independently_feasible = 0
    for row in screen_rows:
        shifted = abs(float(row["anchor_pair_distance_m"]) - float(row["tip_span_m"]))
        lower = abs(float(row["contact_radius_1_m"]) - float(row["contact_radius_2_m"]))
        upper = float(row["contact_radius_1_m"]) + float(row["contact_radius_2_m"])
        feasible = lower - cfg["search_contract"]["analytical_tolerance_m"] <= shifted <= upper + cfg["search_contract"]["analytical_tolerance_m"]
        check(feasible == (row["analytically_feasible"] == "True"), "analytical screen row is independently correct")
        independently_feasible += int(feasible)
    check(len(screen_rows) == campaign["topological_distance_anchor_pair_count"] == 2011, "anchor-pair screen contains 2011 topological/distance pairs")
    check(independently_feasible == campaign["analytically_feasible_anchor_pair_count"] == 761, "independent analytical feasibility count is 761")

    candidate_results = []
    total_ledger_rows = 0
    total_counts = Counter()
    for cfg_candidate, index_row in zip(cfg["candidates"], index_rows):
        candidate_id = cfg_candidate["candidate_id"]
        candidate_dir = CAMPAIGN / candidate_id
        placement_path = candidate_dir / "placement.json"
        ledger_path = candidate_dir / "attempts.csv.gz"
        completion_path = candidate_dir / "completion.json"
        check(placement_path.is_file() and ledger_path.is_file() and completion_path.is_file(), "three-file candidate bundle exists", candidate_id)
        placement = load(placement_path)
        completion = load(completion_path)
        check(digest(placement_path) == completion["placement_sha256"] == index_row["placement_sha256"], "placement hash chain matches", candidate_id)
        check(digest(ledger_path) == completion["attempts_sha256"] == index_row["attempts_sha256"], "ledger hash chain matches", candidate_id)
        check(placement["candidate"] == cfg_candidate, "candidate identity and seed bind config", candidate_id)
        check(placement["attempt_count"] == completion["attempt_count"] == int(index_row["attempt_count"]), "attempt count chain matches", candidate_id)
        check(placement["passed"] == completion["passed"] == (index_row["passed"] == "True"), "candidate passed state chain matches", candidate_id)
        check(placement["analytically_feasible_anchor_pair_count"] == 761, "candidate used exact analytical pair count", candidate_id)
        check(placement["topological_distance_anchor_pair_count"] == 2011, "candidate used exact screened pair count", candidate_id)
        check(placement["source_hashes"] == campaign["source_hashes"], "candidate source hashes bind campaign", candidate_id)
        ledger_counts = Counter()
        ledger_rows = 0
        last_attempt = 0
        with gzip.open(ledger_path, "rt", newline="", encoding="utf-8") as stream:
            for ledger_row in csv.DictReader(stream):
                ledger_rows += 1
                attempt_index = int(ledger_row["attempt_index"])
                if attempt_index != ledger_rows:
                    failures.append(candidate_id + ": ledger attempt indices are not contiguous")
                    break
                last_attempt = attempt_index
                ledger_counts[ledger_row["decision"]] += 1
        check(ledger_rows == placement["attempt_count"] and last_attempt == placement["attempt_count"], "ledger rows and indices match attempt count", candidate_id)
        check(dict(sorted(ledger_counts.items())) == placement["rejection_and_acceptance_counts"], "ledger decision counts match placement", candidate_id)
        total_ledger_rows += ledger_rows
        total_counts.update(ledger_counts)
        if placement["passed"]:
            check(placement["status"] == "passed_joint_geometry_candidate", "passing status is exact", candidate_id)
            check(len(placement["fibres"]) == contract["fibre_count_per_candidate"] == 2, "exactly two fibres", candidate_id)
            check(ledger_counts["accepted_joint_pair"] == 1, "exactly one joint acceptance closes ledger", candidate_id)
            check(placement["attempt_count"] <= cfg["search_contract"]["maximum_proposals_per_candidate"], "success occurred within proposal ceiling", candidate_id)
            all_anchor_ids = []
            independently_verified_fibres = []
            for fibre in placement["fibres"]:
                members = np.asarray(fibre["member_centres_m"], dtype=float)
                check(members.shape == (37, 3), "fibre has exactly 37 member centres", candidate_id)
                check(np.all(members - member_radius >= 0.0) and np.all(members + member_radius <= lengths), "fibre is wholly inside primary cell", candidate_id)
                clearance = periodic_clearance(members, sand_centres, lengths, member_radius + sand_radii[None, :])
                minimum_sand = float(clearance.min())
                contacted = set(np.flatnonzero(clearance.min(axis=0) <= 1e-10).tolist())
                expected_indices = set(fibre["anchor_sand_indices"])
                check(contacted == expected_indices and len(contacted) == 2, "independent contact set equals two anchors", candidate_id)
                check(minimum_sand >= -maximum_penetration - 1e-12, "independent penetration gate passes", candidate_id)
                anchor_clearances = [float(clearance[first_member, fibre["anchor_sand_indices"][0]]), float(clearance[last_member, fibre["anchor_sand_indices"][1]])]
                check(max(abs(value + target_penetration) for value in anchor_clearances) <= 1e-10, "independent anchor penetration target passes", candidate_id)
                force, moment = balance_metrics(members, first_member, last_member, sand_centres[fibre["anchor_sand_indices"][0]], sand_centres[fibre["anchor_sand_indices"][1]], lengths)
                check(abs(force - fibre["initial_normal_force_residual_relative"]) <= 1e-12 and force <= contract["maximum_initial_force_residual_relative"], "independent force residual passes", candidate_id)
                check(abs(moment - fibre["initial_normal_moment_residual_relative"]) <= 1e-12 and moment <= contract["maximum_initial_moment_residual_relative"], "independent moment residual passes", candidate_id)
                check(all(particles[i]["load_bearing_core_member"] and int(particles[i]["sand_network_degree"]) >= contract["minimum_anchor_network_degree"] for i in fibre["anchor_sand_indices"]), "anchors belong to load-bearing core and meet degree gate", candidate_id)
                all_anchor_ids.extend(fibre["anchor_sand_body_ids"])
                independently_verified_fibres.append(members)
            check(len(all_anchor_ids) == len(set(all_anchor_ids)) == 4, "all four anchor IDs are disjoint", candidate_id)
            joint_clearance = float(periodic_clearance(independently_verified_fibres[0], independently_verified_fibres[1], lengths, 2.0 * member_radius).min())
            check(abs(joint_clearance - placement["joint_minimum_fibre_fibre_clearance_m"]) <= 1e-12, "reported joint clearance matches independent value", candidate_id)
            check(joint_clearance >= contract["minimum_initial_fibre_fibre_clearance_m"] and joint_clearance >= 0.0, "joint clearance and zero-overlap gates pass", candidate_id)
            minimum_degree = min(degree for fibre in placement["fibres"] for degree in fibre["anchor_network_degrees"])
            max_force = max(fibre["initial_normal_force_residual_relative"] for fibre in placement["fibres"])
            max_moment = max(fibre["initial_normal_moment_residual_relative"] for fibre in placement["fibres"])
            attempt_indices = sorted(fibre["accepted_attempt_index"] for fibre in placement["fibres"])
            rank = (-minimum_degree, -joint_clearance, max_force, max_moment, attempt_indices)
            candidate_results.append({"candidate_id": candidate_id, "candidate_index": cfg_candidate["candidate_index"], "seed": cfg_candidate["seed"], "passed": True, "attempt_count": placement["attempt_count"], "retained_single_fibre_count": placement["retained_single_fibre_count"], "minimum_anchor_degree": minimum_degree, "minimum_fibre_fibre_clearance_m": joint_clearance, "maximum_force_residual_relative": max_force, "maximum_moment_residual_relative": max_moment, "accepted_attempt_indices": attempt_indices, "selection_rank": rank})
        else:
            check(placement["status"] == "budget_exhausted_without_joint_pair", "negative status is exact budget exhaustion", candidate_id)
            check(placement["attempt_count"] == cfg["search_contract"]["maximum_proposals_per_candidate"] == 400000, "negative candidate exhausted exact ceiling", candidate_id)
            check(len(placement["fibres"]) == 0 and ledger_counts["accepted_joint_pair"] == 0, "negative candidate publishes no joint geometry", candidate_id)
            candidate_results.append({"candidate_id": candidate_id, "candidate_index": cfg_candidate["candidate_index"], "seed": cfg_candidate["seed"], "passed": False, "attempt_count": placement["attempt_count"], "retained_single_fibre_count": placement["retained_single_fibre_count"]})

    passing = [row for row in candidate_results if row["passed"]]
    check(len(passing) == campaign["passing_candidate_count"] == 5, "exactly five independently verified passing candidates")
    selected = min(passing, key=lambda row: tuple(row["selection_rank"]))
    check(selected["candidate_id"] == "stage26b_f002_revision3_candidate_01", "predeclared rank selects candidate 01")
    passed = not failures
    evaluation = {
        "schema": "lbs.stage26b-revision3-joint-placement-campaign-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_complete_campaign_and_selected_geometry" if passed else "failed_campaign_verification",
        "checks": checks,
        "failures": failures,
        "summary": {
            "candidate_count": len(candidate_results),
            "passing_candidate_count": len(passing),
            "acceptance_fraction": len(passing) / len(candidate_results),
            "total_proposal_ledger_rows": total_ledger_rows,
            "aggregate_decision_counts": dict(sorted(total_counts.items())),
            "topological_distance_anchor_pair_count": len(screen_rows),
            "analytically_feasible_anchor_pair_count": independently_feasible,
            "selected_candidate_id": selected["candidate_id"],
            "selected_candidate_metrics": selected,
            "candidate_results": candidate_results,
        },
        "evidence": {
            "campaign_completion_path": str(CAMPAIGN / "completion.json"),
            "campaign_completion_sha256": digest(CAMPAIGN / "completion.json"),
            "execution_checkpoint_path": str(EXECUTION_CHECKPOINT),
            "execution_checkpoint_sha256": digest(EXECUTION_CHECKPOINT),
            "dependency_checkpoint_path": str(DEPENDENCY_CHECKPOINT),
            "dependency_checkpoint_sha256": digest(DEPENDENCY_CHECKPOINT),
        },
        "authority": {
            "selection_and_render_authorized": passed,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    OUTPUT.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(OUTPUT), "passing_candidate_count": len(passing), "selected_candidate_id": selected["candidate_id"], "total_ledger_rows": total_ledger_rows}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
