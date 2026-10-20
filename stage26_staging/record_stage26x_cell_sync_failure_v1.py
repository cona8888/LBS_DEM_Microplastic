import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_evaluations" / "stage26x_periodic_pore_geometry_20260823" / "cell_sync_integration_failure_01"
CONFIG = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_design_01" / "config.json"
RUNNER = ROOT / "stage26_staging" / "run_stage26x_periodic_fixed_sand_fibre_v1.py"
SUPERVISOR = ROOT / "stage26_supervisors" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_pilot_01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if OUT.exists():
    raise RuntimeError("immutable Stage26x failure record exists")
stderr = SUPERVISOR / "stderr.log"
stdout = SUPERVISOR / "stdout.log"
exit_code = SUPERVISOR / "runner_exit_code.txt"
if "periodic cell changed during fixed-source synchronization" not in stderr.read_text(encoding="utf-8"):
    raise RuntimeError("expected synchronization guard is absent")
failure = {
    "schema": "lbs.stage26x-periodic-cell-sync-integration-failure.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "status": "preserved_periodic_cell_synchronization_failure",
    "passed": True,
    "failure_class": "software_integration_pending_periodic_cell_update",
    "finding": "The source checkpoint retained a pending periodic-cell update. The pilot stopped at the exact-cell guard before any fibre loading history or physical result was published.",
    "correction": "Consume one source-state step with the controller dead and velocity gradient zero, restore the exact loaded cell and sand coordinates, then check exact invariance again before fibre loading.",
    "sources": {
        "config": {"path": str(CONFIG), "sha256": sha(CONFIG)},
        "runner": {"path": str(RUNNER), "sha256": sha(RUNNER)},
        "stdout": {"path": str(stdout), "sha256": sha(stdout)},
        "stderr": {"path": str(stderr), "sha256": sha(stderr)},
        "runner_exit_code": {"path": str(exit_code), "sha256": sha(exit_code)},
    },
    "authority": {"corrected_retry_authorized": True, "mobile_sand_execution_authorized": False, "flow_authorized": False, "permeability_claim_authorized": False},
    "claim_boundary": "Periodic source-state synchronization diagnosis only; no fibre mechanics, sand mechanics, flow, or permeability result.",
}
OUT.mkdir(parents=True, exist_ok=False)
path = OUT / "failure.json"
path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
print(path)
print(sha(path))
