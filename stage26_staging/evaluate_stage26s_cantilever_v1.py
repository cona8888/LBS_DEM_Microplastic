#!/usr/bin/env python3
"""Independently evaluate and checkpoint the accepted Stage26s cantilever."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage26_runs" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_03"
SUP = ROOT / "stage26_supervisors" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_03"
CONFIG = ROOT / "stage26_designs" / "stage26s_flexible_fibre_cantilever_20260819" / "clean_design_03" / "config.json"
RUNNER = ROOT / "stage26_staging" / "run_stage26s_flexible_fibre_cantilever_v3.py"
PROBE = ROOT / "stage26_runs" / "stage26s_flexible_fibre_cantilever_20260819" / "grid_connection_probe_01" / "probe.json"
OUT = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_evaluation_03"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite {OUT}")
result_path = RUN / "result.json"
completion_path = RUN / "completion.json"
for path in (result_path, completion_path, CONFIG, RUNNER, PROBE, SUP / "stdout.log", SUP / "stderr.log", SUP / "runner_exit_code.txt", SUP / "launch_manifest.txt"):
    require(path.is_file(), f"missing {path}")

result = read(result_path)
completion = read(completion_path)
config = read(CONFIG)
probe = read(PROBE)
require(result["passed"] and completion["passed"], "benchmark did not pass")
require(result["status"] == completion["status"] == "cantilever_verified", "status mismatch")
require(sha(result_path) == completion["result"]["sha256"], "completion/result hash mismatch")
require(sha(CONFIG) == result["source_hashes"]["config"], "config hash mismatch")
require(sha(RUNNER) == result["source_hashes"]["runner"], "runner hash mismatch")
require(sha(PROBE) == config["source_hashes"]["grid_connection_probe"], "probe hash mismatch")
require((SUP / "runner_exit_code.txt").read_text(encoding="utf-8").strip() == "0", "runner exit was not zero")
stderr = (SUP / "stderr.log").read_text(encoding="utf-8", errors="replace")
require("Traceback" not in stderr and "Exception" not in stderr, "software exception found")

probe_kn = probe["physics"]["kn"]
probe_kr = probe["physics"]["kr"]
require(abs(probe_kn / probe["reference_stiffness"]["EA_over_L_n_per_m"] - 1.0) <= 1.0e-12, "probe kn mapping failed")
require(abs(probe_kr / probe["reference_stiffness"]["EI_over_L_n_m_per_rad"] - 1.0) <= 1.0e-12, "probe kr mapping failed")

for mesh in result["meshes"]:
    history = RUN / mesh["history"]["path"]
    artifact = RUN / mesh["result_artifact"]["path"]
    require(sha(history) == mesh["history"]["sha256"], f"history hash mismatch for N={mesh['node_count']}")
    require(sha(artifact) == mesh["result_artifact"]["sha256"], f"mesh result hash mismatch for N={mesh['node_count']}")
    require(mesh["equilibrium_reached"], f"N={mesh['node_count']} did not equilibrate")
    require(mesh["clamp_displacement_m"] <= config["gates"]["maximum_clamp_displacement_m"], "clamp moved")
    require(mesh["terminal_deflection_over_length"] <= config["gates"]["maximum_terminal_deflection_over_length"], "large-deflection gate failed")
    require(all(math.isfinite(mesh[key]) for key in ("terminal_tip_displacement_m", "analytical_relative_error", "terminal_tip_speed_m_s", "terminal_tip_force_residual_over_applied")), "nonfinite mesh result")
require(result["mesh_37_to_73_relative_change"] <= config["gates"]["maximum_37_to_73_relative_change"], "mesh gate failed")
require(result["meshes"][-1]["analytical_relative_error"] <= config["gates"]["maximum_73_node_analytical_relative_error"], "analytical gate failed")
require(all(result["checks"].values()), "not all runner checks passed")

OUT.mkdir(parents=True)
evaluation = {
    "schema": "lbs.stage26s-flexible-fibre-cantilever-evaluation.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True,
    "status": "cantilever_verified",
    "finding": (
        "YADE GridConnection bending stiffness is bound to EI/Le, and the nonperiodic 0.9 mm by 0.1 mm chain reproduces "
        "the small-deflection cantilever solution at 19, 37, and 73 nodes with convergent response."
    ),
    "metrics": {
        "analytical_tip_displacement_um": result["analytical"]["target_tip_displacement_m"] * 1.0e6,
        "mesh_analytical_relative_errors": {str(m["node_count"]): m["analytical_relative_error"] for m in result["meshes"]},
        "mesh_37_to_73_relative_change": result["mesh_37_to_73_relative_change"],
        "tip_force_micro_n": result["inputs"]["tip_force_n"] * 1.0e6,
        "elapsed_wall_s": result["elapsed_wall_s"],
    },
    "checks": {
        "complete_source_chain": True,
        "native_EA_and_EI_mapping": True,
        "three_meshes_equilibrated": True,
        "small_deflection": True,
        "analytical_agreement": True,
        "mesh_convergence": True,
        "no_exception": True,
    },
    "decision": {
        "flexible_fibre_code_model_verified": True,
        "minimum_verified_mesh_node_count": 19,
        "recommended_future_node_count": 37,
        "nominal_young_modulus_calibrated": False,
        "sand_fibre_contact_verified": False,
        "periodic_grid_connection_verified": False,
        "sand_mixture_authorized": False,
        "flow_authorized": False,
        "next_design_gate": "nonperiodic single-fibre/sand-contact benchmark and boundary strategy",
    },
    "claim_boundary": result["claim_boundary"],
    "source_hashes": {
        "result": sha(result_path),
        "completion": sha(completion_path),
        "config": sha(CONFIG),
        "runner": sha(RUNNER),
        "probe": sha(PROBE),
        "stdout": sha(SUP / "stdout.log"),
        "stderr": sha(SUP / "stderr.log"),
        "exit_code": sha(SUP / "runner_exit_code.txt"),
        "launch_manifest": sha(SUP / "launch_manifest.txt"),
    },
}
evaluation_path = OUT / "evaluation.json"
evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
checkpoint = {
    "schema": "lbs.stage26s-flexible-fibre-cantilever-checkpoint.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "status": "stage26s_complete",
    "evaluation": {"path": str(evaluation_path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(evaluation_path)},
    "authority": evaluation["decision"],
}
checkpoint_path = OUT / "checkpoint_manifest.json"
checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"evaluation": str(evaluation_path), "evaluation_sha256": sha(evaluation_path), "checkpoint": str(checkpoint_path), "checkpoint_sha256": sha(checkpoint_path)}, indent=2))
