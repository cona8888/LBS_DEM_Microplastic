"""Show completed and incomplete diagnostics without hiding missing outcomes."""
from pathlib import Path
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import corrected_transport_v1 as api


def main(results_path,output):
    api.require(not output.exists() and output.is_relative_to(api.ROOT/"stage115_evaluations"),"fresh render required")
    data=api.read(results_path)
    api.require(api.read(results_path.parent/"completion.json")["results_sha256"]==api.sha(results_path),"unbound result")
    design=api.read(api.DESIGN)
    api.verify_design(design)
    rows={r["case_id"]:r for r in data["ledger"]}
    groups=data["three_level_time_groups"]
    n=len(groups)
    labels=[f"s{g['seed']} / {g['flow_factor']:g}U0\n{'sphere' if g['shape']=='equal_volume_sphere' else 'AR4'} / CPD{g['cpd']}" for g in groups]
    colours=["#196f8b","#cd8534","#7855a2"]
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(2,2,figsize=(17,10.6))
    fig.subplots_adjust(left=.065,right=.97,bottom=.12,top=.84,wspace=.28,hspace=.62)
    title="Short-time transport: verification passed" if data["passed"] else "Short-time transport: qualification still open"
    fig.suptitle(title,x=.065,y=.96,ha="left",fontsize=25,fontweight="bold")
    fig.text(.065,.918,"Stage115 | Corrected physical flow; unchanged contact model; original paired sentinel starts",fontsize=13)
    times=np.array([[rows.get(g["case_ids"][j],{}).get("time_s",0) for g in groups] for j in range(3)])
    ax=axes[0,0]
    ax.imshow(times/.25,aspect="auto",vmin=0,vmax=1,cmap="Blues")
    for j in range(3):
        for i in range(n):
            complete=rows.get(groups[i]["case_ids"][j],{}).get("status")=="present_at_horizon"
            ax.text(i,j,f"{times[j,i]:.3f}",ha="center",va="center",fontsize=8,color="white" if complete else "#a52b20",fontweight="bold" if not complete else "normal")
    ax.set(xticks=np.arange(n),xticklabels=labels,yticks=[0,1,2],yticklabels=["base","half dt","quarter dt"],title="A  Physical time reached (s); target 0.250 s")
    ax.tick_params(axis="x",labelrotation=65,labelsize=8)
    ax=axes[0,1]
    for j in range(3):
        values=[rows.get(g["case_ids"][j],{}).get("runtime_s",np.nan) for g in groups]
        ax.plot(np.arange(n),values,"o-",color=colours[j],label=["base","half dt","quarter dt"][j],ms=4)
    ax.axhline(45,ls="--",color="#ac5544",label="Per-run budget: 45 s")
    ax.set(yscale="log",xticks=np.arange(n),xticklabels=labels,ylabel="Integrator runtime (s)",title="B  Cost of this prefix only — not full-trajectory cost")
    ax.tick_params(axis="x",labelrotation=65,labelsize=8)
    ax.legend(fontsize=8,loc="lower right")
    ax=axes[1,0]
    ratios=[]
    for i,g in enumerate(groups):
        if "medium_fine" in g:
            m=g["medium_fine"]
            ratio=max(m["position_difference_over_b"]/.02,m["apolar_axis_angle_rad"]/.01,m["translational_velocity_relative_difference"]/.05)
            ratios.append((i,ratio))
            ax.bar(i,max(ratio,1e-4),color="#217d81" if g["passed"] else "#b6553e",width=.7)
        else:
            ax.scatter(i,.01,marker="x",color="#b6553e",s=60)
    ax.axhline(1,color="#333333",ls="--")
    ax.set(yscale="log",ylim=(.005,max(2,max((r for _,r in ratios),default=1)*1.5)),xticks=np.arange(n),xticklabels=labels,
           ylabel="Largest fine–medium error / declared gate",title="C  Three-level checks; × means incomplete, not zero error")
    ax.tick_params(axis="x",labelrotation=65,labelsize=8)
    ax=axes[1,1];ax.axis("off")
    complete=sum(r.get("status")=="present_at_horizon" for r in data["ledger"])
    incomplete=sum(r.get("status")=="incomplete_budget" for r in data["ledger"])
    healthy=sum(r.get("health",{}).get("passed",False) for r in data["ledger"])
    refined=sum(g["passed"] for g in groups)
    restart=data["restart"]
    text=(f"{complete}/36 reached the common 0.25-s horizon\n"
          f"{incomplete} budget-limited; retained as incomplete\n"
          f"{healthy}/36 passed independent numerical-health checks\n"
          f"{refined}/12 three-level response checks passed\n\n"
          f"Fresh-process restart: {'PASS' if restart['passed'] else 'UNRESOLVED / FAIL'}\n"
          f"Analytical outlet checks: {sum(r['passed'] for r in data['outlet_unit_benchmarks']['rows'])}/13\n\n"
          "No population release fraction is estimated.\n"
          "No full-horizon accuracy or affordability is inferred.\n"
          "Unequal-time partial states are not compared as spatial error.")
    ax.text(0,1,"D  Evidence and limits",fontsize=14,va="top")
    ax.text(0,.87,text,fontsize=12,va="top",linespacing=1.65)
    fig.text(.065,.035,"Fixed sand • independent rigid particles • prescribed one-way flow • numerical verification, not experimental validation",fontsize=11,color="#495867")
    output.mkdir(parents=True)
    for suffix in ["png","svg"]:fig.savefig(output/f"short_time_diagnostics.{suffix}",dpi=180,facecolor="white")
    plt.close(fig)
    api.write(output/"manifest.json",{"results_path":str(results_path),"results_sha256":api.sha(results_path),"renderer_sha256":api.sha(__file__),
        "artifacts":{p.name:api.sha(p) for p in output.iterdir()}})
    print(str(output/"short_time_diagnostics.png"))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();main(a.results.resolve(),a.output.resolve())
