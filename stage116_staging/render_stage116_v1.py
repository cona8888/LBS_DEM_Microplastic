"""Render cost gains separately from remaining physical/numerical claim limits."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import refine_short_velocity_v1 as job
api=job.api


def main():
    root=job.ROOT/"stage116_evaluations/fibre_cost_attribution_20260915"
    output=root/"render_01";api.require(not output.exists(),"immutable render exists")
    data={}
    for key,name in [("profile","profile_evaluation_01"),("optimization","optimization_evaluation_01"),("matrix","short_matrix_evaluation_01"),("refinement","refinement_evaluation_01")]:
        p=root/name/"results.json"
        api.require(api.sha(p)==api.read(p.parent/"completion.json")["results_sha256"],"unbound evaluation")
        data[key]=api.read(p)
    job.verify(api.read(job.DESIGN))
    opt=data["optimization"];matrix=data["matrix"];fine=data["refinement"]
    plt.rcParams.update({"font.size":11,"axes.spines.top":False,"axes.spines.right":False})
    fig,ax=plt.subplots(2,2,figsize=(14.5,9.7))
    fig.subplots_adjust(left=.08,right=.96,top=.82,bottom=.15,wspace=.28,hspace=.45)
    fig.suptitle("Faster fibre clearance checks, unchanged physical model",x=.08,y=.96,ha="left",fontsize=23,fontweight="bold")
    fig.text(.08,.91,"Stage116 | Cost profiling → conservative search pruning → exact-state checks → timestep refinement",fontsize=12)
    groups=opt["groups"];x=np.arange(3)
    a=ax[0,0]
    a.bar(x-.17,[np.median(g["reference_s"]) for g in groups],.34,label="Reference",color="#778ca3")
    a.bar(x+.17,[np.median(g["candidate_s"]) for g in groups],.34,label="Pruned search",color="#167d8d")
    for i,g in enumerate(groups):a.text(i,max(g["reference_s"])+.04,f"{g['median_speedup']:.2f}×",ha="center",weight="bold")
    a.set(xticks=x,xticklabels=["Seed 3\npre-contact","Seed 2\nactive contact","Seed 1\ncontact segment"],ylabel="Unprofiled local runtime (s)",ylim=(0,1.2),title="A  Local speedup; exact checkpoint states")
    a.legend(fontsize=9)
    a=ax[0,1];a.axis("off")
    complete=sum(r["qualified"] for r in matrix["ledger"])
    refined=sum(r["status"]=="present_at_horizon" for r in fine["ledger"])
    text=(f"{complete}/36 original short-query cases completed\n"
          f"{sum(p['exact_original_prefix'] for p in matrix['prefix_equivalence'])}/8 original partial prefixes reproduced exactly\n"
          f"{refined}/4 added finer-step runs reached 0.25 s\n"
          f"{fine['passing_latest_triplets']}/12 latest three-level checks passed\n\n"
          f"{opt['synthetic_cases']} synthetic A/B tests; {opt['bound_checks']:,} bound checks\n"
          "No contact or force tolerance was relaxed.\n"
          "All earlier failures remain in the evidence record.")
    a.text(0,1,"B  Verification evidence",va="top",fontsize=14)
    a.text(0,.86,text,va="top",linespacing=1.6,fontsize=11.5)
    a=ax[1,0];x=np.arange(4)
    original=[];refined_values=[];labels=[]
    for g in fine["groups"]:
        original.append(100*g["coarse_medium"]["translational_velocity_relative_difference"])
        refined_values.append(100*g.get("medium_fine",{}).get("translational_velocity_relative_difference",np.nan))
        labels.append(f"{g['flow_factor']:g} U0\nCPD{g['cpd']}")
    a.bar(x-.17,original,.34,label="Half → quarter step",color="#cb7b37")
    a.bar(x+.17,refined_values,.34,label="Quarter → eighth step",color="#167d8d")
    a.axhline(5,color="#963f32",ls="--",label="Unchanged 5% gate")
    a.set(xticks=x,xticklabels=labels,ylabel="Relative translational-velocity change (%)",title="C  Targeted seed-2 fibre refinement",ylim=(0,max(10,np.nanmax(refined_values)*1.4)))
    a.legend(fontsize=8,loc="upper right")
    a=ax[1,1];a.axis("off")
    a.text(0,1,"D  Matched CPD2 → CPD4 response at 0.25 s",fontsize=13,va="top")
    sphere=matrix["spatial_diagnostics"][0];fibre=fine["fibre_spatial_eighth_step"]
    def value(r,key,scale=1):return f"{r[key]*scale:.4f}" if key in r else "unresolved"
    cells=[["Position / minor radius",value(sphere,"position_difference_over_b"),value(fibre,"position_difference_over_b")],
           ["Axis difference (rad)","not applicable",value(fibre,"apolar_axis_angle_rad")],
           ["Velocity difference (%)",value(sphere,"translational_velocity_relative_difference",100),value(fibre,"translational_velocity_relative_difference",100)]]
    table=a.table(cellText=cells,colLabels=["Observable","Sphere (¼ step)","Fibre (⅛ step)"],cellLoc="left",colLoc="left",bbox=[0,.4,1,.46],colWidths=[.46,.27,.27])
    table.auto_set_font_size(False);table.set_fontsize(9)
    for (row,col),cell in table.get_celld().items():
        cell.set_edgecolor("#d5dce2")
        if row==0:cell.set_facecolor("#edf3f6");cell.set_text_props(weight="bold")
    a.text(0,.28,"Direct fields retain their achieved flow speeds.\nThese are short-time sensitivities, not full-path error bounds.",va="top",fontsize=10.5,linespacing=1.5)
    fig.text(.08,.05,"Still open: longer contact-rich accuracy and cost • full-trajectory feasibility • population release comparison",fontsize=12,color="#963f32")
    fig.text(.08,.023,"Fixed sand | rigid independent particles | one-way prescribed flow | numerical verification, not experimental validation",fontsize=10,color="#556777")
    output.mkdir(parents=True)
    for suffix in ["png","svg"]:fig.savefig(output/f"fibre_cost_and_accuracy.{suffix}",dpi=180,facecolor="white")
    plt.close(fig)
    api.write(output/"manifest.json",{"renderer_sha256":api.sha(__file__),"evaluations":{k:v["bindings"] for k,v in data.items()},"artifacts":{p.name:api.sha(p) for p in output.iterdir()}})
    print(str(output/"fibre_cost_and_accuracy.png"))


if __name__=="__main__":main()
