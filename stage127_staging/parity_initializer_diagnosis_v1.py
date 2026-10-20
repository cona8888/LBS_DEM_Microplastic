"""Stage127: bounded CPD6 one-time parity-initializer diagnosis; no flow qualification or transport."""
from __future__ import annotations

import argparse
import gc
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage126_staging"))
import cpd6_relaxation_v2 as stage126_entry

base = stage126_entry.v1
STUDY = "cpd6_parity_initializer_diagnosis_20260916"
DESIGN = ROOT / "stage127_designs" / STUDY / "design_01.json"
RUN = ROOT / "stage127_runs" / STUDY / "gpu_diagnosis_01"
EVAL = ROOT / "stage127_evaluations" / STUDY
read, write, require, bind, sha = base.read, base.write, base.require, base.bind, base.sha


def verify(d):
    base.s114.verify_bindings(d["bindings"])
    require(d["controls"] == {"tau": 0.8, "nu_lu": 0.1, "threads": 256, "steps": 514}, "controls drift")
    require(d["initializer"] == "one arithmetic average of saved step 4096 and its unchanged-kernel step 4097 state", "initializer drift")
    require(d["authority"] == {"diagnostic_only": True, "full_flow_solution": False, "force_correction": False, "transport": False}, "authority drift")


def prepare():
    require(not DESIGN.parent.exists(), "immutable design exists")
    seal = ROOT / "stage126_evaluations/cpd6_bounded_relaxation_attempt02_20260916/completion.json"
    sealed = read(seal)
    require(sealed["status"] == "bounded_relaxation_verified_stationarity_and_mean_gates_failed", "Stage126 seal absent")
    for path, expected in sealed["artifacts"].items():
        require(sha(path) == expected, "Stage126 drift " + path)
    state = ROOT / "stage126_runs/cpd6_bounded_relaxation_attempt02_20260916/gpu_relaxation_01/stage126_s2_f1p0_cpd6_bounded/final_shifted_state.npz"
    geometry = ROOT / "stage125_designs/third_grid_cost_20260916/geometry_cpd6.npz"
    d126 = read(ROOT / "stage126_designs/cpd6_bounded_relaxation_attempt02_20260916/design_01.json")
    design = {
        "schema": "matdem.stage127.cpd6-parity-initializer-diagnosis.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "question": "Does the already-qualified one-time consecutive-population average remove the persistent CPD6 one-step odd/even mode without changing geometry, force, collision law or boundaries?",
        "claim_boundary": "Initializer-mechanism diagnosis only; not a full flow solution, force correction, spatial-convergence result, permeability validation or transport field.",
        "bindings": {
            "stage126_seal": bind(seal),
            "stage126_design": bind(ROOT / "stage126_designs/cpd6_bounded_relaxation_attempt02_20260916/design_01.json"),
            "stage126_result": bind(ROOT / "stage126_runs/cpd6_bounded_relaxation_attempt02_20260916/gpu_relaxation_01/stage126_s2_f1p0_cpd6_bounded/result.json"),
            "source_state": bind(state),
            "geometry": bind(geometry),
            "runner": bind(__file__),
            "probe": bind(base.s114.probe.__file__),
            "cuda_source": d126["bindings"]["cuda_source"],
        },
        "qualified_ptx_sha256": d126["qualified_ptx_sha256"],
        "forcing": d126["forcing"],
        "initializer": "one arithmetic average of saved step 4096 and its unchanged-kernel step 4097 state",
        "controls": {"tau": 0.8, "nu_lu": 0.1, "threads": 256, "steps": 514},
        "diagnostic_gates": {
            "final_adjacent_field_change_relative_l2_max": 5e-5,
            "final_two_step_field_change_relative_l2_max": 5e-5,
            "final_adjacent_mean_change_relative_max": 5e-5,
            "fatal_health_code": 0,
            "density_drift_max": 5e-6,
            "mach_max": 0.05,
            "runtime_seconds_max": 300,
        },
        "decision": {
            "pass": "Initializer mechanism may proceed to a separately frozen longer convergence/mean-correction design; this result itself is not a qualified field.",
            "fail": "Preserve and stop; do not extend, force-correct, solve fully or run transport.",
        },
        "authority": {"diagnostic_only": True, "full_flow_solution": False, "force_correction": False, "transport": False},
    }
    verify(design)
    DESIGN.parent.mkdir(parents=True)
    write(DESIGN, design)
    print(json.dumps({"design": str(DESIGN), "sha256": sha(DESIGN), "predicted_seconds": 514 * 0.29911353898048354}), flush=True)


