"""Freeze the verified Stage26b Tier-1 adaptive failure checkpoint."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_dry_multifibre_20260814" / "tier1_yade_evaluation_01" / "evaluation.json"
RENDER = PROJECT / "stage26_renders" / "stage26b_dry_multifibre_20260814" / "tier1_yade_failure_render_01" / "render_manifest.json"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26b_dry_multifibre_20260814" / "tier1_yade_failure_checkpoint_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable Tier-1 failure checkpoint already exists")
    evaluation = load_json(EVALUATION)
    render = load_json(RENDER)
    if not evaluation.get("passed") or evaluation.get("scientific_outcome_passed") is not False:
        raise RuntimeError("evaluation does not verify the scientific failure")
    if not render.get("passed") or render["source_hashes"]["evaluation"] != digest(EVALUATION):
        raise RuntimeError("render/evaluation binding failed")
    image_path = Path(render["image_path"])
    if digest(image_path) != render["image_sha256"]:
        raise RuntimeError("image hash mismatch")
    for name in ("result", "completion", "probe"):
        path = Path(evaluation["evidence"][name + "_path"])
        if digest(path) != evaluation["evidence"][name + "_sha256"]:
            raise RuntimeError(name + " evidence hash mismatch")
    terminal = evaluation["terminal"]
    checkpoint = {
        "schema": "lbs.stage26b-tier1-yade-failure-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "frozen_verified_two_fibre_conditioning_failure",
        "scientific_outcome_passed": False,
        "failure_classification": evaluation["failure_classification"],
        "adaptive_decision": evaluation["adaptive_decision"],
        "terminal_metrics": {
            "mean_effective_stress_pa": terminal["mean_effective_stress_pa_compression_positive"],
            "unbalanced_force": terminal["unbalanced_force"],
            "sand_sand_real_contacts": terminal["sand_sand_real_contact_count"],
            "sand_contact_retention_fraction": terminal["sand_sand_contact_retention_fraction"],
            "sand_coordination_excluding_rattlers": terminal["sand_coordination_excluding_degree_lt2_rattlers"],
            "distinct_sand_contacts_by_fibre": terminal["distinct_sand_contacts_by_fibre"],
            "isolated_fibre_count": terminal["isolated_fibre_count"],
            "maximum_sand_displacement_over_D50": terminal["maximum_nonaffine_sand_displacement_over_D50"],
            "maximum_fibre_displacement_over_length": terminal["maximum_fibre_com_displacement_over_length"],
        },
        "evidence": {
            "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION),
            "render_manifest_path": str(RENDER), "render_manifest_sha256": digest(RENDER),
            "failure_visual_path": str(image_path), "failure_visual_sha256": digest(image_path),
            "result_path": evaluation["evidence"]["result_path"], "result_sha256": evaluation["evidence"]["result_sha256"],
            "completion_path": evaluation["evidence"]["completion_path"], "completion_sha256": evaluation["evidence"]["completion_sha256"],
            "initial_contact_probe_path": evaluation["evidence"]["probe_path"], "initial_contact_probe_sha256": evaluation["evidence"]["probe_sha256"],
            "freezer_sha256": digest(Path(__file__)),
        },
        "authority": {
            "authorized_next_activity": "Design-only Tier-1 placement-stability revision using load-bearing anchor screening and an engine-based fixed-conditioning prefilter.",
            "two_fibre_rerun_authorized": False,
            "four_fibre_execution_authorized": False,
            "eight_or_more_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "transient_two_way_coupling_authorized": False,
            "deformation_coupled_flow_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "claim_boundary": evaluation["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "checkpoint_manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(checkpoint, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "checkpoint_manifest_sha256": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
