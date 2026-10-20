"""Deterministic host-Python probe for fresh four-support F37 placements.

The two original tip constraints leave two angular degrees of freedom.  This
probe uses those degrees of freedom to fit two additional sand contacts, then
checks collision, support distribution, and six-DOF frictional wrench rank.
It is exploratory geometry work only: no YADE import or execution is allowed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from plan_stage26a_f37_placement_v1 import anchored_translation, rotation_aligning


SPENT_SUPPORT_BODY_IDS = {6, 18, 40, 119}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def exclusive_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def analytical_tip_feasible(distance, tip_span, first_radius, second_radius, tolerance=1e-14):
    shifted = abs(float(distance) - float(tip_span))
    return (
        abs(float(first_radius) - float(second_radius)) - tolerance
        <= shifted
        <= float(first_radius) + float(second_radius) + tolerance
    )


def periodic_clearance(members, sand_centres, sand_radii, lengths, member_radius):
    delta = members[:, None, :] - sand_centres[None, :, :]
    delta -= np.round(delta / lengths) * lengths
    clearance = np.linalg.norm(delta, axis=2) - (member_radius + sand_radii[None, :])
    return clearance, delta


def frictional_wrench_metrics(points, characteristic_length):
    points = np.asarray(points, dtype=float)
    centre = points.mean(axis=0)
    columns = []
    for point in points:
        arm = (point - centre) / characteristic_length
        for basis in np.eye(3):
            columns.append(np.r_[basis, np.cross(arm, basis)])
    matrix = np.asarray(columns, dtype=float).T
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = singular[0] * max(matrix.shape) * np.finfo(float).eps
    return (
        int(np.sum(singular > tolerance)),
        float(singular[-1] / singular[0]),
        singular.tolist(),
    )


def support_metrics(members, support_indices, clearance, delta, member_radius, tip_span):
    points = []
    normals = []
    member_indices = []
    for sand_index in support_indices:
        member_index = int(np.argmin(clearance[:, sand_index]))
        normal = delta[member_index, sand_index]
        normal /= np.linalg.norm(normal)
        points.append(members[member_index] - member_radius * normal)
        normals.append(normal)
        member_indices.append(member_index)
    rank, condition_ratio, singular = frictional_wrench_metrics(points, tip_span)
    normals = np.asarray(normals, dtype=float)
    normal_singular = np.linalg.svd(normals.T, compute_uv=False)
    normal_ratio = float(normal_singular[-1] / normal_singular[0])
    force_residual = float(np.linalg.norm(normals.sum(axis=0)) / len(normals))
    centre = members.mean(axis=0)
    moments = [np.cross(point - centre, normal) / tip_span for point, normal in zip(points, normals)]
    moment_residual = float(np.linalg.norm(np.sum(moments, axis=0)) / len(moments))
    return {
        "support_member_indices": member_indices,
        "frictional_wrench_rank": rank,
        "frictional_wrench_condition_ratio": condition_ratio,
        "frictional_wrench_singular_values": singular,
        "normal_span_condition_ratio": normal_ratio,
        "equal_normal_force_residual_relative": force_residual,
        "equal_normal_moment_residual_relative": moment_residual,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", required=True)
    parser.add_argument("--geometry", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=26061701)
    parser.add_argument("--maximum-anchor-pairs", type=int, default=96)
    parser.add_argument("--poses-per-anchor-pair", type=int, default=96)
    parser.add_argument("--maximum-optimizations", type=int, default=1200)
    parser.add_argument("--maximum-accepted-singles", type=int, default=24)
    args = parser.parse_args()
    network_path = Path(args.network).resolve()
    geometry_path = Path(args.geometry).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26f feasibility-probe output already exists")

    network = load_json(network_path)
    geometry = load_json(geometry_path)
    template = geometry["fibre_candidates"]["f37_kinked_ar10"]
    local = np.asarray([row["center_m"] for row in template["members"]], dtype=float)
    member_radius = 5.0e-5
    first_member, last_member = 0, len(local) - 1
    tip_span = float(np.linalg.norm(local[last_member] - local[first_member]))
    target_penetration = 0.005 * member_radius
    maximum_penetration = 0.02 * member_radius
    actual_contact_threshold = -0.001 * member_radius
    contact_fit_tolerance = 0.00025 * member_radius
    proximity_for_optimization = 1.0 * member_radius
    particles = network["particles"]
    sand_centres = np.asarray([row["position_m"] for row in particles], dtype=float)
    sand_radii = np.asarray([row["radius_m"] for row in particles], dtype=float)
    body_ids = np.asarray([int(row["sand_body_id"]) for row in particles], dtype=int)
    degrees = np.asarray([int(row["sand_network_degree"]) for row in particles], dtype=int)
    forces = np.asarray([float(row["incident_normal_force_sum_n"]) for row in particles])
    core = np.asarray([bool(row["load_bearing_core_member"]) for row in particles])
    lengths = np.diag(np.asarray(network["cell_hsize_m"], dtype=float))

    pairs = []
    for first in range(len(particles)):
        if not core[first] or degrees[first] < 4 or body_ids[first] in SPENT_SUPPORT_BODY_IDS:
            continue
        for second in range(first + 1, len(particles)):
            if not core[second] or degrees[second] < 4 or body_ids[second] in SPENT_SUPPORT_BODY_IDS:
                continue
            distance = float(np.linalg.norm(sand_centres[second] - sand_centres[first]))
            if not 0.00135 <= distance <= 0.00225:
                continue
            contact_first = sand_radii[first] + member_radius - target_penetration
            contact_second = sand_radii[second] + member_radius - target_penetration
            if not analytical_tip_feasible(distance, tip_span, contact_first, contact_second):
                continue
            pairs.append(
                (
                    -min(degrees[first], degrees[second]),
                    -min(forces[first], forces[second]),
                    int(body_ids[first]),
                    int(body_ids[second]),
                    first,
                    second,
                    contact_first,
                    contact_second,
                )
            )
    pairs.sort()
    pairs = pairs[: args.maximum_anchor_pairs]

    rng = random.Random(args.seed)
    accepted = []
    seen_support_sets = set()
    counters = {
        "poses_screened": 0,
        "outside_primary_cell": 0,
        "no_two_close_backup_bodies": 0,
        "optimizations_attempted": 0,
        "optimization_not_converged": 0,
        "postfit_overlap": 0,
        "postfit_contact_set": 0,
        "postfit_low_degree_contact": 0,
        "postfit_support_distribution": 0,
        "postfit_wrench_rank": 0,
        "postfit_wrench_condition": 0,
        "duplicate_support_set": 0,
        "accepted": 0,
    }

    def pose(pair, angles):
        _, _, _, _, first, second, contact_first, contact_second = pair
        direction = sand_centres[second] - sand_centres[first]
        rotation = rotation_aligning(
            local[last_member] - local[first_member], direction, float(angles[0])
        )
        rotated = local @ rotation.T
        translation = anchored_translation(
            sand_centres[first],
            sand_centres[second],
            rotated[first_member],
            rotated[last_member],
            contact_first,
            contact_second,
            float(angles[1]),
        )
        return rotated + translation, rotation, translation

    stop = False
    for pair in pairs:
        if stop:
            break
        _, _, _, _, first, second, _, _ = pair
        for _ in range(args.poses_per_anchor_pair):
            counters["poses_screened"] += 1
            angles0 = np.asarray([rng.random() * 2.0 * math.pi, rng.random() * 2.0 * math.pi])
            members0, _, _ = pose(pair, angles0)
            if (
                np.any(members0 - member_radius < 0.0)
                or np.any(members0 + member_radius > lengths)
            ):
                counters["outside_primary_cell"] += 1
                continue
            clearance0, _ = periodic_clearance(
                members0, sand_centres, sand_radii, lengths, member_radius
            )
            minimum0 = clearance0.min(axis=0)
            eligible = [
                index
                for index in np.argsort(minimum0)
                if index not in (first, second)
                and core[index]
                and degrees[index] >= 4
                and body_ids[index] not in SPENT_SUPPORT_BODY_IDS
            ][:2]
            if len(eligible) < 2 or minimum0[eligible[1]] > proximity_for_optimization:
                counters["no_two_close_backup_bodies"] += 1
                continue
            if counters["optimizations_attempted"] >= args.maximum_optimizations:
                stop = True
                break
            counters["optimizations_attempted"] += 1

            def residual(angles):
                members, _, _ = pose(pair, angles)
                clearance, _ = periodic_clearance(
                    members, sand_centres[eligible], sand_radii[eligible], lengths, member_radius
                )
                return (clearance.min(axis=0) + target_penetration) / member_radius

            fit = least_squares(
                residual,
                angles0,
                bounds=(np.zeros(2), np.full(2, 2.0 * math.pi)),
                xtol=1e-11,
                ftol=1e-11,
                gtol=1e-11,
                max_nfev=80,
            )
            if not fit.success or np.max(np.abs(residual(fit.x))) * member_radius > contact_fit_tolerance:
                counters["optimization_not_converged"] += 1
                continue
            members, rotation, translation = pose(pair, fit.x)
            if (
                np.any(members - member_radius < 0.0)
                or np.any(members + member_radius > lengths)
            ):
                counters["outside_primary_cell"] += 1
                continue
            clearance, delta = periodic_clearance(
                members, sand_centres, sand_radii, lengths, member_radius
            )
            minimum = clearance.min(axis=0)
            if float(minimum.min()) < -maximum_penetration - 1e-12:
                counters["postfit_overlap"] += 1
                continue
            support_indices = np.flatnonzero(minimum <= actual_contact_threshold).tolist()
            required = {first, second, eligible[0], eligible[1]}
            if len(support_indices) < 4 or not required.issubset(support_indices):
                counters["postfit_contact_set"] += 1
                continue
            if any(not core[index] or degrees[index] < 4 for index in support_indices):
                counters["postfit_low_degree_contact"] += 1
                continue
            metrics = support_metrics(
                members, support_indices, clearance, delta, member_radius, tip_span
            )
            member_indices = metrics["support_member_indices"]
            if len(set(member_indices)) < 3 or not any(
                4 <= member_index <= len(local) - 5 for member_index in member_indices
            ):
                counters["postfit_support_distribution"] += 1
                continue
            if metrics["frictional_wrench_rank"] < 6:
                counters["postfit_wrench_rank"] += 1
                continue
            if metrics["frictional_wrench_condition_ratio"] < 0.01:
                counters["postfit_wrench_condition"] += 1
                continue
            support_body_ids = tuple(sorted(int(body_ids[index]) for index in support_indices))
            if support_body_ids in seen_support_sets:
                counters["duplicate_support_set"] += 1
                continue
            seen_support_sets.add(support_body_ids)
            nearest_noncontacts = [
                index for index in np.argsort(minimum) if index not in support_indices
            ][:4]
            accepted.append(
                {
                    "single_index": len(accepted) + 1,
                    "tip_anchor_body_ids": [int(body_ids[first]), int(body_ids[second])],
                    "support_sand_body_ids": list(support_body_ids),
                    "support_network_degrees": [int(degrees[index]) for index in support_indices],
                    "support_member_indices": member_indices,
                    "support_clearances_um": [float(minimum[index] * 1e6) for index in support_indices],
                    "nearest_noncontact_gaps_um": [float(minimum[index] * 1e6) for index in nearest_noncontacts],
                    "angles_rad": fit.x.tolist(),
                    "rotation_matrix": rotation.tolist(),
                    "translation_m": translation.tolist(),
                    "member_centres_m": members.tolist(),
                    **metrics,
                }
            )
            counters["accepted"] += 1
            if len(accepted) >= args.maximum_accepted_singles:
                stop = True
                break

    output.mkdir(parents=True)
    result = {
        "schema": "lbs.stage26f-multicontact-feasibility-probe.v1",
        "passed": len(accepted) > 0,
        "status": "fresh_four_support_geometry_found" if accepted else "no_fresh_four_support_geometry_found_within_probe_budget",
        "candidate08_read_or_used": False,
        "spent_support_body_ids_excluded": sorted(SPENT_SUPPORT_BODY_IDS),
        "network_anchor_pair_count_after_static_screen": len(pairs),
        "probe_budget": {
            "seed": args.seed,
            "maximum_anchor_pairs": args.maximum_anchor_pairs,
            "poses_per_anchor_pair": args.poses_per_anchor_pair,
            "maximum_optimizations": args.maximum_optimizations,
            "maximum_accepted_singles": args.maximum_accepted_singles,
        },
        "geometry_gates": {
            "minimum_support_count": 4,
            "minimum_support_network_degree": 4,
            "minimum_distinct_support_member_indices": 3,
            "required_interior_support": True,
            "minimum_frictional_wrench_rank": 6,
            "minimum_frictional_wrench_condition_ratio": 0.01,
            "maximum_penetration_over_member_radius": 0.02,
        },
        "counters": counters,
        "accepted_single_count": len(accepted),
        "accepted_singles": accepted,
        "source_hashes": {
            "network": digest(network_path),
            "geometry": digest(geometry_path),
            "probe": digest(Path(__file__)),
        },
        "claim_boundary": "Exploratory host-Python geometry feasibility only; no candidate08 use, YADE execution, release, state promotion, deformation, flow, permeability, or production result.",
    }
    exclusive_json(output / "probe.json", result)
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "accepted_single_count": len(accepted),
                "optimizations_attempted": counters["optimizations_attempted"],
                "probe_sha256": digest(output / "probe.json"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
