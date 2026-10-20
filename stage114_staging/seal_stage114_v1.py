"""Seal the completed numerical stage without granting campaign authority."""
from pathlib import Path

import requalify_stationary_flows_v1 as run


def main():
    root = run.ROOT / "stage114_evaluations" / run.STUDY
    destination = root / "completion.json"
    run.require(not destination.exists(), "stage already sealed")
    design = run.audit.read(run.DESIGN)
    run.verify_design(design)
    evaluated = root / "independent_evaluation_01/results.json"
    loaded = root / "loader_and_centre_probe_01/results.json"
    result, adapter = run.audit.read(evaluated), run.audit.read(loaded)
    for path in [evaluated, loaded]:
        item = run.audit.read(path.parent / "completion.json")
        run.require(item["passed"] is True and item["results_sha256"] == run.audit.sha(path), "evaluation unbound")
    run.verify_bindings(result)
    run.verify_bindings(adapter)
    image_dir = root / "render_01"
    run.verify_bindings(run.audit.read(image_dir / "manifest.json"))
    visual = run.audit.read(image_dir / "visual_inspection.json")
    run.require(visual["status"] == "visually_inspected_passed" and all(visual["checks"].values()), "visual QA incomplete")
    run.require(run.audit.sha(image_dir / visual["image"]) == visual["image_sha256"], "image changed after visual QA")
    run_folder = run.ROOT / "stage114_runs" / run.STUDY / "gpu_correction_01"
    run.require(not list(run_folder.rglob("failure.json")), "run failure present")
    run.require(run.audit.read(run_folder / "completion.json")["passed"] is True, "GPU completion missing")
    artifacts = [evaluated, evaluated.parent / "completion.json", loaded, loaded.parent / "completion.json",
                 image_dir / "manifest.json", image_dir / "visual_inspection.json", image_dir / visual["image"],
                 run_folder / "completion.json", run.DESIGN, Path(__file__), run.ROOT / "MASTER_PLAN.md"]
    run.write(destination, {"schema":"matdem.stage114.stage-completion.v1", "passed":True,
        "status":"stationary_flow_requalification_complete_transport_resolution_required",
        "new_gpu_cases":6, "reused_rechecked_reference_fields":1, "cpu_node_spotchecks":168,
        "unit_tests_passed":adapter["unit_tests"]["count"], "read_only_direct_field_loads":len(adapter["loaded_fields"]),
        "unsolved_field_combinations_rejected":len(adapter["unsupported_combinations_rejected"]),
        "matched_initial_centres_probed":adapter["probe"]["all"]["count"],
        "new_relaxation_runtime_seconds":sum(c["relaxation_runtime_seconds"] for c in result["cases"] if not c["reused_from_stage113"]),
        "artifacts":{str(p.relative_to(run.ROOT)):run.bind(p) for p in artifacts},
        "next_action":"Bind corrected SI fields and achieved-flow PV timing into a new checkpoint-safe both-shape sentinel adapter; verify matched transport/time resolution and complete-case cost before a population campaign.",
        "authority":{"population_campaign":False,"absolute_permeability_validation_claim":False,"new_physics":False},
        "immutable_evidence_preserved":True})
    print(str(destination))


if __name__ == "__main__":
    main()
