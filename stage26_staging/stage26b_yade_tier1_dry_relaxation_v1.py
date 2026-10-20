"""YADE Stage26b: bounded two-/four-rigid-F37 dry relaxation qualification."""

from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade import config, utils


CONFIG_PATH = os.path.abspath(os.environ["STAGE26B_CONFIG"])
CASE_ID = os.environ["STAGE26B_CASE_ID"]
OUTPUT_ROOT = os.path.abspath(os.environ["STAGE26B_OUTPUT"])
SCRIPT_PATH = os.path.abspath(os.environ.get("STAGE26B_SCRIPT", __file__))
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


def zero_body_motion(body_ids):
    for body_id in body_ids:
        body = O.bodies[body_id]
        body.state.vel = Vector3.Zero
        body.state.angVel = Vector3.Zero


def sand_network(sand_ids):
    sand_set = set(sand_ids)
    adjacency = dict((body_id, set()) for body_id in sand_ids)
    sand_contacts = 0
    for interaction in O.interactions:
        if interaction.isReal and interaction.id1 in sand_set and interaction.id2 in sand_set:
            adjacency[interaction.id1].add(interaction.id2)
            adjacency[interaction.id2].add(interaction.id1)
            sand_contacts += 1
    active = set(sand_ids)
    while True:
        remove = [body_id for body_id in active if sum(1 for other in adjacency[body_id] if other in active) < 2]
        if not remove:
            break
        active.difference_update(remove)
    internal_edges = sum(1 for first in active for second in adjacency[first] if second in active and first < second)
    coordination = 2.0 * internal_edges / len(active) if active else 0.0
    return sand_contacts, len(active), 1.0 - len(active) / float(len(sand_ids)), coordination


