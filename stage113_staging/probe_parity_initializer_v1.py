"""Diagnose localisation and test a one-time population-phase initializer.

No force/contact/flow equation changes and no running filter. One reference
CPD2 packing only. Results are not promoted to transport-ready fields.
"""
from __future__ import annotations

import argparse
import gc
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

import audit_flow_time_levels_v1 as audit

legacy = audit.legacy
ROOT = audit.ROOT


def case_for(phase, acceleration, name):
    nz, ny, nx = phase.shape
    return {"case_id": name, "dimensions_lu": [nx, ny, nz],
            "center_offset_lu": [0., 0., 0.], "_stage17_mask": phase,
            "expected_mask_sha256": audit.digest(phase),
            "boundary_mode": legacy.stage13.BOUNDARY_TRIPLY_PERIODIC,
            "acceleration_realized_float32_lu": float(np.float32(acceleration))}


def one_step(driver, state, phase, case):
    session = legacy.stage13.CudaCandidateSession(driver, state, phase, case,
        tau=.8, threads=256, maximum_steps=1)
    try:
        session.step(1)
        result = session.copy_current()
        assert legacy.stage13.split_numerical_health_code(session.health_code(), "candidate")["fatal_sticky_code"] == 0
        return result
    finally:
        session.close()


def average_states(a, b):
    # Binary64 addition then one float32 rounding; this is initialization only.
    result = np.empty_like(a)
    for q in range(19):
        result[q] = ((a[q].astype(np.float64) + b[q]) * .5).astype(np.float32)
    return result


def observe(state, phase, case):
    return legacy.stage13.copied_state_observables(state, phase, case, retain_velocity=True)


def steady_metric(state, phase, case, obs):
    stored, pulled = audit.independent_momentum(state, phase)
    b = obs["body_force_drag_lu"]
    return float(np.linalg.norm(np.array([b, 0, 0]) - stored + pulled) / abs(b))


def cavity_test(driver):
    phase = np.full((3, 3, 3), 2, dtype=np.uint8)
    phase[1, 1, 1] = 0
    case = case_for(phase, 1e-5, "isolated_fluid_voxel")
    state = np.zeros((19, 3, 3, 3), dtype=np.float32)
    first = one_step(driver, state, phase, case)
    averaged = average_states(state, first)
    rows = []
    for label, initial in [("zero", state), ("phase_averaged", averaged)]:
        current = initial
        data = []
        for step in range(5):
            obs = observe(current, phase, case)
            p, _ = audit.independent_momentum(current, phase)
            following = one_step(driver, current, phase, case)
            p_next, _ = audit.independent_momentum(following, phase)
            predicted = -p + np.array([obs["body_force_drag_lu"], 0, 0])
            data.append({"step": step, "u_x": float(obs["velocity_xyz_lu"][0, 1, 1, 1]),
                         "stored_p_x": float(p[0]),
                         "analytic_recurrence_relative_residual": float(np.linalg.norm(p_next - predicted) / obs["body_force_drag_lu"])})
            current = following
        rows.append({"initializer": label, "rows": data})
    return {"model": "One isolated fluid node: all nonrest populations bounce. Collision preserves local momentum plus body impulse.",
            "derived_recurrence": "p[n+1] = -p[n] + B; fixed p = B/2; incoming physical u = (-p+B/2)/rho = 0.",
            "results": rows,
            "passed": all(r["analytic_recurrence_relative_residual"] < 1e-6 for x in rows for r in x["rows"])
                      and max(abs(r["u_x"]) for r in rows[1]["rows"]) < 1e-10}


def localize(first, second, phase, case):
    u0 = observe(first, phase, case)["velocity_xyz_lu"]
    u1 = observe(second, phase, case)["velocity_xyz_lu"]
    d2 = np.sum((u1.astype(np.float64) - u0)**2, axis=0)
    fluid = phase == 0
    degree = np.zeros(phase.shape, dtype=np.uint8)
    for direction in legacy.stage13.DIRECTIONS_I64[1:]:
        degree += np.roll(fluid, tuple(int(x) for x in direction[::-1]), axis=(0, 1, 2))
    counts = []
    total = float(d2.sum())
    for limit in [0, 1, 2, 3, 4, 6, 9, 12, 18]:
        mask = fluid & (degree <= limit)
        counts.append({"max_D3Q19_fluid_degree": limit, "fluid_fraction": float(mask.sum() / fluid.sum()),
                       "fraction_of_squared_oscillation": float(d2[mask].sum() / total)})
    # Components use D3Q19 neighbours but nonperiodic labels. Mark boundary-
    # touching components explicitly; do not mistake this for wrapping analysis.
    structure = np.zeros((3, 3, 3), dtype=np.uint8)
    for direction in legacy.stage13.DIRECTIONS_I64:
        structure[tuple(direction[::-1] + 1)] = 1
    labels, ncomp = ndimage.label(fluid, structure=structure)
    sizes = np.bincount(labels.ravel())
    energy = np.bincount(labels.ravel(), weights=d2.ravel())
    main = int(np.argmax(sizes[1:]) + 1)
    return {"degree_bins": counts, "nonperiodic_component_count": ncomp,
            "largest_component_fluid_fraction": float(sizes[main] / fluid.sum()),
            "largest_component_squared_oscillation_fraction": float(energy[main] / total),
            "interpretation_boundary": "Degree and nonperiodic component localisation are diagnostics, not exact transport-accessible pore classification."}


