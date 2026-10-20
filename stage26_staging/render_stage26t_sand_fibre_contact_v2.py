#!/usr/bin/env python3
"""Render the accepted Stage26t contact and beam verification."""

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage26_runs" / "stage26t_sand_fibre_contact_20260820" / "contact_01"
RESULT = RUN / "result.json"
EVAL = ROOT / "stage26_evaluations" / "stage26t_sand_fibre_contact_20260820" / "contact_evaluation_01" / "evaluation.json"
CONFIG = ROOT / "stage26_designs" / "stage26t_sand_fibre_contact_20260820" / "contact_design_01" / "config.json"
OUT = ROOT / "stage26_renders" / "stage26t_sand_fibre_contact_20260820" / "render_02"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
if OUT.exists(): raise RuntimeError(f"refusing to overwrite {OUT}")
result = json.loads(RESULT.read_text(encoding="utf-8"))
evaluation = json.loads(EVAL.read_text(encoding="utf-8"))
config = json.loads(CONFIG.read_text(encoding="utf-8"))
if not evaluation.get("passed") or evaluation["source_hashes"]["result"] != sha(RESULT):
    raise RuntimeError("render source is not accepted")

styles = {0.20: ("#4c78a8", "-"), 0.10: ("#f58518", "--"), 0.05: ("#54a24b", ":")}
fig, axes = plt.subplots(1, 3, figsize=(16.2, 5.2), constrained_layout=True)
histories = {}
for level in result["levels"]:
    factor = float(level["time_step_safety_factor"])
    history_path = RUN / level["history"]["path"]
    if sha(history_path) != level["history"]["sha256"]: raise RuntimeError("history hash mismatch")
    with history_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    histories[factor] = rows
    t = np.array([float(row["time_s"]) for row in rows]) * 1e3
    reaction = np.array([float(row["sphere_reaction_y_n"]) for row in rows]) * 1e6
    color, linestyle = styles[factor]
    axes[0].plot(t, reaction, color=color, linestyle=linestyle, linewidth=1.7, label=f"safety {factor:.2f}")
axes[0].axvspan(0.75, 1.50, color="#eeeeee", zorder=-2, label="peak hold")
axes[0].set(xlabel="Physical time (ms)", ylabel="Upward sphere reaction (µN)", title="Load–hold–unload contact response")
axes[0].grid(alpha=0.25); axes[0].legend(frameon=False, fontsize=9)

for factor, rows in histories.items():
    load_rows = [row for row in rows if row["phase"] in ("load", "peak_hold")]
    delta = np.array([float(row["midpoint_deflection_m"]) for row in load_rows]) * 1e6
    reaction = np.array([float(row["sphere_reaction_y_n"]) for row in load_rows]) * 1e6
    color, linestyle = styles[factor]
    axes[1].plot(delta, reaction, color=color, linestyle=linestyle, linewidth=1.7, label=f"safety {factor:.2f}")
fine = result["levels"][-1]
delta_line = np.linspace(0, fine["mean_peak_midpoint_deflection_m"] * 1e6 * 1.04, 100)
theory = result["beam"]["fixed_fixed_midpoint_stiffness_n_per_m"] * delta_line
axes[1].plot(delta_line, theory, "k-.", linewidth=1.2, label="fixed–fixed beam theory")
axes[1].set(xlabel="Measured midpoint deflection (µm)", ylabel="Sphere reaction (µN)", title="Contact load transmitted into fibre bending")
axes[1].grid(alpha=0.25); axes[1].legend(frameon=False, fontsize=9)
axes[1].text(0.04, 0.94, f"Fine-grid theory error = {100*fine['beam_theory_relative_error']:.3f}%",
             transform=axes[1].transAxes, va="top", fontsize=9)

peak = np.array(fine["peak_snapshot_node_positions_m"]) * 1e3
axes[2].plot(peak[:, 0], peak[:, 1], color="#d62728", linewidth=5.0, solid_capstyle="round", label="flexible fibre centreline")
rs_mm = 0.5 * config["sand"]["diameter_m"] * 1e3
initial_y = (0.5 * config["sand"]["diameter_m"] + 0.5 * config["fibre"]["diameter_m"] + config["loading"]["initial_clearance_m"]) * 1e3
sphere_y = initial_y - config["loading"]["peak_sphere_travel_m"] * 1e3
axes[2].add_patch(Circle((0.5 * config["fibre"]["length_m"] * 1e3, sphere_y), rs_mm,
                         facecolor="#c6b98b", edgecolor="#6f6546", linewidth=1.2, alpha=0.85, label="LBS D50 sphere"))
axes[2].scatter([0, config["fibre"]["length_m"] * 1e3], [0, 0], marker="s", color="black", s=24, label="fixed ends")
axes[2].set_xlim(-0.02, 0.92); axes[2].set_ylim(-0.03, 0.15); axes[2].set_aspect("equal", adjustable="box")
axes[2].set(xlabel="x (mm)", ylabel="y (mm)", title="Peak contact geometry (actual scale)")
axes[2].grid(alpha=0.20); axes[2].legend(frameon=False, fontsize=8, loc="upper right")
axes[2].text(0.98, 0.04, "No displacement magnification", transform=axes[2].transAxes, ha="right", fontsize=8)

fig.suptitle("Stage26t sphere–flexible-fibre contact verification", fontsize=15, fontweight="bold")
fig.text(0.5, -0.015, "Frictionless nonperiodic single-contact verification. Nominal E = 53 MPa is not polymer calibration; no multigrain caging, mixture, flow, or permeability claim.",
         ha="center", va="top", fontsize=9, color="#444444")
OUT.mkdir(parents=True)
image = OUT / "stage26t_contact_verification.png"
fig.savefig(image, dpi=180, bbox_inches="tight"); plt.close(fig)
manifest = {"schema": "lbs.stage26t-contact-render-manifest.v1",
            "image": {"path": str(image.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(image)},
            "source_hashes": {"evaluation": sha(EVAL), "result": sha(RESULT), "config": sha(CONFIG), "renderer": sha(Path(__file__))},
            "claim_boundary": evaluation["claim_boundary"]}
manifest_path = OUT / "render_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"image": str(image), "image_sha256": sha(image), "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path)}, indent=2))
