#!/usr/bin/env python3
"""Independently evaluate the immutable Stage26n safe-release pilot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--completion", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--stage26m-evaluation", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    cfg, result, completion, prior = (load(args.config), load(args.result), load(args.completion), load(args.stage26m_evaluation))
    assert result["passed"] is True and completion["passed"] is True
    assert completion["result_sha256"] == sha(args.result)
    assert result["source_hashes"]["config"] == sha(args.config)
    assert result["source_hashes"]["runner"] == cfg["sources"]["runner_sha256"]
    assert result["artifacts"]["history_sha256"] == sha(args.history)
    assert cfg["sources"]["stage26m_evaluation_sha256"] == sha(args.stage26m_evaluation)
    assert prior["physical_result_accepted"] is False

    rows = []
    with args.history.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            rows.append({
                "phase": row["phase"],
                "phase_index": int(row["phase_index"]),
                "stress": float(row["mean_effective_stress_pa_compression_positive"]),
                "overlap": float(row["maximum_interobject_penetration_over_smaller_radius"]),
                "translation": float(row["maximum_fibre_translation_over_D50"]),
                "rotation": float(row["maximum_fibre_rotation_deg"]),
                "unbalanced": float(row["unbalanced_force"]),
                "contacts": json.loads(row["distinct_sand_contacts_by_fibre"]),
                "dt": float(row["time_step_s"]),
            })
    assert len(rows) == result["records_written"]
    assert all(math.isfinite(value) for row in rows for value in (row["stress"], row["overlap"], row["translation"], row["rotation"], row["unbalanced"], row["dt"]))
    mobile = [row for row in rows if row["phase"].startswith("release_ramp_") or row["phase"] == "mobile_equilibration"]
    first_both_isolated = next((row for row in mobile if row["contacts"] == [0, 0]), None)
    maxima = {
        "maximum_absolute_principal_stress_pa": max(max(abs(value) for value in result["terminal"]["principal_effective_stress_pa_compression_positive"]), max(abs(row["stress"]) for row in mobile)),
        "maximum_mean_stress_pa_during_mobile": max(row["stress"] for row in mobile),
        "maximum_overlap_ratio_during_mobile": max(row["overlap"] for row in mobile),
        "maximum_translation_over_D50_during_mobile": max(row["translation"] for row in mobile),
        "maximum_rotation_deg_during_mobile": max(row["rotation"] for row in mobile),
        "minimum_time_step_s_during_mobile": min(row["dt"] for row in mobile),
        "maximum_time_step_s_during_mobile": max(row["dt"] for row in mobile),
    }
    numerical_release_stable = (
        all(result["terminal_hard_checks"].values())
        and maxima["maximum_overlap_ratio_during_mobile"] <= cfg["hard_guards"]["maximum_interobject_penetration_over_smaller_radius"]
        and maxima["maximum_translation_over_D50_during_mobile"] <= cfg["hard_guards"]["maximum_nonaffine_translation_over_D50"]
        and maxima["maximum_mean_stress_pa_during_mobile"] <= cfg["hard_guards"]["maximum_absolute_principal_stress_pa"]
    )
    sand_skeleton_healthy = all(result["terminal_checks"][name] for name in (
        "mean_stress", "principal_stress", "unbalanced_force", "normalized_kinetic_energy",
        "sand_coordination", "sand_rattlers", "overlap", "void_ratio", "sand_particle_count", "exact_geometry",
    ))
    caging_qualified = result["qualified"] is True and result["terminal_checks"]["fibre_contacts"] and result["terminal_checks"]["no_isolated_fibre"]
    evaluation = {
        "schema": "lbs.stage26n-equilibrated-safe-release-pilot-evaluation.v1",
        "passed": True,
        "status": "numerically_stable_release_but_mobile_caging_failed",
        "numerical_release_stability_pass": numerical_release_stable,
        "sand_skeleton_healthy": sand_skeleton_healthy,
        "mobile_caging_qualified": caging_qualified,
        "physical_result_accepted": False,
        "finding": (
            "Equilibrating the fixed mixture and ramping timestep/damping removed the Stage26m release impulse. "
            "Both exact fibres nevertheless detached from the sand and ended isolated, so the present isotropic "
            "loose-state reconstruction does not embed the microplastic mechanically."
        ),
        "mechanical_interpretation": (
            "The prior explosion was numerical, but the remaining failure is physical/model-form: the 100 um "
            "diameter fibres occupy pore space without a persistent three-contact cage after release. The sand "
            "skeleton itself is equilibrated and load-bearing."
        ),
        "next_action": "design_gravity_assisted_joint_mixture_deposition_benchmark_before_another_caging_attempt",
        "fixed_release": {
            "block": result["fixed_release_row"]["block"],
            "stress_pa": result["fixed_release_row"]["mean_effective_stress_pa_compression_positive"],
            "sand_contacts": result["fixed_release_row"]["sand_sand_real_contact_count"],
            "fibre_contacts": result["fixed_release_row"]["distinct_sand_contacts_by_fibre"],
            "unbalanced_force": result["fixed_release_row"]["unbalanced_force"],
            "consecutive_pass_blocks": result["fixed_consecutive_pass_blocks"],
        },
        "mobile_maxima": maxima,
        "first_both_fibres_isolated": first_both_isolated,
        "terminal": {
            "stress_pa": result["terminal"]["mean_effective_stress_pa_compression_positive"],
            "sand_contacts": result["terminal"]["sand_sand_real_contact_count"],
            "sand_coordination": result["terminal"]["sand_coordination_excluding_degree_lt2_rattlers"],
            "fibre_contacts": result["terminal"]["distinct_sand_contacts_by_fibre"],
            "translation_over_D50": result["terminal"]["maximum_fibre_translation_over_D50"],
            "rotation_deg": result["terminal"]["maximum_fibre_rotation_deg"],
            "unbalanced_force": result["terminal"]["unbalanced_force"],
        },
        "source_hashes": {
            "config": sha(args.config), "result": sha(args.result), "completion": sha(args.completion),
            "history": sha(args.history), "stage26m_evaluation": sha(args.stage26m_evaluation),
            "evaluator": sha(args.evaluator),
        },
        "authority": completion["authority"],
        "claim_boundary": result["claim_boundary"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    assert numerical_release_stable is True
    assert sand_skeleton_healthy is True
    assert caging_qualified is False
    assert evaluation["terminal"]["fibre_contacts"] == [0, 0]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "evaluation.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"evaluation": str(output), "evaluation_sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
