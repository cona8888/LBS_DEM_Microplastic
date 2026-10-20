import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import lubrication_contact_v1 as lubrication


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def brenner_sphere_plane_factor(gap_over_radius, tolerance=1e-14):
    """Exact normal drag factor from Brenner (1961), Chem. Eng. Sci. 16."""
    epsilon = float(gap_over_radius)
    if epsilon <= 0:
        raise ValueError("positive gap required")
    alpha = np.arccosh(1.0 + epsilon)
    total = 0.0
    for n in range(1, 10000):
        q = 2 * n + 1
        bracket = (
            (2 * np.sinh(q * alpha) + q * np.sinh(2 * alpha))
            / (4 * np.sinh(q * alpha / 2) ** 2 - q * q * np.sinh(alpha) ** 2)
            - 1.0
        )
        term = n * (n + 1) / ((2 * n - 1) * (2 * n + 3)) * bracket
        total += term
        if n > 20 and abs(term) <= tolerance * abs(total):
            return float(4.0 * np.sinh(alpha) * total / 3.0), n
    raise RuntimeError("Brenner series did not converge")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()

    grain_radius = 0.000385
    sphere_radius = (0.0002 * 0.00005 * 0.00005) ** (1.0 / 3.0)
    cutoff = 0.2 * grain_radius
    cutoff_epsilon = cutoff / sphere_radius
    exact_cutoff, _ = brenner_sphere_plane_factor(cutoff_epsilon)
    epsilons = np.geomspace(0.005, cutoff_epsilon, 48)
    canonical = []
    for epsilon in epsilons:
        exact, terms = brenner_sphere_plane_factor(epsilon)
        matched = exact_cutoff + 1.0 / epsilon - 1.0 / cutoff_epsilon
        canonical.append(
            {
                "gap_over_body_radius": float(epsilon),
                "exact_factor": exact,
                "matched_factor": float(matched),
                "relative_error": float(abs(matched / exact - 1.0)),
                "series_terms": terms,
            }
        )
    canonical_error = max(row["relative_error"] for row in canonical)

    # Geometry reductions and algebraic checks in SI units.
    sphere_curvature = lubrication.prolate_principal_curvatures(
        [sphere_radius, 0, 0], [1, 0, 0], sphere_radius, sphere_radius
    )
    sphere_curvature_error = max(abs(value * sphere_radius - 1.0) for value in sphere_curvature)
    plane_prefactor = lubrication.squeeze_prefactor(0.001002, 1e12, sphere_curvature)
    plane_prefactor_exact = 6 * np.pi * 0.001002 * sphere_radius**2
    plane_limit_error = abs(plane_prefactor / plane_prefactor_exact - 1.0)
    scaled_prefactor = lubrication.squeeze_prefactor(
        0.001002, 2 * grain_radius, tuple(value / 2 for value in sphere_curvature)
    )
    base_prefactor = lubrication.squeeze_prefactor(0.001002, grain_radius, sphere_curvature)
    scale_error = abs(scaled_prefactor / (4 * base_prefactor) - 1.0)

    mobility = np.diag([2.0, 3.0, 4.0, 0.5, 0.6, 0.7])
    vfree = np.array([0.2, -0.4, 0.1, 0.03, -0.02, 0.01])
    lever = np.array([sphere_radius, 0.0, 0.0])
    normal = np.array([1.0, 0.0, 0.0])
    contact = [(7, cutoff / 10, normal, lever, grain_radius)]
    motion, corrected, health = lubrication.lubricated_motion(
        vfree, mobility, contact, [1, 0, 0], sphere_radius, sphere_radius,
        sphere_radius, 0.001002, cutoff, cutoff / 100,
    )
    jacobian = lubrication.normal_jacobian(normal, lever, sphere_radius)
    coefficient = health["contacts"][0]["excess_coefficient"]
    expected = np.linalg.solve(np.linalg.inv(mobility) + coefficient * np.outer(jacobian, jacobian), np.linalg.solve(mobility, vfree))
    analytic_error = np.linalg.norm(motion - expected) / np.linalg.norm(expected)
    dissipation = float(vfree @ np.linalg.solve(mobility, vfree))
    corrected_dissipation = float(vfree @ np.linalg.solve(corrected, vfree))
    cutoff_value = lubrication.matched_excess_resistance(cutoff, cutoff, cutoff / 100, base_prefactor)
    just_below = lubrication.matched_excess_resistance(cutoff * (1 - 1e-10), cutoff, cutoff / 100, base_prefactor)
    continuity_scale = base_prefactor / cutoff
    continuity_error = just_below / continuity_scale
    capped_a = lubrication.matched_excess_resistance(-cutoff, cutoff, cutoff / 100, base_prefactor)
    capped_b = lubrication.matched_excess_resistance(cutoff / 100, cutoff, cutoff / 100, base_prefactor)

    checks = {
        "brenner_matched_relative_error_le_0p04": canonical_error <= 0.04,
        "sphere_curvature_exact": sphere_curvature_error <= 1e-12,
        "sphere_plane_prefactor_limit": plane_limit_error <= 1e-9,
        "length_scaling_exact": scale_error <= 1e-12,
        "cutoff_continuous": cutoff_value == 0.0 and continuity_error <= 1.1e-10,
        "roughness_cap_finite_and_constant": np.isfinite(capped_a) and capped_a == capped_b,
        "six_dof_algebra": analytic_error <= 1e-12,
        "mobility_positive_symmetric": health["mobility_symmetry_residual"] <= 1e-12 and health["minimum_mobility_eigenvalue"] > 0,
        "lubrication_adds_dissipation": corrected_dissipation >= dissipation,
    }
    source_paths = [Path(__file__), Path(lubrication.__file__)]
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "values": {
            "grain_radius_m": grain_radius,
            "equal_volume_sphere_radius_m": sphere_radius,
            "cutoff_m": cutoff,
            "cutoff_gap_over_body_radius": cutoff_epsilon,
            "brenner_matched_relative_error_max": canonical_error,
            "sphere_curvature_relative_error": sphere_curvature_error,
            "sphere_plane_prefactor_relative_error": plane_limit_error,
            "length_scale_prefactor_relative_error": scale_error,
            "cutoff_continuity_normalized_error": continuity_error,
            "six_dof_analytic_relative_error": analytic_error,
            "base_dissipation": dissipation,
            "corrected_dissipation": corrected_dissipation,
            "mobility_health": health,
        },
        "canonical_rows": canonical,
        "runtime_seconds": time.perf_counter() - started,
        "scope": "normal near-gap resistance only; no tangential lubrication, contact trajectory, or PET release claim",
        "source_hashes": {str(path.resolve()): sha(path) for path in source_paths},
        "reference": {
            "citation": "Brenner, H. (1961), Chem. Eng. Sci. 16, 242-251",
            "doi": "10.1016/0009-2509(61)80035-3",
        },
    }
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "values": result["values"]}, indent=2))


if __name__ == "__main__":
    main()

