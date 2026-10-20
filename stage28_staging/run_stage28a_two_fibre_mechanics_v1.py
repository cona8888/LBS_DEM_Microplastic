#!/usr/bin/env python3
"""YADE runner for isolated and paired Stage28a flexible-fibre mechanics."""

from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade.gridpfacet import gridConnection, gridNode


CONFIG_PATH = os.environ["STAGE28A_CONFIG"]
HANDOFF_PATH = os.environ["STAGE28A_HANDOFF"]
OUTPUT = os.environ["STAGE28A_OUTPUT"]
RUNNER = "/mnt/c/MATDEM_MICROPLASTIC/stage28_staging/run_stage28a_two_fibre_mechanics_v1.py"


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def norm3(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


def dot3(a, b):
    return sum(float(a[k]) * float(b[k]) for k in range(3))


if os.path.exists(OUTPUT):
    raise RuntimeError("refusing to overwrite %s" % OUTPUT)
os.makedirs(OUTPUT)
with open(CONFIG_PATH) as stream:
    CONFIG = json.load(stream)
with open(HANDOFF_PATH) as stream:
    HANDOFF = json.load(stream)
if CONFIG.get("status") != "stage28a_two_fibre_mechanics_preflight_independent_release_required":
    raise RuntimeError("configuration is not a released preflight candidate")
if CONFIG["authority"].get("mechanics_execution_authorized") is not False:
    raise RuntimeError("preflight configuration must remain fail-closed")
if not (
    HANDOFF.get("passed") is True
    and HANDOFF.get("status") == "stage28a_mechanics_execution_authorized"
    and HANDOFF["authority"].get("mechanics_execution") is True
):
    raise RuntimeError("independent handoff does not authorize mechanics execution")
if sha(CONFIG_PATH) != HANDOFF["bindings"]["config_sha256"]:
    raise RuntimeError("handoff config hash mismatch")
if sha(RUNNER) != HANDOFF["bindings"]["runner_sha256"]:
    raise RuntimeError("handoff runner hash mismatch")
if any(
    CONFIG["authority"].get(name, False)
    for name in (
        "gpu_execution_authorized",
        "production_concentration_campaign_authorized",
        "mobile_sand_authorized",
        "two_way_coupling_authorized",
    )
):
    raise RuntimeError("Stage28a authority boundary exceeded")
for key, binding in CONFIG["sources"].items():
    if key == "expected_yade_version":
        continue
    if sha(binding["path"]) != binding["sha256"]:
        raise RuntimeError("source hash mismatch: " + key)
if sha(RUNNER) != CONFIG["sources"]["runner"]["sha256"]:
    raise RuntimeError("runner self-hash mismatch")

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
    if elapsed <= 0.0:
        return 0.0
    return FORCE * min(1.0, elapsed / RAMP)


def apply_pulls():
    value = applied_force()
    if value <= 0.0:
        return
    for tip_id, direction in TIP_LOADS:
        O.forces.addF(
            tip_id,
            Vector3(*[value * component for component in direction]),
            permanent=False,
        )


def prepare_periodic_source():
    O.load(CONFIG["sources"]["source_state"]["path"])
    if not O.periodic:
        raise RuntimeError("source state is not periodic")
    sand_ids = sorted(
        int(body.id)
        for body in O.bodies
        if body is not None
        and body.shape.__class__.__name__ == "Sphere"
        and not body.isClumpMember
    )
    if len(sand_ids) != int(CONFIG["acceptance"]["required_sand_particles"]):
        raise RuntimeError("source-state particle count mismatch")
    loaded_hsize = Matrix3(
        *[float(O.cell.hSize[i, j]) for i in range(3) for j in range(3)]
    )
    for engine in O.engines:
        if engine.__class__.__name__ == "PeriTriaxController":
            engine.dead = True
    O.cell.velGrad = Matrix3.Zero
    for body_id in sand_ids:
        O.bodies[body_id].state.blockedDOFs = "xyzXYZ"
        O.bodies[body_id].state.vel = Vector3.Zero
        O.bodies[body_id].state.angVel = Vector3.Zero
    initial = {
        body_id: [float(value) for value in O.bodies[body_id].state.pos]
        for body_id in sand_ids
    }
    # Consume the deferred dead-controller cell update, then restore exact state.
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
    sand_ids, sand_initial, loaded_hsize = prepare_periodic_source()
    internal = O.materials.append(
        CohFrictMat(
            young=E,
            poisson=float(CONFIG["mechanics"]["fibre"]["poisson"]),
            density=float(CONFIG["mechanics"]["fibre"]["density_kg_m3"]),
            frictionAngle=0.0,
            normalCohesion=1.0e20,
            shearCohesion=1.0e20,
            momentRotationLaw=True,
            label="stage28a_internal",
        )
    )
    external = O.materials.append(
        FrictMat(
            young=float(CONFIG["mechanics"]["contact"]["young_pa"]),
            poisson=float(CONFIG["mechanics"]["contact"]["poisson"]),
            density=float(CONFIG["mechanics"]["fibre"]["density_kg_m3"]),
            frictionAngle=math.atan(
                float(CONFIG["mechanics"]["contact"]["friction_coefficient"])
            ),
            label="stage28a_external",
        )
    )
    O.engines = [
        ForceResetter(),
        PyRunner(iterPeriod=1, command="apply_pulls()"),
        InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_GridConnection_Aabb()]),
        InteractionLoop(
            [
                Ig2_Sphere_Sphere_ScGeom(),
                Ig2_GridNode_GridNode_GridNodeGeom6D(),
                Ig2_Sphere_GridConnection_ScGridCoGeom(),
                Ig2_GridConnection_GridConnection_GridCoGridCoGeom(),
            ],
            [
                Ip2_FrictMat_FrictMat_FrictPhys(),
                Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(
                    setCohesionNow=True, setCohesionOnNewContacts=True
                ),
            ],
            [
                Law2_ScGeom_FrictPhys_CundallStrack(),
                Law2_ScGeom6D_CohFrictPhys_CohesionMoment(),
                Law2_ScGridCoGeom_FrictPhys_CundallStrack(),
                Law2_GridCoGridCoGeom_FrictPhys_CundallStrack(),
            ],
        ),
        NewtonIntegrator(
            gravity=(0, 0, 0),
            damping=float(CONFIG["mechanics"]["numerics"]["newton_damping"]),
        ),
    ]

    fibre_records = []
    node_owner = {}
    connection_owner = {}
    all_nodes = []
    all_connections = []
    TIP_LOADS = []
    colors = [(0.85, 0.12, 0.10), (0.10, 0.35, 0.90)]
    for fibre_index, fibre in enumerate(case["fibres"]):
        rear = [float(value) for value in fibre["rear_m"]]
        tip = [float(value) for value in fibre["tip_m"]]
        direction = [float(value) for value in fibre["pull_direction"]]
        nodes = []
        for index in range(COUNT):
            fraction = index / float(COUNT - 1)
            position = [rear[k] + fraction * (tip[k] - rear[k]) for k in range(3)]
            nodes.append(
                int(
                    O.bodies.append(
                        gridNode(
                            position,
                            RF,
                            fixed=False,
                            wire=False,
                            color=colors[fibre_index],
                            material=internal,
                        )
                    )
                )
            )
        connections = [
            int(
                O.bodies.append(
                    gridConnection(
                        left,
                        right,
                        RF,
                        wire=False,
                        color=colors[fibre_index],
                        material=external,
                    )
                )
            )
            for left, right in zip(nodes[:-1], nodes[1:])
        ]
        for body_id in nodes:
            node_owner[body_id] = fibre_index
        for body_id in connections:
            connection_owner[body_id] = fibre_index
        all_nodes.extend(nodes)
        all_connections.extend(connections)
        TIP_LOADS.append((nodes[-1], direction))
        fibre_records.append(
            {
                "fibre_id": fibre["fibre_id"],
                "source_face_index": int(fibre["source_face_index"]),
                "pull_direction": direction,
                "nodes": nodes,
                "connections": connections,
                "initial_node_positions_m": [
                    [float(value) for value in O.bodies[body_id].state.pos]
                    for body_id in nodes
                ],
            }
        )

    CASE_START_TIME = float(O.time)
    O.dt = 1.0e-10
    O.step()
    cell_change = max(
        abs(float(O.cell.hSize[i, j]) - float(loaded_hsize[i, j]))
        for i in range(3)
        for j in range(3)
    )
    if cell_change > 1.0e-15:
        raise RuntimeError("periodic cell changed during fixed-source synchronization")
    masses = [float(O.bodies[body_id].state.mass) for body_id in all_nodes]
    segment = LENGTH / float(COUNT - 1)
    axial_kn = E * math.pi * RF ** 2 / segment
    transverse_kn = 12.0 * E * I_SECOND / segment ** 3
    O.dt = float(CONFIG["mechanics"]["numerics"]["time_step_safety_factor"]) * math.sqrt(
        min(masses) / max(axial_kn, transverse_kn)
    )
    sample_steps = max(
        1,
        int(
            math.ceil(
                float(CONFIG["mechanics"]["outputs"]["sample_duration_s"]) / O.dt
            )
        ),
    )
    target_iteration = int(O.iter) + int(math.ceil((HOLD + PULL_DURATION) / O.dt))
    sand_set = set(sand_ids)
    rows = []
    fibre_fibre_contact_ever = 0
    maximum_cross_fibre_node_interactions = 0
    while O.iter < target_iteration:
        O.run(min(sample_steps, target_iteration - int(O.iter)), True)
        sand_contacts = []
        fibre_contacts = []
        intrafibre_contacts = []
        cross_node_interactions = []
        for interaction in O.interactions:
            if not interaction.isReal:
                continue
            first, second = int(interaction.id1), int(interaction.id2)
            if (first in sand_set and second in connection_owner) or (
                second in sand_set and first in connection_owner
            ):
                sand_contacts.append(interaction)
            elif first in connection_owner and second in connection_owner:
                if connection_owner[first] != connection_owner[second]:
                    fibre_contacts.append(interaction)
                else:
                    intrafibre_contacts.append(interaction)
            elif first in node_owner and second in node_owner and node_owner[first] != node_owner[second]:
                cross_node_interactions.append(interaction)
        fibre_fibre_contact_ever = max(fibre_fibre_contact_ever, len(fibre_contacts))
        maximum_cross_fibre_node_interactions = max(
            maximum_cross_fibre_node_interactions, len(cross_node_interactions)
        )
        all_contact_interactions = sand_contacts + fibre_contacts
        penetrations = [
            max(0.0, float(getattr(item.geom, "penetrationDepth", 0.0)))
            for item in all_contact_interactions
        ]
        per_fibre = []
        for record in fibre_records:
            positions = [O.bodies[body_id].state.pos for body_id in record["nodes"]]
            displacements = [
                Vector3(positions[index])
                - Vector3(record["initial_node_positions_m"][index])
                for index in range(COUNT)
            ]
            per_fibre.append(
                {
                    "leading_node_advance_m": dot3(
                        displacements[-1], record["pull_direction"]
                    ),
                    "maximum_node_displacement_m": max(norm3(value) for value in displacements),
                    "maximum_node_speed_m_s": max(
                        norm3(O.bodies[body_id].state.vel) for body_id in record["nodes"]
                    ),
                    "internal_real_bond_count": sum(
                        1
                        for item in O.interactions
                        if item.isReal
                        and int(item.id1) in set(record["nodes"])
                        and int(item.id2) in set(record["nodes"])
                    ),
                }
            )
        elapsed = float(O.time) - CASE_START_TIME
        row = {
            "iteration": int(O.iter),
            "time_s": elapsed,
            "phase": "hold" if elapsed <= HOLD else "pull",
            "applied_pull_force_per_fibre_n": applied_force(),
            "fibre_leading_advances_m": json.dumps(
                [item["leading_node_advance_m"] for item in per_fibre]
            ),
            "maximum_node_displacement_m": max(
                item["maximum_node_displacement_m"] for item in per_fibre
            ),
            "maximum_node_speed_m_s": max(
                item["maximum_node_speed_m_s"] for item in per_fibre
            ),
            "sand_fibre_contact_count": len(sand_contacts),
            "fibre_fibre_contact_count": len(fibre_contacts),
            "intrafibre_contact_count": len(intrafibre_contacts),
            "cross_fibre_node_real_interaction_count": len(cross_node_interactions),
            "sum_sand_contact_normal_force_n": sum(
                norm3(item.phys.normalForce) for item in sand_contacts
            ),
            "sum_fibre_contact_normal_force_n": sum(
                norm3(item.phys.normalForce) for item in fibre_contacts
            ),
            "maximum_penetration_over_fibre_radius": max(penetrations) / RF
            if penetrations
            else 0.0,
            "internal_real_bond_counts": json.dumps(
                [item["internal_real_bond_count"] for item in per_fibre]
            ),
        }
        for key in (
            "maximum_node_displacement_m",
            "maximum_node_speed_m_s",
            "sum_sand_contact_normal_force_n",
            "sum_fibre_contact_normal_force_n",
            "maximum_penetration_over_fibre_radius",
        ):
            if not math.isfinite(float(row[key])):
                raise RuntimeError("nonfinite state")
        rows.append(row)

    history_path = os.path.join(OUTPUT, case["case_id"] + "_history.csv")
    with open(history_path, "x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    hold_rows = [row for row in rows if row["phase"] == "hold"]
    sand_drift = max(
        norm3(Vector3(O.bodies[body_id].state.pos) - Vector3(sand_initial[body_id]))
        for body_id in sand_ids
    )
    terminal_fibres = []
    for record in fibre_records:
        terminal_fibres.append(
            {
                "fibre_id": record["fibre_id"],
                "source_face_index": record["source_face_index"],
                "initial_node_positions_m": record["initial_node_positions_m"],
                "terminal_node_positions_m": [
                    [float(value) for value in O.bodies[body_id].state.pos]
                    for body_id in record["nodes"]
                ],
                "pull_direction": record["pull_direction"],
                "terminal_internal_real_bond_count": sum(
                    1
                    for item in O.interactions
                    if item.isReal
                    and int(item.id1) in set(record["nodes"])
                    and int(item.id2) in set(record["nodes"])
                ),
            }
        )
    result = {
        "case_id": case["case_id"],
        "role": case["role"],
        "fibre_count": len(case["fibres"]),
        "time_step_s": float(O.dt),
        "iterations": int(O.iter),
        "maximum_hold_drift_m": max(row["maximum_node_displacement_m"] for row in hold_rows),
        "maximum_hold_speed_m_s": max(row["maximum_node_speed_m_s"] for row in hold_rows),
        "maximum_fixed_sand_displacement_m": sand_drift,
        "maximum_periodic_cell_change_m": cell_change,
        "maximum_sand_fibre_contact_count": max(row["sand_fibre_contact_count"] for row in rows),
        "maximum_fibre_fibre_contact_count": max(
            row["fibre_fibre_contact_count"] for row in rows
        ),
        "maximum_intrafibre_contact_count": max(row["intrafibre_contact_count"] for row in rows),
        "maximum_cross_fibre_node_real_interaction_count": maximum_cross_fibre_node_interactions,
        "maximum_penetration_over_fibre_radius": max(
            row["maximum_penetration_over_fibre_radius"] for row in rows
        ),
        "maximum_sand_contact_normal_force_n": max(
            row["sum_sand_contact_normal_force_n"] for row in rows
        ),
        "maximum_fibre_contact_normal_force_n": max(
            row["sum_fibre_contact_normal_force_n"] for row in rows
        ),
        "terminal_fibres": terminal_fibres,
        "history": {"path": os.path.basename(history_path), "sha256": sha(history_path)},
    }
    result_path = os.path.join(OUTPUT, case["case_id"] + "_result.json")
    with open(result_path, "x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    result["result_artifact"] = {
        "path": os.path.basename(result_path),
        "sha256": sha(result_path),
    }
    return result


def aligned_rms(first, second, cell_lengths):
    count = min(len(first), len(second))
    a = [[float(value) for value in row] for row in first[:count]]
    b = [[float(value) for value in row] for row in second[:count]]
    centroid_delta = [
        sum(a[i][axis] - b[i][axis] for i in range(count)) / float(count)
        for axis in range(3)
    ]
    minimum_image_shift = [
        centroid_delta[axis]
        - round(centroid_delta[axis] / float(cell_lengths[axis]))
        * float(cell_lengths[axis])
        for axis in range(3)
    ]
    squared = []
    for index in range(count):
        delta = [
            a[index][axis] - minimum_image_shift[axis] - b[index][axis]
            for axis in range(3)
        ]
        squared.append(sum(value * value for value in delta))
    return math.sqrt(sum(squared) / float(count))


started = time.time()
cases = [run_case(case) for case in CONFIG["execution_cases"]]
by_id = {case["case_id"]: case for case in cases}
isolated_by_face = {}
for face, binding in CONFIG["accepted_isolated_controls"].items():
    isolated_by_face[int(face)] = binding["terminal_node_positions_m"]
for case in cases:
    if case["role"] == "new_path_isolated_control":
        isolated_by_face[int(case["terminal_fibres"][0]["source_face_index"])] = case[
            "terminal_fibres"
        ][0]["terminal_node_positions_m"]

cell_lengths = CONFIG["cell_dimensions_m"]
path_match = []
for case_id in ("separated_open_open", "separated_open_constricted"):
    case = by_id[case_id]
    for fibre in case["terminal_fibres"]:
        face = int(fibre["source_face_index"])
        reference = isolated_by_face[face]
        rms = aligned_rms(fibre["terminal_node_positions_m"], reference, cell_lengths)
        path_match.append(
            {
                "case_id": case_id,
                "fibre_id": fibre["fibre_id"],
                "source_face_index": face,
                "aligned_terminal_rms_m": rms,
                "aligned_terminal_rms_over_fibre_diameter": rms / (2.0 * RF),
            }
        )

acceptance = CONFIG["acceptance"]
isolated_cases = [case for case in cases if case["role"] == "new_path_isolated_control"]
paired_cases = [
    by_id[name]
    for name in (
        "separated_open_open",
        "separated_open_constricted",
        "crossing_interaction",
    )
]
checks = {
    "exact_six_execution_cases": len(cases) == 6,
    "three_new_isolated_controls": len(isolated_cases) == 3,
    "three_paired_cases": len(paired_cases) == 3,
    "finite_bond_complete": all(
        all(
            fibre["terminal_internal_real_bond_count"]
            == int(acceptance["required_internal_bonds_per_fibre"])
            for fibre in case["terminal_fibres"]
        )
        for case in cases
    ),
    "zero_load_hold_stable": all(
        case["maximum_hold_drift_m"] <= float(acceptance["maximum_hold_drift_m"])
        and case["maximum_hold_speed_m_s"]
        <= float(acceptance["maximum_hold_speed_m_s"])
        for case in cases
    ),
    "fixed_sand_exact": all(case["maximum_fixed_sand_displacement_m"] == 0.0 for case in cases),
    "fixed_periodic_cell_exact": all(
        case["maximum_periodic_cell_change_m"]
        <= float(acceptance["maximum_cell_dimension_change_m"])
        for case in cases
    ),
    "penetration_guard": all(
        case["maximum_penetration_over_fibre_radius"]
        <= float(acceptance["maximum_penetration_over_fibre_radius"])
        for case in cases
    ),
    "no_cross_fibre_node_bond": all(
        case["maximum_cross_fibre_node_real_interaction_count"] == 0 for case in cases
    ),
    "separated_no_fibre_contact": by_id["separated_open_open"][
        "maximum_fibre_fibre_contact_count"
    ]
    == 0
    and by_id["separated_open_constricted"]["maximum_fibre_fibre_contact_count"] == 0,
    "crossing_contact_resolved": by_id["crossing_interaction"][
        "maximum_fibre_fibre_contact_count"
    ]
    >= int(acceptance["minimum_crossing_fibre_fibre_contacts"]),
    "separated_path_match": all(
        row["aligned_terminal_rms_over_fibre_diameter"]
        <= float(acceptance["maximum_aligned_terminal_centreline_rms_over_fibre_diameter"])
        for row in path_match
    ),
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage28a-two-fibre-mechanics-result.v1",
    "status": "two_fibre_mechanics_verified" if passed else "two_fibre_mechanics_not_qualified",
    "passed": passed,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
    "cases": cases,
    "path_match": path_match,
    "elapsed_wall_s": time.time() - started,
    "source_hashes": {
        "config": sha(CONFIG_PATH),
        "runner": sha(RUNNER),
        "source_state": sha(CONFIG["sources"]["source_state"]["path"]),
    },
    "authority": {
        "independent_mechanics_evaluation": True,
        "hydraulic_geometry_design": False,
        "gpu_execution": False,
        "production_concentration_campaign": False,
        "mobile_sand": False,
        "two_way_coupling": False,
    },
    "claim_boundary": CONFIG["claim_boundary"],
}
result_path = os.path.join(OUTPUT, "result.json")
with open(result_path, "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
completion = {
    "schema": result["schema"] + ".completion",
    "status": result["status"],
    "passed": passed,
    "checks": checks,
    "result": {"path": result_path, "sha256": sha(result_path)},
    "authority": result["authority"],
}
with open(os.path.join(OUTPUT, "completion.json"), "x") as stream:
    json.dump(completion, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(completion, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 2)
