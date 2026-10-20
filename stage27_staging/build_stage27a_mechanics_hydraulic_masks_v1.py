#!/usr/bin/env python3
"""Build immutable CPD2 masks from the accepted Stage26x fibre states."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import ndimage


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_ROOT = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration")
STUDY = "stage27a_stage26x_mechanics_hydraulic_bridge_20260823"
OUTPUT = ROOT / "stage27_designs" / STUDY / "geometry_01"

SOURCES = {
    "network": ROOT / "stage26_network_exports/stage26b_revision2_stage25_network_20260816/export_04/network.json",
    "mechanics_result": ROOT / "stage26_runs/stage26x_periodic_pore_geometry_20260823/fixed_sand_pilot_02/result.json",
    "mechanics_evaluation": ROOT / "stage26_evaluations/stage26x_periodic_pore_geometry_20260823/fixed_sand_evaluation_01/evaluation.json",
    "mechanics_checkpoint": ROOT / "stage26_evaluations/stage26x_periodic_pore_geometry_20260823/fixed_sand_evaluation_01/checkpoint_manifest.json",
    "mechanics_config": ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/fixed_sand_design_02/config.json",
    "stage24_config": EXTERNAL_ROOT / "configs/lbs_stage24c_lbs_f37_cpd2_gpu_screen_v1.json",
    "stage17_adapter": EXTERNAL_ROOT / "scripts/stage17_relaxed_fibre_gpu_lbm_run.py",
}
EXPECTED = {
    "network": "6b1e0912114742f23afc6391539dd373dbe4a85cb6aabc39658fe62a84c07984",
    "mechanics_result": "5d7baf8ebf17e5224bbecf7681bae247aebc92d0481afc32c6b2e57ad606b40a",
    "mechanics_evaluation": "f456ccfec9a058685c4f201574b44159a0d215d22c8fa48020124bd447f262b0",
    "mechanics_checkpoint": "5abf0678a6be71a98cfc3b032ea722e06fd6f6572653d0b36cf89401ad4dba93",
    "mechanics_config": "fbfd8860791aeb05e57d7f5f193275286a0372b7fc043f655d6b7e7b44f18083",
    "stage24_config": "32700c7f7b97ee0c6efd30a5c875daadeeb52456fc08ae8f7e93462f4b2f3353",
    "stage17_adapter": "2346974d997893be019333c3298e4311c5593b497b00c5666b5d6a76b9062163",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def mark_spheres(mask: np.ndarray, centres: np.ndarray, radii: np.ndarray, length: float) -> None:
    n = mask.shape[0]
    spacing = length / n
    for centre, radius in zip(centres, radii):
        for shift in itertools.product((-length, 0.0, length), repeat=3):
            c = centre + np.asarray(shift)
            lo = np.maximum(0, np.floor((c - radius) / spacing - 0.5).astype(int))
            hi = np.minimum(n - 1, np.ceil((c + radius) / spacing - 0.5).astype(int))
            if np.any(lo > hi):
                continue
            z, y, x = np.ogrid[lo[2] : hi[2] + 1, lo[1] : hi[1] + 1, lo[0] : hi[0] + 1]
            dx = (x + 0.5) * spacing - c[0]
            dy = (y + 0.5) * spacing - c[1]
            dz = (z + 0.5) * spacing - c[2]
            local = dx * dx + dy * dy + dz * dz <= radius * radius
            mask[lo[2] : hi[2] + 1, lo[1] : hi[1] + 1, lo[0] : hi[0] + 1] |= local


def mark_capsule(mask: np.ndarray, points: np.ndarray, radius: float, length: float) -> None:
    n = mask.shape[0]
    spacing = length / n
    for first0, second0 in zip(points[:-1], points[1:]):
        for shift in itertools.product((-length, 0.0, length), repeat=3):
            delta = np.asarray(shift)
            first, second = first0 + delta, second0 + delta
            lo = np.maximum(0, np.floor((np.minimum(first, second) - radius) / spacing - 0.5).astype(int))
            hi = np.minimum(n - 1, np.ceil((np.maximum(first, second) + radius) / spacing - 0.5).astype(int))
            if np.any(lo > hi):
                continue
            z, y, x = np.mgrid[lo[2] : hi[2] + 1, lo[1] : hi[1] + 1, lo[0] : hi[0] + 1]
            samples = np.stack(((x + 0.5) * spacing, (y + 0.5) * spacing, (z + 0.5) * spacing), axis=-1)
            axis = second - first
            denom = float(np.dot(axis, axis))
            t = np.clip(np.einsum("...i,i->...", samples - first, axis) / denom, 0.0, 1.0)
            closest = first + t[..., None] * axis
            local = np.sum((samples - closest) ** 2, axis=-1) <= radius * radius
            mask[lo[2] : hi[2] + 1, lo[1] : hi[1] + 1, lo[0] : hi[0] + 1] |= local


def connectivity(solid: np.ndarray) -> dict:
    fluid = ~solid
    labels, count = ndimage.label(fluid, structure=ndimage.generate_binary_structure(3, 1))
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    label = int(np.argmax(sizes)) if count else 0
    component = labels == label
    spans = [bool(np.any(np.take(component, 0, axis=a)) and np.any(np.take(component, -1, axis=a))) for a in (2, 1, 0)]
    return {
        "component_count_nonperiodic": int(count),
        "largest_fluid_component_fraction": float(np.count_nonzero(component) / max(np.count_nonzero(fluid), 1)),
        "largest_component_spans_xyz_nonperiodic": spans,
    }


def write_vtk(path: Path, material: np.ndarray, spacing: float) -> None:
    nz, ny, nx = material.shape
    header = (
        "# vtk DataFile Version 3.0\nStage27a material mask\nBINARY\n\n"
        f"DATASET STRUCTURED_POINTS\nDIMENSIONS {nx} {ny} {nz}\nORIGIN {0.5*spacing} {0.5*spacing} {0.5*spacing}\n"
        f"SPACING {spacing} {spacing} {spacing}\nPOINT_DATA {nx*ny*nz}\n"
        "SCALARS material unsigned_char 1\nLOOKUP_TABLE default\n"
    ).encode("ascii")
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(np.ascontiguousarray(material).tobytes(order="C"))
        stream.write(b"\n")


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    observed = {key: digest(path) for key, path in SOURCES.items()}
    mismatch = [key for key in EXPECTED if observed[key] != EXPECTED[key]]
    if mismatch:
        raise RuntimeError(f"source hash mismatch: {mismatch}")
    network = load(SOURCES["network"])
    result = load(SOURCES["mechanics_result"])
    evaluation = load(SOURCES["mechanics_evaluation"])
    mechanics_config = load(SOURCES["mechanics_config"])
    stage24 = load(SOURCES["stage24_config"])
    if not (network.get("passed") and network.get("periodic") and len(network["particles"]) == 216):
        raise RuntimeError("accepted periodic 216-grain network is absent")
    if not (result.get("passed") and evaluation.get("passed") and evaluation["authority"]["render_authorized"]):
        raise RuntimeError("Stage26x mechanics handoff is not independently verified")
    if evaluation["authority"]["mobile_sand_execution_authorized"] or evaluation["authority"]["flow_authorized"]:
        raise RuntimeError("unexpected upstream authority widening")

    cell = np.diag(np.asarray(network["cell_hsize_m"], dtype=float))
    equivalent_length = float(np.prod(cell) ** (1.0 / 3.0))
    affine = equivalent_length / cell
    maximum_distortion = float(np.max(np.abs(affine - 1.0)))
    n = 93
    spacing = equivalent_length / n
    fibre_radius = 0.5 * float(mechanics_config["fibre"]["diameter_m"])
    centres = np.asarray([p["position_m"] for p in network["particles"]], dtype=float) * affine
    radii = np.asarray([p["radius_m"] for p in network["particles"]], dtype=float)
    sand = np.zeros((n, n, n), dtype=bool)
    mark_spheres(sand, centres, radii, equivalent_length)

    cases = {"clean": None}
    for case in result["cases"]:
        cases[case["case_id"]] = np.asarray(case["terminal_node_positions_m"], dtype=float) * affine

    OUTPUT.mkdir(parents=True)
    artifacts, rows = {}, []
    clean_count = int(np.count_nonzero(sand))
    for case_id in ("clean", "open", "constricted"):
        fibre = np.zeros_like(sand)
        if cases[case_id] is not None:
            mark_capsule(fibre, cases[case_id], fibre_radius, equivalent_length)
        fibre_only = fibre & ~sand
        solid = sand | fibre_only
        phase = np.where(solid, 2, 0).astype(np.uint8)
        material = np.zeros_like(phase)
        material[sand] = 1
        material[fibre_only] = 2
        conn = connectivity(solid)
        checks = {
            "sand_identity": int(np.count_nonzero(material == 1)) == clean_count,
            "fibre_positive_or_clean": case_id == "clean" or int(np.count_nonzero(fibre_only)) > 0,
            "fluid_connected_99pct": conn["largest_fluid_component_fraction"] >= 0.99,
            "fluid_spans_xyz": all(conn["largest_component_spans_xyz_nonperiodic"]),
        }
        case_dir = OUTPUT / case_id
        case_dir.mkdir()
        geometry_path = case_dir / "geometry_cpd2.npz"
        np.savez_compressed(
            geometry_path,
            phase=phase,
            material=material,
            spacing_m=np.asarray([spacing]),
            cell_length_m=np.asarray([equivalent_length]),
            original_cell_lengths_m=cell,
            affine_scale_xyz=affine,
            sand_centres_m=centres,
            sand_radii_m=radii,
            fibre_centrelines_m=np.empty((0, 3)) if cases[case_id] is None else cases[case_id],
            fibre_radius_m=np.asarray([fibre_radius]),
        )
        vtk_path = case_dir / "material.vtk"
        write_vtk(vtk_path, material, spacing)
        artifacts[case_id] = {
            "geometry": str(geometry_path.resolve()),
            "geometry_sha256": digest(geometry_path),
            "material_vtk": str(vtk_path.resolve()),
            "material_vtk_sha256": digest(vtk_path),
        }
        rows.append({
            "case_id": case_id,
            "role": {"clean": "paired_clean_control", "open": "terminal_open_path_fibre", "constricted": "terminal_contact_deflected_fibre"}[case_id],
            "sand_voxel_count": clean_count,
            "fibre_only_voxel_count": int(np.count_nonzero(fibre_only)),
            "solid_fraction": float(np.mean(solid)),
            "voxel_porosity": float(np.mean(~solid)),
            "connectivity": conn,
            "checks": checks,
        })
    global_checks = {
        "source_hashes": not mismatch,
        "sand_particle_count_216": len(network["particles"]) == 216,
        "affine_distortion_below_0p005": maximum_distortion < 0.005,
        "fibre_diameter_cells_at_least_1p9": 2.0 * fibre_radius / spacing >= 1.9,
        "all_case_checks": all(all(row["checks"].values()) for row in rows),
        "sand_voxel_identity": len({row["sand_voxel_count"] for row in rows}) == 1,
        "porosity_order": rows[0]["voxel_porosity"] > rows[1]["voxel_porosity"] and rows[0]["voxel_porosity"] > rows[2]["voxel_porosity"],
    }
    if not all(global_checks.values()):
        raise RuntimeError(f"geometry acceptance failed: {global_checks}")

    config = {
        "schema": "lbs.stage27a-stage26x-mechanics-hydraulic-bridge.v1",
        "status": "geometry_preflight_passed_gpu_pilot_authorized",
        "research_question": "Does one terminal mechanically resolved fibre alter paired CPD2 conductance differently in the open and contact-deflected Stage26x paths?",
        "claim_boundary": "Three-case fixed-solid periodic CPD2 numerical pilot only; no physical concentration law, experimental validation, mobile sand, migration, clogging evolution or two-way coupling.",
        "solver": {**stage24["solver"], "warm_start_dimensionless_mobility": 0.34},
        "acceptance": stage24["acceptance"],
        "execution": stage24["execution"],
        "fluid": {"density_kg_m3": 998.2, "dynamic_viscosity_pa_s": 0.001002, "gravity_m_s2": 9.80665},
        "geometry": {
            "resolution": [n, n, n],
            "equivalent_cell_length_m": equivalent_length,
            "spacing_m": spacing,
            "affine_scale_xyz": affine.tolist(),
            "maximum_affine_distortion": maximum_distortion,
            "fibre_diameter_cells": 2.0 * fibre_radius / spacing,
            "cases": rows,
            "artifacts": artifacts,
        },
        "lineage": {
            **{key: {"path": str(path.resolve()), "sha256": observed[key]} for key, path in SOURCES.items()},
            "stage13_qualification": {"path": str((EXTERNAL_ROOT / stage24["lineage"]["stage13_qualification"]).resolve()), "sha256": stage24["lineage"]["stage13_qualification_sha256"]},
            "stage13_execution_manifest": {"path": str((EXTERNAL_ROOT / stage24["lineage"]["stage13_execution_manifest"]).resolve()), "sha256": stage24["lineage"]["stage13_execution_manifest_sha256"]},
            "stage13_runner": {"path": str((EXTERNAL_ROOT / stage24["lineage"]["stage13_runner"]).resolve()), "sha256": stage24["lineage"]["stage13_runner_sha256"]},
            "cuda_source": {"path": str((EXTERNAL_ROOT / stage24["lineage"]["cuda_source"]).resolve()), "sha256": stage24["lineage"]["cuda_source_sha256"]},
            "qualified_ptx_sha256": stage24["lineage"]["qualified_ptx_sha256"],
        },
        "authority": {"gpu_cpd2_pilot": True, "render": False, "concentration_campaign": False, "mobile_sand": False, "two_way_coupling": False},
    }
    config_path = OUTPUT / "resolved_config.json"
    write_json(config_path, config)
    completion = {
        "schema": config["schema"] + ".geometry-completion",
        "status": "passed_geometry_preflight_gpu_cpd2_pilot_authorized",
        "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": digest(config_path),
        "builder_sha256": digest(Path(__file__).resolve()),
        "checks": global_checks,
        "cases": rows,
        "artifacts": artifacts,
        "next_handoff": {"authorized": "bounded three-case CPD2 GPU-LBM pilot", "not_authorized": "CPD4, concentration campaign, mobile mechanics, transient or two-way coupling"},
    }
    completion_path = OUTPUT / "completion.json"
    write_json(completion_path, completion)
    print(json.dumps({"passed": True, "config": str(config_path), "config_sha256": digest(config_path), "completion": str(completion_path), "completion_sha256": digest(completion_path), "cases": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
