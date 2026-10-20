import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import finite_re_relaxation_v2 as model


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    a, b = 0.0002, 0.00005
    equivalent_radius = (a * b * b) ** (1.0 / 3.0)
    diameter = 2 * equivalent_radius
    phi = model.prolate_sphericity(a, b)
    sphere_phi = model.prolate_sphericity(b, b)
    re_grid = np.geomspace(1e-8, 3.0, 160)
    prolate_multiplier = np.array([model.inertial_multiplier(re, phi) for re in re_grid])
    sphere_selected = np.array([model.inertial_multiplier(re, 1.0) for re in re_grid])
    sphere_specific = np.array([model.sphere_cd(re) * re / 24 for re in re_grid])
    sphere_difference = np.max(abs(sphere_selected / sphere_specific - 1.0))

    mass = 2.0
    resistance = np.diag([3.0, 4.0, 5.0])
    initial = np.array([1.0, -0.5, 0.25])
    horizon = 5.0 * mass / resistance[0, 0]
    convergence = []
    for steps in (64, 128, 256):
        velocity = initial.copy()
        dt = horizon / steps
        for _ in range(steps):
            velocity, _health = model.implicit_translation_step(
                velocity, np.zeros(3), np.zeros(3), resistance, mass, dt,
                1e-12, 1.0, 1.0, 1.0,
            )
        exact = initial * np.exp(-np.diag(resistance) * horizon / mass)
        convergence.append({
            "steps": steps,
            "velocity": velocity.tolist(),
            "exact": exact.tolist(),
            "relative_l2_error": float(np.linalg.norm(velocity - exact) / np.linalg.norm(initial)),
        })

    rho_f, mu, rho_pet = 998.2, 0.001002, 1380.0
    original_regime = []
    for speed in (0.0001, 0.005, 0.01):
        re = rho_f * speed * diameter / mu
        original_regime.append({
            "slip_speed_m_s": speed,
            "reynolds": re,
            "sphere_multiplier": model.inertial_multiplier(re, 1.0),
            "prolate_sphericity_multiplier": model.inertial_multiplier(re, phi),
        })
    particle_mass = rho_pet * 4 * np.pi * a * b * b / 3
    stokes_scale = 6 * np.pi * mu * equivalent_radius
    response_time = particle_mass / stokes_scale
    test_resistance = np.diag([stokes_scale, 1.2 * stokes_scale, 1.4 * stokes_scale])
    old = np.array([0.01, -0.002, 0.001])
    dt = response_time / 4
    new, nonlinear_health = model.implicit_translation_step(
        old, np.zeros(3), np.zeros(3), test_resistance, particle_mass, dt,
        rho_f, mu, diameter, phi,
    )
    drag, returned_health = model.nonlinear_drag(test_resistance, new, rho_f, mu, diameter, phi)
    balance = np.linalg.norm(particle_mass * (new - old) / dt - drag) / max(np.linalg.norm(drag), 1e-30)
    checks = {
        "sphere_sphericity_exact": abs(sphere_phi - 1.0) <= 1e-15,
        "prolate_sphericity_physical": 0 < phi < 1,
        "stokes_limit": model.inertial_multiplier(0.0, phi) == 1.0,
        "positive_monotone_multiplier_to_re3": np.all(prolate_multiplier >= 1) and np.all(np.diff(prolate_multiplier) >= 0),
        "selected_sphere_matches_specific_correlation": sphere_difference <= 0.01,
        "implicit_linear_convergence": convergence[-1]["relative_l2_error"] <= 5e-4 and convergence[-1]["relative_l2_error"] < convergence[-2]["relative_l2_error"] < convergence[-3]["relative_l2_error"],
        "nonlinear_iteration_converged": nonlinear_health["iterations"] < 50,
        "nonlinear_momentum_balance": balance <= 1e-10,
        "nonlinear_drag_reduces_slip": np.linalg.norm(new) < np.linalg.norm(old),
    }
    paths = [Path(__file__), Path(model.__file__), Path(model.base.__file__)]
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "values": {
            "prolate_sphericity": phi,
            "equivalent_diameter_m": diameter,
            "particle_mass_kg": particle_mass,
            "stokes_response_time_s": response_time,
            "sphere_selected_to_specific_difference_max": float(sphere_difference),
            "nonlinear_balance": float(balance),
            "nonlinear_health": nonlinear_health,
            "returned_drag_health": returned_health,
        },
        "linear_convergence": convergence,
        "original_regime": original_regime,
        "source_hashes": {str(path.resolve()): sha(path) for path in paths},
        "supersedes_failed": "../finite_re_relaxation_verification_01",
        "scope": "outer translational drag and relaxation primitive only; no matrix release claim",
        "reference": {"doi": "10.1016/0032-5910(89)80008-7"},
    }
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "values": result["values"], "regime": original_regime}, indent=2))


if __name__ == "__main__":
    main()
