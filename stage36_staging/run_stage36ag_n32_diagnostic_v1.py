from __future__ import annotations

import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import periodic_drag_reference_v1 as solver

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
PARENT = ROOT/"stage36_evaluations"/"stage36af_periodic_drag_runner_audit_20260909"/"audit_01"/"audit.json"
SOURCE = ROOT/"stage36_staging"/"periodic_drag_reference_v1.py"
SELF = ROOT/"stage36_staging"/"run_stage36ag_n32_diagnostic_v1.py"
OUT = ROOT/"stage36_runs"/"stage36ag_periodic_drag_n32_diagnostic_20260910"/"diagnostic_01"

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(p: Path, x) -> None:
    p.write_text(json.dumps(x, indent=2)+"\n", encoding="utf-8")

def main() -> None:
    if OUT.exists(): raise SystemExit(f"fail closed: immutable output exists: {OUT}")
    parent = json.loads(PARENT.read_text())
    if not parent["passed"] or parent["driven_steps_executed"] != 0: raise SystemExit("invalid parent")
    if sha(SOURCE) != parent["input_hashes"]["runner"]: raise SystemExit("runner lineage mismatch")
    OUT.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    history = []
    try:
        state = solver.initialize(32)
        nominal = solver.nominal_parameters(32)
        for step in range(1, 17):
            state, row = solver.step(state, nominal["source_impulse_per_cell"])
            row["step"] = step
            row["elapsed_seconds"] = time.monotonic()-t0
            history.append(row)
            if row["minimum_population"] <= 0 or row["density_error"] >= 0.01:
                raise RuntimeError("numerical-health gate failed")
            if max(abs(x) for x in row["momentum_ledger_residual"]) > 1e-11:
                raise RuntimeError("momentum-ledger gate failed")
        np.savez_compressed(OUT/"final_state.npz", f=state["f"])
        write(OUT/"history.json", history)
        elapsed = time.monotonic()-t0
        last = history[-1]
        speed = last["superficial_velocity"][0]
        force = last["force_on_sphere"][0]
        manifest = {
            "stage":"Stage36AG", "status":"bounded_n32_startup_diagnostic_complete_not_converged",
            "started_utc":started, "completed_utc":datetime.now(timezone.utc).isoformat(),
            "grid":32, "steps":16, "elapsed_seconds":elapsed, "seconds_per_step":elapsed/16,
            "projected_full_five_window_seconds":elapsed/16*5*nominal["viscous_window_steps"],
            "last_superficial_velocity_x":speed, "target_velocity_x":nominal["target_u_lu"],
            "last_force_x":force, "reference_force":nominal["reference_force_lu"],
            "last_force_ratio_to_reference":force/nominal["reference_force_lu"],
            "force_sign_passed":force > 0, "health_passed":True,
            "max_momentum_ledger_residual":max(max(abs(x) for x in r["momentum_ledger_residual"]) for r in history),
            "max_mass_relative_drift":max(r["mass_relative_drift"] for r in history),
            "max_density_error":max(r["density_error"] for r in history),
            "max_marker_slip":max(r["marker_slip"] for r in history),
            "convergence_assessed":False, "force_acceptance_assessed":False,
            "input_hashes":{"parent":sha(PARENT),"solver":sha(SOURCE),"launcher":sha(SELF)},
            "python":platform.python_version(),"numpy":np.__version__,
            "next_action":"use measured cost and startup evidence to decide an optimized but equivalent implementation before any full N32 or N48/N64 run"
        }
        manifest["artifact_hashes"]={str(p):sha(p) for p in OUT.iterdir() if p.is_file()}
        write(OUT/"manifest.json",manifest)
        print(json.dumps(manifest,indent=2))
    except Exception as exc:
        write(OUT/"failure.json",{"error":repr(exc),"completed_steps":len(history),"history":history})
        raise

if __name__ == "__main__": main()
