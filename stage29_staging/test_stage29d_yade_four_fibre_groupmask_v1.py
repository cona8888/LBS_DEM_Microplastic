#!/usr/bin/env python3
"""YADE integration test for four-fibre structural self-contact filtering."""
from __future__ import print_function

import hashlib
import json
import math
import os
from datetime import datetime, timezone

from yade import config
from yade.gridpfacet import gridConnection, gridNode

OUTPUT = os.environ["STAGE29D_UNIT_OUTPUT"]
SCRIPT = "/mnt/c/MATDEM_MICROPLASTIC/stage29_staging/test_stage29d_yade_four_fibre_groupmask_v1.py"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def norm(value):
    return math.sqrt(sum(float(x) ** 2 for x in value))


if os.path.exists(OUTPUT):
    raise RuntimeError("refusing to overwrite immutable output")
os.makedirs(OUTPUT)
r = 50e-6
coh = O.materials.append(CohFrictMat(young=53e6, poisson=.3, density=940,
    frictionAngle=0, normalCohesion=1e20, shearCohesion=1e20, momentRotationLaw=True))
frict = O.materials.append(FrictMat(young=53e6, poisson=.25, density=940, frictionAngle=0))
O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_GridConnection_Aabb()], avoidSelfInteractionMask=30),
    InteractionLoop(
        [Ig2_GridNode_GridNode_GridNodeGeom6D(), Ig2_GridConnection_GridConnection_GridCoGridCoGeom()],
        [Ip2_FrictMat_FrictMat_FrictPhys(), Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionNow=True, setCohesionOnNewContacts=True)],
        [Law2_ScGeom6D_CohFrictPhys_CohesionMoment(), Law2_GridCoGridCoGeom_FrictPhys_CundallStrack()],
    ),
    NewtonIntegrator(gravity=(0, 0, 0), damping=.2),
]

definitions = [
    [(-37.5e-6, 0, 0), (-12.5e-6, 0, 0), (12.5e-6, 0, 0), (37.5e-6, 0, 0)],
    [(25e-6, -0.2e-3, 80e-6), (25e-6, -0.066e-3, 80e-6), (25e-6, 0.066e-3, 80e-6), (25e-6, 0.2e-3, 80e-6)],
    [(-0.4e-3, -0.2e-3, 0.4e-3), (-0.3e-3, -0.1e-3, 0.4e-3), (-0.2e-3, 0, 0.4e-3), (-0.1e-3, 0.1e-3, 0.4e-3)],
    [(0.1e-3, -0.2e-3, -0.4e-3), (0.2e-3, -0.1e-3, -0.4e-3), (0.3e-3, 0, -0.4e-3), (0.4e-3, 0.1e-3, -0.4e-3)],
]
masks = [3, 5, 9, 17]
node_groups, connection_groups = [], []
for positions, mask in zip(definitions, masks):
    nodes = [int(O.bodies.append(gridNode(p, r, fixed=True, material=coh))) for p in positions]
    connections = [int(O.bodies.append(gridConnection(a, b, r, material=frict))) for a, b in zip(nodes[:-1], nodes[1:])]
    for body_id in nodes + connections:
        O.bodies[body_id].groupMask = mask
    node_groups.append(nodes)
    connection_groups.append(connections)

O.dt = 1e-8
O.run(5, True)
self_contacts = []
cross_contacts = []
for item in O.interactions:
    if not item.isReal:
        continue
    a, b = int(item.id1), int(item.id2)
    owners = [i for i, ids in enumerate(connection_groups) if a in ids or b in ids]
    if a in sum(connection_groups, []) and b in sum(connection_groups, []):
        if len(set(owners)) == 1:
            self_contacts.append(item)
        elif len(set(owners)) == 2:
            cross_contacts.append(item)
internal_counts = []
for nodes in node_groups:
    node_set = set(nodes)
    internal_counts.append(sum(1 for item in O.interactions if item.isReal and int(item.id1) in node_set and int(item.id2) in node_set))
forces = [norm(item.phys.normalForce) for item in cross_contacts]
checks = {
    "terminal_same_fibre_grid_contacts_zero": len(self_contacts) == 0,
    "terminal_cross_fibre_grid_contact_present": len(cross_contacts) >= 1,
    "cross_fibre_physics_noncohesive": all(item.phys.__class__.__name__ == "FrictPhys" for item in cross_contacts),
    "cross_fibre_force_positive_finite": bool(forces) and all(math.isfinite(v) and v > 0 for v in forces),
    "all_internal_bonds_preserved": internal_counts == [3, 3, 3, 3],
    "group_masks_exact": all(O.bodies[body_id].groupMask == masks[i] for i in range(4) for body_id in node_groups[i] + connection_groups[i]),
}
passed = all(checks.values())
result = {
    "schema": "lbs.stage29d-yade-four-fibre-groupmask-unit.v1",
    "status": "passed_four_fibre_structural_filter" if passed else "unit_test_failed",
    "passed": passed,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
    "metrics": {"self_contact_count": len(self_contacts), "cross_contact_count": len(cross_contacts), "internal_bond_counts": internal_counts, "cross_normal_forces_n": forces, "avoid_self_interaction_mask": 30, "fibre_group_masks": masks},
    "environment": {"yade_version": str(config.version)},
    "source": {"path": SCRIPT, "sha256": sha(SCRIPT)},
    "claim_boundary": "Four-fibre grid-mask API test only; no sand or application mechanics claim.",
}
with open(os.path.join(OUTPUT, "result.json"), "x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
raise SystemExit(0 if passed else 4)
