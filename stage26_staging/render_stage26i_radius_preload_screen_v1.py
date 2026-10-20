#!/usr/bin/env python3
"""Render the verified Stage26i development screen."""

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
    colors = {0.5: "#2878B5", 1.0: "#D95319", 1.5: "#6A3D9A"}
    data = {}
    for case in evaluation["case_evaluations"]:
        history_path = args.runs_dir / case["trial_id"] / "preload_history.csv"
        assert sha256(history_path) == case["history_sha256"]
        with history_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        scale = round(float(case["temporary_radius_increase_percent"]), 1)
        data[scale] = {
            "block": [int(row["block"]) for row in rows],
            "contacts": [min(json.loads(row["distinct_sand_contacts_by_fibre"])) for row in rows],
            "radius_scale": [float(row["temporary_fibre_radius_scale"]) for row in rows],
            "stress": [float(row["mean_effective_stress_pa_compression_positive"]) for row in rows],
            "unbalanced": [float(row["unbalanced_force"]) for row in rows],
            "phase": [row["phase"] for row in rows],
        }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.2), constrained_layout=True)
    for scale in sorted(data):
        row = data[scale]
        label = f"+{scale:.1f}% radius"
        axes[0, 0].plot(row["block"], row["contacts"], "o-", ms=2.8, lw=1.4, color=colors[scale], label=label)
        axes[0, 1].plot(row["block"], [(value - 1.0) * 100 for value in row["radius_scale"]], lw=1.6, color=colors[scale], label=label)
        axes[1, 0].plot(row["block"], row["stress"], lw=1.5, color=colors[scale], label=label)
        axes[1, 1].semilogy(row["block"], row["unbalanced"], lw=1.5, color=colors[scale], label=label)
    axes[0, 0].axhline(2, color="black", ls="--", lw=1, label="guard minimum")
    axes[0, 0].axhline(3, color="#666666", ls=":", lw=1, label="equilibrium minimum")
    axes[0, 0].set(xlabel="preparation block", ylabel="minimum contacts per fibre", title="Contact survival")
    axes[0, 0].set_ylim(0.7, 4.3)
    axes[0, 0].legend(fontsize=8, ncol=2)
    axes[0, 1].set(xlabel="preparation block", ylabel="temporary radius increase (%)", title="Predeclared inflation and attempted restoration")
    axes[0, 1].legend(fontsize=8)
    axes[1, 0].axhline(100, color="black", ls="--", lw=1, label="100 Pa target")
    axes[1, 0].set(xlabel="preparation block", ylabel="mean effective stress (Pa)", title="Sand stress response")
    axes[1, 0].legend(fontsize=8)
    axes[1, 1].axhline(0.05, color="black", ls="--", lw=1, label="equilibrium maximum")
    axes[1, 1].set(xlabel="preparation block", ylabel="unbalanced force", title="Mechanical relaxation")
    axes[1, 1].legend(fontsize=8)
    fig.suptitle(
        "Stage26i temporary-radius preload screen: no exact-final-geometry state qualified\n"
        "0.5% and 1.5% inflated states passed, then lost contacts during restoration",
        fontsize=14,
    )
    image = args.output_dir / "stage26i_radius_preload_screen.png"
    fig.savefig(image, dpi=180, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26i-radius-preload-screen-render-manifest.v1",
        "passed": True,
        "status": "verified_failed_development_screen_render",
        "image": str(image).replace("\\", "/"),
        "image_sha256": sha256(image),
        "source_hashes": {
            "evaluation": sha256(args.evaluation),
            "renderer": sha256(Path(__file__)),
            "histories": {str(scale): next(case["history_sha256"] for case in evaluation["case_evaluations"] if round(float(case["temporary_radius_increase_percent"]), 1) == scale) for scale in sorted(data)},
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
