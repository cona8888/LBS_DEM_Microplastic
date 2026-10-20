from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "clean_radius_restoration_01"
SUP = ROOT / "stage26_supervisors" / "stage26r_periodic_radius_restoration_20260819" / "clean_radius_restoration_01"
OUT = ROOT / "stage26_evaluations" / "stage26r_periodic_radius_restoration_20260819" / "cell_drift_integration_failure_01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict:
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable failure output exists")
    result_path = RUN / "result.json"
    completion_path = RUN / "completion.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    terminal = result["terminal"]
    checks = {
        "run_nonpassing": result.get("passed") is False,
        "fixed_cell_status_not_qualified": result.get("status") == "fixed_cell_hold_not_qualified",
        "radii_recovered_exactly": float(terminal["maximum_relative_radius_error"]) <= 1.0e-12,
        "cell_drift_exceeded_gate": float(terminal["maximum_relative_cell_dimension_change"]) > 1.0e-12,
        "stress_invalidated_by_cell_drift": float(terminal["mean_stress_pa_compression_positive"]) > 1000.0,
        "state_otherwise_quiet": float(terminal["unbalanced_force"]) <= 1.0e-3 and float(terminal["normalized_kinetic_energy_pV"]) <= 1.0e-7,
    }
    data = {
        "schema": "lbs.stage26r-periodic-cell-drift-integration-failure.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "preserved_periodic_cell_velocity_gradient_failure",
        "passed": all(checks.values()),
        "failure_class": "software_integration_boundary_state",
        "checks": checks,
        "diagnosis": "PeriTriaxController.dead stopped controller updates but the loaded O.cell.velGrad remained nonzero, so the purported fixed cell continued shrinking.",
        "claim_boundary": "Boundary-state integration failure only; no accepted radius-restoration, fibre, flow, or permeability result.",
        "terminal": terminal,
        "sources": {
            "result": bind(result_path),
            "completion": bind(completion_path),
            "history": bind(RUN / "history.csv"),
            "launch_manifest": bind(SUP / "launch_manifest.txt"),
            "stdout": bind(SUP / "stdout.log"),
            "stderr": bind(SUP / "stderr.log"),
        },
        "authority": {
            "zero_cell_velocity_gradient_smoke_authorized": True,
            "boundary_only_corrected_clean_rerun_authorized_after_smoke": True,
            "fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "permeability_claim_authorized": False,
        },
    }
    if not data["passed"]:
        raise RuntimeError(json.dumps(checks, indent=2))
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "failure.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
