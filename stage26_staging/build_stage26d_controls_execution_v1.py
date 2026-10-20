"""Build exact Stage26d 300-block control execution config."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_staging/stage26c_fixed_prefilter_controls_execution_v2.json"
OUTPUT = ROOT / "stage26_staging/stage26d_adaptive_controls_execution_v1.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cfg = json.loads(BASE.read_text())
    cfg["schema"] = "lbs.stage26d-adaptive-controls-execution.v1"
    cfg["claim_boundary"] = "Fixed-fibre 300-block control qualification for the Stage26d adaptive evaluator only; no release, promoted state, or flow."
    additions = {
        "stage26d_design_checkpoint": ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/design_checkpoint_02/checkpoint_manifest.json",
        "stage26d_adaptive_common": ROOT / "stage26_staging/stage26d_adaptive_common_v1.py",
        "stage26d_evaluator_core": ROOT / "stage26_staging/evaluate_stage26d_adaptive_prefilter_v1.py",
        "stage26d_evaluator_adapter": ROOT / "stage26_staging/evaluate_stage26d_adaptive_prefilter_v2.py",
    }
    for key, path in additions.items():
        cfg["sources"][key] = path.as_posix()
        cfg["sources"][key + "_sha256"] = digest(path)
    cfg["prefilter"]["blocks"] = 300
    cfg["adaptive_equilibration"] = {
        "minimum_blocks_before_equilibrium_window": 60,
        "maximum_blocks": 300,
        "required_consecutive_passing_blocks": 10,
    }
    cfg["continuous_engagement_gates"] = {
        "minimum_distinct_sand_contacts_per_fibre_at_every_block": 1,
        "minimum_declared_anchor_contacts_per_fibre_at_every_block": 1,
        "maximum_isolated_fibre_count_at_every_block": 0,
    }
    cfg["equilibrium_window_gates"] = dict(cfg["sand_health_gates_at_terminal_block"])
    cfg["equilibrium_window_gates"].update({
        "minimum_distinct_sand_contacts_per_fibre": 2,
        "minimum_declared_anchor_contacts_per_fibre": 2,
        "maximum_fibre_fibre_real_interaction_count": 0,
        "maximum_intraclump_real_interaction_count": 0,
    })
    cfg["trials"][0]["stage26d_role"] = "positive_control"
    cfg["trials"][1]["stage26d_role"] = "negative_control"
    OUTPUT.open("x").write(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
    print(digest(OUTPUT))


if __name__ == "__main__":
    main()
