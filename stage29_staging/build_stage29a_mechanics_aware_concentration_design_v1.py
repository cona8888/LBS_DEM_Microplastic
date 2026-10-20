from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29a_mechanics_aware_concentration_design_20260825"
OUT = ROOT / "stage29_designs" / STUDY / "design_01"
CONTRACT = ROOT / "stage29_staging" / "STAGE29A_MECHANICS_AWARE_CONCENTRATION_DESIGN_CONTRACT.md"
STAGE28A = ROOT / "stage28_evaluations" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_evaluation_02" / "evaluation.json"
STAGE28C = ROOT / "stage28_evaluations" / "stage28c_selected_two_fibre_cpd4_20260825" / "gpu_evaluation_01" / "evaluation.json"
STAGE28C_CHECKPOINT = ROOT / "stage28_evaluations" / "stage28c_selected_two_fibre_cpd4_20260825" / "gpu_evaluation_01" / "checkpoint_manifest.json"
OLD_ROOT = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration\runs")
STAGE24C = OLD_ROOT / "stage24c_lbs_f37_cpd2_gpu_screen_20260811" / "evaluation_01" / "evaluation.json"
STAGE24E = OLD_ROOT / "stage24e_lbs_f37_selected_cpd4_gpu_20260812" / "evaluation_01" / "evaluation.json"

SAND_MASS_KG = 0.00015213021193865423
FIBRE_MASS_KG = 7.136703508562081e-09
PLACEMENT_SEEDS = {"A": 2026082901, "B": 2026082902, "C": 2026082903}
RANDOMIZATION_SEED = 2026082999


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def concentration(n: int) -> float:
    return 100.0 * n * FIBRE_MASS_KG / (SAND_MASS_KG + n * FIBRE_MASS_KG)


def case(case_id: str, n: int, topology: str, block: str, role: str) -> dict:
    return {
        "case_id": case_id,
        "fibre_count": n,
        "achieved_dry_mass_percent": concentration(n),
        "topology_regime": topology,
        "placement_block": block,
        "placement_seed": PLACEMENT_SEEDS[block],
        "role": role,
        "packing_id": "n216_s1_fixed",
        "sand_mobile": False,
        "hydraulic_resolution": "CPD2_screen_pending_release",
        "mechanics_status": "qualification_required",
        "paired_clean_control": "stage28c_clean_cpd4_positive_and_stage27b_clean_exact",
    }


