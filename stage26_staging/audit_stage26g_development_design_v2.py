"""Audit Stage26g design v2 after the import-only integration correction."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path):
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--design-dir", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--derivation", required=True)
    parser.add_argument("--failure", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    design_dir = Path(args.design_dir).resolve()
    runner_path = Path(args.runner).resolve()
    derivation_path = Path(args.derivation).resolve()
    failure_path = Path(args.failure).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26g design-v2 audit already exists")
    design_path = design_dir / "resolved_design.json"
    execution_path = design_dir / "development_execution.json"
    manifest_path = design_dir / "design_manifest.json"
    design, execution, manifest, derivation, failure = (
        load(design_path), load(execution_path), load(manifest_path),
        load(derivation_path), load(failure_path)
    )
    runner = runner_path.read_text(encoding="utf-8")
    checks = {
        "manifest_bindings": (
            manifest["resolved_design_sha256"] == digest(design_path)
            and manifest["development_execution_sha256"] == digest(execution_path)
            and manifest["allocation_sha256"] == digest(design_dir / "allocation.csv")
        ),
        "v2_runner_binding": (
            derivation["output_v2_sha256"] == digest(runner_path)
            and execution["sources"]["capture_runner_sha256"] == digest(runner_path)
        ),
        "failure_lineage": (
            failure["simulation_steps_executed"] == 0
            and failure["runner_v1_sha256"] == derivation["source_v1_sha256"]
            and execution["sources"]["runner_v1_integration_failure_sha256"] == digest(failure_path)
        ),
        "only_declared_import_change": derivation["single_change"] == {
            "old": "from stage26g_capture_common_v1 import advance_equilibrium_streak",
            "new": "from stage26e_capture_common_v1 import advance_equilibrium_streak",
        },
        "tested_helper_import_present": "from stage26e_capture_common_v1 import advance_equilibrium_streak" in runner,
        "four_contact_insertion": 'all(value == 4 for value in insertion["distinct_sand_contacts_by_fibre"])' in runner,
        "four_support_source": 'fibre["support_sand_body_ids"]' in runner,
        "all_fibre_dofs_blocked": 'parent.state.blockedDOFs = "xyzXYZ"' in runner and 'blockedDOFs = ""' not in runner,
        "allocation_unchanged": design["allocation"] == {"development": [6, 7, 8], "heldout": [4, 2], "reserve": [5, 1, 3]},
        "physics_and_gates_unchanged": manifest["physics_or_acceptance_gate_changed"] is False,
        "heldout_release_flow_locked": (
            execution["authority"]["heldout_execution_authorized"] is False
            and not any(execution["authority"].get(key, False) for key in (
                "two_fibre_free_release_authorized", "flow_execution_authorized",
                "deformation_authorized", "production_parametric_study_authorized",
                "legacy_revision3_candidate08_execution_authorized"
            ))
        ),
        "three_development_trials": len(execution["trials"]) == 3 and [row["candidate_index"] for row in execution["trials"]] == [6, 7, 8],
        "normalized_placements_bound": True,
    }
    for trial in execution["trials"]:
        placement_path = Path(trial["placement"])
        placement = load(placement_path)
        checks["normalized_placements_bound"] = (
            checks["normalized_placements_bound"]
            and digest(placement_path) == trial["placement_sha256"]
            and all(len(fibre["support_sand_body_ids"]) == 4 for fibre in placement["fibres"])
        )
    passed = all(checks.values())
    output.mkdir(parents=True)
    evaluation = {
        "schema": "lbs.stage26g-development-design-audit.v2",
        "passed": passed,
        "status": "development_execution_v2_authorized" if passed else "development_design_v2_audit_failed",
        "checks": checks,
        "source_hashes": {
            "design": digest(design_path), "execution": digest(execution_path),
            "manifest": digest(manifest_path), "runner_v2": digest(runner_path),
            "derivation_v2": digest(derivation_path), "failure_v1": digest(failure_path),
            "auditor": digest(Path(__file__))
        },
        "authority": {
            "development_yade_execution_authorized": passed,
            "heldout_yade_execution_authorized": False,
            "free_release_authorized": False,
            "flow_authorized": False
        },
        "claim_boundary": design["claim_boundary"]
    }
    with (output / "evaluation.json").open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(output / "evaluation.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
