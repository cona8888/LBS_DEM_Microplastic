"""Render the Stage127 parity-initializer diagnosis."""
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage127_staging"))
import parity_initializer_diagnosis_v1 as job
OUTPUT = job.EVAL / "render_01"


def main():
    result_path = job.EVAL / "independent_evaluation_01/results.json"
    r = job.read(result_path)
    raw = job.read(job.RUN / "stage127_cpd6_parity_average/result.json")
    rows = raw["rows"][-8:]
    out = OUTPUT
    out.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5))
    fig.suptitle("CPD6 one-time parity initializer: mechanism verified, cost gate missed", fontsize=20, weight="bold")
    axes[0].bar(["Stage126\nbefore", "Stage127\nafter"], [r["before_final_adjacent_field_change_relative_l2"], r["after_final_adjacent_field_change_relative_l2"]], color=["#c65f32", "#287b8e"])
    axes[0].axhline(5e-5, color="#222222", linestyle="--", label="required 5e-5")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Consecutive-field change (relative L2)")
    axes[0].set_title(f"One-step mode reduced {r['field_change_reduction_factor']:.0f}×")
    axes[0].legend(frameon=False)
    axes[1].plot([x["step"] for x in rows], [x["field_change_relative_l2"] for x in rows], "o-", color="#287b8e", label="field change")
    axes[1].axhline(5e-5, color="#222222", linestyle="--", label="required 5e-5")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("LBM step")
    axes[1].set_ylabel("Consecutive-field change (relative L2)")
    axes[1].set_title("Final eight consecutive states")
    axes[1].legend(frameon=False)
    fig.text(0.06, 0.105, f"Final change {r['after_final_adjacent_field_change_relative_l2']:.2e} | CPU fixed-point passed | force balance {r['steady_force_balance_relative']:.2e}", fontsize=12)
    fig.text(0.06, 0.065, f"Runtime {r['runtime_seconds']:.2f} s exceeded the frozen 300-s diagnostic gate. Mean remains {100*r['mean_relative_error']:+.2f}% from target.", fontsize=12, color="#9b3d22")
    fig.text(0.06, 0.025, "Diagnostic only: not a full flow solution, grid-convergence result, permeability validation or transport field.", fontsize=11, color="#555555")
    fig.tight_layout(rect=(0.03, 0.14, 0.98, 0.88))
    png, svg = out / "cpd6_parity_initializer.png", out / "cpd6_parity_initializer.svg"
    fig.savefig(png, dpi=180)
    fig.savefig(svg)
    plt.close(fig)
    job.write(out / "manifest.json", {"results": job.bind(result_path), "renderer": job.bind(__file__), "artifacts": {str(png): job.sha(png), str(svg): job.sha(svg)}})
    print(png, flush=True)


if __name__ == "__main__":
    main()
