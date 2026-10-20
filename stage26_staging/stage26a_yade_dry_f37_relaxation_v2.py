"""Stage26a revision 2: fixed-fibre conditioning followed by a free-fibre test."""

from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade import config


BOUND_SCRIPT = os.path.abspath(os.environ.get("STAGE26_SCRIPT", __file__))
BASE_SCRIPT = os.path.join(os.path.dirname(BOUND_SCRIPT), "stage26a_yade_dry_f37_relaxation_v1.py")
with open(BASE_SCRIPT, "r") as stream:
    base_source = stream.read()
base_prefix = base_source.split("\ntry:\n    main()", 1)[0]
base_namespace = dict(globals())
base_namespace["__file__"] = BASE_SCRIPT
base_namespace["__name__"] = "stage26a_base"
exec(compile(base_prefix, BASE_SCRIPT, "exec"), base_namespace)

sha256 = base_namespace["sha256"]
load_json = base_namespace["load_json"]
write_json_exclusive = base_namespace["write_json_exclusive"]
windows_to_wsl = base_namespace["windows_to_wsl"]
diagonal_lengths = base_namespace["diagonal_lengths"]
minimum_image = base_namespace["minimum_image"]
vector_norm = base_namespace["vector_norm"]
diagnostic = base_namespace["diagnostic"]
gates = base_namespace["gates"]

CONFIG_PATH = os.path.abspath(os.environ["STAGE26_CONFIG"])
PLACEMENT_PATH = os.path.abspath(os.environ["STAGE26_PLACEMENT"])
OUTPUT_ROOT = os.path.abspath(os.environ["STAGE26_OUTPUT"])
SCRIPT_PATH = os.path.abspath(os.environ.get("STAGE26_SCRIPT", __file__))
START = time.time()


def zero_body_motion(body_ids):
    for body_id in body_ids:
        body = O.bodies[body_id]
        body.state.vel = Vector3.Zero
        body.state.angVel = Vector3.Zero


