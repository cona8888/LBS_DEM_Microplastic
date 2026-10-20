"""Render Revision-3 candidate with both fibres visually unambiguous."""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from render_stage26b_revision3_selected_geometry_v1 import (
    digest,
    draw_cell,
    draw_sphere,
    load,
    set_equal_physical_scale,
)


ROOT = Path("C:/MATDEM_MICROPLASTIC")
BASE_RENDERER = ROOT / "stage26_staging/render_stage26b_revision3_selected_geometry_v1.py"
EXPECTED_BASE_RENDERER_SHA256 = "2a9639ba58ea1e86e3893d2963bf9fd06c75dfdcae5110659368c587f6ad6c78"
CHECKPOINT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/campaign_checkpoint_01/checkpoint_manifest.json"
EXPECTED_CHECKPOINT_SHA256 = "abc7ca7bd5828c9febaa1a95b5f4e86de4beb7040880bf12a7442717fd303819"
NETWORK = ROOT / "stage26_network_exports/stage26b_revision2_stage25_network_20260816/export_04/network.json"
PLACEMENT = ROOT / "stage26_placements/stage26b_revision3_joint_placement_20260816/candidate_generation_01/stage26b_f002_revision3_candidate_01/placement.json"
OUTPUT = ROOT / "stage26_renders/stage26b_revision3_joint_placement_20260816/selected_candidate_render_02"


