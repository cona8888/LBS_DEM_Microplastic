"""Render the verified Revision-3 selected two-F37 geometry at actual scale."""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CHECKPOINT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/campaign_checkpoint_01/checkpoint_manifest.json"
EXPECTED_CHECKPOINT_SHA256 = "abc7ca7bd5828c9febaa1a95b5f4e86de4beb7040880bf12a7442717fd303819"
NETWORK = ROOT / "stage26_network_exports/stage26b_revision2_stage25_network_20260816/export_04/network.json"
PLACEMENT = ROOT / "stage26_placements/stage26b_revision3_joint_placement_20260816/candidate_generation_01/stage26b_f002_revision3_candidate_01/placement.json"
OUTPUT = ROOT / "stage26_renders/stage26b_revision3_joint_placement_20260816/selected_candidate_render_01"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sphere_mesh(center, radius, nu=10, nv=7):
    u = np.linspace(0.0, 2.0 * np.pi, nu)
    v = np.linspace(0.0, np.pi, nv)
    x = center[0] + radius * np.outer(np.cos(u), np.sin(v))
    y = center[1] + radius * np.outer(np.sin(u), np.sin(v))
    z = center[2] + radius * np.outer(np.ones_like(u), np.cos(v))
    return x, y, z


def draw_sphere(ax, center, radius, color, alpha, nu=10, nv=7, edge="none"):
    x, y, z = sphere_mesh(center, radius, nu=nu, nv=nv)
    ax.plot_surface(x, y, z, color=color, alpha=alpha, linewidth=0.15 if edge != "none" else 0.0, edgecolor=edge, shade=True)


def set_equal_physical_scale(ax, lower, upper):
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    span = upper - lower
    ax.set_xlim(lower[0], upper[0])
    ax.set_ylim(lower[1], upper[1])
    ax.set_zlim(lower[2], upper[2])
    ax.set_box_aspect(span)
    ax.set_proj_type("ortho")


