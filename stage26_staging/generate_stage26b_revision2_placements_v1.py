"""Deterministically generate network-screened two-F37 placement candidates.

Host-Python geometry only. This module never imports or invokes YADE.
"""

import argparse
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
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def exclusive_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def balance_metrics(members, first_index, last_index, sand_a, sand_b, lengths):
    centre = members.mean(axis=0)
    forces, moments = [], []
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


def periodic_clearance(first, second, lengths, combined_radius):
    delta = first[:, None, :] - second[None, :, :]
    delta -= np.round(delta / lengths) * lengths
    return np.linalg.norm(delta, axis=2) - combined_radius


def eligible_anchor_pairs(particles, minimum_degree, preferred_degree, distance_range):
    result = []
    for first in range(len(particles)):
        a = particles[first]
        if not a["load_bearing_core_member"] or int(a["sand_network_degree"]) < minimum_degree:
            continue
        for second in range(first + 1, len(particles)):
            b = particles[second]
            if not b["load_bearing_core_member"] or int(b["sand_network_degree"]) < minimum_degree:
                continue
            distance = float(np.linalg.norm(np.array(b["position_m"]) - np.array(a["position_m"])))
            if distance_range[0] <= distance <= distance_range[1]:
                minimum_pair_degree = min(int(a["sand_network_degree"]), int(b["sand_network_degree"]))
                preferred = minimum_pair_degree >= preferred_degree
                force_support = min(float(a["incident_normal_force_sum_n"]), float(b["incident_normal_force_sum_n"]))
                result.append((not preferred, -minimum_pair_degree, -force_support, int(a["sand_body_id"]), int(b["sand_body_id"]), first, second, distance))
    return sorted(result)


