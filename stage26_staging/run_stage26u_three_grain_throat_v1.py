#!/usr/bin/env python3
"""Run the Stage26u three-tangent-sphere throat pull-through screen."""

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

CONFIG_PATH = os.environ["STAGE26U_CONFIG"]
OUTPUT = os.environ["STAGE26U_OUTPUT"]
if os.path.exists(OUTPUT): raise RuntimeError("refusing to overwrite %s" % OUTPUT)
os.makedirs(OUTPUT)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()


with open(CONFIG_PATH) as stream: CONFIG = json.load(stream)
RUNNER_PATH = "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26u_three_grain_throat_v1.py"
if sha256(RUNNER_PATH) != CONFIG["source_hashes"]["runner"]: raise RuntimeError("runner hash mismatch")

L = float(CONFIG["fibre"]["length_m"]); D = float(CONFIG["fibre"]["diameter_m"]); RF = 0.5 * D
E = float(CONFIG["fibre"]["young_pa"]); NU = float(CONFIG["fibre"]["poisson"])
RHO_F = float(CONFIG["fibre"]["density_kg_m3"]); N = int(CONFIG["fibre"]["node_count"])
I_SECOND = math.pi * D ** 4 / 64.0
INITIAL_TIP_X = float(CONFIG["geometry"]["initial_tip_x_m"])
INITIAL_REAR_X = INITIAL_TIP_X - L
OFFSET_Y = float(CONFIG["geometry"]["transverse_imperfection_m"])
PULL_FORCE = float(CONFIG["loading"]["axial_pull_force_n"])
RAMP_TIME = float(CONFIG["loading"]["force_ramp_duration_s"])
TOTAL_TIME = float(CONFIG["loading"]["total_duration_s"])
TIP_ID = -1


def apply_pull():
    fraction = min(1.0, max(0.0, float(O.time) / RAMP_TIME))
    O.forces.addF(TIP_ID, Vector3(PULL_FORCE * fraction, 0.0, 0.0), permanent=False)


def norm3(v): return math.sqrt(sum(float(x) ** 2 for x in v))


