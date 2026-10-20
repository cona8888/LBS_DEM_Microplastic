"""Render hash-bound Stage25a qualification and selected contact-network evidence."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm, colors
import numpy as np


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = PROJECT / "stage25_runs" / "stage25a_pure_sand_mechanics_20260813" / "qualification_04"
EVALUATION = PROJECT / "stage25_evaluations" / "stage25a_pure_sand_mechanics_20260813" / "evaluation_01" / "evaluation.json"
EXPORT = PROJECT / "stage25_exports" / "stage25a_pure_sand_mechanics_20260813" / "contact_export_01"
OUTPUT = PROJECT / "stage25_renders" / "stage25a_pure_sand_mechanics_20260813" / "render_01"
SCRIPT = Path(__file__)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def load_csv(path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def save_bound(fig, path):
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable render output already exists")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir()
    evaluation = load_json(EVALUATION)
    export_completion = load_json(EXPORT / "completion.json")
    if evaluation.get("passed") is not True or export_completion.get("passed") is not True:
        raise RuntimeError("render sources are not accepted")
    if export_completion["source"]["evaluation_sha256"] != digest(EVALUATION):
        raise RuntimeError("contact export is not bound to evaluation")
    for filename, key in [("particles.csv", "particles_csv_sha256"), ("contacts.csv", "contacts_csv_sha256"), ("cell.json", "cell_json_sha256")]:
        if digest(EXPORT / filename) != export_completion["artifacts"][key]:
            raise RuntimeError("contact-export artifact hash mismatch: " + filename)

    cases = sorted(evaluation["cases"], key=lambda row: row["preparation_friction_coefficient"])
    palette = {"mu_0.30": "#2271b2", "mu_0.45": "#e69f00", "mu_0.60": "#009e73"}
    histories = {case["case_id"]: load_csv(RUN / case["case_id"] / "history.csv") for case in cases}

    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.2), constrained_layout=True)
    for case in cases:
        case_id = case["case_id"]
        rows = histories[case_id]
        x = np.array([float(row["block"]) for row in rows])
        label = rf"$\mu_{{prep}}$={case['preparation_friction_coefficient']:.2f}"
        axes[0, 0].plot(x, [float(row["void_ratio"]) for row in rows], color=palette[case_id], lw=1.5, label=label)
        axes[0, 1].plot(x, [float(row["mean_effective_stress_pa_compression_positive"]) for row in rows], color=palette[case_id], lw=1.2)
        axes[1, 0].semilogy(x, [max(float(row["unbalanced_force"]), 1e-8) for row in rows], color=palette[case_id], lw=1.2)
    axes[0, 0].axhline(0.744, color="black", ls="--", lw=1.1, label="reported reference e=0.744")
    axes[0, 0].set(xlabel="check block", ylabel="void ratio, e", title="A  Periodic compaction path")
    axes[0, 0].set_ylim(0.65, 4.1)
    axes[0, 0].legend(frameon=False, fontsize=9)
    axes[0, 1].axhline(100.0, color="black", ls="--", lw=1.1)
    axes[0, 1].set(xlabel="check block", ylabel="mean effective stress (Pa)", title="B  Low-stress equilibrium target")
    axes[0, 1].set_ylim(-5, 125)
    axes[1, 0].axhline(0.02, color="black", ls="--", lw=1.1, label="acceptance limit")
    axes[1, 0].set(xlabel="check block", ylabel="unbalanced force", title="C  Mechanical relaxation")
    axes[1, 0].legend(frameon=False, fontsize=9)

    labels = [rf"$\mu_{{prep}}$={case['preparation_friction_coefficient']:.2f}" for case in cases]
    coordination = [case["terminal"]["coordination_excluding_degree_lt2_rattlers"] for case in cases]
    rattlers = [100.0 * case["terminal"]["rattler_fraction_degree_lt2_iterative"] for case in cases]
    xx = np.arange(len(cases))
    width = 0.36
    axes[1, 1].bar(xx - width / 2, coordination, width, color=[palette[c["case_id"]] for c in cases], label="coordination")
    ax2 = axes[1, 1].twinx()
    ax2.bar(xx + width / 2, rattlers, width, color="#999999", alpha=0.72, label="rattlers")
    axes[1, 1].axhline(3.0, color="#444444", ls="--", lw=1.0)
    ax2.axhline(35.0, color="#777777", ls=":", lw=1.0)
    axes[1, 1].set_xticks(xx, labels)
    axes[1, 1].set_ylabel("coordination excluding rattlers")
    ax2.set_ylabel("iterative rattler fraction (%)")
    axes[1, 1].set_title("D  Accepted terminal contact networks")
    axes[1, 1].legend(loc="upper left", frameon=False, fontsize=9)
    ax2.legend(loc="upper right", frameon=False, fontsize=9)
    for ax in axes.flat:
        ax.grid(alpha=0.18)
    selected = evaluation["selection"]
    fig.suptitle("Stage25a — load-bearing pure LBS-sand preparation qualification", fontsize=16, weight="bold")
    fig.text(0.5, -0.012,
             f"Selected {selected['case_id']}: e={selected['void_ratio']:.5f}, p′={selected['mean_effective_stress_pa']:.3f} Pa, "
             f"Z={selected['coordination_excluding_rattlers']:.3f}, contacts={selected['real_contact_count']}.  "
             "Preparation qualification only; not LBS material calibration, fibre mechanics, permeability, transient FSI, or coupled deformation-flow.",
             ha="center", va="top", fontsize=9.2)
    summary_path = OUTPUT / "stage25a_qualification_summary.png"
    save_bound(fig, summary_path)

    particles = load_csv(EXPORT / "particles.csv")
    contacts = load_csv(EXPORT / "contacts.csv")
    cell = load_json(EXPORT / "cell.json")
    xyz = {int(row["body_id"]): np.array([float(row["x_m"]), float(row["y_m"]), float(row["z_m"])]) * 1000.0 for row in particles}
    radii = {int(row["body_id"]): float(row["radius_m"]) * 1000.0 for row in particles}
    hsize = np.array(cell["cell_hsize"], dtype=float) * 1000.0
    lengths = np.diag(hsize)
    forces = np.array([float(row["normal_force_n"]) for row in contacts])
    log_norm = colors.LogNorm(vmin=max(forces.min(), 1e-9), vmax=forces.max())
    cmap = cm.viridis

    fig = plt.figure(figsize=(13.2, 9.5), constrained_layout=True)
    ax = fig.add_subplot(1, 1, 1, projection="3d")
    for row in contacts:
        i, j = int(row["id1"]), int(row["id2"])
        p1, p2 = xyz[i], xyz[j]
        delta = p2 - p1
        delta -= np.round(delta / lengths) * lengths
        endpoint = p1 + delta
        force = float(row["normal_force_n"])
        ax.plot([p1[0], endpoint[0]], [p1[1], endpoint[1]], [p1[2], endpoint[2]],
                color=cmap(log_norm(force)), lw=0.45 + 1.6 * math.sqrt(force / forces.max()), alpha=0.78)
    points = np.array([xyz[index] for index in sorted(xyz)])
    diameter = np.array([2.0 * radii[index] for index in sorted(radii)])
    sizes = (42.0 * np.array([radii[index] for index in sorted(radii)])) ** 2
    scatter = ax.scatter(points[:, 0], points[:, 1], points[:, 2], s=sizes, c=diameter,
                         cmap="YlOrBr", edgecolors="#5b3a18", linewidths=0.25, alpha=0.62, depthshade=True)
    ax.set_xlim(0, lengths[0]); ax.set_ylim(0, lengths[1]); ax.set_zlim(0, lengths[2])
    ax.set_box_aspect(lengths)
    ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.set_zlabel("z (mm)")
    ax.view_init(elev=23, azim=-55)
    ax.set_title("Actual periodic particle centres and 361 real YADE contacts\n(minimum-image contact segments; equal physical axis scale)", pad=18)
    particle_bar = fig.colorbar(scatter, ax=ax, shrink=0.62, pad=0.03)
    particle_bar.set_label("particle diameter (mm)")
    force_mappable = cm.ScalarMappable(norm=log_norm, cmap=cmap)
    force_bar = fig.colorbar(force_mappable, ax=ax, shrink=0.62, pad=0.10)
    force_bar.set_label("normal contact force (N, log scale)")
    fig.suptitle("Stage25a selected load-bearing pure-sand checkpoint — μprep=0.60", fontsize=16, weight="bold")
    fig.text(0.5, 0.015,
             f"216 LBS-PSD spheres | periodic cell {lengths[0]:.3f}×{lengths[1]:.3f}×{lengths[2]:.3f} mm | "
             f"e={selected['void_ratio']:.5f} | p′={selected['mean_effective_stress_pa']:.3f} Pa | "
             f"Z={selected['coordination_excluding_rattlers']:.3f}.  Actual geometry; no displacement magnification.\n"
             "Pure-sand DEM preparation evidence only; no fibre, permeability, transient FSI, or deformation-coupled-flow claim.",
             ha="center", va="bottom", fontsize=9.4)
    network_path = OUTPUT / "stage25a_selected_contact_network.png"
    save_bound(fig, network_path)

    manifest = {
        "schema": "lbs.stage25a-load-bearing-pure-sand-pilot.v1.render-manifest",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "selected_case_id": selected["case_id"],
        "source_hashes": {
            "evaluation_sha256": digest(EVALUATION),
            "contact_export_completion_sha256": digest(EXPORT / "completion.json"),
            "particles_csv_sha256": digest(EXPORT / "particles.csv"),
            "contacts_csv_sha256": digest(EXPORT / "contacts.csv"),
            "cell_json_sha256": digest(EXPORT / "cell.json"),
            "renderer_sha256": digest(SCRIPT),
        },
        "images": {
            summary_path.name: digest(summary_path),
            network_path.name: digest(network_path),
        },
        "visual_semantics": {
            "particle_coordinates": "Directly exported from accepted YADE checkpoint and converted from metres to millimetres.",
            "contact_segments": "Real YADE contact body pairs joined by orthogonal-periodic minimum-image segments.",
            "axis_scaling": "Equal physical data scaling in the 3-D network; no displacement or geometry magnification.",
        },
        "claim_boundary": evaluation["claim_boundary"],
    }
    with (OUTPUT / "render_manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "summary_sha256": digest(summary_path), "network_sha256": digest(network_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
