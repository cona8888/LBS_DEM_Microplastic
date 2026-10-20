"""Stage26w bounded six-wall shrink-regrow dense LBS preparation pilot."""
from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade import config, utils


START = time.time()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def windows_to_wsl(path):
    value = str(path)
    if len(value) >= 3 and value[1:3] in (":\\", ":/"):
        return "/mnt/%s/%s" % (value[0].lower(), value[3:].replace("\\", "/"))
    return value


def write_json_exclusive(path, data):
    with open(path, "x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def find_engine(class_name):
    matches = [engine for engine in O.engines if engine.__class__.__name__ == class_name]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one %s, found %d" % (class_name, len(matches)))
    return matches[0]


def wall_geometry(triax):
    lower = [
        float(O.bodies[triax.wall_left_id].state.pos[0]),
        float(O.bodies[triax.wall_bottom_id].state.pos[1]),
        float(O.bodies[triax.wall_back_id].state.pos[2]),
    ]
    upper = [
        float(O.bodies[triax.wall_right_id].state.pos[0]),
        float(O.bodies[triax.wall_top_id].state.pos[1]),
        float(O.bodies[triax.wall_front_id].state.pos[2]),
    ]
    dimensions = [upper[k] - lower[k] for k in range(3)]
    return dimensions, lower, upper


def set_wall_bounds(triax, lower, upper):
    wall_axes = [
        (triax.wall_left_id, 0, lower[0]),
        (triax.wall_right_id, 0, upper[0]),
        (triax.wall_bottom_id, 1, lower[1]),
        (triax.wall_top_id, 1, upper[1]),
        (triax.wall_back_id, 2, lower[2]),
        (triax.wall_front_id, 2, upper[2]),
    ]
    for body_id, axis, coordinate in wall_axes:
        body = O.bodies[int(body_id)]
        position = [float(value) for value in body.state.pos]
        position[axis] = float(coordinate)
        body.state.pos = Vector3(*position)
        body.state.vel = Vector3.Zero
        body.state.angVel = Vector3.Zero


def set_sand_friction(sand_ids, coefficient):
    sand_set = set(sand_ids)
    for material_id in {int(O.bodies[body_id].material.id) for body_id in sand_ids}:
        O.materials[material_id].frictionAngle = math.atan(float(coefficient))
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        if first in sand_set and second in sand_set and hasattr(interaction.phys, "tangensOfFrictionAngle"):
            interaction.phys.tangensOfFrictionAngle = float(coefficient)


def contact_network(sand_ids):
    sand_set = set(sand_ids)
    edges = [
        (int(interaction.id1), int(interaction.id2))
        for interaction in O.interactions
        if interaction.isReal
        and int(interaction.id1) in sand_set
        and int(interaction.id2) in sand_set
    ]
    active = set(sand_ids)
    changed = True
    while changed:
        degree = {body_id: 0 for body_id in active}
        for first, second in edges:
            if first in active and second in active:
                degree[first] += 1
                degree[second] += 1
        removed = {body_id for body_id, value in degree.items() if value < 2}
        changed = bool(removed)
        active.difference_update(removed)
    retained = sum(1 for first, second in edges if first in active and second in active)
    coordination = 2.0 * retained / len(active) if active else 0.0
    return len(edges), len(active), 1.0 - len(active) / float(len(sand_ids)), coordination


def diagnostic(record, phase, phase_index, cfg, triax, sand_ids, final_radii, solid_volume):
    dimensions, lower, upper = wall_geometry(triax)
    volume = dimensions[0] * dimensions[1] * dimensions[2]
    stresses = [
        abs(float(O.forces.f(triax.wall_right_id)[0])) / (dimensions[1] * dimensions[2]),
        abs(float(O.forces.f(triax.wall_top_id)[1])) / (dimensions[0] * dimensions[2]),
        abs(float(O.forces.f(triax.wall_front_id)[2])) / (dimensions[0] * dimensions[1]),
    ]
    target_stress = float(cfg["target_state"]["isotropic_stress_pa_compression_positive"])
    mean_stress = sum(stresses) / 3.0
    contacts, active, rattlers, coordination = contact_network(sand_ids)
    sand_set = set(sand_ids)
    maximum_overlap = 0.0
    wall_contacts = 0
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        sand_members = [body_id for body_id in (first, second) if body_id in sand_set]
        if len(sand_members) == 1:
            wall_contacts += 1
        if not sand_members:
            continue
        denominator = min(float(O.bodies[body_id].shape.radius) for body_id in sand_members)
        maximum_overlap = max(
            maximum_overlap,
            max(0.0, float(interaction.geom.penetrationDepth)) / denominator,
        )
    leakage = 0
    for body_id in sand_ids:
        body = O.bodies[body_id]
        radius = float(body.shape.radius)
        if any(
            float(body.state.pos[axis]) < lower[axis] - radius
            or float(body.state.pos[axis]) > upper[axis] + radius
            for axis in range(3)
        ):
            leakage += 1
    unbalanced = float(utils.unbalancedForce())
    if not math.isfinite(unbalanced):
        unbalanced = 1.0
    kinetic = float(utils.kineticEnergy())
    radius_error = max(
        abs(float(O.bodies[body_id].shape.radius) - final_radii[body_id]) / final_radii[body_id]
        for body_id in sand_ids
    )
    return {
        "record": int(record),
        "phase": phase,
        "phase_index": int(phase_index),
        "iteration": int(O.iter),
        "time_s": float(O.time),
        "wall_dimensions_m": dimensions,
        "wall_volume_m3": volume,
        "container_void_ratio_using_final_radii": volume / solid_volume - 1.0,
        "maximum_relative_radius_error": radius_error,
        "principal_wall_stress_pa_compression_positive": stresses,
        "mean_wall_stress_pa_compression_positive": mean_stress,
        "relative_mean_wall_stress_error": abs(mean_stress - target_stress) / target_stress,
        "maximum_principal_wall_stress_error": max(abs(value - target_stress) / target_stress for value in stresses),
        "unbalanced_force": unbalanced,
        "kinetic_energy_j": kinetic,
        "normalized_kinetic_energy_pV": kinetic / (target_stress * volume),
        "sand_sand_real_contact_count": contacts,
        "sand_wall_real_contact_count": wall_contacts,
        "sand_load_bearing_particle_count_after_degree_lt2_pruning": active,
        "sand_rattler_fraction_degree_lt2_iterative": rattlers,
        "sand_coordination_excluding_degree_lt2_rattlers": coordination,
        "maximum_interobject_penetration_over_smaller_radius": maximum_overlap,
        "sand_friction_coefficient": math.tan(float(O.bodies[sand_ids[0]].material.frictionAngle)),
        "particle_count": len(sand_ids),
        "leaked_particle_count": leakage,
    }


def final_checks(row, cfg):
    limits = cfg["acceptance"]
    target_e = float(cfg["target_state"]["void_ratio"])
    finite_values = [
        row["container_void_ratio_using_final_radii"],
        row["mean_wall_stress_pa_compression_positive"],
        row["unbalanced_force"],
        row["kinetic_energy_j"],
        row["maximum_interobject_penetration_over_smaller_radius"],
    ]
    return {
        "finite_state": all(math.isfinite(float(value)) for value in finite_values),
        "exact_radii": row["maximum_relative_radius_error"] <= float(limits["maximum_relative_radius_error"]),
        "void_ratio": abs(row["container_void_ratio_using_final_radii"] - target_e) <= float(limits["maximum_void_ratio_error"]),
        "mean_stress": row["relative_mean_wall_stress_error"] <= float(limits["maximum_relative_mean_wall_stress_error"]),
        "principal_stress": row["maximum_principal_wall_stress_error"] <= float(limits["maximum_principal_wall_stress_error"]),
        "unbalanced_force": row["unbalanced_force"] <= float(limits["maximum_unbalanced_force"]),
        "normalized_kinetic_energy": row["normalized_kinetic_energy_pV"] <= float(limits["maximum_normalized_kinetic_energy_pV"]),
        "overlap": row["maximum_interobject_penetration_over_smaller_radius"] <= float(limits["maximum_penetration_over_smaller_radius"]),
        "coordination": row["sand_coordination_excluding_degree_lt2_rattlers"] >= float(limits["minimum_sand_coordination_excluding_rattlers"]),
        "rattlers": row["sand_rattler_fraction_degree_lt2_iterative"] <= float(limits["maximum_sand_rattler_fraction"]),
        "particle_count": row["particle_count"] == int(limits["required_particle_count"]),
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
    config_path = os.path.abspath(os.environ["STAGE26W_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26W_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26W_SCRIPT", __file__))
    with open(config_path, "r") as stream:
        cfg = json.load(stream)
    if cfg.get("status") != "authorized_stage26w_dense_wall_shrink_regrow_pilot":
        raise RuntimeError("configuration is not Stage26w-authorized")
    authority = cfg.get("authority", {})
    if authority.get("clean_dense_preparation_pilot_authorized") is not True:
        raise RuntimeError("clean dense preparation authority is false")
    forbidden = (
        "pore_throat_extraction_authorized",
        "fibre_execution_authorized",
        "mobile_sand_execution_authorized",
        "flow_execution_authorized",
        "permeability_claim_authorized",
        "production_parametric_study_authorized",
    )
    if any(authority.get(name, False) for name in forbidden):
        raise RuntimeError("Stage26w authority boundary exceeded")
    if sha256(script_path) != cfg["sources"]["runner"]["sha256"]:
        raise RuntimeError("runner hash mismatch")
    for name in ("input_state", "stage26o_checkpoint", "stage26q_nonacceptance", "stage26r_nonacceptance", "stage26v_checkpoint", "research_contract"):
        binding = cfg["sources"][name]
        if sha256(windows_to_wsl(binding["path"])) != binding["sha256"]:
            raise RuntimeError("source hash mismatch: " + name)
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("YADE version mismatch")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26w output exists")
    os.makedirs(output)

    O.load(windows_to_wsl(cfg["sources"]["input_state"]["path"]))
    if O.periodic:
        raise RuntimeError("input must be six-wall nonperiodic")
    triax = find_engine("TriaxialStressController")
    newton = find_engine("NewtonIntegrator")
    stepper = find_engine("GlobalStiffnessTimeStepper")
    sand_ids = sorted(
        int(body.id)
        for body in O.bodies
        if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember
    )
    if len(sand_ids) != int(cfg["target_state"]["particle_count"]):
        raise RuntimeError("particle count mismatch")
    final_radii = {body_id: float(O.bodies[body_id].shape.radius) for body_id in sand_ids}
    solid_volume = sum(4.0 * math.pi * radius ** 3 / 3.0 for radius in final_radii.values())
    dimensions, lower, upper = wall_geometry(triax)
    centre = [(lower[k] + upper[k]) / 2.0 for k in range(3)]
    target_volume = solid_volume * (1.0 + float(cfg["target_state"]["void_ratio"]))
    scale = (target_volume / (dimensions[0] * dimensions[1] * dimensions[2])) ** (1.0 / 3.0)
    target_dimensions = [value * scale for value in dimensions]
    target_lower = [centre[k] - target_dimensions[k] / 2.0 for k in range(3)]
    target_upper = [centre[k] + target_dimensions[k] / 2.0 for k in range(3)]

    triax.dead = True
    triax.stressMask = 0
    newton.gravity = Vector3.Zero
    newton.damping = float(cfg["preparation"]["newton_damping"])
    stepper.timestepSafetyCoefficient = float(cfg["preparation"]["timestep_safety_coefficient"])
    for body_id in sand_ids:
        body = O.bodies[body_id]
        mapped = [centre[k] + scale * (float(body.state.pos[k]) - centre[k]) for k in range(3)]
        body.state.pos = Vector3(*mapped)
        body.state.vel = Vector3.Zero
        body.state.angVel = Vector3.Zero
    set_wall_bounds(triax, target_lower, target_upper)
    shrink = float(cfg["preparation"]["initial_radius_scale"])
    for body_id in sand_ids:
        utils.growParticle(body_id, shrink, True)
    set_sand_friction(sand_ids, float(cfg["preparation"]["preparation_friction_coefficient"]))
    O.step()

    history = []
    record = 0
    hard_guard = float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"])
    growth_blocks = int(cfg["preparation"]["growth_blocks"])
    factor = (1.0 / shrink) ** (1.0 / growth_blocks)
    status = "radius_regrowth_not_qualified"
    for block in range(1, growth_blocks + 1):
        for body_id in sand_ids:
            multiplier = final_radii[body_id] / float(O.bodies[body_id].shape.radius) if block == growth_blocks else factor
            utils.growParticle(body_id, multiplier, True)
        O.run(int(cfg["preparation"]["steps_per_growth_block"]), True)
        record += 1
        row = diagnostic(record, "frictionless_radius_regrowth", block, cfg, triax, sand_ids, final_radii, solid_volume)
        history.append(row)
        if block == 1 or block % 20 == 0 or block == growth_blocks:
            print("STAGE26W_GROW=" + json.dumps({"block": block, "e": row["container_void_ratio_using_final_radii"], "stress": row["mean_wall_stress_pa_compression_positive"], "contacts": row["sand_sand_real_contact_count"], "overlap": row["maximum_interobject_penetration_over_smaller_radius"]}, sort_keys=True), flush=True)
        if row["maximum_interobject_penetration_over_smaller_radius"] > hard_guard or row["leaked_particle_count"]:
            status = "radius_regrowth_hard_guard_failed"
            break

    exact_radii = history and history[-1]["maximum_relative_radius_error"] <= float(cfg["acceptance"]["maximum_relative_radius_error"])
    if status != "radius_regrowth_hard_guard_failed" and exact_radii:
        status = "frictionless_hold_not_qualified"
        hold = cfg["frictionless_hold"]
        for block in range(1, int(hold["maximum_blocks"]) + 1):
            O.run(int(hold["steps_per_block"]), True)
            record += 1
            row = diagnostic(record, "frictionless_fixed_volume_hold", block, cfg, triax, sand_ids, final_radii, solid_volume)
            history.append(row)
            if block == 1 or block % 20 == 0:
                print("STAGE26W_HOLD=" + json.dumps({"block": block, "stress": row["mean_wall_stress_pa_compression_positive"], "unbalanced": row["unbalanced_force"], "ke_pV": row["normalized_kinetic_energy_pV"], "contacts": row["sand_sand_real_contact_count"]}, sort_keys=True), flush=True)
            if row["maximum_interobject_penetration_over_smaller_radius"] > hard_guard or row["leaked_particle_count"]:
                status = "frictionless_hold_hard_guard_failed"
                break
            if (
                block >= int(hold["minimum_blocks"])
                and row["normalized_kinetic_energy_pV"] <= float(hold["maximum_normalized_kinetic_energy_pV"])
                and (
                    row["unbalanced_force"] <= float(hold["maximum_unbalanced_force"])
                    or row["sand_sand_real_contact_count"] == 0
                )
            ):
                status = "stress_restoration_not_qualified"
                break

    final = history[-1]
    checks = final_checks(final, cfg)
    streak = 0
    if status == "stress_restoration_not_qualified":
        set_sand_friction(sand_ids, float(cfg["stress_restoration"]["restored_friction_coefficient"]))
        triax.stressMask = 7
        target_stress = float(cfg["target_state"]["isotropic_stress_pa_compression_positive"])
        triax.goal1 = triax.goal2 = triax.goal3 = -target_stress
        triax.max_vel = float(cfg["stress_restoration"]["controller_maximum_wall_velocity_m_s"])
        triax.dead = False
        newton.damping = float(cfg["stress_restoration"]["newton_damping"])
        stepper.timestepSafetyCoefficient = float(cfg["stress_restoration"]["timestep_safety_coefficient"])
        for block in range(1, int(cfg["stress_restoration"]["maximum_blocks"]) + 1):
            O.run(int(cfg["stress_restoration"]["steps_per_block"]), True)
            record += 1
            row = diagnostic(record, "restored_friction_stress_servo", block, cfg, triax, sand_ids, final_radii, solid_volume)
            history.append(row)
            checks = final_checks(row, cfg)
            eligible = block >= int(cfg["stress_restoration"]["minimum_blocks"])
            streak = streak + 1 if eligible and all(checks.values()) else 0
            if block == 1 or block % 20 == 0 or streak:
                print("STAGE26W_RESTORE=" + json.dumps({"block": block, "e": row["container_void_ratio_using_final_radii"], "stress": row["principal_wall_stress_pa_compression_positive"], "coordination": row["sand_coordination_excluding_degree_lt2_rattlers"], "rattlers": row["sand_rattler_fraction_degree_lt2_iterative"], "unbalanced": row["unbalanced_force"], "ke_pV": row["normalized_kinetic_energy_pV"], "overlap": row["maximum_interobject_penetration_over_smaller_radius"], "streak": streak}, sort_keys=True), flush=True)
            if not checks["finite_state"] or row["maximum_interobject_penetration_over_smaller_radius"] > hard_guard or row["leaked_particle_count"]:
                status = "stress_restoration_hard_guard_failed"
                break
            if streak >= int(cfg["stress_restoration"]["required_consecutive_pass_blocks"]):
                status = "qualified_dense_wall_state"
                break
        final = history[-1]
        checks = final_checks(final, cfg)

    passed = status == "qualified_dense_wall_state" and all(checks.values())
    history_path = os.path.join(output, "history.csv")
    write_history(history_path, history)
    state_path = os.path.join(output, "qualified_dense_wall_state.yade.gz")
    if passed:
        O.tags["stage26w_dense_wall_metadata_json"] = json.dumps({
            "schema": "lbs.stage26w-dense-wall-state-metadata.v1",
            "config_sha256": sha256(config_path),
            "final_streak": streak,
        }, sort_keys=True, separators=(",", ":"))
        O.save(state_path)
    result = {
        "schema": "lbs.stage26w-dense-wall-shrink-regrow-result.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "passed": bool(passed),
        "claim_boundary": cfg["claim_boundary"],
        "checks": checks,
        "terminal": final,
        "records": len(history),
        "source_hashes": {
            "config": sha256(config_path),
            "runner": sha256(script_path),
            "input_state": cfg["sources"]["input_state"]["sha256"],
        },
        "artifacts": {"history": {"path": history_path, "sha256": sha256(history_path)}},
        "authority": cfg["authority"],
        "elapsed_wall_s": time.time() - START,
    }
    if passed:
        result["artifacts"]["state"] = {"path": state_path, "sha256": sha256(state_path)}
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26w-dense-wall-shrink-regrow-completion.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "passed": bool(passed),
        "result": {"path": result_path, "sha256": sha256(result_path)},
        "terminal": final,
        "checks": checks,
        "authority": cfg["authority"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26W_COMPLETION=" + completion_path, flush=True)
    print("STAGE26W_COMPLETION_SHA256=" + sha256(completion_path), flush=True)
    raise SystemExit(0 if passed else 2)


main()
