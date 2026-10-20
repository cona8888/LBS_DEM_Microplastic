"""Independent CPU-side evaluation of the bounded Stage113 initializer test."""
from __future__ import annotations

import argparse
import json
import io
import unittest
from pathlib import Path

import numpy as np

import audit_flow_time_levels_v1 as audit
import steady_flow_gate_v1 as gate
import test_steady_flow_gate_v1 as gate_tests

ROOT = audit.ROOT


def independent_fields(state, phase, accel):
    # Separate float64 implementation; do not reuse native observables.
    fluid = phase == 0
    rho = np.ones(phase.shape, dtype=np.float64)
    momentum = np.zeros((3,) + phase.shape)
    stored_p = np.zeros(3)
    incoming_p = np.zeros(3)
    for q, c in enumerate(audit.legacy.stage13.DIRECTIONS_I64):
        shift = tuple(int(x) for x in c[::-1])
        source_phase = np.roll(phase, shift, axis=(0, 1, 2))
        pulled = np.where(source_phase != 0, state[int(audit.legacy.stage13.OPPOSITE[q])],
                          np.roll(state[q], shift, axis=(0, 1, 2))).astype(np.float64)
        pulled[~fluid] = 0
        rho += pulled
        momentum += c[:, None, None, None] * pulled
        stored_p += c * state[q][fluid].sum(dtype=np.float64)
        incoming_p += c * pulled.sum(dtype=np.float64)
    body = float(np.sum(rho[fluid] * accel, dtype=np.float64))
    velocity = momentum / rho[None]
    velocity[0] += .5 * accel
    velocity[:, ~fluid] = 0
    return velocity, rho, body, stored_p - incoming_p


def cpu_node_residuals(state, phase, acceleration):
    nodes = np.flatnonzero(phase.ravel() == 0)
    # Deterministic stratified C-order sample; all parity classes included where
    # present. This is a spot check, not a full-lattice independent solver.
    selected = nodes[np.linspace(0, len(nodes)-1, 24, dtype=int)]
    rows = []
    dims = np.array(phase.shape)
    oracle = audit.legacy.stage13.arbitrary.frozen_projected_collision_node
    for flat in selected:
        zyx = np.array(np.unravel_index(flat, phase.shape))
        pre = np.zeros(19, dtype=np.float32)
        for q, c in enumerate(audit.legacy.stage13.DIRECTIONS_I64):
            src = tuple((zyx - c[::-1]) % dims)
            pre[q] = state[int(audit.legacy.stage13.OPPOSITE[q])][tuple(zyx)] if phase[src] != 0 else state[q][src]
        calculated = oracle(pre, .8, acceleration)
        actual = state[(slice(None),) + tuple(zyx)]
        rows.append({"node_zyx": zyx.tolist(),
                     "fixed_point_absolute_max_population_residual": float(np.max(np.abs(calculated.astype(np.float64)-actual))),
                     "fixed_point_relative_l2": float(np.linalg.norm(calculated.astype(np.float64)-actual) / max(np.linalg.norm(actual.astype(np.float64)), 1e-30))})
    return rows


