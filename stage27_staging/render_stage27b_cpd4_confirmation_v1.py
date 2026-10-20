#!/usr/bin/env python3
"""Render the independently verified Stage27b CPD2-to-CPD4 comparison."""

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
STUDY = "stage27b_stage26x_mechanics_hydraulic_cpd4_20260824"
CONFIG = ROOT / "stage27_designs" / STUDY / "geometry_01/resolved_config.json"
RUN = ROOT / "stage27_runs" / STUDY / "gpu_confirmation_01"
EVALUATION = ROOT / "stage27_evaluations" / STUDY / "evaluation_01/evaluation.json"
CHECKPOINT = EVALUATION.parent / "checkpoint_manifest.json"
OUTPUT = ROOT / "stage27_renders" / STUDY / "render_01"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    config = load(CONFIG)
    evaluation = load(EVALUATION)
    checkpoint = load(CHECKPOINT)
    if not (
        evaluation.get("passed")
        and evaluation["authority"]["render"]
        and checkpoint.get("passed")
    ):
        raise RuntimeError("independent Stage27b checkpoint does not authorize rendering")
    completion_path = RUN / "completion.json"
    completion = load(completion_path)
    rows = {row["case_id"]: row for row in completion["paired_results"]}
    cpd2 = {
        row["case_id"]: row
        for row in config["cpd2_reference"]["paired_results"]
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(17, 10.5), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=(1.18, 1.0))
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#b8aa8d")

    slices = []
    for case_id in ("clean", "open", "constricted"):
        artifact = config["geometry"]["artifacts"][case_id]
        with np.load(artifact["geometry"], allow_pickle=False) as geometry:
            material = np.asarray(geometry["material"], dtype=np.uint8)
            fibre = np.asarray(geometry["fibre_centrelines_m"], dtype=float)
            spacing = float(geometry["spacing_m"][0])
        with np.load(
            RUN / rows[case_id]["solver_case_id"] / "final_fields.npz",
            allow_pickle=False,
        ) as fields:
            velocity = np.asarray(fields["velocity_xyz_lu"], dtype=float)
        zindex = (
            int(np.clip(np.mean(fibre[:, 2]) / spacing, 0, material.shape[0] - 1))
            if fibre.size
            else material.shape[0] // 2
        )
        speed = np.linalg.norm(velocity[:, zindex], axis=0)
        slices.append(
            (case_id, zindex, material[zindex], np.ma.array(speed, mask=material[zindex] != 0))
        )

    shared_vmax = max(float(np.max(view.compressed())) for _, _, _, view in slices)
    images = []
    titles = {
        "clean": "Clean sand",
        "open": "Open-path fibre",
        "constricted": "Contact-deflected fibre",
    }
    for col, (case_id, zindex, material_slice, view) in enumerate(slices):
        ax = fig.add_subplot(grid[0, col])
        image = ax.imshow(
            view,
            origin="lower",
            cmap=cmap,
            interpolation="nearest",
            vmin=0.0,
            vmax=shared_vmax,
        )
        images.append(image)
        if np.any(material_slice == 2):
            ax.contour(material_slice == 2, levels=[0.5], colors="#ff3030", linewidths=1.4)
        ax.set_title(
            f"{titles[case_id]}\nCPD4 k/k₀={rows[case_id]['paired_permeability_ratio']:.7f}; z={zindex}"
        )
        ax.set_xlabel("x lattice cell")
        ax.set_ylabel("y lattice cell")
    colorbar = fig.colorbar(images[-1], ax=fig.axes[:3], shrink=0.82)
    colorbar.set_label("speed (lattice units; shared scale)")

    ax = fig.add_subplot(grid[1, 0])
    cases = ("open", "constricted")
    positions = np.arange(len(cases))
    width = 0.34
    cpd2_ratios = [cpd2[case]["paired_permeability_ratio"] for case in cases]
    cpd4_ratios = [rows[case]["paired_permeability_ratio"] for case in cases]
    ax.bar(positions - width / 2, cpd2_ratios, width, label="CPD2", color="#4c78a8")
    ax.bar(positions + width / 2, cpd4_ratios, width, label="CPD4", color="#f58518")
    ax.axhline(1.0, color="black", linewidth=0.9)
    ax.set_xticks(positions, ["open", "deflected"])
    ax.set_ylim(min(cpd4_ratios + cpd2_ratios) - 0.00035, 1.00025)
    ax.set_ylabel("paired permeability ratio k/k₀")
    ax.set_title("Resolution comparison")
    ax.legend(frameon=False)
    for x, value in zip(positions - width / 2, cpd2_ratios):
        ax.text(x, value - 0.00006, f"{value:.7f}", rotation=90, ha="center", va="top", fontsize=8)
    for x, value in zip(positions + width / 2, cpd4_ratios):
        ax.text(x, value - 0.00006, f"{value:.7f}", rotation=90, ha="center", va="top", fontsize=8)

    ax = fig.add_subplot(grid[1, 1])
    shifts = [
        100.0 * rows[case]["cpd2_to_cpd4_ratio_shift"]
        for case in cases
    ]
    contrast_shift = 100.0 * evaluation["metrics"]["placement_contrast_shift"]
    labels = ["open ratio", "deflected ratio", "placement\ncontrast"]
    values = shifts + [contrast_shift]
    colors = ["#2e8b57", "#d97706", "#7b5ea7"]
    ax.bar(labels, values, color=colors)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.axhline(0.2, color="#aa0000", linestyle="--", linewidth=0.8, label="single-fibre ±0.2 pp bound")
    ax.axhline(-0.2, color="#aa0000", linestyle="--", linewidth=0.8)
    ax.set_ylabel("CPD2→CPD4 shift (percentage points)")
    ax.set_title("Frozen solution-verification shifts")
    ax.legend(frameon=False, fontsize=8)
    for i, value in enumerate(values):
        ax.text(i, value - 0.007 if value < 0 else value + 0.007, f"{value:.5f}", ha="center", va="top" if value < 0 else "bottom", fontsize=9)

    ax = fig.add_subplot(grid[1, 2])
    for case_id, color in zip(
        ("clean", "open", "constricted"),
        ("#777777", "#2e8b57", "#d97706"),
    ):
        with np.load(
            RUN / rows[case_id]["solver_case_id"] / "audit.npz", allow_pickle=False
        ) as audit:
            step = np.asarray(audit["step"])
            velocity = np.asarray(audit["superficial_velocity_lu"])
        ax.plot(step, velocity / velocity[-1], marker="o", label=case_id, color=color)
    ax.axhline(1.0, color="black", linestyle="--", linewidth=0.8)
    ax.set_xlabel("LBM step")
    ax.set_ylabel("superficial velocity / terminal")
    ax.set_title("CPD4 convergence histories")
    ax.legend(frameon=False)

    fig.suptitle(
        "Stage27b — CPD4 solution verification of single-fibre hydraulic obstruction",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.006,
        "PASS: open and contact-deflected effects retain sign and ordering; both ratio shifts and the placement-contrast shift satisfy frozen bounds. "
        "Scope: one fibre, fixed sand, one periodic 216-grain realization. No concentration law, absolute validation, mobile grains, clogging evolution, or two-way coupling.",
        fontsize=9,
    )
    image_path = OUTPUT / "stage27b_cpd2_to_cpd4_solution_verification.png"
    fig.savefig(image_path, dpi=190)
    plt.close(fig)

    manifest = {
        "schema": "lbs.stage27b-stage26x-mechanics-hydraulic-cpd4-render.v1",
        "status": "rendered_independently_verified_solution_comparison",
        "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "image": {"path": str(image_path), "sha256": digest(image_path)},
        "renderer": {
            "path": str(Path(__file__).resolve()),
            "sha256": digest(Path(__file__).resolve()),
        },
        "source_bindings": {
            "config": {"path": str(CONFIG), "sha256": digest(CONFIG)},
            "completion": {"path": str(completion_path), "sha256": digest(completion_path)},
            "evaluation": {"path": str(EVALUATION), "sha256": digest(EVALUATION)},
            "checkpoint": {"path": str(CHECKPOINT), "sha256": digest(CHECKPOINT)},
        },
        "claim_boundary": evaluation["claim_boundary"],
    }
    manifest_path = OUTPUT / "render_manifest.json"
    write(manifest_path, manifest)
    print(
        json.dumps(
            {
                "image": str(image_path),
                "image_sha256": digest(image_path),
                "manifest": str(manifest_path),
                "manifest_sha256": digest(manifest_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
