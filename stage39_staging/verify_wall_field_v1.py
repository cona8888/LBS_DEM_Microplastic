"""Verification of the deliberately voxel-bound wall field interpolator."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import wall_field_v1 as model


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)

    n = 8
    dx = 0.1
    indices = np.indices((n, n, n), dtype=float)
    centres = (indices + 0.5) * dx
    velocity = np.stack((
        0.2 + 0.3 * centres[0] - 0.1 * centres[1],
        -0.1 + 0.2 * centres[1] + 0.05 * centres[2],
        0.4 - 0.15 * centres[0] + 0.1 * centres[2],
    ))
    fluid = np.ones((n, n, n), bool)
    field = model.WallCellField(velocity, dx, fluid)
    point = np.array([0.37, 0.44, 0.26])
    value, gradient = field.sample(point)
    exact = np.array([
        0.2 + 0.3 * point[0] - 0.1 * point[1],
        -0.1 + 0.2 * point[1] + 0.05 * point[2],
        0.4 - 0.15 * point[0] + 0.1 * point[2],
    ])
    exact_gradient = np.array([[0.3, -0.1, 0], [0, 0.2, 0.05], [-0.15, 0, 0.1]])

    wall_velocity = np.ones((3, n, n, n))
    wall_fluid = np.ones((n, n, n), bool)
    wall_fluid[:3] = False
    wall_velocity[:, ~wall_fluid] = 0
    wall = model.WallCellField(wall_velocity, dx, wall_fluid)
    mixed_point = np.array([0.3, 0.35, 0.45])
    mixed_value, mixed_gradient = wall.sample(mixed_point)
    periodic_value, periodic_gradient = wall.sample(mixed_point + np.array([n * dx, 0, 0]))
    epsilon = 1e-6
    finite_difference = np.column_stack([
        (wall.sample(mixed_point + epsilon * np.eye(3)[axis])[0]
         - wall.sample(mixed_point - epsilon * np.eye(3)[axis])[0]) / (2 * epsilon)
        for axis in range(3)
    ])
    rejected_nonzero_solid = False
    try:
        bad = wall_velocity.copy()
        bad[0, 0, 0, 0] = 1e-12
        model.WallCellField(bad, dx, wall_fluid)
    except ValueError:
        rejected_nonzero_solid = True

    checks = {
        "linear_velocity_exact": np.linalg.norm(value - exact) <= 1e-12,
        "linear_gradient_exact": np.linalg.norm(gradient - exact_gradient) <= 1e-12,
        "mixed_stencil_finite": np.isfinite(mixed_value).all() and np.isfinite(mixed_gradient).all(),
        "mixed_velocity_convex_bound": np.all(mixed_value >= 0) and np.all(mixed_value <= 1),
        "gradient_matches_finite_difference": np.linalg.norm(mixed_gradient - finite_difference) <= 1e-8,
        "periodic_exact": np.linalg.norm(mixed_value - periodic_value) <= 1e-14 and np.linalg.norm(mixed_gradient - periodic_gradient) <= 1e-14,
        "nonzero_solid_rejected": rejected_nonzero_solid,
    }
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "values": {
            "linear_velocity_error": float(np.linalg.norm(value - exact)),
            "linear_gradient_error": float(np.linalg.norm(gradient - exact_gradient)),
            "mixed_velocity": mixed_value.tolist(),
            "mixed_gradient": mixed_gradient.tolist(),
        },
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__), str(Path(model.__file__).resolve()): sha(model.__file__)},
        "scope": "native voxel interpolation only; no sub-grid wall accuracy claim",
    }
    (output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
