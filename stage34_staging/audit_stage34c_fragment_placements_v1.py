#!/usr/bin/env python3
"""Independently audit Stage34C nested CPD4 fragment-anchor selection."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
PLACEMENT_DIR = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_01"
PLACEMENT = PLACEMENT_DIR / "placement_manifest.json"
PLACEMENT_COMPLETION = PLACEMENT_DIR / "completion.json"
DESIGN = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/design_01/design_manifest.json"
DESIGN_AUDIT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/design_audit_01/design_audit.json"
STAGE31B = ROOT / "stage31_designs/stage31b_nested_concentration_replication_20260826/design_01/design_manifest.json"
PATHS = {
    "n216_s1": ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/path_search_01/path_candidates.json",
    "n216_s2": ROOT / "stage31_designs/stage31b_pore_network_exports_20260826/path_search_n216_s2_01/path_candidates.json",
}
OUTPUT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_01"
PACKINGS = ("n216_s1", "n216_s2")
BLOCKS = ("A", "B")
RADIUS_M = 50.0e-6
ABS_TOL = 1.0e-12


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_binding(binding: dict) -> bool:
    path = Path(binding["path"])
    return path.is_file() and sha(path) == binding["sha256"]


def segment_distance(p1: np.ndarray, q1: np.ndarray, p2: np.ndarray, q2: np.ndarray) -> float:
    # Independent closest-points calculation for two finite line segments.
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e = float(d1 @ d1), float(d2 @ d2)
    f = float(d2 @ r)
    if a <= 1.0e-30 and e <= 1.0e-30:
        return float(np.linalg.norm(p1 - p2))
    if a <= 1.0e-30:
        s, t = 0.0, min(max(f / e, 0.0), 1.0)
    else:
        c = float(d1 @ r)
        if e <= 1.0e-30:
            t, s = 0.0, min(max(-c / a, 0.0), 1.0)
        else:
            b = float(d1 @ d2)
            denominator = a * e - b * b
            s = min(max((b * f - c * e) / denominator, 0.0), 1.0) if denominator > 1.0e-30 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, min(max(-c / a, 0.0), 1.0)
            elif t > 1.0:
                t, s = 1.0, min(max((b - c) / a, 0.0), 1.0)
    return float(np.linalg.norm((p1 + s * d1) - (p2 + t * d2)))


def endpoints(row: dict, length: float) -> tuple[np.ndarray, np.ndarray]:
    rear, tip = np.asarray(row["rear_m"], dtype=float), np.asarray(row["tip_m"], dtype=float)
    direction = tip - rear
    direction /= np.linalg.norm(direction)
    centre = 0.5 * (rear + tip)
    return centre - 0.5 * length * direction, centre + 0.5 * length * direction


def periodic_distance(first: dict, second: dict, length: float, cell: np.ndarray) -> float:
    p1, q1 = endpoints(first, length)
    p2, q2 = endpoints(second, length)
    return min(
        segment_distance(p1, q1, p2 + np.asarray(shift) * cell, q2 + np.asarray(shift) * cell)
        for shift in itertools.product((-1, 0, 1), repeat=3)
    )


def close(a: float, b: float, tolerance: float = ABS_TOL) -> bool:
    return math.isclose(float(a), float(b), rel_tol=1.0e-10, abs_tol=tolerance)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    placement = load(PLACEMENT)
    completion = load(PLACEMENT_COMPLETION)
    design = load(DESIGN)
    design_audit = load(DESIGN_AUDIT)
    stage31b = load(STAGE31B)
    contexts = {(row["packing_id"], row["placement_block"]): row for row in design["contexts"]}

    checks: dict[str, bool] = {}
    checks["placement_completion_passed"] = completion.get("passed") is True
    checks["completion_binds_manifest"] = completion.get("placement_manifest_sha256") == sha(PLACEMENT)
    checks["placement_schema_exact"] = placement.get("schema") == "lbs.stage34c-cpd4-fragment-placement.v1"
    checks["design_audit_passed"] = design_audit.get("passed") is True
    checks["all_source_bindings_verified"] = all(check_binding(binding) for binding in placement["source_bindings"].values())
    checks["expected_direct_source_hashes"] = (
        placement["source_bindings"]["stage34c_design"]["sha256"] == sha(DESIGN)
        and placement["source_bindings"]["stage34c_design_audit"]["sha256"] == sha(DESIGN_AUDIT)
        and placement["source_bindings"]["stage31b_seed_design"]["sha256"] == sha(STAGE31B)
        and all(placement["source_bindings"][f"{packing}_path_catalogue"]["sha256"] == sha(PATHS[packing]) for packing in PACKINGS)
    )
    checks["exact_packings"] = set(placement["packings"]) == set(PACKINGS)
    checks["placement_claim_boundary_unchanged"] = placement.get("claim_boundary") == design.get("claim_boundary")
    checks["flow_execution_not_authorized"] = placement.get("authority", {}).get("gpu_flow_execution") is False
    checks["rasterization_not_authorized_before_audit"] = placement.get("authority", {}).get("geometry_rasterization") is False

    catalogue_match = True
    seed_match = True
    ranks_exact = True
    unique_faces = True
    blocks_disjoint = True
    eligibility_exact = True
    candidate_counts_exact = True
    spacing_definition_exact = True
    active_sets_exact = True
    piece_lengths_exact = True
    distance_metrics_exact = True
    spacing_all_pass = True
    all_minimum_gaps: list[float] = []

    for packing in PACKINGS:
        payload = load(PATHS[packing])
        cell = np.asarray(payload["cell_dimensions_m"], dtype=float)
        eligible = [
            row for row in payload["candidates"]
            if float(row["throat_to_fibre_radius_ratio"]) >= 1.25
            and float(row["minimum_sampled_swept_clearance_m"]) >= 2.0e-6
        ]
        by_face = {int(row["face_index"]): row for row in eligible}
        observed = placement["packings"][packing]
        spacing = float(np.prod(cell) ** (1.0 / 3.0)) / 186.0
        threshold = 2.0 * RADIUS_M + spacing
        candidate_counts_exact &= int(observed["eligible_candidate_count"]) == len(eligible)
        spacing_definition_exact &= (
            np.allclose(np.asarray(observed["cell_dimensions_m"], dtype=float), cell, rtol=0.0, atol=ABS_TOL)
            and close(observed["cpd4_spacing_m"], spacing)
            and close(observed["required_centreline_distance_m"], threshold)
        )
        faces_by_block: dict[str, set[int]] = {}
        for block in BLOCKS:
            rows = observed["blocks"][block]["anchors"]
            faces = [int(row["face_index"]) for row in rows]
            faces_by_block[block] = set(faces)
            ranks_exact &= (
                len(rows) == 12
                and sorted((int(row["child_rank"]), int(row["parent_rank"])) for row in rows)
                == [(child, parent) for child in (1, 2, 3) for parent in (1, 2, 3, 4)]
            )
            unique_faces &= len(faces) == len(set(faces))
            expected_seed_faces = [int(row["face_index"]) for row in stage31b["blocks"][packing][block]]
            observed_seed_faces = [int(row["face_index"]) for row in rows if int(row["child_rank"]) == 1]
            seed_match &= observed_seed_faces == expected_seed_faces
            for row in rows:
                face = int(row["face_index"])
                eligibility_exact &= face in by_face
                if face not in by_face:
                    catalogue_match = False
                    continue
                source = by_face[face]
                catalogue_match &= (
                    row["face_body_ids"] == source["face_body_ids"]
                    and np.allclose(row["rear_m"], source["rear_m"], rtol=0.0, atol=ABS_TOL)
                    and np.allclose(row["tip_m"], source["tip_m"], rtol=0.0, atol=ABS_TOL)
                    and np.allclose(row["pull_direction"], source["pull_direction"], rtol=0.0, atol=ABS_TOL)
                    and close(row["throat_to_fibre_radius_ratio"], source["throat_to_fibre_radius_ratio"])
                    and close(row["minimum_sampled_swept_clearance_m"], source["minimum_sampled_swept_clearance_m"])
                )
            context = contexts[(packing, block)]
            parent_length = float(context["mean_parent_contour_length_m"])
            for fragments in (2, 3):
                level = observed["blocks"][block]["level_metrics"][f"frag{fragments}"]
                expected_faces = [int(row["face_index"]) for row in rows if int(row["child_rank"]) <= fragments]
                expected_length = (parent_length - 4.0 * RADIUS_M * (fragments - 1) / 3.0) / fragments
                active_sets_exact &= (
                    int(level["active_anchor_count"]) == 4 * fragments
                    and [int(face) for face in level["face_indices"]] == expected_faces
                )
                piece_lengths_exact &= close(level["piece_length_m"], expected_length)
                active_rows = [by_face[face] for face in expected_faces]
                independently_computed = min(
                    periodic_distance(first, second, expected_length, cell)
                    for first, second in itertools.combinations(active_rows, 2)
                )
                gap = independently_computed - 2.0 * RADIUS_M
                all_minimum_gaps.append(gap)
                distance_metrics_exact &= (
                    close(level["minimum_periodic_centreline_distance_m"], independently_computed)
                    and close(level["minimum_surface_gap_m"], gap)
                    and close(level["minimum_required_surface_gap_m"], spacing)
                )
                independent_pass = gap + ABS_TOL >= spacing
                spacing_all_pass &= independent_pass and level["pairwise_spacing_passed"] is True
        blocks_disjoint &= not (faces_by_block["A"] & faces_by_block["B"])
        blocks_disjoint &= observed["cross_block_shared_face_indices"] == []

    checks.update({
        "eligible_candidate_counts_reproduced": candidate_counts_exact,
        "spacing_definition_reproduced": spacing_definition_exact,
        "exact_child_parent_rank_grid": ranks_exact,
        "unique_faces_within_blocks": unique_faces,
        "blocks_use_disjoint_faces": blocks_disjoint,
        "accepted_seed_faces_exact": seed_match,
        "all_anchors_are_eligible": eligibility_exact,
        "all_anchor_fields_match_catalogues": catalogue_match,
        "nested_active_sets_exact": active_sets_exact,
        "equal_volume_piece_lengths_exact": piece_lengths_exact,
        "periodic_distance_metrics_reproduced": distance_metrics_exact,
        "all_pairwise_spacing_independently_passed": spacing_all_pass,
    })

    search_text = Path(placement["source_bindings"]["searcher"]["path"]).read_text(encoding="utf-8").lower()
    forbidden_flow_tokens = ("paired_permeability_ratio", "conductance_proxy_lu", "pressure_drop", "darcy", "flow_rate")
    checks["selection_code_blind_to_hydraulic_results"] = not any(token in search_text for token in forbidden_flow_tokens)
    checks["selection_method_declares_hydraulic_blinding"] = "blind to hydraulic outcomes" in placement.get("method", "").lower()

    passed = all(checks.values())
    status = "passed_placement_audit_geometry_rasterization_authorized" if passed else "failed_placement_audit_fail_closed"
    authority = {
        "geometry_rasterization": passed,
        "cpd4_cpd6_geometry_sentinel": passed,
        "gpu_flow_execution": False,
        "mechanics_or_coupling": False,
    }
    audit = {
        "schema": "lbs.stage34c-cpd4-fragment-placement-audit.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": status,
        "checks": checks,
        "metrics": {
            "packing_count": len(placement["packings"]),
            "block_count": sum(len(row["blocks"]) for row in placement["packings"].values()),
            "anchor_count": sum(len(block["anchors"]) for row in placement["packings"].values() for block in row["blocks"].values()),
            "minimum_independent_surface_gap_m": min(all_minimum_gaps),
        },
        "source_bindings": {
            "placement_manifest": {"path": str(PLACEMENT.resolve()), "sha256": sha(PLACEMENT)},
            "placement_completion": {"path": str(PLACEMENT_COMPLETION.resolve()), "sha256": sha(PLACEMENT_COMPLETION)},
            "stage34c_design": {"path": str(DESIGN.resolve()), "sha256": sha(DESIGN)},
            "stage34c_design_audit": {"path": str(DESIGN_AUDIT.resolve()), "sha256": sha(DESIGN_AUDIT)},
            "stage31b_seed_design": {"path": str(STAGE31B.resolve()), "sha256": sha(STAGE31B)},
            "auditor": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
        },
        "authority": authority,
        "claim_boundary": placement["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    audit_path = OUTPUT / "placement_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion_out = {
        "schema": "lbs.stage34c-cpd4-fragment-placement-audit.v1.completion",
        "passed": passed,
        "status": status,
        "placement_audit_sha256": sha(audit_path),
        "authority": authority,
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion_out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "status": status, "failed_checks": [name for name, ok in checks.items() if not ok], "metrics": audit["metrics"]}, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
