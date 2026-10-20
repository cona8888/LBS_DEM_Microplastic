"""Render the independently audited Stage26f static cage candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def exclusive_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    campaign = Path(args.campaign).resolve()
    audit_path = Path(args.audit).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26f render output already exists")
    config = load_json(config_path)
    audit = load_json(audit_path)
    if audit.get("passed") is not True or audit.get("candidate08_read_or_used") is not False:
        raise RuntimeError("only the passed candidate08-excluding audit may be rendered")
    network_path = Path(config["sources"]["network"])
    if digest(network_path) != config["sources"]["network_sha256"]:
        raise RuntimeError("network hash mismatch")
    network = load_json(network_path)
    particles = network["particles"]
    sand = np.asarray([row["position_m"] for row in particles], dtype=float) * 1e3
    radii = np.asarray([row["radius_m"] for row in particles], dtype=float) * 1e3
    body_to_position = {
        int(row["sand_body_id"]): np.asarray(row["position_m"], dtype=float) * 1e3
        for row in particles
    }
    lengths = np.diag(np.asarray(network["cell_hsize_m"], dtype=float)) * 1e3

    fig = plt.figure(figsize=(15, 18), constrained_layout=True)
    colours = ["#d62728", "#1565c0"]
    for candidate_index in range(1, 9):
        candidate_id = f"stage26f_f002_cage_candidate_{candidate_index:02d}"
        placement_path = campaign / candidate_id / "placement.json"
        placement = load_json(placement_path)
        if placement.get("passed") is not True:
            raise RuntimeError("renderer received a failed candidate: " + candidate_id)
        ax = fig.add_subplot(4, 2, candidate_index, projection="3d")
        sizes = 10.0 + 20.0 * (radii / radii.mean()) ** 2
        ax.scatter(sand[:, 0], sand[:, 1], sand[:, 2], s=sizes, c="#777777", alpha=0.09, depthshade=False)
        minimum_condition = 1.0
        maximum_force_residual = 0.0
        joint_clearance = placement["fibres"][0]["minimum_fibre_fibre_clearance_m"] * 1e3
        for fibre_index, fibre in enumerate(placement["fibres"]):
            centres = np.asarray(fibre["member_centres_m"], dtype=float) * 1e3
            colour = colours[fibre_index]
            ax.plot(centres[:, 0], centres[:, 1], centres[:, 2], color=colour, lw=3.0, marker="o", ms=1.8)
            support = np.asarray([body_to_position[int(value)] for value in fibre["support_sand_body_ids"]])
            ax.scatter(
                support[:, 0], support[:, 1], support[:, 2],
                s=100, facecolors="none", edgecolors=colour, linewidths=2.0, depthshade=False,
            )
            minimum_condition = min(minimum_condition, fibre["frictional_wrench_condition_ratio"])
            maximum_force_residual = max(maximum_force_residual, fibre["equal_normal_force_residual_relative"])
        ax.set_xlim(0.0, lengths[0])
        ax.set_ylim(0.0, lengths[1])
        ax.set_zlim(0.0, lengths[2])
        ax.set_box_aspect(lengths)
        ax.view_init(elev=24, azim=38)
        ax.set_xlabel("x (mm)", labelpad=2)
        ax.set_ylabel("y (mm)", labelpad=2)
        ax.set_zlabel("z (mm)", labelpad=2)
        ax.set_title(
            f"Candidate {candidate_index:02d}: 2 fibres, 4 supports each\n"
            f"min wrench cond.={minimum_condition:.3f}; max force proxy={maximum_force_residual:.3f}; "
            f"fibre gap={joint_clearance:.3f} mm",
            fontsize=10,
        )
    fig.suptitle(
        "Stage26f fresh robust-cage geometries — independently audited static placements\n"
        "Grey: LBS sand; red/blue: F37 centre-lines; coloured rings: supporting sand bodies\n"
        "Equal physical axis scale. Offline geometry only—not equilibrium, release, flow, or permeability.",
        fontsize=15,
    )
    output.mkdir(parents=True)
    image_path = output / "stage26f_eight_fresh_robust_cage_candidates.png"
    fig.savefig(image_path, dpi=190, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26f-robust-cage-render-manifest.v1",
        "passed": True,
        "candidate_count": 8,
        "candidate08_read_or_used": False,
        "image": str(image_path),
        "image_sha256": digest(image_path),
        "source_hashes": {
            "config": digest(config_path),
            "campaign_completion": digest(campaign / "completion.json"),
            "audit": digest(audit_path),
            "network": digest(network_path),
            "renderer": digest(Path(__file__)),
        },
        "claim_boundary": config["claim_boundary"],
    }
    exclusive_json(output / "render_manifest.json", manifest)
    print(json.dumps({"passed": True, "image_sha256": manifest["image_sha256"], "manifest_sha256": digest(output / "render_manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
