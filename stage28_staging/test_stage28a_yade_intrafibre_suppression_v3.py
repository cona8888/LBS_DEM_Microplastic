#!/usr/bin/env python3
"""YADE selective-contact unit test at the Stage28a 25-micrometre segment scale."""

from __future__ import print_function

import hashlib
import json
import math
import os
from datetime import datetime, timezone

from yade import config
from yade.gridpfacet import gridConnection, gridNode


OUTPUT = os.environ["STAGE28A_UNIT_OUTPUT"]
SCRIPT = "/mnt/c/MATDEM_MICROPLASTIC/stage28_staging/test_stage28a_yade_intrafibre_suppression_v3.py"
OWNER = {}
ERASED = 0


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def norm(value):
    return math.sqrt(sum(float(x) ** 2 for x in value))


def suppress_self():
    global ERASED
    targets = []
    for interaction in O.interactions:
        a, b = int(interaction.id1), int(interaction.id2)
        if a in OWNER and b in OWNER and OWNER[a] == OWNER[b]:
            targets.append((a, b))
    for a, b in targets:
        O.interactions.erase(a, b)
    ERASED += len(targets)


if os.path.exists(OUTPUT):
    raise RuntimeError("refusing to overwrite immutable output")
os.makedirs(OUTPUT)
r = 50e-6
coh = O.materials.append(CohFrictMat(young=53e6, poisson=.3, density=940,
    frictionAngle=0, normalCohesion=1e20, shearCohesion=1e20, momentRotationLaw=True))
frict = O.materials.append(FrictMat(young=53e6, poisson=.25, density=940, frictionAngle=0))
O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_GridConnection_Aabb()]),
    PyRunner(iterPeriod=1, command="suppress_self()"),
    InteractionLoop(
        [Ig2_GridNode_GridNode_GridNodeGeom6D(),
         Ig2_GridConnection_GridConnection_GridCoGridCoGeom()],
        [Ip2_FrictMat_FrictMat_FrictPhys(),
         Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(
             setCohesionNow=True, setCohesionOnNewContacts=True)],
        [Law2_ScGeom6D_CohFrictPhys_CohesionMoment(),
         Law2_GridCoGridCoGeom_FrictPhys_CundallStrack()],
    ),
    NewtonIntegrator(gravity=(0, 0, 0), damping=.2),
]

# Three short collinear segments: non-neighbouring segments overlap geometrically.
x_values = [-37.5e-6, -12.5e-6, 12.5e-6, 37.5e-6]
nodes0 = [int(O.bodies.append(gridNode((x, 0, 0), r, fixed=True, material=coh))) for x in x_values]
connections0 = [int(O.bodies.append(gridConnection(a, b, r, material=frict)))
                for a, b in zip(nodes0[:-1], nodes0[1:])]
# A different fibre crosses the last segment with a known 20-micrometre overlap.
nodes1 = [
    int(O.bodies.append(gridNode((25e-6, -0.2e-3, 80e-6), r, fixed=True, material=coh))),
    int(O.bodies.append(gridNode((25e-6, 0.2e-3, 80e-6), r, fixed=True, material=coh))),
]
connection1 = int(O.bodies.append(gridConnection(nodes1[0], nodes1[1], r, material=frict)))
for body_id in connections0:
    OWNER[body_id] = 0
OWNER[connection1] = 1

O.dt = 1e-8
O.run(5, True)
self_contacts = [item for item in O.interactions if item.isReal
                 and int(item.id1) in connections0 and int(item.id2) in connections0]
cross = [item for item in O.interactions if item.isReal and
         ((int(item.id1) in connections0 and int(item.id2) == connection1) or
          (int(item.id2) in connections0 and int(item.id1) == connection1))]
forces = [norm(item.phys.normalForce) for item in cross]
checks = {
    "suppression_hook_erased_same_fibre_candidates": ERASED > 0,
    "terminal_same_fibre_contacts_zero": len(self_contacts) == 0,
    "terminal_cross_fibre_contact_present": len(cross) >= 1,
    "cross_fibre_physics_is_noncohesive": all(item.phys.__class__.__name__ == "FrictPhys" for item in cross),
    "cross_fibre_force_positive_finite": bool(forces) and all(math.isfinite(v) and v > 0 for v in forces),
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage28a-yade-intrafibre-suppression-unit.v3",
    "status": "passed_selective_grid_contact_suppression" if passed else "unit_test_failed",
    "passed": passed,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
    "metrics": {"cumulative_erased_same_fibre_candidates": ERASED,
                "terminal_same_fibre_contact_count": len(self_contacts),
                "terminal_cross_fibre_contact_count": len(cross),
                "cross_fibre_normal_forces_n": forces},
    "environment": {"yade_version": str(config.version)},
    "source": {"path": SCRIPT, "sha256": sha(SCRIPT)},
    "claim_boundary": "Fixed 25-micrometre segment API test; no sand or full mechanics claim.",
}
with open(os.path.join(OUTPUT, "result.json"), "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
raise SystemExit(0 if passed else 4)