def draw_cell(ax, lengths_mm, color="#555555", alpha=0.35):
    corners = np.asarray([[x, y, z] for x in (0.0, lengths_mm[0]) for y in (0.0, lengths_mm[1]) for z in (0.0, lengths_mm[2])])
    for i, a in enumerate(corners):
        for b in corners[i + 1 :]:
            if np.count_nonzero(np.abs(a - b) > 1e-12) == 1:
                ax.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]], color=color, alpha=alpha, lw=0.7)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable render output already exists")
    if digest(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("campaign checkpoint hash mismatch")
    checkpoint = load(CHECKPOINT)
    if checkpoint.get("passed") is not True or checkpoint["authority"].get("selection_and_render_authorized") is not True:
        raise RuntimeError("campaign checkpoint does not authorize rendering")
    if checkpoint["authority"].get("prefilter_yade_execution_authorized") is not False:
        raise RuntimeError("unexpected YADE authority in campaign checkpoint")
    if digest(PLACEMENT) != checkpoint["evidence"]["selected_placement_sha256"]:
        raise RuntimeError("selected placement hash mismatch")
    placement = load(PLACEMENT)
    network = load(NETWORK)
    if placement.get("passed") is not True or placement["candidate"]["candidate_id"] != checkpoint["summary"]["selected_candidate_id"]:
        raise RuntimeError("selected placement identity or pass state mismatch")
    if len(placement["fibres"]) != 2 or any(len(fibre["member_centres_m"]) != 37 for fibre in placement["fibres"]):
        raise RuntimeError("selected placement does not contain two F37 fibres")

    lengths = np.asarray(placement["cell_dimensions_m"], dtype=float)
    lengths_mm = lengths * 1e3
    sand_centres = np.asarray([row["position_m"] for row in network["particles"]], dtype=float) * 1e3
    sand_radii = np.asarray([row["radius_m"] for row in network["particles"]], dtype=float) * 1e3
    body_to_index = {int(row["sand_body_id"]): i for i, row in enumerate(network["particles"])}
    fibre_members = [np.asarray(fibre["member_centres_m"], dtype=float) * 1e3 for fibre in placement["fibres"]]
    fibre_radius = float(placement["member_radius_m"]) * 1e3
    anchor_sets = [set(fibre["anchor_sand_body_ids"]) for fibre in placement["fibres"]]
    all_anchor_ids = anchor_sets[0] | anchor_sets[1]
    anchor_indices = {body_to_index[body_id] for body_id in all_anchor_ids}

    fig = plt.figure(figsize=(15.5, 8.3), constrained_layout=False, facecolor="white")
    gs = fig.add_gridspec(1, 2, left=0.03, right=0.97, bottom=0.17, top=0.89, wspace=0.05)
    ax_full = fig.add_subplot(gs[0, 0], projection="3d")
    ax_close = fig.add_subplot(gs[0, 1], projection="3d")
    fibre_colors = ["#d62728", "#1f77b4"]
    anchor_colors = ["#ffbf00", "#36a657"]

    for index, (centre, radius) in enumerate(zip(sand_centres, sand_radii)):
        if index in anchor_indices:
            continue
        draw_sphere(ax_full, centre, radius, "#c8b28a", 0.10, nu=8, nv=5)
    for fibre_index, fibre in enumerate(placement["fibres"]):
        for body_id in fibre["anchor_sand_body_ids"]:
            index = body_to_index[body_id]
            draw_sphere(ax_full, sand_centres[index], sand_radii[index], anchor_colors[fibre_index], 0.90, nu=13, nv=9, edge="#333333")
        members = fibre_members[fibre_index]
        ax_full.plot(members[:, 0], members[:, 1], members[:, 2], color=fibre_colors[fibre_index], lw=3.0, zorder=15)
        for centre in members:
            draw_sphere(ax_full, centre, fibre_radius, fibre_colors[fibre_index], 0.98, nu=9, nv=6)
    draw_cell(ax_full, lengths_mm)
    set_equal_physical_scale(ax_full, np.zeros(3), lengths_mm)
    ax_full.view_init(elev=23, azim=-55)
    ax_full.set_title("Full 216-grain cell — actual geometry", fontsize=12, pad=8)

    all_members = np.vstack(fibre_members)
    near = []
    for index, (centre, radius) in enumerate(zip(sand_centres, sand_radii)):
        surface_distance = np.min(np.linalg.norm(all_members - centre, axis=1) - radius - fibre_radius)
        if surface_distance <= 0.55 or index in anchor_indices:
            near.append(index)
    for index in near:
        if index in anchor_indices:
            continue
        draw_sphere(ax_close, sand_centres[index], sand_radii[index], "#c8b28a", 0.26, nu=10, nv=7, edge="#a18e6d")
    for fibre_index, fibre in enumerate(placement["fibres"]):
        members = fibre_members[fibre_index]
        ax_close.plot(members[:, 0], members[:, 1], members[:, 2], color=fibre_colors[fibre_index], lw=4.0, zorder=15)
        for centre in members:
            draw_sphere(ax_close, centre, fibre_radius, fibre_colors[fibre_index], 1.0, nu=12, nv=8)
        for endpoint, body_id in zip((members[0], members[-1]), fibre["anchor_sand_body_ids"]):
            index = body_to_index[body_id]
            draw_sphere(ax_close, sand_centres[index], sand_radii[index], anchor_colors[fibre_index], 0.92, nu=15, nv=10, edge="#222222")
            anchor_centre = sand_centres[index]
            ax_close.plot([endpoint[0], anchor_centre[0]], [endpoint[1], anchor_centre[1]], [endpoint[2], anchor_centre[2]], color="#222222", ls="--", lw=0.9)
    lower = np.minimum(all_members.min(axis=0), sand_centres[list(anchor_indices)].min(axis=0)) - 0.55
    upper = np.maximum(all_members.max(axis=0), sand_centres[list(anchor_indices)].max(axis=0)) + 0.55
    lower = np.maximum(lower, 0.0)
    upper = np.minimum(upper, lengths_mm)
    set_equal_physical_scale(ax_close, lower, upper)
    ax_close.view_init(elev=25, azim=-55)
    ax_close.set_title("Selected F37 pair and four anchor grains — actual scale", fontsize=12, pad=8)

    for ax in (ax_full, ax_close):
        ax.set_xlabel("x (mm)", labelpad=6)
        ax.set_ylabel("y (mm)", labelpad=6)
        ax.set_zlabel("z (mm)", labelpad=6)
        ax.grid(False)
        ax.xaxis.pane.set_alpha(0.025)
        ax.yaxis.pane.set_alpha(0.025)
        ax.zaxis.pane.set_alpha(0.025)

    max_force = max(fibre["initial_normal_force_residual_relative"] for fibre in placement["fibres"])
    max_moment = max(fibre["initial_normal_moment_residual_relative"] for fibre in placement["fibres"])
    clearance_mm = placement["joint_minimum_fibre_fibre_clearance_m"] * 1e3
    clearance_gate_mm = 0.00041129327255147165 * 1e3
    fig.suptitle("Stage 26 Revision 3: verified offline two-fibre insertion candidate", fontsize=16, fontweight="bold", y=0.965)
    fig.text(0.03, 0.105, f"Candidate 01 | seed {placement['candidate']['seed']} | 2 rigid kinked fibres × 37 overlapping members | member radius 0.050 mm", fontsize=10.5, color="#222222")
    fig.text(0.03, 0.070, f"Independent gates: fibre clearance {clearance_mm:.3f} mm ≥ {clearance_gate_mm:.3f} mm; max force residual {max_force:.5f} ≤ 0.05000; max moment residual {max_moment:.5f} ≤ 0.02000", fontsize=10.5, color="#222222")
    fig.text(0.03, 0.034, "Colours: Fibre 1 red / anchors gold; Fibre 2 blue / anchors green. Coordinates and particle sizes are not magnified; both 3-D panels use equal physical data-unit scaling.", fontsize=9.5, color="#333333")
    fig.text(0.5, 0.010, "Claim boundary: verified offline insertion geometry only — no YADE relaxation, mechanical stability, polymer calibration, deformation, permeability, migration, or coupled-flow result.", ha="center", fontsize=9.0, color="#7a1f1f")

    OUTPUT.mkdir(parents=True)
    image_path = OUTPUT / "stage26b_revision3_selected_geometry.png"
    fig.savefig(image_path, dpi=190, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26b-revision3-selected-geometry-render-manifest.v1",
        "passed": True,
        "status": "rendered_verified_offline_geometry",
        "selected_candidate_id": placement["candidate"]["candidate_id"],
        "source_hashes": {
            "campaign_checkpoint": digest(CHECKPOINT),
            "selected_placement": digest(PLACEMENT),
            "network": digest(NETWORK),
            "renderer": digest(__file__)
        },
        "render": {
            "image_path": str(image_path),
            "image_sha256": digest(image_path),
            "equal_physical_data_unit_scaling": True,
            "coordinate_or_displacement_magnification": False,
            "full_cell_sand_count": len(sand_centres),
            "closeup_sand_count": len(near),
            "fibre_count": 2,
            "members_per_fibre": 37
        },
        "metrics": {
            "minimum_fibre_fibre_clearance_m": placement["joint_minimum_fibre_fibre_clearance_m"],
            "minimum_clearance_gate_m": 0.00041129327255147165,
            "maximum_force_residual_relative": max_force,
            "maximum_moment_residual_relative": max_moment
        },
        "authority": {"visual_review_authorized": True, "prefilter_yade_execution_authorized": False},
        "claim_boundary": "Verified offline insertion geometry only. No YADE relaxation, mechanical stability, polymer calibration, deformation, permeability, migration, or coupled-flow result."
    }
    manifest_path = OUTPUT / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "image_path": str(image_path), "image_sha256": digest(image_path), "manifest_sha256": digest(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
