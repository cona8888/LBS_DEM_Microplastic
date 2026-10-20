"""Build the immutable candidate07 Stage26e held-out capture configuration."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_staging/stage26e_candidate05_development_capture_execution_v2.json"
OUTPUT = ROOT / "stage26_staging/stage26e_candidate07_heldout_capture_execution_v1.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def add_source(sources, key, path):
    sources[key] = str(path).replace("\\", "/")
    sources[key + "_sha256"] = digest(path)


def main():
    assert not OUTPUT.exists(), "refusing to overwrite held-out config"
    cfg = json.loads(BASE.read_text(encoding="utf-8"))
    placement = ROOT / "stage26_placements/stage26e_qualified_state_capture_20260816/allocation_01/revision3_candidate07_heldout_capture.json"
    runner = ROOT / "stage26_staging/run_stage26e_qualified_state_capture_v2.py"
    derivation = ROOT / "stage26_staging/build_stage26e_heldout_runner_v2.py"
    development = ROOT / "stage26_checkpoints/stage26e_qualified_state_capture_20260816/development_outcome_checkpoint_01/checkpoint_manifest.json"
    verifier = ROOT / "stage26_staging/verify_stage26e_captured_state_reload_v1.py"
    erratum = ROOT / "stage26_staging/stage26e_reload_semantics_erratum_v1.json"
    cfg["schema"] = "lbs.stage26e-heldout-qualified-state-capture-execution.v1"
    cfg["claim_boundary"] = "One-shot candidate07 held-out confirmation of the frozen fixed-fibre capture and structural-reload method; no rehydration, release, state promotion, flow, deformation, migration, or production result."
    cfg["authority"] = {
        "capture_yade_execution_authorized": True,
        "reload_verification_execution_authorized": False,
        "candidate07_heldout_execution_authorized": True,
        "candidate08_execution_authorized": False,
        "two_fibre_free_release_authorized": False,
        "flow_execution_authorized": False,
        "deformation_authorized": False,
        "production_parametric_study_authorized": False,
    }
    cfg["trials"] = [{
        "trial_id": "revision3_candidate07_heldout_capture",
        "candidate_index": 7,
        "fibre_count": 2,
        "minimum_anchor_degree": 3,
        "record_type": "capture",
        "stage26e_role": "heldout_capture",
        "placement": str(placement).replace("\\", "/"),
        "placement_sha256": digest(placement),
    }]
    sources = cfg["sources"]
    add_source(sources, "capture_runner", runner)
    add_source(sources, "heldout_runner_derivation", derivation)
    add_source(sources, "stage26e_development_outcome", development)
    add_source(sources, "reload_verifier", verifier)
    add_source(sources, "reload_semantics_erratum", erratum)
    OUTPUT.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"config": str(OUTPUT), "sha256": digest(OUTPUT)}, sort_keys=True))


if __name__ == "__main__":
    main()