def relax(driver, initial, phase, case, output, name, max_steps):
    start = time.perf_counter()
    session = legacy.stage13.CudaCandidateSession(driver, initial, phase, case,
        tau=.8, threads=256, maximum_steps=max_steps)
    rows = []
    previous_obs = observe(initial, phase, case)
    previous_state = initial
    final_state = initial
    try:
        for step in range(1, max_steps + 1):
            session.step(step)
            if step % 257 != 0 and step < max_steps - 7:
                continue
            final_state = session.copy_current()
            obs = observe(final_state, phase, case)
            vector_change = float(np.linalg.norm(obs["velocity_xyz_lu"].astype(np.float64) - previous_obs["velocity_xyz_lu"])
                                  / np.linalg.norm(obs["velocity_xyz_lu"].astype(np.float64)))
            row = {"step": step, "u_superficial": obs["superficial_velocity_lu"],
                   "delta_mean_relative": obs["superficial_velocity_lu"] / previous_obs["superficial_velocity_lu"] - 1,
                   "field_change_relative_l2": vector_change,
                   "steady_force_balance_relative": steady_metric(final_state, phase, case, obs),
                   "mean_density": obs["mean_density"], "maximum_speed_lu": obs["maximum_speed_lu"],
                   "fatal_health_code": legacy.stage13.split_numerical_health_code(session.health_code(), "candidate")["fatal_sticky_code"]}
            if step >= max_steps - 7:
                after = one_step(driver, final_state, phase, case)
                p0, pp = audit.independent_momentum(final_state, phase)
                p1, _ = audit.independent_momentum(after, phase)
                b = obs["body_force_drag_lu"]
                row["dynamic_momentum_residual_relative"] = float(np.linalg.norm(np.array([b, 0, 0]) - p0 + pp - p1 + p0) / b)
            rows.append(row)
            previous_obs, previous_state = obs, final_state
            if step % (257 * 16) == 0:
                print(name, step, "field_change", vector_change, flush=True)
        final = observe(final_state, phase, case)
        health = legacy.stage13.split_numerical_health_code(session.health_code(), "candidate")
    finally:
        session.close()
    regular = [x for x in rows if x["step"] % 257 == 0]
    last = rows[-8:]
    checks = {
        "longer_interval_field_stable": all(x["field_change_relative_l2"] < 5e-5 for x in regular[-4:]),
        "adjacent_field_stable": all(x["field_change_relative_l2"] < 5e-5 for x in last[1:]),
        "adjacent_mean_stable": all(abs(x["delta_mean_relative"]) < 5e-5 for x in last[1:]),
        "steady_force_balance": all(x["steady_force_balance_relative"] < .005 for x in last),
        "dynamic_momentum_balance": all(x.get("dynamic_momentum_residual_relative", 1) < .005 for x in last),
        "density_drift": abs(final["mean_density"] - 1) < 5e-6,
        "mach": final["maximum_speed_lu"] * 3**.5 < .05,
        "fatal_health_zero": health["fatal_sticky_code"] == 0,
    }
    path = output / name
    path.mkdir()
    np.savez_compressed(path / "final_shifted_state.npz", phase=phase, shifted_state=final_state)
    np.savez_compressed(path / "final_fields.npz", phase=phase,
                        density_lu=final["density_lu"], velocity_xyz_lu=final["velocity_xyz_lu"])
    result = {"initial_state_sha256": audit.digest(initial), "case": name, "steps": max_steps,
              "rows": rows, "checks": checks, "passed": all(checks.values()),
              "runtime_seconds": time.perf_counter() - start, "numerical_health": health,
              "field_sha256": audit.sha(path / "final_fields.npz"),
              "state_sha256": audit.sha(path / "final_shifted_state.npz")}
    audit.write(path / "result.json", result)
    print(name, "PASSED", result["passed"], checks, flush=True)
    return result, final["velocity_xyz_lu"], final["density_lu"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / "stage113_evaluations")
    assert not output.exists()
    baseline = ROOT / "stage113_evaluations/temporal_flow_consistency_20260915/audit_01"
    proof = audit.read(baseline / "completion.json")
    assert proof["inputs_unchanged"] and not proof["steady_reuse_passed"]
    evidence = audit.read(baseline / "stage111_s2_clean_f1p0_cpd2.json")
    source = evidence["source"]
    assert audit.sha(source["record"]) == source["record_sha256"]
    for name in ["final_fields", "final_shifted_state", "audit"]:
        assert audit.sha(source[name]["path"]) == source[name]["sha256"]
    design = audit.read(baseline / "manifest.json")
    for item in design["lineage"].values():
        if isinstance(item, dict) and "path" in item:
            assert audit.sha(item["path"]) == item["sha256"]
    output.mkdir(parents=True)
    manifest = {"schema": "matdem.stage113.phase-initialization-diagnostic.v1",
                "source": source, "runner_sha256": audit.sha(__file__),
                "audit_module_sha256": audit.sha(audit.__file__), "audit_completion_sha256": audit.sha(baseline / "completion.json"),
                "experiment": "One-time arithmetic average of consecutive stored population states, then unchanged GPU update without filtering.",
                "initializers": {"archive_phase_average": 4096, "cold_first_step_average": 24000},
                "interval": 257, "final_consecutive_samples": 8,
                "comparison_gate": {"field_relative_l2": 2e-4, "mean_relative": 5e-5},
                "claim_boundary": "Diagnostic only. Requires independent evaluation and reproduction across remaining fields before transport reuse.",
                "lineage": design["lineage"]}
    audit.write(output / "manifest.json", manifest)
    legacy.install_generic_mask_oracle()
    adapter = {"lineage": {"cuda_source": design["lineage"]["cuda_source"]["path"],
                           "qualified_ptx_sha256": design["lineage"]["qualified_ptx_sha256"]}}
    driver, build = legacy.create_driver(adapter, Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin"), 0)
    try:
        toy = cavity_test(driver)
        audit.write(output / "isolated_voxel_test.json", toy)
        assert toy["passed"], "analytical isolated-voxel recurrence failed"
        record = audit.read(source["record"])
        with np.load(source["final_shifted_state"]["path"]) as f:
            state, phase = f["shifted_state"], f["phase"]
        case = case_for(phase, record["acceleration_lu"], "seed2_reference_cpd2")
        second = one_step(driver, state, phase, case)
        localization = localize(state, second, phase, case)
        audit.write(output / "localization.json", localization)
        initial = average_states(state, second)
        del state, second
        gc.collect()
        result_a, field_a, rho_a = relax(driver, initial, phase, case, output, "archive_phase_average", 4096)
        cold = np.zeros_like(initial)
        cold_next = one_step(driver, cold, phase, case)
        initial_cold = average_states(cold, cold_next)
        del cold, cold_next, initial
        gc.collect()
        result_b, field_b, rho_b = relax(driver, initial_cold, phase, case, output, "cold_first_step_average", 24000)
    finally:
        driver.close()
    difference = float(np.linalg.norm(field_a.astype(np.float64) - field_b) / np.linalg.norm(field_b.astype(np.float64)))
    mean_difference = float(field_a[0].mean(dtype=np.float64) / field_b[0].mean(dtype=np.float64) - 1)
    result = {"status": "diagnostic_complete", "toy_passed": toy["passed"],
              "both_steady_passed": result_a["passed"] and result_b["passed"],
              "independent_initialization_field_relative_l2": difference,
              "independent_initialization_mean_relative": mean_difference,
              "initialization_agreement_passed": difference < 2e-4 and abs(mean_difference) < 5e-5,
              "density_field_max_difference": float(np.max(np.abs(rho_a - rho_b))),
              "manifest_sha256": audit.sha(output / "manifest.json"), "build": build,
              "source_unchanged": audit.sha(source["final_shifted_state"]["path"]) == source["final_shifted_state"]["sha256"],
              "artifact_sha256": {str(p.relative_to(output)): audit.sha(p) for p in output.rglob("*") if p.is_file()},
              "transport_authorized": False}
    audit.write(output / "completion.json", result)
    print(result, flush=True)


if __name__ == "__main__":
    main()
