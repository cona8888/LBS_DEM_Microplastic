"""Stage115 short-time corrected-flow diagnostics; frozen transport core.

Only the SI field loader, achieved-flow PV convention and bound configuration
dispatch change. No contact, resistance, finite-Re, gravity or integration law
is modified. This module has no population-campaign dispatcher.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage114_staging"), str(ROOT / "stage109_staging"), str(ROOT / "stage106_staging")]
import load_stationary_field_v1 as fields
import comparison_case_core_v1 as original_config
import verify_checkpoint_v2 as frozen

PROTOCOL = original_config.PROTOCOL
DESIGN = ROOT / "stage115_designs/corrected_flow_short_time_20260915/design_01.json"
FLOW_COMBINATIONS = [(2, 1., 2), (2, 1., 4), (2, .5, 2), (2, 2., 2), (1, 1., 2), (3, 1., 2)]
REFINEMENTS = [1., .5, .25]
SHAPES = ["equal_volume_sphere", "rigid_prolate_ar4"]
DT_CONTROLS = ["displacement_fraction", "relaxation_fraction", "angle_limit_rad", "max_dt_s"]


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalized(value):
    return json.loads(json.dumps(value, default=frozen.h.json_value, allow_nan=True))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True, default=frozen.h.json_value).encode()).hexdigest()


def write(path, value, *, raw=False):
    encoded = json.dumps(value, indent=2, sort_keys=True, allow_nan=raw, default=frozen.h.json_value) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(encoded)


def verify_mapping(mapping):
    for path, expected in mapping.items():
        require(sha(path) == expected, "source/input drift: " + path)


def verify_design(design):
    require(design.get("binding") == digest({k:v for k,v in design.items() if k != "binding"}), "design self-binding drift")
    require(len(design["cases"]) == 36 and len({c["case_id"] for c in design["cases"]}) == 36, "diagnostic case set changed")
    verify_mapping(design["source_hashes"])
    verify_mapping(design["input_hashes"])


def case_id(seed, factor, cpd, shape, refinement):
    code = "sphere" if shape == SHAPES[0] else "ar4"
    flow = str(factor).replace(".", "p")
    return f"s{seed}_{code}_f{flow}_cpd{cpd}_dt{int(round(1/refinement))}"


def prepare_spec(seed, factor, cpd, shape, refinement, horizon=.25):
    require((seed, factor, cpd) in FLOW_COMBINATIONS and shape in SHAPES and refinement in REFINEMENTS, "unfrozen diagnostic combination")
    protocol = read(PROTOCOL)
    sample_id = protocol["population"]["stage_b_sentinel_ids"][str(seed)]
    config, state = original_config.resolve(seed, sample_id, shape, factor)
    _, _, metadata = fields.load(seed, factor, cpd)
    config = copy.deepcopy(config)
    nominal = config["target_mean_interstitial_velocity_m_s"]
    config["target_mean_interstitial_velocity_m_s"] = metadata["achieved_mean_interstitial_velocity_m_s"]
    for name in DT_CONTROLS:
        config["numerics"][name] *= refinement
    require(0 < horizon <= metadata["two_pore_volume_horizon_s"], "horizon outside corrected 2-PV boundary")
    return {"case_id": case_id(seed, factor, cpd, shape, refinement), "seed": seed, "sample_id": sample_id,
            "flow_factor": factor, "cpd": cpd, "shape": shape, "refinement": refinement,
            "config": config, "initial_state": state, "field_metadata": metadata,
            "nominal_speed_m_s": nominal, "horizon_s": horizon,
            "horizon_pv": horizon * metadata["pv_per_second"]}


def health(result, spec):
    def bounded(key, limit):
        value = result.get(key)
        return isinstance(value, (int,float)) and np.isfinite(value) and 0 <= value <= limit
    b = spec["config"]["prolate_semiaxes_m"][1]
    gap = result.get("minimum_gap_m")
    checks = {"finite_state": bool(np.isfinite(result["position_m"] + result["orientation"] + result["velocity_generalized"]).all()),
              "unit_orientation": bool(abs(np.linalg.norm(result["orientation"])-1) <= 1e-10),
              "swept_clearance": bool(gap is not None and np.isfinite(gap) and gap >= -1e-5*b),
              "contact_residual": bool(bounded("max_contact_residual",1e-10)),
              "force_closure": bool(bounded("max_force_residual",1e-8)),
              "momentum_closure": bool(bounded("max_momentum_residual",1e-8)),
              "particle_Re_envelope": bool(bounded("max_reynolds",3)),
              "dwell_not_absorbing": result.get("dwell_is_absorbing") is False,
              "time_inside_horizon": bool(0 <= result["time_s"] <= spec["horizon_s"]+1e-12)}
    return {"passed": all(checks.values()), "checks": checks}


class BoundRunner(frozen.Runner):
    checkpoint = None
    pause = None
    binding = ""


def dispatch(module, spec, field, geometry, *, wall_budget):
    cfg, state = spec["config"], spec["initial_state"]
    a,b,_ = cfg["prolate_semiaxes_m"]
    return module.integrate(field, geometry, state["position_m"], state["orientation"], state["velocity_generalized"],
        a,b,cfg["dynamic_viscosity_Pa_s"],cfg["particle_density_kg_m3"],cfg["fluid_density_kg_m3"],
        cfg["gravity_m_s2"],cfg["friction_coefficient"],spec["field_metadata"]["cell_length_m"],spec["horizon_s"],
        added_mass_fraction=cfg["added_mass_fraction"],cutoff_ratio=.2,roughness_ratio=.01,
        displacement_fraction=cfg["numerics"]["displacement_fraction"],relaxation_fraction=cfg["numerics"]["relaxation_fraction"],
        angle_limit=cfg["numerics"]["angle_limit_rad"],max_dt=cfg["numerics"]["max_dt_s"],wall_budget=wall_budget,
        trap_reference_speed=cfg["target_mean_interstitial_velocity_m_s"],trap_dwell_time=cfg["trap"]["dwell_time_s"],
        trap_speed_ratio=cfg["trap"]["speed_ratio"],trap_drift_over_minor_radius=cfg["trap"]["drift_over_minor_radius"],
        stop_on_trap=cfg["trap"]["absorbing"],reynolds_limit=cfg["numerics"]["reynolds_limit"])


def execute(spec, binding, wall_budget, checkpoint=None, pause=None):
    require(0 < wall_budget <= 45, "bounded diagnostic budget required")
    require(pause is None or (type(pause) is int and pause > 0), "positive pause step required")
    field, data, metadata = fields.load(spec["seed"],spec["flow_factor"],spec["cpd"])
    require(metadata == spec["field_metadata"], "field metadata drift")
    geometry = frozen.h.geometry_exact_v1.GrainGeometry(data["sand_centres_m"],data["sand_radii_m"],metadata["cell_length_m"])
    field_hash = hashlib.sha256(field.u.tobytes()).hexdigest()
    BoundRunner.binding, BoundRunner.checkpoint, BoundRunner.pause = binding, checkpoint, pause
    try:
        result = dispatch(BoundRunner,spec,field,geometry,wall_budget=wall_budget)
    finally:
        BoundRunner.checkpoint, BoundRunner.pause = None, None
    require(hashlib.sha256(field.u.tobytes()).hexdigest() == field_hash, "transport mutated frozen field")
    return result
