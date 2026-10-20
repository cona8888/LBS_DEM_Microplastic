#!/usr/bin/env python3
"""Render actual geometry and histories for the verified Stage26v pilot."""

import csv
import hashlib
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage26_runs" / "stage26v_216_flexible_fibre_integration_20260823" / "fixed_sand_pilot_01"
GEOMETRY = ROOT / "stage26_runs" / "stage26v_216_flexible_fibre_integration_20260823" / "geometry_export_02" / "geometry.json"
EVALUATION = ROOT / "stage26_evaluations" / "stage26v_216_flexible_fibre_integration_20260823" / "fixed_sand_evaluation_01" / "evaluation.json"
CHECKPOINT = EVALUATION.parent / "checkpoint_manifest.json"
OUT = ROOT / "stage26_renders" / "stage26v_216_flexible_fibre_integration_20260823" / "render_01"
SCRIPT = Path(__file__).resolve()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable render {OUT}")
evaluation, checkpoint, geometry, result = load(EVALUATION), load(CHECKPOINT), load(GEOMETRY), load(RUN / "result.json")
if evaluation.get("passed") is not True or checkpoint.get("passed") is not True:
    raise RuntimeError("Stage26v evaluation is not accepted")
if checkpoint["evaluation"]["sha256"] != sha(EVALUATION) or evaluation["source_bindings"]["result"]["sha256"] != sha(RUN / "result.json"):
    raise RuntimeError("evaluation binding mismatch")
cases = {item["case_id"]: item for item in result["cases"]}
centres = np.asarray([item["centre_m"] for item in geometry["spheres"]]) * 1e3
radii = np.asarray([item["radius_m"] for item in geometry["spheres"]]) * 1e3
histories = {}
for case_id, case in cases.items():
    path = RUN / case["history"]["path"]
    if sha(path) != case["history"]["sha256"]:
        raise RuntimeError("history hash mismatch")
    with path.open(newline="", encoding="utf-8") as stream:
        histories[case_id] = list(csv.DictReader(stream))

fig = plt.figure(figsize=(15.2, 10.0))
grid = fig.add_gridspec(2, 6, left=0.055, right=0.96, bottom=0.14, top=0.87, hspace=0.34, wspace=0.48)
theta = np.linspace(0, 2 * np.pi, 22)
phi = np.linspace(0, np.pi, 12)
for col, case_id in enumerate(("constricted", "open")):
    case = cases[case_id]
    ax = fig.add_subplot(grid[0, col * 3:(col + 1) * 3], projection="3d")
    initial = np.asarray(case["initial_node_positions_m"]) * 1e3
    terminal = np.asarray(case["terminal_node_positions_m"]) * 1e3
    path_points = np.vstack((initial, terminal))
    distances = np.min(np.linalg.norm(centres[:, None, :] - path_points[None, :, :], axis=2) - radii[:, None], axis=1)
    nearby = np.where(distances <= 0.42)[0]
    for index in nearby:
        centre, radius = centres[index], radii[index]
        x = centre[0] + radius * np.outer(np.cos(theta), np.sin(phi))
        y = centre[1] + radius * np.outer(np.sin(theta), np.sin(phi))
        z = centre[2] + radius * np.outer(np.ones_like(theta), np.cos(phi))
        ax.plot_surface(x, y, z, color="#c5b27e", alpha=0.25, linewidth=0, shade=True)
    ax.plot(initial[:, 0], initial[:, 1], initial[:, 2], "--", color="#666666", lw=2, label="initial fibre")
    ax.plot(terminal[:, 0], terminal[:, 1], terminal[:, 2], color="#c9232a", lw=4, label="terminal fibre")
    ax.scatter(terminal[:, 0], terminal[:, 1], terminal[:, 2], color="#8c1118", s=9)
    all_points = np.vstack((path_points, centres[nearby] - radii[nearby, None], centres[nearby] + radii[nearby, None]))
    spans = np.maximum(np.ptp(all_points, axis=0), 1e-3)
    ax.set_box_aspect(spans)
    ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.set_zlabel("z (mm)")
    title = "Constricted: contact-deflected passage" if case_id == "constricted" else "Open control: unobstructed passage"
    ax.set_title(title + f"\nactual scale; {len(nearby)} nearby grains shown", fontweight="bold", fontsize=12)
    ax.view_init(elev=22, azim=-58)
    ax.legend(loc="upper left", frameon=False, fontsize=9)

