"""Build the immutable candidate05 Stage26e development-capture configuration."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_staging/stage26d_adaptive_development_candidate01_execution_v1.json"
OUTPUT = ROOT / "stage26_staging/stage26e_candidate05_development_capture_execution_v2.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(path):
    return str(path).replace("\\", "/"), digest(path)


def main():
    assert not OUTPUT.exists(), "refusing to overwrite frozen capture config"
    base = json.loads(BASE.read_text(encoding="utf-8"))
    placement = ROOT / "stage26_placements/stage26e_qualified_state_capture_20260816/allocation_01/revision3_candidate05_development_capture.json"
    runner = ROOT / "stage26_staging/run_stage26e_qualified_state_capture_v1.py"
    capture_common = ROOT / "stage26_staging/stage26e_capture_common_v1.py"
    design_checkpoint = ROOT / "stage26_checkpoints/stage26e_qualified_state_capture_20260816/design_checkpoint_01/checkpoint_manifest.json"
    final_stage26d = ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/final_confirmation_checkpoint_01/checkpoint_manifest.json"
    allocation = ROOT / "stage26_placements/stage26e_qualified_state_capture_20260816/allocation_01/manifest.json"
    cfg = {
        "schema": "lbs.stage26e-development-qualified-state-capture-execution.v2",
        "status": "authorized_stage26e_fixed_capture",
        "claim_boundary": "Candidate05 development of fixed-fibre event capture and state publication only; no release, promoted state, permeability, flow, deformation, migration, or production result.",
        "authority": {
            "capture_yade_execution_authorized": True,
            "reload_verification_execution_authorized": False,
            "candidate07_heldout_execution_authorized": False,
            "candidate08_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "adaptive_equilibration": base["adaptive_equilibration"],
        "capture_protocol": {
            "all_fibres_fixed": True,
            "free_release": False,
            "steps_per_block": 500,
            "maximum_strain_rate_s_inv": 0.02,
            "save_on_first_qualifying_window_only": True,
        },
        "continuous_engagement_gates": base["continuous_engagement_gates"],
        "equilibrium_window_gates": base["equilibrium_window_gates"],
        "candidate_generation": base["candidate_generation"],
        "frozen_physics": base["frozen_physics"],
        "network_export": base["network_export"],
        "reload_equivalence_tolerances": {
            "absolute_scalar": 1e-12,
            "relative_scalar": 1e-10,
            "cell_dimension_absolute_m": 1e-12,
            "integer_and_contact_sets_exact": True,
        },
        "sources": dict(base["sources"]),
        "trials": [{
            "trial_id": "revision3_candidate05_development_capture",
            "candidate_index": 5,
            "fibre_count": 2,
            "minimum_anchor_degree": 3,
            "record_type": "capture",
            "stage26e_role": "development_capture",
            "placement": str(placement).replace("\\", "/"),
            "placement_sha256": digest(placement),
        }],
    }
    for key in list(cfg["sources"]):
        if key.startswith("stage26d_evaluator") or key.startswith("temporal_") or key in (
            "normalized_manifest", "visual_checkpoint", "stage26d_design_checkpoint",
        ):
            cfg["sources"].pop(key)
    additions = {
        "capture_runner": runner,
        "capture_common": capture_common,
        "stage26e_design_checkpoint": design_checkpoint,
        "stage26d_final_confirmation": final_stage26d,
        "stage26e_allocation_manifest": allocation,
    }
    for key, path in additions.items():
        cfg["sources"][key], cfg["sources"][key + "_sha256"] = source(path)
    OUTPUT.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"config": str(OUTPUT), "sha256": digest(OUTPUT)}, sort_keys=True))


if __name__ == "__main__":
    main()
