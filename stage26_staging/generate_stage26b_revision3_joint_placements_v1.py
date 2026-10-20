"""Generate deterministic joint two-F37 placement candidates.

Host-Python geometry only.  This module never imports, invokes, or controls YADE.
Revision 3 changes the search strategy, not the physical acceptance gates.
"""

import argparse
import copy
import csv
import gzip
import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from plan_stage26a_f37_placement_v1 import anchored_translation, rotation_aligning


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def exclusive_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


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
    lever_scale = max(
        np.linalg.norm(members[last_index] - members[first_index]), 1e-30
    ) * force_scale
    moment_residual = np.linalg.norm(np.sum(moments, axis=0)) / lever_scale
    return float(force_residual), float(moment_residual)


def periodic_clearance(first, second, lengths, combined_radius):
    delta = first[:, None, :] - second[None, :, :]
    delta -= np.round(delta / lengths) * lengths
    return np.linalg.norm(delta, axis=2) - combined_radius


def analytical_tip_feasible(pair_distance, tip_span, radius_a, radius_b, tolerance):
    """Return the exact two-sphere intersection feasibility for aligned tips."""
    shifted_distance = abs(float(pair_distance) - float(tip_span))
    lower = abs(float(radius_a) - float(radius_b))
    upper = float(radius_a) + float(radius_b)
    return lower - tolerance <= shifted_distance <= upper + tolerance


def screen_anchor_pairs(
    particles,
    minimum_degree,
    preferred_degree,
    distance_range,
    member_radius,
    target_penetration,
    tip_span,
    tolerance,
):
    rows = []
    feasible = []
    for first in range(len(particles)):
        a = particles[first]
        if not a["load_bearing_core_member"] or int(a["sand_network_degree"]) < minimum_degree:
            continue
        for second in range(first + 1, len(particles)):
            b = particles[second]
            if not b["load_bearing_core_member"] or int(b["sand_network_degree"]) < minimum_degree:
                continue
            distance = float(
                np.linalg.norm(np.asarray(b["position_m"], dtype=float) - np.asarray(a["position_m"], dtype=float))
            )
            if not distance_range[0] <= distance <= distance_range[1]:
                continue
            radius_a = float(a["radius_m"]) + member_radius - target_penetration
            radius_b = float(b["radius_m"]) + member_radius - target_penetration
            is_feasible = analytical_tip_feasible(
                distance, tip_span, radius_a, radius_b, tolerance
            )
            minimum_pair_degree = min(
                int(a["sand_network_degree"]), int(b["sand_network_degree"])
            )
            preferred = minimum_pair_degree >= preferred_degree
            force_support = min(
                float(a["incident_normal_force_sum_n"]),
                float(b["incident_normal_force_sum_n"]),
            )
            pair = (
                not preferred,
                -minimum_pair_degree,
                -force_support,
                int(a["sand_body_id"]),
                int(b["sand_body_id"]),
                first,
                second,
                distance,
                radius_a,
                radius_b,
            )
            rows.append(
                {
                    "anchor_body_id_1": pair[3],
                    "anchor_body_id_2": pair[4],
                    "anchor_index_1": first,
                    "anchor_index_2": second,
                    "anchor_pair_distance_m": distance,
                    "tip_span_m": tip_span,
                    "contact_radius_1_m": radius_a,
                    "contact_radius_2_m": radius_b,
                    "minimum_pair_degree": minimum_pair_degree,
                    "preferred_degree_pair": preferred,
                    "analytically_feasible": is_feasible,
                }
            )
            if is_feasible:
                feasible.append(pair)
    return sorted(feasible), sorted(
        rows, key=lambda row: (row["anchor_body_id_1"], row["anchor_body_id_2"])
    )


