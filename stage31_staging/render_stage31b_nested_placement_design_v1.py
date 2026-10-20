#!/usr/bin/env python3
"""Render the audited Stage31b three-packing, two-block placement design."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN = ROOT / "stage31_designs/stage31b_nested_concentration_replication_20260826/design_01/design_manifest.json"
AUDIT = ROOT / "stage31_evaluations/stage31b_nested_concentration_replication_20260826/design_audit_01/design_audit.json"
OUTPUT = ROOT / "stage31_renders/stage31b_nested_concentration_replication_20260826/design_render_02"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable render: {OUTPUT}")
    design, audit = load(DESIGN), load(AUDIT)
    if audit.get("passed") is not True or audit["source_hashes"]["design"] != digest(DESIGN):
        raise RuntimeError("design audit binding failed")
    colours = ["#0072B2", "#E69F00", "#009E73", "#CC79A7"]
    fig = plt.figure(figsize=(13.2, 15.0), constrained_layout=True)
    for row_index, packing in enumerate(("n216_s1", "n216_s2", "n216_s3")):
        network_binding = design["source_bindings"][packing]["network"]
        network_path = Path(network_binding["path"])
        if digest(network_path) != network_binding["sha256"]:
            raise RuntimeError(f"network hash mismatch: {packing}")
        network = load(network_path)
        centres = np.asarray([item["position_m"] for item in network["particles"]], dtype=float)
        radii = np.asarray([item["radius_m"] for item in network["particles"]], dtype=float)
        lengths = np.asarray([network["cell_hsize_m"][axis][axis] for axis in range(3)], dtype=float)
        for col_index, block in enumerate(("A", "B")):
            axis = fig.add_subplot(3, 2, row_index * 2 + col_index + 1, projection="3d")
            sizes = 9.0 + 65.0 * (radii - radii.min()) / max(float(np.ptp(radii)), 1.0e-12)
            axis.scatter(centres[:, 0] * 1e3, centres[:, 1] * 1e3, centres[:, 2] * 1e3, s=sizes, c="#777777", alpha=0.12, edgecolors="none")
            for index, fibre in enumerate(design["blocks"][packing][block]):
                line = np.asarray([fibre["rear_m"], fibre["tip_m"]]) * 1e3
                axis.plot(line[:, 0], line[:, 1], line[:, 2], color=colours[index], linewidth=5.0, label=f"nested fibre {index + 1}")
                axis.scatter(line[1, 0], line[1, 1], line[1, 2], color=colours[index], s=22)
            axis.set_xlim(0.0, lengths[0] * 1e3)
            axis.set_ylim(0.0, lengths[1] * 1e3)
            axis.set_zlim(0.0, lengths[2] * 1e3)
            # Matplotlib normalizes mutable arrays in place; pass an immutable copy
            # so the second placement block retains the physical cell dimensions.
            axis.set_box_aspect(tuple(float(value) for value in lengths))
            axis.view_init(elev=23, azim=-57)
            axis.set_title(f"{packing} — placement block {block}", fontsize=12, weight="bold")
            axis.set_xlabel("x [mm]")
            axis.set_ylabel("y [mm]")
            axis.set_zlabel("z [mm]")
            if row_index == 0 and col_index == 1:
                axis.legend(loc="upper left", fontsize=8, frameon=True)
    fig.suptitle("Stage31b audited nested concentration design\n3 load-bearing sand packings × 2 placement blocks; prefixes give 1, 2, and 4 fibres", fontsize=16, weight="bold")
    OUTPUT.mkdir(parents=True)
    image = OUTPUT / "stage31b_nested_placement_design.png"
    fig.savefig(image, dpi=180, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage31b-nested-placement-render.v1",
        "passed": True,
        "image": {"path": str(image), "sha256": digest(image)},
        "source_bindings": {"design": {"path": str(DESIGN), "sha256": digest(DESIGN)}, "audit": {"path": str(AUDIT), "sha256": digest(AUDIT)}, "renderer": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())}},
        "claim_boundary": "Visual design evidence only; no mechanics execution, flow, or permeability result.",
    }
    (OUTPUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["image"], sort_keys=True))


if __name__ == "__main__":
    main()
