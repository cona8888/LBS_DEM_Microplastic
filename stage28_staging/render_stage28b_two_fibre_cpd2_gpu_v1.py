#!/usr/bin/env python3
"""Render Stage28b CPD2 permeability effects and paired flow slices."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage28_runs/stage28b_two_fibre_cpd2_hydraulic_20260825/gpu_pilot_01"
COMPLETION = RUN / "completion.json"
EVALUATION = ROOT / "stage28_evaluations/stage28b_two_fibre_cpd2_hydraulic_20260825/gpu_evaluation_01/evaluation.json"
GEOMETRY = ROOT / "stage28_designs/stage28b_two_fibre_cpd2_hydraulic_20260824/geometry_01"
OUTPUT = ROOT / "stage28_renders/stage28b_two_fibre_cpd2_hydraulic_20260825/render_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable render: {OUTPUT}")
    completion, evaluation = map(load, (COMPLETION, EVALUATION))
    if not (completion["passed"] and evaluation["passed"]):
        raise RuntimeError("accepted Stage28b evidence required")
    rows = {row["case_id"]: row for row in completion["paired_results"]}
    cases = ["separated_open_open", "separated_open_constricted", "crossing_interaction"]
    labels = ["separated\nopen–open", "separated\nopen–constricted", "crossing\ninteraction"]
    colors = ["#4c78a8", "#72b7b2", "#e45756"]
    changes = [100 * rows[name]["paired_relative_permeability_change"] for name in cases]
    permeabilities = [1e10 * rows[name]["intrinsic_permeability_m2"] for name in ["clean"] + cases]

    with np.load(GEOMETRY / "crossing_interaction/geometry_cpd2.npz") as data:
        centrelines = np.asarray(data["fibre_centrelines_m"])
        spacing = float(data["spacing_m"][0])
    z_index = int(np.clip(round(float(np.mean(centrelines[:, :, 2])) / spacing - 0.5), 0, 92))
    fields, materials = {}, {}
    for name in ("clean", "crossing_interaction"):
        with np.load(RUN / f"stage28b_{name}_cpd2/final_fields.npz") as data:
            fields[name] = np.asarray(data["velocity_xyz_lu"][0, z_index], dtype=float)
        with np.load(GEOMETRY / name / "geometry_cpd2.npz") as data:
            materials[name] = np.asarray(data["material"][z_index], dtype=np.uint8)
    fluid_values = np.concatenate([fields[name][materials[name] == 0] for name in fields])
    vmax = float(np.percentile(fluid_values, 99.5))

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
    bars = axes[0, 0].bar(labels, changes, color=colors)
    axes[0, 0].axhline(0, color="black", linewidth=.8)
    axes[0, 0].bar_label(bars, labels=[f"{v:.3f}%" for v in changes], padding=4)
    axes[0, 0].set_ylabel("permeability change from paired clean (%)")
    axes[0, 0].set_title("Two-fibre placement effect (CPD2)")
    axes[0, 0].grid(axis="y", alpha=.2)

    p_labels = ["clean", "open–open", "open–constricted", "crossing"]
    p_colors = ["#777777"] + colors
    bars = axes[0, 1].bar(p_labels, permeabilities, color=p_colors)
    axes[0, 1].bar_label(bars, labels=[f"{v:.4f}" for v in permeabilities], padding=3, fontsize=9)
    axes[0, 1].set_ylabel(r"intrinsic permeability ($10^{-10}$ m$^2$)")
    axes[0, 1].set_title("Absolute paired permeability")
    axes[0, 1].tick_params(axis="x", rotation=18)
    axes[0, 1].grid(axis="y", alpha=.2)

    image = None
    for ax, name, title in zip(axes[1], ("clean", "crossing_interaction"),
                               ("Clean LBS flow slice", "Crossing-fibre flow slice")):
        plot = np.ma.array(fields[name], mask=materials[name] != 0)
        image = ax.imshow(plot, origin="lower", cmap="turbo", vmin=0, vmax=vmax,
                          extent=(0, 93 * spacing * 1e3, 0, 93 * spacing * 1e3))
        ax.contour(materials[name] == 1, levels=[.5], colors="#333333", linewidths=.25,
                   origin="lower", extent=(0, 93 * spacing * 1e3, 0, 93 * spacing * 1e3))
        if name != "clean":
            ax.contour(materials[name] == 2, levels=[.5], colors="white", linewidths=1.0,
                       origin="lower", extent=(0, 93 * spacing * 1e3, 0, 93 * spacing * 1e3))
        ax.set_title(f"{title}\nz-index {z_index}; sand dark, fibres white")
        ax.set_xlabel("x (mm)")
        ax.set_ylabel("y (mm)")
        ax.set_aspect("equal")
    fig.colorbar(image, ax=axes[1, :], label="streamwise velocity (lattice units)", shrink=.82)
    fig.suptitle("Stage28b: mechanically resolved two-fibre placement changes LBS permeability",
                 fontsize=16, fontweight="bold")
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "stage28b_two_fibre_cpd2_permeability.png"
    fig.savefig(path, dpi=190, facecolor="white")
    plt.close(fig)
    manifest = {"schema": "lbs.stage28b-two-fibre-cpd2-render.v1",
                "status": "rendered_from_independently_accepted_cpd2_checkpoint", "passed": True,
                "bindings": {"completion_sha256": sha(COMPLETION), "evaluation_sha256": sha(EVALUATION),
                             "renderer_sha256": sha(Path(__file__).resolve()), "image_sha256": sha(path)},
                "image": str(path), "slice_z_index": z_index}
    manifest_path = OUTPUT / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"image": str(path), "image_sha256": sha(path),
                      "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
