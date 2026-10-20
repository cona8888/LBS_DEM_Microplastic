from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29e_low_concentration_hydraulic_design_20260826"
RUN = ROOT / "stage29_runs" / STUDY / "gpu_screen_01"
CONFIG = ROOT / "stage29_designs" / STUDY / "geometry_01" / "resolved_config.json"
GEOMETRY_COMPLETION = CONFIG.parent / "completion.json"
RUNNER = ROOT / "stage29_staging" / "run_stage29e_low_concentration_cpd2_gpu_v1.py"
HANDOFF = ROOT / "stage29_evaluations" / STUDY / "gpu_release_01" / "execution_handoff.json"
OUT = ROOT / "stage29_evaluations" / STUDY / "hydraulic_evaluation_01"
RESOLUTION_FLOOR = 2.0e-4


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_tree(value: object) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(finite_tree(x) for x in value)
    if isinstance(value, dict):
        return all(finite_tree(x) for x in value.values())
    return False


def mean_sd(values: list[float]) -> dict:
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "sample_standard_deviation": statistics.stdev(values) if len(values) > 1 else None,
        "minimum": min(values),
        "maximum": max(values),
    }


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")

    completion_path = RUN / "completion.json"
    config = load(CONFIG)
    geometry_completion = load(GEOMETRY_COMPLETION)
    handoff = load(HANDOFF)
    completion = load(completion_path)
    rows = sorted(completion["paired_results"], key=lambda x: x["run_order"])

    expected_order = ["clean"] + [
        x["case_id"] for x in sorted(config["geometry"]["cases"], key=lambda x: x["run_order"])
    ]
    observed_order = [x["case_id"] for x in rows]

    lineage_checks = {}
    for name, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            lineage_checks[name] = path.is_file() and sha(path) == binding["sha256"]

    geometry_hash_checks = {
        cid: Path(binding["geometry"]).is_file()
        and sha(Path(binding["geometry"])) == binding["geometry_sha256"]
        for cid, binding in config["geometry"]["artifacts"].items()
    }
    clean_geometry = Path(config["clean_control"]["geometry"])
    geometry_hash_checks["clean"] = clean_geometry.is_file() and sha(clean_geometry) == config["clean_control"]["geometry_sha256"]

    case_checks = {}
    ratios = {}
    for row in rows:
        cid = row["case_id"]
        case_dir = RUN / row["solver_case_id"]
        record_path = case_dir / "record.json"
        record = load(record_path)
        artifact_checks = {}
        artifact_names = {
            "audit_npz_sha256": "audit.npz",
            "final_fields_npz_sha256": "final_fields.npz",
            "final_flow_vtk_sha256": "final_flow.vtk",
            "final_shifted_state_npz_sha256": "final_shifted_state.npz",
        }
        for key, filename in artifact_names.items():
            path = case_dir / filename
            artifact_checks[filename] = path.is_file() and sha(path) == record["artifacts"][key]
        closure = record["exact_equilibrium_closure"]
        closure_exact = all(
            int(v) == 0
            for key, values in closure.items()
            if key.endswith("numerator_xyz")
            for v in values
        )
        checks = {
            "record_hash_bound": record_path.is_file() and sha(record_path) == completion["case_records"][cid] == row["record_sha256"],
            "case_id_bound": record["case_id"] == row["solver_case_id"],
            "cpd2": record["cpd"] == 2,
            "passed_and_converged": record.get("passed") is True and record.get("converged") is True,
            "all_solver_checks_true": all(record.get("checks", {}).values()),
            "numerical_health_zero": all(int(v) == 0 for v in record["numerical_health"].values())
            and record["final"]["fatal_health_code"] == 0
            and record["final"]["full_health_code"] == 0
            and record["final"]["reporting_only_health_code"] == 0,
            "exact_equilibrium_closure": closure_exact,
            "finite_record_values": finite_tree(record),
            "positive_flow_and_permeability": record["final"]["superficial_velocity_lu"] > 0
            and row["conductance_proxy_lu"] > 0
            and row["intrinsic_permeability_m2"] > 0,
            "step_binding": record["steps_completed"] == row["steps_completed"],
            "artifact_hashes": all(artifact_checks.values()),
        }
        case_checks[cid] = {
            "passed": all(checks.values()),
            "checks": checks,
            "artifact_checks": artifact_checks,
            "momentum_residual_relative": record["final"]["momentum_residual_relative"],
            "mach_number": record["metrics"]["mach_number"],
            "reynolds_number_diameter": record["metrics"]["reynolds_number_diameter"],
            "steps_completed": record["steps_completed"],
        }
        ratios[cid] = float(row["paired_permeability_ratio"])

    singles = [ratios[f"s29e_f001_isolated_{b}"] for b in "ABC"]
    zero4 = [ratios[f"s29e_f004_zero_contact_context_{b}"] for b in "ABC"]
    one4 = [ratios[f"s29e_f004_one_contact_context_{b}"] for b in "ABC"]
    paired_contrasts = {
        b: ratios[f"s29e_f004_one_contact_context_{b}"] - ratios[f"s29e_f004_zero_contact_context_{b}"]
        for b in "ABC"
    }
    two_fibre_contrast = ratios["s29e_f002_crossing"] - ratios["s29e_f002_separated"]
    branch_summary = {
        "clean": {"fibre_count": 0, "dry_mass_percent": 0.0, "ratio": ratios["clean"]},
        "single_isolated": {"fibre_count": 1, "dry_mass_percent": config["geometry"]["cases"][0]["achieved_dry_mass_percent"], **mean_sd(singles)},
        "two_fibre_separated": {"fibre_count": 2, "dry_mass_percent": 0.009381481678218612, "ratio": ratios["s29e_f002_separated"]},
        "two_fibre_crossing": {"fibre_count": 2, "dry_mass_percent": 0.009381481678218612, "ratio": ratios["s29e_f002_crossing"]},
        "four_fibre_zero_contact": {"fibre_count": 4, "dry_mass_percent": 0.018761203277589126, **mean_sd(zero4)},
        "four_fibre_one_contact": {"fibre_count": 4, "dry_mass_percent": 0.018761203277589126, **mean_sd(one4)},
    }
    effects = {
        "single_mean_minus_clean": statistics.fmean(singles) - 1.0,
        "separated_pair_minus_single_mean": ratios["s29e_f002_separated"] - statistics.fmean(singles),
        "crossing_minus_separated": two_fibre_contrast,
        "four_zero_mean_minus_separated": statistics.fmean(zero4) - ratios["s29e_f002_separated"],
        "four_one_mean_minus_crossing": statistics.fmean(one4) - ratios["s29e_f002_crossing"],
        "four_one_minus_zero_paired": {**paired_contrasts, "summary": mean_sd(list(paired_contrasts.values()))},
    }
    resolution_classification = {
        key: ("resolved_at_cpd2" if abs(value) >= RESOLUTION_FLOOR else "unresolved_at_cpd2")
        for key, value in effects.items()
        if isinstance(value, float)
    }
    resolution_classification["four_one_minus_zero_paired"] = {
        b: "resolved_at_cpd2" if abs(v) >= RESOLUTION_FLOOR else "unresolved_at_cpd2"
        for b, v in paired_contrasts.items()
    }

    checks = {
        "completion_passed": completion.get("passed") is True and all(completion["checks"].values()),
        "exact_twelve_case_order": len(rows) == 12 and observed_order == expected_order and [x["run_order"] for x in rows] == list(range(12)),
        "config_hash_bound": completion["config_sha256"] == sha(CONFIG) == handoff["bindings"]["config_sha256"],
        "runner_hash_bound": completion["runner_sha256"] == sha(RUNNER) == handoff["bindings"]["runner_sha256"],
        "handoff_hash_bound": completion["handoff_sha256"] == sha(HANDOFF) and handoff.get("passed") is True,
        "geometry_completion_bound": completion["geometry_completion_sha256"] == sha(GEOMETRY_COMPLETION)
        and geometry_completion.get("passed") is True,
        "all_lineage_hashes_current": all(lineage_checks.values())
        and all(completion["lineage_hashes"].get(k) == config["lineage"][k]["sha256"] for k in lineage_checks),
        "all_geometry_hashes_current": all(geometry_hash_checks.values()),
        "all_case_bundles_pass": len(case_checks) == 12 and all(v["passed"] for v in case_checks.values()),
        "clean_ratio_exact": ratios["clean"] == 1.0,
        "no_failure_marker": not any(RUN.rglob("failure.json")),
        "authority_boundary_preserved": completion["authority"]["cpd4"] is False
        and completion["authority"]["permeability_claim"] is False
        and completion["authority"]["mechanics_rerun"] is False
        and completion["authority"]["mobile_sand"] is False
        and completion["authority"]["two_way_coupling"] is False,
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage29e-low-concentration-cpd2-independent-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_independent_cpd2_screen_evaluation" if passed else "failed_independent_cpd2_screen_evaluation",
        "checks": checks,
        "lineage_checks": lineage_checks,
        "geometry_hash_checks": geometry_hash_checks,
        "case_checks": case_checks,
        "branch_summary": branch_summary,
        "effects_k_over_k0": effects,
        "resolution_floor_absolute_k_over_k0": RESOLUTION_FLOOR,
        "resolution_classification": resolution_classification,
        "interpretation": {
            "concentration": "The fixed-packing zero-contact branch is not forced to be monotone; report the raw one- and two-fibre points and the four-fibre block mean.",
            "topology": "Crossing is more obstructive than separated for the unreplicated two-fibre pair, whereas the one-contact four-fibre contexts are less obstructive than their paired zero-contact contexts.",
            "scope": "These are CPD2 static-flow mechanism effects in one fixed 216-grain periodic packing, not a laboratory permeability validation or a population-average concentration law.",
        },
        "bindings": {
            "completion_sha256": sha(completion_path),
            "config_sha256": sha(CONFIG),
            "runner_sha256": sha(RUNNER),
            "handoff_sha256": sha(HANDOFF),
            "geometry_completion_sha256": sha(GEOMETRY_COMPLETION),
        },
        "authority": {
            "rendering": passed,
            "cpd4": False,
            "permeability_validation_claim": False,
            "mechanics_rerun": False,
            "mobile_sand": False,
            "migration": False,
            "clogging": False,
            "two_way_coupling": False,
        },
        "next_handoff": {
            "authorized": "render the independently verified CPD2 screen" if passed else "diagnosis only",
            "not_authorized": "CPD4, permeability validation claims, mechanics reruns, mobile sand, migration, clogging, or coupling",
        },
    }
    OUT.mkdir(parents=True)
    evaluation_path = OUT / "evaluation.json"
    evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    checkpoint = {
        "schema": evaluation["schema"] + ".checkpoint",
        "passed": passed,
        "evaluation_sha256": sha(evaluation_path),
        "completion_sha256": sha(completion_path),
        "config_sha256": sha(CONFIG),
        "runner_sha256": sha(RUNNER),
        "authority": evaluation["next_handoff"],
    }
    (OUT / "checkpoint_manifest.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "passed": passed, "checks": checks, "effects_k_over_k0": effects}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
