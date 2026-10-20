"""Verify the normal-only cross-step reaction cache."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import inertial_contact_cached_v2 as model


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    a, b, mu = 2e-4, 5e-5, 0.001002
    rp, rf = 1380.0, 998.2
    diameter = 2*(a*b*b)**(1/3)
    phi = model.finite_re.prolate_sphericity(a, b)
    mass, _ = model.generalized_mass_matrix([1, 0, 0], a, b, rp, rf, 1)
    resistance = model.stokes_generalized_resistance([1, 0, 0], a, b, mu)
    contacts = [(11, 0.0, np.array([0., 1., 0.]), np.array([0., -b, 0.])),
                (17, 0.0, np.array([0., -1., 0.]), np.array([0., b, 0.]))]
    supplied = {"11": [2., 4., -3.], "17": [1., -5., 6.], "99": [7., 8., 9.]}
    filtered = model.normal_only_world_reactions(contacts, supplied)
    old = np.array([.001, .004, 0, 0, 0, 0.])
    common = (old, np.zeros(6), np.zeros(6), resistance, np.zeros((6, 6)), mass,
              contacts, a, 1e-4, .3, rf, mu, diameter, phi)
    cold, cold_health = model.inertial_contact_step(*common)
    warm, warm_health = model.inertial_contact_step(
        *common, world_reactions=cold_health["reaction_world_by_grain"]
    )
    checks = {
        "only_current_contacts_retained": set(filtered) == {"11", "17"},
        "tangential_components_removed": abs(filtered["11"][0]) <= 1e-15 and abs(filtered["11"][2]) <= 1e-15
                                         and abs(filtered["17"][0]) <= 1e-15 and abs(filtered["17"][2]) <= 1e-15,
        "compressive_projection_nonnegative": filtered["11"][1] >= 0 and filtered["17"][1] <= 0,
        "warm_cold_velocity_equivalent": np.linalg.norm(warm-cold) <= 1e-10,
        "warm_not_more_iterations": warm_health["total_contact_iterations"] <= cold_health["total_contact_iterations"],
        "closures": max(cold_health["momentum_residual"], warm_health["momentum_residual"]) <= 1e-8
                    and max(cold_health["contact"]["residual"], warm_health["contact"]["residual"]) <= 1e-8,
    }
    result = {"completed": True, "passed": all(checks.values()),
              "checks": {key: bool(value) for key, value in checks.items()},
              "values": {"filtered": filtered, "cold_iterations": cold_health["total_contact_iterations"],
                         "warm_iterations": warm_health["total_contact_iterations"]},
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(model.__file__).resolve()): sha(model.__file__),
                                str(Path(model.previous.__file__).resolve()): sha(model.previous.__file__)},
              "scope": "normal-only cross-step warm start; no tangential contact history"}
    (output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
