"""Independent non-YADE audit of the Revision-2 source bundle."""

import ast
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from stage26b_revision2_prefilter_common_v1 import (
    candidate_contact_pass,
    candidate_rank_key,
    iterative_core,
    sand_terminal_pass,
)


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
INTERFACE = PROJECT / "stage26_staging" / "stage26b_tier1_revision2_source_interface_v1.json"
COMMON = PROJECT / "stage26_staging" / "stage26b_revision2_prefilter_common_v1.py"
EXPORTER = PROJECT / "stage26_staging" / "export_stage26b_revision2_stage25_network_v1.py"
PREFILTER = PROJECT / "stage26_staging" / "run_stage26b_revision2_fixed_prefilter_v1.py"
SELECTOR = PROJECT / "stage26_staging" / "select_stage26b_revision2_prefilter_candidate_v1.py"
TESTS = PROJECT / "stage26_staging" / "test_stage26b_revision2_prefilter_common_v1.py"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "source_audit_02"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def o_calls(parsed):
    values = []
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "O":
                values.append(node.func.attr)
    return values


def blocked_dof_assignments(parsed):
    values = []
    for node in ast.walk(parsed):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr == "blockedDOFs":
                values.append(ast.literal_eval(node.value) if isinstance(node.value, ast.Constant) else None)
    return values


