"""Stage147: a bounded, reproducible trajectory replay harness.

Rebuilds the production transport stack from its own sealed artifacts and runs a
bounded number of accepted steps from a saved checkpoint, under a configuration
that can be varied one element at a time.

Faithfulness and its limits
---------------------------
* The CPD6 field and the sand geometry are loaded by the recipe in
  `stage132_staging/load_cpd6_stationary_field_v1.py`, and both npz files are
  checked against the sha256 recorded in the frozen Stage139 spec.  The achieved
  mean interstitial velocity is checked against the value that spec recorded.
* The integrator is the unmodified `checkpoint_core_v3`, and the contact
  dispatcher is the Stage70 runtime portfolio with the Stage74 scoped scalar
  kernels -- the production default.
* The Stage136 Numba layer is NOT used.  Stage136/139 qualified it as
  algebraically identical to the Stage74/Stage50 path it replaces, so omitting it
  changes speed, not answers.  Any claim of *bitwise* equality with a production
  run must be re-established in the project environment; this harness is for
  comparing configurations against each other under one fixed stack.

Configurations
--------------
`baseline`   the stack exactly as it is today.
`contract`   Stage145's dt-consistent acceptance ceiling, via delta_geom.
`inertia`    Stage146's restored rotational mass block.
Any combination; each is applied by a scoped monkey-patch that is undone in
`finally`, so configurations cannot leak into one another.
"""
from contextlib import contextmanager
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in
                ("stage37_staging", "stage38_staging", "stage39_staging", "stage40_staging",
                 "stage41_staging", "stage42_staging", "stage50_staging", "stage53_staging",
                 "stage63_staging", "stage70_staging", "stage74_staging", "stage119_staging",
                 "stage145_staging", "stage146_staging")]
import wall_field_v1
import geometry_exact_v1 as geometry_module
import checkpoint_core_v3 as core
import inertial_contact_cold_optimized_v1 as stage41
import inertial_contact_runtime_portfolio_v1 as portfolio
import inertial_contact_scalar_kernel_v1 as scoped_kernels
import geometric_tolerance_v1 as contract_module
import rotational_inertia_v1 as rotation_module
sys.path.insert(0, str(ROOT / "stage147_staging"))
import contact_solver_v1 as contact_solver

SEGMENTS = ROOT / ("stage140_runs/sphere_finite_dwell_refinement_20260918/"
                   "refinement_01/sphere_dwell_factor_1")
GEOMETRY = ROOT / "stage125_designs/third_grid_cost_20260916/geometry_cpd6.npz"
FIELD = ROOT / "stage130_runs/cpd6_final_stationarity_20260916/gpu_confirmation_01/stage130_cpd6_final_stationarity/final_fields.npz"
GEOMETRY_SHA = "65c0f56a4f4b1434bb96b985565cedf3f270970c480fa7cfa968b79282714d2a"
FIELD_SHA = "8cba5eb9857a09ba7c09bd3963db0d97855ccbdd037ea636dcca8e7961c62cad"
ACHIEVED_MEAN_M_S = 9.996666087226107e-05
CELL_LENGTH_M = 0.004680605809919908


