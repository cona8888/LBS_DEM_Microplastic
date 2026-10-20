"""Render the independently verified Stage26d fixed-fibre confirmation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/final_confirmation_checkpoint_01/checkpoint_manifest.json"
OUT = ROOT / "stage26_renders/stage26d_adaptive_equilibration_20260816/confirmation_render_03"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_history(path):
    rows = []
    with path.open(newline="", encoding="utf-8") as stream:
        for raw in csv.DictReader(stream):
            rows.append({
                "block": int(raw["block"]),
                "contacts": json.loads(raw["distinct_sand_contacts_by_fibre"]),
                "anchors": json.loads(raw["declared_anchor_contacts_by_fibre"]),
                "mean_error": float(raw["relative_mean_stress_error"]),
                "principal_error": float(raw["maximum_principal_stress_error"]),
                "unbalanced": float(raw["unbalanced_force"]),
                "retention": float(raw["sand_sand_contact_retention_fraction"]),
                "displacement": float(raw["maximum_nonaffine_sand_displacement_over_D50"]),
                "volume_drift": float(raw["cell_volume_relative_drift"]),
                "penetration": float(raw["maximum_interobject_penetration_over_smaller_radius"]),
                "coordination": float(raw["sand_coordination_excluding_degree_lt2_rattlers"]),
                "rattlers": float(raw["sand_rattler_fraction_degree_lt2_iterative"]),
            })
    return rows


def gate_utilization(row):
    return max(
        row["mean_error"] / 0.02,
        row["principal_error"] / 0.03,
        row["unbalanced"] / 0.05,
        (1.0 - row["retention"]) / 0.10,
        row["displacement"] / 0.10,
        row["volume_drift"] / 0.005,
        row["penetration"] / 0.02,
        3.0 / row["coordination"],
        row["rattlers"] / 0.35,
    )


def main():
    checkpoint = load_json(CHECKPOINT)
    assert checkpoint["passed"] is True
    assert checkpoint["authority"]["diagnostic_render_authorized"] is True
    assert checkpoint["authority"]["free_release_authorized"] is False
    assert checkpoint["authority"]["flow_execution_authorized"] is False
    assert checkpoint["source_hashes"]["independent_verifier"] == digest(
        ROOT / "stage26_staging/verify_and_freeze_stage26d_confirmation_v1.py"
    )
    case_paths = {
        "positive": ROOT / "stage26_runs/stage26d_adaptive_equilibration_20260816/controls_01/positive_stage26a",
        "negative": ROOT / "stage26_runs/stage26d_adaptive_equilibration_20260816/controls_01/negative_stage26b_failure",
        "development": ROOT / "stage26_runs/stage26d_adaptive_equilibration_20260816/development_01/revision3_candidate01",
        "heldout": ROOT / "stage26_runs/stage26d_adaptive_equilibration_20260816/holdout_01/revision3_candidate04",
    }
    checkpoint_keys = {
        "positive": "positive_control",
        "negative": "negative_control",
        "development": "development_candidate01",
        "heldout": "heldout_candidate04",
    }
    data = {}
    evaluations = {}
    for name, directory in case_paths.items():
        history_path = directory / "fixed_conditioning_history.csv"
        evaluation_path = directory / "adaptive_evaluation_v1.json"
        expected = checkpoint["cases"][checkpoint_keys[name]]["hashes"]
        assert digest(history_path) == expected["history"]
        assert digest(evaluation_path) == expected["evaluation"]
        data[name] = load_history(history_path)
        evaluations[name] = load_json(evaluation_path)

    OUT.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(2, 2, figsize=(14, 11), constrained_layout=False)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.075, top=0.865, wspace=0.22, hspace=0.30)
    colors = {"development": "#006ba4", "heldout": "#ff800e"}

    for ax, name, title in (
        (axes[0, 0], "development", "Development: candidate01"),
        (axes[0, 1], "heldout", "Held-out confirmation: candidate04"),
    ):
        rows = data[name]
        block = [row["block"] for row in rows]
        ax.step(block, [min(row["contacts"]) for row in rows], where="mid", linewidth=1.5,
                color=colors[name], label="minimum sand contacts/fibre")
        ax.step(block, [min(row["anchors"]) for row in rows], where="mid", linewidth=1.2,
                color="#3e9651", linestyle="--", label="minimum declared anchors/fibre")
        start, end = evaluations[name]["earliest_qualifying_window_blocks"]
        ax.axvspan(start - 0.5, end + 0.5, color="#8dd3c7", alpha=0.45, label=f"first accepted window {start}-{end}")
        ax.axhline(2, color="black", linewidth=0.9, linestyle=":", label="equilibrium contact/anchor gate")
        ax.set(xlim=(1, 300), ylim=(-0.1, 4.2), title=title, ylabel="Minimum count per fibre")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, loc="lower right")

    ax = axes[1, 0]
    for name in ("development", "heldout"):
        rows = data[name]
        ax.plot([row["block"] for row in rows], [gate_utilization(row) for row in rows],
                color=colors[name], linewidth=1.2, label=name)
        start, end = evaluations[name]["earliest_qualifying_window_blocks"]
        ax.axvspan(start - 0.5, end + 0.5, color=colors[name], alpha=0.12)
    ax.axhline(1.0, color="black", linewidth=1.1, linestyle="--", label="sand-health boundary")
    ax.set_yscale("log")
    ax.set(xlim=(1, 300), ylim=(0.5, 35.0), xlabel="Fixed-conditioning block (500 YADE steps)",
           ylabel="Largest normalized sand-health demand", title="Sand state: value <= 1 passes all plotted health gates")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=9)

    ax = axes[1, 1]
    labels = ["positive\ncontrol", "negative\ncontrol", "candidate01\ndevelopment", "candidate04\nheld out"]
    names = ["positive", "negative", "development", "heldout"]
    y = range(len(names))
    ax.set(xlim=(1, 300), ylim=(-0.6, 3.6), xlabel="Fixed-conditioning block",
           title="Frozen adaptive-gate outcomes")
    for idx, name in enumerate(names):
        window = evaluations[name]["earliest_qualifying_window_blocks"]
        ax.hlines(idx, 1, 300, color="#dddddd", linewidth=6)
        if window is None:
            ax.text(150, idx, "no qualifying window (expected negative control)", ha="center", va="center", fontsize=9)
        else:
            ax.hlines(idx, window[0], window[1], color="#3e9651", linewidth=9)
            ax.scatter(window, [idx, idx], color="#1b7837", s=28, zorder=3)
            ax.text(window[1] + 5, idx, f"{window[0]}-{window[1]}", va="center", fontsize=9)
    ax.set_yticks(list(y), labels)
    ax.grid(axis="x", alpha=0.25)

    fig.suptitle(
        "Stage26d fixed-fibre adaptive equilibration — held-out confirmation passed\n"
        "All fibres remained fixed; no saved promotable state, free release, permeability, flow, deformation, or migration claim",
        fontsize=14, y=0.97,
    )
    image = OUT / "stage26d_fixed_fibre_adaptive_confirmation.png"
    fig.savefig(image, dpi=190)
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26d-adaptive-confirmation-render.v1",
        "passed": True,
        "status": "rendered_verified_fixed_fibre_heldout_confirmation",
        "image": str(image),
        "image_sha256": digest(image),
        "renderer_sha256": digest(Path(__file__)),
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": digest(CHECKPOINT),
        "source_hashes": {
            name: {
                "history": digest(directory / "fixed_conditioning_history.csv"),
                "evaluation": digest(directory / "adaptive_evaluation_v1.json"),
            }
            for name, directory in case_paths.items()
        },
        "claim_boundary": checkpoint["claim_boundary"],
    }
    manifest_path = OUT / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"image": str(image), "image_sha256": digest(image), "manifest": str(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
