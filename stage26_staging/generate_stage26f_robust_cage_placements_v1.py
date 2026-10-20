"""Generate fresh two-F37 placements with four-support sand cages.

Host-Python geometry only.  This module never imports or invokes YADE.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

import probe_stage26f_multicontact_feasibility_v1 as geometry_helpers
from plan_stage26a_f37_placement_v1 import anchored_translation, rotation_aligning


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path: Path):
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def exclusive_json(path: Path, value) -> None:
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def verify_source_hashes(config):
    for key, value in config["sources"].items():
        if key.endswith("_sha256"):
            continue
        expected = config["sources"].get(key + "_sha256")
        if expected is not None and digest(Path(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def periodic_fibre_clearance(first, second, lengths, member_radius):
    delta = first[:, None, :] - second[None, :, :]
    delta -= np.round(delta / lengths) * lengths
    return float(np.linalg.norm(delta, axis=2).min() - 2.0 * member_radius)


class GeometryContext:
    def __init__(self, config):
        network = load_json(Path(config["sources"]["network"]))
        review = load_json(Path(config["sources"]["f37_geometry_review"]))
        template = review["fibre_candidates"][config["fibre"]["template_id"]]
        self.local = np.asarray([row["center_m"] for row in template["members"]], dtype=float)
        self.member_radius = float(config["fibre"]["member_radius_m"])
        self.first_member, self.last_member = [int(value) for value in config["fibre"]["tip_member_indices"]]
        self.tip_span = float(
            np.linalg.norm(self.local[self.last_member] - self.local[self.first_member])
        )
        self.target_penetration = (
            float(config["fibre"]["target_contact_penetration_over_member_radius"])
            * self.member_radius
        )
        self.maximum_penetration = (
            float(config["fibre"]["maximum_contact_penetration_over_member_radius"])
            * self.member_radius
        )
        particles = network["particles"]
        self.sand_centres = np.asarray([row["position_m"] for row in particles], dtype=float)
        self.sand_radii = np.asarray([row["radius_m"] for row in particles], dtype=float)
        self.body_ids = np.asarray([int(row["sand_body_id"]) for row in particles], dtype=int)
        self.degrees = np.asarray([int(row["sand_network_degree"]) for row in particles], dtype=int)
        self.forces = np.asarray([float(row["incident_normal_force_sum_n"]) for row in particles])
        self.core = np.asarray([bool(row["load_bearing_core_member"]) for row in particles])
        self.lengths = np.diag(np.asarray(network["cell_hsize_m"], dtype=float))
        self.minimum_degree = int(config["static_acceptance"]["minimum_support_network_degree"])
        self.excluded_body_ids = set(
            int(value) for value in config["static_acceptance"]["excluded_spent_support_body_ids"]
        )

    def all_anchor_pairs(self):
        pairs = []
        for first in range(len(self.body_ids)):
            if (
                not self.core[first]
                or self.degrees[first] < self.minimum_degree
                or self.body_ids[first] in self.excluded_body_ids
            ):
                continue
            for second in range(first + 1, len(self.body_ids)):
                if (
                    not self.core[second]
                    or self.degrees[second] < self.minimum_degree
                    or self.body_ids[second] in self.excluded_body_ids
                ):
                    continue
                distance = float(np.linalg.norm(self.sand_centres[second] - self.sand_centres[first]))
                if not 0.00135 <= distance <= 0.00225:
                    continue
                first_radius = self.sand_radii[first] + self.member_radius - self.target_penetration
                second_radius = self.sand_radii[second] + self.member_radius - self.target_penetration
                if not geometry_helpers.analytical_tip_feasible(
                    distance, self.tip_span, first_radius, second_radius
                ):
                    continue
                pairs.append(
                    {
                        "first": first,
                        "second": second,
                        "first_radius": first_radius,
                        "second_radius": second_radius,
                        "minimum_degree": int(min(self.degrees[first], self.degrees[second])),
                        "minimum_force": float(min(self.forces[first], self.forces[second])),
                    }
                )
        return pairs

    def pose(self, pair, angles):
        first, second = pair["first"], pair["second"]
        direction = self.sand_centres[second] - self.sand_centres[first]
        rotation = rotation_aligning(
            self.local[self.last_member] - self.local[self.first_member],
            direction,
            float(angles[0]),
        )
        rotated = self.local @ rotation.T
        translation = anchored_translation(
            self.sand_centres[first],
            self.sand_centres[second],
            rotated[self.first_member],
            rotated[self.last_member],
            pair["first_radius"],
            pair["second_radius"],
            float(angles[1]),
        )
        return rotated + translation, rotation, translation

    def clearance(self, members, centres=None, radii=None):
        return geometry_helpers.periodic_clearance(
            members,
            self.sand_centres if centres is None else centres,
            self.sand_radii if radii is None else radii,
            self.lengths,
            self.member_radius,
        )


def fit_single(context, pair, angles0, config, exploratory_support_sets):
    first, second = pair["first"], pair["second"]
    members0, _, _ = context.pose(pair, angles0)
    if np.any(members0 - context.member_radius < 0.0) or np.any(
        members0 + context.member_radius > context.lengths
    ):
        return None, "outside_primary_cell"
    clearance0, _ = context.clearance(members0)
    minimum0 = clearance0.min(axis=0)
    eligible = [
        index
        for index in np.argsort(minimum0)
        if index not in (first, second)
        and context.core[index]
        and context.degrees[index] >= context.minimum_degree
        and context.body_ids[index] not in context.excluded_body_ids
    ][:2]
    if len(eligible) < 2 or minimum0[eligible[1]] > context.member_radius:
        return None, "no_two_close_backup_bodies"

    def residual(angles):
        members, _, _ = context.pose(pair, angles)
        clearance, _ = context.clearance(
            members, context.sand_centres[eligible], context.sand_radii[eligible]
        )
        return (clearance.min(axis=0) + context.target_penetration) / context.member_radius

    fit = least_squares(
        residual,
        angles0,
        bounds=(np.zeros(2), np.full(2, 2.0 * math.pi)),
        xtol=1e-11,
        ftol=1e-11,
        gtol=1e-11,
        max_nfev=80,
    )
    tolerance = 0.00025 * context.member_radius
    if not fit.success or np.max(np.abs(residual(fit.x))) * context.member_radius > tolerance:
        return None, "contact_fit_not_converged"
    members, rotation, translation = context.pose(pair, fit.x)
    if np.any(members - context.member_radius < 0.0) or np.any(
        members + context.member_radius > context.lengths
    ):
        return None, "outside_primary_cell"
    clearance, delta = context.clearance(members)
    minimum = clearance.min(axis=0)
    if float(minimum.min()) < -context.maximum_penetration - 1e-12:
        return None, "excessive_sand_fibre_penetration"
    contact_threshold = -0.001 * context.member_radius
    supports = np.flatnonzero(minimum <= contact_threshold).tolist()
    required = {first, second, eligible[0], eligible[1]}
    if len(supports) < config["static_acceptance"]["minimum_distinct_sand_supports_per_fibre"] or not required.issubset(supports):
        return None, "insufficient_support_contact_set"
    if any(
        not context.core[index] or context.degrees[index] < context.minimum_degree
        for index in supports
    ):
        return None, "low_degree_or_noncore_support"
    support_body_ids = tuple(sorted(int(context.body_ids[index]) for index in supports))
    if support_body_ids in exploratory_support_sets:
        return None, "exploratory_probe_support_set_excluded"
    metrics = geometry_helpers.support_metrics(
        members,
        supports,
        clearance,
        delta,
        context.member_radius,
        context.tip_span,
    )
    member_indices = metrics["support_member_indices"]
    if len(set(member_indices)) < config["static_acceptance"]["minimum_distinct_support_member_indices"]:
        return None, "insufficient_distinct_support_members"
    interior = sorted(
        set(index for index in member_indices if index not in (context.first_member, context.last_member))
    )
    if len(interior) < 2 or interior[-1] - interior[0] < config["static_acceptance"]["minimum_interior_support_member_separation"]:
        return None, "interior_supports_not_separated"
    acceptance = config["static_acceptance"]
    if metrics["frictional_wrench_rank"] < acceptance["minimum_frictional_wrench_rank"]:
        return None, "wrench_rank"
    if metrics["frictional_wrench_condition_ratio"] < acceptance["minimum_frictional_wrench_condition_ratio"]:
        return None, "wrench_condition"
    if metrics["normal_span_condition_ratio"] < acceptance["minimum_contact_normal_span_condition_ratio"]:
        return None, "normal_span_condition"
    if metrics["equal_normal_force_residual_relative"] > acceptance["maximum_equal_normal_force_residual_relative"]:
        return None, "equal_normal_force_residual"
    if metrics["equal_normal_moment_residual_relative"] > acceptance["maximum_equal_normal_moment_residual_relative"]:
        return None, "equal_normal_moment_residual"
    noncontacts = [index for index in np.argsort(minimum) if index not in supports][:4]
    return {
        "tip_anchor_sand_body_ids": [int(context.body_ids[first]), int(context.body_ids[second])],
        "support_sand_body_ids": list(support_body_ids),
        "support_network_degrees": [int(context.degrees[index]) for index in supports],
        "support_member_indices": member_indices,
        "support_clearances_m": [float(minimum[index]) for index in supports],
        "nearest_noncontact_gaps_m": [float(minimum[index]) for index in noncontacts],
        "rotation_matrix": rotation.tolist(),
        "translation_m": translation.tolist(),
        "member_centres_m": members.tolist(),
        "angles_rad": fit.x.tolist(),
        **metrics,
    }, "accepted_single"


def generate_candidate(context, candidate_index, config, all_pairs, exploratory_sets, used_joint_topologies):
    budget = config["search_budget"]
    rng = random.Random(int(budget["candidate_seed_base"]) + candidate_index)
    pairs = list(all_pairs)
    rng.shuffle(pairs)
    pairs = pairs[: int(budget["maximum_anchor_pairs_per_candidate"])]
    counters = Counter()
    pool = []
    support_sets = set()
    joint = None
    local_fits = 0
    for pair in pairs:
        for _ in range(int(budget["poses_per_anchor_pair"])):
            counters["poses_screened"] += 1
            angles = np.asarray([rng.random() * 2.0 * math.pi, rng.random() * 2.0 * math.pi])
            if local_fits >= int(budget["maximum_local_contact_fits_per_candidate"]):
                counters["local_fit_budget_reached"] += 1
                break
            single, decision = fit_single(context, pair, angles, config, exploratory_sets)
            if decision not in ("outside_primary_cell", "no_two_close_backup_bodies"):
                local_fits += 1
            counters[decision] += 1
            if single is None:
                continue
            support_set = tuple(single["support_sand_body_ids"])
            if support_set in support_sets:
                counters["duplicate_single_support_set"] += 1
                continue
            for retained in pool:
                if set(support_set).intersection(retained["support_sand_body_ids"]):
                    continue
                clearance = periodic_fibre_clearance(
                    np.asarray(single["member_centres_m"]),
                    np.asarray(retained["member_centres_m"]),
                    context.lengths,
                    context.member_radius,
                )
                if clearance < config["static_acceptance"]["minimum_initial_fibre_fibre_clearance_m"]:
                    continue
                topology = tuple(sorted((support_set, tuple(retained["support_sand_body_ids"]))))
                if topology in used_joint_topologies:
                    continue
                first = copy.deepcopy(retained)
                second = copy.deepcopy(single)
                first["fibre_index"] = 0
                second["fibre_index"] = 1
                first["minimum_fibre_fibre_clearance_m"] = clearance
                second["minimum_fibre_fibre_clearance_m"] = clearance
                joint = [first, second]
                used_joint_topologies.add(topology)
                counters["accepted_joint_pair"] += 1
                break
            if joint is not None:
                break
            if len(pool) < int(budget["maximum_retained_single_fibres_per_candidate"]):
                pool.append(single)
                support_sets.add(support_set)
                counters["accepted_single_retained"] += 1
            else:
                counters["accepted_single_pool_full"] += 1
        if joint is not None or local_fits >= int(budget["maximum_local_contact_fits_per_candidate"]):
            break
    return joint, counters, pool, local_fits, len(pairs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26f campaign output already exists")
    config = load_json(config_path)
    if config.get("status") != "authorized_host_python_geometry_generation_only":
        raise RuntimeError("Stage26f host-Python geometry generation is not authorized")
    authority = config["authority"]
    if authority.get("host_python_geometry_generation_authorized") is not True or any(
        authority.get(key, False)
        for key in (
            "candidate08_execution_authorized",
            "yade_execution_authorized",
            "free_release_authorized",
            "rehydration_authorized",
            "deformation_authorized",
            "flow_authorized",
            "permeability_claim_authorized",
        )
    ):
        raise RuntimeError("Stage26f authority boundary is invalid")
    verify_source_hashes(config)
    diagnostic = load_json(Path(config["sources"]["spent_case_diagnostic"]))
    probe = load_json(Path(config["sources"]["exploratory_multicontact_probe"]))
    if diagnostic.get("candidate08_read_or_used") is not False or probe.get("candidate08_read_or_used") is not False:
        raise RuntimeError("candidate08 reserve boundary is not intact")
    if probe["source_hashes"]["probe"] != digest(Path(geometry_helpers.__file__)):
        raise RuntimeError("geometry-helper source no longer matches exploratory evidence")
    exploratory_sets = {
        tuple(sorted(int(value) for value in row["support_sand_body_ids"]))
        for row in probe["accepted_singles"]
    }
    context = GeometryContext(config)
    all_pairs = context.all_anchor_pairs()
    output.mkdir(parents=True)
    used_joint_topologies = set()
    index_rows = []
    for candidate_index in range(1, int(config["search_budget"]["candidate_count"]) + 1):
        candidate_id = f"stage26f_f002_cage_candidate_{candidate_index:02d}"
        candidate_output = output / candidate_id
        candidate_output.mkdir()
        fibres, counters, pool, fits, sampled_pair_count = generate_candidate(
            context,
            candidate_index,
            config,
            all_pairs,
            exploratory_sets,
            used_joint_topologies,
        )
        passed = fibres is not None
        search_summary = {
            "schema": "lbs.stage26f-cage-search-summary.v1",
            "candidate_id": candidate_id,
            "passed": passed,
            "sampled_anchor_pair_count": sampled_pair_count,
            "local_contact_fit_count": fits,
            "retained_single_count": len(pool),
            "counters": dict(sorted(counters.items())),
            "retained_single_support_sets": [row["support_sand_body_ids"] for row in pool],
        }
        exclusive_json(candidate_output / "search_summary.json", search_summary)
        placement = {
            "schema": "lbs.stage26f-robust-four-support-two-f37-placement.v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "candidate_id": candidate_id,
            "candidate_index": candidate_index,
            "seed": int(config["search_budget"]["candidate_seed_base"]) + candidate_index,
            "passed": passed,
            "status": "passed_static_robust_cage_geometry" if passed else "offline_budget_exhausted_without_joint_cage",
            "sand_count": len(context.body_ids),
            "fibre_count": 0 if fibres is None else len(fibres),
            "members_per_fibre": len(context.local),
            "member_radius_m": context.member_radius,
            "fibres": [] if fibres is None else fibres,
            "candidate08_read_or_used": False,
            "source_hashes": {
                "config": digest(config_path),
                "network": digest(Path(config["sources"]["network"])),
                "geometry": digest(Path(config["sources"]["f37_geometry_review"])),
                "generator": digest(Path(__file__)),
                "geometry_helpers": digest(Path(geometry_helpers.__file__)),
            },
            "authority": config["authority"],
            "claim_boundary": config["claim_boundary"],
        }
        exclusive_json(candidate_output / "placement.json", placement)
        completion = {
            "schema": "lbs.stage26f-cage-candidate-completion.v1",
            "candidate_id": candidate_id,
            "passed": passed,
            "placement_sha256": digest(candidate_output / "placement.json"),
            "search_summary_sha256": digest(candidate_output / "search_summary.json"),
            "claim_boundary": config["claim_boundary"],
        }
        exclusive_json(candidate_output / "completion.json", completion)
        index_rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_index": candidate_index,
                "seed": placement["seed"],
                "passed": passed,
                "local_contact_fit_count": fits,
                "retained_single_count": len(pool),
                "placement_sha256": completion["placement_sha256"],
                "search_summary_sha256": completion["search_summary_sha256"],
            }
        )
    index_path = output / "candidate_index.csv"
    with index_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(index_rows[0]))
        writer.writeheader()
        writer.writerows(index_rows)
    passing = sum(bool(row["passed"]) for row in index_rows)
    completion = {
        "schema": "lbs.stage26f-robust-cage-campaign-completion.v1",
        "passed": passing >= config["campaign_acceptance"]["minimum_passing_two_fibre_candidates"]
        and len(used_joint_topologies) >= config["campaign_acceptance"]["minimum_distinct_joint_support_topologies"],
        "status": "completed_predeclared_static_campaign",
        "candidate_count": len(index_rows),
        "passing_candidate_count": passing,
        "distinct_joint_support_topology_count": len(used_joint_topologies),
        "candidate08_read_or_used": False,
        "candidate_index_sha256": digest(index_path),
        "source_hashes": {
            "config": digest(config_path),
            "network": digest(Path(config["sources"]["network"])),
            "geometry": digest(Path(config["sources"]["f37_geometry_review"])),
            "generator": digest(Path(__file__)),
            "geometry_helpers": digest(Path(geometry_helpers.__file__)),
        },
        "claim_boundary": config["claim_boundary"],
    }
    exclusive_json(output / "completion.json", completion)
    print(
        json.dumps(
            {
                "passed": completion["passed"],
                "passing_candidate_count": passing,
                "distinct_joint_support_topology_count": len(used_joint_topologies),
                "completion_sha256": digest(output / "completion.json"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
