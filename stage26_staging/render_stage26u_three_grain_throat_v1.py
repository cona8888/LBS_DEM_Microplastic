#!/usr/bin/env python3
"""Render the independently accepted Stage26u geometry and histories."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN = ROOT / "stage26_designs" / "stage26u_three_grain_throat_20260820" / "throat_design_01" / "config.json"
RUN = ROOT / "stage26_runs" / "stage26u_three_grain_throat_20260820" / "throat_01"
EVAL = ROOT / "stage26_evaluations" / "stage26u_three_grain_throat_20260820" / "throat_evaluation_01" / "evaluation.json"
CHECKPOINT = EVAL.parent / "checkpoint_manifest.json"
OUT = ROOT / "stage26_renders" / "stage26u_three_grain_throat_20260820" / "render_01"
SCRIPT = Path(__file__).resolve()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable render {OUT}")
for path in (DESIGN, EVAL, CHECKPOINT, RUN / "result.json"):
    if not path.is_file():
        raise RuntimeError(f"missing evidence {path}")
evaluation = load(EVAL)
checkpoint = load(CHECKPOINT)
if evaluation.get("passed") is not True or checkpoint.get("passed") is not True:
    raise RuntimeError("Stage26u evaluation is not accepted")
if checkpoint["evaluation"]["sha256"] != sha(EVAL):
    raise RuntimeError("checkpoint-to-evaluation hash mismatch")
if evaluation["source_bindings"]["result"]["sha256"] != sha(RUN / "result.json"):
    raise RuntimeError("evaluation-to-result hash mismatch")
config = load(DESIGN)
result = load(RUN / "result.json")
cases = sorted(result["cases"], key=lambda item: item["throat_to_fibre_diameter_ratio"])

histories = {}
for case in cases:
    record_path = RUN / case["result_artifact"]["path"]
    if sha(record_path) != case["result_artifact"]["sha256"]:
        raise RuntimeError(f"record hash mismatch for {case['case_id']}")
    history_path = RUN / case["history"]["path"]
    if sha(history_path) != case["history"]["sha256"]:
        raise RuntimeError(f"history hash mismatch for {case['case_id']}")
    with history_path.open(newline="", encoding="utf-8") as stream:
        histories[case["case_id"]] = list(csv.DictReader(stream))

OUT.mkdir(parents=True)
fig = plt.figure(figsize=(15.5, 9.5), constrained_layout=False)
grid = fig.add_gridspec(2, 3, left=0.055, right=0.965, bottom=0.13, top=0.86, hspace=0.31, wspace=0.27)
classifications = evaluation["classifications"]
tan = np.linspace(0, 2 * np.pi, 28)
pol = np.linspace(0, np.pi, 16)

for column, case in enumerate(cases):
    ax = fig.add_subplot(grid[0, column], projection="3d")
    initial = np.asarray(case["initial_node_positions_m"]) * 1e3
    terminal = np.asarray(case["terminal_node_positions_m"]) * 1e3
    radius_mm = 0.5 * case["sand_diameter_m"] * 1e3
    for centre_m in case["sphere_centres_m"]:
        centre = np.asarray(centre_m) * 1e3
        x = centre[0] + radius_mm * np.outer(np.cos(tan), np.sin(pol))
        y = centre[1] + radius_mm * np.outer(np.sin(tan), np.sin(pol))
        z = centre[2] + radius_mm * np.outer(np.ones_like(tan), np.cos(pol))
        ax.plot_surface(x, y, z, color="#c9b787", alpha=0.35, linewidth=0, shade=True)
    ax.plot(initial[:, 0], initial[:, 1], initial[:, 2], "--", color="#707070", lw=1.5, label="initial")
    ax.plot(terminal[:, 0], terminal[:, 1], terminal[:, 2], "-", color="#c9232a", lw=4.2, label="terminal")
    ax.scatter(terminal[:, 0], terminal[:, 1], terminal[:, 2], s=7, color="#8f1017")
    ax.set_xlabel("x (mm)", labelpad=4); ax.set_ylabel("y (mm)", labelpad=4); ax.set_zlabel("z (mm)", labelpad=4)
    all_x = np.concatenate((initial[:, 0], terminal[:, 0], np.array([-radius_mm, radius_mm])))
    centres_mm = np.asarray(case["sphere_centres_m"]) * 1e3
    all_y = np.concatenate((initial[:, 1], terminal[:, 1], centres_mm[:, 1] - radius_mm, centres_mm[:, 1] + radius_mm))
    all_z = np.concatenate((initial[:, 2], terminal[:, 2], centres_mm[:, 2] - radius_mm, centres_mm[:, 2] + radius_mm))
    spans = [max(np.ptp(values), 1e-4) for values in (all_x, all_y, all_z)]
    ax.set_box_aspect(spans)
    ax.view_init(elev=19, azim=-62)
    ratio = case["throat_to_fibre_diameter_ratio"]
    ax.set_title(f"throat / fibre = {ratio:.3f}\n{classifications[case['case_id']].replace('_', ' ')}", fontsize=11, fontweight="bold")
    if column == 0:
        ax.legend(loc="upper left", fontsize=8, frameon=False)

colors = ["#1f77b4", "#e68a00", "#2a8f4e"]
labels = [f"dₜ/dᶠ={case['throat_to_fibre_diameter_ratio']:.3f}" for case in cases]

advance_ax = fig.add_subplot(grid[1, 0])
passage_ax = fig.add_subplot(grid[1, 1])
contact_ax = fig.add_subplot(grid[1, 2])
for color, label, case in zip(colors, labels, cases):
    rows = histories[case["case_id"]]
    time_ms = np.asarray([float(row["time_s"]) for row in rows]) * 1e3
    advance_um = np.asarray([float(row["leading_node_advance_m"]) for row in rows]) * 1e6
    beyond = np.asarray([int(row["nodes_beyond_throat"]) for row in rows])
    contacts = np.asarray([int(row["sand_fibre_contact_count"]) for row in rows])
    advance_ax.plot(time_ms, advance_um, color=color, lw=2.1, label=label)
    passage_ax.step(time_ms, beyond, where="post", color=color, lw=2.1, label=label)
    contact_ax.step(time_ms, contacts, where="post", color=color, lw=2.1, label=label)
advance_ax.axhline(config["gates"]["maximum_blocked_leading_advance_m"] * 1e6, color="#777777", ls=":", lw=1.2, label="blocked advance gate")
advance_ax.set(xlabel="time (ms)", ylabel="leading-node advance (µm)", title="Axial pull-through response")
passage_ax.axhline(config["gates"]["minimum_passable_nodes_beyond_throat"], color="#777777", ls=":", lw=1.2, label="passage gate")
passage_ax.set(xlabel="time (ms)", ylabel="centreline nodes at x > 0", title="Passage through throat plane")
contact_ax.set(xlabel="time (ms)", ylabel="sand–fibre contacts", title="Contact history and applied pull")
force_ax = contact_ax.twinx()
all_times = np.linspace(0, config["loading"]["total_duration_s"] * 1e3, 200)
force = config["loading"]["axial_pull_force_n"] * np.minimum(1.0, all_times / (config["loading"]["force_ramp_duration_s"] * 1e3)) * 1e6
force_ax.plot(all_times, force, color="#252525", lw=1.5, ls="--", label="prescribed pull")
force_ax.set_ylabel("prescribed pull force (µN)")
for ax in (advance_ax, passage_ax, contact_ax):
    ax.grid(alpha=0.22)
    ax.legend(loc="best", fontsize=8, frameon=False)
force_ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.78), fontsize=8, frameon=False)

fig.suptitle("Stage26u — Flexible microplastic fibre crossing an ideal three-grain throat", fontsize=17, fontweight="bold", y=0.965)
fig.text(0.5, 0.915,
         "37-node fibre; three fixed mutually tangent spheres; frictionless, gravity-free mechanism screen. Geometry shown at actual scale; no displacement magnification.",
         ha="center", va="center", fontsize=10)
fig.text(0.055, 0.055,
         "Claim boundary: deterministic throat mechanism only. Not a measured Leighton Buzzard Sand pore-size distribution, polymer/contact calibration, 216-grain mixture, flow, or permeability prediction. Dashed force is prescribed load, not contact reaction.",
         ha="left", va="center", fontsize=9, color="#333333")

image_path = OUT / "stage26u_three_grain_throat.png"
fig.savefig(image_path, dpi=210, facecolor="white")
plt.close(fig)
manifest = {
    "schema": "lbs.stage26u-three-grain-throat-render.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True,
    "image": {"path": str(image_path), "sha256": sha(image_path)},
    "renderer": {"path": str(SCRIPT), "sha256": sha(SCRIPT)},
    "source_bindings": {
        "evaluation": {"path": str(EVAL), "sha256": sha(EVAL)},
        "checkpoint": {"path": str(CHECKPOINT), "sha256": sha(CHECKPOINT)},
        "result": {"path": str(RUN / "result.json"), "sha256": sha(RUN / "result.json")},
        "config": {"path": str(DESIGN), "sha256": sha(DESIGN)},
    },
    "classifications": classifications,
    "claim_boundary": evaluation["claim_boundary"],
}
manifest_path = OUT / "render_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"image": str(image_path), "image_sha256": sha(image_path),
                  "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path)}, indent=2))