# The sphere case as the Stage139 design froze it.  `outlet` is recovered exactly from
# the sealed record: full_exit_function = x[0] - support([1,0,0],p,a,b) - outlet, and the
# Stage140 record carries x, the pose and the function value, giving outlet = cell_length
# to the last bit.  `horizon` is the design's 0.1 pore volumes in seconds.
SEMI_AXIS_M = 7.937005259841001e-05          # equal-volume sphere, a = b
CASE = {
    "viscosity": 0.001002, "particle_density": 1380.0, "fluid_density": 998.2,
    "gravity": [0.0, 0.0, -9.80665], "friction": 0.3,
    "outlet": CELL_LENGTH_M, "horizon": 0.1 * CELL_LENGTH_M / ACHIEVED_MEAN_M_S,
    "added_mass_fraction": 1.0, "cutoff_ratio": 0.2, "roughness_ratio": 0.01,
    "displacement_fraction": 0.0015625, "angle_limit": 0.0003125,
    "max_dt": 0.00015625, "relaxation_fraction": 0.0078125,
    "trap_reference_speed": ACHIEVED_MEAN_M_S, "trap_dwell_time": 0.5,
    "trap_speed_ratio": 0.01, "trap_drift_over_minor_radius": 0.02,
    "stop_on_trap": False, "reynolds_limit": 3.0,
}
BINDING = "stage147_bounded_trajectory_replay_v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def segment(name):
    """The sealed Stage140 record and the checkpoint it carries."""
    record = json.loads((SEGMENTS / f"segment_{name}/record.json").read_text())
    return record["result"]["checkpoint"], record


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def load_scene():
    require(sha(GEOMETRY) == GEOMETRY_SHA, "CPD6 geometry drifted from the Stage139 spec binding")
    require(sha(FIELD) == FIELD_SHA, "CPD6 field drifted from the Stage139 spec binding")
    with np.load(GEOMETRY) as g, np.load(FIELD) as f:
        geometry = {k: g[k].copy() for k in g.files}
        require(np.array_equal(f["phase"], geometry["phase"]), "phase drift")
        fluid = (f["phase"] == 0).transpose(2, 1, 0)
        velocity = f["velocity_xyz_lu"].astype(np.float64).transpose(0, 3, 2, 1)
    dx = float(geometry["spacing_m"][0])
    velocity *= (0.001002 / 998.2) / (0.1 * dx)
    achieved = float(velocity[0, fluid].mean())
    require(abs(achieved / ACHIEVED_MEAN_M_S - 1.0) < 2e-6, "SI reconstruction drift")
    require(np.isfinite(velocity).all() and np.all(velocity[:, ~fluid] == 0), "invalid velocity array")
    field = wall_field_v1.WallCellField(velocity, dx, fluid)
    grains = geometry_module.GrainGeometry(geometry["sand_centres_m"], geometry["sand_radii_m"],
                                           float(geometry["cell_length_m"][0]))
    return field, grains, {"achieved_mean_interstitial_velocity_m_s": achieved,
                           "cell_length_m": float(geometry["cell_length_m"][0]),
                           "spacing_m": dx, "grains": int(len(geometry["sand_radii_m"])),
                           "field_sha256": FIELD_SHA, "geometry_sha256": GEOMETRY_SHA}


# ------------------------------------------------------------------ configuration scopes
@contextmanager
def tolerance_contract(delta_geom, ladder=False):
    """Stage145's dt-consistent ceiling, injected where it actually takes effect.

    NOT at `stage41._solve_prepared`: `portfolio.inertial_contact_step` rebinds that
    name to `portfolio._solve` on every call, so a patch there is overwritten before
    it is used and is silently inert.  Measured, not argued -- the first Stage147
    attempt produced a bit-identical run.  The portfolio entry point is the hook.
    """
    original = portfolio._solve
    portfolio._solve = contact_solver.make_solver(delta_geom, ladder=ladder)
    contact_solver.reset_stats()
    try:
        yield
    finally:
        portfolio._solve = original


@contextmanager
def rotational_inertia(a, b, particle_density, fluid_density, added_mass_fraction):
    """Stage146: keep the rotational block that checkpoint_core_v3 zeroes."""
    original = stage41.generalized_mass_matrix
    core_original = core.inertial.generalized_mass_matrix

    def patched(p, aa, bb, rho_p, rho_f, amf):
        mass, extra = original(p, aa, bb, rho_p, rho_f, amf)
        mass = np.array(mass, float)
        return _KeepRotational(mass), extra
    stage41.generalized_mass_matrix = patched
    core.inertial.generalized_mass_matrix = patched
    try:
        yield
    finally:
        stage41.generalized_mass_matrix = original
        core.inertial.generalized_mass_matrix = core_original


class _KeepRotational(np.ndarray):
    """A mass matrix whose rotational block refuses to be zeroed.

    `checkpoint_core_v3` executes `mass[3:, 3:] = 0.0` immediately after building
    the matrix.  Rather than edit that immutable module, this subclass ignores an
    assignment that would zero the rotational block and leaves it intact, which is
    exactly the one-line production change Stage146 recommends putting behind a flag.
    """
    def __new__(cls, source):
        return np.asarray(source, float).view(cls)

    def __setitem__(self, key, value):
        if isinstance(key, tuple) and len(key) == 2:
            rows, columns = key
            if (isinstance(rows, slice) and isinstance(columns, slice)
                    and rows == slice(3, None) and columns == slice(3, None)
                    and np.all(np.asarray(value) == 0)):
                return                                  # keep the rotational inertia
        super().__setitem__(key, value)