def draw_fibres_and_anchors(ax, placement, fibre_members, sand_centres, sand_radii, body_to_index, fibre_radius, anchor_alpha, label_endpoints=False):
    fibre_colors = ["#d62728", "#1769aa"]
    anchor_colors = ["#ffbf00", "#2ca25f"]
    for fibre_index, fibre in enumerate(placement["fibres"]):
        members = fibre_members[fibre_index]
        for body_id in fibre["anchor_sand_body_ids"]:
            index = body_to_index[body_id]
            draw_sphere(ax, sand_centres[index], sand_radii[index], anchor_colors[fibre_index], anchor_alpha, nu=14, nv=9, edge="#333333")
        ax.plot(members[:, 0], members[:, 1], members[:, 2], color="white", lw=6.0, alpha=0.95, zorder=25)
        ax.plot(members[:, 0], members[:, 1], members[:, 2], color=fibre_colors[fibre_index], lw=3.8, zorder=30, label=f"Fibre {fibre_index + 1}")
        for centre in members:
            draw_sphere(ax, centre, fibre_radius, fibre_colors[fibre_index], 1.0, nu=10, nv=7)
        if label_endpoints:
            for endpoint_index, endpoint in zip((0, 36), (members[0], members[-1])):
                ax.text(endpoint[0], endpoint[1], endpoint[2] + 0.10, f"F{fibre_index + 1}:{endpoint_index}", color=fibre_colors[fibre_index], fontsize=8, fontweight="bold")


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable render-02 output already exists")
    if digest(BASE_RENDERER) != EXPECTED_BASE_RENDERER_SHA256:
        raise RuntimeError("base renderer dependency changed")
    if digest(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("campaign checkpoint hash mismatch")
    checkpoint = load(CHECKPOINT)
    if checkpoint.get("passed") is not True or checkpoint["authority"].get("selection_and_render_authorized") is not True:
        raise RuntimeError("render handoff is not authorized")
    if checkpoint["authority"].get("prefilter_yade_execution_authorized") is not False:
        raise RuntimeError("unexpected downstream authority")
    if digest(PLACEMENT) != checkpoint["evidence"]["selected_placement_sha256"]:
        raise RuntimeError("selected placement hash mismatch")
    placement = load(PLACEMENT)
    network = load(NETWORK)
    lengths_mm = np.asarray(placement["cell_dimensions_m"], dtype=float) * 1e3
    sand_centres = np.asarray([row["position_m"] for row in network["particles"]], dtype=float) * 1e3
    sand_radii = np.asarray([row["radius_m"] for row in network["particles"]], dtype=float) * 1e3
    fibre_members = [np.asarray(fibre["member_centres_m"], dtype=float) * 1e3 for fibre in placement["fibres"]]
    fibre_radius = float(placement["member_radius_m"]) * 1e3
    body_to_index = {int(row["sand_body_id"]): index for index, row in enumerate(network["particles"])}
    anchor_indices = {body_to_index[body_id] for fibre in placement["fibres"] for body_id in fibre["anchor_sand_body_ids"]}

    fig = plt.figure(figsize=(18.5, 7.7), facecolor="white")
    gs = fig.add_gridspec(1, 3, left=0.025, right=0.985, bottom=0.19, top=0.87, wspace=0.055)
    axes = [fig.add_subplot(gs[0, i], projection="3d") for i in range(3)]
    ax_full, ax_plan, ax_isolated = axes

    for index, (centre, radius) in enumerate(zip(sand_centres, sand_radii)):
        if index not in anchor_indices:
            draw_sphere(ax_full, centre, radius, "#c8b28a", 0.075, nu=8, nv=5)
    draw_fibres_and_anchors(ax_full, placement, fibre_members, sand_centres, sand_radii, body_to_index, fibre_radius, 0.86)
    draw_cell(ax_full, lengths_mm)
    set_equal_physical_scale(ax_full, np.zeros(3), lengths_mm)
    ax_full.view_init(elev=20, azim=-48)
    ax_full.set_title("A. Full 216-grain cell", fontsize=12, pad=8)

    all_members = np.vstack(fibre_members)
    near = []
    for index, (centre, radius) in enumerate(zip(sand_centres, sand_radii)):
        surface_distance = np.min(np.linalg.norm(all_members - centre, axis=1) - radius - fibre_radius)
        if surface_distance <= 0.38 and index not in anchor_indices:
            near.append(index)
    for index in near:
        draw_sphere(ax_plan, sand_centres[index], sand_radii[index], "#c8b28a", 0.11, nu=9, nv=6)
    draw_fibres_and_anchors(ax_plan, placement, fibre_members, sand_centres, sand_radii, body_to_index, fibre_radius, 0.50, label_endpoints=True)
    lower = np.maximum(np.minimum(all_members.min(axis=0), sand_centres[list(anchor_indices)].min(axis=0)) - 0.55, 0.0)
    upper = np.minimum(np.maximum(all_members.max(axis=0), sand_centres[list(anchor_indices)].max(axis=0)) + 0.55, lengths_mm)
    set_equal_physical_scale(ax_plan, lower, upper)
    ax_plan.view_init(elev=88, azim=-90)
    ax_plan.set_title("B. Near-top view: both fibres separated", fontsize=12, pad=8)

    draw_fibres_and_anchors(ax_isolated, placement, fibre_members, sand_centres, sand_radii, body_to_index, fibre_radius, 0.30, label_endpoints=True)
    set_equal_physical_scale(ax_isolated, lower, upper)
    ax_isolated.view_init(elev=22, azim=-90)
    ax_isolated.set_title("C. Fibre paths; anchors translucent", fontsize=12, pad=8)

    for ax in axes:
        ax.set_xlabel("x (mm)", labelpad=5)
        ax.set_ylabel("y (mm)", labelpad=5)
        ax.set_zlabel("z (mm)", labelpad=5)
        ax.grid(False)
        ax.xaxis.pane.set_alpha(0.02)
        ax.yaxis.pane.set_alpha(0.02)
        ax.zaxis.pane.set_alpha(0.02)
    ax_isolated.legend(loc="lower left", framealpha=0.92, fontsize=8)

    max_force = max(fibre["initial_normal_force_residual_relative"] for fibre in placement["fibres"])
    max_moment = max(fibre["initial_normal_moment_residual_relative"] for fibre in placement["fibres"])
    clearance_mm = placement["joint_minimum_fibre_fibre_clearance_m"] * 1e3
    gate_mm = 0.00041129327255147165 * 1e3
    fig.suptitle("Stage 26 Revision 3: verified two-F37 offline insertion geometry", fontsize=16, fontweight="bold", y=0.955)
    fig.text(0.03, 0.120, f"Candidate 01 | seed {placement['candidate']['seed']} | red Fibre 1 and blue Fibre 2 | each is a rigid kinked chain of 37 overlapping r = 0.050 mm members", fontsize=10.3)
    fig.text(0.03, 0.082, f"Independent gates: fibre clearance {clearance_mm:.3f} mm ≥ {gate_mm:.3f} mm; max force residual {max_force:.5f} ≤ 0.05000; max moment residual {max_moment:.5f} ≤ 0.02000", fontsize=10.3)
    fig.text(0.03, 0.045, "Coordinates, particle radii and fibre radii are not magnified. All panels use equal physical data-unit scaling. Anchor transparency in panels B–C is solely to reveal the fibre paths.", fontsize=9.4, color="#333333")
    fig.text(0.5, 0.012, "Claim boundary: verified offline insertion geometry only — no YADE relaxation, mechanical stability, polymer calibration, deformation, permeability, migration, or coupled-flow result.", ha="center", fontsize=9.0, color="#7a1f1f")

    OUTPUT.mkdir(parents=True)
    image_path = OUTPUT / "stage26b_revision3_selected_geometry_unambiguous.png"
    fig.savefig(image_path, dpi=190, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26b-revision3-selected-geometry-render-manifest.v2",
        "passed": True,
        "status": "rendered_unambiguous_two_fibre_geometry",
        "selected_candidate_id": placement["candidate"]["candidate_id"],
        "source_hashes": {"campaign_checkpoint": digest(CHECKPOINT), "selected_placement": digest(PLACEMENT), "network": digest(NETWORK), "base_renderer": digest(BASE_RENDERER), "renderer": digest(__file__)},
        "render": {"image_path": str(image_path), "image_sha256": digest(image_path), "equal_physical_data_unit_scaling": True, "coordinate_or_radius_magnification": False, "anchor_transparency_used_to_reveal_fibre_paths": True, "fibre_count": 2, "members_per_fibre": 37},
        "metrics": {"minimum_fibre_fibre_clearance_m": placement["joint_minimum_fibre_fibre_clearance_m"], "minimum_clearance_gate_m": 0.00041129327255147165, "maximum_force_residual_relative": max_force, "maximum_moment_residual_relative": max_moment},
        "authority": {"visual_review_authorized": True, "prefilter_yade_execution_authorized": False},
        "claim_boundary": "Verified offline insertion geometry only. No YADE relaxation, mechanical stability, polymer calibration, deformation, permeability, migration, or coupled-flow result."
    }
    manifest_path = OUTPUT / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "image_path": str(image_path), "image_sha256": digest(image_path), "manifest_sha256": digest(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
