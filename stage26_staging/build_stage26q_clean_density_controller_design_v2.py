from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_designs" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_design_01" / "config.json"
FAILURE = ROOT / "stage26_evaluations" / "stage26q_density_geometry_flexure_20260818" / "strain_sign_integration_failure_01" / "failure.json"
OUT = ROOT / "stage26_designs" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_design_02"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Design02 exists")
    base = json.loads(BASE.read_text(encoding="utf-8"))
    failure = json.loads(FAILURE.read_text(encoding="utf-8"))
    if failure.get("passed") is not True or failure.get("authority", {}).get("negative_sign_kinematic_smoke_authorized") is not True:
        raise RuntimeError("sign failure does not authorize correction")
    cfg = deepcopy(base)
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["density_ramp"]["isotropic_compressive_strain_rate_per_s"] = -0.10
    cfg["integration_correction"] = {
        "classification": "YADE_2022.01a_wall_strain_rate_sign_only",
        "previous_value_per_s": 0.10,
        "corrected_value_per_s": -0.10,
        "physics_changed": False,
        "acceptance_gates_changed": False,
        "input_state_changed": False,
        "runner_changed": False,
        "requires_negative_sign_kinematic_smoke_before_full_execution": True,
    }
    cfg["sources"]["design01_config"] = {"path": str(BASE), "sha256": sha256(BASE)}
    cfg["sources"]["strain_sign_failure"] = {"path": str(FAILURE), "sha256": sha256(FAILURE)}
    cfg["authority"]["clean_density_controller_pilot_authorized"] = False
    cfg["authority"]["negative_sign_kinematic_smoke_authorized"] = True
    cfg["authority"]["clean_density_controller_pilot_authorized_after_smoke"] = True
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
