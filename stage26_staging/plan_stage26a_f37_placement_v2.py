"""Force- and moment-balanced periodic two-grain F37 placement for Stage26a."""

import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from plan_stage26a_f37_placement_v1 import anchored_translation, load_json, rotation_aligning


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


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
    force_sum = np.sum(forces, axis=0)
    force_scale = sum(np.linalg.norm(value) for value in forces)
    moment_sum = np.sum(moments, axis=0)
    lever_scale = max(np.linalg.norm(members[last_index] - members[first_index]), 1e-30) * force_scale
    return float(np.linalg.norm(force_sum) / force_scale), float(np.linalg.norm(moment_sum) / lever_scale)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve(); output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable placement output already exists")
    output.parent.mkdir(parents=True, exist_ok=True); output.mkdir()
    cfg = load_json(config_path); source = cfg["source"]
    if cfg.get("status") != "authorized_bounded_dry_fibre_qualification":
        raise RuntimeError("configuration is not authorized")
    for key in ["stage25_checkpoint_manifest", "stage25_checkpoint", "stage25_evaluation", "stage25_selected_result", "f37_geometry_review"]:
        if digest(Path(source[key])) != source[key + "_sha256"]:
            raise RuntimeError("source hash mismatch: " + key)
    checkpoint_manifest = load_json(Path(source["stage25_checkpoint_manifest"]))
    evaluation = load_json(Path(source["stage25_evaluation"]))
    result = load_json(Path(source["stage25_selected_result"]))
    if not checkpoint_manifest.get("passed") or not evaluation.get("passed") or not result.get("passed"):
        raise RuntimeError("Stage25 source is not accepted")
    review = load_json(Path(source["f37_geometry_review"]))
    template = review["fibre_candidates"][cfg["fibre"]["template_id"]]
    local = np.array([row["center_m"] for row in template["members"]], dtype=float)
    member_radius = float(cfg["fibre"]["member_radius_m"])
    first_index, last_index = [int(value) for value in cfg["placement"]["anchor_member_indices"]]
    span = float(np.linalg.norm(local[last_index] - local[first_index]))
    if span / float(cfg["fibre"]["contour_length_m"]) < cfg["placement"]["minimum_anchor_support_span_over_contour_length"]:
        raise RuntimeError("F37 anchor span is too short")
    sand_centres = np.array([row["position_m"] for row in result["particles"]], dtype=float)
    sand_radii = np.array([row["radius_m"] for row in result["particles"]], dtype=float)
    sand_ids = np.array([int(row["body_id"]) for row in result["particles"]], dtype=int)
    lengths = np.array(result["terminal"]["cell_dimensions_m"], dtype=float)
    placement = cfg["placement"]
    target_penetration = float(placement["target_anchor_penetration_over_member_radius"]) * member_radius
    maximum_penetration = float(placement["maximum_sand_fibre_penetration_over_member_radius"]) * member_radius
    maximum_force_residual = float(placement["maximum_initial_normal_force_residual_relative"])
    maximum_moment_residual = float(placement["maximum_initial_normal_moment_residual_relative"])
    pairs = []
    for i in range(len(sand_centres)):
        for j in range(i + 1, len(sand_centres)):
            distance = float(np.linalg.norm(sand_centres[j] - sand_centres[i]))
            if placement["pair_distance_minimum_m"] <= distance <= placement["pair_distance_maximum_m"]:
                pairs.append((i, j, distance))
    rng = random.Random(int(placement["random_seed"]) + 1); rng.shuffle(pairs)
    best = None; tested = 0; max_trials = int(placement["maximum_pair_trials"])
    for i, j, pair_distance in pairs:
        direction = sand_centres[j] - sand_centres[i]
        for _ in range(int(placement["rolls_per_pair"])):
            if tested >= max_trials:
                break
            tested += 1
            rotation = rotation_aligning(local[last_index] - local[first_index], direction, rng.random() * 2.0 * math.pi)
            rotated = local @ rotation.T
            translation = anchored_translation(sand_centres[i], sand_centres[j], rotated[first_index], rotated[last_index], sand_radii[i] + member_radius - target_penetration, sand_radii[j] + member_radius - target_penetration, rng.random() * 2.0 * math.pi)
            if translation is None:
                continue
            members = rotated + translation
            if placement["require_fibre_wholly_inside_primary_cell"] and (np.any(members - member_radius < 0.0) or np.any(members + member_radius > lengths)):
                continue
            delta = members[:, None, :] - sand_centres[None, :, :]
            delta -= np.round(delta / lengths) * lengths
            clearance = np.linalg.norm(delta, axis=2) - member_radius - sand_radii[None, :]
            minimum = float(clearance.min()); nearest = clearance.min(axis=0)
            contacted = np.flatnonzero(nearest <= 1e-10)
            if minimum < -maximum_penetration - 1e-12 or len(contacted) < placement["minimum_distinct_initial_sand_contacts"]:
                continue
            anchor_clearances = [float(clearance[first_index, i]), float(clearance[last_index, j])]
            if max(abs(value + target_penetration) for value in anchor_clearances) > 1e-10:
                continue
            force_residual, moment_residual = balance_metrics(members, first_index, last_index, sand_centres[i], sand_centres[j], lengths)
            if force_residual > maximum_force_residual or moment_residual > maximum_moment_residual:
                continue
            extra = len(set(contacted.tolist()) - {i, j})
            score = (extra, force_residual, moment_residual, abs(minimum + target_penetration))
            candidate = {"score": score, "i": i, "j": j, "pair_distance": pair_distance, "rotation": rotation, "translation": translation, "members": members, "minimum": minimum, "contacted": contacted, "anchor_clearances": anchor_clearances, "force_residual": force_residual, "moment_residual": moment_residual}
            if best is None or score < best["score"]:
                best = candidate
            if extra == 0 and force_residual <= 0.02 and moment_residual <= 0.02:
                break
        if best is not None and best["score"][0] == 0 and best["force_residual"] <= 0.02 and best["moment_residual"] <= 0.02:
            break
    if best is None:
        raise RuntimeError("no force/moment-balanced admissible F37 placement found")
    plan = {
        "schema": "lbs.stage26a-dry-f37-insertion.v2.placement", "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "algorithm": "two-sand-tip-anchor-force-moment-balanced-periodic-v2",
        "random_seed": int(placement["random_seed"]) + 1, "candidates_tested": tested,
        "cell_dimensions_m": lengths.tolist(), "sand_count": len(sand_centres), "fibre_count": 1,
        "fibre_members_per_clump": len(local), "member_radius_m": member_radius,
        "target_anchor_penetration_m": target_penetration, "maximum_allowed_penetration_m": maximum_penetration,
        "minimum_sand_fibre_clearance_m": best["minimum"],
        "anchor_sand_body_ids": [int(sand_ids[best["i"]]), int(sand_ids[best["j"]])],
        "anchor_sand_indices": [int(best["i"]), int(best["j"])], "anchor_member_indices": [first_index, last_index],
        "anchor_clearances_m": best["anchor_clearances"],
        "initial_contacted_sand_body_ids": [int(sand_ids[index]) for index in best["contacted"]],
        "initial_distinct_sand_contact_count": int(len(best["contacted"])), "anchor_pair_distance_m": best["pair_distance"],
        "initial_normal_force_residual_relative": best["force_residual"],
        "initial_normal_moment_residual_relative": best["moment_residual"],
        "rotation_matrix": best["rotation"].tolist(), "translation_m": best["translation"].tolist(),
        "member_centres_m": best["members"].tolist(), "local_tip_span_m": span,
        "source_hashes": {"config": digest(config_path), "stage25_checkpoint_manifest": source["stage25_checkpoint_manifest_sha256"], "stage25_checkpoint": source["stage25_checkpoint_sha256"], "stage25_evaluation": source["stage25_evaluation_sha256"], "stage25_selected_result": source["stage25_selected_result_sha256"], "f37_geometry_review": source["f37_geometry_review_sha256"], "planner": digest(Path(__file__))},
        "claim_boundary": cfg["claim_boundary"],
    }
    plan_path = output / "placement.json"
    with plan_path.open("x", encoding="utf-8") as stream:
        json.dump(plan, stream, indent=2, sort_keys=True, allow_nan=False); stream.write("\n")
    print(json.dumps({"passed": True, "candidates_tested": tested, "contacts": len(best["contacted"]), "force_residual": best["force_residual"], "moment_residual": best["moment_residual"], "placement_sha256": digest(plan_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