def diagnostic(block, cfg, triax, sand_ids, fibre_parents, fibre_members_by_index, initial):
    lengths = diagonal_lengths()
    volume = float(O.cell.volume)
    stress = [-float(value) for value in triax.stress]
    target = float(cfg["relaxation"]["target_mean_effective_stress_pa_compression_positive"])
    mean_stress = sum(stress) / 3.0
    unbalanced = float(utils.unbalancedForce())
    unbalanced_defined = math.isfinite(unbalanced)
    if not unbalanced_defined:
        unbalanced = 1.0
    kinetic = float(utils.kineticEnergy())
    sand_set = set(sand_ids)
    member_to_fibre = {}
    all_fibre_members = set()
    for fibre_index, members in enumerate(fibre_members_by_index):
        for member in members:
            member_to_fibre[member] = fibre_index
            all_fibre_members.add(member)
    contacted = [set() for _ in fibre_parents]
    sand_fibre_contact_counts = [0 for _ in fibre_parents]
    fibre_fibre_real = 0
    intraclump_real = 0
    maximum_penetration = 0.0
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        first_fibre = member_to_fibre.get(first)
        second_fibre = member_to_fibre.get(second)
        if first_fibre is not None and second_fibre is not None:
            if first_fibre == second_fibre:
                intraclump_real += 1
            else:
                fibre_fibre_real += 1
        elif first in sand_set and second_fibre is not None:
            contacted[second_fibre].add(first)
            sand_fibre_contact_counts[second_fibre] += 1
        elif second in sand_set and first_fibre is not None:
            contacted[first_fibre].add(second)
            sand_fibre_contact_counts[first_fibre] += 1
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

    fibre_displacements = []
    fibre_rotations = []
    fibre_tip_drifts = []
    fibre_tip_spans = []
    for fibre_index, parent_id in enumerate(fibre_parents):
        parent = O.bodies[parent_id]
        com_delta = minimum_image([float(parent.state.pos[index]) - initial["fibres"][fibre_index]["com_m"][index] for index in range(3)], lengths)
        fibre_displacements.append(vector_norm(com_delta) / float(cfg["fibre"]["contour_length_m"]))
        members = fibre_members_by_index[fibre_index]
        first = O.bodies[members[0]].state.pos
        last = O.bodies[members[-1]].state.pos
        tip_vector = minimum_image([float(last[index] - first[index]) for index in range(3)], lengths)
        tip_span = vector_norm(tip_vector)
        initial_axis = initial["fibres"][fibre_index]["tip_vector_m"]
        cosine = sum(tip_vector[index] * initial_axis[index] for index in range(3)) / max(tip_span * vector_norm(initial_axis), 1e-30)
        fibre_rotations.append(math.degrees(math.acos(max(-1.0, min(1.0, cosine)))))
        fibre_tip_spans.append(tip_span)
        fibre_tip_drifts.append(abs(tip_span - initial["fibres"][fibre_index]["tip_span_m"]) / initial["fibres"][fibre_index]["tip_span_m"])

    distinct_counts = [len(value) for value in contacted]
    d50 = float(cfg["acceptance"]["D50_m"])
    return {
        "block": int(block), "iteration": int(O.iter), "time_s": float(O.time),
        "cell_dimensions_m": lengths, "cell_volume_m3": volume,
        "cell_volume_relative_drift": abs(volume - initial["cell_volume_m3"]) / initial["cell_volume_m3"],
        "principal_effective_stress_pa_compression_positive": stress,
        "mean_effective_stress_pa_compression_positive": mean_stress,
        "relative_mean_stress_error": abs(mean_stress - target) / target,
        "maximum_principal_stress_error": max(abs(value - target) / target for value in stress),
        "unbalanced_force": unbalanced, "unbalanced_force_defined": unbalanced_defined,
        "kinetic_energy_j": kinetic, "normalized_kinetic_energy_pV": kinetic / max(abs(target * volume), 1e-30),
        "sand_sand_real_contact_count": sand_contacts,
        "sand_sand_contact_retention_fraction": sand_contacts / float(cfg["acceptance"]["baseline_sand_sand_real_contacts"]),
        "sand_fibre_real_contact_count_by_fibre": sand_fibre_contact_counts,
        "distinct_sand_contacts_by_fibre": distinct_counts,
        "contacted_sand_body_ids_by_fibre": [sorted(value) for value in contacted],
        "minimum_distinct_sand_contacts_per_fibre": min(distinct_counts),
        "isolated_fibre_count": sum(1 for value in distinct_counts if value == 0),
        "fibre_fibre_real_interaction_count": fibre_fibre_real,
        "intraclump_real_interaction_count": intraclump_real,
        "maximum_interobject_penetration_over_smaller_radius": maximum_penetration,
        "sand_load_bearing_particle_count_after_degree_lt2_pruning": load_bearing,
        "sand_rattler_fraction_degree_lt2_iterative": rattler_fraction,
        "sand_coordination_excluding_degree_lt2_rattlers": coordination,
        "rms_nonaffine_sand_displacement_m": rms_displacement,
        "rms_nonaffine_sand_displacement_over_D50": rms_displacement / d50,
        "maximum_nonaffine_sand_displacement_m": max_displacement,
        "maximum_nonaffine_sand_displacement_over_D50": max_displacement / d50,
        "fibre_com_displacement_over_length_by_fibre": fibre_displacements,
        "maximum_fibre_com_displacement_over_length": max(fibre_displacements),
        "fibre_tip_axis_rotation_degrees_by_fibre": fibre_rotations,
        "maximum_fibre_tip_axis_rotation_degrees": max(fibre_rotations),
        "fibre_tip_span_m_by_fibre": fibre_tip_spans,
        "fibre_tip_span_relative_drift_by_fibre": fibre_tip_drifts,
        "maximum_fibre_tip_span_relative_drift": max(fibre_tip_drifts),
    }


