#!/usr/bin/env python3
"""Render the verified Stage26j failed development screen."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluation = load(args.evaluation)
    assert evaluation["passed"] is True and evaluation["screen_success"] is False
    colors = {1.0: "#2878B5", 2.0: "#D95319"}
    series = []
    for case in evaluation["case_evaluations"]:
        history_path = args.runs_dir / case["trial_id"] / "joint_growth_history.csv"
        assert sha256(history_path) == case["history_sha256"]
        with history_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        shrink = round(float(case["initial_sand_radius_shrink_percent"]), 1)
        series.append((shrink, {
            "block": [int(row["block"]) for row in rows],
            "sand_scale": [float(row["temporary_sand_radius_scale"]) for row in rows],
            "sand_contacts": [int(row["sand_sand_real_contact_count"]) for row in rows],
            "fibre_contacts": [min(json.loads(row["distinct_sand_contacts_by_fibre"])) for row in rows],
            "stress": [float(row["mean_effective_stress_pa_compression_positive"]) for row in rows],
            "unbalanced": [float(row["unbalanced_force"]) for row in rows],
        }))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.3), constrained_layout=True)
    for shrink, row in series:
        label = f"{shrink:.0f}% initial sand shrink"
        color = colors[shrink]
        axes[0, 0].plot(row["block"], row["sand_contacts"], lw=1.5, color=color, label=label)
        axes[0, 1].plot(row["block"], row["fibre_contacts"], lw=1.5, color=color, label=label)
        axes[1, 0].plot(row["block"], row["stress"], lw=1.5, color=color, label=label)
        axes[1, 1].plot(row["block"], [(1.0 - x) * 100 for x in row["sand_scale"]], lw=1.5, color=color, label=label)
    axes[0, 0].axhline(361, color="black", ls="--", lw=1, label="original network (361)")
    axes[0, 0].set(xlabel="preparation block", ylabel="sand-sand contacts", title="Load-bearing network was not recovered")
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].axhline(3, color="black", ls="--", lw=1, label="minimum per fibre")
    axes[0, 1].set(xlabel="preparation block", ylabel="minimum contacts per fibre", title="Fibre support remained insufficient")
    axes[0, 1].set_ylim(-0.1, 4.2)
    axes[0, 1].legend(fontsize=8)
    axes[1, 0].axhline(100, color="black", ls="--", lw=1, label="100 Pa target")
    axes[1, 0].set(xlabel="preparation block", ylabel="mean effective stress (Pa)", title="Confining stress collapsed after regrowth")
    axes[1, 0].legend(fontsize=8)
    axes[1, 1].axvline(40, color="#666666", ls=":", lw=1, label="exact radii restored")
    axes[1, 1].set(xlabel="preparation block", ylabel="sand-radius deficit (%)", title="Exact sand geometry restored at block 40")
    axes[1, 1].legend(fontsize=8)
    fig.suptitle(
        "Stage26j joint sand-growth development screen: no mechanics state qualified\n"
        "Exact fibre geometry throughout; exact sand radii restored; held-out and flow not run",
        fontsize=14,
    )
    image = args.output_dir / "stage26j_joint_sand_growth_failure.png"
    fig.savefig(image, dpi=180, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26j-joint-sand-growth-render-manifest.v1",
        "passed": True,
        "status": "verified_failed_development_screen_render",
        "image": str(image).replace("\\", "/"),
        "image_sha256": sha256(image),
        "source_hashes": {
            "evaluation": sha256(args.evaluation),
            "renderer": sha256(Path(__file__)),
            "histories": {str(shrink): case["history_sha256"] for shrink, case in zip([x[0] for x in series], evaluation["case_evaluations"])},
        },
        "claim_boundary": evaluation["claim_boundary"],
    }
    manifest_path = args.output_dir / "render_manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"image": str(image), "image_sha256": sha256(image)}, sort_keys=True))


if __name__ == "__main__":
    main()
