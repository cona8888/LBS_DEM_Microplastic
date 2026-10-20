#!/usr/bin/env python3
"""Build the immutable Stage34B paired fibre-length CPD2 screen design."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUTPUT = ROOT / "stage34_designs/stage34b_literature_informed_length_screen_20260902/design_01"
CONTRACT = ROOT / "stage34_staging/STAGE34B_LENGTH_SCREEN_CONTRACT.md"
STAGE34A = ROOT / "stage34_literature/stage34a_literature_digitization_20260902/release_01/completion.json"
STAGE31B = ROOT / "stage31_designs/stage31b_nested_concentration_replication_20260826/design_01/design_manifest.json"
STAGE31C_RESULT = ROOT / "stage31_runs/stage31c_replicated_nested_mechanics_20260826/mechanics_01/result.json"
STAGE31C_EVAL = ROOT / "stage31_evaluations/stage31c_replicated_nested_mechanics_20260826/mechanics_evaluation_01/evaluation.json"
STAGE31E_EVAL = ROOT / "stage31_evaluations/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_evaluation_01/evaluation.json"
STAGE31F_EVAL = ROOT / "stage31_evaluations/stage31f_selected_replicated_cpd4_20260827/gpu_evaluation_02/evaluation.json"

PACKINGS = ("n216_s1", "n216_s2", "n216_s3")
BLOCKS = ("A", "B")
FRAGMENTS_PER_PARENT = (1, 2, 3)
PARENT_COUNT = 4
RADIUS_M = 50.0e-6
NOMINAL_PARENT_CENTRELINE_M = 0.9e-3
LEGACY_DRY_MASS_PERCENT = {
    "n216_s1": 0.01747047710686622,
    "n216_s2": 0.017969051622828056,
    "n216_s3": 0.01768501813425945,
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def contour_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable design: {OUTPUT}")
    required = [CONTRACT, STAGE34A, STAGE31B, STAGE31C_RESULT, STAGE31C_EVAL, STAGE31E_EVAL, STAGE31F_EVAL]
    if any(not path.is_file() for path in required):
        raise RuntimeError("required source is missing")

    stage34a = load(STAGE34A)
    stage31b = load(STAGE31B)
    stage31c_result = load(STAGE31C_RESULT)
    stage31c_eval = load(STAGE31C_EVAL)
    stage31e = load(STAGE31E_EVAL)
    stage31f = load(STAGE31F_EVAL)
    if not (
        stage34a.get("status") == "complete"
        and stage31c_result.get("passed") is True
        and stage31c_eval.get("passed") is True
        and stage31e.get("passed") is True
        and stage31f.get("passed") is True
    ):
        raise RuntimeError("an upstream acceptance gate is not passed")

    stage31e_rows = {row["case_id"]: row for row in stage31e["rows"]}
    mechanics_records = {}
    mechanics_bindings = {}
    for entry in stage31c_result["case_records"]:
        path = STAGE31C_RESULT.parent / entry["path"]
        if sha(path) != entry["sha256"]:
            raise RuntimeError(f"mechanics record hash mismatch: {path}")
        row = load(path)
        key = (row["packing_id"], row["placement_block"])
        mechanics_records[key] = row
        mechanics_bindings[row["case_id"]] = bind(path)
    if set(mechanics_records) != set((p, b) for p in PACKINGS for b in BLOCKS):
        raise RuntimeError("six accepted packing/block mechanics contexts are required")

    cases = []
    new_order_tokens = []
    contexts = []
    for packing in PACKINGS:
        clean_id = f"s31b_{packing}_clean"
        clean = stage31e_rows[clean_id]
        for block in BLOCKS:
            intact_id = f"s31b_{packing}_{block}_f004_open"
            intact = stage31e_rows[intact_id]
            mechanics = mechanics_records[(packing, block)]
            terminal = mechanics["terminal_fibres"]
            if len(terminal) != PARENT_COUNT:
                raise RuntimeError(f"expected four terminal parent paths: {packing}/{block}")
            parent_lengths = []
            for fibre in terminal:
                points = np.asarray(fibre["terminal_node_positions_m"], dtype=float)
                if points.shape != (37, 3) or not np.isfinite(points).all():
                    raise RuntimeError(f"invalid terminal centreline: {packing}/{block}")
                parent_lengths.append(contour_length(points))
            total_parent_length = float(sum(parent_lengths))
            contexts.append(
                {
                    "packing_id": packing,
                    "placement_block": block,
                    "clean_case_id": clean_id,
                    "clean_record_sha256": clean["record_sha256"],
                    "intact_case_id": intact_id,
                    "intact_record_sha256": intact["record_sha256"],
                    "parent_contour_lengths_m": parent_lengths,
                    "total_parent_contour_length_m": total_parent_length,
                    "intact_paired_permeability_ratio": intact["paired_permeability_ratio"],
                }
            )
            for fragments in FRAGMENTS_PER_PARENT:
                total_fragments = PARENT_COUNT * fragments
                case_id = f"s34b_{packing}_{block}_p4_frag{fragments}"
                role = "reused_stage31e_intact" if fragments == 1 else "new_cpd2_fragment_solve"
                target_mean = total_parent_length / total_fragments
                case = {
                    "case_id": case_id,
                    "packing_id": packing,
                    "placement_block": block,
                    "parent_count_equivalent": PARENT_COUNT,
                    "fragments_per_parent": fragments,
                    "total_fragment_count": total_fragments,
                    "target_mean_centreline_length_m": target_mean,
                    "nominal_mean_centreline_length_m": NOMINAL_PARENT_CENTRELINE_M / fragments,
                    "target_aspect_ratio_overall_length_over_diameter": (NOMINAL_PARENT_CENTRELINE_M / fragments + 2.0 * RADIUS_M) / (2.0 * RADIUS_M),
                    "fibre_radius_m": RADIUS_M,
                    "total_parent_contour_length_m": total_parent_length,
                    "legacy_dry_mass_percent": float(intact["achieved_dry_mass_percent"]),
                    "role": role,
                    "matched_clean_case_id": clean_id,
                    "matched_clean_record_sha256": clean["record_sha256"],
                    "source_mechanics_case_id": mechanics["case_id"],
                    "source_intact_case_id": intact_id,
                    "source_intact_record_sha256": intact["record_sha256"],
                    "reused_paired_permeability_ratio": intact["paired_permeability_ratio"] if fragments == 1 else None,
                    "new_randomized_run_order": None,
                }
                cases.append(case)
                if fragments > 1:
                    token = hashlib.sha256(f"{case_id}|stage34b-v1".encode()).hexdigest()
                    new_order_tokens.append((token, case_id))

    new_order_tokens.sort()
    rank = {case_id: index for index, (_, case_id) in enumerate(new_order_tokens, start=1)}
    for case in cases:
        case["new_randomized_run_order"] = rank.get(case["case_id"])

    manifest = {
        "schema": "lbs.stage34b-literature-informed-length-screen.v1.design",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "design_complete_geometry_and_execution_not_authorized",
        "research_question": "At a fixed four-parent PET dose, how does idealized fragmentation length change steady K/K0 across matched packing and pore-placement contexts?",
        "claim_boundary": "Computational fixed-solid morphology sensitivity only; fibre length is not chemical degradation and no experimental validation, universal law, mobile-particle process or coupling is claimed.",
        "design": {
            "packing_count": 3,
            "placement_blocks_per_packing": 2,
            "matched_context_count": 6,
            "fragmentation_levels": [1, 2, 3],
            "condition_row_count": 18,
            "reused_intact_case_count": 6,
            "new_cpd2_case_count": 12,
            "reused_clean_control_count": 3,
            "sequential_concentration_interaction": "not authorized unless a healthy length contrast meets the frozen selection rule",
        },
        "physical_constants": {
            "fibre_radius_m": RADIUS_M,
            "nominal_parent_centreline_length_m": NOMINAL_PARENT_CENTRELINE_M,
            "fibre_diameter_m": 2.0 * RADIUS_M,
            "parent_count_equivalent": PARENT_COUNT,
        },
        "geometry_rules": {
            "fragmentation_method": "divide each exact accepted terminal parent polyline by arclength; preserve parent path envelope and tangent distribution",
            "mass_control": "match each context's intact CPD2 fibre-only voxel count; repeated capsule end-cap inflation is prohibited",
            "maximum_fibre_only_voxel_deviation": "max(1 voxel, 0.5 percent)",
            "minimum_interfragment_gap": "at least one CPD2 fluid voxel",
            "radius_retuning": False,
            "post_hydraulic_geometry_retuning": False,
        },
        "analysis": {
            "primary_observable": "paired_permeability_ratio_K_over_K0",
            "paired_contrasts": ["frag2_minus_frag1", "frag3_minus_frag1", "frag3_minus_frag2"],
            "practical_selection_threshold_absolute_ratio": 0.005,
            "minimum_concordant_context_signs": 4,
            "monotonicity_imposed": False,
            "report_packing_and_placement_variability_separately": True,
            "maximum_new_cpd4_cases_after_selection": 4,
            "maximum_absolute_selected_cpd2_to_cpd4_ratio_shift": 0.002,
        },
        "contexts": contexts,
        "cases": cases,
        "source_bindings": {
            "contract": bind(CONTRACT),
            "stage34a_literature_completion": bind(STAGE34A),
            "stage31b_design": bind(STAGE31B),
            "stage31c_mechanics_result": bind(STAGE31C_RESULT),
            "stage31c_mechanics_evaluation": bind(STAGE31C_EVAL),
            "stage31e_cpd2_evaluation": bind(STAGE31E_EVAL),
            "stage31f_cpd4_evaluation": bind(STAGE31F_EVAL),
            "builder": bind(Path(__file__).resolve()),
            "mechanics_case_records": mechanics_bindings,
        },
        "authority": {
            "independent_design_audit": True,
            "geometry_construction": False,
            "gpu_execution": False,
            "cpd4_execution": False,
            "physical_experiment": False,
            "chemical_degradation_claim": False,
            "absolute_permeability_validation_claim": False,
            "mobile_sand_or_fibre": False,
            "migration_clogging_deformation_or_coupling": False,
        },
    }

    OUTPUT.mkdir(parents=True)
    manifest_path = OUTPUT / "design_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (OUTPUT / "design_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "case_id", "packing_id", "placement_block", "fragments_per_parent", "total_fragment_count",
            "target_mean_centreline_length_m", "target_aspect_ratio_overall_length_over_diameter",
            "legacy_dry_mass_percent", "role", "new_randomized_run_order", "matched_clean_case_id",
            "source_intact_case_id",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: case[field] for field in fields} for case in cases)
    completion = {
        "schema": "lbs.stage34b-literature-informed-length-screen.v1.design-completion",
        "passed": len(cases) == 18 and len(new_order_tokens) == 12 and len(contexts) == 6,
        "status": "design_complete_independent_audit_required",
        "design_manifest_sha256": sha(manifest_path),
        "design_matrix_sha256": sha(OUTPUT / "design_matrix.csv"),
        "case_count": len(cases),
        "new_cpd2_case_count": len(new_order_tokens),
        "authority": manifest["authority"],
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(completion, sort_keys=True))
    if not completion["passed"]:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
