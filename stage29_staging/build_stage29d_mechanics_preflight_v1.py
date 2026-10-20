from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29d_shared_pair_context_qualification_20260825"
OUT = ROOT / "stage29_designs" / STUDY / "mechanics_preflight_01"
CANDIDATE = ROOT / "stage29_designs" / STUDY / "candidate_geometry_01" / "candidate_geometry.json"
CANDIDATE_COMPLETION = ROOT / "stage29_designs" / STUDY / "candidate_geometry_01" / "completion.json"
GEOMETRY_AUDIT = ROOT / "stage29_evaluations" / STUDY / "candidate_geometry_audit_01" / "geometry_audit.json"
GEOMETRY_CHECKPOINT = ROOT / "stage29_evaluations" / STUDY / "candidate_geometry_audit_01" / "checkpoint_manifest.json"
DESIGN = ROOT / "stage29_designs" / STUDY / "design_01" / "design_manifest.json"
DESIGN_AUDIT = ROOT / "stage29_evaluations" / STUDY / "design_audit_01" / "design_audit.json"
RUNNER = ROOT / "stage29_designs" / STUDY / "mechanics_runner_01" / "run_stage29d_four_fibre_mechanics_v1.py"
UNIT = ROOT / "stage29_tests" / "stage29d_yade_four_fibre_groupmask_20260826" / "unit_01" / "result.json"
STAGE28_CONFIG = ROOT / "stage28_designs" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_preflight_02" / "config.json"
STAGE28_EVALUATION = ROOT / "stage28_evaluations" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_evaluation_02" / "evaluation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wsl(path: Path) -> str:
    return "/mnt/c/" + str(path).replace("C:\\", "").replace("\\", "/")


def binding(path: Path) -> dict:
    return {"path": wsl(path), "sha256": sha(path)}


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    required = [CANDIDATE, CANDIDATE_COMPLETION, GEOMETRY_AUDIT, GEOMETRY_CHECKPOINT, DESIGN, DESIGN_AUDIT, RUNNER, UNIT, STAGE28_CONFIG, STAGE28_EVALUATION]
    if any(not p.is_file() for p in required):
        raise RuntimeError("required frozen source missing")
    candidate = json.loads(CANDIDATE.read_text())
    geometry_audit = json.loads(GEOMETRY_AUDIT.read_text())
    unit = json.loads(UNIT.read_text())
    prior = json.loads(STAGE28_CONFIG.read_text())
    prior_eval = json.loads(STAGE28_EVALUATION.read_text())
    if not (candidate.get("passed") and geometry_audit.get("passed") and unit.get("passed") and prior_eval.get("passed")):
        raise RuntimeError("one or more prerequisite evaluations failed")
    if unit["environment"]["yade_version"] != prior["sources"]["expected_yade_version"]:
        raise RuntimeError("YADE version mismatch")
    sources = {
        "builder": binding(Path(__file__).resolve()),
        "runner": binding(RUNNER),
        "candidate_geometry": binding(CANDIDATE),
        "candidate_completion": binding(CANDIDATE_COMPLETION),
        "geometry_audit": binding(GEOMETRY_AUDIT),
        "geometry_checkpoint": binding(GEOMETRY_CHECKPOINT),
        "design": binding(DESIGN),
        "design_audit": binding(DESIGN_AUDIT),
        "four_fibre_groupmask_unit": binding(UNIT),
        "stage28_revision2_config": binding(STAGE28_CONFIG),
        "stage28_revision2_evaluation": binding(STAGE28_EVALUATION),
        "source_state": prior["sources"]["source_state"],
        "expected_yade_version": prior["sources"]["expected_yade_version"],
    }
    config = {
        "schema": "lbs.stage29d-four-fibre-mechanics-preflight.v1",
        "status": "stage29d_four_fibre_mechanics_preflight_independent_release_required",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": "Does the accepted shared crossing-pair mechanism remain mechanically valid when embedded with three distinct non-contacting two-fibre contexts?",
        "cell_dimensions_m": candidate["cell_dimensions_m"],
        "execution_cases": candidate["cases"],
        "mechanics": prior["mechanics"],
        "acceptance": {
            "required_sand_particles": 216,
            "required_nodes_per_fibre": 37,
            "required_internal_bonds_per_fibre": 36,
            "maximum_hold_drift_m": prior["acceptance"]["maximum_hold_drift_m"],
            "maximum_hold_speed_m_s": prior["acceptance"]["maximum_hold_speed_m_s"],
            "maximum_cell_dimension_change_m": prior["acceptance"]["maximum_cell_dimension_change_m"],
            "maximum_penetration_over_fibre_radius": prior["acceptance"]["maximum_penetration_over_fibre_radius"],
            "maximum_context_aligned_terminal_rms_over_fibre_diameter": prior["acceptance"]["maximum_aligned_terminal_centreline_rms_over_fibre_diameter"],
            "terminal_contact_graphs_exact": True,
            "unintended_contact_edges_ever": 0,
        },
        "checks": {
            "exact_six_cases": len(candidate["cases"]) == 6,
            "all_four_fibres": all(len(case["fibres"]) == 4 for case in candidate["cases"]),
            "three_context_blocks": all(len([case for case in candidate["cases"] if case["context_block"] == block]) == 2 for block in "ABC"),
            "geometry_audit_passed": geometry_audit["passed"],
            "four_fibre_groupmask_unit_passed": unit["passed"],
            "accepted_stage28_revision2_bound": prior_eval["passed"],
        },
        "sources": sources,
        "authority": {"mechanics_execution": False, "gpu_flow": False, "permeability_claim": False, "mobile_sand": False, "two_way_coupling": False},
        "claim_boundary": "Four-fibre fixed-sand mechanics mechanism pilot with one shared crossing pair, one shared separated pair, and three context blocks. Context blocks are not independent crossing-location replicates. No permeability, mixing, migration, clogging, deformation, or coupling claim.",
    }
    if not all(config["checks"].values()):
        raise RuntimeError("preflight construction checks failed")
    OUT.mkdir(parents=True)
    p = OUT / "config.json"
    p.write_text(json.dumps(config, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    completion = {"schema": config["schema"] + ".completion", "passed": True, "status": config["status"], "config_sha256": sha(p), "runner_sha256": sha(RUNNER), "next_handoff": {"authorized": "independent mechanics release audit", "not_authorized": "YADE mechanics execution before release, GPU flow, or permeability claims"}}
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **completion}, indent=2))


if __name__ == "__main__":
    main()
