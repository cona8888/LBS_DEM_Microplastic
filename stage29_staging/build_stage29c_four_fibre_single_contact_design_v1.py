from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29c_four_fibre_single_contact_qualification_20260825"
OUT = ROOT / "stage29_designs" / STUDY / "design_01"
SOURCES = {
    "contract": ROOT / "stage29_staging" / "STAGE29C_FOUR_FIBRE_SINGLE_CONTACT_DESIGN_CONTRACT.md",
    "stage29b_failure": ROOT / "stage29_designs" / "stage29b_four_fibre_mechanics_qualification_20260825" / "candidate_geometry_01" / "failure.json",
    "stage29b_design_audit": ROOT / "stage29_evaluations" / "stage29b_four_fibre_mechanics_qualification_20260825" / "design_audit_01" / "design_audit.json",
    "stage28a_mechanics_evaluation": ROOT / "stage28_evaluations" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_evaluation_02" / "evaluation.json",
    "stage28a_revision2_runner": ROOT / "stage28_designs" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_revision2_runner_01" / "run_stage28a_two_fibre_mechanics_v2.py",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canon(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    missing = [str(p) for p in SOURCES.values() if not p.is_file()]
    if missing:
        raise RuntimeError("missing sources: " + "; ".join(missing))
    cases = []
    for block, seed in zip("ABC", (2026082921, 2026082922, 2026082923)):
        for topology, intended in (("zero_contact", []), ("one_contact", [[1, 2]])):
            cases.append({
                "case_id": f"s29c_f004_{topology}_{block}",
                "placement_block": block,
                "candidate_seed": seed,
                "fibre_count": 4,
                "nodes_per_fibre": 37,
                "topology_regime": topology,
                "intended_terminal_contact_edges": intended,
                "all_other_edges_must_be_separated": True,
                "topology_must_be_measured": True,
                "sand_and_cell_fixed_exactly": True,
                "execution_status": "not_authorized",
            })
    design = {
        "schema": "lbs.stage29c-four-fibre-single-contact-qualification.v1",
        "study_id": STUDY,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "revised_design_not_authorized_for_geometry_or_execution",
        "revision_reason": "Stage29b supplied only one two-disjoint-contact candidate; Stage29c uses the minimal zero-versus-one-contact graph expected to support three source-distinct blocks.",
        "cases": cases,
        "case_matrix_sha256": canon(cases),
        "hard_gates": {
            "path_match_rms_over_fibre_diameter_max": 0.05,
            "penetration_over_fibre_radius_max": 0.02,
            "false_same_fibre_contacts": 0,
            "cross_node_bonds": 0,
            "fixed_sand_and_cell_exact": True,
            "hold_exactly_stable": True,
            "zero_contact_edges": 0,
            "one_contact_edges": 1,
            "all_noncontact_pairs_minimum_centreline_distance_fibre_radii": 4.0,
        },
        "interpretation": "An incremental fibre-fibre contact mechanism at fixed four-fibre concentration; not a population-level contact-frequency model.",
        "authority": {
            "design_generation": True,
            "design_audit": True,
            "candidate_geometry_generation": False,
            "geometry_acceptance": False,
            "runner_construction": False,
            "yade_execution": False,
            "gpu_flow": False,
        },
        "source_paths": {k: str(v) for k, v in SOURCES.items()},
        "source_hashes": {k: sha(v) for k, v in SOURCES.items()},
    }
    OUT.mkdir(parents=True)
    p = OUT / "design_manifest.json"
    p.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {
        "schema": design["schema"] + ".completion",
        "passed": True,
        "status": "passed_revised_design_generation_geometry_not_authorized",
        "design_manifest_sha256": sha(p),
        "next_handoff": "independent revised-design audit only",
    }
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **completion}, indent=2))


if __name__ == "__main__":
    main()
