#!/usr/bin/env python3
"""YADE unit test for noncohesive contact between two flexible grid segments."""

from __future__ import print_function

import hashlib
import json
import math
import os
from datetime import datetime, timezone

from yade import config
from yade.gridpfacet import gridConnection, gridNode


OUTPUT = os.environ["STAGE28A_UNIT_OUTPUT"]
SCRIPT = "/mnt/c/MATDEM_MICROPLASTIC/stage28_staging/test_stage28a_yade_grid_grid_contact_v1.py"


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def norm3(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


if os.path.exists(OUTPUT):
    raise RuntimeError("refusing to overwrite immutable unit-test output")
os.makedirs(OUTPUT)
radius = 50.0e-6
young = 53.0e6
internal = O.materials.append(
    CohFrictMat(
        young=young,
        poisson=0.3,
        density=940.0,
        frictionAngle=0.0,
        normalCohesion=1.0e20,
        shearCohesion=1.0e20,
        momentRotationLaw=True,
    )
)
external = O.materials.append(
    FrictMat(young=young, poisson=0.25, density=940.0, frictionAngle=0.0)
)
O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_GridConnection_Aabb()]),
    InteractionLoop(
        [
            Ig2_GridNode_GridNode_GridNodeGeom6D(),
            Ig2_GridConnection_GridConnection_GridCoGridCoGeom(),
        ],
        [
            Ip2_FrictMat_FrictMat_FrictPhys(),
            Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(
                setCohesionNow=True, setCohesionOnNewContacts=True
            ),
        ],
        [
            Law2_ScGeom6D_CohFrictPhys_CohesionMoment(),
            Law2_GridCoGridCoGeom_FrictPhys_CundallStrack(),
        ],
    ),
    NewtonIntegrator(gravity=(0, 0, 0), damping=0.2),
]

first_nodes = [
    int(O.bodies.append(gridNode((-0.2e-3, 0.0, 0.0), radius, fixed=True, material=internal))),
    int(O.bodies.append(gridNode((0.2e-3, 0.0, 0.0), radius, fixed=True, material=internal))),
]
second_nodes = [
    int(O.bodies.append(gridNode((0.0, -0.2e-3, 0.08e-3), radius, fixed=True, material=internal))),
    int(O.bodies.append(gridNode((0.0, 0.2e-3, 0.08e-3), radius, fixed=True, material=internal))),
]
first_connection = int(
    O.bodies.append(
        gridConnection(first_nodes[0], first_nodes[1], radius, material=external)
    )
)
second_connection = int(
    O.bodies.append(
        gridConnection(second_nodes[0], second_nodes[1], radius, material=external)
    )
)
O.dt = 1.0e-8
O.run(5, True)

cross = [
    item
    for item in O.interactions
    if item.isReal and {int(item.id1), int(item.id2)} == {first_connection, second_connection}
]
cross_nodes = [
    item
    for item in O.interactions
    if item.isReal
    and (
        (int(item.id1) in first_nodes and int(item.id2) in second_nodes)
        or (int(item.id2) in first_nodes and int(item.id1) in second_nodes)
    )
]
interaction = cross[0] if len(cross) == 1 else None
penetration = (
    float(getattr(interaction.geom, "penetrationDepth", float("nan")))
    if interaction is not None
    else float("nan")
)
force = norm3(interaction.phys.normalForce) if interaction is not None else 0.0
checks = {
    "exact_one_grid_grid_contact": len(cross) == 1,
    "geometry_class": interaction is not None
    and interaction.geom.__class__.__name__ == "GridCoGridCoGeom",
    "noncohesive_physics_class": interaction is not None
    and interaction.phys.__class__.__name__ == "FrictPhys",
    "positive_finite_penetration": math.isfinite(penetration) and penetration > 0.0,
    "positive_finite_normal_force": math.isfinite(force) and force > 0.0,
    "no_cross_node_bond": len(cross_nodes) == 0,
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage28a-yade-grid-grid-contact-unit.v1",
    "status": "passed_noncohesive_grid_grid_contact" if passed else "unit_test_failed",
    "passed": passed,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
    "metrics": {
        "penetration_m": penetration,
        "normal_force_n": force,
        "cross_node_real_interaction_count": len(cross_nodes),
    },
    "environment": {"yade_version": str(config.version)},
    "source": {"path": SCRIPT, "sha256": sha(SCRIPT)},
    "claim_boundary": "Two fixed grid segments only; API/contact-law unit verification, not a sand-fibre mechanics result.",
}
path = os.path.join(OUTPUT, "result.json")
with open(path, "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
raise SystemExit(0 if passed else 4)

