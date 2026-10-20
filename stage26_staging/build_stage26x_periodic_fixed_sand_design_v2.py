import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_design_01" / "config.json"
OUT = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_design_02"
RUNNER = ROOT / "stage26_staging" / "run_stage26x_periodic_fixed_sand_fibre_v2.py"
CORE = ROOT / "stage26_staging" / "run_stage26x_periodic_fixed_sand_fibre_v1.py"
FAILURE = ROOT / "stage26_evaluations" / "stage26x_periodic_pore_geometry_20260823" / "cell_sync_integration_failure_01" / "failure.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wsl(path):
    return str(path).replace("C:\\", "/mnt/c/").replace("\\", "/")


if OUT.exists():
    raise RuntimeError("immutable Stage26x Design02 exists")
cfg = json.loads(BASE.read_text(encoding="utf-8"))
failure = json.loads(FAILURE.read_text(encoding="utf-8"))
if failure.get("passed") is not True or failure.get("failure_class") != "software_integration_pending_periodic_cell_update":
    raise RuntimeError("Stage26x integration failure is not preserved")
cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
cfg["schema"] = "lbs.stage26x-periodic-fixed-sand-fibre-design.v2"
cfg["sources"]["design01"] = {"path": wsl(BASE), "sha256": sha(BASE)}
cfg["sources"]["cell_sync_failure"] = {"path": wsl(FAILURE), "sha256": sha(FAILURE)}
cfg["sources"]["core_runner"] = {"path": wsl(CORE), "sha256": sha(CORE)}
cfg["sources"]["runner"] = {"path": wsl(RUNNER), "sha256": sha(RUNNER)}
cfg["integration_correction"] = {
    "classification": "pending_periodic_cell_update_only",
    "correction": "consume one dead-controller zero-velGrad source step, then restore exact loaded cell and sand coordinates before fibre construction",
    "physics_changed": False,
    "placements_changed": False,
    "loading_changed": False,
    "gates_changed": False,
}
OUT.mkdir(parents=True, exist_ok=False)
path = OUT / "config.json"
path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(path)
print(sha(path))
