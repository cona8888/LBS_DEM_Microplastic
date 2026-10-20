"""Frozen-system and local trajectory verification for the compiled PGS seed."""
import json
import sys
import time
from pathlib import Path

import numpy as np
import numba
import llvmlite

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage89_staging"), str(ROOT / "stage90_staging"),
                str(ROOT / "stage74_staging")]
import verify_short_seed_local_v1 as harness
import trajectory_native_pgs_v1 as candidate
import scalar_contact_kernels_v1 as kernels

OUT = ROOT / "stage90_evaluations/native_local_01"
PROFILE = ROOT / "stage88_evaluations/near_outlet_contact_profile_01/results.json"


def main():
    profile = json.loads(PROFILE.read_text())
    completion = json.loads((PROFILE.parent / "completion.json").read_text())
    if completion["results_sha256"] != harness.sha(PROFILE):
        raise RuntimeError("profile hash drift")
    OUT.mkdir(parents=True, exist_ok=False)
    protocol = {"horizon_s": .01, "component_tolerance": 1e-9,
                "wall_budget_s_per_arm": 30., "fastmath": False,
                "original_pgs_sweeps_retained": True,
                "claim_boundary": "Local numerical restart and frozen-system verification only."}
    harness.dump(OUT / "protocol.json", protocol)
    gate = candidate.gate
    original = gate._project, gate._residual
    gate._project, gate._residual = kernels.project, kernels.residual
    rows = []
    try:
        for item in profile["top_systems"]:
            if harness.sha(item["path"]) != item["sha256"]:
                raise RuntimeError("captured system drift")
            with np.load(item["path"]) as data:
                args = [data[k].copy() for k in ("vfree", "mobility", "jacobian", "gaps")]
                args += [float(data["dt"]), float(data["friction"]),
                         float(data["tol"]), int(data["maxiter"])]
            # Compile/load JIT outside the timed comparison.
            candidate.solve(*args)
            start = time.perf_counter()
            old = candidate._original(*args)
            elapsed_old = time.perf_counter()-start
            start = time.perf_counter()
            new = candidate.solve(*args)
            elapsed_new = time.perf_counter()-start
            rows.append({"system": item["path"],
                         "baseline_runtime_s": elapsed_old, "candidate_runtime_s": elapsed_new,
                         "max_velocity_difference": float(np.max(np.abs(old[0]-new[0]))),
                         "max_reaction_difference": float(np.max(np.abs(
                             np.asarray(old[1]["reactions"])-np.asarray(new[1]["reactions"])))),
                         "baseline_iterations": old[1]["iterations"],
                         "candidate_iterations": new[1]["iterations"],
                         "candidate_residual": new[1]["residual"]})
    finally:
        gate._project, gate._residual = original
    harness.dump(OUT / "frozen_systems.json", rows)
    cfg = json.loads(harness.DESIGN.read_text())
    previous = json.loads(harness.CASE.read_text())["result"]
    old = harness.run_local(harness.baseline, cfg, previous, 2, .01, 30.)
    harness.dump(OUT / "baseline.json", old)
    new = harness.run_local(candidate, cfg, previous, 2, .01, 30.)
    harness.dump(OUT / "candidate.json", new)
    checks, differences = harness.compare(old, new, .01)
    checks["candidate_exercised"] = new["native_pgs_stats"]["native_calls"] > 0
    record = {"passed": all(checks.values()), "checks": checks, "differences": differences,
              "baseline_runtime_s": old["runtime_seconds"],
              "candidate_runtime_s": new["runtime_seconds"],
              "native_stats": new["native_pgs_stats"],
              "environment": {"numba": numba.__version__, "llvmlite": llvmlite.__version__,
                              "numpy": np.__version__, "python": sys.version},
              "input_hashes": {str(p): harness.sha(p) for p in (harness.DESIGN, harness.CASE, PROFILE)},
              "source_hashes": {str(p): harness.sha(p) for p in (Path(__file__), Path(candidate.__file__),
                                Path(harness.__file__), Path(candidate.gate.__file__), Path(kernels.__file__))},
              "artifact_hashes": {str(OUT / name): harness.sha(OUT / name) for name in (
                  "protocol.json", "frozen_systems.json", "baseline.json", "candidate.json")}}
    harness.dump(OUT / "results.json", record)
    harness.dump(OUT / "completion.json", {
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": harness.sha(OUT / "results.json")})
    print(json.dumps({key: record[key] for key in ("passed", "checks", "differences",
                                                  "baseline_runtime_s", "candidate_runtime_s", "native_stats")}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