def attempt_one_fibre(local, member_radius, anchors, particles, sand_centres, sand_radii,
                      lengths, contract, rng, existing, anchor_usage, fibre_index,
                      budget, ledger, attempt_offset):
    first_index, last_index = contract["anchor_member_indices"]
    target_penetration = contract["target_anchor_penetration_over_member_radius"] * member_radius
    maximum_penetration = contract["maximum_sand_fibre_penetration_over_member_radius"] * member_radius
    pairs = list(anchors)
    rng.shuffle(pairs)
    attempts = 0
    for pair in pairs:
        _, _, _, first_id, second_id, first, second, pair_distance = pair
        if anchor_usage[first_id] >= contract["maximum_anchor_multiplicity_across_fibres"] or anchor_usage[second_id] >= contract["maximum_anchor_multiplicity_across_fibres"]:
            continue
        rolls_for_pair = min(512, budget - attempts)
        for _ in range(rolls_for_pair):
            attempts += 1
            roll = rng.random() * 2.0 * math.pi
            direction = sand_centres[second] - sand_centres[first]
            rotation = rotation_aligning(local[last_index] - local[first_index], direction, roll)
            rotated = local @ rotation.T
            translation = anchored_translation(
                sand_centres[first], sand_centres[second], rotated[first_index], rotated[last_index],
                sand_radii[first] + member_radius - target_penetration,
                sand_radii[second] + member_radius - target_penetration, rng.random() * 2.0 * math.pi,
            )
            decision = "accepted"
            metrics = {"force_residual": "", "moment_residual": "", "minimum_sand_clearance_m": "", "minimum_fibre_clearance_m": "", "contact_count": ""}
            members = None
            if translation is None:
                decision = "reject_anchor_geometry"
            else:
                members = rotated + translation
                if contract["fibres_wholly_inside_primary_cell"] and (np.any(members - member_radius < 0.0) or np.any(members + member_radius > lengths)):
                    decision = "reject_outside_primary_cell"
                else:
                    clearance = periodic_clearance(members, sand_centres, lengths, member_radius + sand_radii[None, :])
                    minimum_sand = float(clearance.min())
                    contacted = np.flatnonzero(clearance.min(axis=0) <= 1e-10)
                    metrics["minimum_sand_clearance_m"] = minimum_sand
                    metrics["contact_count"] = len(contacted)
                    if minimum_sand < -maximum_penetration - 1e-12:
                        decision = "reject_sand_penetration"
                    elif set(contacted.tolist()) != {first, second}:
                        decision = "reject_contact_set"
                    else:
                        anchor_clearances = [float(clearance[first_index, first]), float(clearance[last_index, second])]
                        if max(abs(value + target_penetration) for value in anchor_clearances) > 1e-10:
                            decision = "reject_anchor_clearance"
                        else:
                            fibre_clearance = math.inf
                            if existing:
                                fibre_clearance = min(float(periodic_clearance(members, previous, lengths, 2.0 * member_radius).min()) for previous in existing)
                            metrics["minimum_fibre_clearance_m"] = fibre_clearance
                            if existing and fibre_clearance < contract["minimum_initial_fibre_fibre_clearance_m"]:
                                decision = "reject_fibre_clearance"
                            else:
                                force_residual, moment_residual = balance_metrics(members, first_index, last_index, sand_centres[first], sand_centres[second], lengths)
                                metrics["force_residual"] = force_residual
                                metrics["moment_residual"] = moment_residual
                                if force_residual > contract["maximum_initial_force_residual_relative"]:
                                    decision = "reject_force_residual"
                                elif moment_residual > contract["maximum_initial_moment_residual_relative"]:
                                    decision = "reject_moment_residual"
            ledger.writerow({
                "attempt_index": attempt_offset + attempts, "fibre_index": fibre_index,
                "anchor_body_id_1": first_id, "anchor_body_id_2": second_id,
                "anchor_pair_distance_m": pair_distance, "roll_rad": roll, "decision": decision,
                **metrics,
            })
            if decision == "accepted":
                return {
                    "fibre_index": fibre_index,
                    "member_centres_m": members.tolist(),
                    "rotation_matrix": rotation.tolist(),
                    "translation_m": translation.tolist(),
                    "anchor_sand_body_ids": [first_id, second_id],
                    "anchor_sand_indices": [first, second],
                    "anchor_member_indices": [first_index, last_index],
                    "anchor_network_degrees": [int(particles[first]["sand_network_degree"]), int(particles[second]["sand_network_degree"])],
                    "initial_contacted_sand_body_ids": [first_id, second_id],
                    "initial_distinct_sand_contact_count": 2,
                    "initial_normal_force_residual_relative": metrics["force_residual"],
                    "initial_normal_moment_residual_relative": metrics["moment_residual"],
                    "minimum_sand_fibre_clearance_m": metrics["minimum_sand_clearance_m"],
                    "minimum_fibre_fibre_clearance_m": None if not existing else metrics["minimum_fibre_clearance_m"],
                    "anchor_pair_distance_m": pair_distance,
                }, attempts
        if attempts >= budget:
            break
    return None, attempts


