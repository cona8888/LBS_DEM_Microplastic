from __future__ import annotations

import ast
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import periodic_drag_reference_v1 as runner

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
CONTRACT = ROOT/"stage36_staging"/"STAGE36AF_PERIODIC_DRAG_RUNNER_CONTRACT.md"
SOURCE = ROOT/"stage36_staging"/"periodic_drag_reference_v1.py"
PARENT = ROOT/"stage36_evaluations"/"stage36ae_periodic_drag_comparator_20260909"/"qualification_01"/"qualification.json"
OUT = ROOT/"stage36_evaluations"/"stage36af_periodic_drag_runner_audit_20260909"/"audit_01"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    if OUT.exists(): raise SystemExit(f"fail closed: output exists: {OUT}")
    parent = json.loads(PARENT.read_text())
    tree = ast.parse(SOURCE.read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    forbidden = {"subprocess", "Popen", "system", "remove", "unlink", "rmtree"}
    names = {getattr(n.func, "id", getattr(n.func, "attr", "")) for n in calls}
    init = runner.initialize(32)
    nominal = {str(n): runner.nominal_parameters(n) for n in (32,48,64)}
    row_sums = np.asarray(init["matrix"].sum(axis=1)).ravel()
    checks = {
        "parent_qualified_and_unrun": parent["passed"] and not parent["flow_executed"],
        "source_parses": True,
        "no_process_or_destructive_calls": not bool(names & forbidden),
        "n32_equilibrium_positive": bool(np.all(init["f"] > 0)),
        "n32_mass_exact": abs(float(init["f"].sum())-32**3) <= 1e-12*32**3,
        "surface_kernel_partition": float(np.max(np.abs(row_sums-1))) <= 1e-14,
        "frozen_grid_parameters_present": set(nominal) == {"32","48","64"},
        "reynolds_reconstructed": all(abs(2*(n/8)*nominal[str(n)]["target_u_lu"]/.1-.05) < 1e-15 for n in (32,48,64)),
        "five_viscous_windows": all(nominal[str(n)]["minimum_post_start_windows"] == 5 for n in (32,48,64)),
        "no_flow_advanced": True,
    }
    record = {"stage":"Stage36AF", "timestamp_utc":datetime.now(timezone.utc).isoformat(),
              "status":"runner_static_audit_passed_driven_flow_not_run" if all(checks.values()) else "failed_closed",
              "checks":checks, "n32_operator_audit":{"marker_count":init["marker_count"],"matrix_shape":init["matrix"].shape,
              "matrix_nnz":int(init["matrix"].nnz),"max_partition_error":float(np.max(np.abs(row_sums-1)))},
              "nominal_parameters":nominal, "driven_steps_executed":0, "passed":all(checks.values()),
              "input_hashes":{"contract":sha(CONTRACT),"runner":sha(SOURCE),"stage36ae_parent":sha(PARENT)},
              "python":platform.python_version(),"numpy":np.__version__,
              "next_action":"run one explicitly authorized N32 diagnostic in a new immutable directory; do not launch N48/N64 concurrently"}
    OUT.mkdir(parents=True)
    (OUT/"audit.json").write_text(json.dumps(record,indent=2)+"\n")
    (OUT/"RESULTS.md").write_text(f"# Stage36AF runner audit\n\n- Status: `{record['status']}`\n- N32 marker operator: {init['marker_count']} markers, {init['matrix'].nnz} nonzeros\n- Maximum kernel partition error: {record['n32_operator_audit']['max_partition_error']:.3e}\n- Driven steps executed: 0\n- Next: one immutable N32 diagnostic only.\n")
    if not record["passed"]: raise SystemExit(2)

if __name__ == "__main__": main()
