"""Seal diagnosis only; the Stage117 numerical failure remains unrepaired."""
from pathlib import Path
import evaluate_probe_v1 as evaluation
job = evaluation.job
api = job.api


def main():
    target = job.EVAL / "completion.json"
    api.require(not target.exists(), "immutable stage seal exists")
    job.verify(api.read(job.DESIGN))
    p = evaluation.OUT / "results.json"
    r = api.read(p)
    api.require(api.read(evaluation.OUT / "completion.json")["results_sha256"] == api.sha(p), "evaluation drift")
    api.require(r["diagnostic_verified"] and r["endpoint_clipping_local_failure_isolated"], "diagnosis unverified")
    api.verify_mapping(r["artifact_hashes"])
    api.require(r["run_completion_sha256"] == api.sha(job.RUN / "completion.json"), "run completion drift")
    regression = api.read(job.EVAL / "evaluator_regression_01/results.json")
    api.require(regression["passed"] and regression["evaluator_sha256"] == api.sha(evaluation.__file__), "regression drift")
    render = job.EVAL / "render_01"
    manifest = api.read(render / "manifest.json")
    api.require(manifest["source_sha256"] == api.sha(p), "render source drift")
    api.verify_mapping(manifest["artifacts"])
    qa = api.read(render / "visual_qa.json")
    api.require(qa["passed"] and qa["image_sha256"] == api.sha(render / "endpoint_contact_diagnosis.png"), "visual QA required")
    paths = [job.DESIGN, *Path(__file__).parent.glob("*.py"), *job.RUN.rglob("*"), *job.EVAL.rglob("*")]
    artifacts = {str(v): api.sha(v) for v in paths if v.is_file() and v.suffix != ".pyc"}
    result = {"stage": "Stage118", "status": "local_endpoint_contact_solver_failure_isolated_not_repaired",
        "workflow_complete": True, "diagnosis_verified": True, "local_probes": 6, "run_wall_s": r["run_wall_s"],
        "accepted_control_exact": True, "physical_model_changed": False, "numerical_failure_repaired": False,
        "trajectory_advanced": False, "population_campaign_authorized": False, "population_release_measured": False,
        "experimental_validation_claimed": False, "artifacts": artifacts, "next": r["next"]}
    api.write(target, result)
    api.verify_mapping(artifacts)
    print(result["status"], "sealed artifacts", len(artifacts))


if __name__ == "__main__":
    main()
