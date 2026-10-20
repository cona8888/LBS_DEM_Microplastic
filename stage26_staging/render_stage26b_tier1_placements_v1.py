"""Render physically scaled Stage26b Tier-1 multi-fibre geometry preflights."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_tier1_placement_preflight_v1.json"
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_dry_multifibre_20260814" / "tier1_placement_evaluation_01" / "evaluation.json"
PLACEMENT_ROOT = PROJECT / "stage26_placements" / "stage26b_dry_multifibre_20260814" / "tier1_preflight_01"
OUTPUT = PROJECT / "stage26_renders" / "stage26b_dry_multifibre_20260814" / "tier1_placement_render_01"
PALETTE = ["#d62728", "#8c2d9b", "#2ca02c", "#ff7f0e"]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def sphere_surface(ax, centre, radius, color, alpha, resolution=6, edge=None):
    u = np.linspace(0, 2 * np.pi, 2 * resolution)
    v = np.linspace(0, np.pi, resolution)
    x = centre[0] + radius * np.outer(np.cos(u), np.sin(v))
    y = centre[1] + radius * np.outer(np.sin(u), np.sin(v))
    z = centre[2] + radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(x, y, z, color=color, alpha=alpha, linewidth=0.12 if edge else 0,
                    edgecolor=edge, shade=True)


def draw_case(ax, placement, particles, closeup):
    lengths = np.array(placement["cell_dimensions_m"]) * 1000.0
    radius = placement["member_radius_m"] * 1000.0
    anchors = {body for fibre in placement["fibres"] for body in fibre["anchor_sand_body_ids"]}
    particle_by_id = {int(row["body_id"]): row for row in particles}
    if not closeup:
        for row in particles:
            is_anchor = int(row["body_id"]) in anchors
            sphere_surface(ax, np.array(row["position_m"]) * 1000.0, row["radius_m"] * 1000.0,
                           "#2878b5" if is_anchor else "#d7b56d", 0.78 if is_anchor else 0.12,
                           resolution=6, edge="#164b73" if is_anchor else None)
        bounds_min = np.zeros(3)
        bounds_max = lengths
    else:
        for body_id in anchors:
            row = particle_by_id[body_id]
            sphere_surface(ax, np.array(row["position_m"]) * 1000.0, row["radius_m"] * 1000.0,
                           "#2878b5", 0.74, resolution=7, edge="#164b73")
        points = []
        for body_id in anchors:
            row = particle_by_id[body_id]
            centre = np.array(row["position_m"]) * 1000.0
            points.extend([centre - row["radius_m"] * 1000.0, centre + row["radius_m"] * 1000.0])
        bounds_min = np.min(points, axis=0) - 0.18
        bounds_max = np.max(points, axis=0) + 0.18
    for fibre in placement["fibres"]:
        colour = PALETTE[fibre["fibre_index"] % len(PALETTE)]
        members = np.array(fibre["member_centres_m"]) * 1000.0
        for centre in members:
            sphere_surface(ax, centre, radius, colour, 0.94, resolution=7, edge="#5c1515")
        ax.plot(members[:, 0], members[:, 1], members[:, 2], color="#4f1b1b", lw=1.0)
        ax.text(*members[len(members) // 2], f"F{fibre['fibre_index'] + 1}", fontsize=7, color="#111111")
        for body_id, member_index in zip(fibre["anchor_sand_body_ids"], fibre["anchor_member_indices"]):
            anchor = np.array(particle_by_id[body_id]["position_m"]) * 1000.0
            tip = members[member_index]
            ax.plot([anchor[0], tip[0]], [anchor[1], tip[1]], [anchor[2], tip[2]], color="#164b73", lw=1.6)
        if closeup:
            bounds_min = np.minimum(bounds_min, members.min(axis=0) - radius - 0.18)
            bounds_max = np.maximum(bounds_max, members.max(axis=0) + radius + 0.18)
    span = bounds_max - bounds_min
    ax.set_xlim(bounds_min[0], bounds_max[0])
    ax.set_ylim(bounds_min[1], bounds_max[1])
    ax.set_zlim(bounds_min[2], bounds_max[2])
    ax.set_box_aspect(span)
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_zlabel("z (mm)")
    ax.view_init(elev=23, azim=-52)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable Tier-1 placement render already exists")
    cfg = load_json(CONFIG)
    evaluation = load_json(EVALUATION)
    if not evaluation.get("passed") or evaluation["config_sha256"] != digest(CONFIG):
        raise RuntimeError("evaluation/config binding failed")
    stage26a = load_json(Path(cfg["sources"]["stage26a_design_config"]))
    result_path = Path(stage26a["source"]["stage25_selected_result"])
    if digest(result_path) != stage26a["source"]["stage25_selected_result_sha256"]:
        raise RuntimeError("Stage25 result binding failed")
    particles = load_json(result_path)["particles"]
    placements = []
    for case_eval in evaluation["cases"]:
        path = Path(case_eval["placement_path"])
        if digest(path) != case_eval["placement_sha256"]:
            raise RuntimeError("placement/evaluation binding failed")
        placements.append(load_json(path))
    fig = plt.figure(figsize=(16, 12), constrained_layout=True)
    axes = [fig.add_subplot(2, 2, index + 1, projection="3d") for index in range(4)]
    for column, placement in enumerate(placements):
        draw_case(axes[column], placement, particles, closeup=False)
        axes[column].set_title(f"{placement['fibre_count']} fibres: full periodic cell\n{placement['case']['dry_mass_percent']:.5f} wt%")
        draw_case(axes[column + 2], placement, particles, closeup=True)
        axes[column + 2].set_title(f"{placement['fibre_count']} fibres: fibre-anchor detail\nblue = declared anchor grains")
    fig.suptitle("Stage26b Tier-1 geometry preflight: actual F37 coordinates and radii", fontsize=17, weight="bold")
    fig.text(0.5, 0.008,
             "Geometry-only dry-mechanics preflight. Full-cell and cropped panels use equal physical data-unit scaling; crops change the view, not the geometry.\n"
             "No DEM relaxation, physical mixing, permeability, migration, polymer calibration or coupled-flow claim.",
             ha="center", va="bottom", fontsize=10)
    OUTPUT.mkdir(parents=True)
    image_path = OUTPUT / "stage26b_tier1_multifibre_placements.png"
    fig.savefig(image_path, dpi=210, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26b-tier1-placement-render.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "source_hashes": {
            "config": digest(CONFIG), "evaluation": digest(EVALUATION),
            "placements": {case["case_id"]: case["placement_sha256"] for case in evaluation["cases"]},
            "stage25_result": digest(result_path), "renderer": digest(Path(__file__)),
        },
        "image_path": str(image_path),
        "image_sha256": digest(image_path),
        "visual_semantics": "Actual physical coordinates and radii; equal data-unit scaling inside each panel; different crop windows do not magnify any object relative to its panel.",
        "claim_boundary": cfg["claim_boundary"],
        "authority": cfg["authority"],
    }
    with (OUTPUT / "render_manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "image_sha256": digest(image_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
