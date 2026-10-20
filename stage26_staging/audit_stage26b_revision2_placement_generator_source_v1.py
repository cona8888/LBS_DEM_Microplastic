"""Independent static and functional audit of the offline placement generator."""

import ast
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
SOURCE = PROJECT / "stage26_staging" / "generate_stage26b_revision2_placements_v1.py"
PREPARATION = PROJECT / "stage26_staging" / "stage26b_revision2_placement_generation_preparation_v1.json"
PREPARATION_CHECKPOINT = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "placement_generation_preparation_checkpoint_01" / "checkpoint_manifest.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "placement_generator_source_evaluation_01"


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
        raise RuntimeError("immutable generator-source evaluation already exists")
    preparation = load_json(PREPARATION)
    checkpoint = load_json(PREPARATION_CHECKPOINT)
    network = load_json(Path(preparation["sources"]["network"]))
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(SOURCE))
    imports = set()
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    spec = importlib.util.spec_from_file_location("stage26b_generator_audit_target", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = preparation["generator_contract"]
    pairs = module.eligible_anchor_pairs(network["particles"], contract["minimum_anchor_network_degree"], contract["preferred_anchor_network_degree"], contract["anchor_pair_distance_m"])
    particles = network["particles"]
    pair_screen_valid = len(pairs) > 0 and all(
        particles[row[5]]["load_bearing_core_member"] is True
        and particles[row[6]]["load_bearing_core_member"] is True
        and min(int(particles[row[5]]["sand_network_degree"]), int(particles[row[6]]["sand_network_degree"])) >= 3
        and contract["anchor_pair_distance_m"][0] <= row[7] <= contract["anchor_pair_distance_m"][1]
        for row in pairs
    )
    synthetic_clearance = module.periodic_clearance(
        np.array([[0.0001, 0.0, 0.0]]), np.array([[0.0099, 0.0, 0.0]]),
        np.array([0.01, 0.01, 0.01]), 0.0,
    )[0, 0]
    decisions = {
        "reject_anchor_geometry", "reject_outside_primary_cell", "reject_sand_penetration",
        "reject_contact_set", "reject_anchor_clearance", "reject_fibre_clearance",
        "reject_force_residual", "reject_moment_residual", "accepted",
    }
    checks = {
        "preparation_checkpoint_passed": checkpoint.get("passed") is True and checkpoint.get("status") == "frozen_deterministic_placement_generator_source_contract",
        "source_path_matches_frozen_contract": Path(contract["future_source"]) == SOURCE,
        "host_python_only_no_yade_or_process_launch": "yade" not in imports and "subprocess" not in imports and not ({"system", "Popen", "run", "execv", "execve"} & calls),
        "fail_closed_status_and_authority": (
            "authorized_stage26b_revision2_placement_generation" in text
            and "placement_generation_authorized" in text
            and all(marker in text for marker in ("prefilter_yade_execution_authorized", "two_fibre_free_release_authorized", "four_fibre_execution_authorized", "flow_execution_authorized"))
        ),
        "immutable_outputs_use_exclusive_creation": 'open("x"' in text and "if output.exists()" in text,
        "every_attempt_has_compressed_ledger": "gzip.open" in text and "attempts.csv.gz" in text and "ledger.writerow" in text,
        "all_rejection_classes_are_explicit": all(decision in text for decision in decisions),
        "predeclared_budget_enforced_without_extension": "maximum_trials_per_candidate" in text and "remaining =" in text and "rolls_for_pair = min(512, budget - attempts)" in text,
        "network_anchor_screen_functional": pair_screen_valid,
        "preferred_degree_sort_is_deterministic": pairs == sorted(pairs) and module.eligible_anchor_pairs(network["particles"], 3, 4, [0.00135, 0.00225]) == pairs,
        "periodic_minimum_image_functional": abs(float(synthetic_clearance) - 0.0002) < 1e-15,
        "exact_two_fibre_and_37_member_contract_present": "for fibre_index in range(2)" in text and contract["members_per_fibre"] == 37,
        "all_required_geometry_gates_present": all(marker in text for marker in (
            "fibres_wholly_inside_primary_cell", "minimum_initial_fibre_fibre_clearance_m",
            "maximum_sand_fibre_penetration_over_member_radius", "maximum_initial_force_residual_relative",
            "maximum_initial_moment_residual_relative", "initial_distinct_sand_contact_count",
        )),
        "campaign_publishes_all_candidate_outcomes": "candidate_index.csv" in text and "passing_candidate_count" in text and "completed_predeclared_candidate_budgets" in text,
        "no_candidate_output_created_during_audit": not Path(preparation["immutable_output_contract"]["future_output_root"]).exists(),
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-placement-generator-source-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_offline_placement_generator_source_audit" if passed else "failed_placement_generator_source_audit",
        "checks": checks,
        "functional_summary": {"eligible_anchor_pair_count": len(pairs), "minimum_image_test_m": float(synthetic_clearance)},
        "evidence": {
            "source_path": str(SOURCE), "source_sha256": digest(SOURCE),
            "preparation_path": str(PREPARATION), "preparation_sha256": digest(PREPARATION),
            "preparation_checkpoint_path": str(PREPARATION_CHECKPOINT), "preparation_checkpoint_sha256": digest(PREPARATION_CHECKPOINT),
            "network_path": preparation["sources"]["network"], "network_sha256": digest(Path(preparation["sources"]["network"])),
            "auditor_sha256": digest(Path(__file__)),
        },
        "authority": {
            "authorized_next_activity": "Prepare and independently audit the exact immutable placement-generation execution configuration; do not generate candidates yet.",
            "placement_generation_execution_preparation_authorized": passed,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": preparation["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(path), "eligible_anchor_pairs": len(pairs)}, sort_keys=True))
    if not passed:
        print(json.dumps({"failed_checks": [name for name, value in checks.items() if not value]}, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
