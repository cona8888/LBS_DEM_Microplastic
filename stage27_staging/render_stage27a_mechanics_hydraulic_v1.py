#!/usr/bin/env python3
"""Render the independently verified Stage27a CPD2 flow comparison."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STUDY = "stage27a_stage26x_mechanics_hydraulic_bridge_20260823"
CONFIG = ROOT / "stage27_designs" / STUDY / "geometry_01/resolved_config.json"
RUN = ROOT / "stage27_runs" / STUDY / "gpu_pilot_01"
EVALUATION = ROOT / "stage27_evaluations" / STUDY / "evaluation_01/evaluation.json"
CHECKPOINT = EVALUATION.parent / "checkpoint_manifest.json"
OUTPUT = ROOT / "stage27_renders" / STUDY / "render_02"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    config, evaluation, checkpoint = load(CONFIG), load(EVALUATION), load(CHECKPOINT)
    if not (evaluation.get("passed") and evaluation["authority"]["render"] and checkpoint.get("passed")):
        raise RuntimeError("independent Stage27a handoff does not authorize rendering")
    completion = load(RUN / "completion.json")
    by_case = {row["case_id"]: row for row in completion["paired_results"]}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(16, 10), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=(1.25, 1.0))
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#b8aa8d")
    slice_data = []
    for case_id in ("clean", "open", "constricted"):
        artifact = config["geometry"]["artifacts"][case_id]
        with np.load(artifact["geometry"], allow_pickle=False) as geometry:
            material = np.asarray(geometry["material"], dtype=np.uint8)
            fibre = np.asarray(geometry["fibre_centrelines_m"], dtype=float)
            spacing = float(geometry["spacing_m"][0])
        solver_id = by_case[case_id]["solver_case_id"]
        with np.load(RUN / solver_id / "final_fields.npz", allow_pickle=False) as fields:
            velocity = np.asarray(fields["velocity_xyz_lu"], dtype=float)
        if fibre.size:
            zindex = int(np.clip(np.mean(fibre[:, 2]) / spacing, 0, material.shape[0] - 1))
        else:
            zindex = material.shape[0] // 2
        speed = np.linalg.norm(velocity[:, zindex], axis=0)
        view = np.ma.array(speed, mask=material[zindex] != 0)
        slice_data.append((case_id, material, zindex, view))
    shared_vmax = max(float(np.max(view.compressed())) for _, _, _, view in slice_data)
    images = []
    for col, (case_id, material, zindex, view) in enumerate(slice_data):
        ax = fig.add_subplot(grid[0, col])
        image = ax.imshow(view, origin="lower", cmap=cmap, interpolation="nearest", vmin=0.0, vmax=shared_vmax)
        images.append(image)
        if np.any(material[zindex] == 2):
            ax.contour(material[zindex] == 2, levels=[0.5], colors="#ff2b2b", linewidths=1.5)
        ax.set_title({"clean": "Clean sand", "open": "Open-path fibre", "constricted": "Contact-deflected fibre"}[case_id] + f"\nz slice {zindex}; k/k₀={by_case[case_id]['paired_permeability_ratio']:.6f}")
        ax.set_xlabel("x lattice cell")
        ax.set_ylabel("y lattice cell")
    cbar = fig.colorbar(images[-1], ax=[fig.axes[0], fig.axes[1], fig.axes[2]], shrink=0.8)
    cbar.set_label("speed (lattice units)")

    ax = fig.add_subplot(grid[1, 0])
    labels = ["clean", "open", "deflected"]
    ratios = [by_case[x]["paired_permeability_ratio"] for x in ("clean", "open", "constricted")]
    ax.bar(labels, ratios, color=["#777777", "#2e8b57", "#d97706"])
    ax.axhline(1.0, color="black", linewidth=1)
    ax.set_ylim(min(ratios) - 0.0005, 1.0005)
    ax.set_ylabel("paired permeability ratio k/k₀")
    ax.set_title("CPD2 paired obstruction")
    for i, value in enumerate(ratios):
        ax.text(i, value + 0.00008, f"{value:.6f}", ha="center", va="bottom", fontsize=9)

    ax = fig.add_subplot(grid[1, 1])
    for case_id, color in zip(("clean", "open", "constricted"), ("#777777", "#2e8b57", "#d97706")):
        solver_id = by_case[case_id]["solver_case_id"]
        with np.load(RUN / solver_id / "audit.npz", allow_pickle=False) as audit:
            step = audit["step"]
            u = audit["superficial_velocity_lu"]
        ax.plot(step, u / u[-1], marker="o", label=case_id, color=color)
    ax.axhline(1.0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("LBM step")
    ax.set_ylabel("superficial velocity / terminal")
    ax.set_title("Convergence histories")
    ax.legend(frameon=False)

    ax = fig.add_subplot(grid[1, 2])
    metrics = evaluation["metrics"]
    ax.axis("off")
    text = (
        "Mechanics-to-hydraulics result\n\n"
        f"Clean k = {metrics['clean_intrinsic_permeability_m2']:.3e} m²\n"
        f"Open change = {metrics['open_relative_change_percent']:.4f}%\n"
        f"Deflected change = {metrics['constricted_relative_change_percent']:.4f}%\n"
        f"Deflected − open = {metrics['constricted_minus_open_percentage_points']:.4f} percentage points\n"
        f"Fibre voxel difference = {metrics['fibre_voxel_difference_constricted_minus_open']}\n\n"
        "Classification:\nCPD2-detected small location-dependent obstruction\n\n"
        "Not yet CPD4 solution-verified."
    )
    ax.text(0.02, 0.98, text, va="top", ha="left", fontsize=12, linespacing=1.35)
    fig.suptitle("Stage27a — fixed-sand hydraulic response of mechanically resolved single fibres", fontsize=18, fontweight="bold")
    fig.text(0.01, 0.005, "Claim boundary: one fibre, one periodic 216-grain realization, CPD2 fixed-solid numerical pilot. No concentration law, experimental validation, mobile grains, clogging evolution, or two-way coupling.", fontsize=9)
    image_path = OUTPUT / "stage27a_mechanics_to_hydraulics_cpd2.png"
    fig.savefig(image_path, dpi=190)
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage27a-stage26x-mechanics-hydraulic-render.v1",
        "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "image": {"path": str(image_path), "sha256": digest(image_path)},
        "renderer": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())},
        "source_bindings": {"evaluation": {"path": str(EVALUATION), "sha256": digest(EVALUATION)}, "checkpoint": {"path": str(CHECKPOINT), "sha256": digest(CHECKPOINT)}, "completion": {"path": str(RUN / 'completion.json'), "sha256": digest(RUN / 'completion.json')}},
        "claim_boundary": evaluation["claim_boundary"],
    }
    manifest_path = OUTPUT / "render_manifest.json"
    write(manifest_path, manifest)
    print(json.dumps({"image": str(image_path), "image_sha256": digest(image_path), "manifest": str(manifest_path), "manifest_sha256": digest(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
