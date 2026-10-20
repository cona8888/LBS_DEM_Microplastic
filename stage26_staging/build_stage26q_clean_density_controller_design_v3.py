from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_designs" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_design_02" / "config.json"
SMOKE = ROOT / "stage26_runs" / "stage26q_density_geometry_flexure_20260818" / "negative_sign_smoke_02" / "result.json"
SMOKE_RUNNER = ROOT / "stage26_staging" / "run_stage26q_negative_strain_sign_smoke_v1.py"
OUT = ROOT / "stage26_designs" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_design_03"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Design03 exists")
    base = json.loads(BASE.read_text(encoding="utf-8"))
    smoke = json.loads(SMOKE.read_text(encoding="utf-8"))
    if smoke.get("passed") is not True or smoke.get("authority", {}).get("sign_only_corrected_clean_pilot_authorized") is not True:
        raise RuntimeError("negative-sign smoke did not authorize the corrected pilot")
    cfg = deepcopy(base)
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["integration_correction"]["negative_sign_kinematic_smoke_passed"] = True
    cfg["sources"]["design02_config"] = {"path": str(BASE), "sha256": sha256(BASE)}
    cfg["sources"]["negative_sign_smoke"] = {"path": str(SMOKE), "sha256": sha256(SMOKE)}
    cfg["sources"]["negative_sign_smoke_runner"] = {"path": str(SMOKE_RUNNER), "sha256": sha256(SMOKE_RUNNER)}
    cfg["authority"]["negative_sign_kinematic_smoke_authorized"] = False
    cfg["authority"]["clean_density_controller_pilot_authorized_after_smoke"] = False
    cfg["authority"]["clean_density_controller_pilot_authorized"] = True
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
