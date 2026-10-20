#!/usr/bin/env python3
"""YADE runner for six Stage31c fixed-sand, four-fibre mechanics blocks."""
from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade.gridpfacet import gridConnection, gridNode

CONFIG_PATH = os.environ["STAGE31C_CONFIG"]
HANDOFF_PATH = os.environ["STAGE31C_HANDOFF"]
OUTPUT = os.environ["STAGE31C_OUTPUT"]
RUNNER = "/mnt/c/MATDEM_MICROPLASTIC/stage31_staging/run_stage31c_replicated_nested_mechanics_v1.py"


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def norm3(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


def dot3(first, second):
    return sum(float(first[index]) * float(second[index]) for index in range(3))


if os.path.exists(OUTPUT):
    raise RuntimeError("refusing to overwrite %s" % OUTPUT)
os.makedirs(OUTPUT)
with open(CONFIG_PATH) as stream:
    CONFIG = json.load(stream)
with open(HANDOFF_PATH) as stream:
    HANDOFF = json.load(stream)
if CONFIG.get("status") != "stage31c_replicated_nested_mechanics_preflight_release_required":
    raise RuntimeError("configuration is not a Stage31c release candidate")
if CONFIG["authority"].get("mechanics_execution") is not False:
    raise RuntimeError("preflight configuration must remain fail-closed")
if not (
    HANDOFF.get("passed") is True
    and HANDOFF.get("status") == "stage31c_replicated_nested_mechanics_execution_authorized"
    and HANDOFF["authority"].get("mechanics_execution") is True
):
    raise RuntimeError("independent handoff does not authorize mechanics")
if sha(CONFIG_PATH) != HANDOFF["bindings"]["config_sha256"]:
    raise RuntimeError("handoff config hash mismatch")
if sha(RUNNER) != HANDOFF["bindings"]["runner_sha256"]:
    raise RuntimeError("handoff runner hash mismatch")
for name, binding in CONFIG["sources"].items():
    if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
        if sha(binding["path"]) != binding["sha256"]:
            raise RuntimeError("source hash mismatch: " + name)
if sha(RUNNER) != CONFIG["sources"]["runner"]["sha256"]:
    raise RuntimeError("runner self-hash mismatch")
if any(CONFIG["authority"].get(name, False) for name in ("gpu_flow", "permeability_claim", "mobile_sand", "coupling")):
    raise RuntimeError("authority boundary exceeded")

RF = 0.5 * float(CONFIG["mechanics"]["fibre"]["diameter_m"])
LENGTH = float(CONFIG["mechanics"]["fibre"]["length_m"])
COUNT = int(CONFIG["mechanics"]["fibre"]["node_count"])
E = float(CONFIG["mechanics"]["fibre"]["young_pa"])
I_SECOND = math.pi * (2.0 * RF) ** 4 / 64.0
HOLD = float(CONFIG["mechanics"]["loading"]["zero_load_hold_duration_s"])
RAMP = float(CONFIG["mechanics"]["loading"]["force_ramp_duration_s"])
PULL_DURATION = float(CONFIG["mechanics"]["loading"]["pull_duration_s"])
FORCE = float(CONFIG["mechanics"]["loading"]["axial_pull_force_n"])
TIP_LOADS = []
CASE_START_TIME = 0.0


def applied_force():
    elapsed = float(O.time) - CASE_START_TIME - HOLD
    return 0.0 if elapsed <= 0.0 else FORCE * min(1.0, elapsed / RAMP)


def apply_pulls():
    value = applied_force()
    if value > 0.0:
        for tip_id, direction in TIP_LOADS:
            O.forces.addF(tip_id, Vector3(*[value * component for component in direction]), permanent=False)


def prepare_source(case):
    state = case["source_state"]
    if sha(state["path"]) != state["sha256"]:
        raise RuntimeError("case source-state hash mismatch: " + case["case_id"])
    O.load(state["path"])
    if not O.periodic:
        raise RuntimeError("source state is not periodic")
    sand_ids = sorted(
        int(body.id)
        for body in O.bodies
        if body is not None and body.shape.__class__.__name__ == "Sphere" and not body.isClumpMember
    )
    if len(sand_ids) != int(CONFIG["acceptance"]["required_sand_particles"]):
        raise RuntimeError("sand count mismatch")
    loaded_hsize = Matrix3(*[float(O.cell.hSize[i, j]) for i in range(3) for j in range(3)])
    for engine in O.engines:
        if engine.__class__.__name__ == "PeriTriaxController":
            engine.dead = True
    O.cell.velGrad = Matrix3.Zero
    initial = {}
    for body_id in sand_ids:
        body = O.bodies[body_id]
        body.state.blockedDOFs = "xyzXYZ"
        body.state.vel = Vector3.Zero
        body.state.angVel = Vector3.Zero
        initial[body_id] = [float(value) for value in body.state.pos]
    O.step()
    O.cell.hSize = loaded_hsize
    O.cell.velGrad = Matrix3.Zero
    for body_id in sand_ids:
        O.bodies[body_id].state.pos = Vector3(*initial[body_id])
        O.bodies[body_id].state.vel = Vector3.Zero
        O.bodies[body_id].state.angVel = Vector3.Zero
    return sand_ids, initial, loaded_hsize


def run_case(case):
    global TIP_LOADS, CASE_START_TIME
    sand_ids, sand_initial, loaded_hsize = prepare_source(case)
    internal = O.materials.append(
        CohFrictMat(
            young=E,
            poisson=float(CONFIG["mechanics"]["fibre"]["poisson"]),
            density=float(CONFIG["mechanics"]["fibre"]["density_kg_m3"]),
            frictionAngle=0.0,
            normalCohesion=1.0e20,
            shearCohesion=1.0e20,
            momentRotationLaw=True,
            label="stage31c_internal",
        )
    )
    external = O.materials.append(
        FrictMat(
            young=float(CONFIG["mechanics"]["contact"]["young_pa"]),
            poisson=float(CONFIG["mechanics"]["contact"]["poisson"]),
            density=float(CONFIG["mechanics"]["fibre"]["density_kg_m3"]),
            frictionAngle=math.atan(float(CONFIG["mechanics"]["contact"]["friction_coefficient"])),
            label="stage31c_external",
        )
    )
    self_mask = sum(2 << index for index in range(4))
    O.engines = [
        ForceResetter(),
        PyRunner(iterPeriod=1, command="apply_pulls()"),
        InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_GridConnection_Aabb()], avoidSelfInteractionMask=self_mask),
        InteractionLoop(
            [
                Ig2_Sphere_Sphere_ScGeom(),
                Ig2_GridNode_GridNode_GridNodeGeom6D(),
                Ig2_Sphere_GridConnection_ScGridCoGeom(),
                Ig2_GridConnection_GridConnection_GridCoGridCoGeom(),
            ],
            [
                Ip2_FrictMat_FrictMat_FrictPhys(),
                Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionNow=True, setCohesionOnNewContacts=True),
            ],
            [
                Law2_ScGeom_FrictPhys_CundallStrack(),
                Law2_ScGeom6D_CohFrictPhys_CohesionMoment(),
                Law2_ScGridCoGeom_FrictPhys_CundallStrack(),
                Law2_GridCoGridCoGeom_FrictPhys_CundallStrack(),
            ],
        ),
        NewtonIntegrator(gravity=(0, 0, 0), damping=float(CONFIG["mechanics"]["numerics"]["newton_damping"])),
    ]
    colours = [(0.0, 0.45, 0.70), (0.90, 0.62, 0.0), (0.0, 0.62, 0.45), (0.80, 0.47, 0.65)]
    records, node_owner, connection_owner, all_nodes = [], {}, {}, []
    TIP_LOADS = []
    for fibre_index, fibre in enumerate(case["fibres"]):
        rear = [float(value) for value in fibre["rear_m"]]
        tip = [float(value) for value in fibre["tip_m"]]
        direction = [float(value) for value in fibre["pull_direction"]]
        nodes = []
        for node_index in range(COUNT):
            fraction = node_index / float(COUNT - 1)
            position = [rear[axis] + fraction * (tip[axis] - rear[axis]) for axis in range(3)]
            nodes.append(int(O.bodies.append(gridNode(position, RF, fixed=False, wire=False, color=colours[fibre_index], material=internal))))
        connections = [
            int(O.bodies.append(gridConnection(left, right, RF, wire=False, color=colours[fibre_index], material=external)))
            for left, right in zip(nodes[:-1], nodes[1:])
        ]
        group_mask = 1 | (2 << fibre_index)
        for body_id in nodes + connections:
            O.bodies[body_id].groupMask = group_mask
        for body_id in nodes:
            node_owner[body_id] = fibre_index
        for body_id in connections:
            connection_owner[body_id] = fibre_index
        all_nodes.extend(nodes)
        TIP_LOADS.append((nodes[-1], direction))
        records.append(
            {
                "fibre_id": fibre["fibre_id"],
                "nested_rank": int(fibre["nested_rank"]),
                "source_face_index": int(fibre["source_face_index"]),
                "pull_direction": direction,
                "nodes": nodes,
                "connections": connections,
                "initial_node_positions_m": [[float(value) for value in O.bodies[node].state.pos] for node in nodes],
            }
        )
    CASE_START_TIME = float(O.time)
    O.dt = 1.0e-10
    O.step()
    cell_change = max(abs(float(O.cell.hSize[i, j]) - float(loaded_hsize[i, j])) for i in range(3) for j in range(3))
    if cell_change > 1.0e-15:
        raise RuntimeError("cell changed during synchronization")
    segment = LENGTH / float(COUNT - 1)
    axial_kn = E * math.pi * RF ** 2 / segment
    transverse_kn = 12.0 * E * I_SECOND / segment ** 3
    O.dt = float(CONFIG["mechanics"]["numerics"]["time_step_safety_factor"]) * math.sqrt(min(float(O.bodies[node].state.mass) for node in all_nodes) / max(axial_kn, transverse_kn))
    sample_steps = max(1, int(math.ceil(float(CONFIG["mechanics"]["outputs"]["sample_duration_s"]) / O.dt)))
    target = int(O.iter) + int(math.ceil((HOLD + PULL_DURATION) / O.dt))
    sand_set, rows = set(sand_ids), []
    ever_fibre_fibre = ever_intrafibre = ever_cross_nodes = 0
    while O.iter < target:
        O.run(min(sample_steps, target - int(O.iter)), True)
        sand_contacts, fibre_contacts, intrafibre, cross_nodes = [], [], [], []
        for interaction in O.interactions:
            if not interaction.isReal:
                continue
            first, second = int(interaction.id1), int(interaction.id2)
            if (first in sand_set and second in connection_owner) or (second in sand_set and first in connection_owner):
                sand_contacts.append(interaction)
            elif first in connection_owner and second in connection_owner:
                if connection_owner[first] == connection_owner[second]:
                    intrafibre.append(interaction)
                else:
                    fibre_contacts.append(interaction)
            elif first in node_owner and second in node_owner and node_owner[first] != node_owner[second]:
                cross_nodes.append(interaction)
        ever_fibre_fibre = max(ever_fibre_fibre, len(fibre_contacts))
        ever_intrafibre = max(ever_intrafibre, len(intrafibre))
        ever_cross_nodes = max(ever_cross_nodes, len(cross_nodes))
        per_fibre = []
        for record in records:
            node_set = set(record["nodes"])
            displacements = [Vector3(O.bodies[node].state.pos) - Vector3(record["initial_node_positions_m"][index]) for index, node in enumerate(record["nodes"])]
            per_fibre.append(
                {
                    "leading_advance_m": dot3(displacements[-1], record["pull_direction"]),
                    "maximum_displacement_m": max(norm3(value) for value in displacements),
                    "maximum_speed_m_s": max(norm3(O.bodies[node].state.vel) for node in record["nodes"]),
                    "internal_bonds": sum(1 for item in O.interactions if item.isReal and int(item.id1) in node_set and int(item.id2) in node_set),
                }
            )
        penetrations = [max(0.0, float(getattr(item.geom, "penetrationDepth", 0.0))) for item in sand_contacts + fibre_contacts]
        elapsed = float(O.time) - CASE_START_TIME
        row = {
            "iteration": int(O.iter),
            "time_s": elapsed,
            "phase": "hold" if elapsed <= HOLD else "pull",
            "applied_pull_force_per_fibre_n": applied_force(),
            "maximum_node_displacement_m": max(item["maximum_displacement_m"] for item in per_fibre),
            "maximum_node_speed_m_s": max(item["maximum_speed_m_s"] for item in per_fibre),
            "sand_fibre_contact_count": len(sand_contacts),
            "fibre_fibre_contact_count": len(fibre_contacts),
            "intrafibre_contact_count": len(intrafibre),
            "cross_fibre_node_real_interaction_count": len(cross_nodes),
            "maximum_penetration_over_fibre_radius": max(penetrations) / RF if penetrations else 0.0,
            "internal_real_bond_counts": json.dumps([item["internal_bonds"] for item in per_fibre]),
        }
        for key in ("time_s", "maximum_node_displacement_m", "maximum_node_speed_m_s", "maximum_penetration_over_fibre_radius"):
            if not math.isfinite(float(row[key])):
                raise RuntimeError("nonfinite mechanics state")
        rows.append(row)
    history_path = os.path.join(OUTPUT, case["case_id"] + "_history.csv")
    with open(history_path, "x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    hold_rows = [row for row in rows if row["phase"] == "hold"]
    terminal_fibres = []
    for record in records:
        node_set = set(record["nodes"])
        terminal_fibres.append(
            {
                "fibre_id": record["fibre_id"],
                "nested_rank": record["nested_rank"],
                "source_face_index": record["source_face_index"],
                "pull_direction": record["pull_direction"],
                "initial_node_positions_m": record["initial_node_positions_m"],
                "terminal_node_positions_m": [[float(value) for value in O.bodies[node].state.pos] for node in record["nodes"]],
                "terminal_internal_real_bond_count": sum(1 for item in O.interactions if item.isReal and int(item.id1) in node_set and int(item.id2) in node_set),
            }
        )
    result = {
        "case_id": case["case_id"],
        "packing_id": case["packing_id"],
        "placement_block": case["placement_block"],
        "fibre_count": 4,
        "source_state_sha256": sha(case["source_state"]["path"]),
        "time_step_s": float(O.dt),
        "maximum_hold_drift_m": max(row["maximum_node_displacement_m"] for row in hold_rows),
        "maximum_hold_speed_m_s": max(row["maximum_node_speed_m_s"] for row in hold_rows),
        "maximum_fixed_sand_displacement_m": max(norm3(Vector3(O.bodies[body_id].state.pos) - Vector3(sand_initial[body_id])) for body_id in sand_ids),
        "maximum_periodic_cell_change_m": cell_change,
        "maximum_fibre_fibre_contact_count": ever_fibre_fibre,
        "maximum_intrafibre_contact_count": ever_intrafibre,
        "maximum_cross_fibre_node_real_interaction_count": ever_cross_nodes,
        "maximum_penetration_over_fibre_radius": max(row["maximum_penetration_over_fibre_radius"] for row in rows),
        "maximum_terminal_displacement_m": max(
            norm3(Vector3(terminal["terminal_node_positions_m"][index]) - Vector3(terminal["initial_node_positions_m"][index]))
            for terminal in terminal_fibres for index in range(COUNT)
        ),
        "terminal_fibres": terminal_fibres,
        "history": {"path": os.path.basename(history_path), "sha256": sha(history_path)},
    }
    result_path = os.path.join(OUTPUT, case["case_id"] + "_result.json")
    with open(result_path, "x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return {"case_id": case["case_id"], "path": os.path.basename(result_path), "sha256": sha(result_path)}


started = time.time()
records = [run_case(case) for case in CONFIG["execution_cases"]]
result = {
    "schema": "lbs.stage31c-replicated-nested-mechanics-result.v1",
    "status": "mechanics_execution_complete_independent_evaluation_required",
    "passed": True,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "case_records": records,
    "elapsed_wall_s": time.time() - started,
    "source_hashes": {"config": sha(CONFIG_PATH), "runner": sha(RUNNER)},
    "authority": {"independent_mechanics_evaluation": True, "gpu_flow": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
    "claim_boundary": CONFIG["claim_boundary"],
}
result_path = os.path.join(OUTPUT, "result.json")
with open(result_path, "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
completion = {
    "schema": result["schema"] + ".completion",
    "status": result["status"],
    "passed": True,
    "result": {"path": result_path, "sha256": sha(result_path)},
    "case_count": len(records),
    "authority": result["authority"],
}
with open(os.path.join(OUTPUT, "completion.json"), "x") as stream:
    json.dump(completion, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(completion, indent=2, sort_keys=True))
