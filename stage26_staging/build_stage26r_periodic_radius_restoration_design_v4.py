from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_03" / "config.json"
SETTERS = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "cell_setter_probe_04" / "probe.json"
SMOKE2 = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "fixed_cell_smoke_02" / "result.json"
SMOKE3_FAILURE = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "fixed_cell_smoke_03" / "failure.json"
SMOKE_RUNNER = ROOT / "stage26_staging" / "run_stage26r_fixed_cell_smoke_v3.py"
OUT = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_04"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict:
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Design04 exists")
    cfg = deepcopy(json.loads(BASE.read_text(encoding="utf-8")))
    setters = json.loads(SETTERS.read_text(encoding="utf-8"))
    failure = json.loads(SMOKE3_FAILURE.read_text(encoding="utf-8"))
    if setters.get("status") != "completed_no_step_setter_probe":
        raise RuntimeError("setter probe incomplete")
    if setters["attempts"]["nextVelGrad"]["writable"] is not False or setters["attempts"]["prevVelGrad"]["writable"] is not False:
        raise RuntimeError("setter probe does not support synchronization correction")
    if failure.get("simulation_steps_executed") != 0:
        raise RuntimeError("Smoke03 failure was not pre-step")
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["sources"]["cell_setter_probe"] = binding(SETTERS)
    cfg["sources"]["fixed_cell_smoke_02"] = binding(SMOKE2)
    cfg["sources"]["fixed_cell_smoke_03_failure"] = binding(SMOKE3_FAILURE)
    cfg["sources"]["fixed_cell_smoke_runner_v3"] = binding(SMOKE_RUNNER)
    cfg["integration_correction"] = {
        "correction": "disable controller; schedule velGrad zero; take one synchronization step; restore exact loaded hSize and body coordinates; then begin the fixed-cell hold",
        "diagnosed_api_semantics": "velGrad assignment is deferred; nextVelGrad and prevVelGrad are read-only in YADE 2022.01a",
        "boundary_condition_changed": False,
        "physics_changed": False,
        "acceptance_gates_changed": False,
        "requires_fixed_cell_smoke": True,
    }
    cfg["authority"]["clean_radius_restoration_authorized"] = False
    cfg["authority"]["zero_cell_history_smoke_authorized"] = False
    cfg["authority"]["synchronized_cell_restore_smoke_authorized"] = True
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
