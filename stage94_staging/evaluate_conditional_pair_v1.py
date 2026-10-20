"""Independently verify and render the completed conditional observation."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "stage94_runs/verified_near_outlet_pair_20260913/pair_01"
OLD = ROOT / "stage86_runs/near_outlet_conditional_20260913/seed2_pair_01"
TRANSFER = ROOT / "stage93_evaluations/near_outlet_original_start_01/results.json"
OUT = ROOT / "stage94_evaluations/conditional_pair_review_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    record = json.loads((RUN / "results.json").read_text())
    completion = json.loads((RUN / "completion.json").read_text())
    if completion["status"] != "complete_passed" or completion["results_sha256"] != sha(RUN / "results.json"):
        raise RuntimeError("paired simulation completion failed")
    count = 0
    for section in ("input_hashes", "source_hashes", "artifact_hashes"):
        for path, digest in record[section].items():
            if sha(path) != digest:
                raise RuntimeError(f"immutable binding failed: {path}")
            count += 1
    if len(record["rows"]) != 2 or not record["passed"]:
        raise RuntimeError("incomplete pair")
    config_path = ROOT / "stage86_designs/near_outlet_conditional_pilot_v1.json"
    config = json.loads(config_path.read_text())
    horizon = record["horizon_s"]
    length = horizon*config["target_mean_interstitial_velocity_m_s"]/.1
    start_path = ROOT / "stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s2.json"
    start = next(row for row in json.loads(start_path.read_text()) if row["id"] == 47)
    summary = []
    for row in record["rows"]:
        result = row["result"]
        resolved = ((result["status"] == "present_at_horizon" and abs(result["time_s"]-horizon) <= 1e-12)
                    or (result["status"] == "full_window_exit" and 0 < result["time_s"] <= horizon))
        valid = [resolved, result["minimum_gap_m"] >= -5e-10,
                 result["max_contact_residual"] <= 1e-8, result["max_force_residual"] <= 1e-8,
                 result["max_momentum_residual"] <= 1e-8, result["max_reynolds"] <= 3,
                 result["runtime_seconds"] <= 600., result["dwell_is_absorbing"] is False]
        if not all(valid):
            raise RuntimeError(f'case verification failed: {row["shape"]}')
        a, b, _ = config["prolate_semiaxes_m"]
        if row["shape"] == "equal_volume_sphere":
            a = b = (a*b*b)**(1/3)
        px = float(result["orientation"][0])
        remaining = length + np.sqrt(b*b+(a*a-b*b)*px*px)-result["position_m"][0]
        summary.append({"shape": row["shape"], "status": result["status"],
                        "first_passage_observed": result["status"] == "full_window_exit",
                        "time_s": result["time_s"], "runtime_s": result["runtime_seconds"],
                        "remaining_whole_body_exit_distance_m": float(remaining),
                        "finite_dwell_observed": bool(result["persistent_contact_observed"]),
                        "native_first_contact_dwell_time_s": result["first_contact_dwell_time_s"],
                        "steps": result["steps"], "rejected": result["rejected"]})
    sphere = next(r["result"] for r in record["rows"] if r["shape"] == "equal_volume_sphere")
    old_sphere_path = OLD / "s2_equal_volume_sphere.json"
    old_sphere = json.loads(old_sphere_path.read_text())["result"]
    sphere_diff = {key: float(np.max(np.abs(np.asarray(sphere[key])-np.asarray(old_sphere[key]))))
                   for key in ("position_m", "orientation", "velocity_generalized")}
    transfer = json.loads(TRANSFER.read_text())
    old_fibre_path = OLD / "s2_prolate_ar4.json"
    old_fibre = json.loads(old_fibre_path.read_text())["result"]
    speedup = old_fibre["runtime_seconds"]/transfer["runtime_s"]
    OUT.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), gridspec_kw={"width_ratios": [1.5, 1]})
    colors = {"equal_volume_sphere": "#147d92", "prolate_ar4": "#b55d30"}
    labels = {"equal_volume_sphere": "Sphere", "prolate_ar4": "AR4 fibre"}
    for row in record["rows"]:
        r = row["result"]
        a, b, _ = config["prolate_semiaxes_m"]
        if row["shape"] == "equal_volume_sphere":
            a = b = (a*b*b)**(1/3)
        samples = [[0., *start["position_m"], *start["orientation"]]]
        samples += [h[:7] for h in r["history"]]
        samples += [[r["time_s"], *r["position_m"], *r["orientation"]]]
        data = np.asarray(samples)
        gap = length+np.sqrt(b*b+(a*a-b*b)*data[:,4]**2)-data[:,1]
        axes[0].plot(data[:,0]/horizon*.1, gap*1e6, color=colors[row["shape"]],
                     lw=2, marker="o", markersize=3, label=labels[row["shape"]])
    axes[0].axhline(0, color="#333333", lw=1, ls="--", label="Whole-body exit")
    axes[0].axvline(old_fibre["time_s"]/horizon*.1, color="#888888", ls=":", lw=1.4)
    axes[0].text(old_fibre["time_s"]/horizon*.1+.002, .97,
                 "Old fibre cutoff", transform=axes[0].get_xaxis_transform(),
                 fontsize=9, va="top", color="#666666")
    axes[0].set(xlabel="Elapsed pore volumes", ylabel="Remaining whole-body exit distance (µm)",
                title="A  Sampled transport history", xlim=(0,.102))
    axes[0].legend(loc="lower left", frameon=False, fontsize=9)
    axes[0].grid(alpha=.16)
    bars = axes[1].barh([1,0], [old_fibre["runtime_seconds"], transfer["runtime_s"]],
                        height=.5, color=["#969fa8", "#147d92"])
    axes[1].set_yticks([1,0], ["Original", "64-sweep seed"])
    axes[1].set(xlabel="CPU wall time (s)", title="B  Cost to the same physical time",
                xlim=(0,old_fibre["runtime_seconds"]*1.22), ylim=(-.7,1.7))
    for bar, value in zip(bars, [old_fibre["runtime_seconds"],transfer["runtime_s"]]):
        axes[1].text(value+8, bar.get_y()+bar.get_height()/2, f"{value:.1f} s", va="center")
    axes[1].text(.98, .98, f"{speedup:.1f}× faster\nMatched time: {old_fibre['time_s']:.3f} s",
                 ha="right", va="top", transform=axes[1].transAxes, fontsize=10)
    axes[1].spines[["top","right"]].set_visible(False)
    axes[0].spines[["top","right"]].set_visible(False)
    fig.suptitle("Resolved near-outlet conditional pair | fixed sand, one-way flow", fontsize=14, y=.99)
    fig.text(.02,.018,"One selected start in packing 2; numerical observation only. Finite dwell does not establish permanent retention.", fontsize=9)
    fig.tight_layout(rect=(0,.065,1,.94))
    figure = OUT / "conditional_pair.png"
    fig.savefig(figure, dpi=180)
    plt.close(fig)
    result = {"passed": True, "verified_bindings": count, "summary": summary,
              "sphere_max_component_changes_vs_stage86": sphere_diff,
              "matched_cutoff_speedup": speedup,
              "input_hashes": {str(p): sha(p) for p in (
                  RUN / "results.json", TRANSFER, old_fibre_path, old_sphere_path, config_path, start_path)},
              "source_hashes": {str(Path(__file__)): sha(__file__)},
              "figure_sha256": sha(figure),
              "claim_boundary": record["claim_boundary"]}
    path = OUT / "results.json"
    path.write_text(json.dumps(result, indent=2))
    (OUT / "completion.json").write_text(json.dumps({"status": "complete_evaluated", "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"summary": summary, "sphere_differences": sphere_diff, "speedup": speedup}, indent=2))


if __name__ == "__main__":
    main()
