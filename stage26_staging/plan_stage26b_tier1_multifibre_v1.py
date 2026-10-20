"""Generate immutable force/moment-balanced Tier-1 multi-fibre placements."""

import argparse
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


def balance_metrics(members, first_index, last_index, sand_a, sand_b, lengths):
    com = members.mean(axis=0)
    forces = []
    moments = []
    for member_index, sand in ((first_index, sand_a), (last_index, sand_b)):
        delta = members[member_index] - sand
        delta -= np.round(delta / lengths) * lengths
        force = delta / np.linalg.norm(delta)
        forces.append(force)
        moments.append(np.cross(members[member_index] - com, force))
    force_scale = sum(np.linalg.norm(value) for value in forces)
    force_residual = np.linalg.norm(np.sum(forces, axis=0)) / force_scale
    lever_scale = max(np.linalg.norm(members[last_index] - members[first_index]), 1e-30) * force_scale
    moment_residual = np.linalg.norm(np.sum(moments, axis=0)) / lever_scale
    return float(force_residual), float(moment_residual)


def minimum_periodic_clearance(a, b, lengths, combined_radius):
    delta = a[:, None, :] - b[None, :, :]
    delta -= np.round(delta / lengths) * lengths
    return float((np.linalg.norm(delta, axis=2) - combined_radius).min())