def write_history(path, rows):
    with open(path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for name in ["cell_dimensions_m", "principal_effective_stress_pa_compression_positive", "contacted_sand_body_ids"]:
                encoded[name] = json.dumps(encoded[name], separators=(",", ":"))
            writer.writerow(encoded)


def main():
    cfg = load_json(CONFIG_PATH); placement = load_json(PLACEMENT_PATH)
    if cfg.get("status") != "authorized_bounded_dry_fibre_qualification" or cfg["promotion"].get("stage26a_execution_authorized") is not True:
        raise RuntimeError("Stage26a configuration is not execution-authorized")
    if str(config.version) != str(cfg["source"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    for key in ["stage25_checkpoint_manifest", "stage25_checkpoint", "stage25_evaluation", "stage25_selected_result", "f37_geometry_review"]:
        if sha256(windows_to_wsl(cfg["source"][key])) != cfg["source"][key + "_sha256"]:
            raise RuntimeError("source hash mismatch: " + key)
    if not placement.get("passed") or placement["source_hashes"]["config"] != sha256(CONFIG_PATH):
        raise RuntimeError("placement/config binding mismatch")
    if placement.get("initial_normal_force_residual_relative", 1.0) > cfg["placement"]["maximum_initial_normal_force_residual_relative"] or placement.get("initial_normal_moment_residual_relative", 1.0) > cfg["placement"]["maximum_initial_normal_moment_residual_relative"]:
        raise RuntimeError("placement balance gates failed")
    if os.path.exists(OUTPUT_ROOT):
        raise RuntimeError("immutable output already exists")
    os.makedirs(OUTPUT_ROOT)

    O.load(windows_to_wsl(cfg["source"]["stage25_checkpoint"]))
    sand_ids = [int(body.id) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
    if len(sand_ids) != cfg["acceptance"]["required_sand_particle_count"]:
        raise RuntimeError("Stage25 checkpoint sand count mismatch")
    if cfg["relaxation"].get("reset_checkpoint_particle_velocities") is not True:
        raise RuntimeError("velocity-reset protocol is not enabled")
    zero_body_motion(sand_ids)
    lengths0 = diagonal_lengths()
    initial = {
        "cell_dimensions_m": lengths0, "cell_volume_m3": float(O.cell.volume),
        "sand_fractional": dict((str(body_id), [float(O.bodies[body_id].state.pos[index]) / lengths0[index] for index in range(3)]) for body_id in sand_ids),
        "checkpoint_velocities_reset": True,
    }
    triax = next(engine for engine in O.engines if isinstance(engine, PeriTriaxController))
    triax.dead = False
    triax.goal = tuple(-float(cfg["relaxation"]["target_mean_effective_stress_pa_compression_positive"]) for _ in range(3))
    triax.maxStrainRate = tuple(float(cfg["relaxation"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["acceptance"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["acceptance"]["maximum_unbalanced_force"])
    for engine in O.engines:
        if isinstance(engine, GlobalStiffnessTimeStepper):
            engine.timestepSafetyCoefficient = float(cfg["relaxation"]["timestep_safety_coefficient"])
        if isinstance(engine, NewtonIntegrator):
            engine.damping = float(cfg["relaxation"]["newton_damping"]); engine.gravity = Vector3(*cfg["relaxation"]["gravity_m_s2"])

    plastic_id = O.materials.append(FrictMat(young=float(cfg["contacts"]["plastic_young_pa"]), poisson=float(cfg["contacts"]["plastic_poisson"]), frictionAngle=math.atan(float(cfg["contacts"]["plastic_friction_coefficient"])), density=float(cfg["fibre"]["density_kg_m3"]), label="stage26a_f37_plastic"))
    members = [sphere(Vector3(*centre), float(placement["member_radius_m"]), material=plastic_id, color=(0.85, 0.12, 0.10)) for centre in placement["member_centres_m"]]
    fibre_parent, fibre_members = O.bodies.appendClumped(members, 20)
    fibre_parent = int(fibre_parent); fibre_members = [int(value) for value in fibre_members]
    parent = O.bodies[fibre_parent]
    raw_mass = float(parent.state.mass); mass_factor = float(cfg["fibre"]["target_mass_kg"]) / raw_mass
    parent.state.mass = float(cfg["fibre"]["target_mass_kg"]); parent.state.inertia = Vector3(*[float(value) * mass_factor for value in parent.state.inertia])
    parent.state.blockedDOFs = "xyzXYZ"
    zero_body_motion(sand_ids + [fibre_parent])
    O.step()
    initial["fibre_com_m"] = [float(parent.state.pos[index]) for index in range(3)]
    first = O.bodies[fibre_members[0]].state.pos; last = O.bodies[fibre_members[-1]].state.pos
    initial["fibre_tip_vector_m"] = minimum_image([float(last[index] - first[index]) for index in range(3)], diagonal_lengths())
    initial["fibre_tip_span_m"] = vector_norm(initial["fibre_tip_vector_m"])

    conditioning = []
    for block in range(1, int(cfg["relaxation"]["fixed_fibre_conditioning_blocks"]) + 1):
        O.run(int(cfg["relaxation"]["fixed_fibre_steps_per_block"]), True)
        row = diagnostic(block, cfg, triax, sand_ids, fibre_parent, fibre_members, initial)
        row["stage"] = "fixed_fibre_conditioning"
        conditioning.append(row)
        if block == 1 or block % 10 == 0:
            print("STAGE26_CONDITIONING=" + json.dumps({"block": block, "unbalanced": row["unbalanced_force"], "fibre_contacts": row["distinct_sand_contacts_per_fibre"], "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"], "max_sand_displacement_D50": row["maximum_nonaffine_sand_displacement_over_D50"]}, sort_keys=True), flush=True)
    parent.state.blockedDOFs = ""
    zero_body_motion(sand_ids + [fibre_parent])

    free = []; streak = 0; final_checks = None
    required = int(cfg["relaxation"]["required_consecutive_pass_blocks"])
    for block in range(1, int(cfg["relaxation"]["maximum_check_blocks"]) + 1):
        O.run(int(cfg["relaxation"]["steps_per_check_block"]), True)
        row = diagnostic(block, cfg, triax, sand_ids, fibre_parent, fibre_members, initial)
        row["stage"] = "free_fibre_relaxation"
        final_checks = gates(row, cfg); free.append(row)
        streak = streak + 1 if all(final_checks.values()) else 0
        if block == 1 or block % 10 == 0 or streak > 0:
            print("STAGE26_FREE=" + json.dumps({"block": block, "stress_pa": row["mean_effective_stress_pa_compression_positive"], "unbalanced": row["unbalanced_force"], "fibre_contacts": row["distinct_sand_contacts_per_fibre"], "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"], "max_sand_displacement_D50": row["maximum_nonaffine_sand_displacement_over_D50"], "fibre_displacement_L": row["fibre_com_displacement_over_length"], "streak": streak}, sort_keys=True), flush=True)
        if streak >= required:
            break
    final = free[-1]; passed = streak >= required and all(final_checks.values())
    conditioning_path = os.path.join(OUTPUT_ROOT, "conditioning_history.csv"); free_path = os.path.join(OUTPUT_ROOT, "free_relaxation_history.csv")
    write_history(conditioning_path, conditioning); write_history(free_path, free)
    checkpoint = os.path.join(OUTPUT_ROOT, "dry_relaxed_state.yade.gz"); O.save(checkpoint)
    particles = []
    for body_id in sand_ids:
        body = O.bodies[body_id]; particles.append({"body_id": body_id, "phase": "sand", "position_m": [float(body.state.pos[index]) for index in range(3)], "radius_m": float(body.shape.radius)})
    for body_id in fibre_members:
        body = O.bodies[body_id]; particles.append({"body_id": body_id, "phase": "fibre", "parent_id": fibre_parent, "position_m": [float(body.state.pos[index]) for index in range(3)], "radius_m": float(body.shape.radius)})
    contacts = []
    for interaction in O.interactions:
        if interaction.isReal:
            contacts.append({"id1": int(interaction.id1), "id2": int(interaction.id2), "normal_force_n": float(interaction.phys.normalForce.norm()), "shear_force_n": float(interaction.phys.shearForce.norm())})
    result = {
        "schema": "lbs.stage26a-dry-f37-insertion.v2.result", "passed": passed,
        "engine": {"yade_version": str(config.version), "features": list(config.features)},
        "protocol": {"fixed_fibre_conditioning_blocks": len(conditioning), "free_fibre_relaxation_blocks": len(free), "checkpoint_velocities_reset": True},
        "source_hashes": {"config": sha256(CONFIG_PATH), "placement": sha256(PLACEMENT_PATH), "runner": sha256(SCRIPT_PATH), "base_runner": sha256(BASE_SCRIPT), "stage25_checkpoint": cfg["source"]["stage25_checkpoint_sha256"]},
        "initial": initial, "conditioning_terminal": conditioning[-1], "terminal": final, "checks": final_checks, "consecutive_pass_blocks": streak,
        "steps_completed": int(O.iter), "sand_ids": sand_ids, "fibre_parent_id": fibre_parent, "fibre_member_ids": fibre_members,
        "particles": particles, "contacts": contacts,
        "artifacts": {"conditioning_history_csv_sha256": sha256(conditioning_path), "free_relaxation_history_csv_sha256": sha256(free_path), "checkpoint_sha256": sha256(checkpoint)},
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(OUTPUT_ROOT, "result.json"); write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26a-dry-f37-insertion.v2.completion", "passed": passed,
        "status": "passed_dry_free_fibre_compatibility" if passed else "completed_no_admissible_free_fibre_state",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.time() - START,
        "result_sha256": sha256(result_path), "terminal": final, "conditioning_terminal": conditioning[-1], "checks": final_checks,
        "promotion": {"dry_single_fibre_checkpoint_qualified": passed, "multi_fibre_execution_authorized": False, "flow_execution_authorized": False, "transient_two_way_coupling_authorized": False, "deformation_coupled_flow_authorized": False},
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(OUTPUT_ROOT, "completion.json"); write_json_exclusive(completion_path, completion)
    print("STAGE26_COMPLETION=" + json.dumps({"passed": passed, "status": completion["status"], "completion_sha256": sha256(completion_path), "wall_seconds": completion["wall_seconds"]}, sort_keys=True), flush=True)


try:
    main()
except Exception as error:
    if os.path.isdir(OUTPUT_ROOT) and not os.path.exists(os.path.join(OUTPUT_ROOT, "failure.json")):
        write_json_exclusive(os.path.join(OUTPUT_ROOT, "failure.json"), {"schema": "lbs.stage26a-dry-f37-insertion.v2.failure", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "error_type": type(error).__name__, "error": str(error), "config_sha256": sha256(CONFIG_PATH), "placement_sha256": sha256(PLACEMENT_PATH), "runner_sha256": sha256(SCRIPT_PATH), "base_runner_sha256": sha256(BASE_SCRIPT)})
    raise
