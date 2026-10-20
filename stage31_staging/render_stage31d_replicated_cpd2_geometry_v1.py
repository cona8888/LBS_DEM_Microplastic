#!/usr/bin/env python3
"""Render accepted Stage31d terminal four-fibre CPD2 geometries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/resolved_config.json"
AUDIT = ROOT / "stage31_evaluations/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_audit_03/geometry_audit.json"
OUTPUT = ROOT / "stage31_renders/stage31d_replicated_nested_cpd2_geometry_20260826/terminal_geometry_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable render: {OUTPUT}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if not audit.get("passed") or audit["bindings"]["config_sha256"] != sha(CONFIG):
        raise RuntimeError("geometry audit binding failed")
    rows = {row["case_id"]: row for row in config["geometry"]["cases"]}
    colours = ["#0072B2", "#E69F00", "#009E73", "#CC79A7"]
    figure = plt.figure(figsize=(13.2, 15.0), constrained_layout=True)
    for row_index, packing in enumerate(("n216_s1", "n216_s2", "n216_s3")):
        for col_index, block in enumerate(("A", "B")):
            case_id = f"s31b_{packing}_{block}_f004_open"
            geometry = Path(config["geometry"]["artifacts"][case_id]["geometry"])
            if sha(geometry) != config["geometry"]["artifacts"][case_id]["geometry_sha256"]:
                raise RuntimeError("geometry hash mismatch: " + case_id)
            with np.load(geometry) as data:
                centres = np.asarray(data["sand_centres_m"], dtype=float)
                radii = np.asarray(data["sand_radii_m"], dtype=float)
                centrelines = np.asarray(data["fibre_centrelines_m"], dtype=float)
                length = float(data["cell_length_m"][0])
            axis = figure.add_subplot(3, 2, row_index * 2 + col_index + 1, projection="3d")
            sizes = 8.0 + 55.0 * (radii - radii.min()) / max(float(np.ptp(radii)), 1.0e-12)
            axis.scatter(centres[:, 0] * 1e3, centres[:, 1] * 1e3, centres[:, 2] * 1e3, s=sizes, c="#777777", alpha=0.10, edgecolors="none")
            for index, points in enumerate(centrelines):
                line = points * 1e3
                axis.plot(line[:, 0], line[:, 1], line[:, 2], color=colours[index], linewidth=4.2, label=f"nested rank {index + 1}")
                axis.scatter(line[-1, 0], line[-1, 1], line[-1, 2], color=colours[index], s=18)
            limit = length * 1e3
            axis.set_xlim(0.0, limit)
            axis.set_ylim(0.0, limit)
            axis.set_zlim(0.0, limit)
            axis.set_box_aspect((1.0, 1.0, 1.0))
            axis.view_init(elev=23, azim=-57)
            row = rows[case_id]
            axis.set_title(f"{packing} — block {block}\n4-fibre porosity {row['voxel_porosity']:.5f}", fontsize=11, weight="bold")
            axis.set_xlabel("x [mm]")
            axis.set_ylabel("y [mm]")
            axis.set_zlabel("z [mm]")
            if row_index == 0 and col_index == 1:
                axis.legend(loc="upper left", fontsize=8)
    figure.suptitle("Stage31d terminal mechanics-qualified CPD2 geometry\n3 independent sand packings × 2 placement blocks; coloured paths are the four nested ranks", fontsize=15, weight="bold")
    OUTPUT.mkdir(parents=True)
    image = OUTPUT / "stage31d_terminal_cpd2_geometry.png"
    figure.savefig(image, dpi=180, facecolor="white")
    plt.close(figure)
    manifest = {
        "schema": "lbs.stage31d-terminal-cpd2-render.v1",
        "passed": True,
        "image": {"path": str(image), "sha256": sha(image)},
        "sources": {"config": {"path": str(CONFIG), "sha256": sha(CONFIG)}, "audit": {"path": str(AUDIT), "sha256": sha(AUDIT)}, "renderer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())}},
        "authority": "Visual evidence only; GPU flow remains unauthorized.",
    }
    (OUTPUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["image"], sort_keys=True))


if __name__ == "__main__":
    main()
