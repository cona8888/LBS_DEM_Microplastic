"""Freeze the accepted Stage26a dry single-fibre checkpoint and authority boundary."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = PROJECT / "stage26_runs" / "stage26a_dry_f37_insertion_20260813" / "qualification_03"
EVALUATION = PROJECT / "stage26_evaluations" / "stage26a_dry_f37_insertion_20260813" / "evaluation_01" / "evaluation.json"
RENDER = PROJECT / "stage26_renders" / "stage26a_dry_f37_insertion_20260813" / "qualification_render_01"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26a_dry_f37_insertion_20260813" / "checkpoint_01"


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
        raise RuntimeError("immutable Stage26 checkpoint already exists")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.mkdir()
    evaluation = load_json(EVALUATION)
    result_path = RUN / "result.json"; completion_path = RUN / "completion.json"; checkpoint_path = RUN / "dry_relaxed_state.yade.gz"
    result = load_json(result_path); completion = load_json(completion_path)
    render_manifest_path = RENDER / "render_manifest.json"; render = load_json(render_manifest_path)
    if not evaluation.get("passed") or not result.get("passed") or not completion.get("passed") or not render.get("passed"):
        raise RuntimeError("one or more Stage26 acceptance sources failed")
    if evaluation["evidence"]["result_sha256"] != digest(result_path) or evaluation["evidence"]["completion_sha256"] != digest(completion_path):
        raise RuntimeError("evaluation evidence binding failed")
    if result["artifacts"]["checkpoint_sha256"] != digest(checkpoint_path) or evaluation["evidence"]["checkpoint_sha256"] != digest(checkpoint_path):
        raise RuntimeError("checkpoint binding failed")
    if render["source_hashes"]["evaluation"] != digest(EVALUATION) or render["source_hashes"]["result"] != digest(result_path):
        raise RuntimeError("render evidence binding failed")
    for name, expected in render["images"].items():
        if digest(RENDER / name) != expected:
            raise RuntimeError("render image hash mismatch: " + name)
    terminal = evaluation["terminal"]
    handoff = {
        "schema": "lbs.stage26a-dry-f37-insertion.v2.frozen-checkpoint",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": True,
        "status": "frozen_dry_single_fibre_checkpoint",
        "metrics": {
            "sand_particle_count": 216, "fibre_count": 1, "fibre_member_count": 37,
            "nominal_plastic_mass_fraction": 0.00004599480104513159,
            "mean_effective_stress_pa": terminal["mean_effective_stress_pa_compression_positive"],
            "unbalanced_force": terminal["unbalanced_force"],
            "sand_sand_real_contacts": terminal["sand_sand_real_contact_count"],
            "sand_fibre_real_contacts": terminal["sand_fibre_real_contact_count"],
            "distinct_contacted_sand_grains": terminal["distinct_sand_contacts_per_fibre"],
            "sand_coordination_excluding_rattlers": terminal["sand_coordination_excluding_degree_lt2_rattlers"],
            "sand_rattler_fraction": terminal["sand_rattler_fraction_degree_lt2_iterative"],
            "maximum_nonaffine_sand_displacement_over_D50": terminal["maximum_nonaffine_sand_displacement_over_D50"],
            "fibre_com_displacement_over_length": terminal["fibre_com_displacement_over_length"],
            "fibre_tip_axis_rotation_degrees": terminal["fibre_tip_axis_rotation_degrees"],
        },
        "evidence": {
            "checkpoint_path": str(checkpoint_path), "checkpoint_sha256": digest(checkpoint_path),
            "result_path": str(result_path), "result_sha256": digest(result_path),
            "completion_path": str(completion_path), "completion_sha256": digest(completion_path),
            "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION),
            "render_manifest_path": str(render_manifest_path), "render_manifest_sha256": digest(render_manifest_path),
            "relaxation_summary_sha256": digest(RENDER / "stage26a_dry_relaxation_summary.png"),
            "accepted_geometry_sha256": digest(RENDER / "stage26a_accepted_free_fibre_geometry.png"),
            "freezer_sha256": digest(Path(__file__)),
        },
        "failure_history": {
            "qualification_01": "Free fibre immediately lost both geometric-only anchors; preserved as failed physics evidence.",
            "qualification_02": "Wrapper path defect before checkpoint load; preserved as software failure evidence.",
            "qualification_03": "Force/moment-balanced placement plus fixed conditioning and free release; independently passed."
        },
        "authority": {
            "authorized_next_activity": "Design-only Stage26b multi-fibre dry concentration ladder using the frozen Stage25 sand baseline and Stage26a insertion lessons.",
            "multi_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "transient_two_way_coupling_authorized": False,
            "deformation_coupled_flow_authorized": False,
            "production_parametric_study_authorized": False
        },
        "claim_boundary": evaluation["claim_boundary"],
    }
    path = OUTPUT / "checkpoint_manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(handoff, stream, indent=2, sort_keys=True, allow_nan=False); stream.write("\n")
    print(json.dumps({"passed": True, "checkpoint_manifest_sha256": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
