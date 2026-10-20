#!/usr/bin/env python3
"""Integration-only adapter for the Stage26x periodic-cell synchronization handoff."""

import hashlib
import os


CORE = "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26x_periodic_fixed_sand_fibre_v1.py"
EXPECTED_CORE_SHA256 = "__BOUND_BY_DESIGN_BUILDER__"


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


with open(os.environ["STAGE26X_CONFIG"], "r") as stream:
    import json
    cfg = json.load(stream)
expected = cfg["sources"]["core_runner"]["sha256"]
if sha(CORE) != expected:
    raise RuntimeError("Stage26x v1 core hash mismatch")
source = open(CORE, "r").read()
old_runner = 'RUNNER = "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26x_periodic_fixed_sand_fibre_v1.py"'
new_runner = 'RUNNER = "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26x_periodic_fixed_sand_fibre_v2.py"'
old_handoff = '''    initial = {body_id: [float(value) for value in O.bodies[body_id].state.pos] for body_id in sand_ids}
    return sand_ids, initial, loaded_hsize'''
new_handoff = '''    initial = {body_id: [float(value) for value in O.bodies[body_id].state.pos] for body_id in sand_ids}
    O.step()
    O.cell.hSize = loaded_hsize
    O.cell.velGrad = Matrix3.Zero
    for body_id in sand_ids:
        O.bodies[body_id].state.pos = Vector3(*initial[body_id])
        O.bodies[body_id].state.vel = Vector3.Zero
        O.bodies[body_id].state.angVel = Vector3.Zero
    return sand_ids, initial, loaded_hsize'''
if source.count(old_runner) != 1 or source.count(old_handoff) != 1:
    raise RuntimeError("Stage26x v1 adapter anchors are not unique")
adapted = source.replace(old_runner, new_runner).replace(old_handoff, new_handoff)
exec(compile(adapted, CORE + "[cell-sync-v2]", "exec"), globals(), globals())
