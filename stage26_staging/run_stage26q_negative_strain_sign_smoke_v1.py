"""Short YADE kinematic smoke for the corrected Stage26q wall-rate sign."""
from __future__ import print_function

import hashlib
import json
import math
import os
from datetime import datetime, timezone

from yade import config


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def windows_to_wsl(path):
    path = str(path)
    if len(path) >= 3 and path[1:3] in (":\\", ":/"):
        return "/mnt/%s/%s" % (path[0].lower(), path[3:].replace("\\", "/"))
    return path


def write_json_exclusive(path, data):
    with open(path, "x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def find_engine(class_name):
    matches = [engine for engine in O.engines if engine.__class__.__name__ == class_name]
    if len(matches) != 1:
        raise RuntimeError("expected one %s, found %d" % (class_name, len(matches)))
    return matches[0]


def dimensions(triax):
    return [
        float(O.bodies[triax.wall_right_id].state.pos[0]) - float(O.bodies[triax.wall_left_id].state.pos[0]),
        float(O.bodies[triax.wall_top_id].state.pos[1]) - float(O.bodies[triax.wall_bottom_id].state.pos[1]),
        float(O.bodies[triax.wall_front_id].state.pos[2]) - float(O.bodies[triax.wall_back_id].state.pos[2]),
    ]


def main():
    config_path = os.path.abspath(os.environ["STAGE26Q_SMOKE_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26Q_SMOKE_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26Q_SMOKE_SCRIPT", __file__))
    with open(config_path, "r") as stream:
        cfg = json.load(stream)
    authority = cfg.get("authority", {})
    if authority.get("negative_sign_kinematic_smoke_authorized") is not True:
        raise RuntimeError("negative-sign smoke lacks authority")
    if authority.get("clean_density_controller_pilot_authorized") is not False:
        raise RuntimeError("full pilot must remain disabled during smoke")
    if float(cfg["density_ramp"]["isotropic_compressive_strain_rate_per_s"]) >= 0.0:
        raise RuntimeError("configured smoke rate is not negative")
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("YADE version mismatch")
    if os.path.exists(output):
        raise RuntimeError("immutable smoke output exists")
    input_binding = cfg["sources"]["input_state"]
    if sha256(windows_to_wsl(input_binding["path"])) != input_binding["sha256"]:
        raise RuntimeError("input state hash mismatch")
    os.makedirs(output)

    O.load(windows_to_wsl(input_binding["path"]))
    triax = find_engine("TriaxialStressController")
    newton = find_engine("NewtonIntegrator")
    stepper = find_engine("GlobalStiffnessTimeStepper")
    sand_ids = [int(body.id) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
    solid_volume = sum(4.0 * math.pi * float(O.bodies[body_id].shape.radius) ** 3 / 3.0 for body_id in sand_ids)
    initial_dimensions = dimensions(triax)
    initial_volume = initial_dimensions[0] * initial_dimensions[1] * initial_dimensions[2]
    initial_e = initial_volume / solid_volume - 1.0

    triax.internalCompaction = False
    triax.stressMask = 0
    rate = float(cfg["density_ramp"]["isotropic_compressive_strain_rate_per_s"])
    triax.goal1 = triax.goal2 = triax.goal3 = rate
    triax.dead = False
    newton.gravity = Vector3(0.0, 0.0, 0.0)
    newton.damping = float(cfg["density_ramp"]["newton_damping"])
    stepper.timestepSafetyCoefficient = float(cfg["density_ramp"]["timestep_safety_coefficient"])
    O.run(5000, True)
    triax.dead = True

    terminal_dimensions = dimensions(triax)
    terminal_volume = terminal_dimensions[0] * terminal_dimensions[1] * terminal_dimensions[2]
    terminal_e = terminal_volume / solid_volume - 1.0
    ratios = [terminal_dimensions[i] / initial_dimensions[i] for i in range(3)]
    checks = {
        "exact_216_sand": len(sand_ids) == 216,
        "negative_rate_configured": rate < 0.0,
        "all_wall_dimensions_decreased": all(value < 1.0 for value in ratios),
        "void_ratio_decreased": terminal_e < initial_e,
        "finite_state": all(math.isfinite(value) for value in initial_dimensions + terminal_dimensions + [initial_e, terminal_e]),
    }
    result = {
        "schema": "lbs.stage26q-negative-strain-sign-smoke.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "negative_sign_compression_verified" if all(checks.values()) else "negative_sign_compression_not_verified",
        "passed": all(checks.values()),
        "claim_boundary": "Five-thousand-step wall-kinematics sign check only; no density qualification, material, fibre, flow, or permeability result.",
        "checks": checks,
        "initial": {"dimensions_m": initial_dimensions, "void_ratio": initial_e},
        "terminal": {"dimensions_m": terminal_dimensions, "void_ratio": terminal_e, "dimension_ratios": ratios},
        "rate_per_s": rate,
        "steps": 5000,
        "sources": {
            "config": {"path": config_path, "sha256": sha256(config_path)},
            "runner": {"path": script_path, "sha256": sha256(script_path)},
            "input_state": input_binding,
        },
        "authority": {
            "sign_only_corrected_clean_pilot_authorized": all(checks.values()),
            "single_fibre_execution_authorized": False,
            "full_mixture_execution_authorized": False,
            "flow_execution_authorized": False,
            "permeability_claim_authorized": False,
        },
    }
    path = os.path.join(output, "result.json")
    write_json_exclusive(path, result)
    print("STAGE26Q_SIGN_SMOKE=" + json.dumps(result, sort_keys=True), flush=True)
    print("STAGE26Q_SIGN_SMOKE_SHA256=" + sha256(path), flush=True)
    raise SystemExit(0 if result["passed"] else 2)


main()
