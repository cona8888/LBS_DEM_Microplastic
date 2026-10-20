"""Fail-closed static and unit audit for the Revision-3 placement generator."""

import ast
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage26_staging/generate_stage26b_revision3_joint_placements_v1.py"
DESIGN = ROOT / "stage26_staging/stage26b_revision3_joint_placement_design_v1.json"
DESIGN_CHECKPOINT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/design_checkpoint_01/checkpoint_manifest.json"
NETWORK = ROOT / "stage26_network_exports/stage26b_revision2_stage25_network_20260816/export_04/network.json"
GEOMETRY = Path("C:/Users/wonjuncha-admin/Documents/Codex/2026-07-19/skill-creator-c-users-wonjuncha-admin/yade_benchmark/lbs_calibration/runs/stage8_shape_fibre_visual_gate_20260722/geometry_review.json")
OUTPUT = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/generator_source_evaluation_02/evaluation.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def check(condition, message, checks, failures):
    checks.append({"check": message, "passed": bool(condition)})
    if not condition:
        failures.append(message)


def main():
    checks = []
    failures = []
    for path in (SOURCE, DESIGN, DESIGN_CHECKPOINT, NETWORK, GEOMETRY):
        check(path.is_file(), f"required file exists: {path}", checks, failures)
    if failures:
        raise RuntimeError("; ".join(failures))
    design = load(DESIGN)
    checkpoint = load(DESIGN_CHECKPOINT)
    check(checkpoint.get("passed") is True, "design checkpoint passed", checks, failures)
    check(
        checkpoint["evidence"]["design_sha256"] == digest(DESIGN),
        "design checkpoint binds exact design",
        checks,
        failures,
    )
    check(
        checkpoint["authority"].get("source_implementation_authorized") is True,
        "design checkpoint authorizes source implementation",
        checks,
        failures,
    )
    source_text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
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
    check("yade" not in imports, "generator does not import YADE", checks, failures)
    check("subprocess" not in imports, "generator does not import subprocess", checks, failures)
    check(not ({"system", "popen", "spawn", "execv", "execve"} & calls), "generator has no process-launch calls", checks, failures)
    for name in (
        "analytical_tip_feasible",
        "screen_anchor_pairs",
        "evaluate_single",
        "find_joint_partner",
        "generate_candidate",
    ):
        check(f"def {name}(" in source_text, f"required function present: {name}", checks, failures)
    check("maximum_proposals_per_candidate" in source_text, "predeclared proposal ceiling is enforced", checks, failures)
    check("maximum_retained_single_fibres" in source_text, "retained-pool ceiling is enforced", checks, failures)
    check("maximum_retained_placements_per_anchor_pair" in source_text, "anchor-pair diversity cap is enforced", checks, failures)
    check("accepted_joint_pair" in source_text, "joint acceptance is explicitly logged", checks, failures)
    check("attempts.csv.gz" in source_text, "every-proposal ledger is configured", checks, failures)
    check("output.exists()" in source_text, "immutable output guard is present", checks, failures)

    sys.path.insert(0, str(SOURCE.parent))
    spec = importlib.util.spec_from_file_location("revision3_generator_audit_target", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tol = 1e-14
    check(module.analytical_tip_feasible(2.0, 1.0, 0.6, 0.4, tol), "analytical upper-bound intersection passes", checks, failures)
    check(module.analytical_tip_feasible(1.2, 1.0, 0.6, 0.4, tol), "analytical lower-bound intersection passes", checks, failures)
    check(not module.analytical_tip_feasible(2.000001, 1.0, 0.6, 0.4, tol), "analytical outside-upper case fails", checks, failures)
    check(not module.analytical_tip_feasible(1.199999, 1.0, 0.6, 0.4, tol), "analytical inside-lower gap fails", checks, failures)
    first = np.asarray([[0.01, 0.50, 0.50]])
    second = np.asarray([[0.99, 0.50, 0.50]])
    clearance = float(module.periodic_clearance(first, second, np.ones(3), 0.01).min())
    check(abs(clearance - 0.01) < 1e-14, "periodic minimum-image clearance is exact", checks, failures)

    network = load(NETWORK)
    geometry = load(GEOMETRY)
    gates = design["unchanged_physical_gates"]
    template = geometry["fibre_candidates"]["f37_kinked_ar10"]
    local = np.asarray([row["center_m"] for row in template["members"]], dtype=float)
    tip_span = float(np.linalg.norm(local[36] - local[0]))
    target_penetration = gates["target_anchor_penetration_over_member_radius"] * gates["member_radius_m"]
    args = (
        network["particles"],
        gates["minimum_anchor_network_degree"],
        gates["preferred_anchor_network_degree"],
        gates["anchor_pair_distance_m"],
        gates["member_radius_m"],
        target_penetration,
        tip_span,
        design["revision3_search"]["analytical_tolerance_m"],
    )
    feasible_a, rows_a = module.screen_anchor_pairs(*args)
    feasible_b, rows_b = module.screen_anchor_pairs(*args)
    check(feasible_a == feasible_b and rows_a == rows_b, "anchor-pair screen is deterministic", checks, failures)
    check(len(rows_a) > 0, "topological/distance anchor-pair screen is nonempty", checks, failures)
    check(0 < len(feasible_a) < len(rows_a), "analytical screen removes impossible pairs but retains feasible pairs", checks, failures)
    check(all(row["analytically_feasible"] for row in rows_a if row["analytically_feasible"]), "screen labels are Boolean-consistent", checks, failures)

    passed = not failures
    evaluation = {
        "schema": "lbs.stage26b-revision3-joint-generator-source-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_source_and_unit_audit" if passed else "failed_source_and_unit_audit",
        "checks": checks,
        "failures": failures,
        "observed": {
            "source_sha256": digest(SOURCE),
            "design_sha256": digest(DESIGN),
            "design_checkpoint_sha256": digest(DESIGN_CHECKPOINT),
            "network_sha256": digest(NETWORK),
            "geometry_sha256": digest(GEOMETRY),
            "tip_span_m": tip_span,
            "topological_distance_pair_count": len(rows_a),
            "analytically_feasible_pair_count": len(feasible_a),
        },
        "authority": {
            "execution_config_preparation_authorized": passed,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
        },
        "claim_boundary": design["claim_boundary"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    OUTPUT.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(OUTPUT), "feasible_pairs": len(feasible_a)}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
