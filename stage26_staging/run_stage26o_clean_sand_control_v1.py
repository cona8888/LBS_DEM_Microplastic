"""Stage26o wall-bounded clean-LBS gravity/confinement preparation control."""
from __future__ import print_function

import csv
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(os.environ.get("STAGE26O_CONTROL_SCRIPT", __file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from yade import config, utils
from stage26b_revision2_prefilter_common_v1 import iterative_core, load_json, sha256, windows_to_wsl, write_json_exclusive

START = time.time()


def bind(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def wall_dimensions(triax):
    x0 = float(O.bodies[triax.wall_left_id].state.pos[0])
    x1 = float(O.bodies[triax.wall_right_id].state.pos[0])
    y0 = float(O.bodies[triax.wall_bottom_id].state.pos[1])
    y1 = float(O.bodies[triax.wall_top_id].state.pos[1])
    z0 = float(O.bodies[triax.wall_back_id].state.pos[2])
    z1 = float(O.bodies[triax.wall_front_id].state.pos[2])
    return [x1 - x0, y1 - y0, z1 - z0], [x0, y0, z0], [x1, y1, z1]


def sand_network(sand_ids):
    sand_set = set(sand_ids)
    edges = []
    for interaction in O.interactions:
        if interaction.isReal and interaction.id1 in sand_set and interaction.id2 in sand_set:
            edges.append((int(interaction.id1), int(interaction.id2)))
    _, _, active = iterative_core(sand_ids, edges, 2)
    retained = sum(1 for first, second in edges if first in active and second in active)
    coordination = 2.0 * retained / len(active) if active else 0.0
    return len(edges), len(active), 1.0 - len(active) / float(len(sand_ids)), coordination


def diagnostic(record, phase, phase_index, cfg, triax, sand_ids, solid_volume, total_weight):
    dimensions, lower, upper = wall_dimensions(triax)
    volume = dimensions[0] * dimensions[1] * dimensions[2]
    stresses = [
        -float(triax.stress(triax.wall_right_id)[0]),
        -float(triax.stress(triax.wall_top_id)[1]),
        -float(triax.stress(triax.wall_front_id)[2]),
    ]
    target = float(cfg["confinement"]["target_mean_wall_stress_pa_compression_positive"])
    mean_stress = sum(stresses) / 3.0
    unbalanced = float(utils.unbalancedForce())
    if not math.isfinite(unbalanced):
        unbalanced = 1.0
    contacts, active, rattlers, coordination = sand_network(sand_ids)
    sand_set = set(sand_ids)
    maximum_penetration = 0.0
    wall_contacts = 0
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        if (first in sand_set) != (second in sand_set):
            wall_contacts += 1
        penetration = max(0.0, float(interaction.geom.penetrationDepth))
        sphere_id = first if first in sand_set else second if second in sand_set else None
        if sphere_id is not None:
            denominator = float(O.bodies[sphere_id].shape.radius)
            if first in sand_set and second in sand_set:
                denominator = min(float(O.bodies[first].shape.radius), float(O.bodies[second].shape.radius))
            maximum_penetration = max(maximum_penetration, penetration / denominator)
    leakage = 0
    for body_id in sand_ids:
        body = O.bodies[body_id]
        radius = float(body.shape.radius)
        for axis in range(3):
            coordinate = float(body.state.pos[axis])
            if coordinate < lower[axis] - radius or coordinate > upper[axis] + radius:
                leakage += 1
                break
    kinetic = float(utils.kineticEnergy())
    p_v = target * volume
    weight_d50 = total_weight * float(cfg["sand"]["D50_m"])
    return {
        "record": int(record), "phase": phase, "phase_index": int(phase_index),
        "iteration": int(O.iter), "time_s": float(O.time), "time_step_s": float(O.dt),
        "wall_dimensions_m": dimensions, "wall_volume_m3": volume,
        "principal_wall_stress_pa_compression_positive": stresses,
        "mean_wall_stress_pa_compression_positive": mean_stress,
        "relative_mean_wall_stress_error": abs(mean_stress - target) / target,
        "maximum_principal_wall_stress_error": max(abs(value - target) / target for value in stresses),
        "unbalanced_force": unbalanced, "kinetic_energy_j": kinetic,
        "normalized_kinetic_energy_pV": kinetic / p_v if p_v > 0 else 1.0,
        "normalized_kinetic_energy_weight_D50": kinetic / weight_d50 if weight_d50 > 0 else 1.0,
        "sand_sand_real_contact_count": contacts,
        "sand_load_bearing_particle_count_after_degree_lt2_pruning": active,
        "sand_rattler_fraction_degree_lt2_iterative": rattlers,
        "sand_coordination_excluding_degree_lt2_rattlers": coordination,
        "sand_wall_real_contact_count": wall_contacts,
        "maximum_interobject_penetration_over_smaller_radius": maximum_penetration,
        "container_void_ratio": volume / solid_volume - 1.0,
        "particle_count": len(sand_ids), "leaked_particle_count": leakage,
    }


def final_gate(row, cfg):
    limits = cfg["acceptance"]
    values = [row["mean_wall_stress_pa_compression_positive"], row["unbalanced_force"], row["kinetic_energy_j"], row["maximum_interobject_penetration_over_smaller_radius"]]
    return {
        "finite_state": all(math.isfinite(float(value)) for value in values),
        "mean_stress": row["relative_mean_wall_stress_error"] <= limits["maximum_relative_mean_wall_stress_error"],
        "principal_stress": row["maximum_principal_wall_stress_error"] <= limits["maximum_principal_wall_stress_error"],
        "unbalanced_force": row["unbalanced_force"] <= limits["maximum_unbalanced_force"],
        "normalized_kinetic_energy": row["normalized_kinetic_energy_pV"] <= limits["maximum_normalized_kinetic_energy_pV"],
        "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"] >= limits["minimum_sand_coordination_excluding_rattlers"],
        "sand_rattlers": row["sand_rattler_fraction_degree_lt2_iterative"] <= limits["maximum_sand_rattler_fraction"],
        "overlap": row["maximum_interobject_penetration_over_smaller_radius"] <= limits["maximum_penetration_over_smaller_radius"],
        "particle_count": row["particle_count"] == limits["required_particle_count"],
        "no_leakage": row["leaked_particle_count"] == 0,
    }


def write_history(path, rows):
    with open(path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            encoded["wall_dimensions_m"] = json.dumps(encoded["wall_dimensions_m"], separators=(",", ":"))
            encoded["principal_wall_stress_pa_compression_positive"] = json.dumps(encoded["principal_wall_stress_pa_compression_positive"], separators=(",", ":"))
            writer.writerow(encoded)


def main():
    config_path = os.path.abspath(os.environ["STAGE26O_CONTROL_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26O_CONTROL_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26O_CONTROL_SCRIPT", __file__))
    cfg = load_json(config_path)
    if cfg.get("status") != "authorized_stage26o_clean_sand_wall_preparation_control":
        raise RuntimeError("configuration is not Stage26o-control-authorized")
    if cfg["authority"].get("clean_sand_control_authorized") is not True or any(cfg["authority"].get(key, False) for key in ("spent_development_mixture_authorized", "heldout_execution_authorized", "flow_execution_authorized", "deformation_authorized", "production_parametric_study_authorized")):
        raise RuntimeError("Stage26o control authority exceeded")
    bind(cfg)
    if sha256(script_path) != cfg["sources"]["runner_sha256"] or str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("runner or YADE version mismatch")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26o control output exists")
    os.makedirs(output)

    O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    radii = [float(body.shape.radius) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
    if len(radii) != int(cfg["sand"]["particle_count"]):
        raise RuntimeError("Stage25 radius count mismatch")
    solid_volume = sum(4.0 * math.pi * radius ** 3 / 3.0 for radius in radii)
    initial_length = (solid_volume * (1.0 + float(cfg["initialization"]["initial_void_ratio"]))) ** (1.0 / 3.0)
    rng = random.Random(int(cfg["initialization"]["deterministic_rsa_seed"]))
    placed = []
    for original_index, radius in sorted(enumerate(radii), key=lambda item: item[1], reverse=True):
        accepted = None
        for _ in range(int(cfg["initialization"]["maximum_trials_per_particle"])):
            centre = [rng.uniform(radius, initial_length - radius) for __ in range(3)]
            if all(sum((centre[k] - other[1][k]) ** 2 for k in range(3)) >= (radius + other[2]) ** 2 for other in placed):
                accepted = centre
                break
        if accepted is None:
            raise RuntimeError("deterministic RSA failed")
        placed.append((original_index, accepted, radius))
    placed.sort(key=lambda item: item[0])

    O.reset()
    O.periodic = False
    sand_mat = O.materials.append(FrictMat(young=float(cfg["sand"]["young_pa"]), poisson=float(cfg["sand"]["poisson"]), frictionAngle=math.atan(float(cfg["sand"]["friction_coefficient"])), density=float(cfg["sand"]["density_kg_m3"]), label="stage26o_clean_lbs"))
    wall_mat = O.materials.append(FrictMat(young=float(cfg["sand"]["young_pa"]), poisson=float(cfg["sand"]["poisson"]), frictionAngle=math.atan(float(cfg["walls"]["friction_coefficient"])), density=0.0, label="stage26o_frictionless_walls"))
    wall_ids = [int(value) for value in O.bodies.append(aabbWalls([Vector3(0, 0, 0), Vector3(initial_length, initial_length, initial_length)], thickness=float(cfg["walls"]["thickness_m"]), material=wall_mat))]
    sand_ids = [int(O.bodies.append(sphere(Vector3(*centre), radius, material=sand_mat))) for _, centre, radius in placed]
    triax = TriaxialStressController(
        wall_left_id=wall_ids[0], wall_right_id=wall_ids[1],
        wall_bottom_id=wall_ids[2], wall_top_id=wall_ids[3],
        wall_back_id=wall_ids[4], wall_front_id=wall_ids[5],
        internalCompaction=False, stressMask=7, thickness=float(cfg["walls"]["thickness_m"]),
        max_vel=float(cfg["confinement"]["controller_maximum_wall_velocity_m_s"]), label="stage26o_triax",
    )
    triax.goal1 = triax.goal2 = triax.goal3 = -float(cfg["confinement"]["target_mean_wall_stress_pa_compression_positive"])
    triax.dead = True
    time_stepper = GlobalStiffnessTimeStepper(active=True, timeStepUpdateInterval=1, timestepSafetyCoefficient=float(cfg["settling"]["timestep_safety_coefficient"]), label="stage26o_time_stepper")
    newton = NewtonIntegrator(damping=float(cfg["settling"]["newton_damping"]), gravity=Vector3(*cfg["settling"]["gravity_m_s2"]), label="stage26o_newton")
    O.engines = [ForceResetter(), InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_Box_Aabb()]), InteractionLoop([Ig2_Sphere_Sphere_ScGeom(), Ig2_Box_Sphere_ScGeom()], [Ip2_FrictMat_FrictMat_FrictPhys()], [Law2_ScGeom_FrictPhys_CundallStrack()]), time_stepper, triax, newton]
    O.trackEnergy = True
    O.step()
    total_weight = solid_volume * float(cfg["sand"]["density_kg_m3"]) * 9.81
    history, record = [], 0

    settle_streak = 0
    for block in range(1, int(cfg["settling"]["maximum_blocks"]) + 1):
        O.run(int(cfg["settling"]["steps_per_block"]), True)
        record += 1
        row = diagnostic(record, "gravity_settling", block, cfg, triax, sand_ids, solid_volume, total_weight)
        history.append(row)
        settle_ok = (
            block >= int(cfg["settling"]["minimum_blocks"])
            and row["unbalanced_force"] <= float(cfg["settling"]["maximum_unbalanced_force"])
            and row["normalized_kinetic_energy_weight_D50"] <= float(cfg["settling"]["maximum_normalized_kinetic_energy_weight_D50"])
            and row["sand_sand_real_contact_count"] >= int(cfg["settling"]["minimum_sand_contact_count"])
            and row["leaked_particle_count"] == 0
        )
        settle_streak = settle_streak + 1 if settle_ok else 0
        if block == 1 or block % 20 == 0 or settle_streak > 0:
            print("STAGE26O_SETTLE=" + json.dumps({"block": block, "contacts": row["sand_sand_real_contact_count"], "unbalanced": row["unbalanced_force"], "ke_WD50": row["normalized_kinetic_energy_weight_D50"], "streak": settle_streak}, sort_keys=True), flush=True)
        if row["maximum_interobject_penetration_over_smaller_radius"] > float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]) or row["leaked_particle_count"]:
            break
        if settle_streak >= int(cfg["settling"]["required_consecutive_pass_blocks"]):
            break

    qualified = False
    status = "gravity_settling_not_qualified"
    final_checks = None
    confinement_streak = 0
    if settle_streak >= int(cfg["settling"]["required_consecutive_pass_blocks"]):
        triax.dead = False
        time_stepper.timestepSafetyCoefficient = float(cfg["confinement"]["timestep_safety_coefficient"])
        newton.damping = float(cfg["confinement"]["newton_damping"])
        status = "confinement_not_qualified"
        for block in range(1, int(cfg["confinement"]["maximum_blocks"]) + 1):
            O.run(int(cfg["confinement"]["steps_per_block"]), True)
            record += 1
            row = diagnostic(record, "gravity_plus_wall_confinement", block, cfg, triax, sand_ids, solid_volume, total_weight)
            history.append(row)
            checks = final_gate(row, cfg)
            eligible = block >= int(cfg["confinement"]["minimum_blocks"])
            confinement_streak = confinement_streak + 1 if eligible and all(checks.values()) else 0
            if block == 1 or block % 20 == 0 or confinement_streak > 0:
                print("STAGE26O_CONFINE=" + json.dumps({"block": block, "stress": row["principal_wall_stress_pa_compression_positive"], "void_ratio": row["container_void_ratio"], "contacts": row["sand_sand_real_contact_count"], "coordination": row["sand_coordination_excluding_degree_lt2_rattlers"], "unbalanced": row["unbalanced_force"], "streak": confinement_streak}, sort_keys=True), flush=True)
            if not checks["finite_state"] or row["maximum_interobject_penetration_over_smaller_radius"] > float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]) or row["leaked_particle_count"]:
                status = "confinement_hard_guard_failed"
                break
            if confinement_streak >= int(cfg["confinement"]["required_consecutive_pass_blocks"]):
                status = "gravity_confinement_qualified"
                break

    if status == "gravity_confinement_qualified":
        start_gravity = [float(value) for value in cfg["settling"]["gravity_m_s2"]]
        terminal_gravity = [float(value) for value in cfg["gravity_removal"]["terminal_gravity_m_s2"]]
        blocks = int(cfg["gravity_removal"]["blocks"])
        for block in range(1, blocks + 1):
            fraction = block / float(blocks)
            newton.gravity = Vector3(*[start_gravity[k] + fraction * (terminal_gravity[k] - start_gravity[k]) for k in range(3)])
            O.run(int(cfg["gravity_removal"]["steps_per_block"]), True)
            record += 1
            row = diagnostic(record, "gravity_removal_ramp", block, cfg, triax, sand_ids, solid_volume, total_weight)
            history.append(row)
            if row["maximum_interobject_penetration_over_smaller_radius"] > float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]):
                status = "gravity_removal_hard_guard_failed"
                break

    hold_streak = 0
    if status == "gravity_confinement_qualified":
        time_stepper.timestepSafetyCoefficient = float(cfg["final_hold"]["timestep_safety_coefficient"])
        newton.damping = float(cfg["final_hold"]["newton_damping"])
        status = "zero_gravity_hold_not_qualified"
        for block in range(1, int(cfg["final_hold"]["maximum_blocks"]) + 1):
            O.run(int(cfg["final_hold"]["steps_per_block"]), True)
            record += 1
            row = diagnostic(record, "zero_gravity_final_hold", block, cfg, triax, sand_ids, solid_volume, total_weight)
            history.append(row)
            final_checks = final_gate(row, cfg)
            eligible = block >= int(cfg["final_hold"]["minimum_blocks"])
            hold_streak = hold_streak + 1 if eligible and all(final_checks.values()) else 0
            if block == 1 or block % 10 == 0 or hold_streak > 0:
                print("STAGE26O_HOLD=" + json.dumps({"block": block, "stress": row["principal_wall_stress_pa_compression_positive"], "contacts": row["sand_sand_real_contact_count"], "coordination": row["sand_coordination_excluding_degree_lt2_rattlers"], "unbalanced": row["unbalanced_force"], "streak": hold_streak}, sort_keys=True), flush=True)
            if not final_checks["finite_state"] or row["maximum_interobject_penetration_over_smaller_radius"] > float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]):
                status = "zero_gravity_hold_hard_guard_failed"
                break
            if hold_streak >= int(cfg["final_hold"]["required_consecutive_pass_blocks"]):
                qualified = True
                status = "clean_sand_wall_preparation_control_qualified"
                break

    history_path = os.path.join(output, "control_history.csv")
    write_history(history_path, history)
    state_digest = None
    if qualified:
        state_path = os.path.join(output, "qualified_clean_sand_wall_state.yade.gz")
        O.tags["stage26o_control_metadata_json"] = json.dumps({"schema": "lbs.stage26o-control-state-metadata.v1", "config_sha256": sha256(config_path), "final_hold_streak": hold_streak}, sort_keys=True, separators=(",", ":"))
        O.save(state_path)
        state_digest = sha256(state_path)
    result = {
        "schema": "lbs.stage26o-clean-sand-wall-preparation-control-result.v1", "passed": True,
        "status": status, "qualified": qualified, "settling_streak": settle_streak,
        "confinement_streak": confinement_streak, "final_hold_streak": hold_streak,
        "terminal": history[-1], "terminal_checks": final_checks, "records_written": len(history),
        "realized_radii_m": radii, "initial_box_length_m": initial_length,
        "artifacts": {"history_sha256": sha256(history_path), "state_sha256": state_digest},
        "source_hashes": {"config": sha256(config_path), "runner": sha256(script_path), "stage25_checkpoint": cfg["sources"]["stage25_checkpoint_sha256"]},
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26o-clean-sand-wall-preparation-control-completion.v1", "passed": True,
        "status": status, "qualified": qualified, "result_sha256": sha256(result_path),
        "state_sha256": state_digest, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": time.time() - START,
        "authority": {"spent_development_mixture_authorized": False, "heldout_execution_authorized": False, "flow_execution_authorized": False, "deformation_authorized": False},
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26O_CONTROL_COMPLETION_SHA256=" + sha256(completion_path), flush=True)


if __name__ == "__main__":
    main()
