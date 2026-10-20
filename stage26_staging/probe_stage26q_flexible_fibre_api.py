"""Read-only YADE namespace probe for the Stage26q flexible-fibre design."""

names = [
    "CohFrictMat",
    "CohFrictPhys",
    "Ip2_CohFrictMat_CohFrictMat_CohFrictPhys",
    "Law2_ScGeom6D_CohFrictPhys_CohesionMoment",
    "ScGeom6D",
    "Ig2_Sphere_Sphere_ScGeom6D",
    "GridConnection",
    "gridConnection",
]

for name in names:
    obj = globals().get(name)
    print("STAGE26Q_API %s=%s" % (name, obj is not None))

raise SystemExit(0)
