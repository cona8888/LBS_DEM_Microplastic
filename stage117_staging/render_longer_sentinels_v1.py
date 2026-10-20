"""Render saved results only; no interpolation of incomplete trajectories."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import longer_sentinels_v1 as job
import evaluate_longer_sentinels_v1 as evaluation
api = job.api
OUT = job.EVAL / "render_01"


def main():
    source = evaluation.OUT / "results.json"
    r = api.read(source)
    api.require(api.read(evaluation.OUT / "completion.json")["results_sha256"] == api.sha(source), "evaluation drift")
    api.require(not OUT.exists(), "immutable render exists")
    OUT.mkdir(parents=True)
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9))
    fig.subplots_adjust(top=.84, bottom=.12, left=.075, right=.98, hspace=.5, wspace=.27)
    fig.suptitle("Longer paired transport check | 0.5 s", fontsize=20, fontweight="bold", x=.075, ha="left", y=.965)
    fig.text(.075, .91, f"{r['complete_queries']}/18 completed queries  |  {r['passing_triplets']}/6 timestep triplets pass  |  integration cost {r['integration_cost_s']/60:.1f} min", fontsize=13)
    labels = [f"S{g['seed']} / CPD{g['cpd']}\n{'Sphere' if g['shape']==job.api.SHAPES[0] else 'AR4 fibre'}" for g in r["three_level_groups"]]
    x = np.arange(len(labels))
    for ax, key, limit, title in [(axes[0, 0], "position_difference_over_b", .02, "Fine-medium position difference / minor radius"),
                                 (axes[0, 1], "translational_velocity_relative_difference", .05, "Fine-medium relative velocity difference")]:
        values = [g.get("medium_fine", {}).get(key, np.nan) for g in r["three_level_groups"]]
        ax.bar(x, values, color=["#197f85" if np.isfinite(v) and v <= limit else "#bd4934" for v in values])
        ax.axhline(limit, ls="--", color="#333333", label=f"Gate {limit:g}")
        ax.set_xticks(x, labels, fontsize=9)
        ax.set_title(title, fontsize=11)
        ax.legend(frameon=False, fontsize=9)
        for i, v in enumerate(values):
            if np.isfinite(v):
                ax.text(i, v, f"{v:.4f}", ha="center", va="bottom", fontsize=9)
            else:
                ax.text(i, 0, "incomplete", rotation=90, fontsize=8)
        ax.margins(y=.22)
    ax = axes[1, 0]
    width = .23
    for j in range(3):
        costs = [r["case_ledger"][g["case_ids"][j]]["integrator_runtime_s"] for g in r["three_level_groups"]]
        ax.bar(x + (j-1)*width, costs, width=width, label=["coarse", "medium", "fine"][j], color=["#b9d1d5", "#60979e", "#235e6c"][j])
    ax.set_xticks(x, labels, fontsize=9)
    ax.set_ylabel("Measured integration seconds")
    ax.set_title("Actual cost, including bounded checkpoint segments", fontsize=11)
    ax.legend(frameon=False, ncol=3, fontsize=9)
    ax = axes[1, 1]
    ax.axis("off")
    lines = ["What this test establishes", ""]
    lines += [f"- {sum(v['health_passed'] for v in r['case_ledger'].values())}/18 cases pass numerical-health checks.",
              "- Contact/dwell sampled at every accepted step.",
              "- Same physics, original starts, fixed compute caps.", "", "Still not established", "", "- Whole-matrix release fraction or irreversible trapping.", "- Full-path time/spatial accuracy or 2-PV cost.", "- Experimental validation or fibre flexibility."]
    ax.text(0, 1, "\n".join(lines), va="top", fontsize=11, linespacing=1.45)
    fig.text(.075, .045, "CPD2/CPD4 comparison retains each solved mean speed. Numerical gate failures are preserved; no population run authorized.", fontsize=10)
    for ax in axes.flat:
        if ax.axison:
            ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(OUT / "longer_paired_diagnostics.png", dpi=160)
    fig.savefig(OUT / "longer_paired_diagnostics.svg")
    plt.close(fig)
    api.write(OUT / "manifest.json", {"source_sha256": api.sha(source), "renderer_sha256": api.sha(__file__),
        "artifacts": {str(p): api.sha(p) for p in OUT.glob("longer_paired_diagnostics.*")}})
    print(OUT)


if __name__ == "__main__":
    main()
