#!/usr/bin/env python3
"""Render the immutable Stage26g development failure histories."""

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


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def load_history(path: Path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {
        "block": [int(r["block"]) for r in rows],
        "contacts": [min(json.loads(r["distinct_sand_contacts_by_fibre"])) for r in rows],
        "supports": [min(json.loads(r["declared_support_contacts_by_fibre"])) for r in rows],
        "stress": [float(r["mean_effective_stress_pa_compression_positive"]) for r in rows],
        "unbalanced": [float(r["unbalanced_force"]) for r in rows],
        "retention": [float(r["sand_sand_contact_retention_fraction"]) for r in rows],
    }


def write_exclusive_json(path: Path, payload) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluation = load_json(args.evaluation)
    assert evaluation["passed"] is True
    assert evaluation["development_acceptance_passed"] is False
    assert evaluation["heldout_execution_authorized"] is False
    args.output_dir.mkdir(parents=True, exist_ok=False)

    colors = {6: "#2878B5", 7: "#D95319", 8: "#6A3D9A"}
    histories = {}
    for case in evaluation["case_evaluations"]:
        index = case["candidate_index"]
        history_path = args.runs_dir / f"stage26f_cage_candidate_{index:02d}" / "fixed_capture_history.csv"
        assert sha256(history_path) == case["history_sha256"]
        histories[index] = load_history(history_path)

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.2), constrained_layout=True)
    ax = axes[0, 0]
    for index, data in histories.items():
        ax.plot(data["block"], data["supports"], marker="o", ms=3, lw=1.5, color=colors[index], label=f"cage {index:02d}")
    ax.axhline(2, color="black", ls="--", lw=1, label="continuous minimum")
    ax.axhline(3, color="#666666", ls=":", lw=1, label="window minimum")
    ax.axvline(60, color="#B00020", ls="--", lw=1, label="window eligibility")
    ax.set(xlabel="equilibration block", ylabel="minimum declared supports per fibre", title="Support persistence")
    ax.set_ylim(0.7, 4.3)
    ax.legend(fontsize=8, ncol=2)

    ax = axes[0, 1]
    for index, data in histories.items():
        ax.plot(data["block"], data["contacts"], marker="o", ms=3, lw=1.5, color=colors[index], label=f"cage {index:02d}")
    ax.axhline(2, color="black", ls="--", lw=1)
    ax.axhline(3, color="#666666", ls=":", lw=1)
    ax.axvline(60, color="#B00020", ls="--", lw=1)
    ax.set(xlabel="equilibration block", ylabel="minimum distinct sand contacts per fibre", title="Actual fibre–sand contacts")
    ax.set_ylim(0.7, 4.3)

    ax = axes[1, 0]
    for index, data in histories.items():
        ax.plot(data["block"], data["stress"], lw=1.7, color=colors[index], label=f"cage {index:02d}")
    ax.axhline(100, color="black", ls="--", lw=1, label="100 Pa target")
    ax.axvline(60, color="#B00020", ls="--", lw=1)
    ax.set(xlabel="equilibration block", ylabel="mean effective stress (Pa)", title="Sand stress equilibration")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    for index, data in histories.items():
        ax.semilogy(data["block"], data["unbalanced"], lw=1.7, color=colors[index], label=f"cage {index:02d}")
    ax.axhline(0.05, color="black", ls="--", lw=1, label="window maximum")
    ax.axvline(60, color="#B00020", ls="--", lw=1)
    ax.set(xlabel="equilibration block", ylabel="unbalanced force", title="Mechanical relaxation")
    ax.legend(fontsize=8)

    fig.suptitle(
        "Stage26g fresh four-support cages: development gate failed (0/3 qualified)\n"
        "Exact [4,4] insertion contacts were not persistent; held-out cases remain locked",
        fontsize=14,
    )
    image_path = args.output_dir / "stage26g_development_failure.png"
    fig.savefig(image_path, dpi=180, facecolor="white")
    plt.close(fig)

    manifest = {
        "schema": "lbs.stage26g-development-failure-render-manifest.v1",
        "passed": True,
        "status": "diagnostic_render_of_verified_development_failure",
        "image": str(image_path).replace("\\", "/"),
        "image_sha256": sha256(image_path),
        "source_hashes": {
            "evaluation": sha256(args.evaluation),
            "renderer": sha256(Path(__file__)),
            "histories": {str(i): evaluation["case_evaluations"][[c["candidate_index"] for c in evaluation["case_evaluations"]].index(i)]["history_sha256"] for i in sorted(histories)},
        },
        "claim_boundary": evaluation["claim_boundary"],
        "annotation": "No qualified state was captured; this figure is a fixed-fibre mechanics diagnostic, not a flow or permeability result.",
    }
    write_exclusive_json(args.output_dir / "render_manifest.json", manifest)
    print(json.dumps({"image": str(image_path), "image_sha256": manifest["image_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
