#!/usr/bin/env python3
"""Probe one frictionless YADE sphere–GridConnection contact."""

from __future__ import print_function

import hashlib
import json
import os
from datetime import datetime, timezone

from yade import utils
from yade.gridpfacet import gridConnection, gridNode

OUT = os.environ["STAGE26T_OUTPUT"]
if os.path.exists(OUT):
    raise RuntimeError("refusing to overwrite %s" % OUT)
os.makedirs(OUT)

E = 53.0e6
RF = 50.0e-6
RS = 0.5 * 0.0008225865451029433
OVERLAP = 1.0e-6

internal = O.materials.append(CohFrictMat(young=E, poisson=0.30, density=940.0, frictionAngle=0.0,
    normalCohesion=1.0e20, shearCohesion=1.0e20, momentRotationLaw=True, label="internal"))
external = O.materials.append(FrictMat(young=E, poisson=0.25, density=940.0, frictionAngle=0.0, label="external"))
sand = O.materials.append(FrictMat(young=E, poisson=0.25, density=2650.0, frictionAngle=0.0, label="sand"))

O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_GridConnection_Aabb()]),
    InteractionLoop(
        [Ig2_GridNode_GridNode_GridNodeGeom6D(), Ig2_Sphere_GridConnection_ScGridCoGeom()],
        [Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionNow=True, setCohesionOnNewContacts=True),
         Ip2_FrictMat_FrictMat_FrictPhys()],
        [Law2_ScGeom6D_CohFrictPhys_CohesionMoment(), Law2_ScGridCoGeom_FrictPhys_CundallStrack()],
    ),
    NewtonIntegrator(gravity=(0, 0, 0), damping=0.70),
]
n0 = O.bodies.append(gridNode([-0.1e-3, 0, 0], RF, fixed=True, material=internal))
n1 = O.bodies.append(gridNode([0.1e-3, 0, 0], RF, fixed=True, material=internal))
connection = O.bodies.append(gridConnection(n0, n1, RF, material=external))
sphere_id = O.bodies.append(utils.sphere((0, RS + RF - OVERLAP, 0), RS, fixed=True, material=sand))
O.dt = 1.0e-9
O.step()

contacts = []
for interaction in O.interactions:
    if not interaction.isReal:
        continue
    ids = {int(interaction.id1), int(interaction.id2)}
    if sphere_id in ids and connection in ids:
        contacts.append(interaction)
if len(contacts) != 1:
    raise RuntimeError("expected exactly one real sphere-grid contact, found %d" % len(contacts))
i = contacts[0]
penetration = float(i.geom.penetrationDepth)
normal_force = [float(v) for v in i.phys.normalForce]
reaction = [float(v) for v in O.forces.f(sphere_id)]
payload = {
    "schema": "lbs.stage26t-sphere-grid-contact-probe.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": penetration > 0 and float(i.phys.kn) > 0 and reaction[1] > 0,
    "inputs": {"young_pa": E, "fibre_radius_m": RF, "sand_radius_m": RS, "imposed_overlap_m": OVERLAP},
    "contact": {"penetration_m": penetration, "kn_n_per_m": float(i.phys.kn), "ks_n_per_m": float(i.phys.ks),
                "normal_force_vector_n": normal_force, "sphere_reaction_vector_n": reaction},
    "force_balance": {"reaction_magnitude_over_kn_overlap": reaction[1] / (float(i.phys.kn) * penetration)},
    "claim_boundary": "One fixed frictionless sphere-grid contact API probe only; no material calibration or caging claim.",
}
path = os.path.join(OUT, "probe.json")
with open(path, "x") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")
h = hashlib.sha256(open(path, "rb").read()).hexdigest()
print(json.dumps({"path": path, "sha256": h, "payload": payload}, indent=2, sort_keys=True))
raise SystemExit(0 if payload["passed"] else 2)
