import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(r"C:\MATDEM_MICROPLASTIC")
RUN=ROOT/"stage36_runs"/"stage36ag_periodic_drag_n32_diagnostic_20260910"/"diagnostic_01"
OUT=ROOT/"stage36_evaluations"/"stage36ag_n32_diagnostic_20260910"/"evaluation_02"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if OUT.exists():raise SystemExit("fail closed: evaluation exists")
    m=json.loads((RUN/"manifest.json").read_text()); h=json.loads((RUN/"history.json").read_text())
    for p,v in m["artifact_hashes"].items():
        if sha(Path(p))!=v:raise SystemExit("artifact hash mismatch")
    steps=[r["step"] for r in h];u=[r["superficial_velocity"][0] for r in h];f=[r["force_on_sphere"][0] for r in h]
    OUT.mkdir(parents=True)
    fig,ax=plt.subplots(1,2,figsize=(9,3.7))
    ax[0].plot(steps,u,"o-");ax[0].axhline(m["target_velocity_x"],color="k",ls="--",label="target")
    ax[0].set(xlabel="LBM step",ylabel="superficial velocity (LU)",title="N32 startup velocity");ax[0].legend()
    ax[1].plot(steps,f,"o-");ax[1].axhline(m["reference_force"],color="k",ls="--",label="steady reference")
    ax[1].set(xlabel="LBM step",ylabel="sphere force (LU)",title="N32 startup force");ax[1].legend()
    fig.tight_layout();fig.savefig(OUT/"startup_diagnostic.png",dpi=180);plt.close(fig)
    text=f'''# Stage36AG N32 startup diagnostic\n\n- Status: `{m["status"]}`\n- Executed: {m["steps"]} driven steps in {m["elapsed_seconds"]:.3f} s ({m["seconds_per_step"]:.4f} s/step).\n- Projected five-window CPU duration: {m["projected_full_five_window_seconds"]/60:.8g} min.\n- Force sign: pass.\n- Maximum mass drift: {m["max_mass_relative_drift"]:.3e}.\n- Maximum momentum-ledger residual: {m["max_momentum_ledger_residual"]:.3e} LU.\n- Maximum density error: {m["max_density_error"]:.3e}.\n- Maximum marker slip: {m["max_marker_slip"]:.3e}.\n\nThe velocity and force are still in startup and are only {100*m["last_superficial_velocity_x"]/m["target_velocity_x"]:.3f}% and {100*m["last_force_ratio_to_reference"]:.3f}% of their respective target/reference values. No convergence or force-accuracy claim is made. The full CPU path is feasible but inefficient; qualify an equivalent constant-reference-density factorization or GPU implementation before the long run.\n'''
    (OUT/"RESULTS.md").write_text(text)
    rec={"stage":"Stage36AG-evaluation","status":"startup_health_passed_convergence_not_assessed","run_manifest_sha256":sha(RUN/"manifest.json"),"figure_sha256":sha(OUT/"startup_diagnostic.png"),"convergence_claim":False,"force_validation_claim":False,"next_action":"static and equivalence audit of an accelerated marker projection before full N32"}
    (OUT/"evaluation.json").write_text(json.dumps(rec,indent=2)+"\n")
if __name__=='__main__':main()
