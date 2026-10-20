import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import inertial_contact_v1 as model


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
    mass_none, meta_none = model.generalized_mass_matrix([1, 0, 0], a, b, rho_p, rho_f, 0.0)
    mass_added, meta_added = model.generalized_mass_matrix([1, 0, 0], a, b, rho_p, rho_f, 1.0)
    sphere_mass, sphere_meta = model.generalized_mass_matrix([1, 0, 0], b, b, rho_p, rho_f, 1.0)
    resistance = model.stokes_generalized_resistance([1, 0, 0], a, b, mu)
    zero = np.zeros((6, 6))

    # Exact low-Re decay under diagonal Stokes resistance.
    initial = np.array([0.002, -0.001, 0.0005, 0.0002, -0.0001, 0.00015])
    horizon = 5 * mass_none[0, 0] / resistance[0, 0]
    convergence = []
    for steps in (64, 128, 256):
        velocity = initial.copy()
        dt = horizon / steps
        for _ in range(steps):
            velocity, health = model.inertial_contact_step(
                velocity, np.zeros(6), np.zeros(6), resistance, zero, mass_none,
                [], a, dt, 0.0, 1e-12, 1.0, 1.0, phi
            )
        decay = np.diag(resistance) / np.diag(mass_none)
        exact = initial * np.exp(-decay * horizon)
        convergence.append({
            "steps": steps,
            "relative_l2_error": float(np.linalg.norm(velocity - exact) / np.linalg.norm(initial)),
            "momentum_residual": health["momentum_residual"],
        })

    # Inelastic normal impact on a fixed plane, expressed as a hard contact.
    plane_contact = [(0, 0.0, np.array([0.0, 1.0, 0.0]), np.array([0.0, -b, 0.0]))]
    impact_old = np.array([0.3, -1.0, 0.0, 0.0, 0.0, 0.0])
    tiny_resistance = np.eye(6) * 1e-12
    impact, impact_health = model.inertial_contact_step(
        impact_old, np.zeros(6), np.zeros(6), tiny_resistance, zero, mass_none,
        plane_contact, a, 1e-4, 0.0, rho_f, mu, diameter, phi
    )
    sliding, sliding_health = model.inertial_contact_step(
        impact_old, np.zeros(6), np.zeros(6), tiny_resistance, zero, mass_none,
        plane_contact, a, 1e-4, 0.3, rho_f, mu, diameter, phi
    )

    # Symmetric two-contact wedge must close momentum without penetration.
    wedge = [
        (0, 0.0, np.array([0.0, 1.0, 0.0]), np.array([0.0, -b, 0.0])),
        (1, 0.0, np.array([0.0, -1.0, 0.0]), np.array([0.0, b, 0.0])),
    ]
    wedge_old = np.array([0.1, 0.4, 0.0, 0.0, 0.0, 0.0])
    wedge_velocity, wedge_health = model.inertial_contact_step(
        wedge_old, np.zeros(6), np.zeros(6), tiny_resistance, zero, mass_none,
        wedge, a, 1e-4, 0.0, rho_f, mu, diameter, phi
    )

    added_eigenvalues = np.linalg.eigvalsh(mass_added - mass_none)
    checks = {
        "sphere_added_mass_half_displaced": max(abs(value - 0.5) for value in sphere_meta["added_mass_coefficients"]) <= 1e-15,
        "prolate_added_mass_anisotropic_positive": 0 < meta_added["added_mass_coefficients"][0] < meta_added["added_mass_coefficients"][1],
        "added_mass_positive_semidefinite": added_eigenvalues.min() >= -1e-20,
        "generalized_mass_positive": np.linalg.eigvalsh(mass_added).min() > 0,
        "linear_relaxation_converges": convergence[-1]["relative_l2_error"] <= 5e-4 and convergence[-1]["relative_l2_error"] < convergence[-2]["relative_l2_error"] < convergence[-3]["relative_l2_error"],
        "impact_no_penetration_velocity": impact[1] >= -1e-10,
        "friction_reduces_tangential_speed": abs(sliding[0]) < abs(impact[0]),
        "impact_energy_nonincreasing": kinetic(mass_none, impact) <= kinetic(mass_none, impact_old) and kinetic(mass_none, sliding) <= kinetic(mass_none, impact_old),
        "wedge_no_normal_motion": abs(wedge_velocity[1]) <= 1e-10,
        "all_momentum_residuals": max(impact_health["momentum_residual"], sliding_health["momentum_residual"], wedge_health["momentum_residual"], *(row["momentum_residual"] for row in convergence)) <= 1e-8,
        "all_contact_fixed_points": max(impact_health["contact"]["residual"], sliding_health["contact"]["residual"], wedge_health["contact"]["residual"]) <= 1e-8,
    }
    sources = [Path(__file__), Path(model.__file__), Path(model.contact_model.__file__), Path(model.finite_re.__file__)]
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "values": {
            "prolate_added_mass_coefficients": meta_added["added_mass_coefficients"],
            "sphere_added_mass_coefficients": sphere_meta["added_mass_coefficients"],
            "linear_convergence": convergence,
            "impact_velocity": impact.tolist(),
            "sliding_velocity": sliding.tolist(),
            "wedge_velocity": wedge_velocity.tolist(),
            "impact_health": impact_health,
            "sliding_health": sliding_health,
            "wedge_health": wedge_health,
        },
        "source_hashes": {str(path.resolve()): sha(path) for path in sources},
        "scope": "single-step and canonical relaxation verification; no matrix trajectories or release claim",
    }
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "values": result["values"]}, indent=2))


if __name__ == "__main__":
    main()

