from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_02" / "config.json"
API = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "cell_api_probe_03" / "probe.json"
SMOKE1 = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "fixed_cell_smoke_02" / "result.json"
FULL_RUNNER = ROOT / "stage26_staging" / "run_stage26r_periodic_radius_restoration_v2.py"
SMOKE_RUNNER = ROOT / "stage26_staging" / "run_stage26r_fixed_cell_smoke_v2.py"
OUT = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_03"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict:
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Design03 exists")
    cfg = deepcopy(json.loads(BASE.read_text(encoding="utf-8")))
    api = json.loads(API.read_text(encoding="utf-8"))
    smoke1 = json.loads(SMOKE1.read_text(encoding="utf-8"))
    if api.get("status") != "completed_read_only_api_probe":
        raise RuntimeError("cell API probe is not complete")
    if smoke1.get("passed") is not False or smoke1.get("checks", {}).get("terminal_velocity_gradient_zero") is not True:
        raise RuntimeError("Smoke01 does not isolate the residual-history issue")
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["sources"]["runner"] = binding(FULL_RUNNER)
    cfg["sources"]["cell_api_probe"] = binding(API)
    cfg["sources"]["fixed_cell_smoke_01"] = binding(SMOKE1)
    cfg["sources"]["fixed_cell_smoke_runner_v2"] = binding(SMOKE_RUNNER)
    cfg["integration_correction"] = {
        "correction": "after disabling PeriTriaxController, set Cell velGrad, nextVelGrad, and prevVelGrad to Matrix3.Zero and mark velGradChanged",
        "diagnosed_residual": "reloaded prevVelGrad was nonzero while nextVelGrad was already zero",
        "boundary_condition_changed": False,
        "physics_changed": False,
        "acceptance_gates_changed": False,
        "requires_fixed_cell_smoke": True,
    }
    cfg["authority"]["clean_radius_restoration_authorized"] = False
    cfg["authority"]["zero_cell_velocity_gradient_smoke_authorized"] = False
    cfg["authority"]["zero_cell_history_smoke_authorized"] = True
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
