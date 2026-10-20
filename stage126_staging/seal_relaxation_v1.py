"""Seal the immutable Stage126 bounded CPD6 relaxation evidence."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage126_staging"))
import cpd6_relaxation_v2 as entry
job = entry.v1


def main():
    design = job.read(job.DESIGN)
    job.verify(design)

    original_failure = ROOT / "stage126_evaluations/cpd6_bounded_relaxation_20260916/preflight_01/failure.json"
    job.require(original_failure.is_file(), "original preflight failure missing")

    preflight_root = job.EVAL / "preflight_01"
    preflight = job.read(preflight_root / "results.json")
    preflight_done = job.read(preflight_root / "completion.json")
    job.require(preflight["passed"] and all(preflight["checks"].values()), "corrected preflight failed")
    job.require(preflight_done["results_sha256"] == job.sha(preflight_root / "results.json"), "preflight drift")

    raw = job.read(job.RUN / "completion.json")
    job.require(raw["status"] == "bounded_relaxation_gate_failed_preserved", "raw status drift")
    job.require(not (job.RUN / "failure.json").exists(), "runtime failure marker present")
    for key in ("record", "field", "state"):
        item = raw[key]
        job.require(job.sha(item["path"]) == item["sha256"], f"raw {key} drift")

    eval_root = job.EVAL / "independent_evaluation_02"
    results = job.read(eval_root / "results.json")
    eval_done = job.read(eval_root / "completion.json")
    job.require(eval_done["results_sha256"] == job.sha(eval_root / "results.json"), "evaluation drift")
    job.require(results["passed"], "evidence audit failed")
    job.require(results["status"] == "bounded_relaxation_verified_stationarity_and_mean_gates_failed", "evaluation status drift")
    job.require(not results["checks"]["steady_gate_passed"], "steady failure unexpectedly absent")
    job.require(not results["checks"]["mean_within_full_protocol_tolerance"], "mean gate unexpectedly passed")
    job.require(not results["checks"]["cpu_collision_spotchecks"], "fixed-point failure unexpectedly absent")
    job.require(not results["full_flow_solution"] and not results["transport_authorized"], "authority broadened")

    disposition = job.read(job.EVAL / "evaluation_attempt_01_disposition.json")
    job.require(disposition, "attempt-01 disposition missing")
    qa1 = job.read(job.EVAL / "render_01/visual_qa.json")
    qa2 = job.read(job.EVAL / "render_02/visual_qa.json")
    job.require(not qa1["passed"], "rejected render unexpectedly accepted")
    job.require(qa2["passed"], "corrected render visual QA absent")
    job.require(qa2["figure_sha256"] == job.sha(job.EVAL / "render_02/cpd6_bounded_relaxation.png"), "corrected figure drift")
    for path, expected in job.read(job.EVAL / "render_02/manifest.json")["artifacts"].items():
        job.require(job.sha(path) == expected, "render artifact drift " + path)

    bases = [
        ROOT / "stage126_designs/cpd6_bounded_relaxation_20260916",
        ROOT / "stage126_designs/cpd6_bounded_relaxation_attempt02_20260916",
        ROOT / "stage126_evaluations/cpd6_bounded_relaxation_20260916",
        job.EVAL,
        job.RUN,
        ROOT / "stage126_staging",
    ]
    files = sorted({p.resolve() for base in bases for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts})
    completion_path = job.EVAL / "completion.json"
    files = [p for p in files if p != completion_path.resolve()]
    completion = {
        "status": results["status"],
        "evidence_audit_passed": True,
        "corrected_preflight_passed": True,
        "bounded_relaxation_completed": True,
        "steady_field_gate_passed": False,
        "mean_match_gate_passed": False,
        "cpu_fixed_point_gate_passed": False,
        "numerical_health_and_reconstruction_passed": True,
        "full_flow_solution": False,
        "spatial_convergence_established": False,
        "empirical_validation_passed": False,
        "transport_authorized": False,
        "automatic_extension_authorized": False,
        "runtime_seconds": results["runtime_seconds"],
        "latest_spaced_field_change_relative_l2": results["latest_spaced_field_change_relative_l2"],
        "field_change_threshold": design["gates"]["field_relative_change_max"],
        "mean_relative_error": results["mean_relative_error"],
        "final_parity_superficial_gap_relative": results["final_parity_superficial_gap_relative"],
        "accepted_figure": str(job.EVAL / "render_02/cpd6_bounded_relaxation.png"),
        "artifacts": {str(p): job.sha(p) for p in files},
        "next": "Freeze a one-time parity-mode/stationary-initializer diagnosis. Do not extend this run, force-correct, dispatch a full CPD6 solve, or start transport until that diagnosis is independently qualified.",
    }
    job.write(completion_path, completion)
    print(completion["status"], "sealed", len(files), "artifacts", flush=True)


if __name__ == "__main__":
    main()
