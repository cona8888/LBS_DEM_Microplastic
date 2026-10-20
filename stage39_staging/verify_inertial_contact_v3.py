"""In-domain tests for the corrected distinct-frame inertial/contact step."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import inertial_contact_v2 as model


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def kinetic(matrix, velocity):
    return float(0.5 * velocity @ matrix @ velocity)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    rho_p, rho_f, mu = 1380.0, 998.2, 0.001002
    a, b = 0.0002, 0.00005
    diameter = 2 * (a * b * b) ** (1 / 3)
    phi = model.finite_re.prolate_sphericity(a, b)
    mass, _ = model.generalized_mass_matrix([1, 0, 0], a, b, rho_p, rho_f, 0.0)
    mass_added, added_meta = model.generalized_mass_matrix([1, 0, 0], a, b, rho_p, rho_f, 1.0)
    _sphere, sphere_meta = model.generalized_mass_matrix([1, 0, 0], b, b, rho_p, rho_f, 1.0)
    resistance = model.stokes_generalized_resistance([1, 0, 0], a, b, mu)
    zero = np.zeros((6, 6))

    # Low-Re linear decay convergence.
    initial = np.array([0.002, -0.001, 0.0005, 0.0002, -0.0001, 0.00015])
    horizon = 5 * mass[0, 0] / resistance[0, 0]
    convergence = []
    for steps in (64, 128, 256):
        velocity = initial.copy()
        dt = horizon / steps
        for _ in range(steps):
            velocity, health = model.inertial_contact_step(
                velocity, np.zeros(6), np.zeros(6), resistance, zero, mass,
                [], a, dt, 0.0, 1e-12, 1.0, 1.0, phi
            )
        exact = initial * np.exp(-np.diag(resistance) / np.diag(mass) * horizon)
        convergence.append({"steps": steps, "error": float(np.linalg.norm(velocity - exact) / np.linalg.norm(initial)), "health": health})

    plane = [(0, 0.0, np.array([0.0, 1.0, 0.0]), np.array([0.0, -b, 0.0]))]
    impact_old = np.array([0.003, -0.01, 0, 0, 0, 0], float)
    tiny = np.eye(6) * 1e-12
    impact, impact_health = model.inertial_contact_step(
        impact_old, np.zeros(6), np.zeros(6), tiny, zero, mass, plane, a,
        1e-4, 0.0, rho_f, mu, diameter, phi
    )
    sliding, sliding_health = model.inertial_contact_step(
        impact_old, np.zeros(6), np.zeros(6), tiny, zero, mass, plane, a,
        1e-4, 0.3, rho_f, mu, diameter, phi
    )
    wedge = [plane[0], (1, 0.0, np.array([0.0, -1.0, 0.0]), np.array([0.0, b, 0.0]))]
    wedge_velocity, wedge_health = model.inertial_contact_step(
        np.array([0.001, 0.004, 0, 0, 0, 0], float), np.zeros(6), np.zeros(6),
        tiny, zero, mass, wedge, a, 1e-4, 0.0, rho_f, mu, diameter, phi
    )

    # Distinct-frame test: a particle exactly following moving fluid must slow
    # when a fixed-wall lubrication resistance is present.
    background = np.array([0.001, 0, 0, 0, 0, 0], float)
    lubrication = np.zeros((6, 6)); lubrication[0, 0] = resistance[0, 0]
    no_wall, no_wall_health = model.inertial_contact_step(
        background, background, np.zeros(6), resistance, zero, mass, [], a,
        1e-3, 0.0, rho_f, mu, diameter, phi
    )
    fixed_wall, fixed_wall_health = model.inertial_contact_step(
        background, background, np.zeros(6), resistance, lubrication, mass, [], a,
        1e-3, 0.0, rho_f, mu, diameter, phi
    )
    expected_x = (mass[0, 0] / 1e-3 + resistance[0, 0]) * background[0] / (
        mass[0, 0] / 1e-3 + resistance[0, 0] + lubrication[0, 0]
    )
    dynamic = [impact_health, sliding_health, wedge_health, no_wall_health, fixed_wall_health]
    maximum_re = max(row["reynolds"] for row in dynamic)
    checks = {
        "all_finite_re_tests_within_re3": maximum_re <= 3.0,
        "sphere_added_mass_half_displaced": max(abs(value - 0.5) for value in sphere_meta["added_mass_coefficients"]) <= 1e-15,
        "prolate_added_mass_anisotropic_positive": 0 < added_meta["added_mass_coefficients"][0] < added_meta["added_mass_coefficients"][1],
        "added_mass_positive_semidefinite": np.linalg.eigvalsh(mass_added - mass).min() >= -1e-20,
        "linear_relaxation_converges": convergence[-1]["error"] <= 5e-4 and convergence[-1]["error"] < convergence[-2]["error"] < convergence[-3]["error"],
        "impact_nonpenetrating": impact[1] >= -1e-10,
        "friction_reduces_tangential_speed": abs(sliding[0]) < abs(impact[0]),
        "unforced_energy_nonincreasing": kinetic(mass, impact) <= kinetic(mass, impact_old) and kinetic(mass, sliding) <= kinetic(mass, impact_old),
        "wedge_normal_velocity_zero": abs(wedge_velocity[1]) <= 1e-10,
        "fluid_following_without_wall": np.linalg.norm(no_wall - background) <= 1e-14,
        "fixed_wall_lubrication_slows_particle": fixed_wall[0] < background[0] and abs(fixed_wall[0] - expected_x) <= 1e-12,
        "all_momentum_residuals": max(row["momentum_residual"] for row in dynamic) <= 1e-8,
        "all_contact_fixed_points": max(row["contact"]["residual"] for row in (impact_health, sliding_health, wedge_health)) <= 1e-8,
    }
    sources = [Path(__file__), Path(model.__file__), Path(model.base.__file__), Path(model.contact_model.__file__), Path(model.finite_re.__file__)]
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "values": {
            "maximum_test_reynolds": maximum_re,
            "linear_convergence": convergence,
            "no_wall_velocity": no_wall.tolist(),
            "fixed_wall_velocity": fixed_wall.tolist(),
            "fixed_wall_expected_x": expected_x,
            "impact_velocity": impact.tolist(),
            "sliding_velocity": sliding.tolist(),
            "wedge_velocity": wedge_velocity.tolist(),
            "dynamic_health": dynamic,
        },
        "source_hashes": {str(path.resolve()): sha(path) for path in sources},
        "supersedes_frame_incomplete_model_test": "../inertial_contact_verification_02",
        "scope": "distinct-frame inertial/contact primitive; no matrix trajectory or release claim",
    }
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "maximum_re": maximum_re}, indent=2))


if __name__ == "__main__":
    main()