def gates(row, cfg):
    acceptance = cfg["acceptance"]
    numeric_names = [
        "cell_volume_m3", "mean_effective_stress_pa_compression_positive", "unbalanced_force",
        "normalized_kinetic_energy_pV", "maximum_interobject_penetration_over_smaller_radius",
        "sand_coordination_excluding_degree_lt2_rattlers", "sand_rattler_fraction_degree_lt2_iterative",
        "rms_nonaffine_sand_displacement_over_D50", "maximum_nonaffine_sand_displacement_over_D50",
        "maximum_fibre_com_displacement_over_length", "maximum_fibre_tip_axis_rotation_degrees",
        "maximum_fibre_tip_span_relative_drift",
    ]
    return {
        "finite_state": all(math.isfinite(float(row[name])) for name in numeric_names),
        "mean_stress": row["relative_mean_stress_error"] <= acceptance["maximum_relative_mean_stress_error"],
        "principal_stress": row["maximum_principal_stress_error"] <= acceptance["maximum_principal_stress_error"],
        "unbalanced_force_defined": row["unbalanced_force_defined"] is True,
        "unbalanced_force": row["unbalanced_force"] <= acceptance["maximum_unbalanced_force"],
        "normalized_kinetic_energy": row["normalized_kinetic_energy_pV"] <= acceptance["maximum_normalized_kinetic_energy_pV"],
        "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"] >= acceptance["minimum_sand_coordination_excluding_rattlers"],
        "sand_rattler_fraction": row["sand_rattler_fraction_degree_lt2_iterative"] <= acceptance["maximum_sand_rattler_fraction"],
        "sand_contact_retention": row["sand_sand_contact_retention_fraction"] >= acceptance["minimum_sand_sand_contact_retention_fraction"],
        "every_fibre_engaged": row["minimum_distinct_sand_contacts_per_fibre"] >= acceptance["minimum_distinct_terminal_sand_contacts_per_fibre"],
        "no_isolated_fibre": row["isolated_fibre_count"] <= acceptance["maximum_isolated_fibre_count"],
        "penetration": row["maximum_interobject_penetration_over_smaller_radius"] <= acceptance["maximum_interobject_penetration_over_smaller_radius"],
        "sand_rms_displacement": row["rms_nonaffine_sand_displacement_over_D50"] <= acceptance["maximum_rms_sand_displacement_over_D50"],
        "sand_max_displacement": row["maximum_nonaffine_sand_displacement_over_D50"] <= acceptance["maximum_sand_displacement_over_D50"],
        "cell_volume_drift": row["cell_volume_relative_drift"] <= acceptance["maximum_cell_volume_relative_drift"],
        "all_fibres_rigid": row["maximum_fibre_tip_span_relative_drift"] <= acceptance["maximum_tip_span_relative_drift"],
        "all_fibre_translations": row["maximum_fibre_com_displacement_over_length"] <= acceptance["maximum_fibre_com_displacement_over_length"],
        "all_fibre_rotations": row["maximum_fibre_tip_axis_rotation_degrees"] <= acceptance["maximum_fibre_rotation_degrees"],
        "no_intraclump_contact": row["intraclump_real_interaction_count"] == 0,
    }


