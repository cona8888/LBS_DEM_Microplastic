"""Stage26o spent-development two-F37 joint gravity-deposition case."""
from __future__ import print_function

import csv
import importlib.util
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(os.environ.get("STAGE26O_MIXTURE_SCRIPT", __file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
V9_PATH = os.path.join(HERE, "run_stage26o_clean_sand_control_v9.py")
SPEC = importlib.util.spec_from_file_location("stage26o_control_v9", V9_PATH)
control = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(control)
core = control.core
for symbol, value in list(globals().items()):
    if not symbol.startswith("__") and symbol not in {"control", "core", "SPEC"}:
        core.__dict__.setdefault(symbol, value)

from yade import config, utils
from stage26b_revision2_prefilter_common_v1 import load_json, sha256, windows_to_wsl, write_json_exclusive

START = time.time()


def bind(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def quaternion(body):
    return tuple(float(body.state.ori[index]) for index in range(4))


def fibre_motion(parent_ids, initial_poses, d50):
    translations, rotations = [], []
    for index, parent_id in enumerate(parent_ids):
        body = O.bodies[parent_id]
        delta = [float(body.state.pos[k]) - initial_poses[index]["position"][k] for k in range(3)]
        translations.append(math.sqrt(sum(value * value for value in delta)))
        current = quaternion(body)
        initial = initial_poses[index]["orientation"]
        dot = max(-1.0, min(1.0, abs(sum(current[k] * initial[k] for k in range(4)))))
        rotations.append(math.degrees(2.0 * math.acos(dot)))
    return {
        "fibre_translation_m_by_fibre": translations,
        "fibre_translation_over_D50_by_fibre": [value / d50 for value in translations],
        "fibre_rotation_deg_by_fibre": rotations,
    }


def diagnostic(record, phase, phase_index, cfg, triax, sand_ids, sand_volume, total_weight, fibre_members, parent_ids, initial_poses, wall_ids):
    row = control.direct_reaction_diagnostic(record, phase, phase_index, cfg, triax, sand_ids, sand_volume, total_weight)
    sand_set, wall_set = set(sand_ids), set(wall_ids)
    member_to_fibre = {}
    for fibre_index, members in enumerate(fibre_members):
        for member_id in members:
            member_to_fibre[int(member_id)] = fibre_index
    contacted = [set() for _ in fibre_members]
    fibre_wall = [0 for _ in fibre_members]
    fibre_fibre = 0
    maximum_penetration = 0.0
    sand_wall = 0
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        first_fibre, second_fibre = member_to_fibre.get(first), member_to_fibre.get(second)
        if first in sand_set and second_fibre is not None:
            contacted[second_fibre].add(first)
        elif second in sand_set and first_fibre is not None:
            contacted[first_fibre].add(second)
        elif first_fibre is not None and second_fibre is not None and first_fibre != second_fibre:
            fibre_fibre += 1
        if first_fibre is not None and second in wall_set:
            fibre_wall[first_fibre] += 1
        elif second_fibre is not None and first in wall_set:
            fibre_wall[second_fibre] += 1
        if (first in sand_set and second in wall_set) or (second in sand_set and first in wall_set):
            sand_wall += 1
        penetration = max(0.0, float(interaction.geom.penetrationDepth))
        radii = []
        for body_id in (first, second):
            body = O.bodies[body_id]
            if isinstance(body.shape, Sphere):
                radii.append(float(body.shape.radius))
        if radii:
            maximum_penetration = max(maximum_penetration, penetration / min(radii))
    distinct = [len(values) for values in contacted]
    row["sand_wall_real_contact_count"] = sand_wall
    row["distinct_sand_contacts_by_fibre"] = distinct
    row["contacted_sand_body_ids_by_fibre"] = [sorted(values) for values in contacted]
    row["minimum_distinct_sand_contacts_per_fibre"] = min(distinct)
    row["isolated_fibre_count"] = sum(1 for value in distinct if value == 0)
    row["fibre_wall_real_contact_count_by_fibre"] = fibre_wall
    row["total_fibre_wall_real_contact_count"] = sum(fibre_wall)
    row["fibre_fibre_real_contact_count"] = fibre_fibre
    row["maximum_interobject_penetration_over_smaller_radius"] = maximum_penetration
    row["fibre_member_count_by_fibre"] = [len(members) for members in fibre_members]
    row["exact_fibre_member_radius_m"] = float(cfg["fibre"]["member_radius_m"])
    row.update(fibre_motion(parent_ids, initial_poses, float(cfg["sand"]["D50_m"])))
    return row


def final_gate(row, cfg):
    checks = control.phase_aware_gate(row, cfg)
    if row.get("phase") == "zero_gravity_final_hold":
        acceptance = cfg["acceptance"]
        checks["fibre_sand_contacts"] = row["minimum_distinct_sand_contacts_per_fibre"] >= acceptance["minimum_distinct_sand_contacts_per_fibre"]
        checks["no_isolated_fibre"] = row["isolated_fibre_count"] == 0
        checks["no_fibre_wall_support"] = row["total_fibre_wall_real_contact_count"] <= acceptance["maximum_fibre_wall_contacts"]
        checks["exact_fibre_geometry"] = row["fibre_member_count_by_fibre"] == [37, 37] and abs(row["exact_fibre_member_radius_m"] - 5.0e-5) <= 1.0e-15
    return checks


def write_history(path, rows):
    json_fields = {"wall_dimensions_m", "principal_wall_stress_pa_compression_positive", "distinct_sand_contacts_by_fibre", "contacted_sand_body_ids_by_fibre", "fibre_wall_real_contact_count_by_fibre", "fibre_member_count_by_fibre", "fibre_translation_m_by_fibre", "fibre_translation_over_D50_by_fibre", "fibre_rotation_deg_by_fibre"}
    with open(path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for field in json_fields:
                if field in encoded:
                    encoded[field] = json.dumps(encoded[field], separators=(",", ":"))
            writer.writerow(encoded)


def main():
    config_path = os.path.abspath(os.environ["STAGE26O_MIXTURE_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26O_MIXTURE_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26O_MIXTURE_SCRIPT", __file__))
    cfg = load_json(config_path)
    if cfg.get("status") != "authorized_stage26o_spent_development_two_fibre_mixture":
        raise RuntimeError("configuration is not mixture-authorized")
    authority = cfg["authority"]
    if authority.get("spent_development_mixture_authorized") is not True or any(authority.get(key, False) for key in ("heldout_execution_authorized", "flow_execution_authorized", "deformation_authorized", "production_parametric_study_authorized")):
        raise RuntimeError("Stage26o mixture authority exceeded")
    bind(cfg)
    if sha256(script_path) != cfg["sources"]["runner_sha256"] or str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("runner or YADE version mismatch")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26o mixture output exists")

    O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    radii = [float(body.shape.radius) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
    if len(radii) != 216:
        raise RuntimeError("Stage25 radius count mismatch")
    sand_volume = sum(4.0 * math.pi * radius ** 3 / 3.0 for radius in radii)
    initial_length = (sand_volume * (1.0 + float(cfg["initialization"]["initial_void_ratio"]))) ** (1.0 / 3.0)
    placement = load_json(windows_to_wsl(cfg["sources"]["placement"]))
    offsets = []
    for fibre in placement["fibres"]:
        centres = [[float(value) for value in centre] for centre in fibre["member_centres_m"]]
        pivot = [sum(centre[k] for centre in centres) / len(centres) for k in range(3)]
        offsets.append([[centre[k] - pivot[k] for k in range(3)] for centre in centres])
    fractions = cfg["initialization"]["fibre_pivot_fractions"]
    fibre_centres = [[[float(fractions[index][k]) * initial_length + offset[k] for k in range(3)] for offset in offsets[index]] for index in range(2)]
    member_radius = float(cfg["fibre"]["member_radius_m"])
    obstacles = [(centre, member_radius) for group in fibre_centres for centre in group]
    if any(any(centre[k] < member_radius or centre[k] > initial_length - member_radius for k in range(3)) for centre, _ in obstacles):
        raise RuntimeError("initial fibre is outside wall clearance")
    rng = random.Random(int(cfg["initialization"]["deterministic_rsa_seed"]))
    placed = []
    for original_index, radius in sorted(enumerate(radii), key=lambda item: item[1], reverse=True):
        accepted = None
        for _ in range(int(cfg["initialization"]["maximum_trials_per_particle"])):
            centre = [rng.uniform(radius, initial_length - radius) for __ in range(3)]
            all_objects = [(other[1], other[2]) for other in placed] + obstacles
            if all(sum((centre[k] - other_centre[k]) ** 2 for k in range(3)) >= (radius + other_radius) ** 2 for other_centre, other_radius in all_objects):
                accepted = centre
                break
        if accepted is None:
            raise RuntimeError("joint deterministic RSA failed")
        placed.append((original_index, accepted, radius))
    placed.sort(key=lambda item: item[0])

    O.reset()
    O.periodic = False
    sand_mat = O.materials.append(FrictMat(young=float(cfg["sand"]["young_pa"]), poisson=float(cfg["sand"]["poisson"]), frictionAngle=math.atan(float(cfg["sand"]["friction_coefficient"])), density=float(cfg["sand"]["density_kg_m3"]), label="stage26o_lbs_sand"))
    fibre_mat = O.materials.append(FrictMat(young=float(cfg["fibre"]["young_pa"]), poisson=float(cfg["fibre"]["poisson"]), frictionAngle=math.atan(float(cfg["fibre"]["friction_coefficient"])), density=float(cfg["fibre"]["density_kg_m3"]), label="stage26o_f37_plastic"))
    wall_mat = O.materials.append(FrictMat(young=float(cfg["sand"]["young_pa"]), poisson=float(cfg["sand"]["poisson"]), frictionAngle=math.atan(float(cfg["walls"]["friction_coefficient"])), density=0.0, label="stage26o_frictionless_walls"))
    wall_ids = [int(value) for value in O.bodies.append(aabbWalls([Vector3(0, 0, 0), Vector3(initial_length, initial_length, initial_length)], thickness=float(cfg["walls"]["thickness_m"]), material=wall_mat))]
    parent_ids, fibre_members = [], []
    for centres in fibre_centres:
        bodies = [sphere(Vector3(*centre), member_radius, material=fibre_mat, color=(0.85, 0.12, 0.10)) for centre in centres]
        parent_id, members = O.bodies.appendClumped(bodies, 20)
        parent_id, members = int(parent_id), [int(value) for value in members]
        parent = O.bodies[parent_id]
        factor = float(cfg["fibre"]["target_mass_kg"]) / float(parent.state.mass)
        parent.state.mass = float(cfg["fibre"]["target_mass_kg"])
        parent.state.inertia = Vector3(*[float(value) * factor for value in parent.state.inertia])
        parent.state.blockedDOFs = ""
        parent_ids.append(parent_id)
        fibre_members.append(members)
    sand_ids = [int(O.bodies.append(sphere(Vector3(*centre), radius, material=sand_mat))) for _, centre, radius in placed]
    triax = TriaxialStressController(wall_left_id=wall_ids[0], wall_right_id=wall_ids[1], wall_bottom_id=wall_ids[2], wall_top_id=wall_ids[3], wall_back_id=wall_ids[4], wall_front_id=wall_ids[5], internalCompaction=False, stressMask=7, thickness=float(cfg["walls"]["thickness_m"]), max_vel=float(cfg["confinement"]["controller_maximum_wall_velocity_m_s"]), label="stage26o_mixture_triax")
    triax.goal1 = triax.goal2 = triax.goal3 = -float(cfg["confinement"]["controller_internal_target_pa"])
    triax.dead = True
    time_stepper = GlobalStiffnessTimeStepper(active=True, timeStepUpdateInterval=1, timestepSafetyCoefficient=float(cfg["settling"]["timestep_safety_coefficient"]), label="stage26o_mixture_time_stepper")
    newton = NewtonIntegrator(damping=float(cfg["settling"]["newton_damping"]), gravity=Vector3(*cfg["settling"]["gravity_m_s2"]), label="stage26o_mixture_newton")
    O.engines = [ForceResetter(), InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_Box_Aabb()]), InteractionLoop([Ig2_Sphere_Sphere_ScGeom(), Ig2_Box_Sphere_ScGeom()], [Ip2_FrictMat_FrictMat_FrictPhys()], [Law2_ScGeom_FrictPhys_CundallStrack()]), time_stepper, triax, newton]
    O.trackEnergy = True
    O.step()
    initial_poses = [{"position": [float(O.bodies[parent_id].state.pos[k]) for k in range(3)], "orientation": quaternion(O.bodies[parent_id])} for parent_id in parent_ids]
    total_weight = (sand_volume * float(cfg["sand"]["density_kg_m3"]) + 2.0 * float(cfg["fibre"]["target_mass_kg"])) * 9.81
    os.makedirs(output)
    history, record = [], 0

    settle_streak = 0
    for block in range(1, int(cfg["settling"]["maximum_blocks"]) + 1):
        O.run(int(cfg["settling"]["steps_per_block"]), True); record += 1
        row = diagnostic(record, "gravity_settling", block, cfg, triax, sand_ids, sand_volume, total_weight, fibre_members, parent_ids, initial_poses, wall_ids); history.append(row)
        settle_ok = block >= int(cfg["settling"]["minimum_blocks"]) and row["unbalanced_force"] <= float(cfg["settling"]["maximum_unbalanced_force"]) and row["normalized_kinetic_energy_weight_D50"] <= float(cfg["settling"]["maximum_normalized_kinetic_energy_weight_D50"]) and row["sand_sand_real_contact_count"] >= int(cfg["settling"]["minimum_sand_contact_count"]) and row["leaked_particle_count"] == 0
        settle_streak = settle_streak + 1 if settle_ok else 0
        if block == 1 or block % 20 == 0 or settle_streak > 0:
            print("STAGE26O_MIX_SETTLE=" + json.dumps({"block": block, "sand_contacts": row["sand_sand_real_contact_count"], "fibre_contacts": row["distinct_sand_contacts_by_fibre"], "unbalanced": row["unbalanced_force"], "ke_WD50": row["normalized_kinetic_energy_weight_D50"], "streak": settle_streak}, sort_keys=True), flush=True)
        if row["maximum_interobject_penetration_over_smaller_radius"] > float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]) or row["leaked_particle_count"]:
            break
        if settle_streak >= int(cfg["settling"]["required_consecutive_pass_blocks"]):
            break

    status, qualified, final_checks, confinement_streak = "gravity_settling_not_qualified", False, None, 0
    if settle_streak >= int(cfg["settling"]["required_consecutive_pass_blocks"]):
        triax.dead = False; time_stepper.timestepSafetyCoefficient = float(cfg["confinement"]["timestep_safety_coefficient"]); newton.damping = float(cfg["confinement"]["newton_damping"]); status = "confinement_not_qualified"
        for block in range(1, int(cfg["confinement"]["maximum_blocks"]) + 1):
            O.run(int(cfg["confinement"]["steps_per_block"]), True); record += 1
            row = diagnostic(record, "gravity_plus_wall_confinement", block, cfg, triax, sand_ids, sand_volume, total_weight, fibre_members, parent_ids, initial_poses, wall_ids); history.append(row)
            checks = final_gate(row, cfg); eligible = block >= int(cfg["confinement"]["minimum_blocks"]); confinement_streak = confinement_streak + 1 if eligible and all(checks.values()) else 0
            if block == 1 or block % 20 == 0 or confinement_streak > 0:
                print("STAGE26O_MIX_CONFINE=" + json.dumps({"block": block, "stress": row["principal_wall_stress_pa_compression_positive"], "sand_contacts": row["sand_sand_real_contact_count"], "fibre_contacts": row["distinct_sand_contacts_by_fibre"], "unbalanced": row["unbalanced_force"], "streak": confinement_streak}, sort_keys=True), flush=True)
            if not checks["finite_state"] or row["maximum_interobject_penetration_over_smaller_radius"] > float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]) or row["leaked_particle_count"]:
                status = "confinement_hard_guard_failed"; break
            if confinement_streak >= int(cfg["confinement"]["required_consecutive_pass_blocks"]):
                status = "gravity_confinement_qualified"; break

    if status == "gravity_confinement_qualified":
        start_g, end_g, blocks = [float(value) for value in cfg["settling"]["gravity_m_s2"]], [float(value) for value in cfg["gravity_removal"]["terminal_gravity_m_s2"]], int(cfg["gravity_removal"]["blocks"])
        for block in range(1, blocks + 1):
            fraction = block / float(blocks); newton.gravity = Vector3(*[start_g[k] + fraction * (end_g[k] - start_g[k]) for k in range(3)])
            O.run(int(cfg["gravity_removal"]["steps_per_block"]), True); record += 1
            row = diagnostic(record, "gravity_removal_ramp", block, cfg, triax, sand_ids, sand_volume, total_weight, fibre_members, parent_ids, initial_poses, wall_ids); history.append(row)
            if row["maximum_interobject_penetration_over_smaller_radius"] > float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]):
                status = "gravity_removal_hard_guard_failed"; break

    hold_streak = 0
    if status == "gravity_confinement_qualified":
        time_stepper.timestepSafetyCoefficient = float(cfg["final_hold"]["timestep_safety_coefficient"]); newton.damping = float(cfg["final_hold"]["newton_damping"]); status = "zero_gravity_hold_not_qualified"
        for block in range(1, int(cfg["final_hold"]["maximum_blocks"]) + 1):
            O.run(int(cfg["final_hold"]["steps_per_block"]), True); record += 1
            row = diagnostic(record, "zero_gravity_final_hold", block, cfg, triax, sand_ids, sand_volume, total_weight, fibre_members, parent_ids, initial_poses, wall_ids); history.append(row); final_checks = final_gate(row, cfg)
            eligible = block >= int(cfg["final_hold"]["minimum_blocks"]); hold_streak = hold_streak + 1 if eligible and all(final_checks.values()) else 0
            if block == 1 or block % 10 == 0 or hold_streak > 0:
                print("STAGE26O_MIX_HOLD=" + json.dumps({"block": block, "stress": row["principal_wall_stress_pa_compression_positive"], "sand_contacts": row["sand_sand_real_contact_count"], "fibre_contacts": row["distinct_sand_contacts_by_fibre"], "fibre_wall": row["fibre_wall_real_contact_count_by_fibre"], "unbalanced": row["unbalanced_force"], "streak": hold_streak}, sort_keys=True), flush=True)
            if not final_checks["finite_state"] or row["maximum_interobject_penetration_over_smaller_radius"] > float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]):
                status = "zero_gravity_hold_hard_guard_failed"; break
            if hold_streak >= int(cfg["final_hold"]["required_consecutive_pass_blocks"]):
                qualified = True; status = "spent_development_two_fibre_joint_deposition_qualified"; break

    history_path = os.path.join(output, "mixture_history.csv"); write_history(history_path, history)
    state_digest = None
    if qualified:
        state_path = os.path.join(output, "qualified_two_fibre_mixture_state.yade.gz")
        O.tags["stage26o_mixture_metadata_json"] = json.dumps({"schema": "lbs.stage26o-two-fibre-state-metadata.v1", "config_sha256": sha256(config_path), "final_hold_streak": hold_streak}, sort_keys=True, separators=(",", ":")); O.save(state_path); state_digest = sha256(state_path)
    result = {"schema": "lbs.stage26o-two-fibre-joint-deposition-result.v1", "passed": True, "status": status, "qualified": qualified, "settling_streak": settle_streak, "confinement_streak": confinement_streak, "final_hold_streak": hold_streak, "terminal": history[-1], "terminal_checks": final_checks, "records_written": len(history), "realized_radii_m": radii, "initial_box_length_m": initial_length, "initial_fibre_pivot_fractions": fractions, "artifacts": {"history_sha256": sha256(history_path), "state_sha256": state_digest}, "source_hashes": {"config": sha256(config_path), "runner": sha256(script_path), "placement": cfg["sources"]["placement_sha256"], "clean_control_acceptance": cfg["sources"]["clean_control_acceptance_sha256"], "stage25_checkpoint": cfg["sources"]["stage25_checkpoint_sha256"]}, "claim_boundary": cfg["claim_boundary"]}
    result_path = os.path.join(output, "result.json"); write_json_exclusive(result_path, result)
    completion = {"schema": "lbs.stage26o-two-fibre-joint-deposition-completion.v1", "passed": True, "status": status, "qualified": qualified, "result_sha256": sha256(result_path), "state_sha256": state_digest, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.time() - START, "authority": {"heldout_execution_authorized": False, "flow_execution_authorized": False, "deformation_authorized": False, "production_parametric_study_authorized": False}, "claim_boundary": cfg["claim_boundary"]}
    completion_path = os.path.join(output, "completion.json"); write_json_exclusive(completion_path, completion); print("STAGE26O_MIXTURE_COMPLETION_SHA256=" + sha256(completion_path), flush=True)


if __name__ == "__main__":
    main()