@contextmanager
def production_dispatch():
    """Stage70 portfolio with the Stage74 scoped scalar kernels: the production default."""
    original = core.inertial
    core.inertial = scoped_kernels
    try:
        yield
    finally:
        core.inertial = original


# ------------------------------------------------------------------ the run
def contract_digest(binding, a, b, cfg):
    def encoded(value):
        return json.dumps(value, sort_keys=True, allow_nan=True,
                          default=lambda z: z.tolist() if isinstance(z, np.ndarray) else z.item())
    contract = [binding, a, b, cfg["viscosity"], cfg["particle_density"], cfg["fluid_density"],
                list(cfg["gravity"]), cfg["friction"], cfg["outlet"], cfg["horizon"],
                cfg["added_mass_fraction"], cfg["cutoff_ratio"], cfg["roughness_ratio"],
                cfg["displacement_fraction"], cfg["angle_limit"], cfg["relaxation_fraction"],
                cfg["max_dt"], cfg["trap_reference_speed"], cfg["trap_dwell_time"],
                cfg["trap_speed_ratio"], cfg["trap_drift_over_minor_radius"],
                cfg["stop_on_trap"], cfg["reynolds_limit"]]
    return hashlib.sha256(encoded(contract).encode()).hexdigest(), encoded


def replay(field, grains, checkpoint, a, b, cfg, steps, binding, *,
           use_contract=False, use_inertia=False, delta_geom=0.0, ladder=False,
           wall_budget=300.0):
    """Run `steps` accepted steps from `checkpoint` under one configuration."""
    checkpoint = copy.deepcopy(checkpoint)
    state = checkpoint["state"]
    digest, encoded = contract_digest(binding, a, b, cfg)
    checkpoint["contract"] = digest
    checkpoint["state_sha256"] = hashlib.sha256(encoded(state).encode()).hexdigest()
    scopes = [production_dispatch()]
    if use_contract:
        scopes.append(tolerance_contract(delta_geom, ladder=ladder))
    if use_inertia:
        scopes.append(rotational_inertia(a, b, cfg["particle_density"], cfg["fluid_density"],
                                         cfg["added_mass_fraction"]))
    from contextlib import ExitStack
    with ExitStack() as stack:
        for scope in scopes:
            stack.enter_context(scope)
        return core.integrate(
            field, grains, state["x"], state["p"], state["q"], a, b, cfg["viscosity"],
            cfg["particle_density"], cfg["fluid_density"], cfg["gravity"], cfg["friction"],
            cfg["outlet"], cfg["horizon"],
            added_mass_fraction=cfg["added_mass_fraction"], cutoff_ratio=cfg["cutoff_ratio"],
            roughness_ratio=cfg["roughness_ratio"], displacement_fraction=cfg["displacement_fraction"],
            angle_limit=cfg["angle_limit"], relaxation_fraction=cfg["relaxation_fraction"],
            max_dt=cfg["max_dt"], wall_budget=wall_budget,
            trap_reference_speed=cfg["trap_reference_speed"], trap_dwell_time=cfg["trap_dwell_time"],
            trap_speed_ratio=cfg["trap_speed_ratio"],
            trap_drift_over_minor_radius=cfg["trap_drift_over_minor_radius"],
            stop_on_trap=cfg["stop_on_trap"], reynolds_limit=cfg["reynolds_limit"],
            checkpoint=checkpoint, checkpoint_binding=binding,
            pause_after_steps=state["steps"] + steps)


def compare(reference, candidate, minor_radius, reference_speed):
    """State difference at whatever clocks the two runs reached."""
    out = {"clock_difference_s": abs(candidate["time_s"] - reference["time_s"]),
           "same_status": candidate["status"] == reference["status"],
           "steps_reference": reference["steps"], "steps_candidate": candidate["steps"],
           "rejected_reference": reference["rejected"], "rejected_candidate": candidate["rejected"],
           "same_step_count": reference["steps"] == candidate["steps"]}
    for key, scale, name in (("position_m", minor_radius, "position_over_minor_radius"),
                             ("velocity_generalized", reference_speed, "velocity_over_reference_speed")):
        difference = np.linalg.norm(np.array(candidate[key]) - np.array(reference[key]))
        out[name] = float(difference / scale)
    out["axis_difference"] = float(np.linalg.norm(np.array(candidate["orientation"]) - np.array(reference["orientation"])))
    for key in ("persistent_contact_observed", "first_contact_dwell_time_s"):
        out[key] = {"reference": reference.get(key), "candidate": candidate.get(key)}
    return out
