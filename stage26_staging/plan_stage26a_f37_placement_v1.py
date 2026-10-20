"""Deterministic two-grain F37 placement in the accepted Stage25 periodic cell."""

import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def rotation_aligning(source, target, roll):
    source = np.asarray(source, dtype=float); source /= np.linalg.norm(source)
    target = np.asarray(target, dtype=float); target /= np.linalg.norm(target)
    cross = np.cross(source, target)
    dot = float(np.clip(np.dot(source, target), -1.0, 1.0))
    if np.linalg.norm(cross) < 1e-14:
        if dot > 0:
            base = np.eye(3)
        else:
            trial = np.array([1.0, 0.0, 0.0]) if abs(source[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
            axis = np.cross(source, trial); axis /= np.linalg.norm(axis)
            base = 2.0 * np.outer(axis, axis) - np.eye(3)
    else:
        axis = cross / np.linalg.norm(cross)
        angle = math.acos(dot)
        k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]], dtype=float)
        base = np.eye(3) + math.sin(angle) * k + (1.0 - math.cos(angle)) * (k @ k)
    axis = target
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]], dtype=float)
    around = np.eye(3) + math.sin(roll) * k + (1.0 - math.cos(roll)) * (k @ k)
    return around @ base


def perpendicular_basis(axis):
    axis = np.asarray(axis, dtype=float); axis /= np.linalg.norm(axis)
    trial = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
    first = np.cross(axis, trial); first /= np.linalg.norm(first)
    return first, np.cross(axis, first)


