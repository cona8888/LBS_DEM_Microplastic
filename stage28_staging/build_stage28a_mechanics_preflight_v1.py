#!/usr/bin/env python3
"""Build the fail-closed Stage28a six-case mechanics execution preflight."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN_V2 = ROOT / "stage28_staging/stage28a_two_fibre_design_v2.json"
REVISION = ROOT / "stage28_staging/STAGE28A_REVISION2_ISOLATED_PATH_CONTROLS.md"
CANDIDATE = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/candidate_geometry_01/candidate_geometry.json"
CANDIDATE_COMPLETION = CANDIDATE.parent / "completion.json"
STAGE26_CONFIG = ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/fixed_sand_design_02/config.json"
STAGE26_RESULT = ROOT / "stage26_runs/stage26x_periodic_pore_geometry_20260823/fixed_sand_pilot_02/result.json"
STAGE26_OPEN = STAGE26_RESULT.parent / "open_result.json"
STAGE26_CONSTRICTED = STAGE26_RESULT.parent / "constricted_result.json"
UNIT_RESULT = ROOT / "stage28_tests/stage28a_yade_grid_grid_contact_20260824/unit_01/result.json"
GEOMETRY_TEST = ROOT / "stage28_staging/test_stage28a_geometry_math_v1.py"
RUNNER = ROOT / "stage28_staging/run_stage28a_two_fibre_mechanics_v1.py"
OUTPUT = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def wsl(path: Path) -> str:
    return str(path).replace("C:\\", "/mnt/c/").replace("\\", "/")


def binding(path: Path) -> dict:
    return {"path": wsl(path), "sha256": digest(path)}


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    design = load(DESIGN_V2)
    candidate = load(CANDIDATE)
    candidate_completion = load(CANDIDATE_COMPLETION)
    stage26_config = load(STAGE26_CONFIG)
    stage26_result = load(STAGE26_RESULT)
    unit = load(UNIT_RESULT)
    if not (candidate.get("passed") and candidate_completion.get("passed") and unit.get("passed")):
        raise RuntimeError("candidate or unit-test evidence is not accepted")

    paired_cases = {case["case_id"]: case for case in candidate["cases"]}
    fibres_by_face = {}
    for case in candidate["cases"]:
        for fibre in case["fibres"]:
            fibres_by_face[int(fibre["source_face_index"])] = dict(fibre)
    new_faces = [int(value) for value in design["new_isolated_path_controls"]]
    if not all(face in fibres_by_face for face in new_faces):
        raise RuntimeError("a Revision-2 isolated path is missing from the candidates")
    isolated_cases = []
    for face in new_faces:
        fibre = dict(fibres_by_face[face])
        fibre["fibre_id"] = "fibre_1"
        isolated_cases.append(
            {
                "case_id": f"isolated_face_{face}",
                "role": "new_path_isolated_control",
                "fibres": [fibre],
            }
        )

    stage26_by_id = {case["case_id"]: case for case in stage26_result["cases"]}
    accepted_controls = {
        "37641": {
            "archetype": "open",
            "terminal_node_positions_m": stage26_by_id["open"]["terminal_node_positions_m"],
            "result": binding(STAGE26_OPEN),
        },
        "37527": {
            "archetype": "constricted",
            "terminal_node_positions_m": stage26_by_id["constricted"]["terminal_node_positions_m"],
            "result": binding(STAGE26_CONSTRICTED),
        },
    }
    execution_cases = isolated_cases + [
        paired_cases[name]
        for name in (
            "separated_open_open",
            "separated_open_constricted",
            "crossing_interaction",
        )
    ]
    acceptance = {
        "required_sand_particles": 216,
        "required_nodes_per_fibre": 37,
        "required_internal_bonds_per_fibre": 36,
        "maximum_cell_dimension_change_m": 0.0,
        "maximum_fixed_sand_displacement_m": 0.0,
        "maximum_penetration_over_fibre_radius": 0.01,
        "minimum_crossing_fibre_fibre_contacts": 1,
        "maximum_aligned_terminal_centreline_rms_over_fibre_diameter": 0.05,
        "maximum_hold_drift_m": 1.0e-6,
        "maximum_hold_speed_m_s": 1.0e-6,
    }
    checks = {
        "exact_six_cases": len(execution_cases) == 6,
        "exact_three_isolated": len(isolated_cases) == 3,
        "exact_three_paired": len(paired_cases) == 3,
        "unique_case_ids": len({case["case_id"] for case in execution_cases}) == 6,
        "new_isolated_faces_bound": {
            int(case["fibres"][0]["source_face_index"]) for case in isolated_cases
        }
        == set(new_faces),
        "accepted_controls_bound": set(accepted_controls) == {"37527", "37641"},
        "all_candidate_checks": all(candidate["checks"].values()),
        "grid_contact_unit_passed": unit["passed"]
        and all(unit["checks"].values())
        and unit["environment"]["yade_version"] == "2022.01a",
        "stage26_source_passed": stage26_result["passed"],
    }
    if not all(checks.values()):
        raise RuntimeError("mechanics preflight construction checks failed")

    sources = {
        "expected_yade_version": "2022.01a",
        "source_state": stage26_config["sources"]["source_state"],
        "design_v2": binding(DESIGN_V2),
        "revision2_contract": binding(REVISION),
        "candidate_geometry": binding(CANDIDATE),
        "candidate_completion": binding(CANDIDATE_COMPLETION),
        "stage26_config": binding(STAGE26_CONFIG),
        "stage26_result": binding(STAGE26_RESULT),
        "stage26_open_control": binding(STAGE26_OPEN),
        "stage26_constricted_control": binding(STAGE26_CONSTRICTED),
        "grid_contact_unit": binding(UNIT_RESULT),
        "geometry_unit_test": binding(GEOMETRY_TEST),
        "runner": binding(RUNNER),
        "builder": binding(Path(__file__).resolve()),
    }
    config = {
        "schema": "lbs.stage28a-two-fibre-mechanics-preflight.v1",
        "status": "stage28a_two_fibre_mechanics_preflight_independent_release_required",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": design["research_question"],
        "claim_boundary": design["claim_boundary"],
        "cell_dimensions_m": candidate["cell_dimensions_m"],
        "mechanics": candidate["mechanics"],
        "acceptance": acceptance,
        "accepted_isolated_controls": accepted_controls,
        "execution_cases": execution_cases,
        "checks": checks,
        "sources": sources,
        "authority": {
            "independent_execution_audit": True,
            "mechanics_execution_authorized": False,
            "gpu_execution_authorized": False,
            "production_concentration_campaign_authorized": False,
            "mobile_sand_authorized": False,
            "two_way_coupling_authorized": False,
        },
    }
    OUTPUT.mkdir(parents=True)
    config_path = OUTPUT / "config.json"
    config_path.write_text(
        json.dumps(config, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    completion = {
        "schema": config["schema"] + ".completion",
        "status": config["status"],
        "passed": True,
        "checks": checks,
        "config": {"path": str(config_path), "sha256": digest(config_path)},
        "next_handoff": {
            "authorized": "independent source, API, placement and authority audit",
            "not_authorized": "YADE mechanics execution or GPU-LBM execution",
        },
    }
    completion_path = OUTPUT / "completion.json"
    completion_path.write_text(
        json.dumps(completion, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "config": str(config_path),
                "config_sha256": digest(config_path),
                "completion": str(completion_path),
                "completion_sha256": digest(completion_path),
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
