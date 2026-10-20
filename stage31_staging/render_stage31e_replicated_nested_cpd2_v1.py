from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


EVALUATION = Path(r"C:\MATDEM_MICROPLASTIC\stage31_evaluations\stage31e_replicated_nested_cpd2_gpu_20260826\gpu_evaluation_01\evaluation.json")
COMPLETION = Path(r"C:\MATDEM_MICROPLASTIC\stage31_runs\stage31e_replicated_nested_cpd2_gpu_20260826\gpu_screen_01\completion.json")
DEFAULT_OUTPUT = Path(r"C:\MATDEM_MICROPLASTIC\stage31_renders\stage31e_replicated_nested_cpd2_gpu_20260826\result_render_02")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"immutable output already exists: {output}")
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    if not evaluation.get("passed") or not evaluation.get("authority", {}).get("render"):
        raise RuntimeError("verified evaluation does not authorize rendering")
    rows = evaluation["rows"]
    counts = np.array([1, 2, 4], dtype=float)
    colors = {"n216_s1": "#2A6FDB", "n216_s2": "#E05D32", "n216_s3": "#2E9D62"}
    styles = {"A": "-", "B": "--"}
    markers = {"A": "o", "B": "s"}

    def ratio(packing: str, block: str, count: int) -> float:
        return next(r["paired_permeability_ratio"] for r in rows
                    if r["packing_id"] == packing and r["placement_block"] == block and r["fibre_count"] == count)

    output.mkdir(parents=True)
    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.2))
    ax = axes[0, 0]
    for packing in colors:
        for block in ("A", "B"):
            values = [ratio(packing, block, int(c)) for c in counts]
            ax.plot(counts, values, styles[block], marker=markers[block], color=colors[packing],
                    linewidth=1.8, markersize=5.5, label=f"{packing[-2:]} / block {block}")
    ax.axhline(1.0, color="#555555", linewidth=1, linestyle=":")
    ax.set_title("A. All six matched trajectories")
    ax.set_xlabel("Fibre count (categorical levels)")
    ax.set_ylabel("Relative conductance, $G/G_{clean}$")
    ax.set_xticks(counts)
    ax.set_ylim(0.980, 1.0008)
    ax.grid(alpha=0.22)
    ax.legend(ncol=2, fontsize=8, frameon=False)

    ax = axes[0, 1]
    means, sds, mins, maxs = [], [], [], []
    for count in counts.astype(int):
        stats = evaluation["analysis"]["count_summaries"][str(count)]
        means.append(stats["mean_ratio"])
        sds.append(stats["sample_standard_deviation"])
        mins.append(stats["minimum_ratio"])
        maxs.append(stats["maximum_ratio"])
    means, sds, mins, maxs = map(np.asarray, (means, sds, mins, maxs))
    ax.fill_between(counts, mins, maxs, color="#77AADD", alpha=0.23, label="Observed min–max")
    ax.errorbar(counts, means, yerr=sds, color="#153B67", marker="o", linewidth=2,
                capsize=4, label="Mean ± sample SD")
    for x, mean in zip(counts, means):
        ax.annotate(f"{100*(1-mean):.3f}% reduction", (x, mean), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=8)
    ax.axhline(1.0, color="#555555", linewidth=1, linestyle=":")
    ax.set_title("B. Fibre-count effect and replicated spread")
    ax.set_xlabel("Fibre count (categorical levels)")
    ax.set_ylabel("Relative conductance, $G/G_{clean}$")
    ax.set_xticks(counts)
    ax.set_ylim(0.980, 1.001)
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 0]
    width = 0.22
    for offset, (packing, color) in zip((-width, 0.0, width), colors.items()):
        values = [np.mean([ratio(packing, block, int(c)) for block in ("A", "B")]) for c in counts]
        ax.bar(counts + offset, 100 * (1 - np.asarray(values)), width=width, color=color,
               label=packing[-2:], alpha=0.88)
    ax.set_title("C. Packing-blocked mean reduction")
    ax.set_xlabel("Fibre count (categorical levels)")
    ax.set_ylabel("Conductance reduction (%)")
    ax.set_xticks(counts)
    ax.grid(axis="y", alpha=0.22)
    ax.legend(title="Packing", frameon=False, fontsize=8)

    ax = axes[1, 1]
    for packing, color in colors.items():
        contrasts = [100 * (ratio(packing, "B", int(c)) - ratio(packing, "A", int(c))) for c in counts]
        ax.plot(counts, contrasts, marker="D", color=color, linewidth=1.8, label=packing[-2:])
    ax.axhline(0.0, color="#555555", linewidth=1, linestyle=":")
    ax.set_title("D. Nested placement-block contrast (B − A)")
    ax.set_xlabel("Fibre count (categorical levels)")
    ax.set_ylabel("Relative-conductance difference (percentage points)")
    ax.set_xticks(counts)
    ax.grid(alpha=0.22)
    ax.legend(title="Packing", frameon=False, fontsize=8)

    fig.suptitle("Stage31e replicated nested CPD2 hydraulic screen\n"
                 "Fixed solid; six ratios per nonzero count; no monotonicity imposed",
                 fontsize=15, fontweight="bold", y=0.985)
    fig.text(0.5, 0.018,
             "Observed result: all 6 packing/block trajectories decreased from 1 → 2 → 4 fibres. "
             "This is descriptive CPD2 relative-conductance evidence, not an absolute permeability validation.",
             ha="center", fontsize=9, color="#333333")
    fig.tight_layout(rect=(0.02, 0.065, 0.98, 0.91))
    png = output / "stage31e_replicated_nested_cpd2_summary.png"
    pdf = output / "stage31e_replicated_nested_cpd2_summary.pdf"
    fig.savefig(png, dpi=220, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "schema": "lbs.stage31e-replicated-nested-cpd2-render.v1",
        "status": "rendered_pending_visual_inspection",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "bindings": {"evaluation_sha256": sha256(EVALUATION), "completion_sha256": sha256(COMPLETION)},
        "artifacts": {
            "summary_png": str(png), "summary_png_sha256": sha256(png),
            "summary_pdf": str(pdf), "summary_pdf_sha256": sha256(pdf),
        },
        "claim_boundary": evaluation["claim_boundary"],
    }
    (output / "render_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