def preflight():
    d = read(DESIGN)
    verify(d)
    with np.load(d["bindings"]["source_state"]["path"]) as saved, np.load(d["bindings"]["geometry"]["path"]) as geom:
        state, phase = saved["shifted_state"], saved["phase"]
        checks = {
            "shape": state.shape == (19, 279, 279, 279),
            "phase_shape": phase.shape == (279, 279, 279),
            "saved_phase_matches_geometry": np.array_equal(phase, geom["phase"]),
            "finite": np.isfinite(state).all(),
            "solids_zero": all(not np.any(state[q][phase != 0]) for q in range(19)),
            "no_broadened_authority": not any(d["authority"][x] for x in ["full_flow_solution", "force_correction", "transport"]),
        }
        source_digest = base.s114.audit.digest(state)
    out = EVAL / "preflight_01"
    out.mkdir(parents=True, exist_ok=False)
    result = {"passed": bool(all(checks.values())), "checks": {k: bool(v) for k, v in checks.items()}, "source_state_array_sha256": source_digest, "design": bind(DESIGN)}
    write(out / "results.json", result)
    write(out / "completion.json", {"passed": result["passed"], "results_sha256": sha(out / "results.json")})
    require(result["passed"], "preflight failed")
    print(result, flush=True)


def run():
    d = read(DESIGN)
    verify(d)
    p = read(EVAL / "preflight_01/results.json")
    require(p["passed"], "preflight absent")
    require(not RUN.exists(), "immutable run exists")
    RUN.mkdir(parents=True)
    write(RUN / "manifest.json", {"design": bind(DESIGN), "preflight": bind(EVAL / "preflight_01/results.json"), "created_utc": datetime.now(timezone.utc).isoformat()})
    driver = None
    try:
        with np.load(d["bindings"]["source_state"]["path"]) as saved:
            state, phase = saved["shifted_state"], saved["phase"]
        require(base.s114.audit.digest(state) == p["source_state_array_sha256"], "source state drift")
        base.s114.audit.legacy.install_generic_mask_oracle()
        adapter = {"lineage": {"cuda_source": d["bindings"]["cuda_source"]["path"], "qualified_ptx_sha256": d["qualified_ptx_sha256"]}}
        driver, build = base.s114.audit.legacy.create_driver(adapter, Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin"), 0)
        case = base.s114.probe.case_for(phase, d["forcing"]["acceleration_lu"], "stage127_cpd6_parity_average")
        next_state = base.s114.probe.one_step(driver, state, phase, case)
        initial = base.s114.probe.average_states(state, next_state)
        initializer = {
            "source_state_array_sha256": base.s114.audit.digest(state),
            "next_state_array_sha256": base.s114.audit.digest(next_state),
            "averaged_state_array_sha256": base.s114.audit.digest(initial),
        }
        del state, next_state
        gc.collect()
        result, _, _ = base.s114.probe.relax(driver, initial, phase, case, RUN, "stage127_cpd6_parity_average", d["controls"]["steps"])
        write(RUN / "completion.json", {
            "status": "diagnostic_complete_pending_independent_evaluation",
            "design": bind(DESIGN),
            "record": bind(RUN / "stage127_cpd6_parity_average/result.json"),
            "field": bind(RUN / "stage127_cpd6_parity_average/final_fields.npz"),
            "state": bind(RUN / "stage127_cpd6_parity_average/final_shifted_state.npz"),
            "initializer": initializer,
            "build": build,
            "full_flow_solution": False,
            "force_correction_authorized": False,
            "transport_authorized": False,
        })
        print("DIAGNOSTIC COMPLETE", result["runtime_seconds"], flush=True)
    except Exception as exc:
        write(RUN / "failure.json", {"error": repr(exc), "traceback": traceback.format_exc(), "automatic_retry": False})
        raise
    finally:
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "preflight", "run"])
    args = parser.parse_args()
    {"prepare": prepare, "preflight": preflight, "run": run}[args.mode]()
