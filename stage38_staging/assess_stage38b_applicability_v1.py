import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage37_staging"))
sys.path.insert(0, str(ROOT / "stage38_staging"))
import transport_contact as stokes
import finite_re_relaxation_v2 as finite_re


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paths(seed):
    case = f"s31b_n216_s{seed}_clean"
    geometry = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01" / case / "geometry_cpd2.npz"
    run = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01" / f"stage31e_{case}_cpd2"
    return geometry, run / "final_fields.npz", run / "record.json"


def terminal_speed(force, resistance, rho_f, mu, diameter, phi):
    function = lambda speed: finite_re.inertial_multiplier(rho_f * speed * diameter / mu, phi) * resistance * speed - force
    high = force / resistance
    return brentq(function, 0.0, max(10 * high, 1e-9), xtol=1e-15)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    a, b = 0.0002, 0.00005
    rho_f, rho_pet, mu, gravity = 998.2, 1380.0, 0.001002, 9.80665
    target_mean = 0.0001
    volume = 4 * np.pi * a * b * b / 3
    mass = rho_pet * volume
    displaced_mass = rho_f * volume
    diameter = 2 * (a * b * b) ** (1 / 3)
    phi = finite_re.prolate_sphericity(a, b)
    rt, _rr = stokes.resistance_axes(a, b, mu)
    net_weight = (rho_pet - rho_f) * volume * gravity
    settling = {}
    for label, resistance in (("major_axis_vertical", rt[0]), ("minor_axis_vertical", rt[1])):
        speed = terminal_speed(net_weight, resistance, rho_f, mu, diameter, phi)
        reynolds = rho_f * speed * diameter / mu
        settling[label] = {
            "terminal_speed_m_s": speed,
            "reynolds": reynolds,
            "finite_re_multiplier": finite_re.inertial_multiplier(reynolds, phi),
            "stokes_response_time_s": mass / resistance,
            "response_time_with_half_displaced_added_mass_s": (mass + 0.5 * displaced_mass) / resistance,
        }
    sphere_radius = diameter / 2
    sphere_resistance = 6 * np.pi * mu * sphere_radius
    sphere_speed = terminal_speed(net_weight, sphere_resistance, rho_f, mu, diameter, 1.0)
    settling["equal_volume_sphere"] = {
        "terminal_speed_m_s": sphere_speed,
        "reynolds": rho_f * sphere_speed * diameter / mu,
        "finite_re_multiplier": finite_re.inertial_multiplier(rho_f * sphere_speed * diameter / mu, 1.0),
        "stokes_response_time_s": mass / sphere_resistance,
        "response_time_with_half_displaced_added_mass_s": (mass + 0.5 * displaced_mass) / sphere_resistance,
    }

    packings = []
    input_hashes = {}
    for seed in (1, 2, 3):
        geometry_path, field_path, record_path = paths(seed)
        record = json.loads(record_path.read_text())
        if not record.get("passed") or not record.get("converged"):
            raise RuntimeError(f"unaccepted archived field for seed {seed}")
        if sha(field_path) != record["artifacts"]["final_fields_npz_sha256"]:
            raise RuntimeError(f"field hash mismatch for seed {seed}")
        geometry = np.load(geometry_path)
        field = np.load(field_path)
        phase = np.asarray(field["phase"])
        velocity = np.asarray(field["velocity_xyz_lu"], float)
        fluid = phase == 0
        mean_x = float(velocity[0][fluid].mean())
        physical = velocity * (target_mean / mean_x)
        speed = np.linalg.norm(physical, axis=0)[fluid]
        spacing = float(geometry["spacing_m"][0])
        local_max = float(speed.max())
        longest_response = max(row["response_time_with_half_displaced_added_mass_s"] for row in settling.values())
        combined_speed = local_max + max(row["terminal_speed_m_s"] for row in settling.values())
        packings.append({
            "seed": seed,
            "spacing_m": spacing,
            "speed_quantiles_m_s": {str(q): float(np.quantile(speed, q)) for q in (0.5, 0.95, 0.99, 1.0)},
            "max_fluid_reynolds_equivalent_diameter": rho_f * local_max * diameter / mu,
            "conservative_cell_stokes_number": longest_response * combined_speed / spacing,
            "particle_length_over_cell": 2 * a / spacing,
            "equivalent_diameter_over_cell": diameter / spacing,
        })
        for path in (geometry_path, field_path, record_path):
            input_hashes[str(path.resolve())] = sha(path)
    max_re = max([row["max_fluid_reynolds_equivalent_diameter"] for row in packings] + [row["reynolds"] for row in settling.values()])
    max_cell_st = max(row["conservative_cell_stokes_number"] for row in packings)
    checks = {
        "all_archived_inputs_hash_bound": len(input_hashes) == 9,
        "finite_re_correlation_within_verified_re_range": max_re <= 3.0,
        "translational_relaxation_cell_stokes_le_0p1": max_cell_st <= 0.1,
        "particle_spans_multiple_flow_cells": min(row["particle_length_over_cell"] for row in packings) >= 3.0,
    }
    source_paths = [Path(__file__), Path(finite_re.__file__), Path(finite_re.base.__file__), Path(stokes.__file__)]
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "settling": settling,
        "packings": packings,
        "max_reynolds": max_re,
        "max_conservative_cell_stokes_number": max_cell_st,
        "decision": "translational inertia is a bounded correction at the archived flow scale; retain semi-implicit relaxation, but do not claim orientation-resolved finite-Re torque or history-force validation",
        "input_hashes": input_hashes,
        "source_hashes": {str(path.resolve()): sha(path) for path in source_paths},
        "claim_boundary": "applicability assessment only; no matrix release execution",
    }
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "settling": settling, "packings": packings}, indent=2))


if __name__ == "__main__":
    main()
