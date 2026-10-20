"""Strict fixed-cell smoke using one YADE synchronization step then exact restore."""
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


def matrix_copy(matrix):
    return Matrix3(*[float(matrix[i, j]) for i in range(3) for j in range(3)])


def matrix_rows(matrix):
    return [[float(matrix[i, j]) for j in range(3)] for i in range(3)]


config_path = os.path.abspath(os.environ["STAGE26R_SMOKE_CONFIG"])
output = os.path.abspath(os.environ["STAGE26R_SMOKE_OUTPUT"])
script_path = os.path.abspath(os.environ.get("STAGE26R_SMOKE_SCRIPT", __file__))
with open(config_path, "r") as stream:
    cfg = json.load(stream)
authority = cfg.get("authority", {})
if authority.get("synchronized_cell_restore_smoke_authorized") is not True:
    raise RuntimeError("synchronized cell-restore smoke is not authorized")
if authority.get("clean_radius_restoration_authorized") is not False:
    raise RuntimeError("smoke-only design unexpectedly authorizes restoration")
if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
    raise RuntimeError("YADE version mismatch")
for source in ("cell_api_probe", "cell_setter_probe", "fixed_cell_smoke_02", "fixed_cell_smoke_03_failure"):
    binding = cfg["sources"][source]
    if sha256(windows_to_wsl(binding["path"])) != binding["sha256"]:
        raise RuntimeError("source hash mismatch: " + source)
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

loaded_dimensions = [float(value) for value in O.cell.size]
loaded_hsize = matrix_copy(O.cell.hSize)
loaded_positions = {
    int(body.id): [float(value) for value in body.state.pos]
    for body in O.bodies
    if body is not None
}
loaded_vel_grad = matrix_rows(O.cell.velGrad)

# YADE 2022.01a applies velGrad assignments on the next Cell integration.
O.cell.velGrad = Matrix3.Zero
O.step()
synchronized_dimensions = [float(value) for value in O.cell.size]
synchronized_vel_grad = matrix_rows(O.cell.velGrad)
synchronized_prev_vel_grad = matrix_rows(O.cell.prevVelGrad)

# Restore the immutable input geometry after the one scheduling step.
O.cell.hSize = loaded_hsize
for body_id, position in loaded_positions.items():
    body = O.bodies[body_id]
    if body is not None:
        body.state.pos = Vector3(*position)
        body.state.vel = Vector3.Zero
        body.state.angVel = Vector3.Zero
restored_dimensions = [float(value) for value in O.cell.size]
O.run(5000, True)

terminal_dimensions = [float(value) for value in O.cell.size]
terminal_vel_grad = matrix_rows(O.cell.velGrad)
terminal_prev_vel_grad = matrix_rows(O.cell.prevVelGrad)
sync_change = max(abs(synchronized_dimensions[i] - loaded_dimensions[i]) / loaded_dimensions[i] for i in range(3))
restore_error = max(abs(restored_dimensions[i] - loaded_dimensions[i]) / loaded_dimensions[i] for i in range(3))
terminal_change = max(abs(terminal_dimensions[i] - loaded_dimensions[i]) / loaded_dimensions[i] for i in range(3))
terminal_position_error = max(
    (O.bodies[body_id].state.pos - Vector3(*position)).norm()
    for body_id, position in loaded_positions.items()
    if O.bodies[body_id] is not None
)
checks = {
    "periodic": bool(O.periodic),
    "controller_dead": bool(controller.dead),
    "loaded_velocity_gradient_was_nonzero": max(abs(value) for row in loaded_vel_grad for value in row) > 0.0,
    "synchronization_step_applied_pending_gradient": sync_change > 0.0,
    "synchronized_velocity_gradient_zero": max(abs(value) for row in synchronized_vel_grad for value in row) == 0.0,
    "synchronized_previous_velocity_gradient_zero": max(abs(value) for row in synchronized_prev_vel_grad for value in row) == 0.0,
    "exact_cell_restored_before_hold": restore_error <= 1.0e-15,
    "terminal_velocity_gradient_zero": max(abs(value) for row in terminal_vel_grad for value in row) == 0.0,
    "terminal_previous_velocity_gradient_zero": max(abs(value) for row in terminal_prev_vel_grad for value in row) == 0.0,
    "cell_unchanged_after_restore": terminal_change <= 1.0e-14,
    "finite": all(math.isfinite(value) for value in loaded_dimensions + terminal_dimensions),
}
result = {
    "schema": "lbs.stage26r-fixed-periodic-cell-smoke.v3",
    "status": "fixed_cell_kinematics_verified" if all(checks.values()) else "fixed_cell_kinematics_not_verified",
    "passed": all(checks.values()),
    "checks": checks,
    "loaded_cell_dimensions_m": loaded_dimensions,
    "synchronized_cell_dimensions_m": synchronized_dimensions,
    "restored_cell_dimensions_m": restored_dimensions,
    "terminal_cell_dimensions_m": terminal_dimensions,
    "synchronization_relative_cell_change": sync_change,
    "restore_relative_cell_error": restore_error,
    "terminal_relative_cell_change_from_loaded": terminal_change,
    "terminal_maximum_particle_position_change_m": terminal_position_error,
    "steps": {"synchronization": 1, "fixed_cell_hold": 5000},
    "claim_boundary": "Fixed-periodic-cell kinematic smoke only; no radius restoration, fibre, flow, or permeability result.",
    "sources": {
        "config": {"path": config_path, "sha256": sha256(config_path)},
        "runner": {"path": script_path, "sha256": sha256(script_path)},
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
