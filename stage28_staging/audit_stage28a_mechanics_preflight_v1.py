#!/usr/bin/env python3
"""Independently audit and release the Stage28a six-case YADE mechanics batch."""

from __future__ import annotations

import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
PREFLIGHT = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_01"
CONFIG = PREFLIGHT / "config.json"
COMPLETION = PREFLIGHT / "completion.json"
DESIGN = ROOT / "stage28_staging/stage28a_two_fibre_design_v2.json"
CANDIDATE = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/candidate_geometry_01/candidate_geometry.json"
STAGE26_RESULT = ROOT / "stage26_runs/stage26x_periodic_pore_geometry_20260823/fixed_sand_pilot_02/result.json"
UNIT_RESULT = ROOT / "stage28_tests/stage28a_yade_grid_grid_contact_20260824/unit_01/result.json"
RUNNER = ROOT / "stage28_staging/run_stage28a_two_fibre_mechanics_v1.py"
MECHANICS_OUTPUT = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_01"
OUTPUT = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/execution_audit_01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def host_path(value: str) -> Path:
    if value.startswith("/mnt/c/"):
        return Path("C:\\" + value[len("/mnt/c/"):].replace("/", "\\"))
    return Path(value)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    config = load(CONFIG)
    completion = load(COMPLETION)
    design = load(DESIGN)
    candidate = load(CANDIDATE)
    stage26 = load(STAGE26_RESULT)
    unit = load(UNIT_RESULT)

    source_checks = {}
    for name, binding in config["sources"].items():
        if name == "expected_yade_version":
            continue
        path = host_path(binding["path"])
        source_checks[name] = path.is_file() and digest(path) == binding["sha256"]

    py_compile.compile(str(RUNNER), doraise=True)
    runner_text = RUNNER.read_text(encoding="utf-8")
    required_runner_tokens = (
        "Ig2_GridConnection_GridConnection_GridCoGridCoGeom",
        "Law2_GridCoGridCoGeom_FrictPhys_CundallStrack",
        'os.environ["STAGE28A_CONFIG"]',
        'os.environ["STAGE28A_HANDOFF"]',
        'os.environ["STAGE28A_OUTPUT"]',
        "maximum_aligned_terminal_centreline_rms_over_fibre_diameter",
        "cross_fibre_node_real_interaction_count",
        "fibre_fibre_contact_count",
    )

    execution = config["execution_cases"]
    expected_order = [
        "isolated_face_14848",
        "isolated_face_30311",
        "isolated_face_30924",
        "separated_open_open",
        "separated_open_constricted",
        "crossing_interaction",
    ]
    paired = {row["case_id"]: row for row in candidate["cases"]}
    actual_paired = {row["case_id"]: row for row in execution if len(row["fibres"]) == 2}
    paired_exact = all(
        name in actual_paired and canonical(actual_paired[name]) == canonical(paired[name])
        for name in design["paired_cases"]
    )

    candidate_fibres = {}
    for row in candidate["cases"]:
        for fibre in row["fibres"]:
            candidate_fibres[int(fibre["source_face_index"])] = fibre
    isolated_exact = True
    for row in execution[:3]:
        fibre = dict(row["fibres"][0])
        face = int(fibre["source_face_index"])
        expected = dict(candidate_fibres[face])
        fibre.pop("fibre_id", None)
        expected.pop("fibre_id", None)
        isolated_exact &= canonical(fibre) == canonical(expected)

    stage26_cases = {row["case_id"]: row for row in stage26["cases"]}
    controls = config["accepted_isolated_controls"]
    controls_exact = (
        canonical(controls["37641"]["terminal_node_positions_m"])
        == canonical(stage26_cases["open"]["terminal_node_positions_m"])
        and canonical(controls["37527"]["terminal_node_positions_m"])
        == canonical(stage26_cases["constricted"]["terminal_node_positions_m"])
    )

    authority = config["authority"]
    checks = {
        "preflight_status_fail_closed": config["status"]
        == "stage28a_two_fibre_mechanics_preflight_independent_release_required",
        "preflight_authority_fail_closed": authority["mechanics_execution_authorized"] is False
        and authority["gpu_execution_authorized"] is False
        and authority["mobile_sand_authorized"] is False
        and authority["two_way_coupling_authorized"] is False,
        "all_preflight_checks_passed": all(config["checks"].values()),
        "completion_passed_and_bound": completion["passed"] is True
        and completion["config"]["sha256"] == digest(CONFIG),
        "all_source_hashes_match": all(source_checks.values()),
        "runner_compiles": True,
        "runner_has_required_fail_closed_contact_logic": all(
            token in runner_text for token in required_runner_tokens
        ),
        "exact_six_case_order": [row["case_id"] for row in execution] == expected_order,
        "three_isolated_then_three_paired": [len(row["fibres"]) for row in execution]
        == [1, 1, 1, 2, 2, 2],
        "revision2_isolated_faces_exact": [
            int(row["fibres"][0]["source_face_index"]) for row in execution[:3]
        ]
        == design["new_isolated_path_controls"],
        "isolated_geometries_exact": isolated_exact,
        "paired_geometries_exact": paired_exact,
        "accepted_stage26_controls_exact": controls_exact,
        "contact_api_unit_evidence_passed": unit["passed"] is True
        and unit["environment"]["yade_version"] == config["sources"]["expected_yade_version"]
        and all(unit["checks"].values()),
        "acceptance_matches_revision2": config["acceptance"][
            "maximum_aligned_terminal_centreline_rms_over_fibre_diameter"
        ]
        == design["path_match_acceptance"][
            "maximum_terminal_centreline_rms_over_fibre_diameter"
        ],
        "accepted_geometry_scale": config["acceptance"]["required_sand_particles"] == 216
        and config["acceptance"]["required_nodes_per_fibre"] == 37
        and config["acceptance"]["required_internal_bonds_per_fibre"] == 36,
        "mechanics_output_absent": not MECHANICS_OUTPUT.exists(),
    }
    passed = all(checks.values())
    if not passed:
        failed = [name for name, value in checks.items() if not value]
        raise RuntimeError("Stage28a mechanics execution audit failed: " + ", ".join(failed))

    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage28a-two-fibre-mechanics-execution-audit.v1",
        "status": "passed_stage28a_mechanics_execution_release",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "checks": checks,
        "source_checks": source_checks,
        "resource_assessment": {
            "case_count": 6,
            "maximum_fibres_per_case": 2,
            "maximum_fibre_nodes_per_case": 74,
            "sand_particles": 216,
            "execution_class": "small CPU YADE mechanics batch; no GPU allocation",
        },
        "claim_boundary": config["claim_boundary"],
        "bindings": {
            "config_sha256": digest(CONFIG),
            "completion_sha256": digest(COMPLETION),
            "runner_sha256": digest(RUNNER),
            "candidate_sha256": digest(CANDIDATE),
            "design_v2_sha256": digest(DESIGN),
            "unit_result_sha256": digest(UNIT_RESULT),
        },
        "next_handoff": {
            "authorized": "one immutable six-case Stage28a CPU YADE mechanics execution",
            "not_authorized": "GPU-LBM, mobile sand, production concentration study, or two-way coupling",
        },
    }
    audit_path = OUTPUT / "audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff = {
        "schema": "lbs.stage28a-two-fibre-mechanics-execution-handoff.v1",
        "status": "stage28a_mechanics_execution_authorized",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "authority": {
            "mechanics_execution": True,
            "gpu_execution": False,
            "mobile_sand": False,
            "production_concentration_campaign": False,
            "two_way_coupling": False,
        },
        "bindings": {
            "config_sha256": digest(CONFIG),
            "runner_sha256": digest(RUNNER),
            "audit_sha256": digest(audit_path),
        },
        "output": str(MECHANICS_OUTPUT),
    }
    handoff_path = OUTPUT / "execution_handoff.json"
    handoff_path.write_text(
        json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "passed": True,
        "audit": str(audit_path),
        "audit_sha256": digest(audit_path),
        "handoff": str(handoff_path),
        "handoff_sha256": digest(handoff_path),
        "checks": checks,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
