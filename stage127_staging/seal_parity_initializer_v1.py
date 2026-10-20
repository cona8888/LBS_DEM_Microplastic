"""Seal Stage127 without converting the mechanism result into flow or transport authority."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage127_staging"))
import parity_initializer_diagnosis_v1 as job


def main():
    d = job.read(job.DESIGN)
    job.verify(d)
    p = job.read(job.EVAL / "preflight_01/results.json")
    pc = job.read(job.EVAL / "preflight_01/completion.json")
    job.require(p["passed"] and pc["results_sha256"] == job.sha(job.EVAL / "preflight_01/results.json"), "preflight drift")
    raw = job.read(job.RUN / "completion.json")
    job.require(raw["status"] == "diagnostic_complete_pending_independent_evaluation", "raw status drift")
    job.require(not (job.RUN / "failure.json").exists(), "runtime failure marker")
    for key in ("record", "field", "state"):
        job.require(job.sha(raw[key]["path"]) == raw[key]["sha256"], key + " drift")
    root = job.EVAL / "independent_evaluation_01"
    r = job.read(root / "results.json")
    rc = job.read(root / "completion.json")
    job.require(rc["results_sha256"] == job.sha(root / "results.json"), "evaluation drift")
    job.require(r["passed"] and r["initializer_mechanism_verified"], "mechanism evidence failed")
    job.require(not r["all_predeclared_gates_passed"] and not r["checks"]["runtime_budget"], "cost failure not preserved")
    job.require(r["status"] == "parity_initializer_mechanism_verified_cost_gate_failed", "status drift")
    job.require(not r["full_flow_solution"] and not r["force_correction_authorized"] and not r["transport_authorized"], "authority broadened")
    job.require((job.EVAL / "render_01/failure.json").is_file(), "renderer failure missing")
    qa = job.read(job.EVAL / "render_02/visual_qa.json")
    fig = job.EVAL / "render_02/cpd6_parity_initializer.png"
    job.require(qa["passed"] and qa["figure_sha256"] == job.sha(fig), "visual QA failed")
    for path, expected in job.read(job.EVAL / "render_02/manifest.json")["artifacts"].items():
        job.require(job.sha(path) == expected, "render drift " + path)
    bases = [job.DESIGN.parent, job.RUN, job.EVAL, ROOT / "stage127_staging"]
    completion_path = job.EVAL / "completion.json"
    files = sorted({p.resolve() for base in bases for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.resolve() != completion_path.resolve()})
    completion = {
        "status": r["status"],
        "evidence_audit_passed": True,
        "initializer_mechanism_verified": True,
        "all_predeclared_gates_passed": False,
        "runtime_budget_passed": False,
        "runtime_seconds": r["runtime_seconds"],
        "runtime_limit_seconds": r["runtime_limit_seconds"],
        "field_change_reduction_factor": r["field_change_reduction_factor"],
        "final_adjacent_field_change_relative_l2": r["after_final_adjacent_field_change_relative_l2"],
        "cpu_fixed_point_passed": r["checks"]["cpu_fixed_point"],
        "full_flow_solution": False,
        "spatial_convergence_established": False,
        "force_correction_authorized": False,
        "transport_authorized": False,
        "empirical_validation_passed": False,
        "accepted_figure": str(fig),
        "artifacts": {str(p): job.sha(p) for p in files},
        "next": "Use the measured 317.94-s diagnostic cost to freeze a separately budgeted stationary CPD6 mean-correction/convergence design. No automatic extension, full solve or transport follows from Stage127.",
    }
    job.write(completion_path, completion)
    print(completion["status"], "sealed", len(files), "artifacts", flush=True)


if __name__ == "__main__":
    main()
