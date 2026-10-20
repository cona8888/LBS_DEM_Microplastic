"""Normalize and freeze candidate04 as the pre-execution Stage26d holdout."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage26_placements/stage26b_revision3_joint_placement_20260816/candidate_generation_01/stage26b_f002_revision3_candidate_04/placement.json"
OUTPUT = ROOT / "stage26_placements/stage26d_adaptive_equilibration_20260816/holdout_01"
EXPECTED = "4c84834a319198561868d8a17ceecfdd6a087bc8bc26cc38a2d749179da47b90"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert digest(SOURCE) == EXPECTED
    source = json.loads(SOURCE.read_text())
    assert source["passed"] is True and source["candidate"]["candidate_index"] == 4
    assert OUTPUT.exists() is False
    OUTPUT.mkdir(parents=True)
    normalized = {
        "schema": "lbs.stage26d-heldout-normalized-placement.v1",
        "record_type": "heldout_confirmation",
        "passed": True,
        "candidate": source["candidate"],
        "selection_rule": "next-lowest-index passing Revision-3 geometry after development candidate01",
        "fibre_count": 2,
        "members_per_fibre": 37,
        "member_radius_m": 0.00005,
        "fibres": source["fibres"],
        "maximum_initial_force_residual_relative": max(row["initial_normal_force_residual_relative"] for row in source["fibres"]),
        "maximum_initial_moment_residual_relative": max(row["initial_normal_moment_residual_relative"] for row in source["fibres"]),
        "source_placement_sha256": EXPECTED,
    }
    placement = OUTPUT / "revision3_candidate04_holdout.json"
    placement.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    manifest = {
        "schema": "lbs.stage26d-heldout-normalization-manifest.v1",
        "passed": True,
        "selection_frozen_before_stage26d_execution": True,
        "source_sha256": EXPECTED,
        "placement_sha256": digest(placement),
        "authority": {"heldout_config_preparation_authorized": True, "heldout_yade_execution_authorized": False},
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
