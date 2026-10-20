"""Stage26o direct-reaction runner with active stress servo in final hold."""
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

_base_load_json = core.load_json
_base_diagnostic = core.diagnostic
_strict_final_gate = core.final_gate


def physical_target_load_json(path):
    cfg = _base_load_json(path)
    cfg["confinement"]["target_mean_wall_stress_pa_compression_positive"] = float(cfg["confinement"]["controller_internal_target_pa"])
    return cfg


def direct_reaction_diagnostic(record, phase, phase_index, cfg, triax, sand_ids, solid_volume, total_weight):
    row = _base_diagnostic(record, phase, phase_index, cfg, triax, sand_ids, solid_volume, total_weight)
    dx, dy, dz = row["wall_dimensions_m"]
    stresses = [abs(float(core.O.forces.f(triax.wall_right_id)[0])) / (dy * dz), abs(float(core.O.forces.f(triax.wall_top_id)[1])) / (dx * dz), abs(float(core.O.forces.f(triax.wall_front_id)[2])) / (dx * dy)]
    target = float(cfg["confinement"]["physical_reaction_target_pa"])
    mean = sum(stresses) / 3.0
    row["principal_wall_stress_pa_compression_positive"] = stresses
    row["mean_wall_stress_pa_compression_positive"] = mean
    row["relative_mean_wall_stress_error"] = abs(mean - target) / target
    row["maximum_principal_wall_stress_error"] = max(abs(value - target) / target for value in stresses)
    return row


def phase_aware_gate(row, cfg):
    checks = _strict_final_gate(row, cfg)
    if row.get("phase") == "gravity_plus_wall_confinement":
        limits = cfg["confinement_transition"]
        checks["mean_stress"] = row["relative_mean_wall_stress_error"] <= limits["maximum_relative_mean_wall_stress_error"]
        checks["principal_stress"] = row["maximum_principal_wall_stress_error"] <= limits["maximum_principal_wall_stress_error"]
        checks["unbalanced_force"] = row["unbalanced_force"] <= limits["maximum_unbalanced_force"]
        checks["normalized_kinetic_energy"] = row["normalized_kinetic_energy_pV"] <= limits["maximum_normalized_kinetic_energy_pV"]
    return checks


core.load_json = physical_target_load_json
core.diagnostic = direct_reaction_diagnostic
core.final_gate = phase_aware_gate

if __name__ == "__main__":
    core.main()