def propose_fibre(local, member_radius, first_index, last_index, sand_centres, sand_radii,
                  sand_ids, lengths, pairs, search, rng, existing_members, anchor_usage):
    target_penetration = search["target_anchor_penetration_over_member_radius"] * member_radius
    maximum_penetration = search["maximum_sand_fibre_penetration_over_member_radius"] * member_radius
    pairs_local = list(pairs)
    rng.shuffle(pairs_local)
    best = None
    tested = 0
    for i, j, pair_distance in pairs_local:
        if anchor_usage[int(sand_ids[i])] >= search["maximum_anchor_multiplicity_across_fibres"]:
            continue
        if anchor_usage[int(sand_ids[j])] >= search["maximum_anchor_multiplicity_across_fibres"]:
            continue
        direction = sand_centres[j] - sand_centres[i]
        for _ in range(search["rolls_per_pair"]):
            if tested >= search["maximum_trials_per_fibre"]:
                break
            tested += 1
            rotation = rotation_aligning(local[last_index] - local[first_index], direction, rng.random() * 2.0 * math.pi)
            rotated = local @ rotation.T
            translation = anchored_translation(
                sand_centres[i], sand_centres[j], rotated[first_index], rotated[last_index],
                sand_radii[i] + member_radius - target_penetration,
                sand_radii[j] + member_radius - target_penetration,
                rng.random() * 2.0 * math.pi,
            )
            if translation is None:
                continue
            members = rotated + translation
            if search["require_fibres_wholly_inside_primary_cell"]:
                if np.any(members - member_radius < 0.0) or np.any(members + member_radius > lengths):
                    continue
            delta = members[:, None, :] - sand_centres[None, :, :]
            delta -= np.round(delta / lengths) * lengths
            clearance = np.linalg.norm(delta, axis=2) - member_radius - sand_radii[None, :]
            minimum_sand_clearance = float(clearance.min())
            contacted_indices = np.flatnonzero(clearance.min(axis=0) <= 1e-10)
            if minimum_sand_clearance < -maximum_penetration - 1e-12:
                continue
            if not (search["minimum_distinct_initial_sand_contacts_per_fibre"] <= len(contacted_indices) <= search["maximum_distinct_initial_sand_contacts_per_fibre"]):
                continue
            if set(contacted_indices.tolist()) != {i, j}:
                continue
            anchor_clearances = [float(clearance[first_index, i]), float(clearance[last_index, j])]
            if max(abs(value + target_penetration) for value in anchor_clearances) > 1e-10:
                continue
            fibre_clearance = math.inf
            if existing_members:
                fibre_clearance = min(
                    minimum_periodic_clearance(members, previous, lengths, 2.0 * member_radius)
                    for previous in existing_members
                )
                if search["require_zero_initial_fibre_fibre_overlap"] and fibre_clearance < -1e-12:
                    continue
            force_residual, moment_residual = balance_metrics(
                members, first_index, last_index, sand_centres[i], sand_centres[j], lengths
            )
            if force_residual > search["maximum_initial_normal_force_residual_relative"]:
                continue
            if moment_residual > search["maximum_initial_normal_moment_residual_relative"]:
                continue
            multiplicity_penalty = anchor_usage[int(sand_ids[i])] + anchor_usage[int(sand_ids[j])]
            score = (multiplicity_penalty, force_residual, moment_residual, -min(fibre_clearance, 1.0))
            candidate = {
                "score": score, "i": i, "j": j, "pair_distance_m": pair_distance,
                "rotation": rotation, "translation": translation, "members": members,
                "minimum_sand_clearance_m": minimum_sand_clearance,
                "minimum_fibre_fibre_clearance_m": None if not existing_members else fibre_clearance,
                "contacted_indices": contacted_indices, "anchor_clearances_m": anchor_clearances,
                "force_residual": force_residual, "moment_residual": moment_residual,
            }
            if best is None or score < best["score"]:
                best = candidate
            if (multiplicity_penalty == 0
                    and force_residual <= search["preferred_initial_normal_force_residual_relative"]
                    and moment_residual <= search["preferred_initial_normal_moment_residual_relative"]):
                return best, tested
        if tested >= search["maximum_trials_per_fibre"]:
            break
    return best, tested


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable placement output already exists")
    cfg = load_json(config_path)
    if cfg["status"] != "authorized_tier1_placement_preflight_only":
        raise RuntimeError("preflight configuration is not authorized")
    if not cfg["authority"]["placement_generation_authorized"] or cfg["authority"]["multi_fibre_yade_execution_authorized"]:
        raise RuntimeError("invalid placement-only authority")
    for key, path_text in cfg["sources"].items():
        if key.endswith("_sha256"):
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected and digest(Path(path_text)) != expected:
            raise RuntimeError("source hash mismatch: " + key)
    case = next((row for row in cfg["cases"] if row["case_id"] == args.case_id), None)
    if case is None:
        raise RuntimeError("case is not in the frozen Tier-1 design")

    stage26a = load_json(Path(cfg["sources"]["stage26a_design_config"]))
    source = stage26a["source"]
    result_path = Path(source["stage25_selected_result"])
    review_path = Path(source["f37_geometry_review"])
    if digest(result_path) != source["stage25_selected_result_sha256"] or digest(review_path) != source["f37_geometry_review_sha256"]:
        raise RuntimeError("Stage25/F37 source binding failed")
    result = load_json(result_path)
    review = load_json(review_path)
    template = review["fibre_candidates"][stage26a["fibre"]["template_id"]]
    local = np.array([row["center_m"] for row in template["members"]], dtype=float)
    member_radius = float(stage26a["fibre"]["member_radius_m"])
    first_index, last_index = cfg["search"]["anchor_member_indices"]
    local_tip_span = float(np.linalg.norm(local[last_index] - local[first_index]))
    sand_centres = np.array([row["position_m"] for row in result["particles"]], dtype=float)
    sand_radii = np.array([row["radius_m"] for row in result["particles"]], dtype=float)
    sand_ids = np.array([int(row["body_id"]) for row in result["particles"]], dtype=int)
    lengths = np.array(result["terminal"]["cell_dimensions_m"], dtype=float)
    pairs = []
    for i in range(len(sand_centres)):
        for j in range(i + 1, len(sand_centres)):
            distance = float(np.linalg.norm(sand_centres[j] - sand_centres[i]))
            if cfg["search"]["pair_distance_minimum_m"] <= distance <= cfg["search"]["pair_distance_maximum_m"]:
                pairs.append((i, j, distance))

    rng = random.Random(case["placement_seed"])
    existing_members = []
    anchor_usage = Counter()
    fibres = []
    total_tested = 0
    for fibre_index in range(case["fibre_count"]):
        best, tested = propose_fibre(
            local, member_radius, first_index, last_index, sand_centres, sand_radii,
            sand_ids, lengths, pairs, cfg["search"], rng, existing_members, anchor_usage,
        )
        total_tested += tested
        if best is None:
            raise RuntimeError(f"no admissible placement for fibre {fibre_index + 1}")
        existing_members.append(best["members"])
        anchor_body_ids = [int(sand_ids[best["i"]]), int(sand_ids[best["j"]])]
        anchor_usage.update(anchor_body_ids)
        fibres.append({
            "fibre_index": fibre_index,
            "members_per_fibre": len(local),
            "member_centres_m": best["members"].tolist(),
            "rotation_matrix": best["rotation"].tolist(),
            "translation_m": best["translation"].tolist(),
            "anchor_sand_body_ids": anchor_body_ids,
            "anchor_sand_indices": [int(best["i"]), int(best["j"])],
            "anchor_member_indices": [first_index, last_index],
            "anchor_clearances_m": best["anchor_clearances_m"],
            "initial_contacted_sand_body_ids": [int(sand_ids[index]) for index in best["contacted_indices"]],
            "initial_distinct_sand_contact_count": int(len(best["contacted_indices"])),
            "initial_normal_force_residual_relative": best["force_residual"],
            "initial_normal_moment_residual_relative": best["moment_residual"],
            "minimum_sand_fibre_clearance_m": best["minimum_sand_clearance_m"],
            "minimum_fibre_fibre_clearance_m": best["minimum_fibre_fibre_clearance_m"],
            "anchor_pair_distance_m": best["pair_distance_m"],
            "candidates_tested": tested,
        })

    finite_fibre_clearances = [row["minimum_fibre_fibre_clearance_m"] for row in fibres if row["minimum_fibre_fibre_clearance_m"] is not None]
    placement = {
        "schema": "lbs.stage26b-tier1-multifibre-placement.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "passed_geometry_preflight_only",
        "case": case,
        "algorithm": "greedy-force-moment-balanced-two-anchor-periodic-multifibre-v1",
        "cell_dimensions_m": lengths.tolist(),
        "sand_count": len(sand_centres),
        "fibre_count": len(fibres),
        "fibre_members_per_clump": len(local),
        "member_radius_m": member_radius,
        "local_tip_span_m": local_tip_span,
        "total_candidates_tested": total_tested,
        "maximum_anchor_multiplicity": max(anchor_usage.values()),
        "minimum_fibre_fibre_clearance_m": min(finite_fibre_clearances) if finite_fibre_clearances else None,
        "maximum_initial_force_residual_relative": max(row["initial_normal_force_residual_relative"] for row in fibres),
        "maximum_initial_moment_residual_relative": max(row["initial_normal_moment_residual_relative"] for row in fibres),
        "fibres": fibres,
        "source_hashes": {
            "config": digest(config_path),
            "stage26b_design_config": cfg["sources"]["stage26b_design_config_sha256"],
            "stage26b_resolved_design": cfg["sources"]["stage26b_resolved_design_sha256"],
            "stage26a_design_config": cfg["sources"]["stage26a_design_config_sha256"],
            "stage25_selected_result": source["stage25_selected_result_sha256"],
            "f37_geometry_review": source["f37_geometry_review_sha256"],
            "planner": digest(Path(__file__)),
        },
        "authority": cfg["authority"],
        "claim_boundary": cfg["claim_boundary"],
    }
    output.mkdir(parents=True)
    placement_path = output / "placement.json"
    with placement_path.open("x", encoding="utf-8") as stream:
        json.dump(placement, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "passed": True,
        "case_id": case["case_id"],
        "fibre_count": len(fibres),
        "total_candidates_tested": total_tested,
        "maximum_force_residual": placement["maximum_initial_force_residual_relative"],
        "maximum_moment_residual": placement["maximum_initial_moment_residual_relative"],
        "minimum_fibre_fibre_clearance_m": placement["minimum_fibre_fibre_clearance_m"],
        "placement_sha256": digest(placement_path),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
