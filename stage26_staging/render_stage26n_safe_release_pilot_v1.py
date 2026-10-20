#!/usr/bin/env python3
"""Render the independently evaluated Stage26n release/caging result."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluation = load(args.evaluation)
    assert evaluation["passed"] is True
    assert evaluation["source_hashes"]["history"] == sha(args.history)
    assert evaluation["numerical_release_stability_pass"] is True
    assert evaluation["mobile_caging_qualified"] is False

    rows = []
    with args.history.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["phase"].startswith("release_ramp_") or row["phase"] == "mobile_equilibration":
                rows.append({
                    "record": len(rows), "phase": row["phase"],
                    "stress": float(row["mean_effective_stress_pa_compression_positive"]),
                    "overlap": float(row["maximum_interobject_penetration_over_smaller_radius"]),
                    "translation": float(row["maximum_fibre_translation_over_D50"]),
                    "rotation": float(row["maximum_fibre_rotation_deg"]),
                    "minimum_contacts": min(json.loads(row["distinct_sand_contacts_by_fibre"])),
                })
    x = [row["record"] for row in rows]
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.4))
    ax = axes[0, 0]
    ax.plot(x, [row["stress"] for row in rows], color="#355f8d", lw=1.5)
    ax.axhline(100.0, color="black", ls="--", lw=1, label="target 100 Pa")
    ax.set(ylabel="Mean effective stress (Pa)", title="Sand skeleton remains controlled")
    ax.legend(frameon=False)
    ax = axes[0, 1]
    ax.semilogy(x, [max(row["overlap"], 1e-12) for row in rows], color="#2a9d8f", lw=1.5)
    ax.axhline(0.05, color="#c1121f", ls="--", lw=1, label="hard guard")
    ax.set(ylabel="Maximum penetration / smaller radius", title="Release impulse eliminated")
    ax.legend(frameon=False)
    ax = axes[1, 0]
    ax.plot(x, [row["translation"] for row in rows], color="#e76f51", lw=1.5, label="translation / D50")
    ax2 = ax.twinx()
    ax2.plot(x, [row["rotation"] for row in rows], color="#6a4c93", lw=1.2, label="rotation")
    ax.set(xlabel="Post-release diagnostic record", ylabel="Maximum fibre translation / D50", title="Motion is bounded, not explosive")
    ax2.set_ylabel("Maximum fibre rotation (deg)")
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [line.get_label() for line in lines], frameon=False, loc="upper left")
    ax = axes[1, 1]
    ax.step(x, [row["minimum_contacts"] for row in rows], where="post", color="#f4a261", lw=1.5)
    ax.axhline(3, color="#c1121f", ls="--", lw=1, label="caging acceptance: 3")
    ax.set(xlabel="Post-release diagnostic record", ylabel="Minimum sand contacts per fibre", title="Both fibres detach and remain isolated", ylim=(-0.2, 3.5))
    ax.legend(frameon=False)
    fig.suptitle("Stage26n — stable numerical release, failed physical embedding", fontsize=15, weight="bold")
    fig.text(0.5, 0.018, "Spent development geometry only; no permeability, flow, deformation, migration, held-out, or production claim.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0.0, 0.055, 1.0, 0.94))

    args.output_dir.mkdir(parents=True, exist_ok=False)
    image = args.output_dir / "stage26n_stable_release_failed_caging.png"
    fig.savefig(image, dpi=180)
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26n-safe-release-render-manifest.v1", "passed": True,
        "status": "diagnostic_render_numerical_release_stable_physical_caging_failed",
        "image": str(image.resolve()).replace("\\", "/"), "image_sha256": sha(image),
        "source_hashes": {"evaluation": sha(args.evaluation), "history": sha(args.history), "renderer": sha(args.renderer)},
        "claim_boundary": evaluation["claim_boundary"],
    }
    manifest_path = args.output_dir / "render_manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"image": str(image), "image_sha256": sha(image), "manifest_sha256": sha(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