def generate_candidate(candidate, cfg, network, template, output):
    contract = cfg["generator_contract"]
    particles = network["particles"]
    sand_centres = np.array([row["position_m"] for row in particles], dtype=float)
    sand_radii = np.array([row["radius_m"] for row in particles], dtype=float)
    lengths = np.array([network["cell_hsize_m"][index][index] for index in range(3)], dtype=float)
    local = np.array([row["center_m"] for row in template["members"]], dtype=float)
    member_radius = float(contract["member_radius_m"])
    anchors = eligible_anchor_pairs(particles, contract["minimum_anchor_network_degree"], contract["preferred_anchor_network_degree"], contract["anchor_pair_distance_m"])
    candidate_output = output / candidate["candidate_id"]
    candidate_output.mkdir()
    ledger_path = candidate_output / "attempts.csv.gz"
    rng = random.Random(candidate["seed"])
    fibres, existing, usage = [], [], Counter()
    attempts = 0
    with gzip.open(ledger_path, "xt", newline="", encoding="utf-8") as stream:
        fields = ["attempt_index", "fibre_index", "anchor_body_id_1", "anchor_body_id_2", "anchor_pair_distance_m", "roll_rad", "decision", "force_residual", "moment_residual", "minimum_sand_clearance_m", "minimum_fibre_clearance_m", "contact_count"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for fibre_index in range(2):
            remaining = int(contract["maximum_trials_per_candidate"]) - attempts
            fibre, used = attempt_one_fibre(local, member_radius, anchors, particles, sand_centres, sand_radii, lengths, contract, rng, existing, usage, fibre_index, remaining, writer, attempts)
            attempts += used
            if fibre is None:
                break
            fibres.append(fibre)
            existing.append(np.array(fibre["member_centres_m"], dtype=float))
            usage.update(fibre["anchor_sand_body_ids"])
    passed = len(fibres) == 2
    placement = {
        "schema": "lbs.stage26b-revision2-two-f37-placement.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_geometry_candidate" if passed else "budget_exhausted_without_two_fibres",
        "candidate": candidate,
        "algorithm": "network-screened-force-moment-balanced-two-anchor-v1",
        "cell_dimensions_m": lengths.tolist(), "sand_count": len(particles),
        "fibre_count": len(fibres), "members_per_fibre": len(local), "member_radius_m": member_radius,
        "eligible_anchor_pair_count": len(anchors), "attempt_count": attempts,
        "maximum_anchor_multiplicity": max(usage.values()) if usage else 0,
        "fibres": fibres,
        "source_hashes": {"config": digest(Path(cfg["execution"]["config_path"])), "network": digest(Path(cfg["sources"]["network"])), "generator": digest(Path(__file__))},
        "authority": cfg["authority"], "claim_boundary": cfg["claim_boundary"],
    }
    exclusive_json(candidate_output / "placement.json", placement)
    completion = {
        "schema": "lbs.stage26b-revision2-placement-candidate-completion.v1", "passed": passed,
        "candidate_id": candidate["candidate_id"], "attempt_count": attempts,
        "placement_sha256": digest(candidate_output / "placement.json"), "attempts_sha256": digest(ledger_path),
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
        raise RuntimeError("immutable placement campaign output already exists")
    cfg = load_json(config_path)
    if cfg.get("status") != "authorized_stage26b_revision2_placement_generation":
        raise RuntimeError("placement generation is not authorized")
    if cfg["authority"].get("placement_generation_authorized") is not True or any(cfg["authority"].get(name, False) for name in ("prefilter_yade_execution_authorized", "two_fibre_free_release_authorized", "four_fibre_execution_authorized", "flow_execution_authorized")):
        raise RuntimeError("placement-generation authority is invalid")
    for name, value in cfg["sources"].items():
        if name.endswith("_sha256"):
            continue
        expected = cfg["sources"].get(name + "_sha256")
        if expected and digest(Path(value)) != expected:
            raise RuntimeError("source hash mismatch: " + name)
    network = load_json(Path(cfg["sources"]["network"]))
    geometry = load_json(Path(cfg["sources"]["f37_geometry_review"]))
    template = geometry["fibre_candidates"][cfg["generator_contract"]["f37_template_id"]]
    output.mkdir(parents=True)
    index_rows = []
    for candidate in cfg["candidates"]:
        placement, completion = generate_candidate(candidate, cfg, network, template, output)
        index_rows.append({"candidate_id": candidate["candidate_id"], "candidate_index": candidate["candidate_index"], "seed": candidate["seed"], "passed": placement["passed"], "attempt_count": placement["attempt_count"], "placement_sha256": completion["placement_sha256"], "attempts_sha256": completion["attempts_sha256"]})
    with (output / "candidate_index.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(index_rows[0]))
        writer.writeheader(); writer.writerows(index_rows)
    completion = {
        "schema": "lbs.stage26b-revision2-placement-campaign-completion.v1", "passed": True,
        "status": "completed_predeclared_candidate_budgets", "candidate_count": len(index_rows),
        "passing_candidate_count": sum(1 for row in index_rows if row["passed"]),
        "candidate_index_sha256": digest(output / "candidate_index.csv"),
        "source_hashes": {"config": digest(config_path), "network": digest(Path(cfg["sources"]["network"])), "generator": digest(Path(__file__))},
        "claim_boundary": cfg["claim_boundary"],
    }
    exclusive_json(output / "completion.json", completion)
    print(json.dumps({"passed": True, "candidate_count": len(index_rows), "passing_candidate_count": completion["passing_candidate_count"], "completion_sha256": digest(output / "completion.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