def main() -> None:
    sources = {
        "contract": CONTRACT,
        "stage28a_mechanics_evaluation": STAGE28A,
        "stage28c_cpd4_evaluation": STAGE28C,
        "stage28c_checkpoint": STAGE28C_CHECKPOINT,
        "stage24c_rigid_screen_evaluation": STAGE24C,
        "stage24e_rigid_cpd4_evaluation": STAGE24E,
    }
    missing = [str(p) for p in sources.values() if not p.is_file()]
    if missing:
        raise SystemExit("Missing frozen source(s): " + "; ".join(missing))
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite immutable output: {OUT}")

    cases = []
    for block in "ABC":
        cases.append(case(f"s29_f001_single_open_{block}", 1, "single_open", block, "low_concentration_curve"))
        cases.append(case(f"s29_f002_separated_{block}", 2, "separated", block, "topology_and_concentration"))
        cases.append(case(f"s29_f002_crossing_{block}", 2, "crossing", block, "topology_and_concentration"))
        cases.append(case(f"s29_f004_low_contact_{block}", 4, "low_contact", block, "four_fibre_mechanics_gate"))
        cases.append(case(f"s29_f004_contact_rich_{block}", 4, "contact_rich", block, "four_fibre_mechanics_gate"))

    randomized_ids = [c["case_id"] for c in cases]
    random.Random(RANDOMIZATION_SEED).shuffle(randomized_ids)
    run_order = {cid: i + 1 for i, cid in enumerate(randomized_ids)}
    for c in cases:
        c["frozen_randomized_run_order"] = run_order[c["case_id"]]

    design = {
        "schema": "lbs.stage29a-mechanics-aware-concentration-design.v1",
        "study_id": STUDY,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "designed_not_authorized_for_execution",
        "scientific_question": "How do F37 fibre count and fibre-fibre topology affect paired permeability in one fixed periodic 216-grain LBS packing?",
        "fixed_parameters": {
            "packing_id": "n216_s1_fixed",
            "particle_count": 216,
            "sand_mass_kg": SAND_MASS_KG,
            "fibre_mass_kg": FIBRE_MASS_KG,
            "fibre_model": "deformable F37 grid-chain inherited from accepted Stage28a",
            "sand_mobile_during_hydraulics": False,
            "clean_control_rerun": False,
        },
        "concentration_mapping": [
            {"fibre_count": n, "achieved_dry_mass_percent": concentration(n)} for n in (0, 1, 2, 4)
        ],
        "design_factors": {
            "fibre_counts": [0, 1, 2, 4],
            "placement_blocks": ["A", "B", "C"],
            "topology_by_count": {
                "0": ["clean_reused"],
                "1": ["single_open"],
                "2": ["separated", "crossing"],
                "4": ["low_contact", "contact_rich"],
            },
            "randomization_seed": RANDOMIZATION_SEED,
        },
        "case_count_new": len(cases),
        "case_count_with_reused_clean": len(cases) + 1,
        "cases": sorted(cases, key=lambda x: x["case_id"]),
        "sequential_plan": [
            "qualify six four-fibre mechanics cases",
            "qualify one- and two-fibre placement-block mechanics cases",
            "independently audit every geometry and mechanics checkpoint",
            "run bounded 15-case CPD2 screen only after a new release",
            "estimate concentration, topology, interaction, and block effects without a monotonicity gate",
            "select a bounded CPD4 confirmation subset",
        ],
        "predeclared_gates": {
            "four_fibre_mechanics_cases_required_to_pass": 6,
            "all_nonclean_mechanics_cases_required_to_pass": 15,
            "maximum_path_match_rms_over_fibre_diameter": 0.05,
            "maximum_penetration_over_fibre_radius": 0.02,
            "false_same_fibre_contacts": 0,
            "cross_node_bonds": 0,
            "fixed_sand_and_cell_exact": True,
            "numerical_resolution_band_k_over_k0": 0.0002,
            "monotonicity_required": False,
        },
        "analysis_plan": {
            "primary_outcome": "paired k_over_k0",
            "effects": ["fibre_count", "topology_regime", "fibre_count_x_topology", "placement_block"],
            "report": ["block-paired contrasts", "means", "sample standard deviations", "numerical-resolution classification"],
            "adaptive_rule": "Do not add 8 or 11 fibres until all four-fibre mechanics and CPD2 health gates pass; require a new audited handoff.",
        },
        "claim_boundary": "Low-concentration fixed-packing static-flow mechanics-aware pore obstruction in one periodic 216-grain LBS realization; excludes mixing, packing rearrangement, scale-up, chemistry, migration, clogging, deformation, mobile sand, and two-way coupling.",
        "authority": {
            "design_generation": True,
            "design_audit": True,
            "mechanics_execution": False,
            "cpd2_gpu_execution": False,
            "cpd4_execution": False,
            "production_concentration_execution": False,
            "new_physics": False,
        },
        "source_paths": {k: str(v) for k, v in sources.items()},
        "source_hashes": {k: sha256(v) for k, v in sources.items()},
    }
    design["case_matrix_sha256"] = canonical_sha(design["cases"])

    OUT.mkdir(parents=True)
    design_path = OUT / "design_manifest.json"
    design_path.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (OUT / "case_matrix.csv").open("w", newline="", encoding="utf-8") as f:
        fields = [
            "frozen_randomized_run_order", "case_id", "fibre_count", "achieved_dry_mass_percent",
            "topology_regime", "placement_block", "placement_seed", "role", "mechanics_status",
        ]
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(cases, key=lambda x: x["frozen_randomized_run_order"]))
    completion = {
        "schema": "lbs.stage29a-mechanics-aware-concentration-design.v1.completion",
        "status": "passed_design_generation_execution_not_authorized",
        "passed": True,
        "design_manifest_sha256": sha256(design_path),
        "case_matrix_csv_sha256": sha256(OUT / "case_matrix.csv"),
        "next_handoff": "independent design audit, then four-fibre mechanics preflight design only",
    }
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **completion}, indent=2))


if __name__ == "__main__":
    main()
