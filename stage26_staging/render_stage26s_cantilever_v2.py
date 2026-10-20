#!/usr/bin/env python3
"""Render the independently accepted Stage26s cantilever verification."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage26_runs" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_03"
EVAL = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_evaluation_03" / "evaluation.json"
RESULT = RUN / "result.json"
OUT = ROOT / "stage26_renders" / "stage26s_flexible_fibre_cantilever_20260819" / "render_02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite {OUT}")
evaluation = json.loads(EVAL.read_text(encoding="utf-8"))
result = json.loads(RESULT.read_text(encoding="utf-8"))
if not evaluation.get("passed") or evaluation["source_hashes"]["result"] != sha(RESULT):
    raise RuntimeError("render source is not the accepted result")

plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10})
fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), constrained_layout=True)
colors = {19: "#4c78a8", 37: "#f58518", 73: "#54a24b"}
styles = {19: ("-", "o"), 37: ("--", "s"), 73: (":", "^")}

for mesh in result["meshes"]:
    path = RUN / mesh["history"]["path"]
    if sha(path) != mesh["history"]["sha256"]:
        raise RuntimeError(f"history hash mismatch for N={mesh['node_count']}")
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    time_ms = np.array([float(row["time_s"]) for row in rows]) * 1.0e3
    deflection_pct = np.abs(np.array([float(row["tip_displacement_m"]) for row in rows])) / result["inputs"]["length_m"] * 100.0
    linestyle, marker = styles[mesh["node_count"]]
    axes[0].plot(time_ms, deflection_pct, linestyle=linestyle, marker=marker, markersize=3.4,
                 linewidth=1.55, alpha=0.85, color=colors[mesh["node_count"]], label=f"{mesh['node_count']} nodes")

axes[0].axhline(1.0, color="black", linestyle="--", linewidth=1.0, label="Euler–Bernoulli target")
axes[0].set_xlabel("Physical time (ms)")
axes[0].set_ylabel("Tip deflection / fibre length (%)")
axes[0].set_title("Quasi-static load ramp and equilibrium")
axes[0].grid(alpha=0.25)
axes[0].legend(frameon=False, loc="lower right")
axes[0].text(0.03, 0.94, "Mesh curves overlap at this scale", transform=axes[0].transAxes,
             ha="left", va="top", fontsize=9, color="#444444")

nodes = [m["node_count"] for m in result["meshes"]]
errors_pct = [100.0 * m["analytical_relative_error"] for m in result["meshes"]]
axes[1].plot(nodes, errors_pct, marker="o", linewidth=1.8, color="#b279a2")
for n, err in zip(nodes, errors_pct):
    axes[1].annotate(f"{err:.4f}%", (n, err), xytext=(0, 7), textcoords="offset points", ha="center")
axes[1].set_xlabel("Grid nodes along 0.9 mm fibre")
axes[1].set_ylabel("Relative error from analytical deflection (%)")
axes[1].set_title("Mesh convergence to Euler–Bernoulli response")
axes[1].set_xticks(nodes)
axes[1].set_ylim(0, 0.052)
axes[1].grid(alpha=0.25)

fig.suptitle("Stage26s flexible-fibre code verification", fontsize=15, fontweight="bold")
fig.text(
    0.5, -0.015,
    "Standalone nonperiodic YADE beam; E = 53 MPa is a nominal numerical reference only. "
    "No sand-contact, polymer-calibration, periodic-mixture, flow, or permeability claim.",
    ha="center", va="top", fontsize=9, color="#444444",
)
OUT.mkdir(parents=True)
image = OUT / "stage26s_cantilever_verification.png"
fig.savefig(image, dpi=180, bbox_inches="tight")
plt.close(fig)
manifest = {
    "schema": "lbs.stage26s-cantilever-render-manifest.v1",
    "image": {"path": str(image.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(image)},
    "source_hashes": {"evaluation": sha(EVAL), "result": sha(RESULT), "renderer": sha(Path(__file__))},
    "claim_boundary": evaluation["claim_boundary"],
}
manifest_path = OUT / "render_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"image": str(image), "image_sha256": sha(image), "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path)}, indent=2))
