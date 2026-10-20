"""Bounded YADE 2022.01a smoke test for Stage26o wall, clump, and gravity APIs."""
from __future__ import print_function

import json
import math
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(os.environ.get("STAGE26O_SMOKE_SCRIPT", __file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from yade import config, utils
from stage26b_revision2_prefilter_common_v1 import load_json, sha256, write_json_exclusive

OBSERVED_WALL_CONTACTS = set()
MAXIMUM_PENETRATION = 0.0


def capture_contacts():
    global MAXIMUM_PENETRATION
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        if (first in SMOKE_WALL_SET and second in SMOKE_DYNAMIC_SET) or (second in SMOKE_WALL_SET and first in SMOKE_DYNAMIC_SET):
            OBSERVED_WALL_CONTACTS.add((first, second))
        MAXIMUM_PENETRATION = max(MAXIMUM_PENETRATION, max(0.0, float(interaction.geom.penetrationDepth)))


def main():
    design_path = os.path.abspath(os.environ["STAGE26O_DESIGN"])
    output = os.path.abspath(os.environ["STAGE26O_SMOKE_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26O_SMOKE_SCRIPT", __file__))
    design = load_json(design_path)
    if design.get("status") != "design_frozen_execution_not_yet_authorized":
        raise RuntimeError("unexpected Stage26o design status")
    if design["authority"].get("api_smoke_authorized") is not True:
        raise RuntimeError("Stage26o API smoke is not authorized")
    if str(config.version) != str(design["verification_before_execution"]["installed_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26o smoke output exists")
    os.makedirs(output)

    O.reset()
    O.periodic = False
    sand_mat = O.materials.append(FrictMat(young=5.3e7, poisson=0.25, frictionAngle=math.atan(0.6), density=2650.0, label="smoke_sand"))
    fibre_mat = O.materials.append(FrictMat(young=5.3e7, poisson=0.25, frictionAngle=math.atan(0.45), density=940.0, label="smoke_fibre"))
    wall_mat = O.materials.append(FrictMat(young=5.3e7, poisson=0.25, frictionAngle=0.0, density=0.0, label="smoke_walls"))
    wall_ids = [int(value) for value in O.bodies.append(aabbWalls([Vector3(0, 0, 0), Vector3(0.004, 0.004, 0.004)], thickness=0, material=wall_mat))]
    sand_id = int(O.bodies.append(sphere(Vector3(0.0026, 0.0022, 0.00055), 0.0004, material=sand_mat)))
    clump_parent, clump_members = O.bodies.appendClumped([
        sphere(Vector3(0.0014, 0.0018, 0.00030), 0.00012, material=fibre_mat),
        sphere(Vector3(0.0016, 0.0018, 0.00030), 0.00012, material=fibre_mat),
    ], 20)
    clump_parent, clump_members = int(clump_parent), [int(value) for value in clump_members]
    global SMOKE_WALL_SET, SMOKE_DYNAMIC_SET
    SMOKE_WALL_SET, SMOKE_DYNAMIC_SET = set(wall_ids), set([sand_id] + clump_members)
    initial_z = {sand_id: float(O.bodies[sand_id].state.pos[2]), clump_parent: float(O.bodies[clump_parent].state.pos[2])}
    time_stepper = GlobalStiffnessTimeStepper(active=True, timeStepUpdateInterval=1, timestepSafetyCoefficient=0.1, label="smoke_time_stepper")
    newton = NewtonIntegrator(damping=0.7, gravity=Vector3(0, 0, -9.81), label="smoke_newton")
    O.engines = [
        ForceResetter(),
        InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_Box_Aabb()]),
        InteractionLoop(
            [Ig2_Sphere_Sphere_ScGeom(), Ig2_Box_Sphere_ScGeom()],
            [Ip2_FrictMat_FrictMat_FrictPhys()],
            [Law2_ScGeom_FrictPhys_CundallStrack()],
        ),
        PyRunner(iterPeriod=1, command="capture_contacts()"),
        time_stepper,
        newton,
    ]
    O.step()
    # Keep the smoke bodies near the floor: the 50 um-scale clump controls
    # O.dt (~5e-8 s), so this still covers the local contact-onset time.
    O.run(300000, True)
    wall_contacts = [list(pair) for pair in sorted(OBSERVED_WALL_CONTACTS)]
    max_penetration = MAXIMUM_PENETRATION
    final_z = {sand_id: float(O.bodies[sand_id].state.pos[2]), clump_parent: float(O.bodies[clump_parent].state.pos[2])}
    controller = TriaxialStressController(internalCompaction=False, stressMask=7, thickness=0)
    controller.goal1 = controller.goal2 = controller.goal3 = -100.0
    controller_api = {
        "class": controller.__class__.__name__,
        "has_goal1": hasattr(controller, "goal1"), "has_goal2": hasattr(controller, "goal2"),
        "has_goal3": hasattr(controller, "goal3"), "has_meanStress": hasattr(controller, "meanStress"),
        "has_porosity": hasattr(controller, "porosity"), "has_internalCompaction": hasattr(controller, "internalCompaction"),
    }
    checks = {
        "six_walls_created": len(wall_ids) == 6,
        "sand_fell": final_z[sand_id] < initial_z[sand_id],
        "clump_fell": final_z[clump_parent] < initial_z[clump_parent],
        "wall_contact_detected": len(wall_contacts) >= 2,
        "finite_time_step": math.isfinite(float(O.dt)) and float(O.dt) > 0,
        "finite_kinetic_energy": math.isfinite(float(utils.kineticEnergy())),
        "controller_api_present": all(controller_api[key] for key in controller_api if key.startswith("has_")),
        "clump_membership_preserved": all(O.bodies[member].isClumpMember for member in clump_members),
    }
    result = {
        "schema": "lbs.stage26o-wall-gravity-api-smoke-result.v1", "passed": all(checks.values()),
        "status": "wall_gravity_clump_and_controller_api_smoke_passed" if all(checks.values()) else "api_smoke_failed",
        "checks": checks, "yade_version": str(config.version), "wall_ids": wall_ids,
        "sand_id": sand_id, "clump_parent_id": clump_parent, "clump_member_ids": clump_members,
        "initial_z_m": dict((str(key), value) for key, value in initial_z.items()),
        "final_z_m": dict((str(key), value) for key, value in final_z.items()),
        "wall_contact_count": len(wall_contacts), "wall_contact_pairs": wall_contacts,
        "maximum_absolute_penetration_m": max_penetration, "time_step_s": float(O.dt),
        "kinetic_energy_j": float(utils.kineticEnergy()), "controller_api": controller_api,
        "source_hashes": {"design": sha256(design_path), "smoke_runner": sha256(script_path)},
        "authority": {"clean_sand_control_authorized": False, "mixture_authorized": False,
                      "flow_execution_authorized": False, "deformation_authorized": False},
        "claim_boundary": design["claim_boundary"], "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    result_path = os.path.join(output, "smoke_result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26o-wall-gravity-api-smoke-completion.v1", "passed": result["passed"],
        "status": result["status"], "result_sha256": sha256(result_path),
        "source_hashes": result["source_hashes"], "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": design["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26O_SMOKE=" + json.dumps({"passed": result["passed"], "checks": checks, "completion_sha256": sha256(completion_path)}, sort_keys=True), flush=True)
    if not result["passed"]:
        raise RuntimeError("Stage26o API smoke failed")


if __name__ == "__main__":
    main()
