from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage31f_selected_replicated_cpd4_20260827"
EVAL_DIR = ROOT / "stage31_evaluations" / STUDY / "gpu_evaluation_02"
EVALUATION = EVAL_DIR / "evaluation.json"
CHECKPOINT = EVAL_DIR / "checkpoint_manifest.json"
OUT = ROOT / "stage31_renders" / STUDY / "cpd4_verification_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if not (evaluation.get("passed") and evaluation["authority"]["rendering"] and checkpoint.get("passed")):
        raise RuntimeError("independent Stage31f checkpoint does not authorize rendering")

    rows = evaluation["paired_results"]
    labels = []
    for row in rows:
        if row["fibre_count"] == 0:
            labels.append("s2 clean")
        else:
            labels.append(f"s{row['packing_id'][-1]} {row['placement_block']} · {row['fibre_count']} fibre" + ("s" if row["fibre_count"] != 1 else ""))
    cpd2 = np.array([row["cpd2_ratio"] for row in rows])
    cpd4 = np.array([row["paired_permeability_ratio"] for row in rows])
    shifts = cpd4 - cpd2
    positions = np.arange(len(rows))
    colors = ["#555555", "#2d72b8", "#4f92ce", "#77add8", "#ec8a62", "#5aaa67", "#d65f59"]

    fig, axes = plt.subplots(1, 3, figsize=(16.4, 5.5), constrained_layout=True)
    ax = axes[0]
    ax.scatter(positions - 0.09, cpd2, marker="o", s=66, color=colors, edgecolor="black", linewidth=.35, label="CPD2")
    ax.scatter(positions + 0.09, cpd4, marker="s", s=66, color=colors, edgecolor="black", linewidth=.35, label="CPD4")
    for i in positions:
        ax.plot([i - .09, i + .09], [cpd2[i], cpd4[i]], color=colors[i], linewidth=1.4)
    ax.axhline(1.0, color="#555555", linestyle="--", linewidth=1)
    ax.set_xticks(positions, labels, rotation=30, ha="right")
    ax.set_ylabel("Paired permeability ratio, k/k₀")
    ax.set_title("Selected replicated responses")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=.22)

    ax = axes[1]
    ax.bar(positions, 1e4 * shifts, color=colors)
    ax.axhline(0.0, color="#555555", linewidth=1)
    ax.axhline(20.0, color="#a33", linestyle="--", linewidth=1, label="±0.002 gate")
    ax.axhline(-20.0, color="#a33", linestyle="--", linewidth=1)
    ax.set_xticks(positions, labels, rotation=30, ha="right")
    ax.set_ylabel("10⁴ × (CPD4 − CPD2) in k/k₀")
    ax.set_title("Resolution shift")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=.22)

    ax = axes[2]
    contrasts = evaluation["contrasts"]
    names = ["Packing s1", "Packing s2"]
    c2 = [contrasts[key]["cpd2_B_minus_A"] for key in ("n216_s1", "n216_s2")]
    c4 = [contrasts[key]["cpd4_B_minus_A"] for key in ("n216_s1", "n216_s2")]
    x = np.arange(2)
    width = .34
    ax.bar(x - width / 2, 100 * np.array(c2), width, color="#8c8c8c", label="CPD2")
    ax.bar(x + width / 2, 100 * np.array(c4), width, color="#8a57b5", label="CPD4")
    ax.axhline(0.0, color="#555555", linewidth=1)
    ax.set_xticks(x, names)
    ax.set_ylabel("Four-fibre B − A contrast in k/k₀ (%)")
    ax.set_title("Packing-dependent placement effect")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=.22)

    fig.suptitle(
        "Stage31f replicated CPD4 solution verification\n"
        "fixed-solid periodic LBS; count trend and opposite placement-block signs retained",
        fontsize=14,
    )
    OUT.mkdir(parents=True)
    image = OUT / "stage31f_selected_replicated_cpd4_verification.png"
    fig.savefig(image, dpi=220, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage31f-selected-replicated-cpd4-render.v1",
        "passed": True,
        "status": "rendered_selected_replicated_cpd4_solution_verification",
        "image": {"path": str(image), "sha256": sha(image)},
        "source_bindings": {"evaluation_sha256": sha(EVALUATION), "checkpoint_sha256": sha(CHECKPOINT)},
        "claim_boundary": evaluation["claim_boundary"],
    }
    (OUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