def pure_logic_checks():
    initial, core, active = iterative_core([1, 2, 3, 4], [(1, 2), (2, 3), (3, 1), (3, 4)], 2)
    graph_ok = initial == {1: 2, 2: 2, 3: 3, 4: 1} and core == {1: 2, 2: 2, 3: 2, 4: 0} and active == {1, 2, 3}
    contact_gates = {
        "minimum_distinct_sand_contacts_per_fibre_at_every_block": 2,
        "minimum_declared_anchor_contacts_per_fibre_at_every_block": 1,
        "required_declared_anchor_contacts_per_fibre_at_terminal_block": 2,
        "maximum_isolated_fibre_count": 0,
    }
    rows = [
        {"distinct_sand_contacts_by_fibre": [2, 2], "declared_anchor_contacts_by_fibre": [1, 1], "isolated_fibre_count": 0},
        {"distinct_sand_contacts_by_fibre": [2, 2], "declared_anchor_contacts_by_fibre": [2, 2], "isolated_fibre_count": 0},
    ]
    contact_ok = candidate_contact_pass(rows, contact_gates)
    bad_rows = [dict(rows[0]), dict(rows[1])]
    bad_rows[0]["declared_anchor_contacts_by_fibre"] = [0, 1]
    contact_fail_closed = not candidate_contact_pass(bad_rows, contact_gates)
    sand_gates = {
        "maximum_relative_mean_stress_error": 0.02,
        "maximum_principal_stress_error": 0.03,
        "maximum_unbalanced_force": 0.05,
        "minimum_sand_coordination_excluding_rattlers": 3.0,
        "maximum_sand_rattler_fraction": 0.35,
        "minimum_sand_contact_retention_fraction": 0.9,
        "maximum_sand_displacement_over_D50": 0.1,
        "maximum_cell_volume_relative_drift": 0.005,
        "maximum_interobject_penetration_over_smaller_radius": 0.02,
    }
    sand_row = {
        "relative_mean_stress_error": 0.01,
        "maximum_principal_stress_error": 0.02,
        "unbalanced_force": 0.04,
        "unbalanced_force_defined": True,
        "sand_coordination_excluding_degree_lt2_rattlers": 3.5,
        "sand_rattler_fraction_degree_lt2_iterative": 0.2,
        "sand_sand_contact_retention_fraction": 0.95,
        "maximum_nonaffine_sand_displacement_over_D50": 0.08,
        "cell_volume_relative_drift": 0.003,
        "maximum_interobject_penetration_over_smaller_radius": 0.01,
    }
    sand_ok = sand_terminal_pass(sand_row, sand_gates)
    sand_row["maximum_nonaffine_sand_displacement_over_D50"] = math.inf
    sand_nan_inf_fail_closed = not sand_terminal_pass(sand_row, sand_gates)
    rank_a = {
        "minimum_contacts_over_all_fibres_and_blocks": 2, "minimum_anchor_degree": 3,
        "maximum_sand_displacement_over_D50": 0.05, "maximum_force_residual_relative": 0.04,
        "maximum_moment_residual_relative": 0.01, "candidate_index": 2,
    }
    rank_b = dict(rank_a, candidate_index=1)
    rank_ok = candidate_rank_key(rank_b) < candidate_rank_key(rank_a)
    return graph_ok and contact_ok and contact_fail_closed and sand_ok and sand_nan_inf_fail_closed and rank_ok


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable source-audit output already exists")
    cfg = load_json(INTERFACE)
    design_checkpoint = load_json(Path(cfg["sources"]["design_checkpoint"]))
    source_files = [COMMON, EXPORTER, PREFILTER, SELECTOR, TESTS]
    compile_ok = True
    for path in source_files:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError:
            compile_ok = False
    checks = {}
    checks["interface_source_bindings"] = all(
        digest(Path(value)) == cfg["sources"][key + "_sha256"]
        for key, value in cfg["sources"].items()
        if not key.endswith("_sha256")
    )
    checks["design_checkpoint_authority"] = (
        design_checkpoint.get("passed") is True
        and design_checkpoint.get("status") == "frozen_revision2_design_no_physics_execution"
        and design_checkpoint["authority"]["network_export_execution_authorized"] is False
        and design_checkpoint["authority"]["prefilter_yade_execution_authorized"] is False
        and design_checkpoint["authority"]["two_fibre_free_release_authorized"] is False
    )
    checks["all_sources_compile"] = compile_ok
    exporter_calls = o_calls(tree(EXPORTER))
    checks["exporter_is_read_only"] = (
        exporter_calls.count("load") == 1
        and not any(name in exporter_calls for name in ("run", "step", "save", "saveTmp", "reset"))
    )
    prefilter_tree = tree(PREFILTER)
    prefilter_calls = o_calls(prefilter_tree)
    dof_values = blocked_dof_assignments(prefilter_tree)
    checks["prefilter_has_bounded_engine_path"] = (
        "load" in prefilter_calls and "step" in prefilter_calls and "run" in prefilter_calls
        and "save" not in prefilter_calls and "saveTmp" not in prefilter_calls
    )
    checks["prefilter_never_releases_fibres"] = dof_values == ["xyzXYZ"]
    prefilter_text = PREFILTER.read_text(encoding="utf-8")
    exporter_text = EXPORTER.read_text(encoding="utf-8")
    checks["yade_entrypoints_resolve_sibling_module"] = (
        "sys.path.insert(0, SCRIPT_DIRECTORY)" in exporter_text
        and "STAGE26B_R2_NETWORK_SCRIPT" in exporter_text
        and "sys.path.insert(0, SCRIPT_DIRECTORY)" in prefilter_text
        and "STAGE26B_R2_PREFILTER_SCRIPT" in prefilter_text
    )
    checks["prefilter_control_and_candidate_roles"] = all(
        marker in prefilter_text for marker in (
            "positive_stage26a", "negative_stage26b_failure", "candidate_contact_pass",
            "sand_terminal_pass", "candidate prefilter is blocked by control checkpoint",
        )
    )
    selector_text = SELECTOR.read_text(encoding="utf-8")
    checks["selector_requires_complete_frozen_schedule"] = (
        "len(trials) != 14" in selector_text
        and "positive_stage26a" in selector_text
        and "negative_stage26b_failure" in selector_text
        and "candidate_rank_key" in selector_text
        and "two_fibre_free_release_authorized\": False" in selector_text
    )
    checks["pure_logic_unit_checks"] = pure_logic_checks()
    forbidden_authority = [
        name for name, value in cfg["authority"].items()
        if name not in {"source_file_creation_authorized", "non_yade_unit_tests_authorized", "source_audit_authorized"} and value
    ]
    checks["source_only_authority"] = not forbidden_authority
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-tier1-revision2-source-audit.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_source_audit_without_yade_execution" if passed else "failed_source_audit",
        "checks": checks,
        "source_hashes": {
            "interface": digest(INTERFACE),
            "common": digest(COMMON),
            "network_exporter": digest(EXPORTER),
            "fixed_prefilter_runner": digest(PREFILTER),
            "selector": digest(SELECTOR),
            "unit_tests": digest(TESTS),
            "auditor": digest(Path(__file__)),
        },
        "interfaces": {
            "network_export_environment": ["STAGE26B_R2_NETWORK_CONFIG", "STAGE26B_R2_NETWORK_OUTPUT", "STAGE26B_R2_NETWORK_SCRIPT"],
            "prefilter_environment": ["STAGE26B_R2_PREFILTER_CONFIG", "STAGE26B_R2_TRIAL_ID", "STAGE26B_R2_PREFILTER_OUTPUT", "STAGE26B_R2_PREFILTER_SCRIPT"],
            "selector_arguments": ["--config", "--run-root", "--output"],
        },
        "authority": {
            "authorized_next_activity": "Prepare and independently audit the exact immutable Stage25 network-export execution configuration; do not execute YADE yet.",
            "network_export_execution_authorized": False,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(path)}, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
