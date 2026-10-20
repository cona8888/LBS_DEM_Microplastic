"""Prospective flow-aware adapter for the frozen shape/flow comparison.

This only corrects flow-field selection relative to the existing run_local
helper. Physical validity of scaling the archived LBM field is a separate gate.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage89_staging"))
import verify_short_seed_local_v1 as h

PROTOCOL = ROOT / "stage109_designs/shape_flow_protocol_20260914/protocol.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(seed, sample_id, shape, flow_factor):
    protocol = json.loads(PROTOCOL.read_text())
    completion = json.loads(PROTOCOL.with_name("completion.json").read_text())
    if sha(PROTOCOL) != completion["protocol_sha256"]:
        raise RuntimeError("frozen protocol drift")
    for section in ("source_hashes", "input_hashes"):
        for path, digest in protocol[section].items():
            if sha(path) != digest:
                raise RuntimeError(f"frozen input/source drift: {path}")
    seed, sample_id = int(seed), int(sample_id)
    flow_factor = float(flow_factor)
    if seed not in (1, 2, 3) or shape not in protocol["shapes"]:
        raise ValueError("unsupported packing or shape")
    if flow_factor not in protocol["flow"]["candidate_factors"]:
        raise ValueError("unfrozen flow factor")
    if sample_id not in ([protocol["population"]["stage_b_sentinel_ids"][str(seed)]]
                         + protocol["population"]["pilot_ids"][str(seed)]):
        raise ValueError("sample not in frozen Stage B/pilot design")
    starts_path = ROOT / f"stage95_designs/common_admissible_population_01/starts_s{seed}.json"
    starts = json.loads(starts_path.read_text())
    start = starts[sample_id]
    if start["id"] != sample_id:
        raise RuntimeError("population ID/order drift")
    config = copy.deepcopy(json.loads(h.DESIGN.read_text()))
    target = protocol["flow"]["reference_u0_m_s"] * flow_factor
    config["target_mean_interstitial_velocity_m_s"] = target
    if shape == "equal_volume_sphere":
        config["prolate_semiaxes_m"] = [protocol["equal_volume_sphere_radius_m"]] * 3
    else:
        config["prolate_semiaxes_m"] = protocol["prolate_semiaxes_m"]
    if (config["particle_density_kg_m3"] != protocol["particle_density_kg_m3"]
            or config["dynamic_viscosity_Pa_s"] != protocol["fluid"]["dynamic_viscosity_Pa_s"]
            or config["fluid_density_kg_m3"] != protocol["fluid"]["density_kg_m3"]
            or config["friction_coefficient"] != protocol["friction_coefficient"]):
        raise RuntimeError("frozen material parameter drift")
    state = {"position_m": start["position_m"],
             "orientation": start["orientation"],
             "velocity_generalized": start["initial_velocity_generalized"]}
    return config, state


def run_local(module, config, previous, seed, horizon, budget):
    """Call the unchanged transport integrator with the requested mean flow."""
    target = config["target_mean_interstitial_velocity_m_s"]
    field, old_geometry, length, _, _ = h.matrix_case_v1.load(
        seed, target_velocity=target)
    actual = float(field.u[0, field.fluid].mean())
    if abs(actual - target) > max(1e-15, 1e-10 * target):
        raise RuntimeError("loaded mean flow differs from requested mean flow")
    geometry = h.geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    a, b, _ = config["prolate_semiaxes_m"]
    return module.integrate(
        field, geometry, previous["position_m"], previous["orientation"],
        previous["velocity_generalized"], a, b,
        config["dynamic_viscosity_Pa_s"], config["particle_density_kg_m3"],
        config["fluid_density_kg_m3"], config["gravity_m_s2"],
        config["friction_coefficient"], length, horizon,
        added_mass_fraction=config["added_mass_fraction"],
        cutoff_ratio=0.2, roughness_ratio=0.01,
        displacement_fraction=config["numerics"]["displacement_fraction"],
        relaxation_fraction=config["numerics"]["relaxation_fraction"],
        angle_limit=config["numerics"]["angle_limit_rad"],
        max_dt=config["numerics"]["max_dt_s"], wall_budget=budget,
        trap_reference_speed=target,
        trap_dwell_time=config["trap"]["dwell_time_s"],
        trap_speed_ratio=config["trap"]["speed_ratio"],
        trap_drift_over_minor_radius=config["trap"]["drift_over_minor_radius"],
        stop_on_trap=config["trap"]["absorbing"],
        reynolds_limit=config["numerics"]["reynolds_limit"])
