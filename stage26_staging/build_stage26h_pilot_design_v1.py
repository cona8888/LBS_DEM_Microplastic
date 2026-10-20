#!/usr/bin/env python3
"""Freeze the Stage26h bounded mobile-conditioning pilot design."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage26g-design", type=Path, required=True)
    parser.add_argument("--stage26g-evaluation", type=Path, required=True)
    parser.add_argument("--stage26g-checkpoint", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    g_design = load_json(args.stage26g_design / "resolved_design.json")
    g_exec = load_json(args.stage26g_design / "development_execution.json")
    g_eval = load_json(args.stage26g_evaluation)
    assert g_eval["development_acceptance_passed"] is False
    assert g_eval["heldout_execution_authorized"] is False
    trial = next(row for row in g_exec["trials"] if row["candidate_index"] == 7)
    assert trial["record_type"] == "development_capture"
    preexecution_rejection = args.runner.with_name("stage26h_design01_preexecution_rejection.json")
    import_failure = args.runner.with_name("stage26h_design02_import_failure.json")
    namespace_failure = args.runner.with_name("stage26h_design03_helper_namespace_failure.json")
    helper = args.runner.with_name("stage26h_common_v1.py")
    assert preexecution_rejection.is_file()
    assert import_failure.is_file()
    assert namespace_failure.is_file()
    assert helper.is_file()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    gates = dict(g_design["equilibrium_window_gates"])
    gates["minimum_declared_support_contacts_per_fibre"] = 2
    gates["minimum_distinct_sand_contacts_per_fibre"] = 3
    config = {
        "schema": "lbs.stage26h-bounded-mobile-conditioning-pilot-config.v1",
        "status": "authorized_stage26h_spent_development_pilot",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "physical_question": (
            "Can a rank-six four-support cage retain at least three fibre-sand contacts when the fibres "
            "are allowed a small, guarded preparation motion and then survive a fixed-fibre validation window?"
        ),
        "trial": trial,
        "authority": {
            "bounded_mobile_conditioning_authorized": True,
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "unbounded_free_release_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "conditioning_protocol": {
            "steps_per_block": 500,
            "mobile_minimum_block": 30,
            "mobile_maximum_blocks": 120,
            "fixed_validation_maximum_blocks": 30,
            "required_consecutive_passing_blocks": 10,
            "maximum_strain_rate_s_inv": 0.01,
        },
        "conditioning_guards": {
            "maximum_isolated_fibre_count": 0,
            "minimum_distinct_contacts_per_fibre": 2,
            "maximum_interobject_penetration_over_smaller_radius": 0.02,
            "maximum_fibre_translation_over_D50": 0.05,
            "maximum_fibre_rotation_deg": 10.0,
        },
        "equilibrium_gates": gates,
        "candidate_generation": g_exec["candidate_generation"],
        "network_export": g_exec["network_export"],
        "frozen_physics": dict(g_exec["frozen_physics"]),
        "sources": {
            "runner": str(args.runner).replace("\\", "/"),
            "runner_sha256": sha256(args.runner),
            "helper": str(helper).replace("\\", "/"),
            "helper_sha256": sha256(helper),
            "stage25_checkpoint": g_exec["sources"]["stage25_checkpoint"],
            "stage25_checkpoint_sha256": g_exec["sources"]["stage25_checkpoint_sha256"],
            "stage26g_design": str(args.stage26g_design / "resolved_design.json").replace("\\", "/"),
            "stage26g_design_sha256": sha256(args.stage26g_design / "resolved_design.json"),
            "stage26g_evaluation": str(args.stage26g_evaluation).replace("\\", "/"),
            "stage26g_evaluation_sha256": sha256(args.stage26g_evaluation),
            "stage26g_checkpoint": str(args.stage26g_checkpoint).replace("\\", "/"),
            "stage26g_checkpoint_sha256": sha256(args.stage26g_checkpoint),
            "design01_preexecution_rejection": str(preexecution_rejection).replace("\\", "/"),
            "design01_preexecution_rejection_sha256": sha256(preexecution_rejection),
            "design02_import_failure": str(import_failure).replace("\\", "/"),
            "design02_import_failure_sha256": sha256(import_failure),
            "design03_helper_namespace_failure": str(namespace_failure).replace("\\", "/"),
            "design03_helper_namespace_failure_sha256": sha256(namespace_failure),
            "expected_yade_version": "2022.01a",
        },
        "claim_boundary": (
            "Stage26h single spent-development-geometry feasibility pilot for bounded fibre motion during "
            "specimen preparation followed by fixed validation; no held-out inference, flow, permeability, "
            "deformation, migration, or production result."
        ),
    }
    config["frozen_physics"]["newton_damping"] = 0.70
    config["frozen_physics"]["timestep_safety_coefficient"] = 0.10
    config_path = args.output_dir / "pilot_config.json"
    with config_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(config, stream, indent=2, sort_keys=True)
        stream.write("\n")
    manifest = {
        "schema": "lbs.stage26h-bounded-mobile-conditioning-design-manifest.v1",
        "passed": True,
        "status": "frozen_spent_development_pilot",
        "config_sha256": sha256(config_path),
        "source_hashes": {
            "builder": sha256(Path(__file__)),
            "runner": sha256(args.runner),
            "stage26g_evaluation": sha256(args.stage26g_evaluation),
            "stage26g_checkpoint": sha256(args.stage26g_checkpoint),
            "design01_preexecution_rejection": sha256(preexecution_rejection),
            "design02_import_failure": sha256(import_failure),
            "design03_helper_namespace_failure": sha256(namespace_failure),
            "helper": sha256(helper),
        },
        "heldout_and_reserve_untouched": True,
    }
    manifest_path = args.output_dir / "design_manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(config_path), "config_sha256": manifest["config_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
