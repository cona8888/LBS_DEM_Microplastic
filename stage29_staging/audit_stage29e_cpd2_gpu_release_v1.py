from __future__ import annotations

import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29e_low_concentration_hydraulic_design_20260826"
GEOMETRY = ROOT / "stage29_designs" / STUDY / "geometry_01"
CONFIG = GEOMETRY / "resolved_config.json"
COMPLETION = GEOMETRY / "completion.json"
GEOMETRY_AUDIT = ROOT / "stage29_evaluations" / STUDY / "geometry_audit_01" / "geometry_audit.json"
RUNNER = ROOT / "stage29_staging" / "run_stage29e_low_concentration_cpd2_gpu_v1.py"
OUTPUT_RUN = ROOT / "stage29_runs" / STUDY / "gpu_screen_01"
OUT = ROOT / "stage29_evaluations" / STUDY / "gpu_release_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    config, completion, audit = json.loads(CONFIG.read_text()), json.loads(COMPLETION.read_text()), json.loads(GEOMETRY_AUDIT.read_text())
    py_compile.compile(str(RUNNER), doraise=True)
    text = RUNNER.read_text()
    artifacts = {cid: sha(Path(v["geometry"])) == v["geometry_sha256"] for cid, v in config["geometry"]["artifacts"].items()}
    lineage = {k: Path(v["path"]).is_file() and sha(Path(v["path"])) == v["sha256"] for k, v in config["lineage"].items() if isinstance(v, dict) and "path" in v and "sha256" in v}
    expected_contact_cases = {cid for cid, value in audit["topology"].items() if value["expected_contact"]}
    resolved_contact_cases = {cid for cid, value in audit["topology"].items() if value["resolved_contact"]}
    required_tokens = ("--handoff", "stage29e_cpd2_gpu_execution_authorized", "clean must run first", "twelve_records", "frozen_case_order", "failure.json")
    checks = {"config_fail_closed": config["status"] == "geometry_built_independent_gpu_release_required" and config["authority"]["gpu_execution"] is False, "geometry_completion_bound": completion.get("passed") is True and completion["config_sha256"] == sha(CONFIG), "geometry_audit_passed_and_bound": audit.get("passed") is True and audit["bindings"]["config_sha256"] == sha(CONFIG), "all_expected_contacts_resolved": expected_contact_cases == resolved_contact_cases, "all_geometry_artifacts_bound": all(artifacts.values()), "clean_geometry_bound": sha(Path(config["clean_control"]["geometry"])) == config["clean_control"]["geometry_sha256"], "all_lineage_bound": all(lineage.values()), "runner_compiles": True, "runner_fail_closed_and_complete": all(token in text for token in required_tokens), "solver_is_cpd2": config["geometry"]["fibre_diameter_cells"] >= 1.9 and config["solver"]["maximum_steps"] == 80000, "exact_eleven_new_cases": len(config["geometry"]["cases"]) == 11, "output_absent": not OUTPUT_RUN.exists(), "no_widened_authority": all(config["authority"][k] is False for k in ("cpd4", "permeability_claim", "mechanics_rerun", "mobile_sand", "two_way_coupling"))}
    if not all(checks.values()):
        raise RuntimeError("GPU release failed: " + ", ".join(k for k, v in checks.items() if not v))
    OUT.mkdir(parents=True)
    release = {"schema": "lbs.stage29e-low-concentration-cpd2-gpu-release.v1", "status": "passed_stage29e_cpd2_gpu_release", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": True, "checks": checks, "artifact_checks": artifacts, "lineage_checks": lineage, "bindings": {"config_sha256": sha(CONFIG), "completion_sha256": sha(COMPLETION), "geometry_audit_sha256": sha(GEOMETRY_AUDIT), "runner_sha256": sha(RUNNER)}, "next_handoff": {"authorized": "one immutable clean-plus-eleven-case Stage29e CPD2 GPU execution", "not_authorized": "rerun, CPD4, permeability claims, mechanics rerun, mobile sand, or coupling"}}
    ap = OUT / "release_audit.json"; ap.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n")
    handoff = {"schema": release["schema"] + ".handoff", "status": "stage29e_cpd2_gpu_execution_authorized", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": True, "authority": {"gpu_cpd2_execution": True, "cpd4": False, "permeability_claim": False, "mechanics_rerun": False, "mobile_sand": False, "two_way_coupling": False}, "bindings": {"config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "release_audit_sha256": sha(ap)}, "output": str(OUTPUT_RUN)}
    hp = OUT / "execution_handoff.json"; hp.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUT), "release_sha256": sha(ap), "handoff_sha256": sha(hp), "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
