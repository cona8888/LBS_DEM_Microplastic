#!/usr/bin/env python3
"""Render the independently accepted Stage28c CPD2-to-CPD4 comparison."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage28c_selected_two_fibre_cpd4_20260825"
CONFIG = ROOT / "stage28_designs" / STUDY / "geometry_01/resolved_config.json"
COMPLETION = ROOT / "stage28_runs" / STUDY / "gpu_confirmation_01/completion.json"
EVALUATION = ROOT / "stage28_evaluations" / STUDY / "gpu_evaluation_01/evaluation.json"
CHECKPOINT = EVALUATION.parent / "checkpoint_manifest.json"
OUTPUT = ROOT / "stage28_renders" / STUDY / "cpd4_verification_02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable render: {OUTPUT}")
    config, completion, evaluation, checkpoint = map(load, (CONFIG, COMPLETION, EVALUATION, CHECKPOINT))
    if not (completion.get("passed") and evaluation.get("passed") and checkpoint.get("passed") and evaluation["authority"]["render"]):
        raise RuntimeError("independent Stage28c render authority is absent")
    OUTPUT.mkdir(parents=True)
    case_ids = ("clean", "separated_open_open", "crossing_interaction")
    titles = ("Clean LBS", "Separated fibres", "Crossing fibres")
    rows = {row["case_id"]: row for row in completion["paired_results"]}
    fig = plt.figure(figsize=(15, 8.5), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=(1.05, 1.0))
    for col, (case_id, title) in enumerate(zip(case_ids, titles)):
        path = Path(config["geometry"]["artifacts"][case_id]["geometry"])
        with np.load(path, allow_pickle=False) as data:
            material = np.asarray(data["material"], dtype=np.uint8)
        counts = np.count_nonzero(material == 2, axis=(1, 2))
        z = int(np.argmax(counts)) if case_id != "clean" else material.shape[0] // 2
        image = np.zeros(material.shape[1:] + (3,), dtype=float)
        plane = material[z]
        image[plane == 1] = (0.22, 0.22, 0.22)
        image[plane == 2] = (0.90, 0.25, 0.12)
        ax = fig.add_subplot(grid[0, col])
        ax.imshow(image, origin="lower")
        ax.set_title(f"{title}\nCPD4 slice z={z}; k/k0={rows[case_id]['paired_permeability_ratio']:.7f}")
        ax.set_xlabel("x lattice cell")
        ax.set_ylabel("y lattice cell")
    ax = fig.add_subplot(grid[1, 0])
    x = np.arange(2)
    width = 0.34
    cpd2 = [rows[case]["cpd2_ratio"] for case in case_ids[1:]]
    cpd4 = [rows[case]["paired_permeability_ratio"] for case in case_ids[1:]]
    ax.bar(x - width / 2, cpd2, width, label="CPD2", color="#4c78a8")
    ax.bar(x + width / 2, cpd4, width, label="CPD4", color="#f58518")
    ax.axhline(1.0, color="black", linewidth=1)
    ax.set_xticks(x, ("Separated", "Crossing"))
    ax.set_ylabel("Paired permeability ratio k/k0")
    ax.set_title("Resolution comparison")
    ax.legend()
    ax = fig.add_subplot(grid[1, 1])
    shifts = [100.0 * rows[case]["cpd2_to_cpd4_ratio_shift"] for case in case_ids[1:]]
    ax.bar(("Separated", "Crossing"), shifts, color=("#72b7b2", "#e45756"))
    ax.axhline(0.2, color="black", linestyle="--", linewidth=1, label="±0.2 pp gate")
    ax.axhline(-0.2, color="black", linestyle="--", linewidth=1)
    ax.set_ylabel("CPD2→CPD4 shift (percentage points)")
    ax.set_title("Solution-verification shifts")
    ax.legend()
    ax = fig.add_subplot(grid[1, 2])
    for case_id, title in zip(case_ids, titles):
        audit_path = ROOT / "stage28_runs" / STUDY / "gpu_confirmation_01" / rows[case_id]["solver_case_id"] / "audit.npz"
        with np.load(audit_path, allow_pickle=False) as audit:
            steps = np.asarray(audit["step"], dtype=float)
            velocity = np.asarray(audit["superficial_velocity_lu"], dtype=float)
        ax.plot(steps, velocity / velocity[-1], marker="o", ms=3, label=title)
    ax.axhline(1.0, color="black", linewidth=1)
    ax.set_xlabel("LBM step")
    ax.set_ylabel("Velocity / terminal velocity")
    ax.set_title("CPD4 convergence histories")
    ax.legend(fontsize=8)
    fig.suptitle("Stage28c — CPD4 solution verification of separated and crossing two-fibre permeability", fontsize=15)
    png = OUTPUT / "stage28c_two_fibre_cpd4_verification.png"
    fig.savefig(png, dpi=180)
    plt.close(fig)
    manifest = {"schema": "lbs.stage28c-selected-two-fibre-cpd4-render.v1", "status": "rendered_from_independently_verified_result",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(), "figure": {"path": str(png), "sha256": sha(png)},
                "sources": {"config": {"path": str(CONFIG), "sha256": sha(CONFIG)},
                            "completion": {"path": str(COMPLETION), "sha256": sha(COMPLETION)},
                            "evaluation": {"path": str(EVALUATION), "sha256": sha(EVALUATION)},
                            "checkpoint": {"path": str(CHECKPOINT), "sha256": sha(CHECKPOINT)},
                            "renderer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())}},
                "claim_boundary": config["claim_boundary"]}
    manifest_path = OUTPUT / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"figure": str(png), "figure_sha256": sha(png), "manifest": str(manifest_path),
                      "manifest_sha256": sha(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
