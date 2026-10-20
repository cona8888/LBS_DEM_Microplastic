"""Stage26o adapter with phase gates and fixed-volume final relaxation."""
from __future__ import print_function

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(os.environ.get("STAGE26O_CONTROL_SCRIPT", __file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
CORE_PATH = os.path.join(HERE, "run_stage26o_clean_sand_control_v1.py")
SPEC = importlib.util.spec_from_file_location("stage26o_control_core_v1", CORE_PATH)
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)
for symbol, value in list(globals().items()):
    if not symbol.startswith("__") and symbol not in {"core", "SPEC"}:
        core.__dict__.setdefault(symbol, value)

_strict_final_gate = core.final_gate
_final_hold_walls_frozen = False


def phase_aware_gate(row, cfg):
    global _final_hold_walls_frozen
    checks = _strict_final_gate(row, cfg)
    if row.get("phase") == "gravity_plus_wall_confinement":
        limits = cfg["confinement_transition"]
        checks["mean_stress"] = row["relative_mean_wall_stress_error"] <= limits["maximum_relative_mean_wall_stress_error"]
        checks["principal_stress"] = row["maximum_principal_wall_stress_error"] <= limits["maximum_principal_wall_stress_error"]
        checks["unbalanced_force"] = row["unbalanced_force"] <= limits["maximum_unbalanced_force"]
        checks["normalized_kinetic_energy"] = row["normalized_kinetic_energy_pV"] <= limits["maximum_normalized_kinetic_energy_pV"]
    elif row.get("phase") == "zero_gravity_final_hold" and not _final_hold_walls_frozen:
        controllers = [engine for engine in core.O.engines if isinstance(engine, core.TriaxialStressController)]
        if len(controllers) != 1:
            raise RuntimeError("expected exactly one triaxial controller before fixed-volume hold")
        controllers[0].dead = True
        _final_hold_walls_frozen = True
    return checks


core.final_gate = phase_aware_gate

if __name__ == "__main__":
    core.main()
