"""YADE Stage26a: one rigid F37 clump in the accepted Stage25a periodic sand."""

from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade import config, utils


CONFIG_PATH = os.path.abspath(os.environ["STAGE26_CONFIG"])
PLACEMENT_PATH = os.path.abspath(os.environ["STAGE26_PLACEMENT"])
OUTPUT_ROOT = os.path.abspath(os.environ["STAGE26_OUTPUT"])
SCRIPT_PATH = os.path.abspath(os.environ.get("STAGE26_SCRIPT", __file__))
START = time.time()


def sha256(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with open(path, "r") as stream:
        return json.load(stream)


def write_json_exclusive(path, payload):
    with open(path, "x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def windows_to_wsl(path):
    value = str(path).replace("\\", "/")
    if len(value) >= 3 and value[1:3] == ":/":
        return "/mnt/%s/%s" % (value[0].lower(), value[3:])
    return value


def diagonal_lengths():
    return [float(O.cell.hSize[index, index]) for index in range(3)]


def minimum_image(delta, lengths):
    return [float(delta[index] - round(float(delta[index]) / lengths[index]) * lengths[index]) for index in range(3)]


def vector_norm(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


def sand_network(sand_ids):
    sand_set = set(sand_ids)
    adjacency = dict((body_id, set()) for body_id in sand_ids)
    sand_contacts = 0
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        if interaction.id1 in sand_set and interaction.id2 in sand_set:
            adjacency[interaction.id1].add(interaction.id2)
            adjacency[interaction.id2].add(interaction.id1)
            sand_contacts += 1
    active = set(sand_ids)
    changed = True
    while changed:
        changed = False
        remove = [body_id for body_id in active if sum(1 for other in adjacency[body_id] if other in active) < 2]
        if remove:
            active.difference_update(remove)
            changed = True
    internal_edges = sum(1 for first in active for second in adjacency[first] if second in active and first < second)
    coordination = 2.0 * internal_edges / len(active) if active else 0.0
    return sand_contacts, len(active), 1.0 - len(active) / float(len(sand_ids)), coordination


def diagnostic(block, cfg, triax, sand_ids, fibre_parent, fibre_members, initial):
    lengths = diagonal_lengths()
    volume = float(O.cell.volume)
    stress = [-float(value) for value in triax.stress]
    target = float(cfg["relaxation"]["target_mean_effective_stress_pa_compression_positive"])
    mean_stress = sum(stress) / 3.0
    relative_mean_error = abs(mean_stress - target) / target
    principal_error = max(abs(value - target) / target for value in stress)
    unbalanced = float(utils.unbalancedForce())
    unbalanced_defined = math.isfinite(unbalanced)
    if not unbalanced_defined:
        unbalanced = 1.0
    kinetic = float(utils.kineticEnergy())
    normalized_ke = kinetic / max(abs(target * volume), 1e-30)
    sand_set = set(sand_ids); fibre_set = set(fibre_members)
    distinct_fibre_sand = set()
    sand_fibre_contacts = 0
    maximum_penetration = 0.0
    intraclump_real = 0
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        if first in fibre_set and second in fibre_set:
            intraclump_real += 1
            continue
        if first in sand_set and second in fibre_set:
            distinct_fibre_sand.add(first); sand_fibre_contacts += 1
        elif second in sand_set and first in fibre_set:
            distinct_fibre_sand.add(second); sand_fibre_contacts += 1
        first_body, second_body = O.bodies[first], O.bodies[second]
        if isinstance(first_body.shape, Sphere) and isinstance(second_body.shape, Sphere):
            penetration = max(0.0, float(interaction.geom.penetrationDepth))
            maximum_penetration = max(maximum_penetration, penetration / min(float(first_body.shape.radius), float(second_body.shape.radius)))
    sand_contacts, load_bearing, rattler_fraction, coordination = sand_network(sand_ids)

    displacements = []
    for body_id in sand_ids:
        body = O.bodies[body_id]
        fractional = [float(body.state.pos[index]) / lengths[index] for index in range(3)]
        fractional_delta = [fractional[index] - initial["sand_fractional"][str(body_id)][index] for index in range(3)]
        fractional_delta = [value - round(value) for value in fractional_delta]
        displacements.append(vector_norm([fractional_delta[index] * lengths[index] for index in range(3)]))
    rms_displacement = math.sqrt(sum(value * value for value in displacements) / len(displacements))
    max_displacement = max(displacements)

    parent = O.bodies[fibre_parent]
    com_delta = minimum_image([float(parent.state.pos[index]) - initial["fibre_com_m"][index] for index in range(3)], lengths)
    fibre_com_displacement = vector_norm(com_delta)
    first = O.bodies[fibre_members[0]].state.pos
    last = O.bodies[fibre_members[-1]].state.pos
    tip_vector = minimum_image([float(last[index] - first[index]) for index in range(3)], lengths)
    tip_span = vector_norm(tip_vector)
    initial_axis = initial["fibre_tip_vector_m"]
    cosine = sum(tip_vector[index] * initial_axis[index] for index in range(3)) / max(tip_span * vector_norm(initial_axis), 1e-30)
    rotation_deg = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
    fibre_length = float(cfg["fibre"]["contour_length_m"])
    d50 = 0.00082
    row = {
        "block": int(block), "iteration": int(O.iter), "time_s": float(O.time),
        "cell_dimensions_m": lengths, "cell_volume_m3": volume,
        "cell_volume_relative_drift": abs(volume - initial["cell_volume_m3"]) / initial["cell_volume_m3"],
        "principal_effective_stress_pa_compression_positive": stress,
        "mean_effective_stress_pa_compression_positive": mean_stress,
        "relative_mean_stress_error": relative_mean_error,
        "maximum_principal_stress_error": principal_error,
        "unbalanced_force": unbalanced, "unbalanced_force_defined": unbalanced_defined,
        "kinetic_energy_j": kinetic, "normalized_kinetic_energy_pV": normalized_ke,
        "sand_sand_real_contact_count": sand_contacts,
        "sand_fibre_real_contact_count": sand_fibre_contacts,
        "distinct_sand_contacts_per_fibre": len(distinct_fibre_sand),
        "contacted_sand_body_ids": sorted(distinct_fibre_sand),
        "intraclump_real_interaction_count": intraclump_real,
        "maximum_interobject_penetration_over_smaller_radius": maximum_penetration,
        "sand_load_bearing_particle_count_after_degree_lt2_pruning": load_bearing,
        "sand_rattler_fraction_degree_lt2_iterative": rattler_fraction,
        "sand_coordination_excluding_degree_lt2_rattlers": coordination,
        "rms_nonaffine_sand_displacement_m": rms_displacement,
        "rms_nonaffine_sand_displacement_over_D50": rms_displacement / d50,
        "maximum_nonaffine_sand_displacement_m": max_displacement,
        "maximum_nonaffine_sand_displacement_over_D50": max_displacement / d50,
        "fibre_com_displacement_m": fibre_com_displacement,
        "fibre_com_displacement_over_length": fibre_com_displacement / fibre_length,
        "fibre_tip_axis_rotation_degrees": rotation_deg,
        "fibre_tip_span_m": tip_span,
        "fibre_tip_span_relative_drift": abs(tip_span - initial["fibre_tip_span_m"]) / initial["fibre_tip_span_m"],
    }
    return row


def gates(row, cfg):
    acceptance = cfg["acceptance"]
    numeric_names = ["cell_volume_m3", "mean_effective_stress_pa_compression_positive", "unbalanced_force", "normalized_kinetic_energy_pV", "maximum_interobject_penetration_over_smaller_radius", "sand_coordination_excluding_degree_lt2_rattlers", "sand_rattler_fraction_degree_lt2_iterative", "rms_nonaffine_sand_displacement_over_D50", "maximum_nonaffine_sand_displacement_over_D50", "fibre_com_displacement_over_length", "fibre_tip_axis_rotation_degrees", "fibre_tip_span_relative_drift"]
    return {
        "finite_state": all(math.isfinite(float(row[name])) for name in numeric_names),
        "mean_stress": row["relative_mean_stress_error"] <= acceptance["maximum_relative_mean_stress_error"],
        "principal_stress": row["maximum_principal_stress_error"] <= acceptance["maximum_principal_stress_error"],
        "unbalanced_force_defined": row["unbalanced_force_defined"] is True,
        "unbalanced_force": row["unbalanced_force"] <= acceptance["maximum_unbalanced_force"],
        "normalized_kinetic_energy": row["normalized_kinetic_energy_pV"] <= acceptance["maximum_normalized_kinetic_energy_pV"],
        "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"] >= acceptance["minimum_sand_coordination_excluding_rattlers"],
        "sand_rattler_fraction": row["sand_rattler_fraction_degree_lt2_iterative"] <= acceptance["maximum_sand_rattler_fraction"],
        "fibre_engagement": row["distinct_sand_contacts_per_fibre"] >= acceptance["minimum_distinct_sand_contacts_per_fibre"],
        "penetration": row["maximum_interobject_penetration_over_smaller_radius"] <= acceptance["maximum_interobject_penetration_over_smaller_radius"],
        "sand_rms_displacement": row["rms_nonaffine_sand_displacement_over_D50"] <= acceptance["maximum_rms_sand_displacement_over_D50"],
        "sand_max_displacement": row["maximum_nonaffine_sand_displacement_over_D50"] <= acceptance["maximum_sand_displacement_over_D50"],
        "cell_volume_drift": row["cell_volume_relative_drift"] <= acceptance["maximum_cell_volume_relative_drift"],
        "fibre_rigidity": row["fibre_tip_span_relative_drift"] <= acceptance["maximum_tip_span_relative_drift"],
        "fibre_translation": row["fibre_com_displacement_over_length"] <= acceptance["maximum_fibre_com_displacement_over_length"],
        "fibre_rotation": row["fibre_tip_axis_rotation_degrees"] <= acceptance["maximum_fibre_rotation_degrees"],
        "no_intraclump_contact": row["intraclump_real_interaction_count"] == 0,
    }


def main():
    cfg = load_json(CONFIG_PATH); placement = load_json(PLACEMENT_PATH)
    if cfg.get("status") != "authorized_bounded_dry_fibre_qualification" or cfg["promotion"].get("stage26a_execution_authorized") is not True:
        raise RuntimeError("Stage26a configuration is not execution-authorized")
    if str(config.version) != str(cfg["source"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    for key in ["stage25_checkpoint_manifest", "stage25_checkpoint", "stage25_evaluation", "stage25_selected_result", "f37_geometry_review"]:
        path = windows_to_wsl(cfg["source"][key])
        if sha256(path) != cfg["source"][key + "_sha256"]:
            raise RuntimeError("source hash mismatch: " + key)
    if not placement.get("passed") or placement["source_hashes"]["config"] != sha256(CONFIG_PATH):
        raise RuntimeError("placement/config binding mismatch")
    if os.path.exists(OUTPUT_ROOT):
        raise RuntimeError("immutable output already exists")
    os.makedirs(OUTPUT_ROOT)

    checkpoint_path = windows_to_wsl(cfg["source"]["stage25_checkpoint"])
    O.load(checkpoint_path)
    sand_ids = [int(body.id) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
    if len(sand_ids) != cfg["acceptance"]["required_sand_particle_count"]:
        raise RuntimeError("Stage25 checkpoint sand count mismatch")
    lengths0 = diagonal_lengths()
    initial = {
        "cell_dimensions_m": lengths0,
        "cell_volume_m3": float(O.cell.volume),
        "sand_fractional": dict((str(body_id), [float(O.bodies[body_id].state.pos[index]) / lengths0[index] for index in range(3)]) for body_id in sand_ids),
    }
    triax = next(engine for engine in O.engines if isinstance(engine, PeriTriaxController))
    triax.goal = tuple(-float(cfg["relaxation"]["target_mean_effective_stress_pa_compression_positive"]) for _ in range(3))
    triax.maxStrainRate = tuple(float(cfg["relaxation"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["acceptance"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["acceptance"]["maximum_unbalanced_force"])
    for engine in O.engines:
        if isinstance(engine, GlobalStiffnessTimeStepper):
            engine.timestepSafetyCoefficient = float(cfg["relaxation"]["timestep_safety_coefficient"])
        if isinstance(engine, NewtonIntegrator):
            engine.damping = float(cfg["relaxation"]["newton_damping"])
            engine.gravity = Vector3(*cfg["relaxation"]["gravity_m_s2"])

    plastic_id = O.materials.append(FrictMat(
        young=float(cfg["contacts"]["plastic_young_pa"]), poisson=float(cfg["contacts"]["plastic_poisson"]),
        frictionAngle=math.atan(float(cfg["contacts"]["plastic_friction_coefficient"])),
        density=float(cfg["fibre"]["density_kg_m3"]), label="stage26a_f37_plastic",
    ))
    members = [sphere(Vector3(*centre), float(placement["member_radius_m"]), material=plastic_id, color=(0.85, 0.12, 0.10)) for centre in placement["member_centres_m"]]
    fibre_parent, fibre_members = O.bodies.appendClumped(members, 20)
    fibre_parent = int(fibre_parent); fibre_members = [int(value) for value in fibre_members]
    if len(fibre_members) != cfg["acceptance"]["required_fibre_member_count"]:
        raise RuntimeError("F37 clump member count mismatch")
    parent = O.bodies[fibre_parent]
    raw_mass = float(parent.state.mass)
    mass_factor = float(cfg["fibre"]["target_mass_kg"]) / raw_mass
    parent.state.mass = float(cfg["fibre"]["target_mass_kg"])
    parent.state.inertia = Vector3(*[float(value) * mass_factor for value in parent.state.inertia])
    O.step()
    initial["fibre_com_m"] = [float(parent.state.pos[index]) for index in range(3)]
    first = O.bodies[fibre_members[0]].state.pos; last = O.bodies[fibre_members[-1]].state.pos
    initial["fibre_tip_vector_m"] = minimum_image([float(last[index] - first[index]) for index in range(3)], diagonal_lengths())
    initial["fibre_tip_span_m"] = vector_norm(initial["fibre_tip_vector_m"])

    history = []
    streak = 0
    required = int(cfg["relaxation"]["required_consecutive_pass_blocks"])
    final_checks = None
    for block in range(1, int(cfg["relaxation"]["maximum_check_blocks"]) + 1):
        O.run(int(cfg["relaxation"]["steps_per_check_block"]), True)
        row = diagnostic(block, cfg, triax, sand_ids, fibre_parent, fibre_members, initial)
        final_checks = gates(row, cfg)
        history.append(row)
        streak = streak + 1 if all(final_checks.values()) else 0
        if block == 1 or block % 10 == 0 or streak > 0:
            print("STAGE26_PROGRESS=" + json.dumps({"block": block, "stress_pa": row["mean_effective_stress_pa_compression_positive"], "unbalanced": row["unbalanced_force"], "fibre_sand_contacts": row["distinct_sand_contacts_per_fibre"], "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"], "max_sand_displacement_D50": row["maximum_nonaffine_sand_displacement_over_D50"], "fibre_displacement_L": row["fibre_com_displacement_over_length"], "streak": streak}, sort_keys=True), flush=True)
        if streak >= required:
            break
    final = history[-1]
    passed = streak >= required and all(final_checks.values())
    history_path = os.path.join(OUTPUT_ROOT, "history.csv")
    with open(history_path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(history[0].keys()))
        writer.writeheader()
        for row in history:
            encoded = dict(row)
            for name in ["cell_dimensions_m", "principal_effective_stress_pa_compression_positive", "contacted_sand_body_ids"]:
                encoded[name] = json.dumps(encoded[name], separators=(",", ":"))
            writer.writerow(encoded)
    checkpoint = os.path.join(OUTPUT_ROOT, "dry_relaxed_state.yade.gz")
    O.save(checkpoint)
    particles = []
    for body_id in sand_ids:
        body = O.bodies[body_id]
        particles.append({"body_id": body_id, "phase": "sand", "position_m": [float(body.state.pos[index]) for index in range(3)], "radius_m": float(body.shape.radius)})
    for body_id in fibre_members:
        body = O.bodies[body_id]
        particles.append({"body_id": body_id, "phase": "fibre", "parent_id": fibre_parent, "position_m": [float(body.state.pos[index]) for index in range(3)], "radius_m": float(body.shape.radius)})
    contacts = []
    for interaction in O.interactions:
        if interaction.isReal:
            contacts.append({"id1": int(interaction.id1), "id2": int(interaction.id2), "normal_force_n": float(interaction.phys.normalForce.norm()), "shear_force_n": float(interaction.phys.shearForce.norm())})
    result = {
        "schema": "lbs.stage26a-dry-f37-insertion.v1.result", "passed": passed,
        "engine": {"yade_version": str(config.version), "features": list(config.features)},
        "source_hashes": {"config": sha256(CONFIG_PATH), "placement": sha256(PLACEMENT_PATH), "runner": sha256(SCRIPT_PATH), "stage25_checkpoint": cfg["source"]["stage25_checkpoint_sha256"]},
        "initial": initial, "terminal": final, "checks": final_checks, "consecutive_pass_blocks": streak,
        "steps_completed": int(O.iter), "sand_ids": sand_ids, "fibre_parent_id": fibre_parent, "fibre_member_ids": fibre_members,
        "particles": particles, "contacts": contacts,
        "artifacts": {"history_csv_sha256": sha256(history_path), "checkpoint_sha256": sha256(checkpoint)},
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(OUTPUT_ROOT, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26a-dry-f37-insertion.v1.completion", "passed": passed,
        "status": "passed_dry_fibre_compatibility" if passed else "completed_no_admissible_dry_fibre_state",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.time() - START,
        "result_sha256": sha256(result_path), "terminal": final, "checks": final_checks,
        "promotion": {"dry_single_fibre_checkpoint_qualified": passed, "multi_fibre_execution_authorized": False, "flow_execution_authorized": False, "transient_two_way_coupling_authorized": False, "deformation_coupled_flow_authorized": False},
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(OUTPUT_ROOT, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26_COMPLETION=" + json.dumps({"passed": passed, "status": completion["status"], "completion_sha256": sha256(completion_path), "wall_seconds": completion["wall_seconds"]}, sort_keys=True), flush=True)


try:
    main()
except Exception as error:
    if os.path.isdir(OUTPUT_ROOT) and not os.path.exists(os.path.join(OUTPUT_ROOT, "failure.json")):
        write_json_exclusive(os.path.join(OUTPUT_ROOT, "failure.json"), {"schema": "lbs.stage26a-dry-f37-insertion.v1.failure", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "error_type": type(error).__name__, "error": str(error), "config_sha256": sha256(CONFIG_PATH), "placement_sha256": sha256(PLACEMENT_PATH), "runner_sha256": sha256(SCRIPT_PATH)})
    raise
