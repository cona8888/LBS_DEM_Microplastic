"""YADE free-clump verification of dry and buoyancy-corrected acceleration."""
from __future__ import print_function

import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade import config


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    with open(path, "r") as stream:
        return json.load(stream)


def run_case(offsets, cfg, acceleration_z):
    O.reset()
    material = O.materials.append(FrictMat(young=5.3e7, poisson=0.25, frictionAngle=math.atan(0.45), density=float(cfg["fibre_density_kg_m3"]), label="stage26p_f37"))
    radius = float(cfg["member_radius_m"])
    bodies = [sphere(Vector3(*offset), radius, material=material) for offset in offsets]
    parent_id, member_ids = O.bodies.appendClumped(bodies, 20)
    parent_id, member_ids = int(parent_id), [int(value) for value in member_ids]
    parent = O.bodies[parent_id]
    factor = float(cfg["target_mass_kg"]) / float(parent.state.mass)
    parent.state.mass = float(cfg["target_mass_kg"])
    parent.state.inertia = Vector3(*[float(value) * factor for value in parent.state.inertia])
    parent.state.blockedDOFs = ""
    parent.state.vel = Vector3.Zero
    parent.state.angVel = Vector3.Zero
    O.engines = [ForceResetter(), NewtonIntegrator(damping=0.0, gravity=Vector3(0.0, 0.0, float(acceleration_z)))]
    O.dt = float(cfg["time_step_s"])
    initial_z = float(parent.state.pos[2])
    O.run(int(cfg["steps"]), True)
    elapsed = float(O.time)
    observed_displacement = float(parent.state.pos[2]) - initial_z
    observed_velocity = float(parent.state.vel[2])
    expected_displacement = 0.5 * float(acceleration_z) * elapsed * elapsed
    expected_velocity = float(acceleration_z) * elapsed
    displacement_scale = max(abs(expected_displacement), 1.0e-30)
    velocity_scale = max(abs(expected_velocity), 1.0e-30)
    return {
        "acceleration_z_m_s2": float(acceleration_z),
        "steps": int(cfg["steps"]),
        "elapsed_time_s": elapsed,
        "observed_displacement_z_m": observed_displacement,
        "expected_displacement_z_m": expected_displacement,
        "relative_displacement_error": abs(observed_displacement - expected_displacement) / displacement_scale,
        "observed_velocity_z_m_s": observed_velocity,
        "expected_velocity_z_m_s": expected_velocity,
        "relative_velocity_error": abs(observed_velocity - expected_velocity) / velocity_scale,
        "member_count": len(member_ids),
        "parent_mass_kg": float(parent.state.mass),
    }


def main():
    started = time.time()
    config_path = os.path.abspath(os.environ["STAGE26P_FORCE_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26P_FORCE_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26P_FORCE_SCRIPT", __file__))
    cfg = load(config_path)
    if cfg.get("status") != "authorized_stage26p_single_f37_force_sign_smoke":
        raise RuntimeError("configuration not authorized")
    if str(config.version) != str(cfg["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    if sha256(script_path) != cfg["sources"]["runner_sha256"]:
        raise RuntimeError("runner hash mismatch")
    for key in ("analytical_check", "placement"):
        if sha256(cfg["sources"][key]) != cfg["sources"][key + "_sha256"]:
            raise RuntimeError("source hash mismatch: " + key)
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26p force output exists")
    placement = load(cfg["sources"]["placement"])
    centres = [[float(value) for value in centre] for centre in placement["fibres"][0]["member_centres_m"]]
    pivot = [sum(centre[axis] for centre in centres) / len(centres) for axis in range(3)]
    offsets = [[centre[axis] - pivot[axis] for axis in range(3)] for centre in centres]
    dry = run_case(offsets, cfg, float(cfg["dry_acceleration_z_m_s2"]))
    submerged = run_case(offsets, cfg, float(cfg["submerged_acceleration_z_m_s2"]))
    tolerance = float(cfg["maximum_relative_integration_error"])
    checks = {
        "dry_direction_downward": dry["observed_displacement_z_m"] < 0.0 and dry["observed_velocity_z_m_s"] < 0.0,
        "submerged_direction_upward": submerged["observed_displacement_z_m"] > 0.0 and submerged["observed_velocity_z_m_s"] > 0.0,
        "dry_displacement": dry["relative_displacement_error"] <= tolerance,
        "dry_velocity": dry["relative_velocity_error"] <= tolerance,
        "submerged_displacement": submerged["relative_displacement_error"] <= tolerance,
        "submerged_velocity": submerged["relative_velocity_error"] <= tolerance,
        "exact_members": dry["member_count"] == submerged["member_count"] == 37,
        "exact_mass": abs(dry["parent_mass_kg"] - float(cfg["target_mass_kg"])) <= 1.0e-20 and abs(submerged["parent_mass_kg"] - float(cfg["target_mass_kg"])) <= 1.0e-20,
    }
    passed = all(checks.values())
    payload = {
        "schema": "lbs.stage26p-single-f37-force-sign-smoke-result.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "single_f37_force_sign_and_magnitude_verified" if passed else "single_f37_force_smoke_failed",
        "checks": checks,
        "dry_case": dry,
        "submerged_case": submerged,
        "source_hashes": {"config": sha256(config_path), "runner": sha256(script_path), "analytical_check": cfg["sources"]["analytical_check_sha256"], "placement": cfg["sources"]["placement_sha256"]},
        "engine": {"yade_version": str(config.version), "time_step_s": float(cfg["time_step_s"])},
        "wall_seconds": time.time() - started,
        "claim_boundary": "Free rigid-clump force integration verification only; no drag, terminal speed, sand contact, trapping, flow, or permeability claim.",
        "authority": {"single_fibre_contact_trapping_design_authorized": passed, "drag_calibration_authorized": False, "full_mixture_execution_authorized": False, "flow_execution_authorized": False},
    }
    os.makedirs(output)
    path = os.path.join(output, "result.json")
    with open(path, "x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print("STAGE26P_FORCE_SMOKE_SHA256=" + sha256(path), flush=True)
    if not passed:
        raise RuntimeError("Stage26p force smoke failed")


if __name__ == "__main__":
    main()
