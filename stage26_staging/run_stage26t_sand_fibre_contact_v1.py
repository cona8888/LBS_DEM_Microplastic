#!/usr/bin/env python3
"""Run Stage26t sphere-on-flexible-fibre contact verification at three timesteps."""

from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade import utils
from yade.gridpfacet import gridConnection, gridNode

CONFIG_PATH = os.environ["STAGE26T_CONFIG"]
OUTPUT = os.environ["STAGE26T_OUTPUT"]
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
RUNNER_PATH = "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26t_sand_fibre_contact_v1.py"
if sha256(RUNNER_PATH) != CONFIG["source_hashes"]["runner"]:
    raise RuntimeError("runner hash mismatch")

L = float(CONFIG["fibre"]["length_m"])
D = float(CONFIG["fibre"]["diameter_m"])
RF = 0.5 * D
E = float(CONFIG["fibre"]["young_pa"])
I_SECOND = math.pi * D ** 4 / 64.0
K_BEAM = 192.0 * E * I_SECOND / L ** 3
RS = 0.5 * float(CONFIG["sand"]["diameter_m"])
NODE_COUNT = int(CONFIG["fibre"]["node_count"])

SPHERE_ID = -1
SPHERE_INITIAL_Y = 0.0
PEAK_TRAVEL = float(CONFIG["loading"]["peak_sphere_travel_m"])
LOAD_DURATION = float(CONFIG["loading"]["load_duration_s"])
PEAK_HOLD_DURATION = float(CONFIG["loading"]["peak_hold_duration_s"])
UNLOAD_DURATION = float(CONFIG["loading"]["unload_duration_s"])
FINAL_HOLD_DURATION = float(CONFIG["loading"]["final_hold_duration_s"])
T1 = LOAD_DURATION
T2 = T1 + PEAK_HOLD_DURATION
T3 = T2 + UNLOAD_DURATION
T4 = T3 + FINAL_HOLD_DURATION


def trajectory(t):
    if t <= T1:
        return PEAK_TRAVEL * t / T1, PEAK_TRAVEL / T1
    if t <= T2:
        return PEAK_TRAVEL, 0.0
    if t <= T3:
        fraction = (t - T2) / UNLOAD_DURATION
        return PEAK_TRAVEL * (1.0 - fraction), -PEAK_TRAVEL / UNLOAD_DURATION
    return 0.0, 0.0


def prescribe_sphere():
    travel, downward_speed = trajectory(float(O.time))
    body = O.bodies[SPHERE_ID]
    body.state.pos = Vector3(0.5 * L, SPHERE_INITIAL_Y - travel, 0.0)
    body.state.vel = Vector3(0.0, -downward_speed, 0.0)
    body.state.angVel = Vector3.Zero


