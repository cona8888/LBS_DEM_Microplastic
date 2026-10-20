"""Strict fixed-periodic-cell kinematic smoke with complete Cell history reset."""
from __future__ import print_function

import hashlib
import json
import math
import os

from yade import config


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def windows_to_wsl(path):
    path = str(path)
    if len(path) >= 3 and path[1:3] in (":\\", ":/"):
        return "/mnt/%s/%s" % (path[0].lower(), path[3:].replace("\\", "/"))
    return path


def matrix_rows(matrix):
    return [[float(matrix[i, j]) for j in range(3)] for i in range(3)]


config_path = os.path.abspath(os.environ["STAGE26R_SMOKE_CONFIG"])
output = os.path.abspath(os.environ["STAGE26R_SMOKE_OUTPUT"])
script_path = os.path.abspath(os.environ.get("STAGE26R_SMOKE_SCRIPT", __file__))
with open(config_path, "r") as stream:
    cfg = json.load(stream)
authority = cfg.get("authority", {})
if authority.get("zero_cell_history_smoke_authorized") is not True:
    raise RuntimeError("complete cell-history smoke is not authorized")
if authority.get("clean_radius_restoration_authorized") is not False:
    raise RuntimeError("smoke-only design unexpectedly authorizes restoration")
if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
    raise RuntimeError("YADE version mismatch")
if sha256(windows_to_wsl(cfg["sources"]["cell_api_probe"]["path"])) != cfg["sources"]["cell_api_probe"]["sha256"]:
    raise RuntimeError("cell API probe hash mismatch")
if os.path.exists(output):
    raise RuntimeError("immutable smoke output exists")
binding = cfg["sources"]["input_state"]
state_path = windows_to_wsl(binding["path"])
if sha256(state_path) != binding["sha256"]:
    raise RuntimeError("input state hash mismatch")

os.makedirs(output)
O.load(state_path)
controllers = [engine for engine in O.engines if engine.__class__.__name__ == "PeriTriaxController"]
if len(controllers) != 1:
    raise RuntimeError("expected one PeriTriaxController")
controller = controllers[0]
controller.dead = True

initial = [float(value) for value in O.cell.size]
loaded = {
    "velGrad": matrix_rows(O.cell.velGrad),
    "nextVelGrad": matrix_rows(O.cell.nextVelGrad),
    "prevVelGrad": matrix_rows(O.cell.prevVelGrad),
}
O.cell.velGrad = Matrix3.Zero
O.cell.nextVelGrad = Matrix3.Zero
O.cell.prevVelGrad = Matrix3.Zero
O.cell.velGradChanged = True
O.run(5000, True)

terminal = [float(value) for value in O.cell.size]
terminal_history = {
    "velGrad": matrix_rows(O.cell.velGrad),
    "nextVelGrad": matrix_rows(O.cell.nextVelGrad),
    "prevVelGrad": matrix_rows(O.cell.prevVelGrad),
}
change = max(abs(terminal[i] - initial[i]) / initial[i] for i in range(3))
zero_terminal = max(
    abs(value)
    for matrix in terminal_history.values()
    for row in matrix
    for value in row
) == 0.0
checks = {
    "periodic": bool(O.periodic),
    "controller_dead": bool(controller.dead),
    "loaded_history_was_nonzero": max(
        abs(value) for matrix in loaded.values() for row in matrix for value in row
    ) > 0.0,
    "terminal_cell_velocity_history_zero": zero_terminal,
    "cell_unchanged": change <= 1.0e-14,
    "finite": all(math.isfinite(value) for value in initial + terminal),
}
result = {
    "schema": "lbs.stage26r-fixed-periodic-cell-smoke.v2",
    "status": "fixed_cell_kinematics_verified" if all(checks.values()) else "fixed_cell_kinematics_not_verified",
    "passed": all(checks.values()),
    "checks": checks,
    "initial_cell_dimensions_m": initial,
    "terminal_cell_dimensions_m": terminal,
    "maximum_relative_cell_dimension_change": change,
    "loaded_cell_velocity_history": loaded,
    "terminal_cell_velocity_history": terminal_history,
    "steps": 5000,
    "claim_boundary": "Fixed-periodic-cell kinematic smoke only; no radius restoration, fibre, flow, or permeability result.",
    "sources": {
        "config": {"path": config_path, "sha256": sha256(config_path)},
        "runner": {"path": script_path, "sha256": sha256(script_path)},
        "cell_api_probe": cfg["sources"]["cell_api_probe"],
        "input_state": binding,
    },
    "authority": {
        "boundary_only_corrected_clean_rerun_authorized": all(checks.values()),
        "fibre_execution_authorized": False,
        "flow_execution_authorized": False,
        "permeability_claim_authorized": False,
    },
}
path = os.path.join(output, "result.json")
with open(path, "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
print("STAGE26R_FIXED_CELL_SMOKE=" + json.dumps(result, sort_keys=True), flush=True)
print("STAGE26R_FIXED_CELL_SMOKE_SHA256=" + sha256(path), flush=True)
raise SystemExit(0 if result["passed"] else 2)
