#!/usr/bin/env python3
"""Verify equal-volume capsule fragmentation before Stage34 application geometry."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(ROOT / "stage27_staging"))
import build_stage27a_mechanics_hydraulic_masks_v1 as geometry_api  # noqa: E402

OUTPUT = ROOT / "stage34_evaluations/stage34b_literature_informed_length_screen_20260902/primitive_geometry_01"
DESIGN = ROOT / "stage34_designs/stage34b_literature_informed_length_screen_20260902/design_01/design_manifest.json"
DESIGN_AUDIT = ROOT / "stage34_evaluations/stage34b_literature_informed_length_screen_20260902/design_audit_01/design_audit.json"
GEOMETRY_API = ROOT / "stage27_staging/build_stage27a_mechanics_hydraulic_masks_v1.py"

RADIUS_M = 50.0e-6
PARENT_CENTRELINE_M = 0.9e-3
CELL_M = 4.65e-3
RESOLUTIONS = (93, 186)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capsule_volume(radius: float, centreline_length: float) -> float:
    return math.pi * radius**2 * centreline_length + 4.0 * math.pi * radius**3 / 3.0


def equal_volume_piece_length(fragment_count: int) -> float:
    # n*(pi*r^2*L_n + 4*pi*r^3/3) = parent capsule volume.
    return (PARENT_CENTRELINE_M - 4.0 * RADIUS_M * (fragment_count - 1) / 3.0) / fragment_count


def line_points(center: np.ndarray, direction: np.ndarray, length: float) -> np.ndarray:
    direction = direction / np.linalg.norm(direction)
    return np.stack((center - 0.5 * length * direction, center + 0.5 * length * direction))


def voxelize(fragment_count: int, piece_length: float, resolution: int, direction: np.ndarray, shift: np.ndarray) -> int:
    mask = np.zeros((resolution, resolution, resolution), dtype=bool)
    base = np.array([0.5, 0.5, 0.5]) * CELL_M + shift
    # Separate fragments perpendicular to their axis; this test isolates volume
    # and connectedness rather than application placement.
    normal = np.cross(direction, np.array([0.0, 0.0, 1.0]))
    if np.linalg.norm(normal) < 0.2:
        normal = np.cross(direction, np.array([0.0, 1.0, 0.0]))
    normal = normal / np.linalg.norm(normal)
    offsets = (np.arange(fragment_count) - 0.5 * (fragment_count - 1)) * 4.0 * RADIUS_M
    for offset in offsets:
        points = line_points(base + offset * normal, direction, piece_length)
        geometry_api.mark_capsule(mask, points, RADIUS_M, CELL_M)
    return int(np.count_nonzero(mask))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable primitive test: {OUTPUT}")
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    audit = json.loads(DESIGN_AUDIT.read_text(encoding="utf-8"))
    if audit.get("passed") is not True or design["authority"]["gpu_execution"] is not False:
        raise RuntimeError("Stage34B design audit or authority is invalid")

    directions = [
        np.array([1.0, 0.0, 0.0]),
        np.array([1.0, 1.0, 0.5]),
        np.array([0.4, 1.0, 0.7]),
    ]
    shifts = [
        np.array([0.00, 0.00, 0.00]),
        np.array([0.17, 0.31, 0.23]) * (CELL_M / 186.0),
        np.array([0.39, 0.11, 0.43]) * (CELL_M / 186.0),
    ]
    parent_volume = capsule_volume(RADIUS_M, PARENT_CENTRELINE_M)
    rows = []
    analytic_checks = []
    for fragments in (1, 2, 3):
        corrected_length = equal_volume_piece_length(fragments)
        nominal_length = PARENT_CENTRELINE_M / fragments
        corrected_volume = fragments * capsule_volume(RADIUS_M, corrected_length)
        analytic_error = abs(corrected_volume / parent_volume - 1.0)
        analytic_checks.append(analytic_error <= 1.0e-12)
        for resolution in RESOLUTIONS:
            for orientation_index, (direction, shift) in enumerate(zip(directions, shifts), start=1):
                intact_count = voxelize(1, PARENT_CENTRELINE_M, resolution, direction, shift)
                nominal_count = voxelize(fragments, nominal_length, resolution, direction, shift)
                corrected_count = voxelize(fragments, corrected_length, resolution, direction, shift)
                rows.append(
                    {
                        "fragments_per_parent": fragments,
                        "resolution": resolution,
                        "orientation_index": orientation_index,
                        "nominal_piece_centreline_length_m": nominal_length,
                        "equal_volume_piece_centreline_length_m": corrected_length,
                        "equal_volume_overall_length_m": corrected_length + 2.0 * RADIUS_M,
                        "equal_volume_aspect_ratio": (corrected_length + 2.0 * RADIUS_M) / (2.0 * RADIUS_M),
                        "analytic_relative_volume_error": analytic_error,
                        "intact_voxel_count": intact_count,
                        "nominal_split_voxel_count": nominal_count,
                        "nominal_split_relative_voxel_error": nominal_count / intact_count - 1.0,
                        "equal_volume_split_voxel_count": corrected_count,
                        "equal_volume_split_relative_voxel_error": corrected_count / intact_count - 1.0,
                    }
                )

    by_key = {(row["fragments_per_parent"], row["resolution"], row["orientation_index"]): row for row in rows}
    nontrivial = [row for row in rows if row["fragments_per_parent"] > 1]
    summary = {}
    for fragments in (2, 3):
        summary[str(fragments)] = {}
        for resolution in RESOLUTIONS:
            selected = [row for row in rows if row["fragments_per_parent"] == fragments and row["resolution"] == resolution]
            summary[str(fragments)][str(resolution)] = {
                "nominal_mean_relative_voxel_error": float(np.mean([row["nominal_split_relative_voxel_error"] for row in selected])),
                "equal_volume_mean_relative_voxel_error": float(np.mean([row["equal_volume_split_relative_voxel_error"] for row in selected])),
                "equal_volume_max_absolute_relative_voxel_error": float(max(abs(row["equal_volume_split_relative_voxel_error"]) for row in selected)),
            }
    refinement_shifts = []
    for fragments in (2, 3):
        for orientation_index in (1, 2, 3):
            coarse = by_key[(fragments, 93, orientation_index)]["equal_volume_split_relative_voxel_error"]
            fine = by_key[(fragments, 186, orientation_index)]["equal_volume_split_relative_voxel_error"]
            refinement_shifts.append(abs(fine - coarse))

    checks = {
        "design_and_audit_hashes_present": DESIGN.is_file() and DESIGN_AUDIT.is_file(),
        "all_analytic_equal_volume_errors_le_1e_12": all(analytic_checks),
        "nominal_split_demonstrates_endcap_inflation": all(row["nominal_split_relative_voxel_error"] > 0.0 for row in nontrivial),
        "equal_volume_correction_reduces_mean_bias_at_cpd4": all(
            abs(summary[str(fragments)]["186"]["equal_volume_mean_relative_voxel_error"])
            < abs(summary[str(fragments)]["186"]["nominal_mean_relative_voxel_error"])
            for fragments in (2, 3)
        ),
        "cpd4_equal_volume_max_abs_voxel_error_le_0p05": all(
            summary[str(fragments)]["186"]["equal_volume_max_absolute_relative_voxel_error"] <= 0.05
            for fragments in (2, 3)
        ),
        "maximum_cpd2_to_cpd4_voxel_bias_shift_le_0p05": max(refinement_shifts) <= 0.05,
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    csv_path = OUTPUT / "primitive_volume_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "schema": "lbs.stage34b-fragment-geometry-primitive-verification.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed_primitive_geometry_verification" if passed else "failed_primitive_geometry_verification",
        "passed": passed,
        "checks": checks,
        "summary": summary,
        "equal_volume_piece_lengths_m": {str(n): equal_volume_piece_length(n) for n in (1, 2, 3)},
        "maximum_cpd2_to_cpd4_voxel_bias_shift": max(refinement_shifts),
        "interpretation": "Repeated capsule end caps add PET volume if nominal lengths are simply divided. Equal-volume endpoint correction removes the analytical bias, but application geometry must still match solver-resolved fibre-only volume within the stricter Stage34B gate.",
        "authority": {"application_geometry": passed, "gpu_execution": False, "cpd4_execution": False},
        "bindings": {
            "design_sha256": sha(DESIGN),
            "design_audit_sha256": sha(DESIGN_AUDIT),
            "geometry_api_sha256": sha(GEOMETRY_API),
            "test_script_sha256": sha(Path(__file__).resolve()),
            "results_csv_sha256": sha(csv_path),
        },
    }
    result_path = OUTPUT / "verification.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "completion.json").write_text(
        json.dumps({"passed": passed, "status": result["status"], "verification_sha256": sha(result_path)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    if not passed:
        raise SystemExit(6)


if __name__ == "__main__":
    main()

