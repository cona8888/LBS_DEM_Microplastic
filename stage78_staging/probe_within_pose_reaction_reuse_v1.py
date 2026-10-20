"""Read-only probe of reaction reuse within one frozen-pose finite-Re step.

The original Stage70 solver decides every trajectory state. A preceding inner
reaction is tested against the *next* inner system using the unchanged Stage50
contact, cone, force-closure and dissipation gates, but never substituted into
the solve. The saved Stage55 pose is a local restart, not a release trajectory.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage50_staging"), str(ROOT / "stage68_staging"),
                str(ROOT / "stage70_staging")]
import matrix_case_v1
import geometry_exact_v1
import inertial_contact_seeded_lm_v1 as gate
import inertial_contact_runtime_portfolio_v1 as contact
import trajectory_extended_recovery_v1 as trajectory

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
OLD = (ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" /
       "pilot_01" / "s2_prolate_ar4.json")
OUT = ROOT / "stage78_evaluations" / "within_pose_reaction_probe_02"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Probe:
    def __init__(self, module):
        self.module = module
        self.groups = []
        self.records = []
        self.errors = {}

    def __getattr__(self, name):
        return getattr(self.module, name)

    def inertial_contact_step(self, *args, **kwargs):
        prior = None
        group = len(self.groups)
        calls = 0
        original = self.module._solve

        def observe(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
            nonlocal prior, calls
            calls += 1
            record = {"group": group, "outer_call": calls,
                      "contacts": int(len(gaps)), "recovery": self.module.recovery_mode(),
                      "prior_available": prior is not None,
                      "prior_gate_pass": False, "prior_gate_reason": None,
                      "prior_normalized_residual": None}
            if prior is not None and len(prior) == 3 * len(gaps) and len(gaps):
                A = jacobian @ mobility @ jacobian.T
                z = jacobian @ vfree
                steps = np.array([
                    np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                    for k in range(len(gaps))])
                residual = gate._residual(prior, z, A, gaps, dt, friction, steps)
                record["prior_normalized_residual"] = float(
                    residual / max(np.linalg.norm(vfree), 1e-15))
                try:
                    candidate, _ = gate._finish(
                        vfree, mobility, jacobian, prior, z, A, gaps, dt,
                        friction, steps, 0, "diagnostic_prior_only", {})
                except (RuntimeError, ValueError, np.linalg.LinAlgError) as exc:
                    record["prior_gate_reason"] = str(exc)
                else:
                    record["prior_gate_pass"] = True
                    record["prior_velocity_norm"] = float(np.linalg.norm(candidate))
            try:
                answer = original(vfree, mobility, jacobian, gaps, dt,
                                  friction, tol, maxiter)
            except (RuntimeError, ValueError, FloatingPointError,
                    np.linalg.LinAlgError) as exc:
                record["cold_error"] = str(exc)
                self.records.append(record)
                raise
            velocity, health = answer
            record["cold_iterations"] = int(health["iterations"])
            record["cold_solver"] = health["solver"]
            record["cold_normalized_residual"] = float(health["residual"])
            if record["prior_gate_pass"]:
                record["prior_to_cold_velocity_delta"] = float(
                    np.linalg.norm(candidate - velocity))
            prior = np.asarray(health["reactions"], dtype=float)
            self.records.append(record)
            return answer

        self.module._solve = observe
        try:
            return self.module.inertial_contact_step(*args, **kwargs)
        except RuntimeError as exc:
            self.errors[str(exc)] = self.errors.get(str(exc), 0) + 1
            raise
        finally:
            self.module._solve = original
            self.groups.append(calls)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    config = json.loads(DESIGN.read_text())
    previous = json.loads(OLD.read_text())["result"]
    if previous["status"] != "numerical_failure":
        raise RuntimeError("expected frozen numerical-failure state")
    field, old_geometry, length, dx, inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    a, b, _ = config["prolate_semiaxes_m"]
    probe = Probe(contact)
    original = trajectory.inertial
    trajectory.inertial = probe
    contact.set_recovery_mode(False)
    try:
        result = trajectory.integrate(
            field, geometry, previous["position_m"], previous["orientation"],
            previous["velocity_generalized"], a, b,
            config["dynamic_viscosity_Pa_s"], config["particle_density_kg_m3"],
            config["fluid_density_kg_m3"], config["gravity_m_s2"],
            config["friction_coefficient"], length, 0.002,
            added_mass_fraction=config["added_mass_fraction"],
            cutoff_ratio=0.2, roughness_ratio=0.01,
            displacement_fraction=config["numerics"]["displacement_fraction"],
            relaxation_fraction=config["numerics"]["relaxation_fraction"],
            angle_limit=config["numerics"]["angle_limit_rad"],
            max_dt=config["numerics"]["max_dt_s"], wall_budget=30.,
            trap_reference_speed=config["target_mean_interstitial_velocity_m_s"],
            trap_dwell_time=config["trap"]["dwell_time_s"],
            trap_speed_ratio=config["trap"]["speed_ratio"],
            trap_drift_over_minor_radius=config["trap"]["drift_over_minor_radius"],
            stop_on_trap=config["trap"]["absorbing"],
            reynolds_limit=config["numerics"]["reynolds_limit"])
    finally:
        trajectory.inertial = original
        contact.set_recovery_mode(False)
    checked = [r for r in probe.records if r["prior_normalized_residual"] is not None]
    passes = [r for r in checked if r["prior_gate_pass"]]
    record = {
        "diagnostic_only": True, "result": result,
        "prior_time_s": previous["time_s"], "local_horizon_s": 0.002,
        "wall_budget_s": 30., "inner_calls": len(probe.records),
        "outer_groups": probe.groups, "outer_errors": probe.errors,
        "prior_checked": len(checked), "prior_gate_passes": len(passes),
        "prior_residual_quantiles": (
            {str(q): float(np.quantile([r["prior_normalized_residual"] for r in checked], q))
             for q in (0, .25, .5, .75, 1)} if checked else {}),
        "prior_to_cold_velocity_delta_max": (
            max(r["prior_to_cold_velocity_delta"] for r in passes
                if "prior_to_cold_velocity_delta" in r)
            if any("prior_to_cold_velocity_delta" in r for r in passes) else None),
        "records": probe.records,
        "input_hashes": {str(p): sha(p) for p in (OLD, DESIGN)},
        "source_hashes": {str(p): sha(p) for p in (
            Path(__file__), Path(contact.__file__), Path(gate.__file__),
            Path(trajectory.__file__), Path(geometry_exact_v1.__file__))},
        "claim_boundary": "Read-only local restarted solver diagnostic; no physical continuation, release, trapping, or validation claim."
    }
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_diagnostic", "results_sha256": sha(path)}, indent=2))
    print(json.dumps({k: record[k] for k in (
        "prior_time_s", "inner_calls", "outer_groups", "outer_errors",
        "prior_checked", "prior_gate_passes", "prior_residual_quantiles",
        "prior_to_cold_velocity_delta_max")}, indent=2))


if __name__ == "__main__":
    main()
