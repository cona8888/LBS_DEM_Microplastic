"""Corrected-layout immutable render for Stage26b Tier-1 placements."""

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from render_stage26b_tier1_placements_v1 import digest, draw_case, load_json


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_tier1_placement_preflight_v1.json"
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_dry_multifibre_20260814" / "tier1_placement_evaluation_01" / "evaluation.json"
OUTPUT = PROJECT / "stage26_renders" / "stage26b_dry_multifibre_20260814" / "tier1_placement_render_02"
BASE_RENDERER = PROJECT / "stage26_staging" / "render_stage26b_tier1_placements_v1.py"


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable corrected Tier-1 placement render already exists")
    cfg = load_json(CONFIG)
    evaluation = load_json(EVALUATION)
    if not evaluation.get("passed") or evaluation["config_sha256"] != digest(CONFIG):
        raise RuntimeError("evaluation/config binding failed")
    stage26a = load_json(Path(cfg["sources"]["stage26a_design_config"]))
    result_path = Path(stage26a["source"]["stage25_selected_result"])
    if digest(result_path) != stage26a["source"]["stage25_selected_result_sha256"]:
        raise RuntimeError("Stage25 result binding failed")
    particles = load_json(result_path)["particles"]
    placements = []
    for case_eval in evaluation["cases"]:
        path = Path(case_eval["placement_path"])
        if digest(path) != case_eval["placement_sha256"]:
            raise RuntimeError("placement/evaluation binding failed")
        placements.append(load_json(path))

    fig = plt.figure(figsize=(16, 14))
    axes = [fig.add_subplot(2, 2, index + 1, projection="3d") for index in range(4)]
    for column, placement in enumerate(placements):
        draw_case(axes[column], placement, particles, closeup=False)
        axes[column].set_title(f"{placement['fibre_count']} fibres: full periodic cell\n{placement['case']['dry_mass_percent']:.5f} wt%", pad=12)
        draw_case(axes[column + 2], placement, particles, closeup=True)
        axes[column + 2].set_title(f"{placement['fibre_count']} fibres: fibre-anchor detail\nblue = declared anchor grains", pad=12)
    fig.subplots_adjust(left=0.035, right=0.975, bottom=0.105, top=0.895, hspace=0.28, wspace=0.08)
    fig.suptitle("Stage26b Tier-1 geometry preflight: actual F37 coordinates and radii",
                 fontsize=17, weight="bold", y=0.965)
    fig.text(0.5, 0.035,
             "Geometry-only dry-mechanics preflight. Each panel uses equal physical data-unit scaling; cropped panels change the view, not the geometry.\n"
             "No DEM relaxation, physical mixing, permeability, migration, polymer calibration or coupled-flow claim.",
             ha="center", va="center", fontsize=10)
    OUTPUT.mkdir(parents=True)
    image_path = OUTPUT / "stage26b_tier1_multifibre_placements.png"
    fig.savefig(image_path, dpi=210, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26b-tier1-placement-render.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "supersedes_for_presentation": "tier1_placement_render_01",
        "source_hashes": {
            "config": digest(CONFIG), "evaluation": digest(EVALUATION),
            "placements": {case["case_id"]: case["placement_sha256"] for case in evaluation["cases"]},
            "stage25_result": digest(result_path), "base_renderer": digest(BASE_RENDERER),
            "renderer": digest(Path(__file__)),
        },
        "image_path": str(image_path),
        "image_sha256": digest(image_path),
        "visual_semantics": "Actual physical coordinates and radii; equal data-unit scaling inside each panel; different crop windows do not magnify objects relative to their panel.",
        "claim_boundary": cfg["claim_boundary"],
        "authority": cfg["authority"],
    }
    with (OUTPUT / "render_manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "image_sha256": digest(image_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