def evaluate_single(
    local,
    member_radius,
    pair,
    particles,
    sand_centres,
    sand_radii,
    lengths,
    contract,
    rng,
):
    first_index, last_index = contract["anchor_member_indices"]
    target_penetration = (
        contract["target_anchor_penetration_over_member_radius"] * member_radius
    )
    maximum_penetration = (
        contract["maximum_sand_fibre_penetration_over_member_radius"] * member_radius
    )
    (
        _,
        _,
        _,
        first_id,
        second_id,
        first,
        second,
        pair_distance,
        radius_a,
        radius_b,
    ) = pair
    roll = rng.random() * 2.0 * math.pi
    anchor_azimuth = rng.random() * 2.0 * math.pi
    direction = sand_centres[second] - sand_centres[first]
    rotation = rotation_aligning(
        local[last_index] - local[first_index], direction, roll
    )
    rotated = local @ rotation.T
    translation = anchored_translation(
        sand_centres[first],
        sand_centres[second],
        rotated[first_index],
        rotated[last_index],
        radius_a,
        radius_b,
        anchor_azimuth,
    )
    metrics = {
        "force_residual": "",
        "moment_residual": "",
        "minimum_sand_clearance_m": "",
        "contact_count": "",
    }
    if translation is None:
        return None, "reject_anchor_geometry", metrics, roll, anchor_azimuth
    members = rotated + translation
    if contract["fibres_wholly_inside_primary_cell"] and (
        np.any(members - member_radius < 0.0)
        or np.any(members + member_radius > lengths)
    ):
        return None, "reject_outside_primary_cell", metrics, roll, anchor_azimuth
    clearance = periodic_clearance(
        members,
        sand_centres,
        lengths,
        member_radius + sand_radii[None, :],
    )
    minimum_sand = float(clearance.min())
    contacted = np.flatnonzero(clearance.min(axis=0) <= 1e-10)
    metrics["minimum_sand_clearance_m"] = minimum_sand
    metrics["contact_count"] = len(contacted)
    if minimum_sand < -maximum_penetration - 1e-12:
        return None, "reject_sand_penetration", metrics, roll, anchor_azimuth
    if set(contacted.tolist()) != {first, second}:
        return None, "reject_contact_set", metrics, roll, anchor_azimuth
    anchor_clearances = [
        float(clearance[first_index, first]),
        float(clearance[last_index, second]),
    ]
    if max(abs(value + target_penetration) for value in anchor_clearances) > 1e-10:
        return None, "reject_anchor_clearance", metrics, roll, anchor_azimuth
    force_residual, moment_residual = balance_metrics(
        members,
        first_index,
        last_index,
        sand_centres[first],
        sand_centres[second],
        lengths,
    )
    metrics["force_residual"] = force_residual
    metrics["moment_residual"] = moment_residual
    if force_residual > contract["maximum_initial_force_residual_relative"]:
        return None, "reject_force_residual", metrics, roll, anchor_azimuth
    if moment_residual > contract["maximum_initial_moment_residual_relative"]:
        return None, "reject_moment_residual", metrics, roll, anchor_azimuth
    fibre = {
        "member_centres_m": members.tolist(),
        "rotation_matrix": rotation.tolist(),
        "translation_m": translation.tolist(),
        "anchor_sand_body_ids": [first_id, second_id],
        "anchor_sand_indices": [first, second],
        "anchor_member_indices": [first_index, last_index],
        "anchor_network_degrees": [
            int(particles[first]["sand_network_degree"]),
            int(particles[second]["sand_network_degree"]),
        ],
        "initial_contacted_sand_body_ids": [first_id, second_id],
        "initial_distinct_sand_contact_count": len(contacted),
        "initial_normal_force_residual_relative": force_residual,
        "initial_normal_moment_residual_relative": moment_residual,
        "minimum_sand_fibre_clearance_m": minimum_sand,
        "minimum_fibre_fibre_clearance_m": None,
        "anchor_pair_distance_m": pair_distance,
    }
    return fibre, "single_physically_admissible", metrics, roll, anchor_azimuth


