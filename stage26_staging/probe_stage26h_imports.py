from __future__ import print_function

checks = {}
try:
    from minieigen import Vector3 as Vector3A
    checks["minieigen.Vector3"] = True
except Exception as exc:
    checks["minieigen.Vector3"] = repr(exc)
try:
    from yade.minieigenHP import Vector3 as Vector3B
    checks["yade.minieigenHP.Vector3"] = True
except Exception as exc:
    checks["yade.minieigenHP.Vector3"] = repr(exc)
try:
    from yade.wrapper import Sphere as SphereA
    checks["yade.wrapper.Sphere"] = True
except Exception as exc:
    checks["yade.wrapper.Sphere"] = repr(exc)
print("STAGE26H_IMPORT_PROBE=" + repr(checks), flush=True)
