from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_04" / "config.json"
SMOKE = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "fixed_cell_smoke_04" / "result.json"
RUNNER = ROOT / "stage26_staging" / "run_stage26r_periodic_radius_restoration_v3.py"
OUT = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_05"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict:
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Design05 exists")
    cfg = deepcopy(json.loads(BASE.read_text(encoding="utf-8")))
    smoke = json.loads(SMOKE.read_text(encoding="utf-8"))
    if smoke.get("passed") is not True:
        raise RuntimeError("fixed-cell smoke did not pass")
    if smoke.get("authority", {}).get("boundary_only_corrected_clean_rerun_authorized") is not True:
        raise RuntimeError("fixed-cell smoke does not authorize a clean rerun")
    required = (
        "exact_cell_restored_before_hold",
        "cell_unchanged_after_restore",
        "synchronized_velocity_gradient_zero",
        "synchronized_previous_velocity_gradient_zero",
    )
    if not all(smoke.get("checks", {}).get(name) is True for name in required):
        raise RuntimeError("fixed-cell smoke lacks required checks")
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["sources"]["runner"] = binding(RUNNER)
    cfg["sources"]["fixed_cell_smoke"] = binding(SMOKE)
    cfg["sources"]["design04_config"] = binding(BASE)
    cfg["integration_correction"] = {
        "correction": "disable controller; schedule velGrad zero; take one synchronization step; restore exact loaded hSize and body coordinates; then begin radius restoration at fixed cell",
        "verification": "passed strict 5000-step fixed-cell smoke with zero terminal relative cell change",
        "boundary_condition_changed": False,
        "physics_changed": False,
        "acceptance_gates_changed": False,
    }
    cfg["authority"]["clean_radius_restoration_authorized"] = True
    cfg["authority"]["synchronized_cell_restore_smoke_authorized"] = False
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
