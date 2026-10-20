#!/usr/bin/env python3
"""Build the immutable Stage34C CPD4-first fragmentation geometry design."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUTPUT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/design_01"
CONTRACT = ROOT / "stage34_staging/STAGE34C_CPD4_FIRST_FRAGMENTATION_GEOMETRY_CONTRACT.md"
RESOLUTION_DECISION = ROOT / "stage34_evaluations/stage34b_literature_informed_length_screen_20260902/resolution_decision_01/completion.json"
STAGE31F_CONFIG = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/resolved_config.json"
STAGE31F_EVAL = ROOT / "stage31_evaluations/stage31f_selected_replicated_cpd4_20260827/gpu_evaluation_02/evaluation.json"
STAGE31C_RESULT = ROOT / "stage31_runs/stage31c_replicated_nested_mechanics_20260826/mechanics_01/result.json"
PATHS = {
    "n216_s1": ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/path_search_01/path_candidates.json",
    "n216_s2": ROOT / "stage31_designs/stage31b_pore_network_exports_20260826/path_search_n216_s2_01/path_candidates.json",
}
PACKINGS = ("n216_s1", "n216_s2")
BLOCKS = ("A", "B")
FRAGMENT_LEVELS = (1, 2, 3)
RADIUS_M = 50.0e-6


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable design: {OUTPUT}")
    required = [CONTRACT, RESOLUTION_DECISION, STAGE31F_CONFIG, STAGE31F_EVAL, STAGE31C_RESULT, *PATHS.values()]
    if any(not path.is_file() for path in required):
        raise RuntimeError("required Stage34C input is missing")
    decision, config, evaluation, mechanics_index = map(load, [RESOLUTION_DECISION, STAGE31F_CONFIG, STAGE31F_EVAL, STAGE31C_RESULT])
    if not (decision.get("passed") is True and evaluation.get("passed") is True and mechanics_index.get("passed") is True):
        raise RuntimeError("upstream decision or CPD4 evidence is not passed")

    paired = {row["case_id"]: row for row in evaluation["paired_results"]}
    mechanics = {}
    mechanics_bindings = {}
    for entry in mechanics_index["case_records"]:
        path = STAGE31C_RESULT.parent / entry["path"]
        if sha(path) != entry["sha256"]:
            raise RuntimeError(f"mechanics hash mismatch: {path}")
        row = load(path)
        if row["packing_id"] in PACKINGS:
            mechanics[(row["packing_id"], row["placement_block"])] = row
            mechanics_bindings[row["case_id"]] = bind(path)

    candidate_summary = {}
    for packing, path in PATHS.items():
        payload = load(path)
        candidates = payload["candidates"]
        eligible = [
            row for row in candidates
            if float(row["throat_to_fibre_radius_ratio"]) >= 1.25
            and float(row["minimum_sampled_swept_clearance_m"]) >= 2.0e-6
        ]
        candidate_summary[packing] = {
            "source_candidate_count": len(candidates),
            "eligible_long_parent_scale_candidate_count": len(eligible),
            "minimum_required_per_fragmentation_block": 12,
            "count_feasible_before_pairwise_selection": len(eligible) >= 24,
        }

    cases, contexts, order_tokens = [], [], []
    for packing in PACKINGS:
        for block in BLOCKS:
            source_id = f"s31b_{packing}_{block}_f004_open"
            if source_id not in paired or source_id not in config["geometry"]["artifacts"]:
                raise RuntimeError(f"missing accepted CPD4 intact source: {source_id}")
            source = paired[source_id]
            artifact = config["geometry"]["artifacts"][source_id]
            mech = mechanics[(packing, block)]
            parent_lengths = []
            for fibre in mech["terminal_fibres"]:
                points = np.asarray(fibre["terminal_node_positions_m"], dtype=float)
                if points.shape != (37, 3):
                    raise RuntimeError(f"invalid parent polyline: {packing}/{block}")
                parent_lengths.append(length(points))
            if len(parent_lengths) != 4:
                raise RuntimeError(f"four parent paths required: {packing}/{block}")
            mean_parent = float(np.mean(parent_lengths))
            contexts.append({
                "packing_id": packing,
                "placement_block": block,
                "source_intact_case_id": source_id,
                "source_intact_record_sha256": source["record_sha256"],
                "source_intact_geometry": artifact["geometry"],
                "source_intact_geometry_sha256": artifact["geometry_sha256"],
                "source_intact_material_vtk_sha256": artifact["material_vtk_sha256"],
                "matched_clean_conductance_proxy_lu": source["conductance_proxy_lu"] / source["paired_permeability_ratio"],
                "intact_cpd4_paired_permeability_ratio": source["paired_permeability_ratio"],
                "parent_contour_lengths_m": parent_lengths,
                "mean_parent_contour_length_m": mean_parent,
            })
            for fragments in FRAGMENT_LEVELS:
                endpoint_corrected = (mean_parent - 4.0 * RADIUS_M * (fragments - 1) / 3.0) / fragments
                case_id = f"s34c_{packing}_{block}_p4_frag{fragments}_cpd4"
                role = "reused_stage31f_intact_cpd4" if fragments == 1 else "new_cpd4_fragment_geometry"
                row = {
                    "case_id": case_id,
                    "packing_id": packing,
                    "placement_block": block,
                    "fragments_per_parent": fragments,
                    "total_fragment_count": 4 * fragments,
                    "mean_parent_contour_length_m": mean_parent,
                    "initial_equal_volume_piece_centreline_length_m": endpoint_corrected,
                    "initial_overall_piece_length_m": endpoint_corrected + 2.0 * RADIUS_M,
                    "initial_piece_aspect_ratio": (endpoint_corrected + 2.0 * RADIUS_M) / (2.0 * RADIUS_M),
                    "fibre_radius_m": RADIUS_M,
                    "length_multiplier_lower": 0.90,
                    "length_multiplier_upper": 1.10,
                    "target_solver_pet_volume": "source_intact_fibre_only_voxel_count",
                    "maximum_solver_pet_volume_error": "max(1 voxel, 0.5 percent)",
                    "source_intact_case_id": source_id,
                    "source_intact_record_sha256": source["record_sha256"],
                    "source_intact_geometry_sha256": artifact["geometry_sha256"],
                    "reused_paired_permeability_ratio": source["paired_permeability_ratio"] if fragments == 1 else None,
                    "role": role,
                    "new_randomized_run_order": None,
                }
                cases.append(row)
                if fragments > 1:
                    order_tokens.append((hashlib.sha256(f"{case_id}|stage34c-v1".encode()).hexdigest(), case_id))
    order_tokens.sort()
    rank = {case_id: i for i, (_, case_id) in enumerate(order_tokens, start=1)}
    for row in cases:
        row["new_randomized_run_order"] = rank.get(row["case_id"])

    manifest = {
        "schema": "lbs.stage34c-cpd4-first-fragmentation-geometry.v1.design",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "cpd4_first_design_complete_placement_search_not_executed",
        "research_question": "At fixed solver-resolved PET volume, how does idealized intact/split-2/split-3 fragmentation state affect K/K0 across two packings and two placement blocks?",
        "claim_boundary": "Fixed-solid fragmentation-state sensitivity only; not a pure length coefficient, degradation law, experimental validation or mobile-particle process.",
        "design": {
            "resolution": [186, 186, 186],
            "packing_count": 2,
            "placement_blocks_per_packing": 2,
            "matched_context_count": 4,
            "fragmentation_levels": [1, 2, 3],
            "condition_row_count": 12,
            "reused_intact_cpd4_count": 4,
            "maximum_new_cpd4_case_count": 8,
            "new_case_order_randomized_before_geometry": True,
        },
        "candidate_summary": candidate_summary,
        "placement_algorithm": {
            "hydraulic_results_used_for_selection": False,
            "seed_with_four_accepted_parent_faces": True,
            "nested_anchor_counts": {"frag2": 8, "frag3": 12},
            "ranking_terms": ["face_and_grain_disjointness", "periodic_centreline_separation", "throat_ratio_similarity", "orientation_mismatch", "parent_midpoint_displacement"],
            "rigid_piece_transform_only": True,
            "minimum_interfragment_gap": "one CPD4 fluid voxel",
            "pair_mask_overlap_allowed": False,
            "record_all_transforms": True,
        },
        "volume_control": {
            "analytical_initialization": "equal-volume capsule endpoint correction",
            "solver_primary": "match intact context fibre-only voxel count outside sand",
            "tolerance": "max(1 voxel, 0.5 percent)",
            "uniform_piece_length_multiplier_bounds": [0.90, 1.10],
            "radius_retuning": False,
            "post_flow_retuning": False,
        },
        "geometry_only_refinement_sentinel": {
            "resolutions": [[186, 186, 186], [279, 279, 279]],
            "maximum_volume_ratio_shift": 0.02,
            "require_orientation_order_stability": True,
            "require_no_topology_reversal": True,
            "flow_at_279_cubed_authorized": False,
        },
        "analysis": {
            "primary_observable": "paired_permeability_ratio_K_over_K0",
            "paired_contrasts": ["frag2_minus_frag1", "frag3_minus_frag1", "frag3_minus_frag2"],
            "practical_selection_threshold_absolute_ratio": 0.005,
            "minimum_concordant_context_signs": 3,
            "monotonicity_imposed": False,
            "maximum_selected_finer_grid_fragment_cases": 2,
            "concentration_interaction_authorized": False,
        },
        "contexts": contexts,
        "cases": cases,
        "source_bindings": {
            "contract": bind(CONTRACT),
            "stage34b_resolution_decision": bind(RESOLUTION_DECISION),
            "stage31f_config": bind(STAGE31F_CONFIG),
            "stage31f_evaluation": bind(STAGE31F_EVAL),
            "stage31c_mechanics_index": bind(STAGE31C_RESULT),
            "n216_s1_path_catalogue": bind(PATHS["n216_s1"]),
            "n216_s2_path_catalogue": bind(PATHS["n216_s2"]),
            "builder": bind(Path(__file__).resolve()),
            "mechanics_case_records": mechanics_bindings,
        },
        "authority": {
            "independent_design_audit": True,
            "placement_search": False,
            "geometry_rasterization": False,
            "gpu_flow_execution": False,
            "cpd6_flow_execution": False,
            "physical_experiment": False,
            "chemical_degradation_claim": False,
            "absolute_permeability_validation_claim": False,
            "migration_clogging_deformation_or_coupling": False,
        },
    }
    OUTPUT.mkdir(parents=True)
    manifest_path = OUTPUT / "design_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    matrix_path = OUTPUT / "design_matrix.csv"
    fields = [
        "case_id", "packing_id", "placement_block", "fragments_per_parent", "total_fragment_count",
        "initial_equal_volume_piece_centreline_length_m", "initial_piece_aspect_ratio", "role",
        "new_randomized_run_order", "source_intact_case_id", "source_intact_record_sha256",
        "source_intact_geometry_sha256",
    ]
    with matrix_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in cases)
    completion = {
        "schema": "lbs.stage34c-cpd4-first-fragmentation-geometry.v1.design-completion",
        "status": "design_complete_independent_audit_required",
        "passed": len(cases) == 12 and len(order_tokens) == 8 and all(row["count_feasible_before_pairwise_selection"] for row in candidate_summary.values()),
        "condition_row_count": len(cases),
        "new_cpd4_case_count": len(order_tokens),
        "design_manifest_sha256": sha(manifest_path),
        "design_matrix_sha256": sha(matrix_path),
        "authority": manifest["authority"],
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(completion, sort_keys=True))
    if not completion["passed"]:
        raise SystemExit(7)


if __name__ == "__main__":
    main()
