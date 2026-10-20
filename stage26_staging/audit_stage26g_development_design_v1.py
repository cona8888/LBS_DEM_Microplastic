"""Fail-closed audit of Stage26g runner and development execution design."""

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
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    design_dir = Path(args.design_dir).resolve()
    runner_path = Path(args.runner).resolve()
    derivation_path = Path(args.derivation).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26g design audit already exists")
    design_path = design_dir / "resolved_design.json"
    execution_path = design_dir / "development_execution.json"
    manifest_path = design_dir / "design_manifest.json"
    design, execution, manifest, derivation = (
        load(design_path), load(execution_path), load(manifest_path), load(derivation_path)
    )
    runner = runner_path.read_text(encoding="utf-8")
    checks = {
        "design_manifest_bindings": (
            manifest["resolved_design_sha256"] == digest(design_path)
            and manifest["development_execution_sha256"] == digest(execution_path)
            and manifest["allocation_sha256"] == digest(design_dir / "allocation.csv")
        ),
        "runner_derivation_binding": (
            derivation.get("passed") is True
            and derivation["output_sha256"] == digest(runner_path)
            and execution["sources"]["capture_runner_sha256"] == digest(runner_path)
        ),
        "runner_uses_stage26g_environment": "STAGE26G_CAGE_CONFIG" in runner and "STAGE26G_CAGE_OUTPUT" in runner,
        "runner_requires_four_contacts": 'all(value == 4 for value in insertion["distinct_sand_contacts_by_fibre"])' in runner,
        "runner_uses_support_bodies": 'fibre["support_sand_body_ids"]' in runner and "anchor_sand_body_ids" not in runner,
        "runner_blocks_all_fibre_dofs": 'parent.state.blockedDOFs = "xyzXYZ"' in runner,
        "runner_has_no_free_release_assignment": 'blockedDOFs = ""' not in runner,
        "development_allocation_frozen": design["allocation"] == {
            "development": [6, 7, 8], "heldout": [4, 2], "reserve": [5, 1, 3]
        },
        "development_acceptance_frozen": design["development_acceptance"]["required_qualified_cases"] == 2,
        "heldout_locked": (
            design["authority"]["heldout_yade_execution_authorized"] is False
            and execution["authority"]["heldout_execution_authorized"] is False
        ),
        "release_and_flow_locked": not any(
            execution["authority"].get(key, False)
            for key in (
                "two_fibre_free_release_authorized",
                "flow_execution_authorized",
                "deformation_authorized",
                "production_parametric_study_authorized",
                "legacy_revision3_candidate08_execution_authorized",
            )
        ),
        "three_development_trials_only": (
            len(execution["trials"]) == 3
            and [row["candidate_index"] for row in execution["trials"]] == [6, 7, 8]
            and all(row["stage26g_role"] == "development_capture" for row in execution["trials"])
        ),
        "four_support_placement_inputs": True,
        "normalized_hashes_bound": True,
    }
    for trial in execution["trials"]:
        path = Path(trial["placement"])
        value = load(path)
        checks["normalized_hashes_bound"] = checks["normalized_hashes_bound"] and digest(path) == trial["placement_sha256"]
        checks["four_support_placement_inputs"] = checks["four_support_placement_inputs"] and all(
            len(fibre["support_sand_body_ids"]) == 4 for fibre in value["fibres"]
        ) and value.get("legacy_stage26b_revision3_candidate08_read_or_used") is False
    passed = all(checks.values())
    output.mkdir(parents=True)
    evaluation = {
        "schema": "lbs.stage26g-development-design-audit.v1",
        "passed": passed,
        "status": "development_execution_authorized" if passed else "development_design_audit_failed",
        "checks": checks,
        "source_hashes": {
            "design": digest(design_path),
            "execution": digest(execution_path),
            "manifest": digest(manifest_path),
            "runner": digest(runner_path),
            "derivation": digest(derivation_path),
            "auditor": digest(Path(__file__)),
        },
        "authority": {
            "development_yade_execution_authorized": passed,
            "heldout_yade_execution_authorized": False,
            "free_release_authorized": False,
            "flow_authorized": False,
        },
        "claim_boundary": design["claim_boundary"],
    }
    with (output / "evaluation.json").open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(output / "evaluation.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
