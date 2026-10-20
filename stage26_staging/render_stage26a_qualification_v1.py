"""Render the independently accepted Stage26a dry single-fibre checkpoint."""

import csv
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
PLACEMENT = PROJECT / "stage26_placements" / "stage26a_dry_f37_insertion_20260813" / "placement_03" / "placement.json"
RUN = PROJECT / "stage26_runs" / "stage26a_dry_f37_insertion_20260813" / "qualification_03"
EVALUATION = PROJECT / "stage26_evaluations" / "stage26a_dry_f37_insertion_20260813" / "evaluation_01" / "evaluation.json"
OUTPUT = PROJECT / "stage26_renders" / "stage26a_dry_f37_insertion_20260813" / "qualification_render_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def rows(path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sphere_surface(ax, centre, radius, color, alpha, resolution=8, edge=None):
    u = np.linspace(0, 2 * np.pi, 2 * resolution); v = np.linspace(0, np.pi, resolution)
    x = centre[0] + radius * np.outer(np.cos(u), np.sin(v)); y = centre[1] + radius * np.outer(np.sin(u), np.sin(v)); z = centre[2] + radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(x, y, z, color=color, alpha=alpha, linewidth=0.10 if edge else 0, edgecolor=edge, shade=True)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable render output already exists")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.mkdir()
    cfg = load_json(CONFIG); placement = load_json(PLACEMENT); evaluation = load_json(EVALUATION)
    result_path = RUN / "result.json"; result = load_json(result_path)
    if evaluation.get("passed") is not True or result.get("passed") is not True:
        raise RuntimeError("render sources are not accepted")
    if evaluation["evidence"]["result_sha256"] != digest(result_path):
        raise RuntimeError("evaluation/result binding mismatch")
    conditioning = rows(RUN / "conditioning_history.csv"); free = rows(RUN / "free_relaxation_history.csv")
    combined = conditioning + free; x = np.arange(1, len(combined) + 1); release = len(conditioning) + 0.5

    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.0), constrained_layout=True)
    axes[0, 0].semilogy(x, [max(float(row["unbalanced_force"]), 1e-8) for row in combined], color="#375a7f", lw=1.5)
    axes[0, 0].axhline(cfg["acceptance"]["maximum_unbalanced_force"], color="black", ls="--", label="acceptance limit")
    axes[0, 0].set(xlabel="500-step block", ylabel="unbalanced force", title="A  Mechanical equilibrium")
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(x, [float(row["mean_effective_stress_pa_compression_positive"]) for row in combined], color="#009e73", lw=1.5)
    axes[0, 1].axhline(100.0, color="black", ls="--", label="100 Pa target")
    axes[0, 1].set(xlabel="500-step block", ylabel="mean effective stress (Pa)", title="B  Stress control")
    axes[0, 1].legend(frameon=False)
    axes[1, 0].step(x, [int(row["distinct_sand_contacts_per_fibre"]) for row in combined], where="mid", color="#d62728", lw=1.8)
    axes[1, 0].axhline(2, color="black", ls="--", label="minimum engagement")
    axes[1, 0].set(xlabel="500-step block", ylabel="distinct contacted sand grains", title="C  Fibre engagement", ylim=(-0.1, 3.1))
    axes[1, 0].legend(frameon=False)
    axes[1, 1].plot(x, [float(row["maximum_nonaffine_sand_displacement_over_D50"]) for row in combined], color="#e69f00", lw=1.6, label="max sand displacement / D50")
    axes[1, 1].plot(x, [float(row["fibre_com_displacement_over_length"]) for row in combined], color="#8e44ad", lw=1.6, label="fibre COM displacement / L")
    axes[1, 1].axhline(cfg["acceptance"]["maximum_sand_displacement_over_D50"], color="#e69f00", ls="--", alpha=0.8)
    axes[1, 1].set(xlabel="500-step block", ylabel="normalized displacement", title="D  Rearrangement and fibre motion")
    axes[1, 1].legend(frameon=False, fontsize=9)
    for ax in axes.flat:
        ax.axvline(release, color="#777777", ls=":", lw=1.2)
        ax.grid(alpha=0.18)
    fig.suptitle("Stage26a — fixed conditioning followed by a free F37-fibre relaxation", fontsize=16, weight="bold")
    terminal = evaluation["terminal"]
    fig.text(0.5, -0.012,
             f"Fibre released after block {len(conditioning)}; terminal contacts={terminal['distinct_sand_contacts_per_fibre']}, p′={terminal['mean_effective_stress_pa_compression_positive']:.3f} Pa, "
             f"unbalanced={terminal['unbalanced_force']:.4f}, Zsand={terminal['sand_coordination_excluding_degree_lt2_rattlers']:.3f}.  "
             "Dry one-fibre compatibility only; no polymer/LBS calibration, permeability, migration, transient FSI, or coupled-flow claim.",
             ha="center", va="top", fontsize=9.2)
    summary_path = OUTPUT / "stage26a_dry_relaxation_summary.png"
    fig.savefig(summary_path, dpi=220, bbox_inches="tight", facecolor="white"); plt.close(fig)

    particles = result["particles"]
    sand = [row for row in particles if row["phase"] == "sand"]; fibre = [row for row in particles if row["phase"] == "fibre"]
    sand_by_id = {row["body_id"]: row for row in sand}; fibre_ids = {row["body_id"] for row in fibre}
    contacted = set(terminal["contacted_sand_body_ids"])
    lengths = np.array(terminal["cell_dimensions_m"], dtype=float) * 1000
    fibre_points = np.array([row["position_m"] for row in fibre]) * 1000
    initial_fibre = np.array(placement["member_centres_m"]) * 1000
    fibre_radius = fibre[0]["radius_m"] * 1000
    fibre_com = fibre_points.mean(axis=0)
    close_radius = 1.05

    fig = plt.figure(figsize=(15.0, 8.2), constrained_layout=True)
    full = fig.add_subplot(1, 2, 1, projection="3d"); close = fig.add_subplot(1, 2, 2, projection="3d")
    for row in sand:
        centre = np.array(row["position_m"]) * 1000; radius = row["radius_m"] * 1000
        anchor = row["body_id"] in contacted
        sphere_surface(full, centre, radius, "#2878b5" if anchor else "#d7b56d", 0.70 if anchor else 0.12, resolution=6, edge="#164b73" if anchor else None)
        if anchor or np.linalg.norm(centre - fibre_com) <= close_radius + radius:
            sphere_surface(close, centre, radius, "#2878b5" if anchor else "#d7b56d", 0.75 if anchor else 0.25, resolution=8, edge="#164b73" if anchor else None)
    for centre in fibre_points:
        sphere_surface(full, centre, fibre_radius, "#d62728", 0.95, resolution=7, edge="#7f0000")
        sphere_surface(close, centre, fibre_radius, "#d62728", 0.95, resolution=9, edge="#7f0000")
    full.plot(fibre_points[:, 0], fibre_points[:, 1], fibre_points[:, 2], color="#7f0000", lw=1.3)
    close.plot(fibre_points[:, 0], fibre_points[:, 1], fibre_points[:, 2], color="#7f0000", lw=1.3, label="terminal F37 centreline")
    close.plot(initial_fibre[:, 0], initial_fibre[:, 1], initial_fibre[:, 2], color="#555555", lw=1.0, ls="--", label="initial centreline (actual, unmagnified)")
    for contact in result["contacts"]:
        first, second = contact["id1"], contact["id2"]
        if (first in fibre_ids and second in contacted) or (second in fibre_ids and first in contacted):
            fibre_id = first if first in fibre_ids else second; sand_id = second if first in fibre_ids else first
            a = np.array(next(row for row in fibre if row["body_id"] == fibre_id)["position_m"]) * 1000
            b = np.array(sand_by_id[sand_id]["position_m"]) * 1000
            close.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]], color="#101010", lw=2.0)
    full.set_xlim(0, lengths[0]); full.set_ylim(0, lengths[1]); full.set_zlim(0, lengths[2]); full.set_box_aspect(np.array(lengths, copy=True))
    margin = 0.75
    close.set_xlim(fibre_com[0] - margin, fibre_com[0] + margin); close.set_ylim(fibre_com[1] - margin, fibre_com[1] + margin); close.set_zlim(fibre_com[2] - margin, fibre_com[2] + margin); close.set_box_aspect(np.ones(3))
    for ax, title in [(full, "A  Full periodic cell"), (close, "B  Actual-scale lodged-fibre detail")]:
        ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.set_zlabel("z (mm)"); ax.view_init(elev=23, azim=-54); ax.set_title(title, pad=12)
    close.legend(loc="upper left", frameon=False, fontsize=8)
    fig.suptitle("Stage26a accepted free-fibre checkpoint — actual particles and contact geometry", fontsize=16, weight="bold")
    fig.text(0.5, 0.012,
             f"216 sand spheres + one rigid 37-member F37 clump | final contacts to sand IDs {sorted(contacted)} | fibre translation={1e6*terminal['fibre_com_displacement_m']:.3f} µm | rotation={terminal['fibre_tip_axis_rotation_degrees']:.3f}°.\n"
             "Coordinates and radii are unscaled; transparency and the close-up crop change visibility only. Dry compatibility evidence—not permeability, polymer flexibility, migration, or coupled flow.",
             ha="center", va="bottom", fontsize=9.2)
    geometry_path = OUTPUT / "stage26a_accepted_free_fibre_geometry.png"
    fig.savefig(geometry_path, dpi=220, bbox_inches="tight", facecolor="white"); plt.close(fig)

    manifest = {
        "schema": "lbs.stage26a-dry-f37-insertion.v2.render-manifest", "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {"config": digest(CONFIG), "placement": digest(PLACEMENT), "result": digest(result_path), "evaluation": digest(EVALUATION), "conditioning_history": digest(RUN / "conditioning_history.csv"), "free_history": digest(RUN / "free_relaxation_history.csv"), "renderer": digest(Path(__file__))},
        "images": {summary_path.name: digest(summary_path), geometry_path.name: digest(geometry_path)},
        "visual_semantics": {"geometry": "Direct terminal YADE coordinates and radii in millimetres.", "initial_overlay": "Direct placement coordinates, no displacement multiplier.", "axes": "Equal physical scale; close-up is a crop, not magnification of relative geometry.", "transparency": "Visibility aid only."},
        "claim_boundary": cfg["claim_boundary"],
    }
    with (OUTPUT / "render_manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False); stream.write("\n")
    print(json.dumps({"passed": True, "summary_sha256": digest(summary_path), "geometry_sha256": digest(geometry_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
