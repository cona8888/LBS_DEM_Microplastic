#!/usr/bin/env python3
"""YADE unit test: suppress same-fibre grid contact, retain cross-fibre contact."""

from __future__ import print_function

import hashlib
import json
import math
import os
from datetime import datetime, timezone

from yade import config
from yade.gridpfacet import gridConnection, gridNode


OUTPUT = os.environ["STAGE28A_UNIT_OUTPUT"]
SCRIPT = "/mnt/c/MATDEM_MICROPLASTIC/stage28_staging/test_stage28a_yade_intrafibre_suppression_v2.py"
CONNECTION_OWNER = {}
ERASED_INTRAFIBRE = 0


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def norm3(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


def suppress_intrafibre_grid_contacts():
    global ERASED_INTRAFIBRE
    erase = []
    for item in O.interactions:
        first, second = int(item.id1), int(item.id2)
        if (
            first in CONNECTION_OWNER
            and second in CONNECTION_OWNER
            and CONNECTION_OWNER[first] == CONNECTION_OWNER[second]
        ):
            erase.append((first, second))
    for first, second in erase:
        O.interactions.erase(first, second)
    ERASED_INTRAFIBRE += len(erase)


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
    PyRunner(iterPeriod=1, command="suppress_intrafibre_grid_contacts()"),
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

# Fibre 0: two adjacent segments sharing the middle node.
nodes0 = [
    int(O.bodies.append(gridNode((-0.2e-3, 0.0, 0.0), radius, fixed=True, material=internal))),
    int(O.bodies.append(gridNode((0.0, 0.0, 0.0), radius, fixed=True, material=internal))),
    int(O.bodies.append(gridNode((0.2e-3, 0.0, 0.0), radius, fixed=True, material=internal))),
]
connections0 = [
    int(O.bodies.append(gridConnection(nodes0[0], nodes0[1], radius, material=external))),
    int(O.bodies.append(gridConnection(nodes0[1], nodes0[2], radius, material=external))),
]
# Fibre 1: one segment crossing fibre 0 with 20 micrometres overlap.
nodes1 = [
    int(O.bodies.append(gridNode((0.1e-3, -0.2e-3, 0.08e-3), radius, fixed=True, material=internal))),
    int(O.bodies.append(gridNode((0.1e-3, 0.2e-3, 0.08e-3), radius, fixed=True, material=internal))),
]
connection1 = int(
    O.bodies.append(gridConnection(nodes1[0], nodes1[1], radius, material=external))
)
for body_id in connections0:
    CONNECTION_OWNER[body_id] = 0
CONNECTION_OWNER[connection1] = 1

O.dt = 1.0e-8
O.run(5, True)
intrafibre = [
    item
    for item in O.interactions
    if item.isReal and {int(item.id1), int(item.id2)} == set(connections0)
]
cross = [
    item
    for item in O.interactions
    if item.isReal
    and (
        (int(item.id1) in connections0 and int(item.id2) == connection1)
        or (int(item.id2) in connections0 and int(item.id1) == connection1)
    )
]
forces = [norm3(item.phys.normalForce) for item in cross]
checks = {
    "same_fibre_grid_contact_absent": len(intrafibre) == 0,
    "cross_fibre_grid_contact_present": len(cross) >= 1,
    "cross_fibre_physics_noncohesive": all(
        item.phys.__class__.__name__ == "FrictPhys" for item in cross
    ),
    "cross_fibre_force_positive_finite": bool(forces)
    and all(math.isfinite(value) and value > 0.0 for value in forces),
    "suppression_hook_activated": ERASED_INTRAFIBRE > 0,
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage28a-yade-intrafibre-suppression-unit.v2",
    "status": "passed_selective_grid_contact_suppression" if passed else "unit_test_failed",
    "passed": passed,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
    "metrics": {
        "terminal_intrafibre_real_contact_count": len(intrafibre),
        "terminal_cross_fibre_real_contact_count": len(cross),
        "cross_fibre_normal_forces_n": forces,
        "cumulative_erased_intrafibre_candidates": ERASED_INTRAFIBRE,
    },
    "environment": {"yade_version": str(config.version)},
    "source": {"path": SCRIPT, "sha256": sha(SCRIPT)},
    "claim_boundary": "Fixed three-segment API unit test only; no sand or full-fibre mechanics claim.",
}
path = os.path.join(OUTPUT, "result.json")
with open(path, "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
raise SystemExit(0 if passed else 4)
