"""Create immutable schema-normalized placements for the audited fixed prefilter."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
POSITIVE = ROOT / "stage26_placements/stage26a_dry_f37_insertion_20260813/placement_03/placement.json"
NEGATIVE = ROOT / "stage26_placements/stage26b_dry_multifibre_20260814/tier1_preflight_01/stage26b_f002_A/placement.json"
CANDIDATE = ROOT / "stage26_placements/stage26b_revision3_joint_placement_20260816/candidate_generation_01/stage26b_f002_revision3_candidate_01/placement.json"
VISUAL = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/visual_checkpoint_01/checkpoint_manifest.json"
OUTPUT = ROOT / "stage26_placements/stage26c_revision3_fixed_prefilter_20260816/normalized_01"
EXPECTED = {
    "positive": "d1092744d76738de1974e5545b152716e12c6aa7ed03c728e5f8c4cbb2507ba2",
    "negative": "b151af80213490c932b378a6eea673cc619c90fd93a2ff8e5a1ec04294c1a270",
    "candidate": "7b574d43014c60a3ff301387637899772593b4036e66e0dd185e2fc9496beaa9",
    "visual": "c6cadd8e7d89b8867b3d14f21c70032772c109f11897b225c062878e21ea83d6",
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def normalize_positive(source):
    fibre = {
        "fibre_index": 0,
        "member_centres_m": source["member_centres_m"],
        "anchor_sand_body_ids": source["anchor_sand_body_ids"],
        "anchor_sand_indices": source["anchor_sand_indices"],
        "anchor_member_indices": source["anchor_member_indices"],
        "initial_distinct_sand_contact_count": source["initial_distinct_sand_contact_count"],
        "initial_normal_force_residual_relative": source["initial_normal_force_residual_relative"],
        "initial_normal_moment_residual_relative": source["initial_normal_moment_residual_relative"],
    }
    return {
        "schema": "lbs.stage26c-fixed-prefilter-normalized-placement.v1",
        "record_type": "positive_control",
        "passed": source["passed"],
        "fibre_count": 1,
        "members_per_fibre": 37,
        "member_radius_m": source["member_radius_m"],
        "fibres": [fibre],
        "maximum_initial_force_residual_relative": source["initial_normal_force_residual_relative"],
        "maximum_initial_moment_residual_relative": source["initial_normal_moment_residual_relative"],
        "source_placement_sha256": digest(POSITIVE),
    }


def normalize_multifibre(source, record_type, source_path):
    fibres = source["fibres"]
    return {
        "schema": "lbs.stage26c-fixed-prefilter-normalized-placement.v1",
        "record_type": record_type,
        "passed": source["passed"],
        "fibre_count": len(fibres),
        "members_per_fibre": 37,
        "member_radius_m": source.get("member_radius_m", 0.00005),
        "fibres": fibres,
        "maximum_initial_force_residual_relative": max(float(row["initial_normal_force_residual_relative"]) for row in fibres),
        "maximum_initial_moment_residual_relative": max(float(row["initial_normal_moment_residual_relative"]) for row in fibres),
        "source_placement_sha256": digest(source_path),
    }


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable normalized-placement output exists")
    for name, path in (("positive", POSITIVE), ("negative", NEGATIVE), ("candidate", CANDIDATE), ("visual", VISUAL)):
        if digest(path) != EXPECTED[name]:
            raise RuntimeError("source hash mismatch: " + name)
    visual = load(VISUAL)
    if visual.get("passed") is not True or visual["authority"].get("prefilter_design_authorized") is not True:
        raise RuntimeError("visual handoff does not authorize prefilter preparation")
    OUTPUT.mkdir(parents=True)
    values = {
        "positive_control.json": normalize_positive(load(POSITIVE)),
        "negative_control.json": normalize_multifibre(load(NEGATIVE), "negative_control", NEGATIVE),
        "revision3_candidate01.json": normalize_multifibre(load(CANDIDATE), "candidate", CANDIDATE),
    }
    for name, value in values.items():
        write(OUTPUT / name, value)
    manifest = {
        "schema": "lbs.stage26c-fixed-prefilter-normalized-placement-manifest.v1",
        "passed": True,
        "outputs": {name: digest(OUTPUT / name) for name in values},
        "sources": {"positive": digest(POSITIVE), "negative": digest(NEGATIVE), "candidate": digest(CANDIDATE), "visual_checkpoint": digest(VISUAL), "normalizer": digest(__file__)},
        "authority": {"prefilter_execution_config_preparation_authorized": True, "prefilter_yade_execution_authorized": False, "two_fibre_free_release_authorized": False},
        "claim_boundary": "Schema normalization for the fixed-fibre YADE prefilter only; no DEM execution or physics result."
    }
    write(OUTPUT / "manifest.json", manifest)
    print(json.dumps({"passed": True, "manifest_sha256": digest(OUTPUT / "manifest.json"), "outputs": manifest["outputs"]}, sort_keys=True))


if __name__ == "__main__":
    main()
