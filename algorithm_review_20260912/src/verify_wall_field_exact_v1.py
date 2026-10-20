"""Exact-output, boundary, invalid-state and analytic checks of field sampling."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

import wall_field_exact_v1 as candidate

ROOT = Path(__file__).resolve().parents[2]
SEED = 20260912


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def outcome(call):
    try:
        value = call()
        return ("ok", value)
    except Exception as exc:
        return (type(exc).__name__, str(exc))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sources = (Path(__file__).resolve(), Path(candidate.__file__).resolve(),
               ROOT / "stage39_staging/wall_field_v1.py")
    hashes_before = {str(path): digest(path) for path in sources}
    rng = np.random.default_rng(SEED)
    checks = {}
    max_velocity_delta = max_gradient_delta = 0.0
    comparisons = mixed_stencils = 0
    benchmark_fields = None
    shape = (7, 9, 11)
    fluid = rng.random(shape) > 0.35
    source = rng.normal(size=(3, *shape))
    source[:, ~fluid] = 0.0
    checks["input_values_unchanged"] = True
    checks["exact_velocity_and_gradient"] = True
    checks["same_arrays_referenced"] = True
    for spacing in (1e-12, 1e-7, 2.5e-5, 0.3, 1e5):
        for amplitude in (1e-12, 1e-4, 1.0, 1e6):
            data = source * amplitude
            original = data.copy()
            baseline = candidate.ReferenceWallCellField(data, spacing, fluid)
            fast = candidate.WallCellFieldExact.from_field(baseline)
            checks["same_arrays_referenced"] &= bool(fast.u is baseline.u and fast.fluid is baseline.fluid)
            positions = list(rng.uniform(-2, 3, size=(120, 3)) * np.asarray(shape) * spacing)
            # Cell centres, boundaries, periodic wrap and adjacent floating values.
            for axis in range(3):
                for boundary in (-shape[axis], -0.5, 0.0, 0.5, shape[axis] - 0.5, shape[axis]):
                    point = np.array([1.5, 2.5, 3.5]) * spacing
                    point[axis] = boundary * spacing
                    positions.extend((point.copy(), np.nextafter(point, np.inf), np.nextafter(point, -np.inf)))
            for position in positions:
                bv, bg = baseline.sample(position)
                fv, fg = fast.sample(position)
                checks["exact_velocity_and_gradient"] &= bool(np.array_equal(bv, fv) and np.array_equal(bg, fg))
                max_velocity_delta = max(max_velocity_delta, float(np.max(np.abs(bv - fv))))
                max_gradient_delta = max(max_gradient_delta, float(np.max(np.abs(bg - fg))))
                comparisons += 1
                lower = np.floor(position / spacing - 0.5).astype(int)
                values = [fluid[tuple((lower + bit) % shape)] for bit in candidate._BITS]
                mixed_stencils += int(any(values) and not all(values))
            checks["input_values_unchanged"] &= bool(np.array_equal(data, original))
            if spacing == 2.5e-5 and amplitude == 1e-4:
                benchmark_fields = baseline, fast, positions
    checks["mixed_solid_fluid_stencils_exercised"] = mixed_stencils > 0

    invalid = ([1, 2], [1, 2, 3, 4], [0, np.nan, 0], [0, np.inf, 0], 1.0)
    baseline, fast, positions = benchmark_fields
    checks["invalid_position_exception_equivalence"] = all(
        outcome(lambda p=p: baseline.sample(p)) == outcome(lambda p=p: fast.sample(p))
        for p in invalid)
    construction_cases = (
        (np.zeros((2, 3, 3, 3)), 1.0, np.ones((3, 3, 3), bool)),
        (np.zeros((3, 3, 3, 3)), 1.0, np.ones((3, 3), bool)),
        (np.zeros((3, 3, 3, 3)), 0.0, np.ones((3, 3, 3), bool)),
        (np.full((3, 3, 3, 3), np.nan), 1.0, np.ones((3, 3, 3), bool)),
        (np.ones((3, 3, 3, 3)), 1.0, np.zeros((3, 3, 3), bool)),
    )
    checks["invalid_constructor_exception_equivalence"] = all(
        outcome(lambda arg=arg: candidate.ReferenceWallCellField(*arg)) ==
        outcome(lambda arg=arg: candidate.WallCellFieldExact(*arg))
        for arg in construction_cases)
    checks["wrong_field_type_rejected"] = outcome(lambda: candidate.WallCellFieldExact.from_field(object()))[0] == "TypeError"
    # Caller mutation has the same effect as the reference: no stale value cache.
    baseline.u[0, 0, 0, 0] += 1.0
    checks["no_stale_field_value_cache"] = all(np.array_equal(a, b) for a, b in
        zip(baseline.sample(np.array([0.5, 0.5, 0.5]) * baseline.dx),
            fast.sample(np.array([0.5, 0.5, 0.5]) * baseline.dx)))

    # Independent multilinear polynomial is reconstructed exactly inside the grid.
    spacing = 0.25
    grid = (np.indices((6, 6, 6)) + 0.5) * spacing
    coefficient = rng.normal(size=(3, 8))

    def polynomial(point):
        x, y, z = point
        basis = np.array([1, x, y, z, x*y, x*z, y*z, x*y*z])
        derivative = np.array([[0, 1, 0, 0, y, z, 0, y*z],
                               [0, 0, 1, 0, x, 0, z, x*z],
                               [0, 0, 0, 1, 0, x, y, x*y]])
        return coefficient @ basis, coefficient @ derivative.T

    native = np.empty((3, 6, 6, 6))
    for index in np.ndindex(6, 6, 6):
        native[(slice(None),) + index] = polynomial(grid[(slice(None),) + index])[0]
    analytic_field = candidate.WallCellFieldExact(native, spacing, np.ones((6, 6, 6), bool))
    analytic_velocity_error = analytic_gradient_error = 0.0
    for point in rng.uniform(0.125, 1.375, size=(256, 3)):
        expected_v, expected_g = polynomial(point)
        sampled_v, sampled_g = analytic_field.sample(point)
        analytic_velocity_error = max(analytic_velocity_error, float(np.max(abs(expected_v-sampled_v))))
        analytic_gradient_error = max(analytic_gradient_error, float(np.max(abs(expected_g-sampled_g))))
    checks["analytic_multilinear_field"] = analytic_velocity_error < 2e-13 and analytic_gradient_error < 2e-13
    checks["immutable_stencil_indices"] = all(not b.flags.writeable for b in candidate._BITS)

    # Paired alternating-order microbenchmark; no whole-trajectory speed claim.
    timings = {"baseline": [], "candidate": []}
    for repeat in range(5):
        names = ("baseline", "candidate") if repeat % 2 == 0 else ("candidate", "baseline")
        for name in names:
            field = baseline if name == "baseline" else fast
            start = time.perf_counter()
            for point in positions:
                field.sample(point)
            timings[name].append(time.perf_counter() - start)
    hashes_after = {str(path): digest(path) for path in sources}
    checks["sources_unchanged"] = hashes_before == hashes_after
    result = {
        "passed": all(checks.values()), "checks": {k: bool(v) for k, v in checks.items()},
        "comparison_samples": comparisons, "mixed_stencil_samples": mixed_stencils,
        "max_velocity_delta": max_velocity_delta, "max_gradient_delta": max_gradient_delta,
        "analytic_velocity_max_abs_error": analytic_velocity_error,
        "analytic_gradient_max_abs_error": analytic_gradient_error,
        "benchmark_seconds": timings,
        "benchmark_median_speedup": float(np.median(timings["baseline"]) / np.median(timings["candidate"])),
        "seed": SEED, "python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "command": sys.argv,
        "hashes_before": hashes_before, "hashes_after": hashes_after,
        "scope": "Unchanged local trilinear interpolation. Primitive timing only; no physical or campaign qualification.",
    }
    (args.output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ("hashes_before", "hashes_after", "benchmark_seconds")}, indent=2), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
