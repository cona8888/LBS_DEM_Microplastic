from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_01" / "config.json"
FAILURE = ROOT / "stage26_evaluations" / "stage26r_periodic_radius_restoration_20260819" / "cell_drift_integration_failure_01" / "failure.json"
RUNNER = ROOT / "stage26_staging" / "run_stage26r_periodic_radius_restoration_v2.py"
OUT = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_02"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Design02 exists")
    cfg = deepcopy(json.loads(BASE.read_text(encoding="utf-8")))
    failure = json.loads(FAILURE.read_text(encoding="utf-8"))
    if failure.get("passed") is not True or failure.get("authority", {}).get("zero_cell_velocity_gradient_smoke_authorized") is not True:
        raise RuntimeError("cell-drift failure does not authorize correction")
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["sources"]["runner"] = {"path": str(RUNNER), "sha256": sha256(RUNNER)}
    cfg["sources"]["cell_drift_failure"] = {"path": str(FAILURE), "sha256": sha256(FAILURE)}
    cfg["sources"]["design01_config"] = {"path": str(BASE), "sha256": sha256(BASE)}
    cfg["integration_correction"] = {
        "correction": "set O.cell.velGrad to Matrix3.Zero after disabling PeriTriaxController",
        "boundary_condition_changed": False,
        "physics_changed": False,
        "acceptance_gates_changed": False,
        "requires_fixed_cell_smoke": True,
    }
    cfg["authority"]["clean_radius_restoration_authorized"] = False
    cfg["authority"]["zero_cell_velocity_gradient_smoke_authorized"] = True
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