def find_joint_partner(fibre, pool, lengths, member_radius, minimum_clearance):
    current_ids = set(fibre["anchor_sand_body_ids"])
    current_members = np.asarray(fibre["member_centres_m"], dtype=float)
    best = None
    for retained_index, retained in enumerate(pool):
        if current_ids.intersection(retained["anchor_sand_body_ids"]):
            continue
        retained_members = np.asarray(retained["member_centres_m"], dtype=float)
        clearance = float(
            periodic_clearance(
                current_members,
                retained_members,
                lengths,
                2.0 * member_radius,
            ).min()
        )
        if clearance >= minimum_clearance:
            rank = (
                -min(
                    fibre["anchor_network_degrees"]
                    + retained["anchor_network_degrees"]
                ),
                -clearance,
                max(
                    fibre["initial_normal_force_residual_relative"],
                    retained["initial_normal_force_residual_relative"],
                ),
                max(
                    fibre["initial_normal_moment_residual_relative"],
                    retained["initial_normal_moment_residual_relative"],
                ),
                retained["accepted_attempt_index"],
            )
            if best is None or rank < best[0]:
                best = (rank, retained_index, clearance)
    return best


def generate_candidate(candidate, cfg, network, template, output, feasible_pairs, screen_count):
    contract = cfg["generator_contract"]
    search = cfg["search_contract"]
    particles = network["particles"]
    sand_centres = np.asarray([row["position_m"] for row in particles], dtype=float)
    sand_radii = np.asarray([row["radius_m"] for row in particles], dtype=float)
    lengths = np.asarray(
        [network["cell_hsize_m"][index][index] for index in range(3)], dtype=float
    )
    local = np.asarray([row["center_m"] for row in template["members"]], dtype=float)
    member_radius = float(contract["member_radius_m"])
    candidate_output = output / candidate["candidate_id"]
    candidate_output.mkdir()
    ledger_path = candidate_output / "attempts.csv.gz"
    rng = random.Random(int(candidate["seed"]))
    pairs = list(feasible_pairs)
    rng.shuffle(pairs)
    pool = []
    retained_by_anchor_pair = Counter()
    rejection_counts = Counter()
    fibres = []
    joint_clearance = None
    maximum_attempts = int(search["maximum_proposals_per_candidate"])
    attempts = 0
    fields = [
        "attempt_index",
        "anchor_body_id_1",
        "anchor_body_id_2",
        "anchor_pair_distance_m",
        "roll_rad",
        "anchor_azimuth_rad",
        "decision",
        "force_residual",
        "moment_residual",
        "minimum_sand_clearance_m",
        "minimum_fibre_clearance_m",
        "contact_count",
        "retained_pool_size",
    ]
    with gzip.open(ledger_path, "xt", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        if pairs:
            for attempt_index in range(1, maximum_attempts + 1):
                if (attempt_index - 1) and (attempt_index - 1) % len(pairs) == 0:
                    rng.shuffle(pairs)
                pair = pairs[(attempt_index - 1) % len(pairs)]
                fibre, decision, metrics, roll, anchor_azimuth = evaluate_single(
                    local,
                    member_radius,
                    pair,
                    particles,
                    sand_centres,
                    sand_radii,
                    lengths,
                    contract,
                    rng,
                )
                attempts = attempt_index
                minimum_fibre_clearance = ""
                if fibre is not None:
                    fibre["accepted_attempt_index"] = attempt_index
                    partner = find_joint_partner(
                        fibre,
                        pool,
                        lengths,
                        member_radius,
                        contract["minimum_initial_fibre_fibre_clearance_m"],
                    )
                    if partner is not None:
                        _, retained_index, joint_clearance = partner
                        first = copy.deepcopy(pool[retained_index])
                        second = copy.deepcopy(fibre)
                        first["fibre_index"] = 0
                        second["fibre_index"] = 1
                        first["minimum_fibre_fibre_clearance_m"] = joint_clearance
                        second["minimum_fibre_fibre_clearance_m"] = joint_clearance
                        fibres = [first, second]
                        decision = "accepted_joint_pair"
                        minimum_fibre_clearance = joint_clearance
                    else:
                        pair_key = tuple(sorted(fibre["anchor_sand_body_ids"]))
                        if len(pool) >= int(search["maximum_retained_single_fibres"]):
                            decision = "accepted_single_not_retained_pool_cap"
                        elif retained_by_anchor_pair[pair_key] >= int(
                            search["maximum_retained_placements_per_anchor_pair"]
                        ):
                            decision = "accepted_single_not_retained_anchor_pair_cap"
                        else:
                            pool.append(fibre)
                            retained_by_anchor_pair[pair_key] += 1
                            decision = "accepted_single_retained"
                rejection_counts[decision] += 1
                writer.writerow(
                    {
                        "attempt_index": attempt_index,
                        "anchor_body_id_1": pair[3],
                        "anchor_body_id_2": pair[4],
                        "anchor_pair_distance_m": pair[7],
                        "roll_rad": roll,
                        "anchor_azimuth_rad": anchor_azimuth,
                        "decision": decision,
                        "force_residual": metrics["force_residual"],
                        "moment_residual": metrics["moment_residual"],
                        "minimum_sand_clearance_m": metrics[
                            "minimum_sand_clearance_m"
                        ],
                        "minimum_fibre_clearance_m": minimum_fibre_clearance,
                        "contact_count": metrics["contact_count"],
                        "retained_pool_size": len(pool),
                    }
                )
                if fibres:
                    break
    passed = len(fibres) == int(contract["fibre_count_per_candidate"])
    placement = {
        "schema": "lbs.stage26b-revision3-joint-two-f37-placement.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": (
            "passed_joint_geometry_candidate"
            if passed
            else (
                "no_analytically_feasible_anchor_pairs"
                if not feasible_pairs
                else "budget_exhausted_without_joint_pair"
            )
        ),
        "candidate": candidate,
        "algorithm": search["algorithm"],
        "cell_dimensions_m": lengths.tolist(),
        "sand_count": len(particles),
        "fibre_count": len(fibres),
        "members_per_fibre": len(local),
        "member_radius_m": member_radius,
        "topological_distance_anchor_pair_count": screen_count,
        "analytically_feasible_anchor_pair_count": len(feasible_pairs),
        "attempt_count": attempts,
        "retained_single_fibre_count": len(pool),
        "rejection_and_acceptance_counts": dict(sorted(rejection_counts.items())),
        "maximum_anchor_multiplicity": 1 if passed else 0,
        "joint_minimum_fibre_fibre_clearance_m": joint_clearance,
        "fibres": fibres,
        "source_hashes": {
            "config": digest(cfg["execution"]["config_path"]),
            "network": digest(cfg["sources"]["network"]),
            "generator": digest(__file__),
            "design_checkpoint": digest(cfg["sources"]["design_checkpoint"]),
        },
        "authority": cfg["authority"],
        "claim_boundary": cfg["claim_boundary"],
    }
    exclusive_json(candidate_output / "placement.json", placement)
    completion = {
        "schema": "lbs.stage26b-revision3-placement-candidate-completion.v1",
        "passed": passed,
        "candidate_id": candidate["candidate_id"],
        "attempt_count": attempts,
        "retained_single_fibre_count": len(pool),
        "placement_sha256": digest(candidate_output / "placement.json"),
        "attempts_sha256": digest(ledger_path),
        "claim_boundary": cfg["claim_boundary"],
    }
    exclusive_json(candidate_output / "completion.json", completion)
    return placement, completion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Revision-3 placement campaign output already exists")
    cfg = load_json(config_path)
    if cfg.get("status") != "authorized_stage26b_revision3_joint_placement_generation":
        raise RuntimeError("Revision-3 joint placement generation is not authorized")
    if cfg["authority"].get("placement_generation_authorized") is not True or any(
        cfg["authority"].get(name, False)
        for name in (
            "prefilter_yade_execution_authorized",
            "two_fibre_free_release_authorized",
            "four_fibre_execution_authorized",
            "flow_execution_authorized",
            "production_parametric_study_authorized",
        )
    ):
        raise RuntimeError("placement-generation authority is invalid")
    if Path(cfg["execution"]["config_path"]).resolve() != config_path:
        raise RuntimeError("execution config_path does not bind the supplied config")
    for name, value in cfg["sources"].items():
        if name.endswith("_sha256"):
            continue
        expected = cfg["sources"].get(name + "_sha256")
        if expected and digest(value) != expected:
            raise RuntimeError("source hash mismatch: " + name)
    network = load_json(cfg["sources"]["network"])
    geometry = load_json(cfg["sources"]["f37_geometry_review"])
    contract = cfg["generator_contract"]
    search = cfg["search_contract"]
    template = geometry["fibre_candidates"][contract["f37_template_id"]]
    local = np.asarray([row["center_m"] for row in template["members"]], dtype=float)
    first_index, last_index = contract["anchor_member_indices"]
    tip_span = float(np.linalg.norm(local[last_index] - local[first_index]))
    target_penetration = (
        contract["target_anchor_penetration_over_member_radius"]
        * contract["member_radius_m"]
    )
    feasible_pairs, screen_rows = screen_anchor_pairs(
        network["particles"],
        contract["minimum_anchor_network_degree"],
        contract["preferred_anchor_network_degree"],
        contract["anchor_pair_distance_m"],
        contract["member_radius_m"],
        target_penetration,
        tip_span,
        search["analytical_tolerance_m"],
    )
    output.mkdir(parents=True)
    screen_path = output / "anchor_pair_screen.csv"
    with screen_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(screen_rows[0]))
        writer.writeheader()
        writer.writerows(screen_rows)
    index_rows = []
    for candidate in cfg["candidates"]:
        placement, completion = generate_candidate(
            candidate,
            cfg,
            network,
            template,
            output,
            feasible_pairs,
            len(screen_rows),
        )
        index_rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_index": candidate["candidate_index"],
                "seed": candidate["seed"],
                "passed": placement["passed"],
                "attempt_count": placement["attempt_count"],
                "retained_single_fibre_count": placement[
                    "retained_single_fibre_count"
                ],
                "placement_sha256": completion["placement_sha256"],
                "attempts_sha256": completion["attempts_sha256"],
            }
        )
    index_path = output / "candidate_index.csv"
    with index_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(index_rows[0]))
        writer.writeheader()
        writer.writerows(index_rows)
    campaign = {
        "schema": "lbs.stage26b-revision3-placement-campaign-completion.v1",
        "passed": True,
        "status": "completed_predeclared_joint_candidate_budgets",
        "candidate_count": len(index_rows),
        "passing_candidate_count": sum(row["passed"] for row in index_rows),
        "topological_distance_anchor_pair_count": len(screen_rows),
        "analytically_feasible_anchor_pair_count": len(feasible_pairs),
        "anchor_pair_screen_sha256": digest(screen_path),
        "candidate_index_sha256": digest(index_path),
        "source_hashes": {
            "config": digest(config_path),
            "network": digest(cfg["sources"]["network"]),
            "generator": digest(__file__),
            "design_checkpoint": digest(cfg["sources"]["design_checkpoint"]),
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    exclusive_json(output / "completion.json", campaign)
    print(
        json.dumps(
            {
                "passed": True,
                "candidate_count": len(index_rows),
                "passing_candidate_count": campaign["passing_candidate_count"],
                "analytically_feasible_anchor_pair_count": len(feasible_pairs),
                "completion_sha256": digest(output / "completion.json"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
