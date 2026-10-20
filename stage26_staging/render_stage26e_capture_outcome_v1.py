"""Render Stage26e development success and held-out non-equilibration."""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from render_stage26d_confirmation_v1 import gate_utilization, load_history


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "stage26_checkpoints/stage26e_qualified_state_capture_20260816/final_outcome_checkpoint_01/checkpoint_manifest.json"
OUT = ROOT / "stage26_renders/stage26e_qualified_state_capture_20260816/final_outcome_render_01"
DEV = ROOT / "stage26_runs/stage26e_qualified_state_capture_20260816/development_01/revision3_candidate05"
HELD = ROOT / "stage26_runs/stage26e_qualified_state_capture_20260816/heldout_01/revision3_candidate07"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    assert checkpoint["passed"] is True
    assert checkpoint["authority"]["diagnostic_render_authorized"] is True
    assert checkpoint["authority"]["free_release_authorized"] is False
    assert checkpoint["status"] == "development_capture_passed_but_heldout_capture_failed"
    dev_history_path = DEV / "fixed_capture_history.csv"
    held_history_path = HELD / "fixed_capture_history.csv"
    assert digest(dev_history_path) == "97709c50856d870a6c9912ab2126150eb04ea0ada98b2f349604a2b3c1225aae"
    assert digest(held_history_path) == checkpoint["heldout"]["history_sha256"]
    assert digest(HELD / "heldout_evaluation_v1.json") == checkpoint["heldout"]["evaluation_sha256"]
    dev = load_history(dev_history_path)
    held = load_history(held_history_path)
    dev_window = checkpoint["development"]["captured_window"]
    held_best = checkpoint["heldout"]["longest_passing_streak"][:2]

    OUT.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(2, 2, figsize=(14, 11), constrained_layout=False)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.075, top=0.86, wspace=0.22, hspace=0.30)
    cases = (
        (axes[0, 0], dev, "candidate05 development — captured", "#006ba4", dev_window, "first qualifying window"),
        (axes[0, 1], held, "candidate07 held out — no capture", "#cc2529", held_best, "longest streak: 8/10 blocks"),
    )
    for ax, rows, title, color, span, span_label in cases:
        blocks = [row["block"] for row in rows]
        ax.step(blocks, [min(row["contacts"]) for row in rows], where="mid", color=color,
                linewidth=1.5, label="minimum sand contacts/fibre")
        ax.step(blocks, [min(row["anchors"]) for row in rows], where="mid", color="#3e9651",
                linewidth=1.1, linestyle="--", label="minimum declared anchors/fibre")
        ax.axhline(2, color="black", linewidth=0.9, linestyle=":", label="equilibrium contact/anchor gate")
        ax.axvspan(span[0] - 0.5, span[1] + 0.5, color="#8dd3c7" if color == "#006ba4" else "#fdb462",
                   alpha=0.42, label=span_label)
        ax.set(xlim=(1, 300), ylim=(-0.1, 4.2), ylabel="Minimum count per fibre", title=title)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, loc="lower right")

    ax = axes[1, 0]
    for rows, label, color in ((dev, "candidate05 development", "#006ba4"), (held, "candidate07 held out", "#cc2529")):
        ax.plot([row["block"] for row in rows], [gate_utilization(row) for row in rows],
                linewidth=1.15, color=color, label=label)
    ax.axvspan(dev_window[0] - 0.5, dev_window[1] + 0.5, color="#006ba4", alpha=0.10)
    ax.axvspan(held_best[0] - 0.5, held_best[1] + 0.5, color="#cc2529", alpha=0.10)
    ax.axhline(1, color="black", linestyle="--", linewidth=1.0, label="sand-health boundary")
    ax.set_yscale("log")
    ax.set(xlim=(1, 300), ylim=(0.5, 100), xlabel="Fixed-conditioning block (500 YADE steps)",
           ylabel="Largest normalized sand-health demand", title="Full health-gate demand (<= 1 passes)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    ax.axis("off")
    ax.text(0.02, 0.94, "Frozen Stage26e conclusion", fontsize=15, weight="bold", va="top")
    ax.text(0.02, 0.80,
            "candidate05 development\n"
            "  captured blocks 149–158 (10/10)\n"
            "  state structurally reloadable\n"
            "  state remains non-release-ready",
            fontsize=12, va="top", color="#004c6d")
    ax.text(0.02, 0.53,
            "candidate07 held out\n"
            "  best streak blocks 137–144 (8/10)\n"
            "  no qualifying window by block 300\n"
            "  no state file created",
            fontsize=12, va="top", color="#9b1c1f")
    ax.text(0.02, 0.24,
            "Decision: method does not generalize.\n"
            "No rerun, retuning, rehydration, free release,\n"
            "permeability, flow, deformation, or migration.",
            fontsize=12, va="top", weight="bold")

    fig.suptitle(
        "Stage26e qualified-state capture — held-out confirmation failed\n"
        "Fixed two-F37 development evidence only; candidate08 remains untouched",
        fontsize=14, y=0.97,
    )
    image = OUT / "stage26e_development_and_heldout_capture_outcome.png"
    fig.savefig(image, dpi=190)
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26e-capture-outcome-render.v1",
        "passed": True,
        "status": "rendered_verified_development_pass_heldout_failure",
        "image": str(image),
        "image_sha256": digest(image),
        "renderer_sha256": digest(Path(__file__)),
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": digest(CHECKPOINT),
        "source_hashes": {
            "development_history": digest(dev_history_path),
            "development_result": digest(DEV / "result.json"),
            "heldout_history": digest(held_history_path),
            "heldout_result": digest(HELD / "result.json"),
            "heldout_evaluation": digest(HELD / "heldout_evaluation_v1.json"),
        },
        "claim_boundary": checkpoint["claim_boundary"],
    }
    manifest_path = OUT / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"image": str(image), "image_sha256": digest(image), "manifest": str(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
