from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage34c_cpd4_first_fragmentation_geometry_20260902"
EVALUATION = ROOT / "stage34_evaluations" / STUDY / "gpu_evaluation_02" / "evaluation.json"
OUT = ROOT / "stage34_renders" / STUDY / "fragmentation_cpd4_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable render: {OUT}")
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    if evaluation.get("passed") is not True or evaluation["authority"].get("rendering") is not True:
        raise RuntimeError("independent evaluation does not authorize rendering")

    contexts = ["n216_s1_A", "n216_s1_B", "n216_s2_A", "n216_s2_B"]
    labels = ["Packing s1 · block A", "Packing s1 · block B", "Packing s2 · block A", "Packing s2 · block B"]
    colors = ["#176B87", "#64CCC5", "#7A3E9D", "#D16D9E"]
    markers = ["o", "s", "^", "D"]
    states = np.array([1, 2, 3], dtype=float)
    contrasts = evaluation["contrasts"]
    threshold = evaluation["cross_context_sign_concordance"]["frag2_minus_frag1"]["practical_threshold_absolute_ratio"]

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "legend.fontsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 6.4), gridspec_kw={"width_ratios": [1.08, 1.0]})
    fig.patch.set_facecolor("white")

    for context, label, color, marker in zip(contexts, labels, colors, markers):
        row = contrasts[context]
        y = [row["frag1_intact_ratio"], row["frag2_ratio"], row["frag3_ratio"]]
        ax1.plot(states, y, color=color, marker=marker, markersize=7, linewidth=2.0, label=label)
    ax1.axhline(1.0, color="#343A40", linewidth=1.2, linestyle="--", label="Matched clean control")
    ax1.set_xticks(states, ["Intact", "Split into 2", "Split into 3"])
    ax1.set_ylabel(r"Paired permeability ratio, $K/K_0$")
    ax1.set_title("A  Context-matched CPD4 response", loc="left", fontweight="bold")
    ax1.grid(axis="y", color="#DDE2E5", linewidth=0.8)
    ax1.set_ylim(0.979, 1.0015)
    ax1.legend(loc="lower right", frameon=False)

    names = ["frag2_minus_frag1", "frag3_minus_frag1", "frag3_minus_frag2"]
    pretty = ["Split 2 − intact", "Split 3 − intact", "Split 3 − split 2"]
    x = np.arange(len(names), dtype=float)
    offsets = np.linspace(-0.27, 0.27, len(contexts))
    for offset, context, label, color, marker in zip(offsets, contexts, labels, colors, markers):
        values = [contrasts[context][name] for name in names]
        ax2.scatter(x + offset, values, s=58, marker=marker, color=color, edgecolor="white", linewidth=0.7, zorder=3, label=label)
    ax2.axhline(0.0, color="#343A40", linewidth=1.1)
    ax2.axhline(threshold, color="#C0392B", linewidth=1.0, linestyle="--")
    ax2.axhline(-threshold, color="#C0392B", linewidth=1.0, linestyle="--")
    ax2.fill_between([-0.55, 2.55], -threshold, threshold, color="#F5E8E6", alpha=0.55, zorder=0)
    ax2.set_xlim(-0.55, 2.55)
    ax2.set_xticks(x, pretty, rotation=13, ha="right")
    ax2.set_ylabel(r"Contrast in $K/K_0$")
    ax2.set_title("B  Fragmentation contrasts across contexts", loc="left", fontweight="bold")
    ax2.grid(axis="y", color="#DDE2E5", linewidth=0.8)
    ax2.text(2.50, threshold + 0.00025, "practical threshold ±0.005", ha="right", va="bottom", color="#9B2C20", fontsize=9)

    fig.suptitle("Fixed-volume idealized PET fragmentation: hydraulic sensitivity is context-dependent", fontsize=15, fontweight="bold", x=0.5, y=0.985)
    fig.text(
        0.5, 0.015,
        "Independent CPD4 evaluation · 4 matched packing/placement contexts · points are deterministic case outcomes\n"
        "Signs are not imposed. Only 1/4 split-vs-intact effects exceeds |ΔK/K₀| = 0.005; no split-3-vs-split-2 effect does.",
        ha="center", va="bottom", fontsize=9.5, color="#343A40",
    )
    fig.tight_layout(rect=(0.03, 0.09, 0.99, 0.94), w_pad=3.2)

    OUT.mkdir(parents=True)
    png = OUT / "stage34c_fragmentation_cpd4_context_effects.png"
    svg = OUT / "stage34c_fragmentation_cpd4_context_effects.svg"
    fig.savefig(png, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    manifest = {
        "schema": "lbs.stage34c-fragment-cpd4-render.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "evaluation": {"path": str(EVALUATION), "sha256": sha(EVALUATION)},
        "artifacts": {
            png.name: sha(png),
            svg.name: sha(svg),
        },
        "visual_message": "Fragmentation-state effects vary with packing and placement; the evidence does not support a universal monotonic length-degradation law.",
        "claim_boundary": evaluation["claim_boundary"],
        "authority": {
            "visual_inspection": True,
            "cpd6_flow_execution": False,
            "absolute_permeability_validation_claim": False,
            "chemical_degradation_claim": False,
            "mechanics_rerun": False,
            "mobile_sand": False,
            "migration": False,
            "clogging": False,
            "deformation": False,
            "transient_coupling": False,
            "two_way_coupling": False,
        },
    }
    manifest_path = OUT / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "png": str(png), "png_sha256": sha(png), "passed": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
