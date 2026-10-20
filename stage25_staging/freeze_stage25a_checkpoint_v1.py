"""Freeze the accepted Stage25a pure-sand mechanics checkpoint without promoting physics."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage25_evaluations" / "stage25a_pure_sand_mechanics_20260813" / "evaluation_01" / "evaluation.json"
RUN = PROJECT / "stage25_runs" / "stage25a_pure_sand_mechanics_20260813" / "qualification_04"
EXPORT = PROJECT / "stage25_exports" / "stage25a_pure_sand_mechanics_20260813" / "contact_export_01"
RENDER = PROJECT / "stage25_renders" / "stage25a_pure_sand_mechanics_20260813" / "render_05"
OUTPUT = PROJECT / "stage25_checkpoints" / "stage25a_pure_sand_mechanics_20260813" / "checkpoint_01"


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
        raise RuntimeError("immutable checkpoint handoff already exists")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir()
    evaluation = load_json(EVALUATION)
    export_completion_path = EXPORT / "completion.json"
    export_completion = load_json(export_completion_path)
    render_manifest_path = RENDER / "render_manifest.json"
    render_manifest = load_json(render_manifest_path)
    selected = evaluation["selection"]
    case_dir = RUN / selected["case_id"]
    checkpoint = case_dir / "load_bearing_state.yade.gz"
    result_path = case_dir / "result.json"
    if evaluation.get("passed") is not True or selected["case_id"] != "mu_0.60":
        raise RuntimeError("evaluation not accepted or selection changed")
    if digest(checkpoint) != selected["checkpoint_sha256"]:
        raise RuntimeError("checkpoint hash mismatch")
    if export_completion.get("passed") is not True or export_completion["source"]["checkpoint_sha256"] != digest(checkpoint):
        raise RuntimeError("contact export is not bound to selected checkpoint")
    if render_manifest.get("passed") is not True or render_manifest["selected_case_id"] != selected["case_id"]:
        raise RuntimeError("final render is not accepted")
    if render_manifest["source_hashes"]["evaluation_sha256"] != digest(EVALUATION):
        raise RuntimeError("final render is not bound to evaluation")
    for image, expected in render_manifest["images"].items():
        if digest(RENDER / image) != expected:
            raise RuntimeError("final image hash mismatch: " + image)

    handoff = {
        "schema": "lbs.stage25a-load-bearing-pure-sand-pilot.v1.frozen-checkpoint",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_pure_sand_load_bearing_checkpoint",
        "passed": True,
        "selected_case_id": selected["case_id"],
        "selection_interpretation": selected["basis"],
        "metrics": {
            "particle_count": 216,
            "void_ratio": selected["void_ratio"],
            "mean_effective_stress_pa": selected["mean_effective_stress_pa"],
            "coordination_excluding_rattlers": selected["coordination_excluding_rattlers"],
            "rattler_fraction": selected["rattler_fraction"],
            "real_contact_count": selected["real_contact_count"],
        },
        "evidence": {
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": digest(checkpoint),
            "selected_result_path": str(result_path),
            "selected_result_sha256": digest(result_path),
            "evaluation_path": str(EVALUATION),
            "evaluation_sha256": digest(EVALUATION),
            "contact_export_completion_path": str(export_completion_path),
            "contact_export_completion_sha256": digest(export_completion_path),
            "render_manifest_path": str(render_manifest_path),
            "render_manifest_sha256": digest(render_manifest_path),
            "qualification_summary_sha256": digest(RENDER / "stage25a_qualification_summary.png"),
            "selected_contact_network_sha256": digest(RENDER / "stage25a_selected_contact_network.png"),
            "freezer_sha256": digest(Path(__file__)),
        },
        "authority": {
            "authorized_next_activity": "Design-only Stage26 fibre insertion and dry mechanical compatibility qualification using this frozen pure-sand checkpoint.",
            "fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "transient_two_way_coupling_authorized": False,
            "deformation_coupled_flow_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "claim_boundary": evaluation["claim_boundary"],
    }
    output_path = OUTPUT / "checkpoint_manifest.json"
    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(handoff, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "selected_case_id": selected["case_id"], "checkpoint_manifest_sha256": digest(output_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
