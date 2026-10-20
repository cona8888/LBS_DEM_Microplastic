"""Stage26q clean-sand density-controller qualification pilot for YADE 2022.01a."""
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
    path = str(path)
    if len(path) >= 3 and path[1:3] in (":\\", ":/"):
        drive = path[0].lower()
        return "/mnt/%s/%s" % (drive, path[3:].replace("\\", "/"))
    return path


def write_json_exclusive(path, data):
    with open(path, "x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def find_engine(class_name):
    matches = [engine for engine in O.engines if engine.__class__.__name__ == class_name]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one %s, found %d" % (class_name, len(matches)))
    return matches[0]


def wall_dimensions(triax):
    x0 = float(O.bodies[triax.wall_left_id].state.pos[0])
    x1 = float(O.bodies[triax.wall_right_id].state.pos[0])
    y0 = float(O.bodies[triax.wall_bottom_id].state.pos[1])
    y1 = float(O.bodies[triax.wall_top_id].state.pos[1])
    z0 = float(O.bodies[triax.wall_back_id].state.pos[2])
    z1 = float(O.bodies[triax.wall_front_id].state.pos[2])
    return [x1 - x0, y1 - y0, z1 - z0], [x0, y0, z0], [x1, y1, z1]


def iterative_network(sand_ids):
    sand_set = set(sand_ids)
    edges = []
    for interaction in O.interactions:
        if interaction.isReal and interaction.id1 in sand_set and interaction.id2 in sand_set:
            edges.append((int(interaction.id1), int(interaction.id2)))
    active = set(sand_ids)
    changed = True
    while changed:
        degree = {body_id: 0 for body_id in active}
        for first, second in edges:
            if first in active and second in active:
                degree[first] += 1
                degree[second] += 1
        remove = {body_id for body_id, value in degree.items() if value < 2}
        changed = bool(remove)
        active.difference_update(remove)
    retained = sum(1 for first, second in edges if first in active and second in active)
    coordination = 2.0 * retained / len(active) if active else 0.0
    return len(edges), len(active), 1.0 - len(active) / float(len(sand_ids)), coordination


def diagnostic(record, phase, phase_index, cfg, triax, sand_ids, solid_volume):
    dimensions, lower, upper = wall_dimensions(triax)
    volume = dimensions[0] * dimensions[1] * dimensions[2]
    stresses = [
        -float(triax.stress(triax.wall_right_id)[0]),
        -float(triax.stress(triax.wall_top_id)[1]),
        -float(triax.stress(triax.wall_front_id)[2]),
    ]
    target_stress = float(cfg["stress_restoration"]["target_isotropic_stress_pa_compression_positive"])
    mean_stress = sum(stresses) / 3.0
    unbalanced = float(utils.unbalancedForce())
    if not math.isfinite(unbalanced):
        unbalanced = 1.0
    kinetic = float(utils.kineticEnergy())
    contacts, active, rattlers, coordination = iterative_network(sand_ids)
    sand_set = set(sand_ids)
    maximum_penetration = 0.0
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        sphere_ids = [body_id for body_id in (first, second) if body_id in sand_set]
        if not sphere_ids:
            continue
        denominator = min(float(O.bodies[body_id].shape.radius) for body_id in sphere_ids)
        penetration = max(0.0, float(interaction.geom.penetrationDepth))
        maximum_penetration = max(maximum_penetration, penetration / denominator)
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
    return {
        "record": int(record),
        "phase": phase,
        "phase_index": int(phase_index),
        "iteration": int(O.iter),
        "time_s": float(O.time),
        "wall_dimensions_m": dimensions,
        "wall_volume_m3": volume,
        "container_void_ratio": volume / solid_volume - 1.0,
        "principal_wall_stress_pa_compression_positive": stresses,
        "mean_wall_stress_pa_compression_positive": mean_stress,
        "relative_mean_wall_stress_error": abs(mean_stress - target_stress) / target_stress,
        "maximum_principal_wall_stress_error": max(abs(value - target_stress) / target_stress for value in stresses),
        "unbalanced_force": unbalanced,
        "kinetic_energy_j": kinetic,
        "normalized_kinetic_energy_pV": kinetic / (target_stress * volume),
        "sand_sand_real_contact_count": contacts,
        "sand_load_bearing_particle_count_after_degree_lt2_pruning": active,
        "sand_rattler_fraction_degree_lt2_iterative": rattlers,
        "sand_coordination_excluding_degree_lt2_rattlers": coordination,
        "maximum_interobject_penetration_over_smaller_radius": maximum_penetration,
        "particle_count": len(sand_ids),
        "leaked_particle_count": leakage,
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


def final_checks(row, cfg):
    limits = cfg["acceptance"]
    target_e = float(cfg["density_ramp"]["reference_void_ratio"])
    finite = [
        row["container_void_ratio"],
        row["mean_wall_stress_pa_compression_positive"],
        row["unbalanced_force"],
        row["kinetic_energy_j"],
        row["maximum_interobject_penetration_over_smaller_radius"],
    ]
    return {
        "finite_state": all(math.isfinite(float(value)) for value in finite),
        "void_ratio": abs(row["container_void_ratio"] - target_e) <= float(limits["maximum_terminal_void_ratio_error"]),
        "mean_stress": row["relative_mean_wall_stress_error"] <= float(limits["maximum_relative_mean_wall_stress_error"]),
        "principal_stress": row["maximum_principal_wall_stress_error"] <= float(limits["maximum_principal_wall_stress_error"]),
        "unbalanced_force": row["unbalanced_force"] <= float(limits["maximum_unbalanced_force"]),
        "normalized_kinetic_energy": row["normalized_kinetic_energy_pV"] <= float(limits["maximum_normalized_kinetic_energy_pV"]),
        "overlap": row["maximum_interobject_penetration_over_smaller_radius"] <= float(limits["maximum_penetration_over_smaller_radius"]),
        "coordination": row["sand_coordination_excluding_degree_lt2_rattlers"] >= float(limits["minimum_sand_coordination_excluding_rattlers"]),
        "rattlers": row["sand_rattler_fraction_degree_lt2_iterative"] <= float(limits["maximum_sand_rattler_fraction"]),
        "particle_count": row["particle_count"] == int(limits["required_particle_count"]),
        "no_leakage": row["leaked_particle_count"] <= int(limits["maximum_leaked_particle_count"]),
    }


def main():
    config_path = os.path.abspath(os.environ["STAGE26Q_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26Q_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26Q_SCRIPT", __file__))
    with open(config_path, "r") as stream:
        cfg = json.load(stream)
    if cfg.get("status") != "authorized_stage26q_clean_density_controller_pilot":
        raise RuntimeError("configuration is not Stage26q-authorized")
    authority = cfg.get("authority", {})
    if authority.get("clean_density_controller_pilot_authorized") is not True:
        raise RuntimeError("clean density-controller pilot lacks authority")
    if any(authority.get(key, False) for key in (
        "single_fibre_execution_authorized",
        "full_mixture_execution_authorized",
        "flexible_fibre_execution_authorized",
        "flow_execution_authorized",
        "permeability_claim_authorized",
        "production_parametric_study_authorized",
    )):
        raise RuntimeError("Stage26q authority boundary exceeded")
    if sha256(script_path) != cfg["sources"]["runner"]["sha256"]:
        raise RuntimeError("runner hash mismatch")
    for name in ("stage25_reference", "stage26o_clean_control", "stage26p_mechanism_checkpoint", "research_contract", "input_state"):
        binding = cfg["sources"][name]
        if sha256(windows_to_wsl(binding["path"])) != binding["sha256"]:
            raise RuntimeError("source hash mismatch: " + name)
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("YADE version mismatch")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26q output exists")
    os.makedirs(output)

    O.load(windows_to_wsl(cfg["sources"]["input_state"]["path"]))
    triax = find_engine("TriaxialStressController")
    newton = find_engine("NewtonIntegrator")
    stepper = find_engine("GlobalStiffnessTimeStepper")
    newton.gravity = Vector3(0.0, 0.0, 0.0)
    sand_ids = [
        int(body.id)
        for body in O.bodies
        if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember
    ]
    if len(sand_ids) != int(cfg["sand"]["particle_count"]):
        raise RuntimeError("input state particle count mismatch")
    solid_volume = sum(4.0 * math.pi * float(O.bodies[body_id].shape.radius) ** 3 / 3.0 for body_id in sand_ids)
    history = []
    record = 0
    hard_guard = float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"])

    ramp = cfg["density_ramp"]
    target_e = float(ramp["reference_void_ratio"])
    triax.internalCompaction = False
    triax.dead = False
    triax.stressMask = 0
    rate = float(ramp["isotropic_compressive_strain_rate_per_s"])
    triax.goal1 = triax.goal2 = triax.goal3 = rate
    newton.damping = float(ramp["newton_damping"])
    stepper.timestepSafetyCoefficient = float(ramp["timestep_safety_coefficient"])
    ramp_ok = False
    status = "density_ramp_not_qualified"
    for block in range(1, int(ramp["maximum_blocks"]) + 1):
        O.run(int(ramp["steps_per_block"]), True)
        record += 1
        row = diagnostic(record, "isotropic_density_ramp", block, cfg, triax, sand_ids, solid_volume)
        history.append(row)
        if block == 1 or block % 20 == 0 or row["container_void_ratio"] <= target_e + 0.01:
            print("STAGE26Q_RAMP=" + json.dumps({"block": block, "e": row["container_void_ratio"], "stress": row["mean_wall_stress_pa_compression_positive"], "overlap": row["maximum_interobject_penetration_over_smaller_radius"]}, sort_keys=True), flush=True)
        if row["maximum_interobject_penetration_over_smaller_radius"] > hard_guard or row["leaked_particle_count"]:
            status = "density_ramp_hard_guard_failed"
            break
        if row["container_void_ratio"] <= target_e:
            triax.dead = True
            ramp_ok = abs(row["container_void_ratio"] - target_e) <= float(ramp["handoff_void_ratio_tolerance"])
            status = "fixed_volume_hold_not_qualified" if ramp_ok else "density_ramp_overshoot"
            break

    hold_ok = False
    if ramp_ok:
        hold = cfg["fixed_volume_hold"]
        newton.damping = float(hold["newton_damping"])
        streak = 0
        for block in range(1, int(hold["maximum_blocks"]) + 1):
            O.run(int(hold["steps_per_block"]), True)
            record += 1
            row = diagnostic(record, "fixed_volume_hold", block, cfg, triax, sand_ids, solid_volume)
            history.append(row)
            ok = (
                block >= int(hold["minimum_blocks"])
                and row["unbalanced_force"] <= float(hold["maximum_unbalanced_force"])
                and row["normalized_kinetic_energy_pV"] <= float(hold["maximum_normalized_kinetic_energy_pV"])
                and row["maximum_interobject_penetration_over_smaller_radius"] <= hard_guard
                and row["leaked_particle_count"] == 0
            )
            streak = streak + 1 if ok else 0
            if block == 1 or block % 20 == 0 or streak:
                print("STAGE26Q_HOLD=" + json.dumps({"block": block, "e": row["container_void_ratio"], "unbalanced": row["unbalanced_force"], "ke_pV": row["normalized_kinetic_energy_pV"], "streak": streak}, sort_keys=True), flush=True)
            if row["maximum_interobject_penetration_over_smaller_radius"] > hard_guard or row["leaked_particle_count"]:
                status = "fixed_volume_hold_hard_guard_failed"
                break
            if streak >= int(hold["required_consecutive_pass_blocks"]):
                hold_ok = True
                status = "stress_restoration_not_qualified"
                break

    final = None
    checks = None
    if hold_ok:
        restore = cfg["stress_restoration"]
        target_stress = float(restore["target_isotropic_stress_pa_compression_positive"])
        triax.stressMask = 7
        triax.goal1 = triax.goal2 = triax.goal3 = -target_stress
        triax.max_vel = float(restore["controller_maximum_wall_velocity_m_s"])
        triax.dead = False
        newton.damping = float(restore["newton_damping"])
        stepper.timestepSafetyCoefficient = float(restore["timestep_safety_coefficient"])
        streak = 0
        for block in range(1, int(restore["maximum_blocks"]) + 1):
            O.run(int(restore["steps_per_block"]), True)
            record += 1
            row = diagnostic(record, "stress_restoration_100Pa", block, cfg, triax, sand_ids, solid_volume)
            history.append(row)
            checks = final_checks(row, cfg)
            eligible = block >= int(restore["minimum_blocks"])
            streak = streak + 1 if eligible and all(checks.values()) else 0
            if block == 1 or block % 20 == 0 or streak:
                print("STAGE26Q_RESTORE=" + json.dumps({"block": block, "e": row["container_void_ratio"], "stress": row["principal_wall_stress_pa_compression_positive"], "unbalanced": row["unbalanced_force"], "streak": streak}, sort_keys=True), flush=True)
            if not checks["finite_state"] or row["maximum_interobject_penetration_over_smaller_radius"] > hard_guard or row["leaked_particle_count"]:
                status = "stress_restoration_hard_guard_failed"
                break
            if streak >= int(restore["required_consecutive_pass_blocks"]):
                status = "qualified_clean_density_controller"
                final = row
                break

    if final is None and history:
        final = history[-1]
        checks = final_checks(final, cfg)
    passed = status == "qualified_clean_density_controller" and checks is not None and all(checks.values())
    history_path = os.path.join(output, "history.csv")
    write_history(history_path, history)
    state_path = os.path.join(output, "qualified_dense_clean_state.yade.gz")
    if passed:
        O.save(state_path)
    result = {
        "schema": "lbs.stage26q-clean-density-controller-result.v1",
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
        "schema": "lbs.stage26q-clean-density-controller-completion.v1",
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
    print("STAGE26Q_COMPLETION=" + completion_path, flush=True)
    print("STAGE26Q_COMPLETION_SHA256=" + sha256(completion_path), flush=True)
    raise SystemExit(0 if passed else 2)


main()
