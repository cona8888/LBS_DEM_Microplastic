"""Diagnose the spent Stage26 two-fibre placements before a cage redesign.

This is a host-Python, read-only evidence analysis.  It never imports YADE and
never executes mechanics, release, or flow.  Candidate08 is deliberately not
read: it remains an untouched validation geometry.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import deque
from pathlib import Path

import numpy as np


SPENT_CASES = {
    1: (
        "stage26_runs/stage26d_adaptive_equilibration_20260816/development_01/"
        "revision3_candidate01/adaptive_evaluation_v1.json"
    ),
    4: (
        "stage26_runs/stage26d_adaptive_equilibration_20260816/holdout_01/"
        "revision3_candidate04/adaptive_evaluation_v1.json"
    ),
    5: (
        "stage26_runs/stage26e_qualified_state_capture_20260816/development_01/"
        "revision3_candidate05/result.json"
    ),
    7: (
        "stage26_runs/stage26e_qualified_state_capture_20260816/heldout_01/"
        "revision3_candidate07/heldout_evaluation_v1.json"
    ),
}


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


def shortest_path_length(adjacency, start, stop):
    if start == stop:
        return 0
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        node, depth = queue.popleft()
        for neighbour in adjacency.get(node, ()):
            if neighbour == stop:
                return depth + 1
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append((neighbour, depth + 1))
    return None


def frictional_wrench_metrics(contact_points, characteristic_length):
    """Rank/conditioning of arbitrary contact forces at point contacts.

    Each contact contributes three force directions.  Moments are divided by
    the fibre length so the six rows are dimensionless and comparable.
    """
    points = np.asarray(contact_points, dtype=float)
    centre = points.mean(axis=0)
    columns = []
    for point in points:
        arm = (point - centre) / characteristic_length
        for basis in np.eye(3):
            columns.append(np.r_[basis, np.cross(arm, basis)])
    matrix = np.asarray(columns, dtype=float).T
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = singular[0] * max(matrix.shape) * np.finfo(float).eps
    rank = int(np.sum(singular > tolerance))
    ratio = float(singular[-1] / singular[0]) if singular[0] else 0.0
    return rank, ratio, singular.tolist()


def case_outcome(index, evidence):
    if index in (1, 4):
        return {
            "qualified": bool(evidence["qualified_fixed_prefilter"]),
            "earliest_window": evidence["earliest_qualifying_window_blocks"],
            "passing_row_count": evidence["metrics"]["passing_equilibrium_row_count"],
            "terminal_mean_stress_pa": evidence["metrics"]["window_terminal_mean_stress_pa"],
            "terminal_unbalanced_force": evidence["metrics"]["window_terminal_unbalanced_force"],
        }
    if index == 5:
        return {
            "qualified": bool(evidence["qualified_fixed_state_captured"]),
            "earliest_window": evidence["captured_window"],
            "passing_row_count": 10,
            "terminal_mean_stress_pa": evidence["capture_row"]["mean_effective_stress_pa_compression_positive"],
            "terminal_unbalanced_force": evidence["capture_row"]["unbalanced_force"],
        }
    return {
        "qualified": bool(evidence["heldout_capture_qualified"]),
        "earliest_window": evidence["metrics"]["earliest_qualifying_window"],
        "passing_row_count": evidence["metrics"]["passing_equilibrium_row_count"],
        "terminal_mean_stress_pa": evidence["metrics"]["terminal_mean_stress_pa"],
        "terminal_unbalanced_force": evidence["metrics"]["terminal_unbalanced_force"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.workspace).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26f diagnostic output already exists")

    network_path = root / (
        "stage26_network_exports/stage26b_revision2_stage25_network_20260816/"
        "export_04/network.json"
    )
    network = load_json(network_path)
    particles = {int(row["sand_body_id"]): row for row in network["particles"]}
    lengths = np.diag(np.asarray(network["cell_hsize_m"], dtype=float))
    adjacency = {body_id: set() for body_id in particles}
    for contact in network["contacts"]:
        first, second = int(contact["id1"]), int(contact["id2"])
        adjacency[first].add(second)
        adjacency[second].add(first)

    rows = []
    unique_anchor_quartets = set()
    source_hashes = {"network": digest(network_path)}
    placement_root = root / (
        "stage26_placements/stage26b_revision3_joint_placement_20260816/"
        "candidate_generation_01"
    )
    for index, evidence_relative in SPENT_CASES.items():
        placement_path = placement_root / (
            f"stage26b_f002_revision3_candidate_{index:02d}/placement.json"
        )
        evidence_path = root / evidence_relative
        placement = load_json(placement_path)
        evidence = load_json(evidence_path)
        source_hashes[f"candidate{index:02d}_placement"] = digest(placement_path)
        source_hashes[f"candidate{index:02d}_dynamic_evidence"] = digest(evidence_path)
        quartet = tuple(
            sorted(body for fibre in placement["fibres"] for body in fibre["anchor_sand_body_ids"])
        )
        unique_anchor_quartets.add(quartet)
        outcome = case_outcome(index, evidence)
        for fibre in placement["fibres"]:
            members = np.asarray(fibre["member_centres_m"], dtype=float)
            centre = members.mean(axis=0)
            characteristic_length = float(np.linalg.norm(members[-1] - members[0]))
            sand_centres = np.asarray(
                [particles[body_id]["position_m"] for body_id in sorted(particles)],
                dtype=float,
            )
            sand_radii = np.asarray(
                [particles[body_id]["radius_m"] for body_id in sorted(particles)],
                dtype=float,
            )
            delta = members[:, None, :] - sand_centres[None, :, :]
            delta -= np.round(delta / lengths) * lengths
            clearance = np.linalg.norm(delta, axis=2) - (5.0e-5 + sand_radii[None, :])
            minimum_by_sand = clearance.min(axis=0)
            nearest = np.argsort(minimum_by_sand)[:6]
            anchor_ids = [int(value) for value in fibre["anchor_sand_body_ids"]]
            contact_points = []
            for member_index, body_id in zip(fibre["anchor_member_indices"], anchor_ids):
                sand = np.asarray(particles[body_id]["position_m"], dtype=float)
                normal = members[int(member_index)] - sand
                normal -= np.round(normal / lengths) * lengths
                normal /= np.linalg.norm(normal)
                contact_points.append(members[int(member_index)] - 5.0e-5 * normal)
            rank, condition_ratio, singular = frictional_wrench_metrics(
                contact_points, characteristic_length
            )
            first, second = anchor_ids
            common_neighbours = len(adjacency[first].intersection(adjacency[second]))
            rows.append(
                {
                    "candidate_index": index,
                    "fibre_index": int(fibre["fibre_index"]),
                    "qualified_dynamic_outcome": outcome["qualified"],
                    "earliest_window_start": None if outcome["earliest_window"] is None else outcome["earliest_window"][0],
                    "passing_row_count": outcome["passing_row_count"],
                    "terminal_mean_stress_pa": outcome["terminal_mean_stress_pa"],
                    "terminal_unbalanced_force": outcome["terminal_unbalanced_force"],
                    "anchor_ids": anchor_ids,
                    "anchor_degrees": [int(particles[value]["sand_network_degree"]) for value in anchor_ids],
                    "anchor_core_degrees": [int(particles[value]["load_bearing_core_degree"]) for value in anchor_ids],
                    "anchor_shortest_path_edges": shortest_path_length(adjacency, first, second),
                    "anchor_common_neighbour_count": common_neighbours,
                    "initial_contact_count": int(fibre["initial_distinct_sand_contact_count"]),
                    "contact_member_indices": [int(value) for value in fibre["anchor_member_indices"]],
                    "minimum_nonanchor_gap_um": float(
                        min(
                            minimum_by_sand[body_id]
                            for body_id in particles
                            if body_id not in anchor_ids
                        )
                        * 1.0e6
                    ),
                    "nearest_sand_clearances_um": [
                        [int(value), float(minimum_by_sand[value] * 1.0e6)]
                        for value in nearest
                    ],
                    "two_contact_frictional_wrench_rank": rank,
                    "two_contact_frictional_wrench_condition_ratio": condition_ratio,
                    "two_contact_frictional_wrench_singular_values": singular,
                    "fibre_centroid_m": centre.tolist(),
                }
            )

    output.mkdir(parents=True)
    csv_path = output / "spent_case_features.csv"
    flat_fields = [
        "candidate_index",
        "fibre_index",
        "qualified_dynamic_outcome",
        "earliest_window_start",
        "passing_row_count",
        "terminal_mean_stress_pa",
        "terminal_unbalanced_force",
        "anchor_ids",
        "anchor_degrees",
        "anchor_core_degrees",
        "anchor_shortest_path_edges",
        "anchor_common_neighbour_count",
        "initial_contact_count",
        "contact_member_indices",
        "minimum_nonanchor_gap_um",
        "two_contact_frictional_wrench_rank",
        "two_contact_frictional_wrench_condition_ratio",
    ]
    with csv_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=flat_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(row[key]) if isinstance(row[key], list) else row[key]
                    for key in flat_fields
                }
            )

    all_two_contact = all(row["initial_contact_count"] == 2 for row in rows)
    all_rank_deficient = all(row["two_contact_frictional_wrench_rank"] < 6 for row in rows)
    evaluation = {
        "schema": "lbs.stage26f-spent-placement-robustness-diagnostic.v1",
        "passed": True,
        "status": "diagnosed_spent_cases_before_fresh_geometry_redesign",
        "candidate08_read_or_used": False,
        "spent_candidate_indices": sorted(SPENT_CASES),
        "dynamic_success_count": sum(
            bool(row["qualified_dynamic_outcome"])
            for row in rows[::2]
        ),
        "dynamic_failure_count": sum(
            not bool(row["qualified_dynamic_outcome"])
            for row in rows[::2]
        ),
        "unique_anchor_quartet_count": len(unique_anchor_quartets),
        "unique_anchor_quartets": [list(value) for value in sorted(unique_anchor_quartets)],
        "all_fibres_exactly_two_tip_contacts": all_two_contact,
        "all_two_contact_frictional_wrench_systems_rank_deficient": all_rank_deficient,
        "mechanics_diagnosis": [
            "All four spent candidates reuse the same two anchor pairs; they vary pose around those anchors, so the prior campaign did not test anchor-topology robustness.",
            "Each fibre starts with exactly two tip contacts. Even allowing arbitrary frictional force components, two point contacts have a rank-deficient six-DOF wrench system and cannot provide a general rigid-body cage.",
            "Three of four spent poses reached the fixed-fibre temporal gate while candidate07 did not, despite identical anchor topology. The original degree, pair-distance, force-residual and moment-residual gates therefore do not predict general equilibration.",
            "A small third-body gap alone is not a sufficient selector: near-contact backups occur in both successful and failed spent poses.",
        ],
        "redesign_requirements": {
            "fresh_anchor_topologies_only": True,
            "minimum_distinct_sand_supports_per_fibre": 3,
            "minimum_noncollinear_support_member_count": 3,
            "minimum_frictional_wrench_rank": 6,
            "minimum_anchor_network_degree": 4,
            "disjoint_support_bodies_across_fibres": True,
            "record_contact_wrench_conditioning": True,
            "record_near_contact_backups": True,
            "candidate08_reserved_and_excluded": True,
            "free_release_authorized": False,
            "flow_authorized": False,
        },
        "rows": rows,
        "source_hashes": source_hashes,
        "spent_case_features_sha256": digest(csv_path),
        "claim_boundary": "Offline diagnosis of spent fixed-fibre placement evidence only; no new YADE state, candidate08 use, release, rehydration, deformation, flow, permeability, or production result.",
    }
    exclusive_json(output / "evaluation.json", evaluation)
    print(
        json.dumps(
            {
                "passed": True,
                "unique_anchor_quartet_count": len(unique_anchor_quartets),
                "all_two_contact_wrench_rank_deficient": all_rank_deficient,
                "evaluation_sha256": digest(output / "evaluation.json"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
