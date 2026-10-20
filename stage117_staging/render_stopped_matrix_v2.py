"""Second immutable layout; correct the left-label clipping in render 01."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import longer_sentinels_v1 as job
import audit_stopped_matrix_v1 as audit
api = job.api
OUT = job.EVAL / "stop_render_02"


def main():
    source = audit.OUT / "results.json"
    r = api.read(source)
    api.require(api.read(audit.OUT / "completion.json")["results_sha256"] == api.sha(source), "audit drift")
    api.require(not OUT.exists(), "immutable render exists")
    OUT.mkdir(parents=True)
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.7), gridspec_kw={"width_ratios": [1.2, 1.35, 1.2]})
    fig.subplots_adjust(top=.70, bottom=.23, left=.11, right=.98, wspace=.52)
    fig.suptitle("Stage117 | Longer test stopped at a numerical limit", x=.055, y=.96, ha="left", fontsize=18, weight="bold")
    fig.text(.055, .86, "0.5-s target  |  Original paired sphere / AR4 starts  |  Contact physics unchanged", fontsize=12)
    fig.text(.055, .79, "1 complete  +  2 budget-incomplete  +  1 numerical failure  +  14 not run", fontsize=13, weight="bold", color="#8e392e")
    colors = ["#267f83", "#d8a23a", "#bb4c3b", "#b7bfc8"]
    ax = axes[0]
    counts = [1, 2, 1, 14]
    ax.barh(range(4), counts, color=colors)
    ax.set_yticks(range(4), ["Complete", "Budget limit", "Numerical\nfailure", "Not run"], fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Frozen cases (18 total)")
    ax.set_xlim(0, 16)
    for i, v in enumerate(counts):
        ax.text(v+.2, i, str(v), va="center")
    ax.set_title("All cases accounted for", fontsize=12)
    attempted = [v for v in r["ledger"] if v["segments"]]
    ax = axes[1]
    ax.bar(range(4), [v["runtime_s"] for v in attempted], color=[colors[1], colors[0], colors[1], colors[2]])
    ax.set_xticks(range(4), ["Sphere\nbase", "Sphere\nhalf caps", "Sphere\nquarter caps", "Fibre\nbase"], fontsize=9)
    ax.set_ylabel("Measured integration time (s)")
    ax.set_title("Original seed-1 sentinel", fontsize=12)
    ax.margins(y=.18)
    for i, v in enumerate(attempted):
        ax.text(i, v["runtime_s"]+2, f"{v['runtime_s']:.1f}", ha="center", fontsize=10)
    ax = axes[2]
    ax.axis("off")
    ax.text(0, 1, "Failure location", weight="bold", fontsize=12, va="top")
    ax.text(0, .86, "t = 0.499995 s\nThree touching grains\n30 / 30 rejected attempts:\ncontact-solver exceptions\n\nLast accepted state is healthy.\nNo complete timestep triplet.\nNo release / retention claim.\n\nNext: local solver diagnosis.", fontsize=10.5, va="top", linespacing=1.45)
    for ax in axes[:2]:
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(.055, .06, "Budget checks occur between accepted steps; expensive internal retries can exceed the nominal 45-s segment threshold.", fontsize=10)
    fig.savefig(OUT / "longer_test_stop.png", dpi=160)
    fig.savefig(OUT / "longer_test_stop.svg")
    plt.close(fig)
    api.write(OUT / "manifest.json", {"audit_sha256": api.sha(source), "renderer_sha256": api.sha(__file__),
        "branch_diagnosis_sha256": api.sha(job.EVAL / "stop_render_01/branch_diagnosis.json"),
        "supersedes_layout_only": "stop_render_01: left numerical-failure label clipped; evidence and conclusions unchanged.",
        "artifacts": {str(p): api.sha(p) for p in OUT.glob("longer_test_stop.*")}})
    print(OUT, api.sha(OUT / "longer_test_stop.png"))


if __name__ == "__main__":
    main()
