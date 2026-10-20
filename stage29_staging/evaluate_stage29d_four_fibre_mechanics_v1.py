from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29d_shared_pair_context_qualification_20260825"
RUN = ROOT / "stage29_runs" / STUDY / "mechanics_01"
CONFIG = ROOT / "stage29_designs" / STUDY / "mechanics_preflight_01" / "config.json"
RUNNER = ROOT / "stage29_designs" / STUDY / "mechanics_runner_01" / "run_stage29d_four_fibre_mechanics_v1.py"
HANDOFF = ROOT / "stage29_evaluations" / STUDY / "mechanics_release_01" / "handoff.json"
GEOMETRY_AUDIT = ROOT / "stage29_evaluations" / STUDY / "candidate_geometry_audit_01" / "geometry_audit.json"
OUT = ROOT / "stage29_evaluations" / STUDY / "mechanics_evaluation_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def windows_path(wsl_path: str) -> Path:
    if not wsl_path.startswith("/mnt/c/"):
        raise ValueError(wsl_path)
    return Path("C:/" + wsl_path[len("/mnt/c/"):])


def edge_strings(edges: list[list[int]]) -> list[str]:
    return sorted(f"{min(a,b)}-{max(a,b)}" for a, b in edges)


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    result_path, completion_path = RUN / "result.json", RUN / "completion.json"
    config = json.loads(CONFIG.read_text())
    handoff = json.loads(HANDOFF.read_text())
    geometry_audit = json.loads(GEOMETRY_AUDIT.read_text())
    result = json.loads(result_path.read_text())
    completion = json.loads(completion_path.read_text())
    cases = result["cases"]
    case_checks = {}
    maxima = {"penetration_over_radius": 0.0, "context_path_rms_over_diameter": 0.0, "contact_force_n": 0.0, "hold_drift_m": 0.0, "hold_speed_m_s": 0.0}
    for case in cases:
        cid = case["case_id"]
        case_path = RUN / case["result_artifact"]["path"]
        history_path = RUN / case["history"]["path"]
        saved = json.loads(case_path.read_text())
        with history_path.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        expected = edge_strings(case["expected_contact_edges"])
        checks = {
            "case_artifact_hash": sha(case_path) == case["result_artifact"]["sha256"],
            "history_hash": sha(history_path) == case["history"]["sha256"],
            "saved_case_id": saved["case_id"] == cid,
            "history_nonempty_and_terminal": bool(rows) and float(rows[-1]["time_s"]) >= 0.00524,
            "four_fibres": case["fibre_count"] == 4 and len(case["terminal_fibres"]) == 4,
            "internal_bonds_complete": all(x["terminal_internal_real_bond_count"] == 36 for x in case["terminal_fibres"]),
            "fixed_sand_exact": case["maximum_fixed_sand_displacement_m"] == 0.0,
            "fixed_cell_exact": case["maximum_periodic_cell_change_m"] == 0.0,
            "zero_false_contacts": case["maximum_intrafibre_contact_count"] == 0 and case["maximum_cross_fibre_node_real_interaction_count"] == 0,
            "no_unintended_edges_ever": set(case["ever_contact_edges"]).issubset(set(expected)),
            "terminal_graph_exact": sorted(case["terminal_contact_edges"]) == expected,
            "penetration_guard": case["maximum_penetration_over_fibre_radius"] <= config["acceptance"]["maximum_penetration_over_fibre_radius"],
            "hold_stable": case["maximum_hold_drift_m"] <= config["acceptance"]["maximum_hold_drift_m"] and case["maximum_hold_speed_m_s"] <= config["acceptance"]["maximum_hold_speed_m_s"],
        }
        case_checks[cid] = {"passed": all(checks.values()), "checks": checks, "expected_edges": expected, "terminal_edges": case["terminal_contact_edges"], "ever_edges": case["ever_contact_edges"], "maximum_penetration_over_fibre_radius": case["maximum_penetration_over_fibre_radius"], "maximum_fibre_contact_normal_force_n": case["maximum_fibre_contact_normal_force_n"]}
        maxima["penetration_over_radius"] = max(maxima["penetration_over_radius"], case["maximum_penetration_over_fibre_radius"])
        maxima["contact_force_n"] = max(maxima["contact_force_n"], case["maximum_fibre_contact_normal_force_n"])
        maxima["hold_drift_m"] = max(maxima["hold_drift_m"], case["maximum_hold_drift_m"])
        maxima["hold_speed_m_s"] = max(maxima["hold_speed_m_s"], case["maximum_hold_speed_m_s"])
    for row in result["context_path_match"]:
        maxima["context_path_rms_over_diameter"] = max(maxima["context_path_rms_over_diameter"], row["aligned_terminal_rms_over_fibre_diameter"])
    files = sorted(p.name for p in RUN.iterdir() if p.is_file())
    required = {"result.json", "completion.json"}
    for case in cases:
        required.add(case["result_artifact"]["path"])
        required.add(case["history"]["path"])
    checks = {
        "release_handoff_passed_and_bound": handoff.get("passed") is True and handoff["bindings"]["config_sha256"] == sha(CONFIG) and handoff["bindings"]["runner_sha256"] == sha(RUNNER),
        "geometry_audit_passed": geometry_audit.get("passed") is True,
        "completion_passed": completion.get("passed") is True,
        "completion_binds_result": completion["result"]["sha256"] == sha(result_path),
        "aggregate_source_hashes": result["source_hashes"]["config"] == sha(CONFIG) and result["source_hashes"]["runner"] == sha(RUNNER) and result["source_hashes"]["source_state"] == config["sources"]["source_state"]["sha256"],
        "all_config_sources_still_bound": all(sha(windows_path(v["path"])) == v["sha256"] for k, v in config["sources"].items() if k != "expected_yade_version"),
        "exact_six_cases": len(cases) == 6 and len({x["case_id"] for x in cases}) == 6,
        "all_case_bundles_pass": all(v["passed"] for v in case_checks.values()),
        "all_aggregate_runner_checks_true": all(result["checks"].values()) and all(completion["checks"].values()),
        "context_path_match_within_limit": maxima["context_path_rms_over_diameter"] <= config["acceptance"]["maximum_context_aligned_terminal_rms_over_fibre_diameter"],
        "exact_required_file_set": set(files) == required,
        "no_failure_marker": not any("failure" in name.lower() for name in files),
        "finite_metrics": all(math.isfinite(v) for v in maxima.values()),
        "authority_stops_before_flow": result["authority"]["gpu_flow"] is False and result["authority"]["permeability_claim"] is False and result["authority"]["hydraulic_geometry_design"] is False,
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage29d-four-fibre-mechanics-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_four_fibre_context_mechanics_qualification" if passed else "failed_four_fibre_context_mechanics_qualification",
        "checks": checks,
        "case_checks": case_checks,
        "maxima": maxima,
        "context_path_match": result["context_path_match"],
        "elapsed_wall_s": result["elapsed_wall_s"],
        "bindings": {"result_sha256": sha(result_path), "completion_sha256": sha(completion_path), "config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "release_handoff_sha256": sha(HANDOFF), "geometry_audit_sha256": sha(GEOMETRY_AUDIT)},
        "interpretation": "The one shared crossing-pair mechanism and one shared separated control remain mechanically valid in three distinct two-fibre contexts. The contexts are paired nuisance blocks, not independent crossing-location replicates.",
        "authority": {"rendering": passed, "revise_low_concentration_design": passed, "hydraulic_geometry_design": False, "mechanics_rerun": False, "gpu_flow": False, "permeability_claim": False, "mobile_sand": False, "two_way_coupling": False},
        "next_handoff": {"authorized": "render accepted mechanics evidence and revise/audit the low-concentration hydraulic design using the qualified shared-pair/context structure" if passed else "diagnosis only", "not_authorized": "mechanics rerun, hydraulic geometry execution, GPU flow, permeability claims, mobile sand, or coupling"},
    }
    OUT.mkdir(parents=True)
    ep = OUT / "evaluation.json"
    ep.write_text(json.dumps(evaluation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    checkpoint = {"schema": evaluation["schema"] + ".checkpoint", "passed": passed, "evaluation_sha256": sha(ep), "result_sha256": sha(result_path), "completion_sha256": sha(completion_path), "config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "authority": evaluation["next_handoff"]}
    (OUT / "checkpoint_manifest.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **evaluation}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
