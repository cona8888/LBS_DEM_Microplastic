"""Seal cost verification and bounded short-time convergence, not Stage B."""
import argparse
from pathlib import Path

import refine_short_velocity_v1 as job
api=job.api


def main(visual_review_passed):
    root=job.ROOT/"stage116_evaluations/fibre_cost_attribution_20260915"
    api.require(not (root/"completion.json").exists(),"immutable stage seal exists")
    api.require(visual_review_passed,"manual rendered-figure inspection required")
    job.verify(api.read(job.DESIGN));artifacts={};evaluations={}
    names=["profile_evaluation_01","optimization_evaluation_01","short_matrix_evaluation_01","refinement_evaluation_01"]
    for name in names:
        path=root/name/"results.json";r=api.read(path)
        api.require(api.sha(path)==api.read(path.parent/"completion.json")["results_sha256"],"evaluation digest drift")
        evaluations[name]=r
        artifacts[str(path)]=api.sha(path);artifacts[str(path.parent/"completion.json")]=api.sha(path.parent/"completion.json")
    api.require(all(evaluations[n]["passed"] for n in names if n!="short_matrix_evaluation_01"),"required final gate failed")
    api.require(not evaluations["short_matrix_evaluation_01"]["passed"],"expected coarser failed gate not preserved")
    api.require(evaluations["refinement_evaluation_01"]["passing_latest_triplets"]==12,"short-time gate incomplete")
    for run in [job.parent.opt.profile.RUN,job.parent.opt.RUN,job.parent.RUN,job.RUN]:
        completion=api.read(run/"completion.json")
        api.require(not list(run.rglob("failure.json")) and not any(p.stat().st_size for p in run.glob("*.stderr.txt")),"failure/stderr in sealed run")
        artifacts[str(run/"completion.json")]=api.sha(run/"completion.json")
        for name,digest in completion["records"].items():
            child=run/name
            api.require(api.sha(child/"record.json")==digest==api.read(child/"completion.json")["record_sha256"],"raw record digest drift")
            child_completion=api.read(child/"completion.json")
            for file,expected in child_completion.get("artifacts",{}).items():api.require(api.sha(child/file)==expected,"raw artifact drift")
            if "prefix_sha256" in child_completion:api.require(api.sha(child/"prefix_result.json")==child_completion["prefix_sha256"],"raw prefix drift")
    render=root/"render_01";manifest=api.read(render/"manifest.json")
    api.require(manifest["renderer_sha256"]==api.sha(Path(__file__).with_name("render_stage116_v1.py")),"renderer drift")
    for name,digest in manifest["artifacts"].items():
        api.require(api.sha(render/name)==digest,"figure drift");artifacts[str(render/name)]=digest
    api.write(render/"visual_qa.json",{"passed":True,"reviewer":"assistant visual inspection of rendered PNG",
        "checks":["All four panels and labels legible, no overlap or clipping","Local timing scope and exact-state comparison clear",
                  "Coarser failed velocity checks remain shown against unchanged 5% gate","Spatial sensitivity and full-trajectory limitations visible"],
        "png_sha256":api.sha(render/"fibre_cost_and_accuracy.png")})
    for p in [render/"manifest.json",render/"visual_qa.json"]:artifacts[str(p)]=api.sha(p)
    for script in Path(__file__).parent.glob("*.py"):artifacts[str(script.resolve())]=api.sha(script)
    for path in job.DESIGN.parent.glob("*.json"):artifacts[str(path)]=api.sha(path)
    api.write(root/"completion.json",{"stage":"Stage116","status":"implementation_speedup_and_short_time_response_verified_stage_B_remains_open",
        "workflow_complete":True,"implementation_gate_passed":True,"short_time_timestep_gate_passed":True,
        "full_trajectory_feasibility_passed":False,"population_campaign_authorized":False,"experimental_validation_claimed":False,
        "coarser_failed_gate_preserved":True,"artifacts":artifacts,"sealer_sha256":api.sha(__file__),
        "next":"Bounded longer contact-rich paired sentinels; quantify accumulated time/spatial sensitivity and measured cost before campaign planning."})
    print("SEALED Stage116: optimization and bounded short-time timestep checks pass; broader Stage B remains open.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--visual-review-passed",action="store_true")
    main(p.parse_args().visual_review_passed)