def anchored_translation(a, b, rotated_first, rotated_last, contact_first, contact_second, phase):
    span = rotated_last - rotated_first
    shifted_second = b - span
    delta = shifted_second - a
    distance = float(np.linalg.norm(delta))
    if distance < 1e-14 or distance > contact_first + contact_second or distance < abs(contact_first - contact_second):
        return None
    axis = delta / distance
    along = (contact_first**2 - contact_second**2 + distance**2) / (2.0 * distance)
    height2 = contact_first**2 - along**2
    if height2 < -1e-18:
        return None
    first, second = perpendicular_basis(axis)
    first_tip = a + along * axis + math.sqrt(max(0.0, height2)) * (math.cos(phase) * first + math.sin(phase) * second)
    return first_tip - rotated_first


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable placement output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    cfg = load_json(config_path)
    if cfg.get("status") != "authorized_bounded_dry_fibre_qualification":
        raise RuntimeError("configuration is not authorized")
    source = cfg["source"]
    for key in ["stage25_checkpoint_manifest", "stage25_checkpoint", "stage25_evaluation", "stage25_selected_result", "f37_geometry_review"]:
        path = Path(source[key])
        if digest(path) != source[key + "_sha256"]:
            raise RuntimeError("source hash mismatch: " + key)
    checkpoint_manifest = load_json(Path(source["stage25_checkpoint_manifest"]))
    evaluation = load_json(Path(source["stage25_evaluation"]))
    result = load_json(Path(source["stage25_selected_result"]))
    if not checkpoint_manifest.get("passed") or not evaluation.get("passed") or not result.get("passed"):
        raise RuntimeError("one or more Stage25 sources are not accepted")
    if checkpoint_manifest["selected_case_id"] != "mu_0.60" or evaluation["selection"]["case_id"] != "mu_0.60":
        raise RuntimeError("Stage25 selection mismatch")
    if checkpoint_manifest["evidence"]["checkpoint_sha256"] != source["stage25_checkpoint_sha256"]:
        raise RuntimeError("checkpoint manifest binding mismatch")

    review = load_json(Path(source["f37_geometry_review"]))
    template = review["fibre_candidates"][cfg["fibre"]["template_id"]]
    if len(template["members"]) != cfg["fibre"]["members_per_fibre"]:
        raise RuntimeError("F37 member count mismatch")
    local = np.array([row["center_m"] for row in template["members"]], dtype=float)
    member_radius = float(cfg["fibre"]["member_radius_m"])
    if not all(abs(float(row["radius_m"]) - member_radius) < 1e-15 for row in template["members"]):
        raise RuntimeError("F37 radius mismatch")
    first_index, last_index = [int(value) for value in cfg["placement"]["anchor_member_indices"]]
    span = float(np.linalg.norm(local[last_index] - local[first_index]))
    if span / float(cfg["fibre"]["contour_length_m"]) < cfg["placement"]["minimum_anchor_support_span_over_contour_length"]:
        raise RuntimeError("F37 anchor span is too short")

    sand_centres = np.array([row["position_m"] for row in result["particles"]], dtype=float)
    sand_radii = np.array([row["radius_m"] for row in result["particles"]], dtype=float)
    sand_ids = np.array([int(row["body_id"]) for row in result["particles"]], dtype=int)
    lengths = np.array(result["terminal"]["cell_dimensions_m"], dtype=float)
    if len(sand_centres) != cfg["acceptance"]["required_sand_particle_count"]:
        raise RuntimeError("sand particle count mismatch")

    placement = cfg["placement"]
    target_penetration = float(placement["target_anchor_penetration_over_member_radius"]) * member_radius
    maximum_penetration = float(placement["maximum_sand_fibre_penetration_over_member_radius"]) * member_radius
    pairs = []
    for i in range(len(sand_centres)):
        for j in range(i + 1, len(sand_centres)):
            delta = sand_centres[j] - sand_centres[i]
            distance = float(np.linalg.norm(delta))
            if placement["pair_distance_minimum_m"] <= distance <= placement["pair_distance_maximum_m"]:
                pairs.append((i, j, distance))
    rng = random.Random(int(placement["random_seed"]))
    rng.shuffle(pairs)
    best = None
    tested = 0
    max_trials = int(placement["maximum_pair_trials"])
    for i, j, pair_distance in pairs:
        direction = sand_centres[j] - sand_centres[i]
        for _ in range(int(placement["rolls_per_pair"])):
            if tested >= max_trials:
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
            if placement["require_fibre_wholly_inside_primary_cell"] and (np.any(members - member_radius < 0.0) or np.any(members + member_radius > lengths)):
                continue
            delta = members[:, None, :] - sand_centres[None, :, :]
            delta -= np.round(delta / lengths) * lengths
            clearance = np.linalg.norm(delta, axis=2) - member_radius - sand_radii[None, :]
            minimum = float(clearance.min())
            nearest_by_sand = clearance.min(axis=0)
            contacted = np.flatnonzero(nearest_by_sand <= 1e-10)
            if minimum < -maximum_penetration - 1e-12 or len(contacted) < placement["minimum_distinct_initial_sand_contacts"]:
                continue
            anchor_clearances = [float(clearance[first_index, i]), float(clearance[last_index, j])]
            if max(abs(value + target_penetration) for value in anchor_clearances) > 1e-10:
                continue
            extra_contacts = len(set(contacted.tolist()) - {i, j})
            score = (extra_contacts, abs(minimum + target_penetration), -float(nearest_by_sand[contacted].max()))
            candidate = {
                "score": score, "i": i, "j": j, "pair_distance": pair_distance,
                "rotation": rotation, "translation": translation, "members": members,
                "minimum": minimum, "contacted": contacted, "nearest": nearest_by_sand,
                "anchor_clearances": anchor_clearances,
            }
            if best is None or score < best["score"]:
                best = candidate
            if extra_contacts == 0 and minimum >= -maximum_penetration:
                break
        if best is not None and best["score"][0] == 0:
            break
    if best is None:
        raise RuntimeError("no admissible two-anchor F37 placement found")

    plan = {
        "schema": "lbs.stage26a-dry-f37-insertion.v1.placement",
        "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "algorithm": placement["algorithm"],
        "random_seed": placement["random_seed"],
        "candidates_tested": tested,
        "cell_dimensions_m": lengths.tolist(),
        "sand_count": len(sand_centres),
        "fibre_count": 1,
        "fibre_members_per_clump": len(local),
        "member_radius_m": member_radius,
        "target_anchor_penetration_m": target_penetration,
        "maximum_allowed_penetration_m": maximum_penetration,
        "minimum_sand_fibre_clearance_m": best["minimum"],
        "anchor_sand_body_ids": [int(sand_ids[best["i"]]), int(sand_ids[best["j"]])],
        "anchor_sand_indices": [int(best["i"]), int(best["j"])],
        "anchor_member_indices": [first_index, last_index],
        "anchor_clearances_m": best["anchor_clearances"],
        "initial_contacted_sand_body_ids": [int(sand_ids[index]) for index in best["contacted"]],
        "initial_distinct_sand_contact_count": int(len(best["contacted"])),
        "anchor_pair_distance_m": best["pair_distance"],
        "rotation_matrix": best["rotation"].tolist(),
        "translation_m": best["translation"].tolist(),
        "member_centres_m": best["members"].tolist(),
        "local_tip_span_m": span,
        "source_hashes": {
            "config": digest(config_path),
            "stage25_checkpoint_manifest": source["stage25_checkpoint_manifest_sha256"],
            "stage25_checkpoint": source["stage25_checkpoint_sha256"],
            "stage25_evaluation": source["stage25_evaluation_sha256"],
            "stage25_selected_result": source["stage25_selected_result_sha256"],
            "f37_geometry_review": source["f37_geometry_review_sha256"],
            "planner": digest(Path(__file__)),
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    plan_path = output / "placement.json"
    with plan_path.open("x", encoding="utf-8") as stream:
        json.dump(plan, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "candidates_tested": tested, "contacts": len(best["contacted"]), "minimum_clearance_m": best["minimum"], "placement_sha256": digest(plan_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
