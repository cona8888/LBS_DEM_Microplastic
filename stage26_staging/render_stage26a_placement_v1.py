"""Render the hash-bound Stage26a pre-relaxation placement at physical scale."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26a_dry_f37_insertion_design_v1.json"
PLACEMENT = PROJECT / "stage26_placements" / "stage26a_dry_f37_insertion_20260813" / "placement_02" / "placement.json"
OUTPUT = PROJECT / "stage26_renders" / "stage26a_dry_f37_insertion_20260813" / "placement_render_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def sphere_surface(ax, centre, radius, color, alpha, resolution=9, edge=None):
    u = np.linspace(0, 2 * np.pi, 2 * resolution)
    v = np.linspace(0, np.pi, resolution)
    x = centre[0] + radius * np.outer(np.cos(u), np.sin(v))
    y = centre[1] + radius * np.outer(np.sin(u), np.sin(v))
    z = centre[2] + radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(x, y, z, color=color, alpha=alpha, linewidth=0.12 if edge else 0, edgecolor=edge, shade=True)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable placement render already exists")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.mkdir()
    cfg = load_json(CONFIG); placement = load_json(PLACEMENT)
    if not placement.get("passed") or placement["source_hashes"]["config"] != digest(CONFIG):
        raise RuntimeError("placement/config binding failed")
    result_path = Path(cfg["source"]["stage25_selected_result"])
    if digest(result_path) != cfg["source"]["stage25_selected_result_sha256"]:
        raise RuntimeError("sand result hash mismatch")
    result = load_json(result_path)
    lengths = np.array(placement["cell_dimensions_m"]) * 1000
    anchors = set(placement["anchor_sand_body_ids"])
    members = np.array(placement["member_centres_m"]) * 1000
    member_radius = placement["member_radius_m"] * 1000

    fig = plt.figure(figsize=(13.5, 9.5), constrained_layout=True)
    ax = fig.add_subplot(111, projection="3d")
    for row in result["particles"]:
        sphere_surface(ax, np.array(row["position_m"]) * 1000, row["radius_m"] * 1000,
                       "#2878b5" if row["body_id"] in anchors else "#d7b56d",
                       0.72 if row["body_id"] in anchors else 0.18,
                       resolution=7, edge="#164b73" if row["body_id"] in anchors else None)
    for centre in members:
        sphere_surface(ax, centre, member_radius, "#d62728", 0.92, resolution=8, edge="#7f0000")
    ax.plot(members[:, 0], members[:, 1], members[:, 2], color="#7f0000", lw=1.2)
    for anchor_id, member_index in zip(placement["anchor_sand_body_ids"], placement["anchor_member_indices"]):
        anchor = next(row for row in result["particles"] if row["body_id"] == anchor_id)
        a = np.array(anchor["position_m"]) * 1000
        b = members[member_index]
        ax.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]], color="#164b73", lw=2.3)
    ax.set_xlim(0, lengths[0]); ax.set_ylim(0, lengths[1]); ax.set_zlim(0, lengths[2])
    ax.set_box_aspect(np.array(lengths, copy=True))
    ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.set_zlabel("z (mm)")
    ax.view_init(elev=22, azim=-54)
    ax.set_title("Actual Stage26a pre-relaxation geometry\nF37 rigid clump (red), two declared anchor grains (blue), remaining LBS spheres (tan)", pad=18)
    fig.suptitle("One F37 fibre inserted into the frozen Stage25a load-bearing packing", fontsize=16, weight="bold")
    fig.text(0.5, 0.015,
             f"Cell {lengths[0]:.3f}×{lengths[1]:.3f}×{lengths[2]:.3f} mm | 216 sand spheres | 37 fibre members | "
             f"anchor penetration={-1e6 * min(placement['anchor_clearances_m']):.3f} µm | nominal plastic={100*cfg['fibre']['nominal_mixture_mass_fraction']:.4f} wt%.\n"
             "Physical coordinates and radii; geometry preflight only—no relaxation, permeability, migration, polymer-flexibility, or coupled-flow claim.",
             ha="center", va="bottom", fontsize=9.3)
    image_path = OUTPUT / "stage26a_pre_relaxation_placement.png"
    fig.savefig(image_path, dpi=220, bbox_inches="tight", facecolor="white"); plt.close(fig)
    manifest = {
        "schema": "lbs.stage26a-dry-f37-insertion.v1.placement-render",
        "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {"config": digest(CONFIG), "placement": digest(PLACEMENT), "renderer": digest(Path(__file__))},
        "image_sha256": digest(image_path),
        "visual_semantics": "Physical coordinates and radii with equal axis scale; transparent non-anchor sand is a visibility choice, not a phase or size change.",
        "claim_boundary": cfg["claim_boundary"],
    }
    with (OUTPUT / "render_manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True); stream.write("\n")
    print(json.dumps({"passed": True, "image_sha256": digest(image_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
