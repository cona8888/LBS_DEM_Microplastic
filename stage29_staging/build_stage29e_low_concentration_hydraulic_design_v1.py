from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29e_low_concentration_hydraulic_design_20260826"
OUT = ROOT / "stage29_designs" / STUDY / "design_01"
CONTRACT = ROOT / "stage29_staging" / "STAGE29E_LOW_CONCENTRATION_HYDRAULIC_DESIGN_CONTRACT.md"
S28_RESULT = ROOT / "stage28_runs" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_02" / "result.json"
S28_EVAL = ROOT / "stage28_evaluations" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_evaluation_02" / "evaluation.json"
S29_RESULT = ROOT / "stage29_runs" / "stage29d_shared_pair_context_qualification_20260825" / "mechanics_01" / "result.json"
S29_EVAL = ROOT / "stage29_evaluations" / "stage29d_shared_pair_context_qualification_20260825" / "mechanics_evaluation_01" / "evaluation.json"
S29_CHECKPOINT = ROOT / "stage29_evaluations" / "stage29d_shared_pair_context_qualification_20260825" / "mechanics_evaluation_01" / "checkpoint_manifest.json"
S29_RENDER = ROOT / "stage29_renders" / "stage29d_shared_pair_context_qualification_20260825" / "mechanics_01" / "render_manifest.json"
SAND_MASS = 0.00015213021193865423
FIBRE_MASS = 7.136703508562081e-09


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canon(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def wt(n: int) -> float:
    return 100.0 * n * FIBRE_MASS / (SAND_MASS + n * FIBRE_MASS)


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    sources = {"contract": CONTRACT, "stage28_mechanics_result": S28_RESULT, "stage28_mechanics_evaluation": S28_EVAL, "stage29d_mechanics_result": S29_RESULT, "stage29d_mechanics_evaluation": S29_EVAL, "stage29d_checkpoint": S29_CHECKPOINT, "stage29d_render": S29_RENDER}
    if any(not p.is_file() for p in sources.values()):
        raise RuntimeError("frozen source missing")
    s28, e28 = json.loads(S28_RESULT.read_text()), json.loads(S28_EVAL.read_text())
    s29, e29 = json.loads(S29_RESULT.read_text()), json.loads(S29_EVAL.read_text())
    if not (s28.get("passed") and e28.get("passed") and s29.get("passed") and e29.get("passed") and e29["authority"]["revise_low_concentration_design"]):
        raise RuntimeError("mechanics evidence does not authorize design")
    cases28 = {x["case_id"]: x for x in s28["cases"]}
    cases29 = {x["case_id"]: x for x in s29["cases"]}
    cases = []
    for block, cid in zip("ABC", ("isolated_face_14848", "isolated_face_30311", "isolated_face_30924")):
        cases.append({"case_id": f"s29e_f001_isolated_{block}", "fibre_count": 1, "achieved_dry_mass_percent": wt(1), "topology": "single_isolated", "replicate_role": "independent_single_path", "block": block, "mechanics_source_study": "stage28a", "mechanics_source_case_id": cid, "mechanics_source_case_result_sha256": cases28[cid]["result_artifact"]["sha256"]})
    for topology, cid in (("separated", "separated_open_open"), ("crossing", "crossing_interaction")):
        cases.append({"case_id": f"s29e_f002_{topology}", "fibre_count": 2, "achieved_dry_mass_percent": wt(2), "topology": topology, "replicate_role": "unreplicated_mechanism_case", "block": "shared_pair", "mechanics_source_study": "stage28a", "mechanics_source_case_id": cid, "mechanics_source_case_result_sha256": cases28[cid]["result_artifact"]["sha256"]})
    for block in "ABC":
        for topology in ("zero_contact", "one_contact"):
            cid = f"s29d_f004_{topology}_context_{block}"
            cases.append({"case_id": f"s29e_f004_{topology}_context_{block}", "fibre_count": 4, "achieved_dry_mass_percent": wt(4), "topology": topology, "replicate_role": "paired_context_block_not_crossing_location_replication", "block": block, "mechanics_source_study": "stage29d", "mechanics_source_case_id": cid, "mechanics_source_case_result_sha256": cases29[cid]["result_artifact"]["sha256"]})
    order = [x["case_id"] for x in cases]
    random.Random(2026082699).shuffle(order)
    order_map = {cid: i + 1 for i, cid in enumerate(order)}
    for case in cases:
        case["frozen_cpd2_run_order"] = order_map[case["case_id"]]
    design = {
        "schema": "lbs.stage29e-low-concentration-hydraulic-design.v1",
        "study_id": STUDY,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "designed_hydraulic_geometry_not_authorized",
        "clean_control": {"reused": True, "case_id": "stage28c_clean_cpd4_positive_and_stage27b_clean_exact", "fibre_count": 0, "achieved_dry_mass_percent": 0.0},
        "new_case_count": len(cases),
        "total_with_reused_clean": len(cases) + 1,
        "cases": sorted(cases, key=lambda x: x["case_id"]),
        "case_matrix_sha256": canon(sorted(cases, key=lambda x: x["case_id"])),
        "concentration_mapping": [{"fibre_count": n, "achieved_dry_mass_percent": wt(n)} for n in (0, 1, 2, 4)],
        "analysis_plan": {"primary": "paired k_over_k0", "numerical_resolution_band": 0.0002, "monotonicity_gate": False, "comparisons": ["zero-contact concentration branch", "contact branch", "four-fibre paired topology contrast", "context variability"], "two_fibre_uncertainty": "not_estimable_from_one_case_per_topology"},
        "claim_boundary": "Fixed-packing static CPD2 low-concentration mechanism study in one 216-grain periodic LBS cell; excludes population inference, mixing, rearrangement, chemistry, migration, clogging, deformation, mobile sand, and coupling.",
        "authority": {"design_generation": True, "design_audit": True, "hydraulic_geometry_generation": False, "gpu_execution": False, "cpd4_execution": False, "permeability_claim": False, "mechanics_rerun": False, "mobile_sand": False, "two_way_coupling": False},
        "source_paths": {k: str(v) for k, v in sources.items()},
        "source_hashes": {k: sha(v) for k, v in sources.items()},
    }
    OUT.mkdir(parents=True)
    p = OUT / "design_manifest.json"
    p.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {"schema": design["schema"] + ".completion", "passed": True, "status": design["status"], "design_manifest_sha256": sha(p), "next_handoff": {"authorized": "independent design audit", "not_authorized": "hydraulic geometry, GPU execution, CPD4, or permeability claims"}}
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **completion}, indent=2))


if __name__ == "__main__":
    main()
