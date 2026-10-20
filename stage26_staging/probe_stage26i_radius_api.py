from __future__ import print_function

body_id = O.bodies.append(sphere((0, 0, 0), 5e-5))
before = float(O.bodies[body_id].shape.radius)
O.bodies[body_id].shape.radius = 5.05e-5
after = float(O.bodies[body_id].shape.radius)
assert abs(before - 5e-5) < 1e-15
assert abs(after - 5.05e-5) < 1e-15
print("STAGE26I_RADIUS_API_OK before=%r after=%r" % (before, after), flush=True)
