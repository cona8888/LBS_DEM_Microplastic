#!/usr/bin/env python3
"""Independently verify the Stage31a three-packing pure-sand bridge."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN = ROOT / "stage31_designs/stage31a_packing_replication_bridge_20260826/design_01"
RUN = ROOT / "stage31_runs/stage31a_packing_replication_bridge_20260826"
SUPERVISOR = ROOT / "stage31_supervisors/stage31a_packing_replication_bridge_20260826/supervisor_01"
OUTPUT = ROOT / "stage31_evaluations/stage31a_packing_replication_bridge_20260826/mechanics_evaluation_01"
S1_RESULT = ROOT / "stage25_runs/stage25a_pure_sand_mechanics_20260813/qualification_04/mu_0.60/result.json"
S1_COMPLETION = ROOT / "stage25_runs/stage25a_pure_sand_mechanics_20260813/qualification_04/completion.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite(value: object) -> bool:
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    if isinstance(value, list):
        return all(finite(item) for item in value)
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return True


def positions_signature(result: dict) -> str:
    payload = json.dumps(
        [[row["body_id"], row["position_m"], row["radius_m"]] for row in result["particles"]],
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def audit_case(packing: str, seed: int, result_path: Path, completion_path: Path, config_path: Path) -> dict:
    config, result, completion = load(config_path), load(result_path), load(completion_path)
    terminal = result["terminal"]
    acceptance = config["acceptance"]
    checks = {
        "config_hash": digest(config_path) == completion["source_hashes"]["config"] == result["source_hashes"]["config"],
        "runner_hash": completion["source_hashes"]["runner"] == result["source_hashes"]["runner"] == "1ed89f6afd79ca8a8811e8a18e1a53217dcebffeed83522eb2e8710698d79d5b",
        "seed_identity": int(config["sand"]["random_seed"]) == seed,
        "single_frozen_friction": config["contacts"]["preparation_friction_coefficients"] == [0.6] and result["preparation_friction_coefficient"] == 0.6,
        "completion_passed": completion.get("passed") is True and completion.get("passed_case_ids") == ["mu_0.60"],
        "result_passed": result.get("passed") is True and all(result.get("checks", {}).values()),
        "record_binding": digest(result_path) == completion["case_records"]["mu_0.60"],
        "checkpoint_hash": digest(result_path.parent / "load_bearing_state.yade.gz") == result["artifacts"]["checkpoint_sha256"],
        "history_hash": digest(result_path.parent / "history.csv") == result["artifacts"]["history_csv_sha256"],
        "finite_result": finite(result),
        "particle_count": len(result["particles"]) == int(acceptance["required_particle_count"]) == 216,
        "unique_body_ids": len({row["body_id"] for row in result["particles"]}) == 216,
        "stress_gate": terminal["relative_mean_stress_error"] <= acceptance["maximum_relative_mean_stress_error"],
        "unbalanced_gate": terminal["unbalanced_force_defined"] is True and terminal["unbalanced_force"] <= acceptance["maximum_unbalanced_force"],
        "kinetic_gate": terminal["normalized_kinetic_energy_pV"] <= acceptance["maximum_normalized_kinetic_energy_pV"],
        "coordination_gate": terminal["coordination_excluding_degree_lt2_rattlers"] >= acceptance["minimum_coordination_excluding_rattlers"],
        "rattler_gate": terminal["rattler_fraction_degree_lt2_iterative"] <= acceptance["maximum_rattler_fraction"],
        "overlap_gate": terminal["maximum_overlap_over_smaller_radius"] <= acceptance["maximum_overlap_over_smaller_radius"],
        "void_ratio_gate": abs(terminal["void_ratio"] - config["reference_state"]["void_ratio"]) <= acceptance["maximum_absolute_void_ratio_difference_from_reference"],
        "no_failure": not (result_path.parent / "failure.json").exists(),
    }
    return {
        "packing_id": packing,
        "seed": seed,
        "passed": all(checks.values()),
        "checks": checks,
        "result_sha256": digest(result_path),
        "completion_sha256": digest(completion_path),
        "checkpoint_sha256": digest(result_path.parent / "load_bearing_state.yade.gz"),
        "positions_signature": positions_signature(result),
        "terminal": terminal,
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable evaluation: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    manifest = load(DESIGN / "manifest.json")
    stage30 = Path(manifest["lineage"]["stage30_evaluation"])
    stage25 = Path(manifest["lineage"]["stage25_completion"])
    runner = Path(manifest["lineage"]["stage25_runner"])
    lineage_checks = {
        "stage30_hash": digest(stage30) == manifest["lineage"]["stage30_evaluation_sha256"],
        "stage30_passed": load(stage30).get("passed") is True,
        "stage25_hash": digest(stage25) == manifest["lineage"]["stage25_completion_sha256"],
        "stage25_passed": load(stage25).get("passed") is True,
        "runner_hash": digest(runner) == manifest["lineage"]["stage25_runner_sha256"],
        "primary_result_hash": digest(S1_RESULT) == manifest["primary_replicate_reused_without_rerun"]["result_sha256"],
        "primary_completion_hash": digest(S1_COMPLETION) == manifest["lineage"]["stage25_completion_sha256"],
    }

    s1 = load(S1_RESULT)
    primary_checks = {
        "passed": s1.get("passed") is True and all(s1.get("checks", {}).values()),
        "particle_count": len(s1["particles"]) == 216,
        "finite": finite(s1),
        "friction": s1["preparation_friction_coefficient"] == 0.6,
        "checkpoint_hash": digest(S1_RESULT.parent / "load_bearing_state.yade.gz") == s1["artifacts"]["checkpoint_sha256"],
        "history_hash": digest(S1_RESULT.parent / "history.csv") == s1["artifacts"]["history_csv_sha256"],
    }
    cases = [{
        "packing_id": "n216_s1",
        "seed": 202608231,
        "passed": all(primary_checks.values()),
        "checks": primary_checks,
        "result_sha256": digest(S1_RESULT),
        "checkpoint_sha256": digest(S1_RESULT.parent / "load_bearing_state.yade.gz"),
        "positions_signature": positions_signature(s1),
        "terminal": s1["terminal"],
    }]
    for packing, seed in (("n216_s2", 202608232), ("n216_s3", 202608233)):
        case_root = RUN / f"{packing}_qualification_01"
        cases.append(audit_case(
            packing,
            seed,
            case_root / "mu_0.60/result.json",
            case_root / "completion.json",
            DESIGN / f"{packing}_config.json",
        ))

    stderr_checks = {}
    expected = "Running script /mnt/c/MATDEM_MICROPLASTIC/stage25_staging/stage25a_yade_pure_sand_mechanics_v1.py"
    for packing in ("n216_s2", "n216_s3"):
        text = (SUPERVISOR / f"{packing}.stderr.log").read_text(encoding="utf-8")
        stderr_checks[packing] = "Traceback" not in text and "ERROR" not in text and expected in text

    signatures = [case["positions_signature"] for case in cases]
    aggregate_checks = {
        "all_three_passed": len(cases) == 3 and all(case["passed"] for case in cases),
        "three_distinct_packings": len(set(signatures)) == 3,
        "lineage": all(lineage_checks.values()),
        "supervisor_completed": (SUPERVISOR / "status.txt").read_text(encoding="utf-8") == "completed\nexit_code=0\n",
        "stderr_benign": all(stderr_checks.values()),
        "no_failure_markers": not any(RUN.rglob("failure.json")),
        "authority_respected": manifest["authority"] == {
            "pure_sand_replication_execution": True,
            "fibre_mechanics": False,
            "flow": False,
            "permeability_claim": False,
            "coupling": False,
        },
    }
    passed = all(aggregate_checks.values())
    evaluation = {
        "schema": "lbs.stage31a-packing-replication-bridge.v1.evaluation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed_three_packing_pure_sand_bridge" if passed else "failed_closed",
        "passed": passed,
        "checks": aggregate_checks,
        "lineage_checks": lineage_checks,
        "stderr_checks": stderr_checks,
        "cases": cases,
        "summary": {
            "void_ratio_range": [min(c["terminal"]["void_ratio"] for c in cases), max(c["terminal"]["void_ratio"] for c in cases)],
            "coordination_range": [min(c["terminal"]["coordination_excluding_degree_lt2_rattlers"] for c in cases), max(c["terminal"]["coordination_excluding_degree_lt2_rattlers"] for c in cases)],
            "rattler_fraction_range": [min(c["terminal"]["rattler_fraction_degree_lt2_iterative"] for c in cases), max(c["terminal"]["rattler_fraction_degree_lt2_iterative"] for c in cases)],
        },
        "decision": "The frozen pure-sand preparation passed for all three packing seeds. A separate Stage31b may now design and audit matched fibre placements; flow remains unauthorized.",
        "claim_boundary": manifest["claim_boundary"],
        "authority": {
            "matched_fibre_design": passed,
            "fibre_mechanics_execution": False,
            "flow": False,
            "permeability_claim": False,
            "coupling": False,
        },
        "source_hashes": {
            "design_manifest": digest(DESIGN / "manifest.json"),
            "evaluator": digest(Path(__file__).resolve()),
            "supervisor_inputs": digest(SUPERVISOR / "input_sha256.tsv"),
        },
    }
    (OUTPUT / "evaluation.json").write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint = {
        "schema": "lbs.stage31a-packing-replication-bridge.v1.checkpoint",
        "passed": passed,
        "evaluation_sha256": digest(OUTPUT / "evaluation.json"),
        "case_result_sha256": {case["packing_id"]: case["result_sha256"] for case in cases},
        "case_checkpoint_sha256": {case["packing_id"]: case["checkpoint_sha256"] for case in cases},
    }
    (OUTPUT / "checkpoint_manifest.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "status": evaluation["status"], "summary": evaluation["summary"]}, sort_keys=True))
    if not passed:
        raise SystemExit(4)


if __name__ == "__main__":
    main()

