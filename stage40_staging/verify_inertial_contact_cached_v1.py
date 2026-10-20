"""Frame-objectivity and equivalence tests for persisted contact reactions."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import inertial_contact_cached_v1 as model


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    a, b, mu = 2e-4, 5e-5, 0.001002
    density_particle, density_fluid = 1380.0, 998.2
    diameter = 2 * (a*b*b)**(1/3)
    sphericity = model.finite_re.prolate_sphericity(a, b)
    mass, _ = model.generalized_mass_matrix([1, 0, 0], a, b, density_particle, density_fluid, 1)
    resistance = model.stokes_generalized_resistance([1, 0, 0], a, b, mu)
    lubrication = np.zeros((6, 6))
    contacts = [
        (11, 0.0, np.array([0.0, 1.0, 0.0]), np.array([0.0, -b, 0.0])),
        (17, 0.0, np.array([0.0, -1.0, 0.0]), np.array([0.0, b, 0.0])),
    ]
    initial_local = np.array([2.0, 0.2, -0.1, 3.0, -0.4, 0.3])
    world = model.local_reactions_to_world(contacts, initial_local)
    roundtrip = model.world_reactions_to_local(contacts, world)
    rotated = [
        (11, 0.0, np.array([0.01, np.sqrt(1-0.01**2), 0.0]), np.array([0.0, -b, 0.0])),
        contacts[1],
    ]
    rotated_local = model.world_reactions_to_local(rotated, world)
    rotated_world = model.local_reactions_to_world(rotated, rotated_local)
    stale_removed = model.world_reactions_to_local([contacts[0]], world)

    old = np.array([0.001, 0.004, 0, 0, 0, 0])
    background = np.zeros(6)
    load = np.zeros(6)
    cold_velocity, cold_health = model.inertial_contact_step(
        old, background, load, resistance, lubrication, mass, contacts, a, 1e-4,
        0.3, density_fluid, mu, diameter, sphericity,
    )
    warm_velocity, warm_health = model.inertial_contact_step(
        old, background, load, resistance, lubrication, mass, contacts, a, 1e-4,
        0.3, density_fluid, mu, diameter, sphericity,
        world_reactions=cold_health["reaction_world_by_grain"],
    )
    checks = {
        "local_world_roundtrip": np.linalg.norm(roundtrip - initial_local) <= 1e-12,
        "rotated_frame_preserves_world_vectors": max(np.linalg.norm(np.asarray(rotated_world[key]) - np.asarray(world[key])) for key in world) <= 1e-12,
        "stale_contact_removed": stale_removed.shape == (3,),
        "warm_cold_velocity_equivalent": np.linalg.norm(warm_velocity - cold_velocity) <= 1e-10,
        "warm_not_more_iterations": warm_health["total_contact_iterations"] <= cold_health["total_contact_iterations"],
        "momentum_closure": max(cold_health["momentum_residual"], warm_health["momentum_residual"]) <= 1e-8,
        "contact_closure": max(cold_health["contact"]["residual"], warm_health["contact"]["residual"]) <= 1e-8,
    }
    result = {"completed": True, "passed": all(checks.values()),
              "checks": {key: bool(value) for key, value in checks.items()},
              "values": {"cold_iterations": cold_health["total_contact_iterations"],
                         "warm_iterations": warm_health["total_contact_iterations"],
                         "velocity_difference": float(np.linalg.norm(warm_velocity-cold_velocity))},
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(model.__file__).resolve()): sha(model.__file__),
                                str(Path(model.previous.__file__).resolve()): sha(model.previous.__file__)},
              "scope": "cross-step reaction transport and solver equivalence only"}
    (output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
