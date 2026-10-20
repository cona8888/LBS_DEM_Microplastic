"""CPU-side verification and physical/spatial comparisons of corrected fields."""
from __future__ import annotations

import argparse
import gc
import traceback
from pathlib import Path

import numpy as np

import requalify_stationary_flows_v1 as runmod
import evaluate_parity_correction_v2 as cpu

audit, probe, gate = runmod.audit, runmod.probe, runmod.gate
ROOT, DESIGN = runmod.ROOT, runmod.DESIGN
read, write, require = audit.read, runmod.write, runmod.require


def profile(reference, direct, fluid):
    m0 = float(reference[0, fluid].mean(dtype=np.float64))
    m1 = float(direct[0, fluid].mean(dtype=np.float64))
    require(m0 > 0 and m1 > 0, "nonpositive profile flow")
    v0, v1 = reference[:, fluid].astype(np.float64) / m0, direct[:, fluid].astype(np.float64) / m1
    delta = np.linalg.norm(v1 - v0, axis=0)
    rms = float(np.sqrt(np.mean(delta**2) / np.mean(np.sum(v1**2, axis=0))))
    return {"normalized_vector_rms_relative": rms, "normalized_vector_p95": float(np.quantile(delta, .95)),
            "normalized_vector_maximum": float(delta.max())}


def evaluate_case(spec, path, design, reused=False):
    data = read(path / "result.json")
    require(audit.sha(path / "final_fields.npz") == data["field_sha256"], "field hash mismatch")
    require(audit.sha(path / "final_shifted_state.npz") == data["state_sha256"], "state hash mismatch")
    if not reused:
        record = read(path / "record.json")
        require(record["design_sha256"] == audit.sha(DESIGN), "record design mismatch")
        require(record["case_id"] == spec["case_id"] and record["acceleration_lu"] == spec["acceleration_lu"], "record identity mismatch")
        require(record["initializer"]["averaged_state_array_sha256"] == data["initial_state_sha256"], "initializer mismatch")
        runmod.verify_bindings(record)
    with np.load(path / "final_shifted_state.npz") as saved, np.load(path / "final_fields.npz") as exported, np.load(spec["geometry"]["path"]) as geom:
        phase, state = saved["phase"], saved["shifted_state"]
        field, density = exported["velocity_xyz_lu"], exported["density_lu"]
        require(np.array_equal(phase, exported["phase"]) and np.array_equal(phase, geom["phase"]), "geometry phase changed")
        dx, diameter = float(geom["spacing_m"][0]), float(np.median(2 * geom["sand_radii_m"]))
    fluid = phase == 0
    accel = spec["acceleration_lu"]
    case = probe.case_for(phase, accel, spec["case_id"])
    native = probe.observe(state, phase, case)
    exact = bool(np.array_equal(native["velocity_xyz_lu"], field) and np.array_equal(native["density_lu"], density))
    health = data["numerical_health"]
    temporal = gate.check_steady_flow([x for x in data["rows"] if x["step"] % 257 == 0], data["rows"][-8:],
                                   export_exact=exact, fatal_health_code=health["fatal_sticky_code"])
    independent_u, rho, body, wall_force = cpu.independent_fields(state, phase, accel)
    reconstruction_l2 = float(np.linalg.norm(independent_u - field) / np.linalg.norm(independent_u))
    force_residual = float(np.linalg.norm(np.array([body, 0, 0]) - wall_force) / abs(body))
    nodes = cpu.cpu_node_residuals(state, phase, accel)
    threshold = design["thresholds"]
    checks = {"source_gates": bool(data["passed"] and all(data["checks"].values())),
              "common_temporal_gate": temporal["passed"], "exact_export": exact,
              "full_health_zero": type(health["full_sticky_code"]) is int and health["full_sticky_code"] == 0,
              "independent_field_reconstruction": reconstruction_l2 <= threshold["independent_field_relative_l2_max"],
              "independent_steady_force_balance": force_residual <= threshold["steady_balance_relative_max"],
              "independent_mean_density": bool(abs(rho[fluid].mean() - 1) <= 5e-6),
              "cpu_fixed_point_spotcheck": max(n["fixed_point_relative_l2"] for n in nodes) <= threshold["cpu_node_relative_l2_max"],
              "finite_fields_and_state": bool(np.isfinite(field).all() and np.isfinite(state).all() and np.isfinite(density).all())}
    mean_lu = float(independent_u[0, fluid].mean())
    nu_si = design["physical_fluid"]["dynamic_viscosity_Pa_s"] / design["physical_fluid"]["density_kg_m3"]
    unit_speed = nu_si / (design["controls"]["nu_lu"] * dx)
    mean_si = mean_lu * unit_speed
    target = spec["target_mean_interstitial_velocity_m_s"]
    target_error = abs(mean_si / target - 1) if target is not None else None
    checks["positive_mean_flow"] = mean_si > 0
    checks["physical_target_mean"] = target is None or target_error <= threshold["target_mean_relative_error_max"]
    with np.load(spec["source"]["final_fields"]["path"]) as old:
        old_field = old["velocity_xyz_lu"]
        correction_l2 = float(np.linalg.norm(field.astype(np.float64) - old_field) / np.linalg.norm(field.astype(np.float64)))
        correction_mean = float(field[0, fluid].mean(dtype=np.float64) / old_field[0, fluid].mean(dtype=np.float64) - 1)
    result = {"case_id": spec["case_id"], "packing_seed": spec["packing_seed"], "cpd": spec["cpd"],
              "flow_factor": spec["flow_factor"], "reused_from_stage113": reused, "checks": checks, "passed": all(checks.values()),
              "temporal_gate": temporal, "reconstruction_relative_l2": reconstruction_l2,
              "steady_force_balance_relative": force_residual, "independent_cpu_node_checks": nodes,
              "mean_density_drift": float(rho[fluid].mean() - 1), "mean_interstitial_velocity_lu": mean_lu,
              "spacing_m": dx, "lattice_velocity_unit_m_s": unit_speed, "mean_interstitial_velocity_m_s": mean_si,
              "superficial_velocity_m_s": mean_si * float(fluid.mean()), "porosity_voxel": float(fluid.mean()),
              "target_mean_relative_error": target_error, "median_grain_Re": mean_si * diameter / nu_si,
              "dimensionless_mobility": mean_lu * float(fluid.mean()) * .1 / (accel * spec["cpd"]**2),
              "maximum_mach": float(native["maximum_speed_lu"] * np.sqrt(3)),
              "last_adjacent_field_relative_l2": data["rows"][-1]["field_change_relative_l2"],
              "correction_field_relative_l2": correction_l2, "correction_mean_relative_shift": correction_mean,
              "relaxation_runtime_seconds": data["runtime_seconds"],
              "bundle": {name: runmod.bind(path / name) for name in ["result.json", "final_fields.npz", "final_shifted_state.npz"]}}
    print(spec["case_id"], "independent passed", result["passed"], "target error", target_error, flush=True)
    return result, field, fluid


