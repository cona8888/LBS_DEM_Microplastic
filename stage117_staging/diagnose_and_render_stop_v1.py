"""Source-backed failure-branch diagnosis and graphic; no transport execution."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import longer_sentinels_v1 as job
import audit_stopped_matrix_v1 as audit
api = job.api
OUT = job.EVAL / "stop_render_01"


def main():
    source = audit.OUT / "results.json"
    r = api.read(source)
    api.require(api.read(audit.OUT / "completion.json")["results_sha256"] == api.sha(source), "audit drift")
    api.verify_mapping(r["artifact_hashes"])
    api.require(not OUT.exists(), "immutable render exists")
    detail = r["failure_detail"]
    final_dir = job.RUN / detail["case_id"] / "segment_02"
    prior = api.read(final_dir.parent / "segment_01/record.json")["result"]
    last = api.read(final_dir / "record.json")["result"]
    retry_delta = last["contact_solver_retries"] - prior["contact_solver_retries"]
    reject_delta = last["rejected"] - prior["rejected"]
    diagnosis = {"cause_class": "contact_solver_retry_exhaustion", "solver_retry_delta": retry_delta, "all_rejection_delta": reject_delta,
        "last_segment_accepted_steps": last["steps"] - prior["steps"],
        "swept_gap_calls_last_segment": last["fail_fast_sweep_stats"]["calls"],
        "evidence": "The frozen core increments contact_solver_retries only in the caught contact-solver RuntimeError branch. All 30 rejections in the failed segment were solver retries, and only seven swept checks were called for seven accepted intervals. The generic final message is not evidence that geometric clearance caused the failure.",
        "specific_solver_exception": "Not archived by the frozen core; direct residual/normal-force/cone or inertial fixed-point error cannot be distinguished without a new local diagnostic.",
        "not_proven": ["Which contact solver exception occurred", "Whether near-endpoint dt triggered conditioning", "Whether a different solver or timestep completes the query"],
        "next_action": "Read-only local contact-system capture/replay at the source-bound failed episode, with per-retry exception and conditioning evidence, before any solver revision. Do not drop the seed-1 sphere/fibre or loosen force/clearance gates.",
        "core_sha256": api.sha(api.frozen.core.__file__), "audit_sha256": api.sha(source), "script_sha256": api.sha(__file__)}
    api.require(retry_delta == reject_delta == 30, "unexpected rejection classification")
    OUT.mkdir(parents=True)
    api.write(OUT / "branch_diagnosis.json", diagnosis)
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.7), gridspec_kw={"width_ratios": [1.2, 1.35, 1.2]})
    fig.subplots_adjust(top=.70, bottom=.23, left=.08, right=.98, wspace=.53)
    fig.suptitle("Stage117 | Longer test stopped at a numerical limit", x=.055, y=.96, ha="left", fontsize=18, weight="bold")
    fig.text(.055, .86, "0.5-s target  |  Original paired sphere / AR4 starts  |  Contact physics unchanged", fontsize=12)
    fig.text(.055, .79, "1 complete  +  2 budget-incomplete  +  1 numerical failure  +  14 not run", fontsize=13, weight="bold", color="#8e392e")
    ax = axes[0]
    counts = [1, 2, 1, 14]
    colors = ["#267f83", "#d8a23a", "#bb4c3b", "#b7bfc8"]
    labels = ["Complete", "Budget limit", "Numerical failure", "Not run"]
    ax.barh(range(4), counts, color=colors)
    ax.set_yticks(range(4), labels, fontsize=10)
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
    lines = ["t = 0.499995 s", "Three touching grains", "30 / 30 rejected attempts:", "contact-solver exceptions", "", "Last accepted state is healthy.", "No complete timestep triplet.", "No release / retention claim.", "", "Next: local solver diagnosis."]
    ax.text(0, .86, "\n".join(lines), fontsize=10.5, va="top", linespacing=1.45)
    for ax in axes[:2]:
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(.055, .06, "Budget checks occur between accepted steps; expensive internal retries can exceed the nominal 45-s segment threshold.", fontsize=10)
    fig.savefig(OUT / "longer_test_stop.png", dpi=160)
    fig.savefig(OUT / "longer_test_stop.svg")
    plt.close(fig)
    api.write(OUT / "manifest.json", {"audit_sha256": api.sha(source), "renderer_sha256": api.sha(__file__),
        "artifacts": {str(p): api.sha(p) for p in OUT.iterdir() if p.is_file()}})
    print(diagnosis)
    print(OUT)


if __name__ == "__main__":
    main()
