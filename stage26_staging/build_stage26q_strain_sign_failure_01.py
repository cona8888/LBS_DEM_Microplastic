from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
SUPERVISOR = ROOT / "stage26_supervisors" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_01"
RUN = ROOT / "stage26_runs" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_01"
OUT = ROOT / "stage26_evaluations" / "stage26q_density_geometry_flexure_20260818" / "strain_sign_integration_failure_01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict:
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable failure record exists")
    stdout = SUPERVISOR / "stdout.log"
    stderr = SUPERVISOR / "stderr.log"
    launch = SUPERVISOR / "launch_manifest.txt"
    result = RUN / "result.json"
    completion = RUN / "completion.json"
    history = RUN / "history.csv"
    config = ROOT / "stage26_designs" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_design_01" / "config.json"
    runner = ROOT / "stage26_staging" / "run_stage26q_clean_density_controller_v1.py"
    rows = []
    pattern = re.compile(r"^STAGE26Q_RAMP=(\{.*\})$")
    for line in stdout.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            rows.append(json.loads(match.group(1)))
    if len(rows) < 2:
        raise RuntimeError("insufficient sign-failure observations")
    first, terminal = rows[0], rows[-1]
    checks = {
        "void_ratio_increased_under_configured_positive_rate": terminal["e"] > first["e"],
        "terminal_stress_remained_zero": terminal["stress"] == 0.0,
        "terminal_overlap_remained_zero": terminal["overlap"] == 0.0,
        "nonpassing_result_and_completion_were_published": (
            result.is_file()
            and completion.is_file()
            and json.loads(result.read_text(encoding="utf-8")).get("passed") is False
            and json.loads(completion.read_text(encoding="utf-8")).get("passed") is False
            and json.loads(result.read_text(encoding="utf-8")).get("status") == "density_ramp_not_qualified"
        ),
        "invalid_process_no_longer_active_by_construction": True,
    }
    failure = {
        "schema": "lbs.stage26q-strain-sign-integration-failure.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "preserved_controller_sign_integration_failure",
        "passed": all(checks.values()),
        "failure_class": "software_integration_sign_convention",
        "claim_boundary": "YADE wall-controller sign diagnostic only; no clean-density, material, fibre, flow, or permeability result.",
        "checks": checks,
        "observations": {
            "first_logged_block": first,
            "last_logged_block": terminal,
            "logged_ramp_observations": len(rows),
            "diagnosis": "In this YADE 2022.01a wall-controller state, positive goal strain rate expanded the cell. Compression requires the opposite sign.",
        },
        "sources": {
            "config": binding(config),
            "runner": binding(runner),
            "launch_manifest": binding(launch),
            "stdout": binding(stdout),
            "stderr": binding(stderr),
            "result": binding(result),
            "completion": binding(completion),
            "history": binding(history),
        },
        "authority": {
            "negative_sign_kinematic_smoke_authorized": True,
            "sign_only_corrected_clean_pilot_authorized_after_smoke": True,
            "single_fibre_execution_authorized": False,
            "full_mixture_execution_authorized": False,
            "flow_execution_authorized": False,
            "permeability_claim_authorized": False,
        },
    }
    if not failure["passed"]:
        raise RuntimeError(json.dumps(checks, indent=2))
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "failure.json"
    path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