def write_history(path, rows):
    json_names = [
        "cell_dimensions_m", "principal_effective_stress_pa_compression_positive",
        "sand_fibre_real_contact_count_by_fibre", "distinct_sand_contacts_by_fibre",
        "contacted_sand_body_ids_by_fibre", "fibre_com_displacement_over_length_by_fibre",
        "fibre_tip_axis_rotation_degrees_by_fibre", "fibre_tip_span_m_by_fibre",
        "fibre_tip_span_relative_drift_by_fibre",
    ]
    with open(path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for name in json_names:
                encoded[name] = json.dumps(encoded[name], separators=(",", ":"))
            writer.writerow(encoded)


def main():
    cfg = load_json(CONFIG_PATH)
    if cfg.get("status") != "authorized_bounded_tier1_dry_yade_execution":
        raise RuntimeError("configuration is not Tier-1 execution-authorized")
    if not cfg["authority"]["tier1_two_and_four_fibre_yade_execution_authorized"]:
        raise RuntimeError("Tier-1 execution authority is false")
    if any(cfg["authority"][key] for key in (
            "eight_or_more_fibre_execution_authorized", "flow_execution_authorized",
            "transient_two_way_coupling_authorized", "deformation_coupled_flow_authorized",
            "production_parametric_study_authorized")):
        raise RuntimeError("downstream authority violation")
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)
    case = next((row for row in cfg["cases"] if row["case_id"] == CASE_ID), None)
    if case is None:
        raise RuntimeError("case is outside frozen Tier-1 authority")
    placement_path = windows_to_wsl(case["placement"])
    if sha256(placement_path) != case["placement_sha256"]:
        raise RuntimeError("placement hash mismatch")
    placement = load_json(placement_path)
    if not placement.get("passed") or placement["fibre_count"] != case["fibre_count"]:
        raise RuntimeError("placement did not pass or fibre count mismatches")
    checkpoint_manifest = load_json(windows_to_wsl(cfg["sources"]["tier1_placement_checkpoint"]))
    checkpoint_case = next((row for row in checkpoint_manifest["cases"] if row["case_id"] == CASE_ID), None)
    if not checkpoint_manifest.get("passed") or checkpoint_case is None or checkpoint_case["placement_sha256"] != case["placement_sha256"]:
        raise RuntimeError("Tier-1 checkpoint case binding failed")
    if os.path.exists(OUTPUT_ROOT):
        raise RuntimeError("immutable output already exists")
    os.makedirs(OUTPUT_ROOT)

    O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    sand_ids = [int(body.id) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
    if len(sand_ids) != cfg["acceptance"]["required_sand_particle_count"]:
        raise RuntimeError("Stage25 checkpoint sand count mismatch")
    if cfg["relaxation"].get("reset_checkpoint_particle_velocities") is not True or cfg["relaxation"].get("release_all_fibres_together") is not True:
        raise RuntimeError("frozen reset/release protocol is not enabled")
    zero_body_motion(sand_ids)
    lengths0 = diagonal_lengths()
    initial = {
        "cell_dimensions_m": lengths0,
        "cell_volume_m3": float(O.cell.volume),
        "sand_fractional": dict((str(body_id), [float(O.bodies[body_id].state.pos[index]) / lengths0[index] for index in range(3)]) for body_id in sand_ids),
        "checkpoint_velocities_reset": True,
        "fibres": [],
    }
    triax = next(engine for engine in O.engines if isinstance(engine, PeriTriaxController))
    triax.dead = False
    target = float(cfg["relaxation"]["target_mean_effective_stress_pa_compression_positive"])
    triax.goal = tuple(-target for _ in range(3))
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
        young=float(cfg["contacts"]["plastic_young_pa"]),
        poisson=float(cfg["contacts"]["plastic_poisson"]),
        frictionAngle=math.atan(float(cfg["contacts"]["plastic_friction_coefficient"])),
        density=float(cfg["fibre"]["density_kg_m3"]), label="stage26b_f37_plastic",
    ))
    fibre_parents = []
    fibre_members_by_index = []
    for fibre in placement["fibres"]:
        members = [sphere(Vector3(*centre), float(placement["member_radius_m"]), material=plastic_id, color=(0.85, 0.12, 0.10)) for centre in fibre["member_centres_m"]]
        parent_id, member_ids = O.bodies.appendClumped(members, 20)
        parent_id = int(parent_id)
        member_ids = [int(value) for value in member_ids]
        if len(member_ids) != cfg["acceptance"]["required_members_per_fibre"]:
            raise RuntimeError("F37 clump member count mismatch")
        parent = O.bodies[parent_id]
        raw_mass = float(parent.state.mass)
        factor = float(cfg["fibre"]["target_mass_per_fibre_kg"]) / raw_mass
        parent.state.mass = float(cfg["fibre"]["target_mass_per_fibre_kg"])
        parent.state.inertia = Vector3(*[float(value) * factor for value in parent.state.inertia])
        parent.state.blockedDOFs = "xyzXYZ"
        fibre_parents.append(parent_id)
        fibre_members_by_index.append(member_ids)
    zero_body_motion(sand_ids + fibre_parents)
    O.step()
    for fibre_index, parent_id in enumerate(fibre_parents):
        parent = O.bodies[parent_id]
        members = fibre_members_by_index[fibre_index]
        first = O.bodies[members[0]].state.pos
        last = O.bodies[members[-1]].state.pos
        tip_vector = minimum_image([float(last[index] - first[index]) for index in range(3)], diagonal_lengths())
        initial["fibres"].append({
            "fibre_index": fibre_index,
            "com_m": [float(parent.state.pos[index]) for index in range(3)],
            "tip_vector_m": tip_vector,
            "tip_span_m": vector_norm(tip_vector),
        })

    conditioning = []
    for block in range(1, int(cfg["relaxation"]["fixed_all_fibres_conditioning_blocks"]) + 1):
        O.run(int(cfg["relaxation"]["fixed_fibre_steps_per_block"]), True)
        row = diagnostic(block, cfg, triax, sand_ids, fibre_parents, fibre_members_by_index, initial)
        row["stage"] = "fixed_all_fibres_conditioning"
        conditioning.append(row)
        if block == 1 or block % 10 == 0:
            print("STAGE26B_CONDITIONING=" + json.dumps({
                "case_id": CASE_ID, "block": block, "unbalanced": row["unbalanced_force"],
                "contacts_by_fibre": row["distinct_sand_contacts_by_fibre"],
                "sand_contacts": row["sand_sand_real_contact_count"],
                "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"],
                "max_sand_displacement_D50": row["maximum_nonaffine_sand_displacement_over_D50"],
            }, sort_keys=True), flush=True)
    for parent_id in fibre_parents:
        O.bodies[parent_id].state.blockedDOFs = ""
    zero_body_motion(sand_ids + fibre_parents)

    free = []
    streak = 0
    final_checks = None
    required = int(cfg["relaxation"]["required_consecutive_pass_blocks"])
    for block in range(1, int(cfg["relaxation"]["maximum_check_blocks"]) + 1):
        O.run(int(cfg["relaxation"]["steps_per_check_block"]), True)
        row = diagnostic(block, cfg, triax, sand_ids, fibre_parents, fibre_members_by_index, initial)
        row["stage"] = "free_all_fibres_relaxation"
        final_checks = gates(row, cfg)
        free.append(row)
        streak = streak + 1 if all(final_checks.values()) else 0
        if block == 1 or block % 10 == 0 or streak > 0:
            print("STAGE26B_FREE=" + json.dumps({
                "case_id": CASE_ID, "block": block, "stress_pa": row["mean_effective_stress_pa_compression_positive"],
                "unbalanced": row["unbalanced_force"], "contacts_by_fibre": row["distinct_sand_contacts_by_fibre"],
                "sand_contacts": row["sand_sand_real_contact_count"],
                "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"],
                "max_sand_displacement_D50": row["maximum_nonaffine_sand_displacement_over_D50"],
                "max_fibre_displacement_L": row["maximum_fibre_com_displacement_over_length"],
                "streak": streak,
            }, sort_keys=True), flush=True)
        if streak >= required:
            break
    final = free[-1]
    passed = streak >= required and all(final_checks.values())
    conditioning_path = os.path.join(OUTPUT_ROOT, "conditioning_history.csv")
    free_path = os.path.join(OUTPUT_ROOT, "free_relaxation_history.csv")
    write_history(conditioning_path, conditioning)
    write_history(free_path, free)
    checkpoint_path = os.path.join(OUTPUT_ROOT, "dry_relaxed_state.yade.gz")
    O.save(checkpoint_path)
    particles = []
    for body_id in sand_ids:
        body = O.bodies[body_id]
        particles.append({"body_id": body_id, "phase": "sand", "position_m": [float(body.state.pos[index]) for index in range(3)], "radius_m": float(body.shape.radius)})
    for fibre_index, members in enumerate(fibre_members_by_index):
        for body_id in members:
            body = O.bodies[body_id]
            particles.append({"body_id": body_id, "phase": "fibre", "fibre_index": fibre_index, "parent_id": fibre_parents[fibre_index], "position_m": [float(body.state.pos[index]) for index in range(3)], "radius_m": float(body.shape.radius)})
    contacts = []
    for interaction in O.interactions:
        if interaction.isReal:
            contacts.append({"id1": int(interaction.id1), "id2": int(interaction.id2), "normal_force_n": float(interaction.phys.normalForce.norm()), "shear_force_n": float(interaction.phys.shearForce.norm())})
    result = {
        "schema": "lbs.stage26b-tier1-dry-relaxation.v1.result", "passed": passed,
        "case": case,
        "engine": {"yade_version": str(config.version), "features": list(config.features)},
        "protocol": {"fixed_all_fibres_conditioning_blocks": len(conditioning), "free_all_fibres_relaxation_blocks": len(free), "checkpoint_velocities_reset": True, "simultaneous_release": True},
        "source_hashes": {"config": sha256(CONFIG_PATH), "placement": sha256(placement_path), "runner": sha256(SCRIPT_PATH), "stage25_checkpoint": cfg["sources"]["stage25_checkpoint_sha256"], "tier1_placement_checkpoint": cfg["sources"]["tier1_placement_checkpoint_sha256"]},
        "initial": initial, "conditioning_terminal": conditioning[-1], "terminal": final,
        "checks": final_checks, "consecutive_pass_blocks": streak, "steps_completed": int(O.iter),
        "sand_ids": sand_ids, "fibre_parent_ids": fibre_parents, "fibre_member_ids_by_fibre": fibre_members_by_index,
        "particles": particles, "contacts": contacts,
        "artifacts": {"conditioning_history_csv_sha256": sha256(conditioning_path), "free_relaxation_history_csv_sha256": sha256(free_path), "checkpoint_sha256": sha256(checkpoint_path)},
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(OUTPUT_ROOT, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26b-tier1-dry-relaxation.v1.completion", "passed": passed,
        "status": "passed_tier1_dry_multifibre_compatibility" if passed else "completed_no_admissible_tier1_dry_multifibre_state",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.time() - START,
        "case": case, "result_sha256": sha256(result_path), "terminal": final,
        "conditioning_terminal": conditioning[-1], "checks": final_checks,
        "promotion": {"independent_evaluation_authorized": True, "eight_or_more_fibre_execution_authorized": False, "flow_execution_authorized": False, "transient_two_way_coupling_authorized": False, "deformation_coupled_flow_authorized": False},
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(OUTPUT_ROOT, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26B_COMPLETION=" + json.dumps({"case_id": CASE_ID, "passed": passed, "status": completion["status"], "completion_sha256": sha256(completion_path), "wall_seconds": completion["wall_seconds"]}, sort_keys=True), flush=True)


try:
    main()
except Exception as error:
    if os.path.isdir(OUTPUT_ROOT) and not os.path.exists(os.path.join(OUTPUT_ROOT, "failure.json")):
        write_json_exclusive(os.path.join(OUTPUT_ROOT, "failure.json"), {
            "schema": "lbs.stage26b-tier1-dry-relaxation.v1.failure",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "case_id": CASE_ID,
            "error_type": type(error).__name__, "error": str(error),
            "config_sha256": sha256(CONFIG_PATH), "runner_sha256": sha256(SCRIPT_PATH),
        })
    raise
