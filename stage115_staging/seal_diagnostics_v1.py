"""Seal the completed diagnostic and its explicitly unresolved scientific gate."""
import argparse
from pathlib import Path

import corrected_transport_v1 as api


def main(visual_review_passed):
    root=api.ROOT/"stage115_evaluations/corrected_flow_short_time_20260915"
    api.require(not (root/"completion.json").exists(),"immutable stage seal already exists")
    api.require(visual_review_passed,"manual visual inspection of render_02 is required")
    api.verify_design(api.read(api.DESIGN))
    artifacts={}
    for name in ["independent_evaluation_01","evaluator_regression_01"]:
        path=root/name/"results.json"
        api.require(api.sha(path)==api.read(path.parent/"completion.json")["results_sha256"],"unbound evaluation: "+name)
        artifacts[str(path)]=api.sha(path)
        artifacts[str(path.parent/"completion.json")]=api.sha(path.parent/"completion.json")
    result=api.read(root/"independent_evaluation_01/results.json")
    audit=api.read(root/"evaluator_regression_01/results.json")
    api.require(audit["passed"] and audit["evaluator_sha256"]==api.sha(Path(__file__).with_name("evaluate_corrected_diagnostics_v1.py")),"evaluator regression drift")
    api.require(result["bindings"]["evaluator_sha256"]==audit["evaluator_sha256"],"unequal evaluator versions")
    api.require(result["run_complete"] and not result["passed"],"unexpected scientific status")
    api.require(sum(r["qualified"] for r in result["ledger"])==28,"completion count drift")
    api.require(all(r["health"]["passed"] for r in result["ledger"]),"numerical-health failure")
    api.require(sum(g["passed"] for g in result["three_level_time_groups"])==6 and result["restart"]["passed"],"verification count drift")
    render=root/"render_02"
    manifest=api.read(render/"manifest.json")
    api.require(manifest["results_sha256"]==api.sha(root/"independent_evaluation_01/results.json"),"render/evaluation drift")
    api.require(manifest["renderer_sha256"]==api.sha(Path(__file__).with_name("render_corrected_diagnostics_v2.py")),"renderer drift")
    for name,digest in manifest["artifacts"].items():
        api.require(api.sha(render/name)==digest,"render artifact drift")
        artifacts[str(render/name)]=digest
    artifacts[str(render/"manifest.json")]=api.sha(render/"manifest.json")
    api.write(render/"visual_qa.json",{
        "passed":True,"reviewer":"assistant visual inspection of rendered PNG",
        "checked":["All 12 group labels legible and within page","No footer/axis-label overlap in render_02",
                   "28 completed and eight budget-incomplete observations shown","Incomplete errors explicitly marked, not treated as zero",
                   "No population release or full-horizon verification claims"],
        "previous_render":"render_01 preserved; rejected for footer/axis-label collision only; scientific data unchanged",
        "png_sha256":api.sha(render/"short_time_diagnostics.png")})
    artifacts[str(render/"visual_qa.json")]=api.sha(render/"visual_qa.json")
    api.write(root/"completion.json",{
        "stage":"Stage115","workflow_complete":True,"scientific_gate_passed":False,
        "status":result["status"],"reason":"All eight budget-incomplete observations are fibres; all six fibre three-level comparisons remain unresolved.",
        "design_sha256":api.sha(api.DESIGN),"run_completion_sha256":result["bindings"]["completion_sha256"],
        "artifacts":artifacts,"sealer_sha256":api.sha(__file__),
        "population_campaign_authorized":False,"new_physics_executed":False,
        "next":"Bounded fibre geometry/hydrodynamic/contact/timestep profiling; equivalent-code verification before trajectory continuation."})
    print("SEALED: diagnostic complete; comparative accuracy and feasibility unresolved.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--visual-review-passed",action="store_true")
    main(p.parse_args().visual_review_passed)