def wall_null_localization(old_field, corrected_field, phase):
    fluid = phase == 0
    gram = np.zeros((int(fluid.sum()), 3, 3))
    for c in audit.legacy.stage13.DIRECTIONS_I64[1:]:
        neighbour = np.roll(fluid, tuple(int(x) for x in c[::-1]), axis=(0, 1, 2))[fluid]
        gram += neighbour[:, None, None] * np.outer(c, c)[None]
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    null = eigenvalues < 1e-8
    delta = (old_field.astype(np.float64) - corrected_field)[:, fluid].T
    coordinates = np.einsum("nij,ni->nj", eigenvectors, delta)
    total = float(np.sum(delta**2))
    return {"rank_deficient_fluid_fraction": float(np.mean(np.any(null, axis=1))),
            "squared_field_correction_in_local_nullspace_fraction": float(np.sum(coordinates**2 * null) / total),
            "definition": "Gram = sum c*c^T over links to fluid neighbours. Null directions cannot transmit their momentum through a fluid link at this voxel.",
            "limitation": "This supports a local geometric mechanism; it is not a global eigenmode proof or a physical pore-connectivity classification."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    probe, output = args.probe.resolve(), args.output.resolve()
    assert output.is_relative_to(ROOT / "stage113_evaluations") and not output.exists()
    completion = audit.read(probe / "completion.json")
    for rel, digest in completion["artifact_sha256"].items():
        assert audit.sha(probe / rel) == digest, rel
    manifest = audit.read(probe / "manifest.json")
    source = manifest["source"]
    record = audit.read(source["record"])
    for name in ["final_fields", "final_shifted_state", "audit"]:
        assert audit.sha(source[name]["path"]) == source[name]["sha256"]
    results = []
    field_list = []
    for name in ["archive_phase_average", "cold_first_step_average"]:
        data = audit.read(probe / name / "result.json")
        with np.load(probe / name / "final_shifted_state.npz") as f:
            state, phase = f["shifted_state"], f["phase"]
        with np.load(probe / name / "final_fields.npz") as f:
            field, density = f["velocity_xyz_lu"], f["density_lu"]
            assert np.array_equal(phase, f["phase"])
        independent_u, rho, body, force = independent_fields(state, phase, record["acceleration_lu"])
        rel = float(np.linalg.norm(independent_u-field)/np.linalg.norm(independent_u))
        force_residual = float(np.linalg.norm(np.array([body, 0, 0])-force)/abs(body))
        cpu = cpu_node_residuals(state, phase, record["acceleration_lu"])
        audit.legacy.install_generic_mask_oracle()
        case = {"dimensions_lu": list(phase.shape[::-1]), "_stage17_mask": phase,
                "expected_mask_sha256": audit.digest(phase),
                "boundary_mode": audit.legacy.stage13.BOUNDARY_TRIPLY_PERIODIC,
                "acceleration_realized_float32_lu": record["acceleration_lu"]}
        reconstructed = audit.legacy.stage13.copied_state_observables(state, phase, case, retain_velocity=True)
        exact = bool(np.array_equal(reconstructed["velocity_xyz_lu"], field) and np.array_equal(reconstructed["density_lu"], density))
        common_gate = gate.check_steady_flow([r for r in data["rows"] if r["step"] % 257 == 0],
                         data["rows"][-8:], export_exact=exact,
                         fatal_health_code=data["numerical_health"]["fatal_sticky_code"])
        checks = {"source_run_gates": bool(data["passed"] and all(data["checks"].values())),
                  "common_temporal_gate": common_gate["passed"],
                  "independent_field_reconstruction": rel < 2e-6,
                  "independent_steady_force_balance": force_residual < .005,
                  "independent_density_mean": bool(abs(rho[phase==0].mean()-1) < 5e-6),
                  "independent_cpu_fixed_point_spotcheck": max(x["fixed_point_relative_l2"] for x in cpu) < 5e-5}
        results.append({"name": name, "checks": checks, "passed": all(checks.values()),
                        "independent_field_relative_l2": rel, "steady_force_balance_relative": force_residual,
                        "density_mean_drift": float(rho[phase==0].mean()-1),
                        "density_reconstruction_max_difference": float(np.max(np.abs(rho-density))),
                        "cpu_spot_checks": cpu, "runtime_seconds": data["runtime_seconds"],
                        "temporal_gate": common_gate,
                        "last_adjacent_field_relative_l2": data["rows"][-1]["field_change_relative_l2"]})
        field_list.append(field)
    with np.load(source["final_fields"]["path"]) as f:
        old = f["velocity_xyz_lu"]
    null = wall_null_localization(old, field_list[0], phase)
    l2 = float(np.linalg.norm(field_list[0].astype(np.float64)-field_list[1]) / np.linalg.norm(field_list[1].astype(np.float64)))
    mean_shift = float(field_list[0][0].mean(dtype=np.float64)/field_list[1][0].mean(dtype=np.float64)-1)
    agreement = l2 < 2e-4 and abs(mean_shift) < 5e-5
    test_log = io.StringIO()
    test_result = unittest.TextTestRunner(stream=test_log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(gate_tests))
    assert test_result.wasSuccessful(), test_log.getvalue()
    output.mkdir(parents=True)
    result = {"schema": "matdem.stage113.independent-parity-evaluation.v1",
              "status": "seed2_reference_diagnostic_passed_remaining_fields_required" if all(x["passed"] for x in results) and agreement else "diagnostic_failed_preserved",
              "passed": all(x["passed"] for x in results) and agreement,
              "results": results, "local_nullspace_diagnostic": null,
              "independent_initialization_relative_l2": l2, "independent_initialization_mean_shift": mean_shift,
              "old_export_to_corrected_field_relative_l2": float(np.linalg.norm(old.astype(np.float64)-field_list[0]) / np.linalg.norm(field_list[0].astype(np.float64))),
              "old_export_to_corrected_mean_shift": float(field_list[0][0].mean(dtype=np.float64)/old[0].mean(dtype=np.float64)-1),
              "bindings": {"probe_completion_sha256": audit.sha(probe / "completion.json"),
                           "evaluator_sha256": audit.sha(__file__), "audit_module_sha256": audit.sha(audit.__file__),
                           "steady_gate_sha256": audit.sha(gate.__file__), "steady_gate_tests_sha256": audit.sha(gate_tests.__file__),
                           "literature_context_sha256": audit.sha(ROOT / "stage113_designs/parity_correction_reference_20260915.json")},
              "gate_regression": {"tests_run": test_result.testsRun, "passed": test_result.wasSuccessful(), "log": test_log.getvalue()},
              "authority": {"transport": False, "campaign": False},
              "claim_boundary": "One clean CPD2 reference-field diagnostic, not all-field requalification, permeability validation, or particle-release evidence."}
    json.dumps(result, allow_nan=False)  # Validate all types before opening output.
    audit.write(output / "results.json", result)
    print({k: v for k,v in result.items() if k not in ["results"]}, flush=True)


if __name__ == "__main__":
    main()
