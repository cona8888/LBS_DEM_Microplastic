from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29b_four_fibre_mechanics_qualification_20260825"
OUT = ROOT / "stage29_designs" / STUDY / "design_01"
SOURCES = {
    "contract": ROOT / "stage29_staging" / "STAGE29B_FOUR_FIBRE_MECHANICS_QUALIFICATION_CONTRACT.md",
    "stage29a_design_audit": ROOT / "stage29_evaluations" / "stage29a_mechanics_aware_concentration_design_20260825" / "design_audit_01" / "design_audit.json",
    "stage29a_checkpoint": ROOT / "stage29_evaluations" / "stage29a_mechanics_aware_concentration_design_20260825" / "design_audit_01" / "checkpoint_manifest.json",
    "stage28a_mechanics_evaluation": ROOT / "stage28_evaluations" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_evaluation_02" / "evaluation.json",
    "stage28a_revision2_config": ROOT / "stage28_designs" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_preflight_02" / "config.json",
    "stage28a_revision2_runner": ROOT / "stage28_designs" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_revision2_runner_01" / "run_stage28a_two_fibre_mechanics_v2.py",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    missing = [str(p) for p in SOURCES.values() if not p.is_file()]
    if missing:
        raise SystemExit("Missing source(s): " + "; ".join(missing))
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite immutable output: {OUT}")
    cases = []
    block_seeds = {"A": 2026082911, "B": 2026082912, "C": 2026082913}
    for block in "ABC":
        for topology, intended in (("low_contact", []), ("contact_rich", [[1, 2], [3, 4]])):
            cases.append({
                "case_id": f"s29b_f004_{topology}_{block}",
                "placement_block": block,
                "candidate_seed": block_seeds[block],
                "topology_regime": topology,
                "fibre_count": 4,
                "nodes_per_fibre": 37,
                "intended_terminal_contact_edges": intended,
                "forbidden_terminal_contact_edges": (
                    [[1, 2], [1, 3], [1, 4], [2, 3], [2, 4], [3, 4]] if topology == "low_contact"
                    else [[1, 3], [1, 4], [2, 3], [2, 4]]
                ),
                "topology_must_be_measured": True,
                "sand_and_cell_fixed_exactly": True,
                "execution_status": "not_authorized",
            })
    design = {
        "schema": "lbs.stage29b-four-fibre-mechanics-qualification.v1",
        "study_id": STUDY,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "designed_not_authorized_for_geometry_or_execution",
        "cases": cases,
        "case_count": 6,
        "matched_blocks": ["A", "B", "C"],
        "construction": {
            "source_path_family": "accepted Stage28a revision-2 two-fibre mechanics paths",
            "periodic_clearance_metric": "minimum-image segment/point distances",
            "candidate_policy": "generate, screen, and audit in a new immutable directory",
            "paired_matching_metrics": [
                "per-fibre contour length exact",
                "per-fibre orientation target exact",
                "block centroid-distribution mismatch",
                "minimum sand clearance",
                "unintended inter-fibre clearance",
            ],
        },
        "hard_gates": {
            "path_match_rms_over_fibre_diameter_max": 0.05,
            "penetration_over_fibre_radius_max": 0.02,
            "false_same_fibre_contacts": 0,
            "cross_node_bonds": 0,
            "intrafibre_bonds_complete": True,
            "fixed_sand_and_cell_exact": True,
            "hold_exactly_stable": True,
            "low_contact_terminal_edges": 0,
            "contact_rich_terminal_edges": 2,
            "contact_rich_graph": "two_disjoint_edges",
        },
        "failure_policy": "preserve failure evidence; do not relabel topology, relax gates, rerun, or proceed to flow without a new audited revision",
        "authority": {
            "design_generation": True,
            "design_audit": True,
            "candidate_geometry_generation": False,
            "geometry_acceptance": False,
            "runner_construction": False,
            "yade_execution": False,
            "gpu_flow": False,
            "permeability_claim": False,
            "new_physics": False,
        },
        "source_paths": {k: str(v) for k, v in SOURCES.items()},
        "source_hashes": {k: sha256(v) for k, v in SOURCES.items()},
    }
    design["case_matrix_sha256"] = canonical_sha(cases)
    OUT.mkdir(parents=True)
    p = OUT / "design_manifest.json"
    p.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {
        "schema": "lbs.stage29b-four-fibre-mechanics-qualification.v1.completion",
        "passed": True,
        "status": "passed_design_generation_geometry_and_execution_not_authorized",
        "design_manifest_sha256": sha256(p),
        "next_handoff": "independent design audit only",
    }
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **completion}, indent=2))


if __name__ == "__main__":
    main()
