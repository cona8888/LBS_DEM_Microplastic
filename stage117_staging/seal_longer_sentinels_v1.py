"""Seal completion of the bounded workflow without promoting failed numerics."""
from pathlib import Path
import longer_sentinels_v1 as job
import evaluate_longer_sentinels_v1 as evaluation
api = job.api


def main():
    target = job.EVAL / "completion.json"
    api.require(not target.exists(), "immutable stage seal exists")
    d = api.read(job.DESIGN)
    job.verify(d)
    result_path = evaluation.OUT / "results.json"
    r = api.read(result_path)
    api.require(api.read(evaluation.OUT / "completion.json")["results_sha256"] == api.sha(result_path), "evaluation drift")
    api.verify_mapping(r["artifact_hashes"])
    regression = api.read(job.EVAL / "evaluator_regression_01/results.json")
    api.require(regression["passed"] and regression["evaluator_sha256"] == api.sha(evaluation.__file__), "evaluator regression drift")
    api.require(api.read(job.PREFLIGHT)["passed"], "preflight failed")
    render = job.EVAL / "render_01"
    manifest = api.read(render / "manifest.json")
    api.require(manifest["source_sha256"] == api.sha(result_path), "render source drift")
    api.verify_mapping(manifest["artifacts"])
    qa = api.read(render / "visual_qa.json")
    api.require(qa["passed"] and qa["image_sha256"] == api.sha(render / "longer_paired_diagnostics.png"), "visual QA required")
    paths = [job.DESIGN, *Path(__file__).parent.glob("*.py"), *job.RUN.rglob("*"), *job.EVAL.rglob("*")]
    artifacts = {str(p): api.sha(p) for p in paths if p.is_file() and p.suffix != ".pyc"}
    status = "bounded_longer_diagnostics_verified_full_path_gate_open" if r["passed"] else "bounded_longer_diagnostics_complete_accuracy_or_budget_gate_open"
    api.write(target, {"stage": "Stage117", "workflow_complete": True, "status": status,
        "numerical_gate_passed": r["passed"], "complete_queries": r["complete_queries"], "passing_triplets": r["passing_triplets"],
        "raw_failures_or_incompletes_preserved": True, "physical_model_changed": False,
        "population_release_measured": False, "population_campaign_authorized": False, "full_path_feasibility_passed": False,
        "experimental_validation_claimed": False, "artifacts": artifacts,
        "next": "Diagnose any accumulated-error or budget failures using saved dense observations/checkpoints before extending horizon or selecting population cost. Preserve the current gates and slow cases."})
    print(status, "artifacts", len(artifacts))


if __name__ == "__main__":
    main()
