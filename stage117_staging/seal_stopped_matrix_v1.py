"""Seal a failed/stopped bounded workflow; never label the matrix successful."""
from pathlib import Path
import longer_sentinels_v1 as job
import audit_stopped_matrix_v1 as audit
api = job.api


def main():
    target = job.EVAL / "completion.json"
    api.require(not target.exists(), "immutable stage seal exists")
    job.verify(api.read(job.DESIGN))
    path = audit.OUT / "results.json"
    r = api.read(path)
    api.require(api.read(audit.OUT / "completion.json")["results_sha256"] == api.sha(path) and r["audit_passed"], "failure audit drift")
    api.verify_mapping(r["artifact_hashes"])
    api.require(r["case_accounting"] == {"incomplete_budget": 2, "not_run_after_fail_closed_stop": 14, "numerical_failure": 1, "present_at_horizon": 1}, "unexpected accounting")
    api.require(not (job.RUN / "completion.json").exists(), "simulation falsely completed")
    regression = api.read(job.EVAL / "evaluator_regression_01/results.json")
    api.require(regression["passed"] and api.read(job.PREFLIGHT)["passed"], "preflight/regression failure")
    render = job.EVAL / "stop_render_02"
    manifest = api.read(render / "manifest.json")
    api.require(manifest["audit_sha256"] == api.sha(path), "render source drift")
    api.verify_mapping(manifest["artifacts"])
    diagnosis_path = job.EVAL / "stop_render_01/branch_diagnosis.json"
    api.require(manifest["branch_diagnosis_sha256"] == api.sha(diagnosis_path), "diagnosis drift")
    diagnosis = api.read(diagnosis_path)
    api.require(diagnosis["core_sha256"] == api.sha(api.frozen.core.__file__), "diagnostic source drift")
    qa = api.read(render / "visual_qa.json")
    api.require(qa["passed"] and qa["image_sha256"] == api.sha(render / "longer_test_stop.png"), "visual QA required")
    paths = [job.DESIGN, *Path(__file__).parent.glob("*.py"), *job.RUN.rglob("*"), *job.EVAL.rglob("*")]
    artifacts = {str(p): api.sha(p) for p in paths if p.is_file() and p.suffix != ".pyc"}
    result = {"stage": "Stage117", "status": "failure_audited_and_preserved_local_contact_solver_diagnosis_required",
        "bounded_workflow_closed": True, "planned_matrix_completed": False, "failure_audit_passed": True,
        "scientific_numerical_gate_passed": False, "case_accounting": r["case_accounting"],
        "all_last_accepted_states_healthy": r["all_last_accepted_states_healthy"], "integration_cost_s": r["total_integrator_runtime_s"],
        "failure_class": diagnosis["cause_class"], "failed_time_s": r["failure_detail"]["last_accepted_time_s"],
        "physical_model_changed": False, "source_and_raw_evidence_preserved": True, "population_campaign_authorized": False,
        "population_release_measured": False, "full_path_feasibility_passed": False, "experimental_validation_claimed": False,
        "next": diagnosis["next_action"], "artifacts": artifacts}
    api.write(target, result)
    api.verify_mapping(artifacts)
    print(result["status"], "sealed artifacts", len(artifacts))


if __name__ == "__main__":
    main()
