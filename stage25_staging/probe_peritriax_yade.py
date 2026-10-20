from __future__ import print_function

import json

from yade import config, pack


O.periodic = True
O.cell.hSize = Matrix3(0.01, 0, 0, 0, 0.01, 0, 0, 0, 0.01)
material = O.materials.append(FrictMat(young=5.3e7, poisson=0.5, frictionAngle=atan(0.45), density=2650.0))
cloud = pack.SpherePack()
cloud.makeCloud(Vector3.Zero, Vector3(0.01, 0.01, 0.01), rMean=0.0004, rRelFuzz=0.1, num=64, periodic=True, seed=25)
cloud.toSimulation(material=material)
triax = PeriTriaxController(
    goal=(-100.0, -100.0, -100.0), stressMask=7, dynCell=True,
    maxStrainRate=(0.2, 0.2, 0.2), relStressTol=0.05,
    maxUnbalanced=0.10, label="triax",
)
O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_Sphere_Aabb()], allowBiggerThanPeriod=True),
    InteractionLoop(
        [Ig2_Sphere_Sphere_ScGeom()],
        [Ip2_FrictMat_FrictMat_FrictPhys()],
        [Law2_ScGeom_FrictPhys_CundallStrack()],
    ),
    GlobalStiffnessTimeStepper(active=True, timeStepUpdateInterval=20, timestepSafetyCoefficient=0.4),
    triax,
    NewtonIntegrator(damping=0.35),
]
O.step()
print("STAGE25_PERITRIAX_PROBE=" + json.dumps({
    "yade_version": str(config.version),
    "goal": [float(x) for x in triax.goal],
    "stress_mask": int(triax.stressMask),
    "dyn_cell": bool(triax.dynCell),
    "max_strain_rate": [float(x) for x in triax.maxStrainRate],
    "particle_count": len([b for b in O.bodies if b is not None and isinstance(b.shape, Sphere)]),
}, sort_keys=True))
