#!/usr/bin/env python3
"""Render the exact Stage24d CPD4 material masks for scientific visual review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap


ROOT = Path(__file__).resolve().parents[1]


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--completion", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path, completion_path, output = args.config.resolve(), args.completion.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable Stage24d render: {output}")
    completion = load(completion_path)
    if completion.get("passed") is not True or completion.get("status") != "passed_all_six_selected_cpd4_geometry_preflights":
        raise RuntimeError("renderer requires a passed Stage24d geometry completion")
    if completion["config_sha256"] != digest(config_path):
        raise RuntimeError("Stage24d render/config binding mismatch")
    builder = ROOT / "scripts/build_stage24d_lbs_f37_cpd4_selected_geometry_v1.py"
    if completion["builder_sha256"] != digest(builder):
        raise RuntimeError("Stage24d render/builder binding mismatch")

    rows = {row["case_id"]: row for row in completion["cases"]}
    order = [
        "stage24_n216_s1_isotropic_B_w0p005_f001",
        "stage24_n216_s1_isotropic_B_w0p100_f021",
        "stage24_n216_s1_isotropic_B_w0p400_f086",
        "stage24_n216_s1_parallel_biased_B_w0p400_f086",
        "stage24_n216_s1_transverse_biased_B_w0p400_f086",
        "stage24_n216_s2_isotropic_B_w0p400_f086",
    ]
    labels = ["Isotropic · 0.005 wt% · s1", "Isotropic · 0.1 wt% · s1", "Isotropic · 0.4 wt% · s1",
              "Parallel-biased · 0.4 wt% · s1", "Transverse-biased · 0.4 wt% · s1", "Isotropic · 0.4 wt% · holdout s2"]
    output.mkdir(parents=True)
    figure, axes = plt.subplots(2, 3, figsize=(14.2, 10.0), constrained_layout=False)
    figure.subplots_adjust(left=0.055, right=0.98, top=0.90, bottom=0.21, wspace=0.17, hspace=0.31)
    cmap = ListedColormap(["#ffffff00", "#cfb184", "#d62728"])
    selected_hashes = {}
    for axis, case_id, label in zip(axes.ravel(), order, labels):
        artifact = completion["artifacts"][case_id]
        path = ROOT / artifact["geometry"]
        if digest(path) != artifact["geometry_sha256"]:
            raise RuntimeError(f"Stage24d geometry hash mismatch: {case_id}")
        selected_hashes[case_id] = artifact["geometry_sha256"]
        with np.load(path, allow_pickle=False) as archive:
            material = np.asarray(archive["material"], dtype=np.uint8)
            spacing = float(archive["spacing_m"][0])
            length = float(archive["cell_length_m"][0])
        middle = material.shape[0] // 2
        sand_slice = np.any(material[middle - 1:middle + 2] == 1, axis=0)
        fibre_projection = np.any(material == 2, axis=0)
        display = np.zeros_like(sand_slice, dtype=np.uint8)
        display[sand_slice] = 1
        display[fibre_projection] = 2
        limit = length * 1e3
        axis.imshow(display, origin="lower", interpolation="nearest", cmap=cmap, vmin=0, vmax=2,
                    extent=(0, limit, 0, limit), aspect="equal")
        row = rows[case_id]
        axis.set_title(label, fontsize=10, fontweight="bold")
        axis.set_xlabel("x (mm)")
        axis.set_ylabel("y (mm)")
        axis.text(0.02, 0.02,
                  f"{row['fibre_count']} fibres · {row['dimensions_xyz'][0]}³\n"
                  f"connected fluid={row['connectivity']['largest_fluid_component_fraction']:.5f}",
                  transform=axis.transAxes, fontsize=8,
                  bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.84, "edgecolor": "0.6"})
    figure.suptitle("Stage24d CPD4 phase-assignment review · exact physical scale", fontsize=15, fontweight="bold")
    figure.text(0.5, 0.145,
                "Tan: three-cell-thick central z slice of the exact CPD4 sand mask. Red: full-z projection of exact CPD4 F37 voxels. "
                "Fibre width and coordinates are not magnified.", ha="center", fontsize=9)
    figure.text(0.5, 0.065,
                "Numerical-resolution geometry only: rigid hydrodynamically neutral fibres in frozen periodic spherical LBS pores.\n"
                "Excludes mixing rearrangement, polymer deformation/chemistry/migration, mechanics, transient FSI, bounded-specimen effects,\n"
                "and deformation-coupled flow.",
                ha="center", va="center", fontsize=8.3, color="#333333",
                bbox={"boxstyle": "round,pad=0.4", "facecolor": "#f4f4f4", "edgecolor": "#aaaaaa"})
    image_path = output / "stage24d_selected_cpd4_phase_review.png"
    figure.savefig(image_path, dpi=200, facecolor="white")
    plt.close(figure)

    manifest = {
        "schema": "lbs.stage24d-lbs-f37-selected-cpd4-geometry.v1.render",
        "status": "rendered_exact_cpd4_masks_for_scientific_review",
        "claim_boundary": completion["claim_boundary"],
        "config_sha256": digest(config_path),
        "completion_sha256": digest(completion_path),
        "builder_sha256": digest(builder),
        "renderer_sha256": digest(Path(__file__).resolve()),
        "selected_geometry_sha256": selected_hashes,
        "image": str(image_path.relative_to(ROOT)).replace("\\", "/"),
        "image_sha256": digest(image_path),
        "render_definition": "Three-cell-thick central z sand slice plus full-z fibre-voxel projection; exact physical x-y scale and no fibre magnification.",
        "next_handoff": "Independent hash/phase review may authorize the frozen six-case sequential CPD4 GPU confirmation.",
    }
    write_json(output / "render_manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "image": str(image_path), "image_sha256": manifest["image_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
