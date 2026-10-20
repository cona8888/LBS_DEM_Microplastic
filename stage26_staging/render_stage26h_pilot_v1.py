#!/usr/bin/env python3
"""Render the verified Stage26h contact-loss pilot."""

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluation = load_json(args.evaluation)
    assert evaluation["passed"] is True
    assert evaluation["source_hashes"]["history"] == sha256(args.history)
    with args.history.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    block = [int(r["block"]) for r in rows]
    contacts = [json.loads(r["distinct_sand_contacts_by_fibre"]) for r in rows]
    supports = [json.loads(r["declared_support_contacts_by_fibre"]) for r in rows]
    translations = [json.loads(r["fibre_translation_over_D50_by_fibre"]) for r in rows]
    rotations = [json.loads(r["fibre_rotation_deg_by_fibre"]) for r in rows]
    stress = [float(r["mean_effective_stress_pa_compression_positive"]) for r in rows]
    unbalanced = [float(r["unbalanced_force"]) for r in rows]
    colors = ["#2878B5", "#D95319"]

    args.output_dir.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    for fibre in range(2):
        axes[0, 0].plot(block, [v[fibre] for v in contacts], "o-", ms=3, color=colors[fibre], label=f"fibre {fibre + 1}")
        axes[0, 0].plot(block, [v[fibre] for v in supports], ":", lw=1.5, color=colors[fibre])
    axes[0, 0].axhline(2, color="black", ls="--", lw=1, label="guard minimum")
    axes[0, 0].set(xlabel="conditioning block", ylabel="contact count", title="Contacts (solid) and original supports (dotted)")
    axes[0, 0].set_ylim(-0.2, 4.4)
    axes[0, 0].legend(fontsize=8)

    for fibre in range(2):
        axes[0, 1].plot(block, [v[fibre] for v in translations], "-", color=colors[fibre], label=f"fibre {fibre + 1}")
    axes[0, 1].axhline(0.05, color="black", ls="--", lw=1, label="translation guard")
    axes[0, 1].set(xlabel="conditioning block", ylabel="translation / D50", title="Bounded fibre translation")
    axes[0, 1].legend(fontsize=8)

    for fibre in range(2):
        axes[1, 0].plot(block, [v[fibre] for v in rotations], "-", color=colors[fibre], label=f"fibre {fibre + 1}")
    axes[1, 0].axhline(10.0, color="black", ls="--", lw=1, label="rotation guard")
    axes[1, 0].set(xlabel="conditioning block", ylabel="rotation (degrees)", title="Bounded fibre rotation")
    axes[1, 0].legend(fontsize=8)

    axes[1, 1].plot(block, stress, color="#2878B5", label="mean stress (Pa)")
    axes[1, 1].axhline(100, color="#2878B5", ls="--", lw=1, label="100 Pa target")
    twin = axes[1, 1].twinx()
    twin.semilogy(block, unbalanced, color="#D95319", label="unbalanced force")
    twin.axhline(0.05, color="#D95319", ls="--", lw=1, label="0.05 maximum")
    axes[1, 1].set(xlabel="conditioning block", ylabel="mean effective stress (Pa)", title="Sand response")
    twin.set_ylabel("unbalanced force")
    lines = axes[1, 1].lines + twin.lines
    axes[1, 1].legend(lines, [line.get_label() for line in lines], fontsize=8, loc="center right")

    fig.suptitle(
        "Stage26h bounded mobile-conditioning pilot: one fibre isolated at block 20\n"
        "Motion remained tiny; near-tangent insertion contacts lacked persistent preload",
        fontsize=14,
    )
    image = args.output_dir / "stage26h_bounded_conditioning_failure.png"
    fig.savefig(image, dpi=180, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26h-bounded-conditioning-render-manifest.v1",
        "passed": True,
        "status": "verified_physical_failure_render",
        "image": str(image).replace("\\", "/"),
        "image_sha256": sha256(image),
        "source_hashes": {
            "evaluation": sha256(args.evaluation),
            "history": sha256(args.history),
            "renderer": sha256(Path(__file__)),
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