def norm3(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


def phase(t):
    if t <= T1:
        return "load"
    if t <= T2:
        return "peak_hold"
    if t <= T3:
        return "unload"
    return "final_hold"


def sphere_contacts(connection_ids):
    connection_set = set(connection_ids)
    contacts = []
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        if (first == SPHERE_ID and second in connection_set) or (second == SPHERE_ID and first in connection_set):
            contacts.append(interaction)
    return contacts


def run_level(safety_factor):
    global SPHERE_ID, SPHERE_INITIAL_Y
    O.reset()
    internal = O.materials.append(CohFrictMat(
        young=E, poisson=float(CONFIG["fibre"]["poisson"]), density=float(CONFIG["fibre"]["density_kg_m3"]),
        frictionAngle=0.0, normalCohesion=1.0e20, shearCohesion=1.0e20,
        momentRotationLaw=True, label="fibreInternal"))
    external = O.materials.append(FrictMat(
        young=float(CONFIG["contact"]["young_pa"]), poisson=float(CONFIG["contact"]["poisson"]),
        density=float(CONFIG["fibre"]["density_kg_m3"]), frictionAngle=0.0, label="fibreExternal"))
    sand = O.materials.append(FrictMat(
        young=float(CONFIG["contact"]["young_pa"]), poisson=float(CONFIG["contact"]["poisson"]),
        density=float(CONFIG["sand"]["density_kg_m3"]), frictionAngle=0.0, label="sand"))
    O.engines = [
        ForceResetter(),
        PyRunner(iterPeriod=1, command="prescribe_sphere()"),
        InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_GridConnection_Aabb()]),
        InteractionLoop(
            [Ig2_GridNode_GridNode_GridNodeGeom6D(), Ig2_Sphere_GridConnection_ScGridCoGeom()],
            [Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionNow=True, setCohesionOnNewContacts=True),
             Ip2_FrictMat_FrictMat_FrictPhys()],
            [Law2_ScGeom6D_CohFrictPhys_CohesionMoment(), Law2_ScGridCoGeom_FrictPhys_CundallStrack()],
        ),
        NewtonIntegrator(gravity=(0.0, 0.0, 0.0), damping=float(CONFIG["numerics"]["newton_damping"])),
    ]
    segment = L / float(NODE_COUNT - 1)
    nodes = []
    for index in range(NODE_COUNT):
        nodes.append(O.bodies.append(gridNode(
            [index * segment, 0.0, 0.0], RF, fixed=(index in (0, NODE_COUNT - 1)),
            wire=False, color=(0.85, 0.12, 0.10), material=internal)))
    connections = []
    for left, right in zip(nodes[:-1], nodes[1:]):
        connections.append(O.bodies.append(gridConnection(
            left, right, RF, wire=False, color=(0.85, 0.12, 0.10), material=external)))
    SPHERE_INITIAL_Y = RS + RF + float(CONFIG["loading"]["initial_clearance_m"])
    SPHERE_ID = O.bodies.append(utils.sphere(
        (0.5 * L, SPHERE_INITIAL_Y, 0.0), RS, fixed=True, color=(0.70, 0.66, 0.54), material=sand))
    initial_endpoints = [tuple(float(v) for v in O.bodies[nodes[i]].state.pos) for i in (0, -1)]
    initial_midpoint_y = float(O.bodies[nodes[NODE_COUNT // 2]].state.pos[1])
    O.dt = 1.0e-10
    O.step()
    masses = [float(O.bodies[body_id].state.mass) for body_id in nodes if O.bodies[body_id].state.mass > 0]
    axial_kn = E * math.pi * RF ** 2 / segment
    transverse_kn = 12.0 * E * I_SECOND / segment ** 3
    O.dt = float(safety_factor) * math.sqrt(min(masses) / max(axial_kn, transverse_kn))
    sample_steps = max(1, int(math.ceil(float(CONFIG["outputs"]["sample_duration_s"]) / O.dt)))
    maximum_steps = int(math.ceil(T4 / O.dt))
    rows = []
    peak_snapshot = None
    while O.iter < maximum_steps:
        O.run(min(sample_steps, maximum_steps - int(O.iter)), True)
        t = float(O.time)
        mid = O.bodies[nodes[NODE_COUNT // 2]]
        midpoint_deflection = max(0.0, initial_midpoint_y - float(mid.state.pos[1]))
        contacts = sphere_contacts(connections)
        reaction = [float(v) for v in O.forces.f(SPHERE_ID)]
        penetrations = [max(0.0, float(i.geom.penetrationDepth)) for i in contacts]
        endpoint_displacement = max(
            norm3(Vector3(O.bodies[nodes[index]].state.pos) - Vector3(initial_endpoints[j]))
            for j, index in enumerate((0, -1)))
        row = {
            "iteration": int(O.iter), "time_s": t, "phase": phase(t),
            "sphere_travel_m": SPHERE_INITIAL_Y - float(O.bodies[SPHERE_ID].state.pos[1]),
            "midpoint_deflection_m": midpoint_deflection,
            "sphere_reaction_y_n": reaction[1],
            "sphere_grid_real_contact_count": len(contacts),
            "maximum_contact_penetration_m": max(penetrations) if penetrations else 0.0,
            "maximum_node_speed_m_s": max(norm3(O.bodies[body_id].state.vel) for body_id in nodes),
            "maximum_endpoint_displacement_m": endpoint_displacement,
        }
        rows.append(row)
        if peak_snapshot is None and t >= T2:
            peak_snapshot = [[float(x) for x in O.bodies[body_id].state.pos] for body_id in nodes]
        if not all(math.isfinite(float(row[key])) for key in (
            "sphere_travel_m", "midpoint_deflection_m", "sphere_reaction_y_n",
            "maximum_contact_penetration_m", "maximum_node_speed_m_s", "maximum_endpoint_displacement_m")):
            raise RuntimeError("nonfinite state at safety factor %s" % safety_factor)

    final_snapshot = [[float(x) for x in O.bodies[body_id].state.pos] for body_id in nodes]
    peak_rows = [row for row in rows if T2 - float(CONFIG["analysis"]["hold_average_window_s"]) <= row["time_s"] <= T2]
    final_rows = [row for row in rows if T4 - float(CONFIG["analysis"]["hold_average_window_s"]) <= row["time_s"] <= T4 + O.dt]
    if not peak_rows or not final_rows:
        raise RuntimeError("hold averaging window is empty")
    mean_peak_deflection = sum(row["midpoint_deflection_m"] for row in peak_rows) / len(peak_rows)
    mean_peak_reaction = sum(row["sphere_reaction_y_n"] for row in peak_rows) / len(peak_rows)
    mean_theory_force = K_BEAM * mean_peak_deflection
    mean_final_deflection = sum(row["midpoint_deflection_m"] for row in final_rows) / len(final_rows)
    history_path = os.path.join(OUTPUT, "dt_%0.2f_history.csv" % safety_factor)
    with open(history_path, "x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    level = {
        "time_step_safety_factor": safety_factor,
        "time_step_s": float(O.dt), "iterations": int(O.iter),
        "mean_peak_midpoint_deflection_m": mean_peak_deflection,
        "mean_peak_sphere_reaction_y_n": mean_peak_reaction,
        "beam_theory_force_from_measured_deflection_n": mean_theory_force,
        "beam_theory_relative_error": abs(mean_peak_reaction / mean_theory_force - 1.0),
        "minimum_peak_hold_contact_count": min(row["sphere_grid_real_contact_count"] for row in peak_rows),
        "minimum_peak_hold_reaction_y_n": min(row["sphere_reaction_y_n"] for row in peak_rows),
        "maximum_peak_hold_node_speed_m_s": max(row["maximum_node_speed_m_s"] for row in peak_rows),
        "maximum_endpoint_displacement_m": max(row["maximum_endpoint_displacement_m"] for row in rows),
        "mean_final_midpoint_deflection_m": mean_final_deflection,
        "maximum_final_hold_contact_count": max(row["sphere_grid_real_contact_count"] for row in final_rows),
        "recovery_residual_over_peak": mean_final_deflection / mean_peak_deflection,
        "peak_snapshot_node_positions_m": peak_snapshot,
        "final_snapshot_node_positions_m": final_snapshot,
        "history": {"path": os.path.basename(history_path), "sha256": sha256(history_path)},
    }
    level_path = os.path.join(OUTPUT, "dt_%0.2f_result.json" % safety_factor)
    with open(level_path, "x") as stream:
        json.dump(level, stream, indent=2, sort_keys=True); stream.write("\n")
    level["result_artifact"] = {"path": os.path.basename(level_path), "sha256": sha256(level_path)}
    return level


started = time.time()
levels = [run_level(float(value)) for value in CONFIG["numerics"]["time_step_safety_factors"]]
coarse, medium, fine = levels
force_change = abs(fine["mean_peak_sphere_reaction_y_n"] / medium["mean_peak_sphere_reaction_y_n"] - 1.0)
deflection_change = abs(fine["mean_peak_midpoint_deflection_m"] / medium["mean_peak_midpoint_deflection_m"] - 1.0)
gates = CONFIG["gates"]
checks = {
    "all_finite_and_complete": all(level["iterations"] > 0 for level in levels),
    "peak_contact_persistent": all(level["minimum_peak_hold_contact_count"] >= 1 for level in levels),
    "reaction_direction_correct": all(level["minimum_peak_hold_reaction_y_n"] > 0 for level in levels),
    "endpoints_fixed": all(level["maximum_endpoint_displacement_m"] <= float(gates["maximum_endpoint_displacement_m"]) for level in levels),
    "small_deflection": all(level["mean_peak_midpoint_deflection_m"] / L <= float(gates["maximum_peak_deflection_over_length"]) for level in levels),
    "peak_hold_quasi_static": all(level["maximum_peak_hold_node_speed_m_s"] <= float(gates["maximum_peak_hold_node_speed_m_s"]) for level in levels),
    "fine_beam_theory_agreement": fine["beam_theory_relative_error"] <= float(gates["maximum_fine_beam_theory_relative_error"]),
    "medium_to_fine_force_convergence": force_change <= float(gates["maximum_medium_to_fine_relative_change"]),
    "medium_to_fine_deflection_convergence": deflection_change <= float(gates["maximum_medium_to_fine_relative_change"]),
    "elastic_contact_release": all(level["maximum_final_hold_contact_count"] == 0 for level in levels),
    "elastic_shape_recovery": all(level["recovery_residual_over_peak"] <= float(gates["maximum_recovery_residual_over_peak"]) for level in levels),
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage26t-sand-fibre-contact-result.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed, "status": "contact_verified" if passed else "contact_not_qualified",
    "beam": {"second_moment_area_m4": I_SECOND, "fixed_fixed_midpoint_stiffness_n_per_m": K_BEAM},
    "levels": levels,
    "medium_to_fine_peak_force_relative_change": force_change,
    "medium_to_fine_peak_deflection_relative_change": deflection_change,
    "checks": checks, "elapsed_wall_s": time.time() - started,
    "source_hashes": {"config": sha256(CONFIG_PATH), "runner": sha256(RUNNER_PATH)},
    "authority": CONFIG["authority"], "claim_boundary": CONFIG["claim_boundary"],
}
result_path = os.path.join(OUTPUT, "result.json")
with open(result_path, "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
completion = {
    "schema": "lbs.stage26t-sand-fibre-contact-completion.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed, "status": result["status"], "checks": checks,
    "result": {"path": result_path, "sha256": sha256(result_path)}, "authority": CONFIG["authority"],
}
with open(os.path.join(OUTPUT, "completion.json"), "x") as stream:
    json.dump(completion, stream, indent=2, sort_keys=True); stream.write("\n")
print(json.dumps(completion, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 2)
