"""Independently verify and freeze the complete Stage26d evidence chain."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/final_confirmation_checkpoint_01/checkpoint_manifest.json"

CASES = {
    "positive_control": {
        "directory": ROOT / "stage26_runs/stage26d_adaptive_equilibration_20260816/controls_01/positive_stage26a",
        "config": ROOT / "stage26_staging/stage26d_adaptive_controls_execution_v1.json",
        "evaluation_sha256": "1a18ee3d77309e63babab54d3ee3cbee2aa3060d83111b8e2b6c3ee230d49c09",
        "expected_window": [247, 256],
        "expected_engagement": True,
        "expected_control": True,
        "expected_qualified": None,
    },
    "negative_control": {
        "directory": ROOT / "stage26_runs/stage26d_adaptive_equilibration_20260816/controls_01/negative_stage26b_failure",
        "config": ROOT / "stage26_staging/stage26d_adaptive_controls_execution_v1.json",
        "evaluation_sha256": "6c3fcffee89e42df09a76ff6f132003182f18aa671d756839079996dcc208e60",
        "expected_window": None,
        "expected_engagement": False,
        "expected_control": True,
        "expected_qualified": None,
    },
    "development_candidate01": {
        "directory": ROOT / "stage26_runs/stage26d_adaptive_equilibration_20260816/development_01/revision3_candidate01",
        "config": ROOT / "stage26_staging/stage26d_adaptive_development_candidate01_execution_v1.json",
        "evaluation_sha256": "dfbe55c5e874c00738983ac14df1551d15d4aa2516fb637202cde7a7a45d2c52",
        "expected_window": [143, 152],
        "expected_engagement": True,
        "expected_control": None,
        "expected_qualified": True,
    },
    "heldout_candidate04": {
        "directory": ROOT / "stage26_runs/stage26d_adaptive_equilibration_20260816/holdout_01/revision3_candidate04",
        "config": ROOT / "stage26_staging/stage26d_adaptive_holdout_candidate04_execution_v1.json",
        "evaluation_sha256": "05703ffed8864a4b25533629dabebf177830666f0b21b1a3a51820e57aa84081",
        "expected_window": [158, 167],
        "expected_engagement": True,
        "expected_control": None,
        "expected_qualified": True,
    },
}

JSON_COLUMNS = {
    "distinct_sand_contacts_by_fibre",
    "declared_anchor_contacts_by_fibre",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_history(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as stream:
        for source in csv.DictReader(stream):
            row = dict(source)
            row["block"] = int(row["block"])
            for name in JSON_COLUMNS:
                row[name] = json.loads(row[name])
            for name in (
                "isolated_fibre_count", "fibre_fibre_real_interaction_count",
                "intraclump_real_interaction_count",
            ):
                row[name] = int(row[name])
            row["unbalanced_force_defined"] = row["unbalanced_force_defined"].lower() == "true"
            for name in (
                "relative_mean_stress_error", "maximum_principal_stress_error", "unbalanced_force",
                "sand_coordination_excluding_degree_lt2_rattlers",
                "sand_rattler_fraction_degree_lt2_iterative", "sand_sand_contact_retention_fraction",
                "maximum_nonaffine_sand_displacement_over_D50", "cell_volume_relative_drift",
                "maximum_interobject_penetration_over_smaller_radius",
                "mean_effective_stress_pa_compression_positive",
            ):
                row[name] = float(row[name])
            rows.append(row)
    return rows


def continuous_engagement(rows, gates):
    return all(
        min(row["distinct_sand_contacts_by_fibre"]) >= gates["minimum_distinct_sand_contacts_per_fibre_at_every_block"]
        and min(row["declared_anchor_contacts_by_fibre"]) >= gates["minimum_declared_anchor_contacts_per_fibre_at_every_block"]
        and row["isolated_fibre_count"] <= gates["maximum_isolated_fibre_count_at_every_block"]
        for row in rows
    )


def equilibrium_pass(row, gates):
    finite_names = (
        "relative_mean_stress_error", "maximum_principal_stress_error", "unbalanced_force",
        "sand_coordination_excluding_degree_lt2_rattlers", "sand_rattler_fraction_degree_lt2_iterative",
        "sand_sand_contact_retention_fraction", "maximum_nonaffine_sand_displacement_over_D50",
        "cell_volume_relative_drift", "maximum_interobject_penetration_over_smaller_radius",
    )
    return (
        all(math.isfinite(row[name]) for name in finite_names)
        and min(row["distinct_sand_contacts_by_fibre"]) >= gates["minimum_distinct_sand_contacts_per_fibre"]
        and min(row["declared_anchor_contacts_by_fibre"]) >= gates["minimum_declared_anchor_contacts_per_fibre"]
        and row["fibre_fibre_real_interaction_count"] <= gates["maximum_fibre_fibre_real_interaction_count"]
        and row["intraclump_real_interaction_count"] <= gates["maximum_intraclump_real_interaction_count"]
        and row["relative_mean_stress_error"] <= gates["maximum_relative_mean_stress_error"]
        and row["maximum_principal_stress_error"] <= gates["maximum_principal_stress_error"]
        and row["unbalanced_force_defined"] is True
        and row["unbalanced_force"] <= gates["maximum_unbalanced_force"]
        and row["sand_coordination_excluding_degree_lt2_rattlers"] >= gates["minimum_sand_coordination_excluding_rattlers"]
        and row["sand_rattler_fraction_degree_lt2_iterative"] <= gates["maximum_sand_rattler_fraction"]
        and row["sand_sand_contact_retention_fraction"] >= gates["minimum_sand_contact_retention_fraction"]
        and row["maximum_nonaffine_sand_displacement_over_D50"] <= gates["maximum_sand_displacement_over_D50"]
        and row["cell_volume_relative_drift"] <= gates["maximum_cell_volume_relative_drift"]
        and row["maximum_interobject_penetration_over_smaller_radius"] <= gates["maximum_interobject_penetration_over_smaller_radius"]
    )


def earliest_window(rows, minimum_block, width, gates):
    streak = []
    for row in rows:
        if row["block"] < minimum_block:
            continue
        streak = streak + [row["block"]] if equilibrium_pass(row, gates) else []
        if len(streak) == width:
            return [streak[0], streak[-1]]
    return None


def verify_case(name, spec):
    directory = spec["directory"]
    paths = {
        "evaluation": directory / "adaptive_evaluation_v1.json",
        "result": directory / "result.json",
        "completion": directory / "completion.json",
        "history": directory / "fixed_conditioning_history.csv",
    }
    actual_hashes = {key: digest(path) for key, path in paths.items()}
    assert actual_hashes["evaluation"] == spec["evaluation_sha256"]
    cfg = load_json(spec["config"])
    evaluation = load_json(paths["evaluation"])
    result = load_json(paths["result"])
    completion = load_json(paths["completion"])
    rows = load_history(paths["history"])
    assert result["passed"] is True and completion["passed"] is True and evaluation["passed"] is True
    assert result["protocol"] == {"all_fibres_fixed": True, "blocks": 300, "free_release": False, "steps_per_block": 500}
    assert result["source_hashes"]["config"] == digest(spec["config"])
    assert completion["result_sha256"] == actual_hashes["result"]
    assert result["artifacts"]["fixed_conditioning_history_csv_sha256"] == actual_hashes["history"]
    assert evaluation["bindings"] == {
        "config_sha256": digest(spec["config"]),
        "raw_result_sha256": actual_hashes["result"],
        "raw_completion_sha256": actual_hashes["completion"],
        "raw_history_sha256": actual_hashes["history"],
    }
    assert len(rows) == 300 and [row["block"] for row in rows] == list(range(1, 301))
    assert all(value == 2 for value in result["insertion"]["distinct_sand_contacts_by_fibre"])
    engagement = continuous_engagement(rows, cfg["continuous_engagement_gates"])
    window = earliest_window(
        rows,
        cfg["adaptive_equilibration"]["minimum_blocks_before_equilibrium_window"],
        cfg["adaptive_equilibration"]["required_consecutive_passing_blocks"],
        cfg["equilibrium_window_gates"],
    )
    assert engagement is spec["expected_engagement"]
    assert window == spec["expected_window"] == evaluation["earliest_qualifying_window_blocks"]
    assert evaluation["control_reproduced"] is spec["expected_control"]
    assert evaluation["qualified_fixed_prefilter"] is spec["expected_qualified"]
    return {
        "role": evaluation["trial"]["stage26d_role"],
        "trial_id": evaluation["trial"]["trial_id"],
        "continuous_engagement": engagement,
        "earliest_qualifying_window_blocks": window,
        "passing_equilibrium_row_count": sum(equilibrium_pass(row, cfg["equilibrium_window_gates"]) for row in rows),
        "evaluation_metrics": evaluation["metrics"],
        "hashes": actual_hashes,
        "config_sha256": digest(spec["config"]),
    }


def main():
    assert not OUT.exists(), "refusing to overwrite immutable final checkpoint"
    cases = {name: verify_case(name, spec) for name, spec in CASES.items()}
    assert cases["heldout_candidate04"]["earliest_qualifying_window_blocks"] == [158, 167]
    checkpoint = {
        "schema": "lbs.stage26d-adaptive-final-confirmation-checkpoint.v1",
        "passed": True,
        "status": "fixed_fibre_adaptive_prefilter_confirmed_on_heldout_geometry",
        "conclusion": (
            "The frozen 300-block fixed-fibre protocol and 10-consecutive-block adaptive gate reproduced both controls, "
            "qualified development candidate01, and independently qualified the preselected candidate04 holdout."
        ),
        "cases": cases,
        "source_hashes": {
            "design": digest(ROOT / "stage26_staging/stage26d_adaptive_equilibration_design_v1.json"),
            "design_checkpoint": digest(ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/design_checkpoint_02/checkpoint_manifest.json"),
            "control_checkpoint": digest(ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/control_requalification_checkpoint_01/checkpoint_manifest.json"),
            "development_checkpoint": digest(ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/development_outcome_checkpoint_01/checkpoint_manifest.json"),
            "holdout_execution_checkpoint": digest(ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/holdout_execution_checkpoint_01/checkpoint_manifest.json"),
            "runner": digest(ROOT / "stage26_staging/run_stage26b_revision2_fixed_prefilter_v1.py"),
            "evaluator_core": digest(ROOT / "stage26_staging/evaluate_stage26d_adaptive_prefilter_v1.py"),
            "evaluator_adapter": digest(ROOT / "stage26_staging/evaluate_stage26d_adaptive_prefilter_v2.py"),
            "independent_verifier": digest(Path(__file__)),
        },
        "authority": {
            "diagnostic_render_authorized": True,
            "free_release_authorized": False,
            "promoted_dem_state_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
            "heldout_rerun_authorized": False,
            "protocol_retuning_authorized": False,
        },
        "claim_boundary": (
            "Verified dry fixed-fibre equilibration-method result for two F37 fibres in the 216-sphere LBS surrogate. "
            "No free-fibre stability, saved promotable DEM state, polymer calibration, permeability, flow, deformation, "
            "migration, transient FSI, or production concentration effect is claimed."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"checkpoint": str(OUT), "sha256": digest(OUT), "status": checkpoint["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
