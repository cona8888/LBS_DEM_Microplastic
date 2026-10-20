"""Bounded adjacent-step audit of immutable flow states; no particle transport.

Tests whether even-interval convergence masked an odd/even state difference.
The original solver and all input evidence remain untouched. Four transitions
from each saved state are diagnostic replays, not extensions of accepted runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration\scripts")
sys.path.insert(0, str(EXTERNAL))
import stage17_relaxed_fibre_gpu_lbm_run as legacy


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def independent_momentum(state, phase):
    """Direct binary64 sums, independently of the legacy reduction helpers."""
    stored_p = np.zeros(3)
    incoming_p = np.zeros(3)
    fluid = phase == 0
    for q, direction in enumerate(legacy.stage13.DIRECTIONS_I64):
        if not np.any(direction):
            continue
        shift = tuple(int(x) for x in direction[::-1])
        source = np.roll(state[q], shift, axis=(0, 1, 2))
        source_solid = np.roll(phase, shift, axis=(0, 1, 2)) != 0
        pulled = np.where(source_solid, state[int(legacy.stage13.OPPOSITE[q])], source)
        stored_p += direction * np.sum(state[q][fluid], dtype=np.float64)
        incoming_p += direction * np.sum(pulled[fluid], dtype=np.float64)
    return stored_p, incoming_p


def collect_sources():
    paths = []
    for relative in [
        "stage111_runs/seed2_clean_physical_re_flow_validation_20260915/gpu_validation_01",
        "stage112_runs/reference_flow_resolution_packing_20260915/gpu_verification_01",
    ]:
        base = ROOT / relative
        assert not (base / "failure.json").exists()
        paths.extend(sorted(base.glob("*/record.json")))
    assert len(paths) == 6
    paths += [
        ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01/stage31e_s31b_n216_s2_clean_cpd2/record.json",
        ROOT / "stage31_runs/stage31f_selected_replicated_cpd4_20260827/gpu_confirmation_01/stage31f_s31b_n216_s2_clean_cpd4/record.json",
    ]
    sources = []
    for path in paths:
        record = read(path)
        item = {"case_id": record["case_id"], "record": str(path), "record_sha256": sha(path)}
        for name in ["final_fields", "final_shifted_state", "audit"]:
            artifact = path.with_name(name + ".npz")
            assert sha(artifact) == record["artifacts"][name + "_npz_sha256"]
            item[name] = {"path": str(artifact), "sha256": sha(artifact)}
        sources.append(item)
    return sources


def replay(driver, source, controls, output):
    record = read(source["record"])
    with np.load(source["final_shifted_state"]["path"]) as archive:
        phase = archive["phase"]
        state = archive["shifted_state"]
    nx, ny, nz = record["dimensions_lu"]
    assert phase.shape == (nz, ny, nx) and state.shape == (19, nz, ny, nx)
    case = {
        "case_id": record["case_id"], "dimensions_lu": [nx, ny, nz],
        "center_offset_lu": [0., 0., 0.],
        "boundary_mode": legacy.stage13.BOUNDARY_TRIPLY_PERIODIC,
        "acceleration_realized_float32_lu": float(np.float32(record["acceleration_lu"])),
        "_stage17_mask": phase, "expected_mask_sha256": hashlib.sha256(phase.tobytes()).hexdigest(),
    }
    signature_before = digest(state)
    initial_obs = legacy.stage13.copied_state_observables(state, phase, case, retain_velocity=True)
    with np.load(source["final_fields"]["path"]) as fields:
        export_exact = (np.array_equal(fields["phase"], phase)
                        and np.array_equal(fields["velocity_xyz_lu"], initial_obs["velocity_xyz_lu"])
                        and np.array_equal(fields["density_lu"], initial_obs["density_lu"]))
    assert signature_before == digest(state), "observable reconstruction mutated state"
    stored, pulled = independent_momentum(state, phase)
    previous = state
    previous_u = initial_obs["velocity_xyz_lu"]
    two_back_u = None
    rows = [{"offset": 0, "u_superficial": initial_obs["superficial_velocity_lu"],
             "stored_p": stored.tolist(), "pulled_p": pulled.tolist()}]
    session = legacy.stage13.CudaCandidateSession(driver, state, phase, case,
        tau=controls["tau"], threads=controls["threads_per_block"], maximum_steps=4)
    start = time.perf_counter()
    try:
        for step in range(1, 5):
            body = initial_obs["body_force_drag_lu"]
            force = stored - pulled
            session.step(step)
            current = session.copy_current()
            obs = legacy.stage13.copied_state_observables(current, phase, case, retain_velocity=True)
            new_stored, new_pulled = independent_momentum(current, phase)
            delta_p = new_stored - stored
            field = obs["velocity_xyz_lu"]
            denom = np.linalg.norm(previous_u.astype(np.float64))
            row = {"offset": step, "u_superficial": obs["superficial_velocity_lu"],
                   "mean_density": obs["mean_density"], "body_x": body,
                   "solid_force": force.tolist(), "stored_p": new_stored.tolist(),
                   "pulled_p": new_pulled.tolist(), "delta_stored_p": delta_p.tolist(),
                   "steady_imbalance_relative": float(np.linalg.norm(np.array([body, 0, 0]) - force) / abs(body)),
                   "dynamic_residual_relative": float(np.linalg.norm(np.array([body, 0, 0]) - force - delta_p) / abs(body)),
                   "u_adjacent_relative": obs["superficial_velocity_lu"] / initial_obs["superficial_velocity_lu"] - 1,
                   "field_adjacent_relative_l2": float(np.linalg.norm(field.astype(np.float64) - previous_u) / denom),
                   "field_two_step_relative_l2": (None if two_back_u is None else float(np.linalg.norm(field.astype(np.float64) - two_back_u) / denom)),
                   "state_exact_unchanged": bool(np.array_equal(current, previous)),
                   "health": legacy.stage13.split_numerical_health_code(session.health_code(), "candidate")}
            rows.append(row)
            two_back_u, previous_u = previous_u, field
            previous, stored, pulled, initial_obs = current, new_stored, new_pulled, obs
    finally:
        session.close()
    result = {"case_id": record["case_id"], "source": source, "rows": rows,
              "export_exact_reconstruction": bool(export_exact),
              "record_vs_saved_field_relative": rows[0]["u_superficial"] / record["final"]["superficial_velocity_lu"] - 1,
              "elapsed_seconds": time.perf_counter() - start,
              "checks": {"export_exact_reconstruction": bool(export_exact),
                         "adjacent_mean_steady": all(abs(x["u_adjacent_relative"]) <= 5e-5 for x in rows[1:]),
                         "steady_force_balance": all(x["steady_imbalance_relative"] <= .005 for x in rows[1:]),
                         "dynamic_momentum_balance": all(x["dynamic_residual_relative"] <= .005 for x in rows[1:]),
                         "fatal_health_zero": all(x["health"]["fatal_sticky_code"] == 0 for x in rows[1:])}}
    write(output / (record["case_id"] + ".json"), result)
    print(json.dumps({"case": record["case_id"], "checks": result["checks"],
                      "u_sequence": [x["u_superficial"] for x in rows],
                      "field_adjacent_l2": rows[1]["field_adjacent_relative_l2"],
                      "field_two_step_l2": rows[2]["field_two_step_relative_l2"]}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / "stage113_evaluations")
    if output.exists():
        raise FileExistsError(output)
    design_path = ROOT / "stage112_designs/reference_flow_resolution_packing_20260915/design_01/resolved_design.json"
    design = read(design_path)
    for item in design["lineage"].values():
        if isinstance(item, dict) and "path" in item:
            assert sha(item["path"]) == item["sha256"], item["path"]
    sources = collect_sources()
    output.mkdir(parents=True)
    manifest = {"schema": "matdem.stage113.temporal-flow-audit.v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "runner_sha256": sha(__file__), "sources": sources,
                "design_sha256": sha(design_path), "lineage": design["lineage"],
                "question": "Do four consecutive transitions of frozen states support steady-field reuse?",
                "controls": design["solver"], "steps_per_source": 4,
                "acceptance": {"adjacent_mean_relative": 5e-5, "steady_force_balance_relative": .005,
                               "dynamic_momentum_balance_relative": .005},
                "authority": {"diagnostic_replay_only": True, "transport": False, "campaign": False}}
    write(output / "manifest.json", manifest)
    adapter = {"lineage": {"cuda_source": design["lineage"]["cuda_source"]["path"],
                           "qualified_ptx_sha256": design["lineage"]["qualified_ptx_sha256"]}}
    legacy.install_generic_mask_oracle()
    driver, build = legacy.create_driver(adapter, Path(design["execution"]["cuda_bin"]), 0)
    try:
        results = [replay(driver, item, design["solver"], output) for item in sources]
    finally:
        driver.close()
    unchanged = all(sha(s["record"]) == s["record_sha256"] and
                    all(sha(s[n]["path"]) == s[n]["sha256"] for n in ["final_fields", "final_shifted_state", "audit"])
                    for s in sources)
    completion = {"status": "audit_complete", "steady_reuse_passed": all(all(x["checks"].values()) for x in results),
                  "inputs_unchanged": unchanged, "build": build,
                  "result_sha256": {r["case_id"]: sha(output / (r["case_id"] + ".json")) for r in results},
                  "manifest_sha256": sha(output / "manifest.json"), "particle_transport": False}
    write(output / "completion.json", completion)
    print(json.dumps(completion), flush=True)


if __name__ == "__main__":
    main()
