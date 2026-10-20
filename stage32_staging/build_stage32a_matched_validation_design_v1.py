from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage32a_matched_constant_head_validation_20260828"
OUT = ROOT / "stage32_designs" / STUDY / "design_01"
CONTRACT = ROOT / "stage32_staging/STAGE32A_MATCHED_CONSTANT_HEAD_VALIDATION_CONTRACT.md"
OLD = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration")
SOURCES = {
    "stage23c_clean_cpd2": OLD / "runs/stage23c_clean_lbs_cpd2_gpu_ensemble_20260809/evaluation_01/evaluation.json",
    "stage23e_clean_cpd4": OLD / "runs/stage23e_clean_lbs_cpd4_selected_gpu_20260810/evaluation_01/evaluation.json",
    "stage24c_concentration": OLD / "runs/stage24c_lbs_f37_cpd2_gpu_screen_20260811/evaluation_01/evaluation.json",
    "stage31e_replication": ROOT / "stage31_evaluations/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_evaluation_01/evaluation.json",
    "stage31f_cpd4": ROOT / "stage31_evaluations/stage31f_selected_replicated_cpd4_20260827/gpu_evaluation_02/evaluation.json",
    "ea_fraction_b": OLD / "data/literature/lbs_fraction_b_ea_digitization_v1.json",
    "pure_sand_literature": OLD / "data/literature/lbs_pure_sand_permeability_v1.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def constrained_shuffle(rows: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed)
    for _ in range(10000):
        candidate = rows[:]
        rng.shuffle(candidate)
        if all(not (candidate[i]["group_id"] == candidate[i + 1]["group_id"] == candidate[i + 2]["group_id"]) for i in range(len(candidate) - 2)):
            return candidate
    raise RuntimeError("could not generate constrained randomized order")


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    src = {key: load(path) for key, path in SOURCES.items()}
    if not all(src[key].get("passed") is True for key in ("stage23c_clean_cpd2", "stage23e_clean_cpd4", "stage24c_concentration", "stage31e_replication", "stage31f_cpd4")):
        raise RuntimeError("one or more numerical sources are not passed")

    curve = src["stage24c_concentration"]["effects"]["primary_concentration_curve"]
    by_target = {round(float(row["target_dry_mass_percent"]), 3): row for row in curve}
    targets = [
        ("clean", 0.0, 1.0, 1.0, 1.0),
        ("iso_0p004691", 0.004690960879927048, by_target[0.005]["mean_ratio"], by_target[0.005]["minimum_ratio"], by_target[0.005]["maximum_ratio"]),
        ("iso_0p051576", 0.05157637540326301, by_target[0.05]["mean_ratio"], by_target[0.05]["minimum_ratio"], by_target[0.05]["maximum_ratio"]),
        ("iso_0p098418", 0.09841784362759924, by_target[0.1]["mean_ratio"], by_target[0.1]["minimum_ratio"], by_target[0.1]["maximum_ratio"]),
        ("iso_0p401820", 0.40182045026272944, by_target[0.4]["mean_ratio"], by_target[0.4]["minimum_ratio"], by_target[0.4]["maximum_ratio"]),
    ]
    rows = []
    for group_id, wt, mean, low, high in targets:
        for replicate in range(1, 7):
            rows.append({"phase": 1, "group_id": group_id, "orientation": "clean" if wt == 0 else "isotropic",
                         "target_dry_mass_percent": wt, "replicate": replicate,
                         "numerical_mean_ratio": mean, "numerical_minimum_ratio": low, "numerical_maximum_ratio": high})
    orientation = src["stage24c_concentration"]["effects"]["orientation"]["0.400"]["cells"]
    for label, source_key in (("parallel_0p401820", "parallel_biased"), ("transverse_0p401820", "transverse_biased")):
        cell = orientation[source_key]
        for replicate in range(1, 5):
            rows.append({"phase": 2, "group_id": label, "orientation": source_key,
                         "target_dry_mass_percent": 0.40182045026272944, "replicate": replicate,
                         "numerical_mean_ratio": cell["mean_ratio"], "numerical_minimum_ratio": cell["minimum_ratio"],
                         "numerical_maximum_ratio": cell["maximum_ratio"]})
    phase1 = constrained_shuffle([r for r in rows if r["phase"] == 1], 20260828)
    phase2 = constrained_shuffle([r for r in rows if r["phase"] == 2], 20260829)
    ordered = phase1 + phase2
    for i, row in enumerate(ordered, 1):
        row["run_order"] = i
        row["specimen_id"] = f"S32A-{i:03d}"
        row["preparation_block"] = 1 + (i - 1) // 10 if row["phase"] == 1 else 4
        row["fibre_mass_g_per_1000g_dry_sand"] = 10.0 * row["target_dry_mass_percent"]

    clean_cpd2 = [float(case["hydraulic_conductivity_at_20c_m_s"]) for case in src["stage23c_clean_cpd2"]["cases"]]
    clean_cpd4 = [float(case["cpd4_intrinsic_permeability_m2"]) for case in src["stage23e_clean_cpd4"]["cases"]]
    protocol = {
        "schema": "lbs.stage32a-matched-constant-head-validation-design.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_prospective_validation_design",
        "passed": True,
        "research_question": "Can the frozen fixed-solid DEM-LBM model predict clean K20 and concentration-dependent relative K20 in matched LBS specimens?",
        "evidence_role": "prospective physical-validation protocol; no physical validation claim before blinded data evaluation",
        "system": {"sand": "Leighton Buzzard Sand Fraction B / matched 0.60-1.18 mm fraction",
                   "target_void_ratio": 0.744, "void_ratio_tolerance": 0.010,
                   "water_temperature_c": 20.0, "water_temperature_tolerance_c": 0.5,
                   "fibre_length_mm": 0.90, "fibre_radius_mm": 0.05,
                   "test": "steady saturated constant-head"},
        "design": {"phase1_specimens": 30, "phase2_holdout_specimens": 8, "total_specimens": 38,
                   "phase2_release_condition": "clean repeatability and state-control gates pass",
                   "randomization_seeds": {"phase1": 20260828, "phase2": 20260829},
                   "monotonicity_is_not_acceptance_gate": True},
        "frozen_predictions": {"concentration_groups": [dict(group_id=g, target_dry_mass_percent=w,
            numerical_mean_ratio=m, numerical_minimum_ratio=lo, numerical_maximum_ratio=hi) for g, w, m, lo, hi in targets],
            "clean_cpd2_K20_m_s_values": clean_cpd2,
            "clean_cpd2_K20_m_s_envelope": [min(clean_cpd2), max(clean_cpd2)],
            "clean_cpd4_intrinsic_permeability_m2_envelope": [min(clean_cpd4), max(clean_cpd4)]},
        "decision_rules": {
            "minimum_valid_phase1_per_group": 5, "minimum_valid_phase2_per_group": 3,
            "maximum_clean_cv": 0.05,
            "clean_gate": "experimental mean-K20 interval overlaps frozen numerical clean envelope",
            "relative_gate": "mean-ratio interval overlaps numerical range at >=2 of 0.05, 0.10, 0.40 wt%; 0.40 upper 95% interval < 1",
            "detection_floor": "0.004691 wt% is descriptive and cannot fail the model alone",
            "orientation_gate": "parallel mean ratio < isotropic mean ratio < transverse mean ratio at 0.401820 wt%"},
        "source_bindings": {key: {"path": str(path), "sha256": sha(path)} for key, path in SOURCES.items()},
        "contract": {"path": str(CONTRACT), "sha256": sha(CONTRACT)},
        "authority": {"laboratory_execution": False, "physical_validation_claim": False,
                      "numerical_rerun": False, "migration": False, "clogging": False,
                      "deformation": False, "transient_coupling": False, "two_way_coupling": False},
    }
    OUT.mkdir(parents=True)
    (OUT / "resolved_protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    fields = ["run_order", "specimen_id", "phase", "preparation_block", "group_id", "orientation",
              "target_dry_mass_percent", "replicate", "fibre_mass_g_per_1000g_dry_sand",
              "numerical_mean_ratio", "numerical_minimum_ratio", "numerical_maximum_ratio"]
    with (OUT / "design_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows([{k: row[k] for k in fields} for row in ordered])
    capture_fields = fields + ["batch_id", "dry_sand_mass_g", "fibre_mass_g", "initial_void_ratio", "final_void_ratio",
        "water_temperature_c", "specimen_diameter_mm", "specimen_length_mm", "head_difference_m", "collection_time_s",
        "collected_water_mass_g", "K_raw_m_s", "K20_m_s", "valid", "rejection_reason", "operator_notes"]
    with (OUT / "data_capture_template.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=capture_fields)
        writer.writeheader(); writer.writerows([{**{k: row[k] for k in fields}, **{k: "" for k in capture_fields if k not in fields}} for row in ordered])
    completion = {"schema": protocol["schema"] + ".completion", "passed": True,
        "status": "frozen_design_ready_for_independent_audit", "checks": {"protocol_frozen": True,
        "exact_38_specimens": len(ordered) == 38, "phase1_30": len(phase1) == 30, "phase2_8": len(phase2) == 8},
        "artifacts": {name: sha(OUT / name) for name in ("resolved_protocol.json", "design_matrix.csv", "data_capture_template.csv")},
        "next_handoff": "independent design audit only; no laboratory execution or validation claim"}
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "rows": len(ordered), "phase1": len(phase1), "phase2": len(phase2)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
