from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_designs" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_design_03" / "config.json"
PRIOR_EVALUATION = ROOT / "stage26_evaluations" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_evaluation_03" / "evaluation.json"
ADDENDUM = ROOT / "stage26_staging" / "STAGE26Q_FRICTION_REDUCTION_ADDENDUM.md"
RUNNER = ROOT / "stage26_staging" / "run_stage26q_clean_density_controller_v2.py"
OUT = ROOT / "stage26_designs" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_design_04"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Design04 exists")
    base = json.loads(BASE.read_text(encoding="utf-8"))
    evaluation = json.loads(PRIOR_EVALUATION.read_text(encoding="utf-8"))
    if evaluation.get("passed") is not False or evaluation.get("status") != "clean_density_controller_not_accepted":
        raise RuntimeError("prior attempt is not an independently preserved nonacceptance")
    terminal = evaluation["terminal"]
    if not (
        float(terminal["unbalanced_force"]) <= 1.0e-3
        and float(terminal["normalized_kinetic_energy_pV"]) <= 1.0e-5
        and float(terminal["maximum_interobject_penetration_over_smaller_radius"]) >= 0.05
    ):
        raise RuntimeError("prior evidence does not support friction-lock diagnosis")
    cfg = deepcopy(base)
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["preparation_friction"] = {
        "role": "temporary_specimen_preparation_control_not_material_calibration",
        "coefficient_during_density_ramp": 0.30,
        "coefficient_restored_before_fixed_volume_hold": 0.60,
        "wall_friction_coefficient": 0.0,
        "automatic_second_level_authorized": False,
    }
    cfg["sources"]["runner"] = {"path": str(RUNNER), "sha256": sha256(RUNNER)}
    cfg["sources"]["friction_reduction_addendum"] = {"path": str(ADDENDUM), "sha256": sha256(ADDENDUM)}
    cfg["sources"]["prior_nonacceptance_evaluation"] = {"path": str(PRIOR_EVALUATION), "sha256": sha256(PRIOR_EVALUATION)}
    cfg["sources"]["design03_config"] = {"path": str(BASE), "sha256": sha256(BASE)}
    cfg["authority"]["clean_density_controller_mu_prep_030_attempt_authorized"] = True
    cfg["authority"]["lower_preparation_friction_attempt_authorized"] = False
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
