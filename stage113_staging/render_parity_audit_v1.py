"""Render the saved Stage113 diagnostic only; no smoothed scientific data."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import audit_flow_time_levels_v1 as audit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    out = args.output.resolve()
    assert out.is_relative_to(audit.ROOT / "stage113_evaluations") and not out.exists()
    root = audit.ROOT / "stage113_evaluations/temporal_flow_consistency_20260915"
    result = audit.read(root / "independent_evaluation_02/results.json")
    assert result["passed"]
    rows = []
    for path in sorted((root / "audit_01").glob("stage11*.json")):
        rows.append(audit.read(path))
    assert len(rows) == 6
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.9), gridspec_kw={"width_ratios":[1,1.25,1]})
    fig.suptitle("A steady-flow check caught an odd/even numerical mode", x=.06, ha="left", fontsize=18, fontweight="bold")
    fig.text(.06,.89,"Stage113 | 15 September 2026 | Bounded verification, not permeability or release validation", color="#52616b")
    a = next(x for x in rows if x["case_id"] == "stage111_s2_clean_f1p0_cpd2")
    b = next(x for x in rows if x["case_id"] == "stage112_s2_clean_f1p0_cpd4")
    for data,label,color in [(a,"CPD2 reference","#cf5f44"),(b,"CPD4 reference","#315d93")]:
        values = np.array([x["u_superficial"] for x in data["rows"]])
        mean = .5*(values[0]+values[1])
        axes[0].plot(range(5),100*(values/mean-1),"o-",label=label,color=color,lw=2)
    axes[0].set(title="1  Every second step looks steady",xlabel="Diagnostic step after saved state",ylabel="Mean velocity deviation from pair mean (%)")
    axes[0].set_xticks(range(5)); axes[0].axhline(0,color="#aab2b5",lw=.6)
    axes[0].legend(frameon=False,loc="lower right")
    labels = [x["case_id"].replace("stage111_","").replace("stage112_","").replace("clean_","").replace("f0p5","0.5U").replace("f1p0","1U").replace("f2p0","2U").replace("_"," ").upper() for x in rows]
    y = np.arange(len(rows))
    vals = [100*max(r["field_adjacent_relative_l2"] for r in x["rows"][1:]) for x in rows]
    axes[1].barh(y,vals,color=["#315d93" if "cpd4" in x["case_id"] else "#cf5f44" for x in rows],height=.6)
    axes[1].set_yticks(y,labels,fontsize=9); axes[1].invert_yaxis()
    axes[1].set(title="2  Local fields did not converge",xlabel="Consecutive velocity-field difference, L2 (%)",xlim=(0,26))
    for yi,value in zip(y,vals): axes[1].text(value+.3,yi,f"{value:.2f}",va="center",fontsize=9)
    names = ["Original\nCPD2 field","Corrected\nwarm start","Independent\ncold start"]
    values = [a["rows"][-1]["field_adjacent_relative_l2"]] + [x["last_adjacent_field_relative_l2"] for x in result["results"]]
    axes[2].bar(range(3),values,color=["#cf5f44","#238b78","#238b78"],width=.55)
    axes[2].set_yscale("log"); axes[2].set_xticks(range(3),names,fontsize=9)
    axes[2].axhline(5e-5,color="#444",ls="--",lw=1,label="Prospective gate")
    axes[2].set(title="3  One reference case corrected",ylabel="Consecutive field difference (relative L2)",ylim=(1e-8,1))
    axes[2].legend(frameon=False,fontsize=8,loc="upper right")
    fig.text(.06,.055,"Correction: one-time population initialization, then unchanged equations. No running filter or averaged final field.",fontsize=10)
    fig.text(.06,.018,"Remaining: requalify other flows/packings and CPD4, then sphere–fibre transport sensitivity. Historical evidence is preserved.",fontsize=10,color="#52616b")
    fig.subplots_adjust(left=.06,right=.985,top=.78,bottom=.23,wspace=.48)
    out.mkdir(parents=True)
    fig.savefig(out/"parity_verification.png",dpi=180)
    fig.savefig(out/"parity_verification.svg")
    plt.close(fig)
    audit.write(out/"manifest.json",{"renderer_sha256":audit.sha(__file__),
        "evaluation_sha256":audit.sha(root/"independent_evaluation_02/results.json"),
        "audit_completion_sha256":audit.sha(root/"audit_01/completion.json"),
        "artifacts":{x.name:audit.sha(x) for x in out.iterdir() if x.is_file()}})
    print(str(out/"parity_verification.png"))


if __name__ == "__main__":
    main()
