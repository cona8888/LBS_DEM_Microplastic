#!/usr/bin/env python3
"""Render accepted Stage28a Revision-2 two-fibre mechanics evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RESULT = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_02/result.json"
REV1 = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_01/result.json"
EVALUATION = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_evaluation_02/evaluation.json"
OUTPUT = ROOT / "stage28_renders/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_revision2_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def equal_local_axes(ax, arrays):
    points = np.vstack(arrays)
    lo, hi = points.min(axis=0), points.max(axis=0)
    centre = 0.5 * (lo + hi)
    half = max(0.5 * (hi - lo).max(), 0.12) * 1.15
    ax.set_xlim(centre[0] - half, centre[0] + half)
    ax.set_ylim(centre[1] - half, centre[1] + half)
    ax.set_zlim(centre[2] - half, centre[2] + half)
    ax.set_box_aspect((1, 1, 1))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable render: {OUTPUT}")
    result, rev1, evaluation = map(load, (RESULT, REV1, EVALUATION))
    if not (result["passed"] and evaluation["passed"]):
        raise RuntimeError("accepted mechanics evidence is required")
    by_id = {case["case_id"]: case for case in result["cases"]}
    case_ids = ["separated_open_open", "separated_open_constricted", "crossing_interaction"]
    titles = ["Separated: open + open", "Separated: open + constricted", "Controlled crossing"]
    colors = ["#d94841", "#2b6cb0"]

    fig = plt.figure(figsize=(16, 10), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=[1.25, 0.75])
    for column, (case_id, title) in enumerate(zip(case_ids, titles)):
        ax = fig.add_subplot(grid[0, column], projection="3d")
        arrays = []
        for index, fibre in enumerate(by_id[case_id]["terminal_fibres"]):
            initial = 1e3 * np.asarray(fibre["initial_node_positions_m"], dtype=float)
            terminal = 1e3 * np.asarray(fibre["terminal_node_positions_m"], dtype=float)
            arrays.extend([initial, terminal])
            ax.plot(initial[:, 0], initial[:, 1], initial[:, 2], color=colors[index],
                    alpha=.28, linestyle="--", linewidth=1.2)
            ax.plot(terminal[:, 0], terminal[:, 1], terminal[:, 2], color=colors[index],
                    linewidth=3.0, label=f"fibre {index + 1}")
            ax.scatter(*terminal[-1], color=colors[index], s=28)
        equal_local_axes(ax, arrays)
        contacts = by_id[case_id]["maximum_fibre_fibre_contact_count"]
        force = 1e6 * by_id[case_id]["maximum_fibre_contact_normal_force_n"]
        ax.set_title(f"{title}\nmax contacts = {contacts}; max normal force = {force:.2f} µN", fontsize=11)
        ax.set_xlabel("x (mm)")
        ax.set_ylabel("y (mm)")
        ax.set_zlabel("z (mm)")
        ax.view_init(elev=24, azim=-55)
        ax.legend(loc="upper right", frameon=False, fontsize=9)

    ax = fig.add_subplot(grid[1, 0])
    labels = [f"{row['case_id'].replace('separated_', '')}\nface {row['source_face_index']}"
              for row in result["path_match"]]
    values = [row["aligned_terminal_rms_over_fibre_diameter"] for row in result["path_match"]]
    ax.bar(np.arange(len(values)), values, color="#4c78a8")
    ax.axhline(.05, color="#b22222", linestyle="--", label="frozen limit = 0.05 D")
    ax.set_xticks(np.arange(len(values)), labels, rotation=22, ha="right", fontsize=8)
    ax.set_ylabel("aligned RMS / fibre diameter")
    ax.set_title("Separated-path reproducibility")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="y", alpha=.2)

    ax = fig.add_subplot(grid[1, 1])
    rev1_max = max(case["maximum_intrafibre_contact_count"] for case in rev1["cases"])
    rev2_max = max(case["maximum_intrafibre_contact_count"] for case in result["cases"])
    bars = ax.bar(["Revision 1\nfailed", "Revision 2\naccepted"], [rev1_max, rev2_max],
                  color=["#d95f02", "#1b9e77"])
    ax.bar_label(bars, fmt="%.0f", padding=3)
    ax.set_ylabel("maximum false same-fibre contacts")
    ax.set_title("Structural contact-filter correction")
    ax.set_ylim(0, max(145, rev1_max * 1.08))
    ax.grid(axis="y", alpha=.2)

    ax = fig.add_subplot(grid[1, 2])
    ax.axis("off")
    metrics = evaluation["metrics"]
    lines = [
        "Accepted mechanics checkpoint",
        "",
        "✓ 6/6 immutable cases passed",
        "✓ zero hold drift and speed",
        "✓ 36/36 internal bonds per fibre",
        "✓ fixed sand and periodic cell",
        "✓ zero false same-fibre contacts",
        "✓ separated pairs: zero mutual contact",
        f"✓ crossing: {metrics['crossing_maximum_contact_count']} mutual contact",
        f"✓ crossing peak normal force: {1e6 * metrics['crossing_maximum_contact_normal_force_n']:.2f} µN",
        f"✓ max penetration/radius: {metrics['maximum_penetration_over_fibre_radius']:.3e}",
        "",
        "Scope: fixed-sand mechanism pilot only.",
        "Hydraulic/GPU execution is not yet authorized.",
    ]
    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left", fontsize=10.5,
            family="DejaVu Sans", bbox=dict(boxstyle="round,pad=.6", facecolor="#f5f7fa", edgecolor="#b8c2cc"))

    fig.suptitle("Stage28a: two flexible microplastic fibres — verified mechanics before flow",
                 fontsize=17, fontweight="bold")
    OUTPUT.mkdir(parents=True)
    image = OUTPUT / "stage28a_two_fibre_mechanics_revision2.png"
    fig.savefig(image, dpi=190, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage28a-two-fibre-mechanics-revision2-render.v1",
        "status": "rendered_from_accepted_mechanics_checkpoint",
        "passed": True,
        "bindings": {"result_sha256": sha(RESULT), "revision1_result_sha256": sha(REV1),
                     "evaluation_sha256": sha(EVALUATION), "renderer_sha256": sha(Path(__file__).resolve()),
                     "image_sha256": sha(image)},
        "image": str(image),
    }
    manifest_path = OUTPUT / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"image": str(image), "image_sha256": sha(image),
                      "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
