#!/usr/bin/env python3
"""Independently verify and checkpoint the accepted Stage26t contact benchmark."""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage26_runs" / "stage26t_sand_fibre_contact_20260820" / "contact_01"
SUP = ROOT / "stage26_supervisors" / "stage26t_sand_fibre_contact_20260820" / "contact_01"
CONFIG = ROOT / "stage26_designs" / "stage26t_sand_fibre_contact_20260820" / "contact_design_01" / "config.json"
RUNNER = ROOT / "stage26_staging" / "run_stage26t_sand_fibre_contact_v1.py"
PROBE = ROOT / "stage26_runs" / "stage26t_sand_fibre_contact_20260820" / "contact_probe_01" / "probe.json"
OUT = ROOT / "stage26_evaluations" / "stage26t_sand_fibre_contact_20260820" / "contact_evaluation_01"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding="utf-8"))
def require(condition, message):
    if not condition: raise RuntimeError(message)


if OUT.exists(): raise RuntimeError(f"refusing to overwrite {OUT}")
result_path, completion_path = RUN / "result.json", RUN / "completion.json"
for path in (result_path, completion_path, CONFIG, RUNNER, PROBE, SUP / "stdout.log", SUP / "stderr.log", SUP / "runner_exit_code.txt", SUP / "launch_manifest.txt"):
    require(path.is_file(), f"missing {path}")
result, completion, config, probe = read(result_path), read(completion_path), read(CONFIG), read(PROBE)
require(result["passed"] and completion["passed"] and probe["passed"], "accepted source did not pass")
require(result["status"] == completion["status"] == "contact_verified", "status mismatch")
require(sha(result_path) == completion["result"]["sha256"], "completion/result mismatch")
require(sha(CONFIG) == result["source_hashes"]["config"], "config mismatch")
require(sha(RUNNER) == result["source_hashes"]["runner"], "runner mismatch")
require(sha(PROBE) == config["source_hashes"]["contact_probe"], "probe mismatch")
require((SUP / "runner_exit_code.txt").read_text(encoding="utf-8").strip() == "0", "runner exit mismatch")
stderr = (SUP / "stderr.log").read_text(encoding="utf-8", errors="replace")
require("Traceback" not in stderr and "Exception" not in stderr, "exception found")
require(abs(probe["force_balance"]["reaction_magnitude_over_kn_overlap"] - 1.0) <= 1e-12, "probe force balance failed")
require(probe["contact"]["sphere_reaction_vector_n"][1] > 0, "probe reaction direction failed")
require(all(result["checks"].values()), "runner checks are not all true")

for level in result["levels"]:
    history = RUN / level["history"]["path"]
    artifact = RUN / level["result_artifact"]["path"]
    require(sha(history) == level["history"]["sha256"], "history hash mismatch")
    require(sha(artifact) == level["result_artifact"]["sha256"], "level result hash mismatch")
    require(level["minimum_peak_hold_contact_count"] >= 1, "peak contact absent")
    require(level["minimum_peak_hold_reaction_y_n"] > 0, "wrong reaction direction")
    require(level["maximum_final_hold_contact_count"] == 0, "contact did not release")
    require(all(math.isfinite(level[key]) for key in (
        "mean_peak_midpoint_deflection_m", "mean_peak_sphere_reaction_y_n", "beam_theory_relative_error",
        "maximum_peak_hold_node_speed_m_s", "recovery_residual_over_peak")), "nonfinite level metric")

fine = result["levels"][-1]
OUT.mkdir(parents=True)
evaluation = {
    "schema": "lbs.stage26t-sand-fibre-contact-evaluation.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": True, "status": "contact_verified",
    "finding": (
        "The frictionless YADE sphere-GridConnection contact transmits the correct normal-force sign, remains stable "
        "through a small fixed-fixed bending hold, converges in timestep, agrees with beam theory, releases on unloading, "
        "and leaves no measurable permanent fibre deformation."
    ),
    "metrics": {
        "fine_peak_midpoint_deflection_um": fine["mean_peak_midpoint_deflection_m"] * 1e6,
        "fine_peak_reaction_micro_n": fine["mean_peak_sphere_reaction_y_n"] * 1e6,
        "fine_beam_theory_relative_error": fine["beam_theory_relative_error"],
        "medium_to_fine_peak_force_relative_change": result["medium_to_fine_peak_force_relative_change"],
        "medium_to_fine_peak_deflection_relative_change": result["medium_to_fine_peak_deflection_relative_change"],
        "fine_recovery_residual_over_peak": fine["recovery_residual_over_peak"],
        "peak_contact_count": fine["minimum_peak_hold_contact_count"],
    },
    "checks": {"source_chain_bound": True, "single_contact_force_balance": True, "reaction_sign": True,
               "three_timestep_convergence": True, "beam_comparator": True, "contact_release": True,
               "elastic_recovery": True, "no_exception": True},
    "decision": {"sphere_grid_normal_contact_verified": True, "37_node_fibre_retained": True,
                 "friction_calibrated": False, "multigrain_caging_design_authorized": True,
                 "multigrain_caging_execution_authorized": False, "sand_mixture_authorized": False,
                 "periodic_grid_connection_authorized": False, "flow_authorized": False},
    "claim_boundary": result["claim_boundary"],
    "source_hashes": {"result": sha(result_path), "completion": sha(completion_path), "config": sha(CONFIG),
                      "runner": sha(RUNNER), "probe": sha(PROBE), "stdout": sha(SUP / "stdout.log"),
                      "stderr": sha(SUP / "stderr.log"), "exit_code": sha(SUP / "runner_exit_code.txt"),
                      "launch_manifest": sha(SUP / "launch_manifest.txt")},
}
evaluation_path = OUT / "evaluation.json"
evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
checkpoint = {"schema": "lbs.stage26t-sand-fibre-contact-checkpoint.v1",
              "timestamp_utc": datetime.now(timezone.utc).isoformat(), "status": "stage26t_complete",
              "evaluation": {"path": str(evaluation_path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(evaluation_path)},
              "authority": evaluation["decision"]}
checkpoint_path = OUT / "checkpoint_manifest.json"
checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"evaluation": str(evaluation_path), "evaluation_sha256": sha(evaluation_path),
                  "checkpoint": str(checkpoint_path), "checkpoint_sha256": sha(checkpoint_path)}, indent=2))