colors = {"constricted": "#d97706", "open": "#26834a"}
advance_ax = fig.add_subplot(grid[1, 0:2])
force_ax = fig.add_subplot(grid[1, 2:4])
state_ax = fig.add_subplot(grid[1, 4:6])
for case_id in ("constricted", "open"):
    rows = histories[case_id]
    t = np.asarray([float(row["time_s"]) for row in rows]) * 1e3
    advance = np.asarray([float(row["leading_node_advance_m"]) for row in rows]) * 1e6
    force = np.asarray([float(row["sum_contact_normal_force_n"]) for row in rows]) * 1e6
    contacts = np.asarray([int(row["distinct_contacted_sand_count"]) for row in rows])
    nodes = np.asarray([int(row["nodes_beyond_classification_plane"]) for row in rows])
    advance_ax.plot(t, advance, lw=2.3, color=colors[case_id], label=case_id)
    force_ax.plot(t, force, lw=2.3, color=colors[case_id], label=case_id)
    state_ax.step(t, nodes, where="post", lw=2.1, color=colors[case_id], label=f"{case_id}: nodes beyond plane")
    state_ax.step(t, contacts, where="post", lw=1.7, ls="--", color=colors[case_id], label=f"{case_id}: contacted grains")
advance_ax.set(title="Leading-node advance", xlabel="elapsed time (ms)", ylabel="advance (µm)")
force_ax.set(title="Resolved sand–fibre normal contact", xlabel="elapsed time (ms)", ylabel="sum of contact-force magnitudes (µN)")
state_ax.set(title="Passage and contact state", xlabel="elapsed time (ms)", ylabel="count")
for ax in (advance_ax, force_ax, state_ax):
    ax.axvspan(0, 0.25, color="#cccccc", alpha=0.25)
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, fontsize=8)

fig.suptitle("Stage26v — Flexible fibre in the accepted fixed 216-grain LBS geometry", fontsize=17, fontweight="bold", y=0.965)
fig.text(0.5, 0.91,
         "The constricted path engaged one grain and deflected; it did not form a multi-grain cage. Open-path advance = 509.8 µm; constricted advance = 195.7 µm.",
         ha="center", fontsize=10.5)
boundary = "Claim boundary: paired fixed-sand small-assembly integration pilot only. No mobile-sand response, polymer calibration, flow, permeability, deformation, or production concentration inference."
fig.text(0.055, 0.055, "\n".join(textwrap.wrap(boundary, 170)), ha="left", va="center", fontsize=9.2, color="#333333")

OUT.mkdir(parents=True)
image_path = OUT / "stage26v_fixed_sand_flexible_pilot.png"
fig.savefig(image_path, dpi=210, facecolor="white")
plt.close(fig)
manifest = {"schema": "lbs.stage26v-fixed-sand-flexible-pilot-render.v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "passed": True, "image": {"path": str(image_path), "sha256": sha(image_path)},
            "renderer": {"path": str(SCRIPT), "sha256": sha(SCRIPT)},
            "source_bindings": {"evaluation": {"path": str(EVALUATION), "sha256": sha(EVALUATION)},
                                "checkpoint": {"path": str(CHECKPOINT), "sha256": sha(CHECKPOINT)},
                                "result": {"path": str(RUN / "result.json"), "sha256": sha(RUN / "result.json")},
                                "geometry": {"path": str(GEOMETRY), "sha256": sha(GEOMETRY)}},
            "constricted_classification": evaluation["constricted_classification"],
            "multi_contact_cage_observed": evaluation["multi_contact_cage_observed"],
            "claim_boundary": evaluation["claim_boundary"]}
manifest_path = OUT / "render_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"image": str(image_path), "image_sha256": sha(image_path),
                  "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path)}, indent=2))
