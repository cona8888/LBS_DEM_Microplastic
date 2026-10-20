#!/usr/bin/env python3
"""Run paired flexible-fibre paths in the fixed accepted Stage26o sand geometry."""

from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade.gridpfacet import gridConnection, gridNode

CONFIG_PATH = os.environ["STAGE26V_CONFIG"]
OUTPUT = os.environ["STAGE26V_OUTPUT"]
RUNNER = "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26v_fixed_sand_flexible_pilot_v1.py"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm3(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


def dot3(a, b):
    return sum(float(a[k]) * float(b[k]) for k in range(3))


if os.path.exists(OUTPUT):
    raise RuntimeError("refusing to overwrite %s" % OUTPUT)
os.makedirs(OUTPUT)
with open(CONFIG_PATH) as stream:
    CONFIG = json.load(stream)
if CONFIG.get("status") != "authorized_stage26v_fixed_sand_flexible_pilot":
    raise RuntimeError("configuration is not authorized")
if sha(RUNNER) != CONFIG["source_hashes"]["runner"] or sha(CONFIG["source_state"]) != CONFIG["source_hashes"]["source_state"]:
    raise RuntimeError("runner or source-state hash mismatch")

RF = 0.5 * float(CONFIG["fibre"]["diameter_m"])
LENGTH = float(CONFIG["fibre"]["length_m"])
COUNT = int(CONFIG["fibre"]["node_count"])
E = float(CONFIG["fibre"]["young_pa"])
I_SECOND = math.pi * (2.0 * RF) ** 4 / 64.0
HOLD = float(CONFIG["loading"]["zero_load_hold_duration_s"])
RAMP = float(CONFIG["loading"]["force_ramp_duration_s"])
PULL_DURATION = float(CONFIG["loading"]["pull_duration_s"])
FORCE = float(CONFIG["loading"]["axial_pull_force_n"])
TIP_ID = -1
PULL_DIRECTION = [1.0, 0.0, 0.0]
CASE_START_TIME = 0.0


def applied_force():
    elapsed = float(O.time) - CASE_START_TIME - HOLD
    if elapsed <= 0.0:
        return 0.0
    return FORCE * min(1.0, elapsed / RAMP)


def apply_pull():
    value = applied_force()
    if value > 0.0:
        O.forces.addF(TIP_ID, Vector3(*[value * component for component in PULL_DIRECTION]), permanent=False)


def run_case(case):
    global TIP_ID, PULL_DIRECTION, CASE_START_TIME
    O.load(CONFIG["source_state"])
    sand_ids = [int(body.id) for body in O.bodies if body is not None and body.shape.__class__.__name__ == "Sphere" and not body.isClumpMember]
    wall_ids = [int(body.id) for body in O.bodies if body is not None and body.shape.__class__.__name__ == "Box"]
    if len(sand_ids) != 216 or len(wall_ids) != 6 or O.periodic:
        raise RuntimeError("source-state geometry mismatch")
    sand_initial = {body_id: [float(x) for x in O.bodies[body_id].state.pos] for body_id in sand_ids}
    for body_id in sand_ids + wall_ids:
        O.bodies[body_id].state.blockedDOFs = "xyzXYZ"
        O.bodies[body_id].state.vel = Vector3.Zero
        O.bodies[body_id].state.angVel = Vector3.Zero
    internal = O.materials.append(CohFrictMat(
        young=E, poisson=float(CONFIG["fibre"]["poisson"]), density=float(CONFIG["fibre"]["density_kg_m3"]),
        frictionAngle=0.0, normalCohesion=1e20, shearCohesion=1e20, momentRotationLaw=True, label="stage26v_internal"))
    external = O.materials.append(FrictMat(
        young=float(CONFIG["contact"]["young_pa"]), poisson=float(CONFIG["contact"]["poisson"]),
        density=float(CONFIG["fibre"]["density_kg_m3"]), frictionAngle=0.0, label="stage26v_external"))
    O.engines = [
        ForceResetter(), PyRunner(iterPeriod=1, command="apply_pull()"),
        InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_Box_Aabb(), Bo1_GridConnection_Aabb()]),
        InteractionLoop(
            [Ig2_Sphere_Sphere_ScGeom(), Ig2_Box_Sphere_ScGeom(), Ig2_GridNode_GridNode_GridNodeGeom6D(), Ig2_Sphere_GridConnection_ScGridCoGeom()],
            [Ip2_FrictMat_FrictMat_FrictPhys(), Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionNow=True, setCohesionOnNewContacts=True)],
            [Law2_ScGeom_FrictPhys_CundallStrack(), Law2_ScGeom6D_CohFrictPhys_CohesionMoment(), Law2_ScGridCoGeom_FrictPhys_CundallStrack()]),
        NewtonIntegrator(gravity=(0, 0, 0), damping=float(CONFIG["numerics"]["newton_damping"])),
    ]
    rear = [float(x) for x in case["rear_m"]]
    tip = [float(x) for x in case["tip_m"]]
    PULL_DIRECTION = [float(x) for x in case["pull_direction"]]
    nodes = []
    for index in range(COUNT):
        fraction = index / float(COUNT - 1)
        position = [rear[k] + fraction * (tip[k] - rear[k]) for k in range(3)]
        nodes.append(int(O.bodies.append(gridNode(position, RF, fixed=False, wire=False, color=(0.85, 0.12, 0.10), material=internal))))
    connections = [int(O.bodies.append(gridConnection(left, right, RF, wire=False, color=(0.85, 0.12, 0.10), material=external))) for left, right in zip(nodes[:-1], nodes[1:])]
    TIP_ID = nodes[-1]
    initial_positions = [[float(x) for x in O.bodies[body_id].state.pos] for body_id in nodes]
    CASE_START_TIME = float(O.time)
    O.dt = 1e-10
    O.step()
    masses = [float(O.bodies[body_id].state.mass) for body_id in nodes]
    segment = LENGTH / float(COUNT - 1)
    axial_kn = E * math.pi * RF ** 2 / segment
    transverse_kn = 12.0 * E * I_SECOND / segment ** 3
    O.dt = float(CONFIG["numerics"]["time_step_safety_factor"]) * math.sqrt(min(masses) / max(axial_kn, transverse_kn))
    sample_steps = max(1, int(math.ceil(float(CONFIG["outputs"]["sample_duration_s"]) / O.dt)))
    target_iteration = int(O.iter) + int(math.ceil((HOLD + PULL_DURATION) / O.dt))
    sand_set, connection_set, node_set = set(sand_ids), set(connections), set(nodes)
    contacted_ever = set()
    rows = []
    plane = [float(x) for x in case["classification_plane_point_m"]]
    while O.iter < target_iteration:
        O.run(min(sample_steps, target_iteration - int(O.iter)), True)
        contacts = []
        for interaction in O.interactions:
            if not interaction.isReal:
                continue
            first, second = int(interaction.id1), int(interaction.id2)
            if (first in sand_set and second in connection_set) or (second in sand_set and first in connection_set):
                contacts.append(interaction)
        contacted = set(int(i.id1) if int(i.id1) in sand_set else int(i.id2) for i in contacts)
        contacted_ever.update(contacted)
        penetrations = [max(0.0, float(i.geom.penetrationDepth)) for i in contacts]
        normal_force_sum = sum(norm3(i.phys.normalForce) for i in contacts)
        positions = [O.bodies[body_id].state.pos for body_id in nodes]
        displacements = [Vector3(positions[index]) - Vector3(initial_positions[index]) for index in range(COUNT)]
        elapsed_time = float(O.time) - CASE_START_TIME
        row = {
            "iteration": int(O.iter), "time_s": elapsed_time, "phase": "hold" if elapsed_time <= HOLD else "pull",
            "applied_pull_force_n": applied_force(),
            "leading_node_advance_m": dot3(displacements[-1], PULL_DIRECTION),
            "maximum_node_displacement_m": max(norm3(value) for value in displacements),
            "maximum_node_speed_m_s": max(norm3(O.bodies[body_id].state.vel) for body_id in nodes),
            "nodes_beyond_classification_plane": sum(1 for position in positions if dot3([float(position[k]) - plane[k] for k in range(3)], PULL_DIRECTION) > 0.0),
            "sand_fibre_contact_count": len(contacts), "distinct_contacted_sand_count": len(contacted),
            "cumulative_distinct_contacted_sand_count": len(contacted_ever),
            "sum_contact_normal_force_n": normal_force_sum,
            "maximum_penetration_over_fibre_radius": max(penetrations) / RF if penetrations else 0.0,
            "internal_real_bond_count": sum(1 for i in O.interactions if i.isReal and int(i.id1) in node_set and int(i.id2) in node_set),
        }
        if not all(math.isfinite(float(row[key])) for key in ("leading_node_advance_m", "maximum_node_displacement_m", "maximum_node_speed_m_s", "sum_contact_normal_force_n", "maximum_penetration_over_fibre_radius")):
            raise RuntimeError("nonfinite state in %s" % case["case_id"])
        rows.append(row)
    history_path = os.path.join(OUTPUT, case["case_id"] + "_history.csv")
    with open(history_path, "x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    hold_rows = [row for row in rows if row["phase"] == "hold"]
    terminal = rows[-int(CONFIG["outputs"]["terminal_record_count"]):]
    sand_drift = max(norm3(Vector3(O.bodies[body_id].state.pos) - Vector3(sand_initial[body_id])) for body_id in sand_ids)
    record = {
        "case_id": case["case_id"], "role": case["role"], "time_step_s": float(O.dt), "iterations": int(O.iter),
        "maximum_hold_drift_m": max(row["maximum_node_displacement_m"] for row in hold_rows),
        "maximum_hold_speed_m_s": max(row["maximum_node_speed_m_s"] for row in hold_rows),
        "terminal_leading_node_advance_m": rows[-1]["leading_node_advance_m"],
        "terminal_nodes_beyond_classification_plane": rows[-1]["nodes_beyond_classification_plane"],
        "minimum_terminal_contact_count": min(row["sand_fibre_contact_count"] for row in terminal),
        "maximum_simultaneous_distinct_contacted_sand_count": max(row["distinct_contacted_sand_count"] for row in rows),
        "cumulative_distinct_contacted_sand_count": rows[-1]["cumulative_distinct_contacted_sand_count"],
        "maximum_contact_normal_force_n": max(row["sum_contact_normal_force_n"] for row in rows),
        "maximum_penetration_over_fibre_radius": max(row["maximum_penetration_over_fibre_radius"] for row in rows),
        "terminal_internal_real_bond_count": rows[-1]["internal_real_bond_count"],
        "maximum_fixed_sand_displacement_m": sand_drift,
        "initial_node_positions_m": initial_positions,
        "terminal_node_positions_m": [[float(x) for x in O.bodies[body_id].state.pos] for body_id in nodes],
        "classification_plane_point_m": plane, "pull_direction": PULL_DIRECTION,
        "history": {"path": os.path.basename(history_path), "sha256": sha(history_path)},
    }
    record_path = os.path.join(OUTPUT, case["case_id"] + "_result.json")
    with open(record_path, "x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True); stream.write("\n")
    record["result_artifact"] = {"path": os.path.basename(record_path), "sha256": sha(record_path)}
    return record


started = time.time()
cases = [run_case(case) for case in CONFIG["cases"]]
by_id = {case["case_id"]: case for case in cases}
constricted, open_case = by_id["constricted"], by_id["open"]
gates = CONFIG["gates"]
multi_contact_caged = (constricted["maximum_simultaneous_distinct_contacted_sand_count"] >= 2 and
                       constricted["minimum_terminal_contact_count"] >= 1 and
                       constricted["terminal_nodes_beyond_classification_plane"] == 0 and
                       constricted["terminal_leading_node_advance_m"] <= float(gates["maximum_caged_advance_m"]))
if multi_contact_caged:
    constricted_class = "multi_contact_caged"
elif constricted["maximum_contact_normal_force_n"] > 0 and constricted["terminal_nodes_beyond_classification_plane"] > 0:
    constricted_class = "contact_deflected_passage"
elif constricted["maximum_contact_normal_force_n"] > 0:
    constricted_class = "single_or_transient_obstacle_arrest"
else:
    constricted_class = "no_engagement"
checks = {
    "finite_bond_complete": all(case["terminal_internal_real_bond_count"] == COUNT - 1 for case in cases),
    "zero_load_hold_stable": all(case["maximum_hold_drift_m"] <= float(gates["maximum_hold_drift_m"]) for case in cases),
    "fixed_sand_exact": all(case["maximum_fixed_sand_displacement_m"] == 0.0 for case in cases),
    "penetration_guard": all(case["maximum_penetration_over_fibre_radius"] <= float(gates["maximum_penetration_over_fibre_radius"]) for case in cases),
    "open_no_contact": open_case["maximum_contact_normal_force_n"] == 0.0,
    "open_passage": open_case["terminal_nodes_beyond_classification_plane"] >= int(gates["minimum_open_nodes_beyond_plane"]),
    "open_advance": open_case["terminal_leading_node_advance_m"] >= float(gates["minimum_open_advance_m"]),
    "constricted_engagement": constricted["maximum_contact_normal_force_n"] > 0.0,
    "response_contrast": open_case["terminal_leading_node_advance_m"] - constricted["terminal_leading_node_advance_m"] >= float(gates["minimum_response_contrast_m"]),
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage26v-fixed-sand-flexible-pilot-result.v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed, "status": "fixed_sand_integration_verified" if passed else "fixed_sand_integration_not_qualified",
    "cases": cases, "checks": checks, "constricted_classification": constricted_class,
    "multi_contact_cage_observed": multi_contact_caged, "elapsed_wall_s": time.time() - started,
    "source_hashes": {"config": sha(CONFIG_PATH), "runner": sha(RUNNER), "source_state": sha(CONFIG["source_state"])},
    "authority": {"mobile_sand_release_design_authorized": bool(passed and multi_contact_caged),
                  "mobile_sand_execution_authorized": False, "flow_authorized": False, "permeability_claim_authorized": False},
    "claim_boundary": CONFIG["claim_boundary"],
}
result_path = os.path.join(OUTPUT, "result.json")
with open(result_path, "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
completion = {"schema": "lbs.stage26v-fixed-sand-flexible-pilot-completion.v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "passed": passed, "status": result["status"], "checks": checks,
              "result": {"path": result_path, "sha256": sha(result_path)}, "authority": result["authority"]}
with open(os.path.join(OUTPUT, "completion.json"), "x") as stream:
    json.dump(completion, stream, indent=2, sort_keys=True); stream.write("\n")
print(json.dumps(completion, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 2)
