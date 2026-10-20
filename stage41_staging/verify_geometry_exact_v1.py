"""Reproducible equivalence and bounded-angle sweep checks for Stage41 geometry."""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy

import geometry_exact_v1 as optimized
import transport_contact as reference
import trajectory as reference_trajectory

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def error_or_value(function, *args):
    try:
        return None, function(*args)
    except (ValueError, FloatingPointError, RuntimeError) as exc:
        return (type(exc).__name__, str(exc)), None


def contact_equal(left, right):
    return (len(left) == len(right)
            and all(a[0] == b[0] and a[1] == b[1]
                    and np.array_equal(a[2], b[2]) and np.array_equal(a[3], b[3])
                    for a, b in zip(left, right)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    rng = np.random.default_rng(410912)
    checks, details = {}, {}
    scales = (1e-7, 2e-4, 1.0, 10.0)
    aspects = (1.0, 1+5e-14, 1+2e-13, 2.0, 4.0, 10.0, 100.0)
    point_count = 0
    point_mismatches = 0
    largest_point_error = 0.0
    interior_rejections = 0
    residual_surface = 0.0
    residual_normal = 0.0
    for a in scales:
        for aspect in aspects:
            b = a/aspect
            for _ in range(32):
                p = reference.unit(rng.normal(size=3))
                x = rng.uniform(-1, 1, 3)*a
                direction = reference.unit(rng.normal(size=3))
                transverse = direction - np.dot(direction, p)*p
                surface = a*np.dot(direction, p)*p + b*transverse
                normal = reference.unit(np.dot(surface, p)*p/a**2
                                        + (surface-np.dot(surface, p)*p)/b**2)
                clearance = a*10**rng.uniform(-14, 1)
                c = x + surface + clearance*normal
                radius = a*10**rng.uniform(-3, 0)
                err1, value1 = error_or_value(reference.ellipsoid_grain_contact,
                                              x, p, a, b, c, radius)
                err2, value2 = error_or_value(optimized._gap_at_pose,
                                              x, p, a, b, c, radius)
                point_count += 1
                if err1 != err2:
                    point_mismatches += 1
                elif err1 is None:
                    point_mismatches += int(value1[0] != value2)
                    largest_point_error = max(largest_point_error, abs(value1[0]-value2)/a)
                    # Independent ellipsoid-surface and gradient-normal identities.
                    gap, n, lever = value1
                    parallel = np.dot(lever, reference.unit(p))*reference.unit(p)
                    transverse = lever-parallel
                    residual_surface = max(residual_surface, abs(
                        np.dot(parallel, parallel)/a**2
                        + np.dot(transverse, transverse)/b**2 - 1))
                    grad = parallel/a**2+transverse/b**2
                    # The reference's fixed root tolerance degrades for near-zero
                    # separation; log this rather than silently relaxing physics.
                    if np.linalg.norm(x+lever-c) > 1e-7*a:
                        residual_normal = max(residual_normal,
                                              np.linalg.norm(reference.unit(grad)+n))
            for center in (np.zeros(3), np.array([.5*a, 0, 0])):
                exc1, _ = error_or_value(reference.ellipsoid_grain_contact,
                                         np.zeros(3), [1, 0, 0], a, b, center, b)
                exc2, _ = error_or_value(optimized._gap_at_pose,
                                         np.zeros(3), [1, 0, 0], a, b, center, b)
                interior_rejections += int(exc1 == exc2 and exc1 is not None)
    checks["point_gaps_bitwise_equal"] = point_mismatches == 0
    checks["deep_overlap_rejection_preserved"] = interior_rejections == len(scales)*len(aspects)*2
    details["closest_point"] = {"cases": point_count, "mismatches": point_mismatches,
                                "maximum_gap_difference_over_a": largest_point_error,
                                "reference_surface_residual": residual_surface,
                                "reference_normal_residual_when_separation_over_a_gt_1e_7": residual_normal,
                                "aspect_ratios": aspects, "major_semiaxes": scales}

    pose_mismatches = 0
    for count in range(300):
        a = 10**rng.uniform(-7, 1)
        x = rng.normal(size=3)*a
        p = rng.normal(size=3)
        v = rng.normal(size=6)*a
        if count % 5 == 0:
            v[3:] = 0
        dt = rng.uniform(0, .02)
        move = optimized._FixedMotion(x, p, v, a)
        for step in (0.0, dt/2, dt):
            first = reference.advance_pose(x, p, v, a, step)
            second = move.at(step)
            pose_mismatches += int(any(not np.array_equal(one, two)
                                      for one, two in zip(first, second)))
    checks["hoisted_poses_bitwise_equal"] = pose_mismatches == 0
    details["pose_cases"] = 900

    a, b, length = 2e-4, 5e-5, .01
    centres = rng.uniform(0, length, (216, 3))
    radii = rng.uniform(1e-4, 5e-4, 216)
    regular = reference.GrainGeometry(centres, radii, length)
    cached = optimized.GrainGeometry(centres, radii, length)
    contact_mismatches = 0
    contact_queries = 0
    for _ in range(200):
        x, p = rng.uniform(-length, 2*length, 3), rng.normal(size=3)
        for skin in (0.0, 2e-4, 1e-5, 0.0, 2e-4):
            exc1, one = error_or_value(regular.contacts, x, p, a, b, skin)
            exc2, two = error_or_value(cached.contacts, x, p, a, b, skin)
            contact_queries += 1
            contact_mismatches += int(exc1 != exc2 or (exc1 is None and not contact_equal(one, two)))
    checks["cached_contacts_bitwise_equal"] = contact_mismatches == 0
    details["contacts"] = {"queries": contact_queries, "mismatches": contact_mismatches,
                            "cache": cached.stats}
    input_snapshot = cached.c.copy()
    centres[:] = -123.0
    immutable = np.array_equal(cached.c, input_snapshot)
    for array in (cached.c, cached.r, cached.tree.data):
        try:
            array.flags.writeable = True
            immutable = False
        except ValueError:
            pass
    checks["grain_inputs_immutable"] = immutable

    # Known flank contact; each equality-at-skin branch and caller mutation.
    one_grain = optimized.GrainGeometry([[.5, .5+.1+.04, .5]], [.04], 1.0)
    initial = one_grain.contacts([.5, .5, .5], [1, 0, 0], .2, .1, .01)
    gap = initial[0][1]
    edge_skins = (np.nextafter(gap, -np.inf), gap, np.nextafter(gap, np.inf))
    baseline = reference.GrainGeometry(one_grain.c, one_grain.r, one_grain.L)
    checks["skin_thresholds_preserved"] = all(
        contact_equal(baseline.contacts([.5, .5, .5], [1, 0, 0], .2, .1, skin),
                      one_grain.contacts([.5, .5, .5], [1, 0, 0], .2, .1, skin))
        for skin in edge_skins)
    initial[0][2][:] = 5
    initial[0][3][:] = 5
    checks["caller_cannot_corrupt_contact_cache"] = contact_equal(
        baseline.contacts([.5, .5, .5], [1, 0, 0], .2, .1, .01),
        one_grain.contacts([.5, .5, .5], [1, 0, 0], .2, .1, .01))

    # Near-contact rotating/translating prolate trials spanning tip, flank,
    # simultaneous grains, large unwrapped coordinates, stationary poses,
    # and near-spherical branches. Bounds match the trajectory's angle limit.
    sweep_rows, cases = [], []
    for index in range(32):
        a = 2e-4
        aspect = (1, 1+5e-14, 2, 4, 10, 100, 4, 4)[index % 8]
        b = a/aspect
        p = reference.unit(rng.normal(size=3))
        x = np.array([.004, .004, .004])
        grain_centres, grain_radii = [], []
        for j in range(1+(index % 3)):
            direction = reference.unit(rng.normal(size=3))
            if index % 4 == 0:
                direction = p if j == 0 else -p
            if index % 4 == 1:
                direction = reference.unit(np.cross(p, [1, 0, 0]))
            transverse = direction - np.dot(direction, p)*p
            lever = a*np.dot(direction, p)*p+b*transverse
            parallel = np.dot(lever, p)*p
            normal = reference.unit(parallel/a**2+(lever-parallel)/b**2)
            radius = .3*a
            initial_gap = (-1, 0, 1, 100)[index % 4]*1e-7*b
            grain_centres.append(x+lever+(radius+initial_gap)*normal)
            grain_radii.append(radius)
        geometry = reference.GrainGeometry(grain_centres, grain_radii, .01)
        if index % 7 == 0:
            x = x+np.array([-.02, .03, -.01])
        dt = .003
        v = rng.normal(size=6)
        v[:3] = reference.unit(v[:3])*.08*b/dt
        v[3:] = reference.unit(v[3:])*.019*a/dt
        if index % 6 == 0:
            v[:] = 0
        cases.append((geometry, x, p, v, a, b, dt))
        baseline_gap = reference_trajectory.swept_gap(*cases[-1])
        candidate_gap = optimized.swept_gap(*cases[-1])
        dense_count = 1501
        dense_min = np.inf
        for sample_time in np.linspace(0, dt, dense_count):
            xx, pp = reference.advance_pose(x, p, v, a, sample_time)
            for k in range(len(geometry.r)):
                d = geometry.c[k]-x
                d -= geometry.L*np.round(d/geometry.L)
                c = x+d
                dense_min = min(dense_min, reference.ellipsoid_grain_contact(
                    xx, pp, a, b, c, geometry.r[k])[0])
        # The distance function is 1-Lipschitz under rigid surface motion.
        bound = (np.linalg.norm(v[:3])+np.linalg.norm(v[3:]))*dt/(2*(dense_count-1))
        numerical = 1e-10*a
        sweep_rows.append({"case": index, "aspect_ratio": aspect,
                           "baseline_gap": baseline_gap, "candidate_gap": candidate_gap,
                           "dense_minimum": dense_min, "dense_error_bound": bound,
                           "bitwise_equal": baseline_gap == candidate_gap,
                           "same_penetration_decision": bool((baseline_gap < -1e-5*b) == (candidate_gap < -1e-5*b)),
                           "dense_check": bool(-numerical <= dense_min-candidate_gap <= bound+numerical)})
    empty = reference.GrainGeometry([[.008, .008, .008]], [1e-5], .01)
    empty_args = (empty, np.zeros(3), np.array([1., 0, 0]), np.zeros(6), 2e-4, 5e-5, .001)
    checks["empty_sweep_preserved"] = (reference_trajectory.swept_gap(*empty_args)
                                         == optimized.swept_gap(*empty_args) == np.inf)
    checks["sweeps_bitwise_equal"] = all(row["bitwise_equal"] for row in sweep_rows)
    checks["sweep_penetration_decisions_preserved"] = all(row["same_penetration_decision"] for row in sweep_rows)
    checks["sweeps_agree_with_dense_sampling_bound"] = all(row["dense_check"] for row in sweep_rows)
    details["sweeps"] = sweep_rows
    # Alternating timing order reduces warm-cache and monotone load bias.
    timings = {"baseline": [], "optimized": []}
    for repeat in range(5):
        names = ("baseline", "optimized") if repeat % 2 == 0 else ("optimized", "baseline")
        for name in names:
            function = reference_trajectory.swept_gap if name == "baseline" else optimized.swept_gap
            tick = time.perf_counter()
            for case in cases:
                function(*case)
            timings[name].append(time.perf_counter()-tick)
    details["sweep_benchmark"] = {**timings, "median_speedup": float(
        np.median(timings["baseline"])/np.median(timings["optimized"]))}
    sources = [Path(__file__), Path(optimized.__file__), Path(reference.__file__),
               Path(reference_trajectory.__file__)]
    result = {"completed": True, "passed": all(checks.values()), "checks": checks,
              "details": details, "seed": 410912,
              "runtime_seconds": time.perf_counter()-started,
              "environment": {"python": sys.version, "numpy": np.__version__,
                              "scipy": scipy.__version__, "platform": platform.platform()},
              "command": sys.argv, "working_directory": str(Path.cwd()),
              "hashes": {str(path.resolve()): sha(path) for path in sources},
              "claim_boundary": "Numerical equivalence in fixed periodic prolate geometry. Dense bounded-angle checks are not a global proof of sweep minimization or physical validation."}
    (output/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({"passed": result["passed"], "checks": checks,
                      "sweep_benchmark": details["sweep_benchmark"],
                      "closest_point": details["closest_point"]}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
