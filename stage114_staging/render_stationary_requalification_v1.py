"""Render only evaluated Stage114 numerical evidence; immutable output."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import requalify_stationary_flows_v1 as run


def main(results_path, output):
    run.require(output.is_relative_to(run.ROOT / "stage114_evaluations") and not output.exists(), "fresh render directory required")
    data = run.audit.read(results_path)
    completion = run.audit.read(results_path.parent / "completion.json")
    run.require(completion["results_sha256"] == run.audit.sha(results_path), "results not bound")
    run.require(data["passed"] is True, "do not render a success for a failed evaluation")
    for case in data["cases"]:
        run.verify_bindings(case["bundle"])
    design = run.audit.read(run.DESIGN)
    cases = {c["case_id"]: c for c in data["cases"]}
    names = ["s2_f0p5_cpd2", "s2_f1p0_cpd2", "s2_f2p0_cpd2", "s1_f1p0_cpd2", "s3_f1p0_cpd2", "s2_f1p0_cpd4"]
    labels = ["s2 / 0.5U0", "s2 / U0", "s2 / 2U0", "s1 / U0", "s3 / U0", "s2 / U0\nCPD4"]
    colour = "#167d8d"
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(15, 10.2))
    fig.subplots_adjust(left=.08, right=.96, bottom=.15, top=.85, hspace=.5, wspace=.32)
    fig.suptitle("Stationary flow fields requalified", x=.08, y=.965, ha="left", fontsize=24, fontweight="bold")
    fig.text(.08, .925, "Stage114  |  Unchanged LBM physics; one-time population initialization correction", fontsize=13, color="#40515f")
    x = np.arange(len(names))
    ax = axes[0,0]
    means = [cases[n]["mean_interstitial_velocity_m_s"] / 1e-4 for n in names]
    ax.bar(x, means, color=colour, width=.62)
    for i, name in enumerate(names):
        target = cases[name]["flow_factor"]
        ax.plot([i-.36,i+.36], [target,target], color="#d98b36", lw=2)
        ax.text(i, means[i]+.065, f"{means[i]:.3f}", ha="center", fontsize=9)
    ax.set(xticks=x, xticklabels=labels, ylabel="Achieved mean interstitial speed / U0", ylim=(0,2.35), title="A  Physical speed retained (target: orange mark)")
    ax.tick_params(axis="x", labelsize=9)
    ax.text(.01,.96,"U0 = 10⁻⁴ m/s; target tolerance ±5%",transform=ax.transAxes,va="top",fontsize=10)
    ax = axes[0,1]
    specs = {s["case_id"]:s for s in design["cases"]+[design["reused_reference"]]}
    old = []
    for name in names:
        source_id = specs[name]["source"]["case_id"]
        prior = run.audit.read(run.BASE / "audit_01" / (source_id+".json"))
        old.append(max(r.get("field_adjacent_relative_l2",0) for r in prior["rows"]))
    new = [cases[n]["last_adjacent_field_relative_l2"] for n in names]
    ax.scatter(x,old,color="#a04735",label="Original consecutive-step change",s=40)
    ax.scatter(x,new,color=colour,label="Corrected final consecutive-step change",s=40)
    ax.axhline(5e-5,color="#788390",ls="--",label="Temporal gate: 5 × 10⁻⁵")
    ax.set(yscale="log",xticks=x,xticklabels=labels,ylabel="Velocity-field relative L2 change",title="B  Odd/even state cycle removed")
    ax.tick_params(axis="x",labelsize=9)
    ax.legend(fontsize=8,loc="center left")
    ax = axes[1,0]
    profiles = data["corrected_archive_to_direct_profiles"]
    factors = [.5,1,2]
    ax.plot(factors,[p["normalized_vector_rms_relative"]*100 for p in profiles],"o-",color=colour,label="Vector RMS / direct RMS")
    ax.plot(factors,[p["normalized_vector_p95"]*100 for p in profiles],"s-",color="#8462a2",label="Vector p95 / direct mean speed")
    ax.axhline(2,color=colour,ls="--",alpha=.6,label="RMS gate: 2%")
    ax.axhline(5,color="#8462a2",ls="--",alpha=.6,label="p95 gate: 5%")
    ax.set(xticks=factors,xlabel="Seed-2 target speed / U0",ylabel="Normalized profile difference (%)",title="C  Corrected low-Re archive vs direct solution")
    ax.legend(fontsize=8)
    ax.set_ylim(bottom=0)
    ax = axes[1,1]
    m2,m4 = cases["s2_f1p0_cpd2"]["dimensionless_mobility"],cases["s2_f1p0_cpd4"]["dimensionless_mobility"]
    ax.bar([0,1],[1,m4/m2],color=[colour,"#d98b36"],width=.5)
    ax.set(xticks=[0,1],xticklabels=["CPD2","CPD4"],ylabel="Mobility / CPD2 mobility",ylim=(0,1.35),title="D  Spatial resolution remains a separate issue")
    s=data["spatial_resolution"]
    ax.text(.5,1.2,f"Mobility shift: {s['signed_mobility_relative_shift']:+.2%}",ha="center",fontsize=12)
    ax.text(.03,.29,f"Interior field RMS difference: {s['normalized_vector_rms_relative']:.2%}\nCommon fully fluid blocks: {s['common_fraction_of_cpd2_fluid']:.1%}\nMixed wall blocks excluded; not a transport-error bound.",transform=ax.transAxes,fontsize=10,va="top",bbox={"facecolor":"white","edgecolor":"none","alpha":.96})
    fig.text(.08,.072,"NEXT: corrected-field near-wall and matched particle-response/transport checks, then the cost gate.",fontsize=12,fontweight="bold")
    fig.text(.08,.04,"No population export result, absolute permeability validation, mobile sand or two-way coupling is claimed.  |  15 Sep 2026",fontsize=10,color="#52606d")
    output.mkdir(parents=True)
    for suffix in ["png","svg"]:
        fig.savefig(output / ("stationary_flow_requalification."+suffix),dpi=180,facecolor="white")
    plt.close(fig)
    run.write(output / "manifest.json", {"results":run.bind(results_path),"renderer":run.bind(__file__),"artifacts":{p.name:run.bind(p) for p in output.iterdir()}})
    print(str(output / "stationary_flow_requalification.png"))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    main(a.results.resolve(),a.output.resolve())