def main(run, output):
    require(output.is_relative_to(ROOT / "stage114_evaluations") and not output.exists(), "fresh evaluation output required")
    design = read(DESIGN)
    runmod.verify_design(design)
    completion = read(run / "completion.json")
    require(not list(run.rglob("failure.json")), "failure marker present")
    require(completion["passed"] is True and completion["status"] == "complete_pending_independent_evaluation", "incomplete run")
    require(completion["design_sha256"] == audit.sha(DESIGN) and completion["manifest_sha256"] == audit.sha(run / "manifest.json"), "completion binding mismatch")
    require(completion["frozen_order"] == [s["case_id"] for s in design["cases"]], "case order mismatch")
    require(set(completion["record_sha256"]) == {s["case_id"] for s in design["cases"]}, "case set mismatch")
    require({p.name for p in run.iterdir() if p.is_dir()} == set(completion["record_sha256"]), "unexpected run subdirectory")
    for name, digest in completion["record_sha256"].items():
        require(audit.sha(run / name / "record.json") == digest, "record hash mismatch")
    audit.legacy.install_generic_mask_oracle()
    results, fields, masks = {}, {}, {}
    specs = design["cases"] + [design["reused_reference"]]
    for spec in specs:
        reused = spec is design["reused_reference"]
        path = Path(spec["corrected_bundle"]["result.json"]["path"]).parent if reused else run / spec["case_id"]
        result, field, fluid = evaluate_case(spec, path, design, reused)
        name = spec["case_id"]
        results[name], fields[name], masks[name] = result, field, fluid
        gc.collect()

    seed2_names = ["s2_f0p5_cpd2", "s2_f1p0_cpd2", "s2_f2p0_cpd2"]
    profiles = []
    for name in seed2_names:
        require(np.array_equal(masks[name], masks["s2_archive_low_re_cpd2"]), "archive/direct fluid mismatch")
        row = profile(fields["s2_archive_low_re_cpd2"], fields[name], masks[name])
        row.update({"case_id": name, "passed": row["normalized_vector_rms_relative"] <= design["thresholds"]["profile_rms_max"]
                    and row["normalized_vector_p95"] <= design["thresholds"]["profile_p95_max"]})
        profiles.append(row)
    pairwise = [{"lower": a, "upper": b, **profile(fields[a], fields[b], masks[a])} for a,b in zip(seed2_names, seed2_names[1:])]
    means = [results[n]["mean_interstitial_velocity_m_s"] for n in seed2_names]
    flow_order = all(a < b for a,b in zip(means, means[1:]))
    m2, m4 = results["s2_f1p0_cpd2"]["dimensionless_mobility"], results["s2_f1p0_cpd4"]["dimensionless_mobility"]
    geom2 = design["reused_reference"]["geometry"]["path"]
    geom4 = next(s["geometry"]["path"] for s in specs if s["cpd"] == 4)
    with np.load(geom2) as g2, np.load(geom4) as g4:
        require(np.array_equal(g2["sand_centres_m"], g4["sand_centres_m"]) and np.array_equal(g2["sand_radii_m"], g4["sand_radii_m"]), "spatial grains differ")
        require(np.allclose(g2["spacing_m"], 2 * g4["spacing_m"], rtol=1e-14, atol=0), "spatial spacing differs")
    f2, f4 = masks["s2_f1p0_cpd2"], masks["s2_f1p0_cpd4"]
    require(f4.shape == tuple(2 * n for n in f2.shape), "nonmatching 2x resolution")
    nz, ny, nx = f2.shape
    full4 = f4.reshape(nz,2,ny,2,nx,2).all(axis=(1,3,5))
    common = f2 & full4
    u2, u4 = fields["s2_f1p0_cpd2"].astype(np.float64), fields["s2_f1p0_cpd4"].astype(np.float64)
    u2 /= u2[0, f2].mean()
    u4 /= u4[0, f4].mean()
    block4 = u4.reshape(3,nz,2,ny,2,nx,2).mean(axis=(2,4,6))
    delta = np.linalg.norm(u2[:,common] - block4[:,common], axis=0)
    shift = float(m4 / m2 - 1)
    spatial = {"common_fully_fluid_cells": int(common.sum()), "common_fraction_of_cpd2_fluid": float(common.sum()/f2.sum()),
               "normalized_vector_rms_relative": float(np.sqrt(np.mean(delta**2)/np.mean(np.sum(block4[:,common]**2,axis=0)))),
               "normalized_vector_p95": float(np.quantile(delta, .95)), "signed_mobility_relative_shift": shift,
               "gross_mobility_passed": abs(shift) <= design["thresholds"]["gross_mobility_relative_shift_max"],
               "limitation": "Excludes mixed wall blocks. A field RMS is not a trajectory/release-error bound; matched near-wall response and transport tests remain required."}
    mobility = [results[f"s{i}_f1p0_cpd2"]["dimensionless_mobility"] for i in [1,2,3]]
    packing = {"seed_order": [1,2,3], "dimensionless_mobility": mobility, "sample_CV": float(np.std(mobility,ddof=1)/np.mean(mobility)),
               "range_over_mean": float(np.ptp(mobility)/np.mean(mobility)), "population_generalization": False}
    runmod.verify_design(design)
    passed = all(x["passed"] for x in results.values()) and flow_order and spatial["gross_mobility_passed"]
    data = {"schema": "matdem.stage114.stationary-field-independent-evaluation.v1", "passed": passed,
            "status": "stationary_fields_requalified_transport_resolution_required" if passed else "requalification_failed_preserved",
            "cases": list(results.values()), "corrected_archive_to_direct_profiles": profiles, "direct_pairwise_profiles": pairwise,
            "flow_ordering_passed": flow_order, "spatial_resolution": spatial, "packing_variability": packing,
            "decision": {"corrected_archive_profile_test_passed_seed2_only": all(x["passed"] for x in profiles),
                         "direct_fields_preferred_for_next_test": True, "particle_transport_authorized": False,
                         "population_campaign_authorized": False, "absolute_permeability_validated": False},
            "claim_boundary": design["claim_boundary"], "all_lineage_hashes_verified_before_and_after": True,
            "bindings": {"design": runmod.bind(DESIGN), "run_completion": runmod.bind(run / "completion.json"), "evaluator": runmod.bind(__file__)}}
    output.mkdir(parents=True)
    write(output / "results.json", data)
    write(output / "completion.json", {"passed": passed, "status": data["status"], "results_sha256": audit.sha(output / "results.json")})
    print(data["status"], "spatial", spatial, "packing", packing, flush=True)
    return 0 if passed else 4


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(main(args.run.resolve(), args.output.resolve()))
