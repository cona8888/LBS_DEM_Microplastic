#!/usr/bin/env python3
"""Run the immutable Stage26s three-mesh cantilever verification in YADE."""

from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade.gridpfacet import gridConnection, gridNode


CONFIG_PATH = os.environ["STAGE26S_CONFIG"]
OUTPUT = os.environ["STAGE26S_OUTPUT"]
if os.path.exists(OUTPUT):
    raise RuntimeError("refusing to overwrite %s" % OUTPUT)
os.makedirs(OUTPUT)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


with open(CONFIG_PATH, "r") as stream:
    CONFIG = json.load(stream)

HERE = "/mnt/c/MATDEM_MICROPLASTIC"
RUNNER_PATH = HERE + "/stage26_staging/run_stage26s_flexible_fibre_cantilever_v3.py"
if sha256(CONFIG_PATH) == "":
    raise RuntimeError("unreachable hash failure")
if sha256(RUNNER_PATH) != CONFIG["source_hashes"]["runner"]:
    raise RuntimeError("runner hash mismatch")

L = float(CONFIG["geometry"]["length_m"])
D = float(CONFIG["geometry"]["diameter_m"])
R = 0.5 * D
E = float(CONFIG["material"]["young_pa"])
NU = float(CONFIG["material"]["poisson"])
RHO = float(CONFIG["material"]["density_kg_m3"])
I_SECOND = math.pi * D ** 4 / 64.0
TARGET_DELTA = float(CONFIG["loading"]["target_tip_deflection_over_length"]) * L
TIP_FORCE = 3.0 * E * I_SECOND * TARGET_DELTA / L ** 3

CURRENT_TIP = -1
CURRENT_FORCE = TIP_FORCE
RAMP_STEPS = 1


def apply_tip_force():
    fraction = min(1.0, max(0.0, float(O.iter + 1) / float(RAMP_STEPS)))
    O.forces.addF(CURRENT_TIP, Vector3(0.0, -CURRENT_FORCE * fraction, 0.0), permanent=False)


def norm3(v):
    return math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2)


def run_mesh(node_count):
    global CURRENT_TIP, RAMP_STEPS
    O.reset()
    material = O.materials.append(CohFrictMat(
        young=E,
        poisson=NU,
        density=RHO,
        frictionAngle=0.0,
        normalCohesion=1.0e20,
        shearCohesion=1.0e20,
        momentRotationLaw=True,
        label="fibreInternal",
    ))
    O.engines = [
        ForceResetter(),
        PyRunner(iterPeriod=1, command="apply_tip_force()"),
        InsertionSortCollider([Bo1_GridConnection_Aabb()]),
        InteractionLoop(
            [Ig2_GridNode_GridNode_GridNodeGeom6D()],
            [Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionNow=True, setCohesionOnNewContacts=True)],
            [Law2_ScGeom6D_CohFrictPhys_CohesionMoment()],
        ),
        NewtonIntegrator(gravity=(0.0, 0.0, 0.0), damping=float(CONFIG["numerics"]["newton_damping"])),
    ]
    node_ids = []
    segment = L / float(node_count - 1)
    for index in range(node_count):
        node_ids.append(O.bodies.append(gridNode(
            [index * segment, 0.0, 0.0], R, wire=False, fixed=(index == 0), material=material
        )))
    connection_ids = []
    for left, right in zip(node_ids[:-1], node_ids[1:]):
        connection_ids.append(O.bodies.append(gridConnection(left, right, R, material=material)))
    CURRENT_TIP = node_ids[-1]
    clamp_initial = tuple(float(x) for x in O.bodies[node_ids[0]].state.pos)
    tip_initial = tuple(float(x) for x in O.bodies[CURRENT_TIP].state.pos)

    O.step()
    masses = [float(O.bodies[body_id].state.mass) for body_id in node_ids if O.bodies[body_id].state.mass > 0]
    if not masses:
        raise RuntimeError("grid-node masses were not assigned")
    axial_kn = E * math.pi * R ** 2 / segment
    transverse_kn = 12.0 * E * I_SECOND / segment ** 3
    controlling_kn = max(axial_kn, transverse_kn)
    O.dt = float(CONFIG["numerics"]["time_step_safety_factor"]) * math.sqrt(min(masses) / controlling_kn)
    RAMP_STEPS = max(1, int(math.ceil(float(CONFIG["loading"]["ramp_duration_s"]) / O.dt)))

    block = max(1, int(math.ceil(float(CONFIG["loading"]["settle_block_duration_s"]) / O.dt)))
    maximum = max(RAMP_STEPS + block, int(math.ceil(float(CONFIG["loading"]["maximum_duration_s"]) / O.dt)))
    required = int(CONFIG["numerics"]["required_consecutive_equilibrium_blocks"])
    rows = []
    consecutive = 0
    while O.iter < maximum:
        O.run(block, True)
        tip = O.bodies[CURRENT_TIP]
        displacement = float(tip.state.pos[1] - tip_initial[1])
        tip_speed = norm3(tip.state.vel)
        residual = norm3(O.forces.f(CURRENT_TIP)) / TIP_FORCE
        max_node_speed = max(norm3(O.bodies[body_id].state.vel) for body_id in node_ids)
        row = {
            "iteration": int(O.iter),
            "time_s": float(O.time),
            "tip_displacement_m": displacement,
            "tip_speed_m_s": tip_speed,
            "maximum_node_speed_m_s": max_node_speed,
            "tip_force_residual_over_applied": residual,
        }
        rows.append(row)
        equilibrium = (
            O.iter >= RAMP_STEPS
            and tip_speed <= float(CONFIG["gates"]["maximum_tip_speed_m_s"])
            and residual <= float(CONFIG["gates"]["maximum_tip_force_residual_over_applied"])
        )
        consecutive = consecutive + 1 if equilibrium else 0
        if consecutive >= required:
            break

    terminal_tip = O.bodies[CURRENT_TIP]
    terminal_delta = abs(float(terminal_tip.state.pos[1] - tip_initial[1]))
    clamp_displacement = norm3(Vector3(O.bodies[node_ids[0]].state.pos) - Vector3(clamp_initial))
    history_path = os.path.join(OUTPUT, "mesh_%03d_history.csv" % node_count)
    with open(history_path, "w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "node_count": node_count,
        "segment_count": node_count - 1,
        "segment_length_m": segment,
        "time_step_s": float(O.dt),
        "axial_stiffness_n_per_m": axial_kn,
        "transverse_stiffness_n_per_m": transverse_kn,
        "controlling_stiffness_n_per_m": controlling_kn,
        "ramp_steps": RAMP_STEPS,
        "settle_block_steps": block,
        "maximum_steps": maximum,
        "iterations": int(O.iter),
        "equilibrium_reached": consecutive >= required,
        "terminal_tip_displacement_m": terminal_delta,
        "analytical_tip_displacement_m": TARGET_DELTA,
        "analytical_relative_error": abs(terminal_delta / TARGET_DELTA - 1.0),
        "terminal_deflection_over_length": terminal_delta / L,
        "terminal_tip_speed_m_s": norm3(terminal_tip.state.vel),
        "terminal_maximum_node_speed_m_s": max(norm3(O.bodies[body_id].state.vel) for body_id in node_ids),
        "terminal_tip_force_residual_over_applied": norm3(O.forces.f(CURRENT_TIP)) / TIP_FORCE,
        "clamp_displacement_m": clamp_displacement,
        "history": {"path": os.path.basename(history_path), "sha256": sha256(history_path)},
    }
    result_path = os.path.join(OUTPUT, "mesh_%03d_result.json" % node_count)
    with open(result_path, "w") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    result["result_artifact"] = {"path": os.path.basename(result_path), "sha256": sha256(result_path)}
    return result


