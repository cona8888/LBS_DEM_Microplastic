"""Stage26n equilibrated, timestep-ramped exact-fibre release pilot."""
from __future__ import print_function

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(os.environ.get("STAGE26N_SCRIPT", __file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from yade import config
from stage26b_revision2_prefilter_common_v1 import load_json, sha256, windows_to_wsl, write_json_exclusive
from stage26h_common_v1 import diagnostic, diagonal_lengths, write_history, zero_motion
from run_stage26k_loose_cocompaction_pilot_v1 import solid_volume, enrich, gate as base_gate
from run_stage26l_mobile_cocompaction_pilot_v1 import quat, motion

START = time.time()


def authority(cfg):
    if cfg.get("status") != "authorized_stage26n_spent_development_equilibrated_safe_release_pilot":
        raise RuntimeError("configuration is not Stage26n-authorized")
    auth = cfg["authority"]
    if auth.get("equilibrated_safe_release_pilot_authorized") is not True:
        raise RuntimeError("safe-release authority is false")
    forbidden = (
        "heldout_execution_authorized", "reserve_execution_authorized", "flow_execution_authorized",
        "deformation_authorized", "production_parametric_study_authorized",
    )
    if any(auth.get(name, False) for name in forbidden):
        raise RuntimeError("Stage26n authority exceeded")


def bind(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def engine_controls(safety, damping, update_interval=None):
    for engine in O.engines:
        if isinstance(engine, GlobalStiffnessTimeStepper):
            engine.timestepSafetyCoefficient = float(safety)
            if update_interval is not None:
                engine.timeStepUpdateInterval = int(update_interval)
        if isinstance(engine, NewtonIntegrator):
            engine.damping = float(damping)


def control_values():
    safety, damping = None, None
    for engine in O.engines:
        if isinstance(engine, GlobalStiffnessTimeStepper):
            safety = float(engine.timestepSafetyCoefficient)
        if isinstance(engine, NewtonIntegrator):
            damping = float(engine.damping)
    return safety, damping


def fixed_release_gate(row, cfg):
    limits = cfg["fixed_equilibration"]
    return {
        "finite_state": all(math.isfinite(float(value)) for value in (
            row["mean_effective_stress_pa_compression_positive"], row["unbalanced_force"],
            row["normalized_kinetic_energy_pV"], row["maximum_interobject_penetration_over_smaller_radius"],
        )),
        "mean_stress": row["relative_mean_stress_error"] <= limits["maximum_relative_mean_stress_error"],
        "principal_stress": row["maximum_principal_stress_error"] <= limits["maximum_principal_stress_error"],
        "unbalanced_force": row["unbalanced_force_defined"] and row["unbalanced_force"] <= limits["maximum_unbalanced_force"],
        "normalized_kinetic_energy": row["normalized_kinetic_energy_pV"] <= limits["maximum_normalized_kinetic_energy_pV"],
        "sand_contacts": row["sand_sand_real_contact_count"] >= limits["minimum_sand_contact_count"],
        "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"] >= limits["minimum_sand_coordination_excluding_rattlers"],
        "sand_rattlers": row["sand_rattler_fraction_degree_lt2_iterative"] <= limits["maximum_sand_rattler_fraction"],
        "overlap": row["maximum_interobject_penetration_over_smaller_radius"] <= limits["maximum_interobject_penetration_over_smaller_radius"],
        "void_ratio": abs(row["sand_skeleton_void_ratio_difference_from_reference"]) <= limits["maximum_absolute_sand_skeleton_void_ratio_difference"],
        "fibre_contact_on_each": min(row["distinct_sand_contacts_by_fibre"]) >= limits["minimum_distinct_sand_contacts_per_fibre"],
        "no_fibre_fibre_contact": row["fibre_fibre_real_interaction_count"] == 0,
        "no_intraclump_contact": row["intraclump_real_interaction_count"] == 0,
    }


def mobile_gate(row, cfg):
    checks = base_gate(row, cfg)
    checks["bounded_translation"] = (
        row["maximum_fibre_translation_over_D50"] <=
        cfg["motion_guards"]["maximum_nonaffine_translation_over_D50"]
    )
    checks["bounded_rotation"] = row["maximum_fibre_rotation_deg"] <= cfg["motion_guards"]["maximum_rotation_deg"]
    return checks


def hard_guard(row, cfg):
    limits = cfg["hard_guards"]
    return {
        "finite_state": all(math.isfinite(float(value)) for value in (
            row["mean_effective_stress_pa_compression_positive"], row["unbalanced_force"],
            row["normalized_kinetic_energy_pV"], row["maximum_fibre_translation_over_D50"],
            row["maximum_interobject_penetration_over_smaller_radius"], row["time_step_s"],
        )),
        "overlap": row["maximum_interobject_penetration_over_smaller_radius"] <= limits["maximum_interobject_penetration_over_smaller_radius"],
        "translation": row["maximum_fibre_translation_over_D50"] <= limits["maximum_nonaffine_translation_over_D50"],
        "stress": max(abs(value) for value in row["principal_effective_stress_pa_compression_positive"]) <= limits["maximum_absolute_principal_stress_pa"],
    }


def annotate(row, phase, phase_index, parent_ids, release_poses, cfg):
    if release_poses is None:
        row.update({
            "fibre_translation_m_by_fibre": [0.0 for _ in parent_ids],
            "fibre_translation_over_D50_by_fibre": [0.0 for _ in parent_ids],
            "fibre_rotation_deg_by_fibre": [0.0 for _ in parent_ids],
            "maximum_fibre_translation_over_D50": 0.0,
            "maximum_fibre_rotation_deg": 0.0,
        })
    else:
        row.update(motion(parent_ids, release_poses, float(cfg["sand"]["D50_m"])))
    safety, damping = control_values()
    row.update({
        "phase": phase, "phase_index": int(phase_index), "time_step_s": float(O.dt),
        "timestep_safety_coefficient": safety, "newton_damping": damping,
    })
    return row


def main():
    config_path = os.path.abspath(os.environ["STAGE26N_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26N_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26N_SCRIPT", __file__))
    cfg = load_json(config_path)
    authority(cfg)
    bind(cfg)
    if sha256(script_path) != cfg["sources"]["runner_sha256"]:
        raise RuntimeError("runner hash mismatch")
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26n output already exists")
    os.makedirs(output)

    O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    sand_ids = sorted(int(body.id) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember)
    if len(sand_ids) != int(cfg["sand"]["particle_count"]):
        raise RuntimeError("sand count mismatch")
    original_radii = dict((body_id, float(O.bodies[body_id].shape.radius)) for body_id in sand_ids)
    sand_solid = solid_volume(sand_ids)
    old_lengths = diagonal_lengths()
    old_volume = float(O.cell.volume)
    desired_volume = sand_solid * (1.0 + float(cfg["preparation"]["initial_sand_skeleton_void_ratio"]))
    scale = (desired_volume / old_volume) ** (1.0 / 3.0)
    fractions = dict((body_id, [float(O.bodies[body_id].state.pos[k]) / old_lengths[k] for k in range(3)]) for body_id in sand_ids)
    new_lengths = [value * scale for value in old_lengths]
    O.cell.hSize = Matrix3(new_lengths[0], 0, 0, 0, new_lengths[1], 0, 0, 0, new_lengths[2])
    for body_id in sand_ids:
        O.bodies[body_id].state.pos = Vector3(*[fractions[body_id][k] * new_lengths[k] for k in range(3)])
    zero_motion(sand_ids)
    O.step()

    placement = load_json(windows_to_wsl(cfg["sources"]["placement"]))
    material_id = O.materials.append(FrictMat(
        young=float(cfg["fibre"]["young_pa"]), poisson=float(cfg["fibre"]["poisson"]),
        frictionAngle=math.atan(float(cfg["fibre"]["friction_coefficient"])),
        density=float(cfg["fibre"]["density_kg_m3"]), label="stage26n_f37_plastic",
    ))
    parent_ids, member_groups = [], []
    for fibre in placement["fibres"]:
        source = [[float(value) for value in centre] for centre in fibre["member_centres_m"]]
        pivot = [sum(centre[k] for centre in source) / len(source) for k in range(3)]
        expanded_pivot = [pivot[k] * scale for k in range(3)]
        centres = [[expanded_pivot[k] + centre[k] - pivot[k] for k in range(3)] for centre in source]
        bodies = [sphere(Vector3(*centre), float(cfg["fibre"]["member_radius_m"]), material=material_id, color=(0.85, 0.12, 0.10)) for centre in centres]
        parent_id, members = O.bodies.appendClumped(bodies, 20)
        parent_id, members = int(parent_id), [int(value) for value in members]
        parent = O.bodies[parent_id]
        factor = float(cfg["fibre"]["target_mass_kg"]) / float(parent.state.mass)
        parent.state.mass = float(cfg["fibre"]["target_mass_kg"])
        parent.state.inertia = Vector3(*[float(value) * factor for value in parent.state.inertia])
        parent.state.blockedDOFs = "xyzXYZ"
        parent_ids.append(parent_id)
        member_groups.append(members)
    zero_motion(sand_ids + parent_ids)
    O.step()

    triax = next(engine for engine in O.engines if isinstance(engine, PeriTriaxController))
    target = float(cfg["preparation"]["target_mean_effective_stress_pa"])
    triax.dead = False
    triax.goal = tuple(-target for _ in range(3))
    triax.maxStrainRate = tuple(float(cfg["preparation"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["acceptance"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["acceptance"]["maximum_unbalanced_force"])
    engine_controls(cfg["preparation"]["timestep_safety_coefficient"], cfg["preparation"]["newton_damping"])
    for engine in O.engines:
        if isinstance(engine, NewtonIntegrator):
            engine.gravity = Vector3(*cfg["preparation"]["gravity_m_s2"])

    initial = {
        "cell_volume_m3": float(O.cell.volume),
        "sand_fractional": dict((str(body_id), [float(O.bodies[body_id].state.pos[k]) / new_lengths[k] for k in range(3)]) for body_id in sand_ids),
        "checkpoint_velocities_reset": True,
    }
    supports = [[] for _ in member_groups]
    history = []
    fixed_streak, release_row, release_checks = 0, None, None
    fixed_cfg = cfg["fixed_equilibration"]
    for block in range(1, int(fixed_cfg["maximum_blocks"]) + 1):
        O.run(int(fixed_cfg["steps_per_block"]), True)
        zero_motion(parent_ids)
        row = enrich(diagnostic(block, cfg, triax, sand_ids, member_groups, supports, initial), cfg, sand_solid)
        row = annotate(row, "fixed_full_skeleton_equilibration", block, parent_ids, None, cfg)
        history.append(row)
        release_checks = fixed_release_gate(row, cfg)
        eligible = block >= int(fixed_cfg["minimum_blocks"])
        fixed_streak = fixed_streak + 1 if eligible and all(release_checks.values()) else 0
        if block == 1 or block % 20 == 0 or fixed_streak > 0:
            print("STAGE26N_FIXED=" + json.dumps({
                "block": block, "stress_pa": row["mean_effective_stress_pa_compression_positive"],
                "unbalanced": row["unbalanced_force"], "sand_contacts": row["sand_sand_real_contact_count"],
                "fibre_contacts": row["distinct_sand_contacts_by_fibre"], "streak": fixed_streak,
            }, sort_keys=True), flush=True)
        if not release_checks["finite_state"] or row["maximum_interobject_penetration_over_smaller_radius"] > 0.05:
            break
        if fixed_streak >= int(fixed_cfg["required_consecutive_pass_blocks"]):
            release_row = row
            break

    qualified = False
    mobile_streak = 0
    final_checks = None
    final_hard_checks = None
    release_metadata = None
    status = "fixed_equilibrium_not_reached"
    global_record = len(history)
    if release_row is not None:
        lengths = diagonal_lengths()
        release_poses = [{
            "fractional_position": [float(O.bodies[parent_id].state.pos[k]) / lengths[k] for k in range(3)],
            "orientation": quat(O.bodies[parent_id]),
        } for parent_id in parent_ids]
        old_dt = float(O.dt)
        first_stage = cfg["release_protocol"]["ramp_stages"][0]
        engine_controls(first_stage["timestep_safety_coefficient"], first_stage["newton_damping"], cfg["release_protocol"]["time_step_update_interval"])
        O.dt = old_dt * float(cfg["release_protocol"]["forced_pre_release_dt_multiplier"])
        zero_motion(parent_ids)
        for parent_id in parent_ids:
            O.bodies[parent_id].state.blockedDOFs = ""
        O.step()
        release_metadata = {
            "fixed_release_block": int(release_row["block"]), "fixed_release_streak": fixed_streak,
            "old_time_step_s": old_dt, "forced_pre_release_time_step_s": old_dt * float(cfg["release_protocol"]["forced_pre_release_dt_multiplier"]),
            "first_mobile_step_time_step_s": float(O.dt),
        }
        status = "release_ramp_in_progress"
        stop = False
        for stage in cfg["release_protocol"]["ramp_stages"]:
            engine_controls(stage["timestep_safety_coefficient"], stage["newton_damping"], cfg["release_protocol"]["time_step_update_interval"])
            for subblock in range(1, int(stage["subblocks"]) + 1):
                O.run(int(stage["steps_per_subblock"]), True)
                global_record += 1
                row = enrich(diagnostic(global_record, cfg, triax, sand_ids, member_groups, supports, initial), cfg, sand_solid)
                row = annotate(row, "release_ramp_" + stage["name"], subblock, parent_ids, release_poses, cfg)
                history.append(row)
                final_hard_checks = hard_guard(row, cfg)
                print("STAGE26N_RAMP=" + json.dumps({
                    "stage": stage["name"], "subblock": subblock, "dt": row["time_step_s"],
                    "stress_pa": row["mean_effective_stress_pa_compression_positive"],
                    "overlap": row["maximum_interobject_penetration_over_smaller_radius"],
                    "fibre_contacts": row["distinct_sand_contacts_by_fibre"],
                    "translation_D50": row["maximum_fibre_translation_over_D50"],
                    "rotation_deg": row["maximum_fibre_rotation_deg"],
                }, sort_keys=True), flush=True)
                if not all(final_hard_checks.values()):
                    status = "release_ramp_hard_guard_failed"
                    stop = True
                    break
                if row["maximum_fibre_translation_over_D50"] > cfg["motion_guards"]["maximum_nonaffine_translation_over_D50"]:
                    status = "release_ramp_bounded_translation_acceptance_lost"
                    stop = True
                    break
            if stop:
                break
        if not stop:
            protocol = cfg["release_protocol"]
            engine_controls(protocol["mobile_timestep_safety_coefficient"], protocol["mobile_newton_damping"], protocol["time_step_update_interval"])
            status = "mobile_relaxation_resource_ceiling"
            for mobile_block in range(1, int(protocol["mobile_maximum_blocks"]) + 1):
                O.run(int(protocol["mobile_steps_per_block"]), True)
                global_record += 1
                if any(abs(float(O.bodies[body_id].shape.radius) - original_radii[body_id]) > 1e-15 for body_id in sand_ids):
                    raise RuntimeError("sand radius changed")
                row = enrich(diagnostic(global_record, cfg, triax, sand_ids, member_groups, supports, initial), cfg, sand_solid)
                row = annotate(row, "mobile_equilibration", mobile_block, parent_ids, release_poses, cfg)
                history.append(row)
                final_checks = mobile_gate(row, cfg)
                final_hard_checks = hard_guard(row, cfg)
                if not all(final_hard_checks.values()):
                    status = "mobile_hard_guard_failed"
                    break
                if not final_checks["bounded_translation"]:
                    status = "mobile_bounded_translation_acceptance_lost"
                    break
                eligible = mobile_block >= int(protocol["mobile_minimum_blocks"])
                mobile_streak = mobile_streak + 1 if eligible and all(final_checks.values()) else 0
                if mobile_block == 1 or mobile_block % 10 == 0 or mobile_streak > 0:
                    print("STAGE26N_MOBILE=" + json.dumps({
                        "block": mobile_block, "dt": row["time_step_s"],
                        "stress_pa": row["mean_effective_stress_pa_compression_positive"],
                        "unbalanced": row["unbalanced_force"], "sand_contacts": row["sand_sand_real_contact_count"],
                        "fibre_contacts": row["distinct_sand_contacts_by_fibre"],
                        "translation_D50": row["maximum_fibre_translation_over_D50"],
                        "rotation_deg": row["maximum_fibre_rotation_deg"], "streak": mobile_streak,
                    }, sort_keys=True), flush=True)
                if mobile_streak >= int(protocol["required_consecutive_pass_blocks"]):
                    qualified = True
                    status = "equilibrated_safe_release_mobile_state_qualified"
                    break

    history_path = os.path.join(output, "safe_release_history.csv")
    write_history(history_path, history)
    state_digest = None
    if qualified:
        state_path = os.path.join(output, "qualified_safe_release_mobile_state.yade.gz")
        O.tags["stage26n_metadata_json"] = json.dumps({
            "schema": "lbs.stage26n-qualified-state-metadata.v1", "config_sha256": sha256(config_path),
            "release_metadata": release_metadata, "mobile_final_streak": mobile_streak,
        }, sort_keys=True, separators=(",", ":"))
        O.save(state_path)
        state_digest = sha256(state_path)
    result = {
        "schema": "lbs.stage26n-equilibrated-safe-release-pilot-result.v1", "passed": True,
        "status": status, "qualified": qualified, "trial": cfg["trial"],
        "fixed_release_row": release_row, "fixed_release_checks": release_checks,
        "release_metadata": release_metadata, "terminal": history[-1],
        "terminal_checks": final_checks, "terminal_hard_checks": final_hard_checks,
        "fixed_consecutive_pass_blocks": fixed_streak, "mobile_consecutive_pass_blocks": mobile_streak,
        "records_written": len(history), "exact_sand_radii_unchanged": True,
        "exact_fibre_geometry_unchanged": True,
        "artifacts": {"history_sha256": sha256(history_path), "state_sha256": state_digest},
        "source_hashes": {"config": sha256(config_path), "runner": sha256(script_path),
                          "placement": cfg["sources"]["placement_sha256"],
                          "stage25_checkpoint": cfg["sources"]["stage25_checkpoint_sha256"]},
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26n-equilibrated-safe-release-pilot-completion.v1", "passed": True,
        "status": status, "qualified": qualified, "result_sha256": sha256(result_path),
        "state_sha256": state_digest, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": time.time() - START,
        "authority": {"heldout_execution_authorized": False, "reserve_execution_authorized": False,
                      "flow_execution_authorized": False, "deformation_authorized": False},
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26N_COMPLETION_SHA256=" + sha256(completion_path), flush=True)


if __name__ == "__main__":
    main()
