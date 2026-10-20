"""Classify adaptive-step rejections without changing the Stage68 controller.

Instrument the original-start seed-2 trajectory for a short wall budget. The
same Stage70 contact solver, geometry, and acceptance logic remain active.
This is a diagnostic; a budget-censored result cannot imply trapping/release.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage70_staging")]
import verify_short_fibre_crossing_v1 as source
import trajectory_extended_recovery_v1 as trajectory
import inertial_contact_runtime_portfolio_v1 as contact


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ContactProbe:
    def __init__(self, module):
        self.module = module
        self.calls = 0
        self.failures = {}
        self.elapsed_s = 0.
    def __getattr__(self, name):
        return getattr(self.module, name)
    def inertial_contact_step(self, *args, **kwargs):
        self.calls += 1
        started = time.perf_counter()
        try:
            return self.module.inertial_contact_step(*args, **kwargs)
        except RuntimeError as exc:
            key = str(exc)
            self.failures[key] = self.failures.get(key, 0) + 1
            raise
        finally:
            self.elapsed_s += time.perf_counter() - started


def main():
    out = ROOT / "stage75_evaluations" / "s2_rejection_diagnostic_01"
    out.mkdir(parents=True, exist_ok=False)
    old_path = ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" / "pilot_01" / "s2_prolate_ar4.json"
    old = json.loads(old_path.read_text())["result"]
    design_path = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
    design = json.loads(design_path.read_text())
    b = design["prolate_semiaxes_m"][1]
    threshold = -1e-5 * b
    original_inertial = trajectory.inertial
    original_sweep = trajectory.geometry_tools.swept_gap
    probe = ContactProbe(contact)
    sweeps = {"calls": 0, "clearance_rejects": 0, "elapsed_s": 0.}

    def measured_sweep(*args, **kwargs):
        sweeps["calls"] += 1
        started = time.perf_counter()
        try:
            gap = original_sweep(*args, **kwargs)
        finally:
            sweeps["elapsed_s"] += time.perf_counter() - started
        if gap < threshold:
            sweeps["clearance_rejects"] += 1
        return gap

    source.trajectory = trajectory
    trajectory.inertial = probe
    trajectory.geometry_tools.swept_gap = measured_sweep
    contact.set_recovery_mode(False)
    try:
        result, _ = source.run(2, "prolate_ar4", old["time_s"] + .05, 30.)
    finally:
        contact.set_recovery_mode(False)
        trajectory.inertial = original_inertial
        trajectory.geometry_tools.swept_gap = original_sweep
    runtime_failures = sum(probe.failures.values())
    displacement_rejects = probe.calls - runtime_failures - sweeps["calls"]
    classified = runtime_failures + displacement_rejects + sweeps["clearance_rejects"]
    checks = {
        "nonnegative_displacement_count": displacement_rejects >= 0,
        "rejection_accounting": classified == result["rejected"],
        "sweep_acceptance_accounting": sweeps["calls"] - sweeps["clearance_rejects"] == result["steps"],
        "preterminal_clearance": result["minimum_gap_m"] is None or result["minimum_gap_m"] >= -5e-10,
        "preterminal_contact": result["max_contact_residual"] <= 1e-8,
        "preterminal_force": result["max_force_residual"] <= 1e-8,
        "preterminal_momentum": result["max_momentum_residual"] <= 1e-8,
        "reynolds_envelope": result["max_reynolds"] <= 3,
    }
    checks = {key: bool(value) for key, value in checks.items()}
    record = {
        "passed": all(checks.values()), "checks": checks,
        "wall_budget_s": 30., "result": result,
        "inertial_calls": probe.calls, "inertial_elapsed_s": probe.elapsed_s,
        "runtime_failures": probe.failures,
        "displacement_rejects": displacement_rejects,
        "swept_clearance_rejects": sweeps["clearance_rejects"],
        "swept_calls": sweeps["calls"], "swept_elapsed_s": sweeps["elapsed_s"],
        "classified_rejections": classified,
        "input_hashes": {str(old_path): sha(old_path), str(design_path): sha(design_path)},
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                          str(Path(trajectory.__file__).resolve()): sha(trajectory.__file__),
                          str(Path(contact.__file__).resolve()): sha(contact.__file__)},
        "claim_boundary": "Partial original-start algorithm diagnostic only; budget censoring is not a physical event."
    }
    path = out / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "time_s": result["time_s"], "runtime_s": result["runtime_seconds"],
                      "accepted_steps": result["steps"], "rejected_steps": result["rejected"],
                      "inertial_calls": probe.calls, "runtime_failures": probe.failures,
                      "displacement_rejects": displacement_rejects,
                      "swept_clearance_rejects": sweeps["clearance_rejects"],
                      "inertial_elapsed_s": probe.elapsed_s,
                      "swept_elapsed_s": sweeps["elapsed_s"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
