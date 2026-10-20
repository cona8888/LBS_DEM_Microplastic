#!/usr/bin/env python3
"""Record YADE GridConnection interaction stiffness for one isolated segment."""

from __future__ import print_function

import hashlib
import json
import os
from datetime import datetime, timezone

from yade.gridpfacet import gridConnection, gridNode


OUT = os.environ["STAGE26S_OUTPUT"]
if os.path.exists(OUT):
    raise RuntimeError("refusing to overwrite %s" % OUT)
os.makedirs(OUT)

E = 53.0e6
NU = 0.30
R = 50.0e-6
SEGMENT = 0.9e-3 / 36.0

mat = O.materials.append(CohFrictMat(
    young=E,
    poisson=NU,
    density=940.0,
    frictionAngle=0.0,
    normalCohesion=1.0e20,
    shearCohesion=1.0e20,
    momentRotationLaw=True,
    label="fibreInternal",
))

O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_GridConnection_Aabb()]),
    InteractionLoop(
        [Ig2_GridNode_GridNode_GridNodeGeom6D()],
        [Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionNow=True, setCohesionOnNewContacts=True)],
        [Law2_ScGeom6D_CohFrictPhys_CohesionMoment()],
    ),
    NewtonIntegrator(gravity=(0, 0, 0), damping=0.4),
]

n0 = O.bodies.append(gridNode([0, 0, 0], R, wire=False, fixed=True, material=mat))
n1 = O.bodies.append(gridNode([SEGMENT, 0, 0], R, wire=False, fixed=False, material=mat))
connection = O.bodies.append(gridConnection(n0, n1, R, material=mat))
O.dt = 1.0e-9
O.step()

interaction = O.interactions[n0, n1]
if not interaction or not interaction.isReal:
    raise RuntimeError("grid-node interaction was not created")

phys = interaction.phys
names = ["kn", "ks", "kr", "ktw", "alphaKr", "alphaKtw", "maxRollPl", "normalAdhesion", "shearAdhesion"]
values = {}
for name in names:
    if hasattr(phys, name):
        value = getattr(phys, name)
        try:
            values[name] = float(value)
        except Exception:
            values[name] = str(value)

payload = {
    "schema": "lbs.stage26s-grid-connection-stiffness-probe.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True,
    "inputs": {"young_pa": E, "poisson": NU, "radius_m": R, "segment_length_m": SEGMENT},
    "interaction_phys_class": phys.__class__.__name__,
    "interaction_geom_class": interaction.geom.__class__.__name__,
    "physics": values,
    "reference_stiffness": {
        "EA_over_L_n_per_m": E * 3.141592653589793 * R ** 2 / SEGMENT,
        "EI_over_L_n_m_per_rad": E * 3.141592653589793 * R ** 4 / (4.0 * SEGMENT),
    },
    "claim_boundary": "One isolated YADE grid connection API probe; no calibrated polymer or sand-mixture claim.",
}

path = os.path.join(OUT, "probe.json")
with open(path, "w") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")

h = hashlib.sha256()
with open(path, "rb") as stream:
    h.update(stream.read())
print(json.dumps({"path": path, "sha256": h.hexdigest(), "physics": values}, indent=2, sort_keys=True))
O.pause()