def run_case(case):
    global TIP_ID
    O.reset()
    internal = O.materials.append(CohFrictMat(
        young=E, poisson=NU, density=RHO_F, frictionAngle=0.0,
        normalCohesion=1e20, shearCohesion=1e20, momentRotationLaw=True, label="fibreInternal"))
    external = O.materials.append(FrictMat(
        young=float(CONFIG["contact"]["young_pa"]), poisson=float(CONFIG["contact"]["poisson"]),
        density=RHO_F, frictionAngle=0.0, label="fibreExternal"))
    sand_mat = O.materials.append(FrictMat(
        young=float(CONFIG["contact"]["young_pa"]), poisson=float(CONFIG["contact"]["poisson"]),
        density=float(CONFIG["sand"]["density_kg_m3"]), frictionAngle=0.0, label="sand"))
    O.engines = [
        ForceResetter(), PyRunner(iterPeriod=1, command="apply_pull()"),
        InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_GridConnection_Aabb()]),
        InteractionLoop(
            [Ig2_GridNode_GridNode_GridNodeGeom6D(), Ig2_Sphere_GridConnection_ScGridCoGeom()],
            [Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionNow=True, setCohesionOnNewContacts=True),
             Ip2_FrictMat_FrictMat_FrictPhys()],
            [Law2_ScGeom6D_CohFrictPhys_CohesionMoment(), Law2_ScGridCoGeom_FrictPhys_CundallStrack()]),
        NewtonIntegrator(gravity=(0, 0, 0), damping=float(CONFIG["numerics"]["newton_damping"])),
    ]
    segment = L / float(N - 1)
    nodes = [O.bodies.append(gridNode(
        [INITIAL_REAR_X + index * segment, OFFSET_Y, 0.0], RF, fixed=False, wire=False,
        color=(0.85, 0.12, 0.10), material=internal)) for index in range(N)]
    connections = [O.bodies.append(gridConnection(
        left, right, RF, wire=False, color=(0.85, 0.12, 0.10), material=external))
        for left, right in zip(nodes[:-1], nodes[1:])]
    TIP_ID = nodes[-1]
    sand_radius = 0.5 * float(case["sand_diameter_m"])
    throat_radius = 0.5 * float(case["throat_diameter_m"])
    centroid_radius = sand_radius + throat_radius
    sphere_ids = []
    for angle_deg in (90.0, 210.0, 330.0):
        angle = math.radians(angle_deg)
        y = centroid_radius * math.cos(angle); z = centroid_radius * math.sin(angle)
        sphere_ids.append(O.bodies.append(utils.sphere((0.0, y, z), sand_radius, fixed=True,
            color=(0.70, 0.66, 0.54), material=sand_mat)))
    initial_positions = [[float(x) for x in O.bodies[body_id].state.pos] for body_id in nodes]
    O.dt = 1e-10; O.step()
    masses = [float(O.bodies[body_id].state.mass) for body_id in nodes]
    axial_kn = E * math.pi * RF ** 2 / segment
    transverse_kn = 12.0 * E * I_SECOND / segment ** 3
    O.dt = float(CONFIG["numerics"]["time_step_safety_factor"]) * math.sqrt(min(masses) / max(axial_kn, transverse_kn))
    sample_steps = max(1, int(math.ceil(float(CONFIG["outputs"]["sample_duration_s"]) / O.dt)))
    maximum_steps = int(math.ceil(TOTAL_TIME / O.dt))
    connection_set = set(connections); sphere_set = set(sphere_ids)
    rows = []
    while O.iter < maximum_steps:
        O.run(min(sample_steps, maximum_steps - int(O.iter)), True)
        contacts = []
        for interaction in O.interactions:
            if not interaction.isReal: continue
            first, second = int(interaction.id1), int(interaction.id2)
            if (first in sphere_set and second in connection_set) or (second in sphere_set and first in connection_set):
                contacts.append(interaction)
        positions = [O.bodies[body_id].state.pos for body_id in nodes]
        penetrations = [max(0.0, float(i.geom.penetrationDepth)) for i in contacts]
        internal_bonds = sum(1 for i in O.interactions if i.isReal and int(i.id1) in set(nodes) and int(i.id2) in set(nodes))
        row = {
            "iteration": int(O.iter), "time_s": float(O.time),
            "leading_node_advance_m": float(positions[-1][0]) - INITIAL_TIP_X,
            "leading_node_x_m": float(positions[-1][0]), "rear_node_x_m": float(positions[0][0]),
            "nodes_beyond_throat": sum(1 for p in positions if float(p[0]) > 0.0),
            "sand_fibre_contact_count": len(contacts),
            "distinct_contacted_spheres": len(set(int(i.id1) if int(i.id1) in sphere_set else int(i.id2) for i in contacts)),
            "maximum_penetration_over_fibre_radius": (max(penetrations) / RF) if penetrations else 0.0,
            "maximum_node_speed_m_s": max(norm3(O.bodies[body_id].state.vel) for body_id in nodes),
            "maximum_transverse_centreline_displacement_m": max(
                math.sqrt((float(p[1]) - OFFSET_Y) ** 2 + float(p[2]) ** 2) for p in positions),
            "internal_real_bond_count": internal_bonds,
        }
        if not all(math.isfinite(float(row[key])) for key in (
            "leading_node_advance_m", "leading_node_x_m", "rear_node_x_m",
            "maximum_penetration_over_fibre_radius", "maximum_node_speed_m_s",
            "maximum_transverse_centreline_displacement_m")):
            raise RuntimeError("nonfinite state in %s" % case["case_id"])
        rows.append(row)
    terminal_positions = [[float(x) for x in O.bodies[body_id].state.pos] for body_id in nodes]
    history_path = os.path.join(OUTPUT, case["case_id"] + "_history.csv")
    with open(history_path, "x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    terminal_window = rows[-int(CONFIG["analysis"]["terminal_record_count"]):]
    record = {
        "case_id": case["case_id"], "throat_to_fibre_diameter_ratio": float(case["throat_to_fibre_diameter_ratio"]),
        "sand_diameter_m": 2.0 * sand_radius, "throat_diameter_m": 2.0 * throat_radius,
        "tangent_centre_distance_m": 2.0 * sand_radius,
        "analytical_throat_diameter_m": 2.0 * sand_radius * (2.0 / math.sqrt(3.0) - 1.0),
        "analytical_throat_relative_error": abs((2.0 * sand_radius * (2.0 / math.sqrt(3.0) - 1.0)) / (2.0 * throat_radius) - 1.0),
        "time_step_s": float(O.dt), "iterations": int(O.iter),
        "terminal_leading_node_advance_m": rows[-1]["leading_node_advance_m"],
        "terminal_nodes_beyond_throat": rows[-1]["nodes_beyond_throat"],
        "minimum_terminal_contact_count": min(row["sand_fibre_contact_count"] for row in terminal_window),
        "maximum_recorded_contact_count": max(row["sand_fibre_contact_count"] for row in rows),
        "maximum_penetration_over_fibre_radius": max(row["maximum_penetration_over_fibre_radius"] for row in rows),
        "terminal_internal_real_bond_count": rows[-1]["internal_real_bond_count"],
        "maximum_transverse_centreline_displacement_m": max(row["maximum_transverse_centreline_displacement_m"] for row in rows),
        "initial_node_positions_m": initial_positions, "terminal_node_positions_m": terminal_positions,
        "sphere_centres_m": [[float(x) for x in O.bodies[body_id].state.pos] for body_id in sphere_ids],
        "history": {"path": os.path.basename(history_path), "sha256": sha256(history_path)},
    }
    record_path = os.path.join(OUTPUT, case["case_id"] + "_result.json")
    with open(record_path, "x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True); stream.write("\n")
    record["result_artifact"] = {"path": os.path.basename(record_path), "sha256": sha256(record_path)}
    return record


started = time.time(); cases = [run_case(case) for case in CONFIG["cases"]]
by_ratio = {round(case["throat_to_fibre_diameter_ratio"], 6): case for case in cases}
blocked = by_ratio[0.8]; marginal = by_ratio[1.0]; passable = max(cases, key=lambda x: x["throat_to_fibre_diameter_ratio"])
gates = CONFIG["gates"]
checks = {
    "analytical_geometry": all(case["analytical_throat_relative_error"] <= 1e-12 for case in cases),
    "finite_and_bond_complete": all(case["terminal_internal_real_bond_count"] == N - 1 for case in cases),
    "penetration_guard": all(case["maximum_penetration_over_fibre_radius"] <= float(gates["maximum_penetration_over_fibre_radius"]) for case in cases),
    "ratio_0p8_persistent_contact": blocked["minimum_terminal_contact_count"] >= 1,
    "ratio_0p8_no_node_passage": blocked["terminal_nodes_beyond_throat"] == 0,
    "ratio_0p8_advance_bounded": blocked["terminal_leading_node_advance_m"] <= float(gates["maximum_blocked_leading_advance_m"]),
    "lbs_d50_no_contact": passable["maximum_recorded_contact_count"] == 0,
    "lbs_d50_node_passage": passable["terminal_nodes_beyond_throat"] >= int(gates["minimum_passable_nodes_beyond_throat"]),
    "lbs_d50_advance": passable["terminal_leading_node_advance_m"] >= float(gates["minimum_passable_leading_advance_m"]),
    "passage_contrast": passable["terminal_leading_node_advance_m"] - blocked["terminal_leading_node_advance_m"] >= float(gates["minimum_passage_contrast_m"]),
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage26u-three-grain-throat-result.v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed, "status": "throat_screen_verified" if passed else "throat_screen_not_qualified",
    "cases": cases, "checks": checks,
    "marginal_ratio_1p0_observation": {"terminal_leading_node_advance_m": marginal["terminal_leading_node_advance_m"],
        "terminal_nodes_beyond_throat": marginal["terminal_nodes_beyond_throat"],
        "minimum_terminal_contact_count": marginal["minimum_terminal_contact_count"],
        "classification": "marginal_transition_observed_without_forced_acceptance_class"},
    "elapsed_wall_s": time.time() - started,
    "source_hashes": {"config": sha256(CONFIG_PATH), "runner": sha256(RUNNER_PATH)},
    "authority": CONFIG["authority"], "claim_boundary": CONFIG["claim_boundary"],
}
result_path = os.path.join(OUTPUT, "result.json")
with open(result_path, "x") as stream: json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
completion = {"schema": "lbs.stage26u-three-grain-throat-completion.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": passed, "status": result["status"],
    "checks": checks, "result": {"path": result_path, "sha256": sha256(result_path)}, "authority": CONFIG["authority"]}
with open(os.path.join(OUTPUT, "completion.json"), "x") as stream: json.dump(completion, stream, indent=2, sort_keys=True); stream.write("\n")
print(json.dumps(completion, indent=2, sort_keys=True)); raise SystemExit(0 if passed else 2)