started = time.time()
meshes = [run_mesh(int(item["node_count"])) for item in CONFIG["meshes"]]
by_nodes = {item["node_count"]: item for item in meshes}
change_37_73 = abs(by_nodes[73]["terminal_tip_displacement_m"] / by_nodes[37]["terminal_tip_displacement_m"] - 1.0)
checks = {
    "all_equilibrated": all(item["equilibrium_reached"] for item in meshes),
    "all_finite": all(math.isfinite(item[key]) for item in meshes for key in (
        "terminal_tip_displacement_m", "analytical_relative_error", "terminal_tip_speed_m_s",
        "terminal_tip_force_residual_over_applied", "clamp_displacement_m"
    )),
    "clamp_fixed": all(item["clamp_displacement_m"] <= float(CONFIG["gates"]["maximum_clamp_displacement_m"]) for item in meshes),
    "small_deflection": all(item["terminal_deflection_over_length"] <= float(CONFIG["gates"]["maximum_terminal_deflection_over_length"]) for item in meshes),
    "mesh_convergence_37_to_73": change_37_73 <= float(CONFIG["gates"]["maximum_37_to_73_relative_change"]),
    "analytical_agreement_73": by_nodes[73]["analytical_relative_error"] <= float(CONFIG["gates"]["maximum_73_node_analytical_relative_error"]),
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage26s-flexible-fibre-cantilever-result.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "status": "cantilever_verified" if passed else "cantilever_not_qualified",
    "inputs": {"length_m": L, "diameter_m": D, "young_pa": E, "density_kg_m3": RHO, "tip_force_n": TIP_FORCE},
    "analytical": {"second_moment_area_m4": I_SECOND, "target_tip_displacement_m": TARGET_DELTA, "formula": "F*L^3/(3*E*I)"},
    "meshes": meshes,
    "mesh_37_to_73_relative_change": change_37_73,
    "checks": checks,
    "elapsed_wall_s": time.time() - started,
    "source_hashes": {"config": sha256(CONFIG_PATH), "runner": sha256(RUNNER_PATH)},
    "authority": CONFIG["authority"],
    "claim_boundary": CONFIG["claim_boundary"],
}
result_path = os.path.join(OUTPUT, "result.json")
with open(result_path, "w") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
completion = {
    "schema": "lbs.stage26s-flexible-fibre-cantilever-completion.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "status": result["status"],
    "checks": checks,
    "result": {"path": result_path, "sha256": sha256(result_path)},
    "authority": CONFIG["authority"],
}
with open(os.path.join(OUTPUT, "completion.json"), "w") as stream:
    json.dump(completion, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(completion, indent=2, sort_keys=True))
O.pause()
raise SystemExit(0 if passed else 2)
