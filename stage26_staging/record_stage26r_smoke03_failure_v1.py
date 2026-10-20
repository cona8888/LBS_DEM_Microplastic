from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "fixed_cell_smoke_03"
CONFIG = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_03" / "config.json"
RUNNER = ROOT / "stage26_staging" / "run_stage26r_fixed_cell_smoke_v2.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = OUT / "failure.json"
    if path.exists():
        raise RuntimeError("immutable smoke03 failure already exists")
    payload = {
        "schema": "lbs.stage26r-fixed-periodic-cell-smoke.v2.failure",
        "status": "failed_before_simulation_step_preserved",
        "passed": False,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "failure_class": "YADE Cell API writeability mismatch",
        "failure": "AttributeError: can't set attribute O.cell.nextVelGrad",
        "simulation_steps_executed": 0,
        "interpretation": "YADE exposes nextVelGrad for inspection but not assignment. A read-only setter probe is required before another kinematic smoke.",
        "sources": {
            "config": {"path": str(CONFIG), "sha256": sha256(CONFIG)},
            "runner": {"path": str(RUNNER), "sha256": sha256(RUNNER)},
        },
        "authority": {
            "cell_setter_probe_authorized": True,
            "clean_radius_restoration_authorized": False,
            "fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
