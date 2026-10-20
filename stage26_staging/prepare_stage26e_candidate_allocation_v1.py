"""Normalize and freeze the unused Revision-3 geometries for Stage26e."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE_ROOT = ROOT / "stage26_placements/stage26b_revision3_joint_placement_20260816/candidate_generation_01"
OUTPUT = ROOT / "stage26_placements/stage26e_qualified_state_capture_20260816/allocation_01"
EXPECTED = {
    5: "cb51de36eedbd2a433395419545ba91af4fe368e814f1ced702245b00ca05aeb",
    7: "e17ce8b08218c949776fc1fb867d41a9d0c74ea7eaf23009c3026fac38b4ec00",
    8: "37bdfc90e5223d1449748cfd1f844215bcfbd232e06785432129200add2a0234",
}
ROLES = {5: "development_capture", 7: "heldout_capture", 8: "reserved_free_release_validation"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not OUTPUT.exists(), "refusing to overwrite frozen allocation"
    OUTPUT.mkdir(parents=True)
    records = {}
    for index in (5, 7, 8):
        source = SOURCE_ROOT / f"stage26b_f002_revision3_candidate_{index:02d}/placement.json"
        assert digest(source) == EXPECTED[index]
        raw = json.loads(source.read_text(encoding="utf-8"))
        assert raw["passed"] is True and raw["candidate"]["candidate_index"] == index
        normalized = {
            "schema": "lbs.stage26e-normalized-placement.v1",
            "record_type": ROLES[index],
            "passed": True,
            "candidate": raw["candidate"],
            "allocation_frozen_before_stage26e_execution": True,
            "fibre_count": 2,
            "members_per_fibre": 37,
            "member_radius_m": 0.00005,
            "fibres": raw["fibres"],
            "maximum_initial_force_residual_relative": max(
                row["initial_normal_force_residual_relative"] for row in raw["fibres"]
            ),
            "maximum_initial_moment_residual_relative": max(
                row["initial_normal_moment_residual_relative"] for row in raw["fibres"]
            ),
            "source_placement_sha256": EXPECTED[index],
        }
        target = OUTPUT / f"revision3_candidate{index:02d}_{ROLES[index]}.json"
        target.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        records[str(index)] = {
            "role": ROLES[index],
            "source": str(source),
            "source_sha256": EXPECTED[index],
            "normalized": str(target),
            "normalized_sha256": digest(target),
        }
    manifest = {
        "schema": "lbs.stage26e-candidate-allocation-manifest.v1",
        "passed": True,
        "status": "unused_geometries_normalized_and_roles_frozen",
        "records": records,
        "authority": {
            "capture_config_preparation_authorized": True,
            "yade_execution_authorized": False,
            "free_release_authorized": False,
        },
    }
    manifest_path = OUTPUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "sha256": digest(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
