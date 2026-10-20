from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage30a_selected_low_concentration_cpd4_20260826"
EVAL_DIR = ROOT / "stage30_evaluations" / STUDY / "gpu_evaluation_01"
EVALUATION = EVAL_DIR / "evaluation.json"
CHECKPOINT = EVAL_DIR / "checkpoint_manifest.json"
OUT = ROOT / "stage30_renders" / STUDY / "cpd4_verification_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if not (evaluation.get("passed") and evaluation["authority"]["rendering"] and checkpoint.get("passed")):
        raise RuntimeError("independent Stage30a checkpoint does not authorize rendering")
    rows = evaluation["combined_selected_evidence"]
    labels = [x["label"] for x in rows]
    cpd2 = np.array([x["cpd2_ratio"] for x in rows])
    cpd4 = np.array([x["cpd4_ratio"] for x in rows])
    shifts = cpd4 - cpd2
    contrasts = evaluation["contrasts"]
    colors = ["#555555", "#6aa5d8", "#78b76a", "#d54a3a", "#2672bd", "#e38273"]
    positions = np.arange(len(rows))
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.4), constrained_layout=True)
    ax = axes[0]
    ax.scatter(positions - 0.09, cpd2, marker="o", s=64, color=colors, edgecolor="black", linewidth=.35, label="CPD2")
    ax.scatter(positions + 0.09, cpd4, marker="s", s=64, color=colors, edgecolor="black", linewidth=.35, label="CPD4")
    for i in positions:
        ax.plot([i - .09, i + .09], [cpd2[i], cpd4[i]], color=colors[i], linewidth=1.4)
    ax.axhline(1.0, color="#555555", linestyle="--", linewidth=1)
    ax.set_xticks(positions, labels, rotation=28, ha="right")
    ax.set_ylabel("Paired permeability ratio, k/k₀")
    ax.set_title("Selected mechanism responses")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=.22)
    ax = axes[1]
    ax.bar(positions, 1e4 * shifts, color=colors)
    ax.axhline(0.0, color="#555555", linewidth=1)
    ax.axhline(20.0, color="#a33", linestyle="--", linewidth=1, label="±0.002 gate")
    ax.axhline(-20.0, color="#a33", linestyle="--", linewidth=1)
    ax.set_xticks(positions, labels, rotation=28, ha="right")
    ax.set_ylabel("10⁴ × (CPD4 − CPD2) in k/k₀")
    ax.set_title("Resolution shift")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=.22)
    ax = axes[2]
    names = ["2 fibres:\ncrossing − separated", "4 fibres B:\none-contact − zero-contact"]
    x = np.arange(2)
    width = .34
    c2 = [contrasts["two_fibre_crossing_minus_separated"]["cpd2"], contrasts["four_fibre_one_minus_zero_B"]["cpd2"]]
    c4 = [contrasts["two_fibre_crossing_minus_separated"]["cpd4"], contrasts["four_fibre_one_minus_zero_B"]["cpd4"]]
    ax.bar(x - width / 2, 100 * np.array(c2), width, color="#8c8c8c", label="CPD2")
    ax.bar(x + width / 2, 100 * np.array(c4), width, color="#8a57b5", label="CPD4")
    ax.axhline(0.0, color="#555555", linewidth=1)
    ax.set_xticks(x, names)
    ax.set_ylabel("Topology contrast in k/k₀ (%)")
    ax.set_title("Context-dependent topology effect")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=.22)
    fig.suptitle("Stage30a selected CPD4 solution verification\nfixed 216-grain periodic LBS; static mechanics-qualified F37 fibres", fontsize=14)
    OUT.mkdir(parents=True)
    image = OUT / "stage30a_selected_cpd4_verification.png"
    fig.savefig(image, dpi=220, facecolor="white")
    plt.close(fig)
    manifest = {"schema": "lbs.stage30a-selected-low-concentration-cpd4-render.v1", "passed": True,
    "status": "rendered_combined_selected_cpd4_solution_verification", "image": {"path": str(image), "sha256": sha(image)},
    "source_bindings": {"evaluation_sha256": sha(EVALUATION), "checkpoint_sha256": sha(CHECKPOINT)},
    "claim_boundary": evaluation["claim_boundary"]}
    (OUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
