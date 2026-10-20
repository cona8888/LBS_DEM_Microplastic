"""Rebind the frozen Stage26g design to the import-corrected runner v2."""

import argparse
import csv
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


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-design", required=True)
    parser.add_argument("--runner-v2", required=True)
    parser.add_argument("--derivation-v2", required=True)
    parser.add_argument("--failure", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(args.source_design).resolve()
    runner = Path(args.runner_v2).resolve()
    derivation = Path(args.derivation_v2).resolve()
    failure = Path(args.failure).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26g design-v2 output already exists")
    prior_design = load(source / "resolved_design.json")
    prior_execution = load(source / "development_execution.json")
    derivation_value = load(derivation)
    failure_value = load(failure)
    if derivation_value.get("output_v2_sha256") != digest(runner):
        raise RuntimeError("runner-v2 derivation mismatch")
    if failure_value.get("runner_v1_sha256") != derivation_value.get("source_v1_sha256"):
        raise RuntimeError("integration-failure lineage mismatch")
    output.mkdir(parents=True)
    normalized = output / "normalized_placements"
    normalized.mkdir()
    new_paths = {}
    for old_path in sorted((source / "normalized_placements").glob("*.json")):
        new_path = normalized / old_path.name
        write(new_path, load(old_path))
        if digest(new_path) != digest(old_path):
            raise RuntimeError("normalized placement changed during v2 rebinding")
        new_paths[old_path.name] = new_path
    allocation_rows = []
    with (source / "allocation.csv").open("r", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            old_name = Path(row["normalized_placement"]).name
            row["normalized_placement"] = str(new_paths[old_name]).replace("\\", "/")
            row["normalized_placement_sha256"] = digest(new_paths[old_name])
            allocation_rows.append(row)
    allocation_path = output / "allocation.csv"
    with allocation_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(allocation_rows[0]))
        writer.writeheader()
        writer.writerows(allocation_rows)
    design = dict(prior_design)
    design["schema"] = "lbs.stage26g-fresh-cage-fixed-fibre-qualification-design.v2"
    design["status"] = "frozen_after_pre_execution_import_correction"
    design["integration_erratum"] = {
        "simulation_steps_in_failed_v1_launch": 0,
        "physics_or_gates_changed": False,
        "only_change": "Bind the generated runner to the existing frozen stage26e_capture_common_v1 helper module name."
    }
    design["source_hashes"] = dict(design["source_hashes"])
    design["source_hashes"].update(
        {
            "runner": digest(runner),
            "runner_derivation": digest(derivation),
            "runner_v1_integration_failure": digest(failure),
            "allocation": digest(allocation_path),
        }
    )
    design_path = output / "resolved_design.json"
    write(design_path, design)
    execution = dict(prior_execution)
    execution["schema"] = "lbs.stage26g-development-fixed-cage-capture-execution.v2"
    execution["sources"] = dict(execution["sources"])
    execution["sources"].update(
        {
            "capture_runner": str(runner).replace("\\", "/"),
            "capture_runner_sha256": digest(runner),
            "runner_derivation": str(derivation).replace("\\", "/"),
            "runner_derivation_sha256": digest(derivation),
            "runner_v1_integration_failure": str(failure).replace("\\", "/"),
            "runner_v1_integration_failure_sha256": digest(failure),
            "stage26g_resolved_design": str(design_path).replace("\\", "/"),
            "stage26g_resolved_design_sha256": digest(design_path),
        }
    )
    for trial in execution["trials"]:
        name = Path(trial["placement"]).name
        trial["placement"] = str(new_paths[name]).replace("\\", "/")
        trial["placement_sha256"] = digest(new_paths[name])
    execution_path = output / "development_execution.json"
    write(execution_path, execution)
    manifest = {
        "schema": "lbs.stage26g-development-design-manifest.v2",
        "passed": True,
        "prior_design_manifest_sha256": digest(source / "design_manifest.json"),
        "resolved_design_sha256": digest(design_path),
        "development_execution_sha256": digest(execution_path),
        "allocation_sha256": digest(allocation_path),
        "runner_v2_sha256": digest(runner),
        "runner_v2_derivation_sha256": digest(derivation),
        "runner_v1_integration_failure_sha256": digest(failure),
        "physics_or_acceptance_gate_changed": False,
        "builder_sha256": digest(Path(__file__)),
    }
    write(output / "design_manifest.json", manifest)
    print(json.dumps({"passed": True, "design_sha256": digest(design_path), "execution_sha256": digest(execution_path), "manifest_sha256": digest(output / "design_manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
