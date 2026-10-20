"""Render the fixed-pose timestep/conditioning diagnosis from saved evidence."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import evaluate_probe_v1 as evaluation
job = evaluation.job
api = job.api
OUT = job.EVAL / "render_01"


def main():
    source = evaluation.OUT / "results.json"
    r = api.read(source)
    api.require(api.read(evaluation.OUT / "completion.json")["results_sha256"] == api.sha(source), "evaluation drift")
    api.require(not OUT.exists(), "immutable render exists")
    OUT.mkdir(parents=True)
    rows = sorted([v for v in r["ledger"] if v["scenario"] != "accepted_control"], key=lambda v: v["dt_s"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5))
    fig.subplots_adjust(left=.09, right=.97, bottom=.29, top=.72, wspace=.3)
    fig.suptitle("Stage118 | Failure isolated to a local endpoint-step interaction", x=.055, y=.95, ha="left", fontsize=17, weight="bold")
    fig.text(.055, .86, "Same saved fibre pose and three contacts. Six local solves; no trajectory advanced.", fontsize=12)
    fig.text(.055, .80, "Previously accepted step reproduced exactly. Original force, friction and residual gates retained.", fontsize=11)
    for row in rows:
        passed = row["status"] == "solver_returned"
        color = "#257f83" if passed else "#bb4b36"
        marker = "o" if passed else "X"
        dt = row["dt_s"]*1e6
        axes[0].scatter(dt, row["verification"]["system_condition_2"], color=color, marker=marker, s=90, zorder=3)
        axes[1].scatter(dt, max(abs(v) for v in row["verification"]["gap_over_dt_m_s"]), color=color, marker=marker, s=90, zorder=3)
    for ax in axes:
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Local trial step (microseconds, log scale)")
        ax.grid(alpha=.2, which="major")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Generalized-system condition number")
    axes[0].set_title("Step halving worsens conditioning", fontsize=12)
    axes[1].set_ylabel("Maximum |gap / step| (m/s)")
    axes[1].set_title("Near-zero geometry gaps are amplified", fontsize=12)
    ax = axes[0]
    endpoint = next(row for row in rows if row["scenario"] == "failed_remaining")
    accepted = next(row for row in rows if row["scenario"] == "failed_without_endpoint_clip")
    ax.annotate("Endpoint: 5.409 microseconds\nresidual nonconvergence", (endpoint["dt_s"]*1e6, endpoint["verification"]["system_condition_2"]), xytext=(.49, .65), textcoords="axes fraction", fontsize=9, arrowprops={"arrowstyle": "->", "color": "#666666"})
    ax.annotate("Unclipped: 788 microseconds\nlocal solver passes", (accepted["dt_s"]*1e6, accepted["verification"]["system_condition_2"]), xytext=(.49, .27), textcoords="axes fraction", fontsize=9, arrowprops={"arrowstyle": "->", "color": "#666666"})
    fig.text(.09, .17, "Red crosses: rejected local solves. Teal circle: solver return passing the unchanged independent gates.", fontsize=10)
    fig.text(.09, .11, "The unclipped candidate is NOT an endpoint fix: it would extend beyond the requested query time.", fontsize=10, weight="bold")
    fig.text(.09, .06, "Conditioning is diagnostic evidence, not proof of the sole cause. No release or retention conclusion.", fontsize=10)
    fig.savefig(OUT / "endpoint_contact_diagnosis.png", dpi=160)
    fig.savefig(OUT / "endpoint_contact_diagnosis.svg")
    plt.close(fig)
    api.write(OUT / "manifest.json", {"source_sha256": api.sha(source), "renderer_sha256": api.sha(__file__), "artifacts": {str(p): api.sha(p) for p in OUT.glob("endpoint_contact_diagnosis.*")}})
    print(OUT, api.sha(OUT / "endpoint_contact_diagnosis.png"))


if __name__ == "__main__":
    main()
