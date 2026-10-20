"""Verify the sampling pool and first transport pair; keep censoring explicit."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from release_accounting_v1 import release_bounds

ROOT=Path(__file__).resolve().parents[1]
POP=ROOT / "stage95_designs/common_admissible_population_01"
RUN=ROOT / "stage96_runs/population_prefix_01"
OUT=ROOT / "stage96_evaluations/population_prefix_review_01"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify(folder):
    result=json.loads((folder / "results.json").read_text())
    completion=json.loads((folder / "completion.json").read_text())
    if sha(folder / "results.json") != completion["results_sha256"]:
        raise RuntimeError("completion hash drift")
    n=0
    for section in ("input_hashes","source_hashes","artifact_hashes"):
        for path,digest in result.get(section,{}).items():
            if sha(path)!=digest:
                raise RuntimeError(f"binding drift: {path}")
            n+=1
    return result,n


def main():
    population,pop_bindings=verify(POP)
    run,run_bindings=verify(RUN)
    accounting_tests,test_bindings=verify(ROOT / "stage96_evaluations/accounting_tests_01")
    if not population["passed"] or not accounting_tests["passed"] or not run["executions_accounted"]:
        raise RuntimeError("missing population, execution or accounting evidence")
    planned=[]
    pools={}
    for seed in (1,2,3):
        rows=json.loads((POP / f"starts_s{seed}.json").read_text())
        pools[seed]=rows
        for row in rows:
            if abs(np.linalg.norm(row["orientation"])-1)>1e-12:
                raise RuntimeError("nonunit initial orientation")
            planned.append({"id":f'{seed}:{row["id"]}',"weight":row["weight_across_three_packings"]})
    summary=[]
    bounds=[]
    for row in run["rows"]:
        r=row["result"]
        independently_healthy=bool(r["minimum_gap_m"] is not None and r["minimum_gap_m"]>=-5e-10
            and r["max_contact_residual"]<=1e-8 and r["max_force_residual"]<=1e-8
            and r["max_momentum_residual"]<=1e-8 and r["max_reynolds"]<=3)
        if independently_healthy!=row["health_passed"]:
            raise RuntimeError("health flag mismatch")
        obs={f'{row["packing_seed"]}:{row["sample_id"]}':{
            "status":r["status"],"observed_pv":row["observed_pv"],"health_passed":row["health_passed"]}}
        bounds += [{"shape":row["shape"],**release_bounds(planned,obs,H)} for H in (.1,.25,.5,1.,2.)]
        summary.append({"shape":row["shape"],"status":r["status"],"observed_pv":row["observed_pv"],
                        "runtime_s":r["runtime_seconds"],"health_passed":row["health_passed"],
                        "resolved":row["resolved"],"first_passage_observed":r["status"]=="full_window_exit",
                        "finite_dwell_observed":r["persistent_contact_observed"]})
    OUT.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10})
    fig,axes=plt.subplots(1,2,figsize=(11,4.6))
    for seed,rows in pools.items():
        gap=np.sort([max(r["sphere_mean_exit_distance_pv"],r["fibre_mean_exit_distance_pv"]) for r in rows])
        axes[0].step(gap,np.arange(1,len(gap)+1)/len(gap),where="post",label=f"Packing {seed}")
    axes[0].axvline(.1,color="#999999",ls=":",label="Old 0.1-PV window")
    axes[0].set(xlabel="Paired mean-flow exit-distance proxy (PV)",ylabel="Cumulative fraction of sampled starts",
                title="A  768 paired probability-sampled starts",xlim=(0,1.05),ylim=(0,1.02))
    axes[0].legend(frameon=False,fontsize=9,loc="lower right")
    labels=["Sphere","AR4 fibre"]
    values=[r["observed_pv"] for r in summary]
    bars=axes[1].barh([1,0],values,height=.5,color=["#147d92","#b55d30"])
    axes[1].axvline(2.,color="#333333",ls="--",lw=1)
    axes[1].set_yticks([1,0],labels)
    axes[1].set(xlabel="Observed pore volumes",title="B  First sampled pair: 2-PV target",xlim=(0,2.5),ylim=(-.65,1.65))
    for bar,row in zip(bars,summary):
        label="Exit" if row["first_passage_observed"] else ("Complete; no exit" if row["resolved"] else "Unresolved")
        axes[1].text(.03,bar.get_y()+bar.get_height()+.08,f"{label} | {row['runtime_s']:.0f} s",fontsize=9)
    for ax in axes:
        ax.spines[["top","right"]].set_visible(False)
        ax.grid(axis="x",alpha=.15)
    fig.suptitle("Release-study sampling and bounded computational feasibility",fontsize=14)
    fig.text(.02,.02,"Common admissible reference population; one executed pair cannot identify a population release fraction.",fontsize=9)
    fig.tight_layout(rect=(0,.065,1,.94))
    figure=OUT / "sampling_and_feasibility.png"
    fig.savefig(figure,dpi=180)
    plt.close(fig)
    result={"evaluation_complete":True,"all_pilot_observations_resolved":run["all_resolved"],
            "summary":summary,"finite_pool_release_bounds":bounds,
            "binding_counts":{"population":pop_bindings,"run":run_bindings,"accounting_tests":test_bindings},
            "input_hashes":{str(p / "results.json"):sha(p / "results.json") for p in (POP,RUN,ROOT / "stage96_evaluations/accounting_tests_01")},
            "source_hashes":{str(Path(__file__)):sha(__file__),str(ROOT / "stage96_staging/release_accounting_v1.py"):sha(ROOT / "stage96_staging/release_accounting_v1.py")},
            "figure_sha256":sha(figure),"claim_boundary":"Finite-pool bounds keep unrun and censored mass explicit; no identified population fraction or independent-censoring assumption."}
    path=OUT / "results.json"
    path.write_text(json.dumps(result,indent=2))
    (OUT / "completion.json").write_text(json.dumps({"status":"complete_evaluated","results_sha256":sha(path)},indent=2))
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
