import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import lubrication_contact_v2 as model


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    a, b, mu = 0.0002, 0.00005, 0.001002
    mobility = np.diag([2e5, 1.5e5, 1.7e5, 9e4, 8e4, 7e4])
    vfree = np.array([1e-4, -2e-5, 3e-5, 2e-5, -1e-5, 4e-5])
    axis = np.array([1.0, 0.0, 0.0])
    # Two different grain sizes at the same normalized gap.
    radii = [0.0003007400398208087, 0.0005873723409295079]
    contacts = []
    for grain_id, (radius, normal, lever) in enumerate(zip(
        radii,
        ([0, 1, 0], [0, 0, 1]),
        ([0, -b, 0], [0, 0, -b]),
    )):
        contacts.append((grain_id, 0.1 * radius, normal, lever, radius))
    motion, corrected, health = model.lubricated_motion(
        vfree, mobility, contacts, axis, a, b, a, mu, 0.2, 0.01
    )
    normalized_cutoffs = [row["cutoff"] / row["grain_radius"] for row in health["contacts"]]
    normalized_roughness = [row["roughness"] / row["grain_radius"] for row in health["contacts"]]
    coefficients = [row["excess_coefficient"] for row in health["contacts"]]
    checks = {
        "per_grain_cutoff_ratio_exact": max(abs(x - 0.2) for x in normalized_cutoffs) <= 1e-15,
        "per_grain_roughness_ratio_exact": max(abs(x - 0.01) for x in normalized_roughness) <= 1e-15,
        "distinct_grain_coefficients": coefficients[0] != coefficients[1],
        "positive_symmetric": health["minimum_mobility_eigenvalue"] > 0 and health["mobility_symmetry_residual"] <= 1e-12,
        "finite_motion": np.isfinite(motion).all(),
        "added_resistance_positive_semidefinite": np.linalg.eigvalsh(np.linalg.inv(corrected) - np.linalg.inv(mobility)).min() >= -1e-12,
    }
    sources = [Path(__file__), Path(model.__file__)]
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "health": health,
        "motion": motion.tolist(),
        "source_hashes": {str(path.resolve()): sha(path) for path in sources},
        "scope": "polydisperse algebra and scaling only; no trajectory or release claim",
    }
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
