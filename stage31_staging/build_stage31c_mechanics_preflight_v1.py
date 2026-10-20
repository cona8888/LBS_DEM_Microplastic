#!/usr/bin/env python3
"""Freeze the fail-closed Stage31c six-block mechanics preflight."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage31c_replicated_nested_mechanics_20260826"
OUTPUT = ROOT / "stage31_designs" / STUDY / "mechanics_preflight_01"
DESIGN = ROOT / "stage31_designs/stage31b_nested_concentration_replication_20260826/design_01/design_manifest.json"
DESIGN_AUDIT = ROOT / "stage31_evaluations/stage31b_nested_concentration_replication_20260826/design_audit_01/design_audit.json"
RENDER_AUDIT = ROOT / "stage31_evaluations/stage31b_nested_concentration_replication_20260826/render_audit_02/render_audit.json"
PACKING_EVALUATION = ROOT / "stage31_evaluations/stage31a_packing_replication_bridge_20260826/mechanics_evaluation_01/evaluation.json"
PRIOR_CONFIG = ROOT / "stage29_designs/stage29d_shared_pair_context_qualification_20260825/mechanics_preflight_01/config.json"
PRIOR_EVALUATION = ROOT / "stage29_evaluations/stage29d_shared_pair_context_qualification_20260825/mechanics_evaluation_01/evaluation.json"
RUNNER = ROOT / "stage31_staging/run_stage31c_replicated_nested_mechanics_v1.py"
CONTRACT = ROOT / "stage31_staging/STAGE31C_REPLICATED_NESTED_MECHANICS_CONTRACT.md"

STATE_PATHS = {
    "n216_s1": ROOT / "stage25_runs/stage25a_pure_sand_mechanics_20260813/qualification_04/mu_0.60/load_bearing_state.yade.gz",
    "n216_s2": ROOT / "stage31_runs/stage31a_packing_replication_bridge_20260826/n216_s2_qualification_01/mu_0.60/load_bearing_state.yade.gz",
    "n216_s3": ROOT / "stage31_runs/stage31a_packing_replication_bridge_20260826/n216_s3_qualification_01/mu_0.60/load_bearing_state.yade.gz",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wsl(path: Path) -> str:
    return "/mnt/c/" + str(path.resolve()).replace("C:\\", "").replace("\\", "/")


def binding(path: Path) -> dict:
    return {"path": wsl(path), "sha256": sha(path)}


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable preflight: {OUTPUT}")
    required = [DESIGN, DESIGN_AUDIT, RENDER_AUDIT, PACKING_EVALUATION, PRIOR_CONFIG, PRIOR_EVALUATION, RUNNER, CONTRACT, *STATE_PATHS.values()]
    if any(not path.is_file() for path in required):
        raise RuntimeError("required frozen source is missing")
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    design_audit = json.loads(DESIGN_AUDIT.read_text(encoding="utf-8"))
    render_audit = json.loads(RENDER_AUDIT.read_text(encoding="utf-8"))
    packing_evaluation = json.loads(PACKING_EVALUATION.read_text(encoding="utf-8"))
    prior_config = json.loads(PRIOR_CONFIG.read_text(encoding="utf-8"))
    prior_evaluation = json.loads(PRIOR_EVALUATION.read_text(encoding="utf-8"))
    if not all(item.get("passed") is True for item in (design_audit, render_audit, packing_evaluation, prior_evaluation)):
        raise RuntimeError("one or more prerequisites did not pass")
    expected_state_hashes = {item["packing_id"]: item["checkpoint_sha256"] for item in packing_evaluation["cases"]}
    if any(sha(path) != expected_state_hashes[packing_id] for packing_id, path in STATE_PATHS.items()):
        raise RuntimeError("packing checkpoint does not match Stage31a evaluation")
    execution_cases = []
    for packing_id in ("n216_s1", "n216_s2", "n216_s3"):
        for placement_block in ("A", "B"):
            fibres = []
            for source in design["blocks"][packing_id][placement_block]:
                fibres.append(
                    {
                        "fibre_id": f"{packing_id}_{placement_block}_f{source['nested_rank']}",
                        "nested_rank": int(source["nested_rank"]),
                        "source_face_index": int(source["face_index"]),
                        "source_face_body_ids": [int(value) for value in source["face_body_ids"]],
                        "rear_m": source["rear_m"],
                        "tip_m": source["tip_m"],
                        "pull_direction": source["pull_direction"],
                        "initial_minimum_surface_clearance_m": source["initial_minimum_surface_clearance_m"],
                    }
                )
            execution_cases.append(
                {
                    "case_id": f"s31c_{packing_id}_{placement_block}_f004_open",
                    "packing_id": packing_id,
                    "placement_block": placement_block,
                    "source_state": binding(STATE_PATHS[packing_id]),
                    "fibres": fibres,
                }
            )
    sources = {
        "builder": binding(Path(__file__).resolve()),
        "runner": binding(RUNNER),
        "contract": binding(CONTRACT),
        "stage31b_design": binding(DESIGN),
        "stage31b_design_audit": binding(DESIGN_AUDIT),
        "stage31b_render_audit": binding(RENDER_AUDIT),
        "stage31a_packing_evaluation": binding(PACKING_EVALUATION),
        "accepted_stage29d_config": binding(PRIOR_CONFIG),
        "accepted_stage29d_evaluation": binding(PRIOR_EVALUATION),
        "n216_s1_state": binding(STATE_PATHS["n216_s1"]),
        "n216_s2_state": binding(STATE_PATHS["n216_s2"]),
        "n216_s3_state": binding(STATE_PATHS["n216_s3"]),
        "expected_yade_version": prior_config["sources"]["expected_yade_version"],
    }
    config = {
        "schema": "lbs.stage31c-replicated-nested-mechanics-preflight.v1",
        "status": "stage31c_replicated_nested_mechanics_preflight_release_required",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": "Do all six packing-by-placement blocks remain mechanically valid under the accepted fixed-sand F37 pull protocol?",
        "execution_cases": execution_cases,
        "mechanics": prior_config["mechanics"],
        "acceptance": {
            "required_case_count": 6,
            "required_sand_particles": 216,
            "required_nodes_per_fibre": 37,
            "required_internal_bonds_per_fibre": 36,
            "maximum_hold_drift_m": prior_config["acceptance"]["maximum_hold_drift_m"],
            "maximum_hold_speed_m_s": prior_config["acceptance"]["maximum_hold_speed_m_s"],
            "maximum_cell_dimension_change_m": prior_config["acceptance"]["maximum_cell_dimension_change_m"],
            "maximum_penetration_over_fibre_radius": prior_config["acceptance"]["maximum_penetration_over_fibre_radius"],
            "maximum_fibre_fibre_contacts": 0,
            "maximum_cross_fibre_node_interactions": 0,
            "maximum_intrafibre_grid_contacts": 0,
            "minimum_initial_interfibre_surface_clearance_m": design_audit["metrics"]["minimum_interfibre_surface_clearance_m"],
        },
        "checks": {
            "exact_six_cases": len(execution_cases) == 6,
            "three_packings_two_blocks": {(case["packing_id"], case["placement_block"]) for case in execution_cases} == {(packing, block) for packing in STATE_PATHS for block in ("A", "B")},
            "four_fibres_each": all(len(case["fibres"]) == 4 for case in execution_cases),
            "nested_ranks_exact": all([fibre["nested_rank"] for fibre in case["fibres"]] == [1, 2, 3, 4] for case in execution_cases),
            "design_audit_passed": design_audit["passed"],
            "visual_audit_passed": render_audit["passed"],
            "three_packings_qualified": packing_evaluation["passed"],
            "accepted_mechanics_bound": prior_evaluation["passed"],
        },
        "sources": sources,
        "authority": {"mechanics_execution": False, "gpu_flow": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
        "claim_boundary": "Six fixed-sand four-fibre mechanics blocks only. Successful mechanics may support terminal 1/2/4 nested geometry construction but does not authorize flow, permeability claims, mobile sand, migration, clogging, deformation, or coupling.",
    }
    if not all(config["checks"].values()):
        raise RuntimeError("mechanics preflight construction check failed")
    OUTPUT.mkdir(parents=True)
    config_path = OUTPUT / "config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    completion = {
        "schema": config["schema"] + ".completion",
        "passed": True,
        "status": config["status"],
        "config_sha256": sha(config_path),
        "runner_sha256": sha(RUNNER),
        "next_handoff": {"authorized": "independent mechanics release audit", "not_authorized": "YADE execution or flow"},
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), **completion}, indent=2))


if __name__ == "__main__":
    main()
