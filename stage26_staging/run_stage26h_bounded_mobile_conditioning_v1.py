"""Stage26h bounded mobile-conditioning pilot for a spent Stage26g development cage.

The fibres may translate/rotate only during specimen preparation.  A state is
accepted only after a subsequent fixed-fibre validation window.  No flow,
deformation, held-out geometry, or production inference is permitted.
"""

from __future__ import print_function

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(os.environ.get("STAGE26H_SCRIPT", __file__)))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from yade import config, utils

from stage26b_revision2_prefilter_common_v1 import load_json, sha256, windows_to_wsl, write_json_exclusive
from stage26d_adaptive_common_v1 import row_sand_health_pass
from stage26h_common_v1 import diagnostic, diagonal_lengths, write_history, zero_motion


START = time.time()


def assert_authority(cfg):
    if cfg.get("status") != "authorized_stage26h_spent_development_pilot":
        raise RuntimeError("configuration is not Stage26h pilot-authorized")
    authority = cfg["authority"]
    if authority.get("bounded_mobile_conditioning_authorized") is not True:
        raise RuntimeError("bounded mobile conditioning authority is false")
    forbidden = (
        "heldout_execution_authorized",
        "reserve_execution_authorized",
        "flow_execution_authorized",
        "deformation_authorized",
        "production_parametric_study_authorized",
        "unbounded_free_release_authorized",
    )
    if any(authority.get(name, False) for name in forbidden):
        raise RuntimeError("Stage26h pilot configuration exceeds authority")


def bind_sources(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def quaternion_tuple(body):
    value = body.state.ori
    return tuple(float(value[index]) for index in range(4))


def pose_metrics(parent_ids, initial_poses, d50):
    translations = []
    rotations = []
    for index, parent_id in enumerate(parent_ids):
        body = O.bodies[parent_id]
        p0 = initial_poses[index]["position"]
        q0 = initial_poses[index]["orientation"]
        translation = math.sqrt(sum((float(body.state.pos[k]) - p0[k]) ** 2 for k in range(3)))
        q = quaternion_tuple(body)
        dot = abs(sum(q[k] * q0[k] for k in range(4)))
        dot = max(-1.0, min(1.0, dot))
        rotations.append(math.degrees(2.0 * math.acos(dot)))
        translations.append(translation)
    return {
        "fibre_translation_m_by_fibre": translations,
        "fibre_translation_over_D50_by_fibre": [value / d50 for value in translations],
        "fibre_rotation_deg_by_fibre": rotations,
        "maximum_fibre_translation_over_D50": max(translations) / d50,
        "maximum_fibre_rotation_deg": max(rotations),
    }


def phase_row(block, phase, cfg, triax, sand_ids, members, supports, initial, parent_ids, initial_poses):
    row = diagnostic(block, cfg, triax, sand_ids, members, supports, initial)
    row["phase"] = phase
    row.update(pose_metrics(parent_ids, initial_poses, float(cfg["candidate_generation"]["D50_m"])))
    return row


def bounded(row, cfg):
    guards = cfg["conditioning_guards"]
    return (
        row["isolated_fibre_count"] <= guards["maximum_isolated_fibre_count"]
        and min(row["distinct_sand_contacts_by_fibre"]) >= guards["minimum_distinct_contacts_per_fibre"]
        and row["maximum_interobject_penetration_over_smaller_radius"] <= guards["maximum_interobject_penetration_over_smaller_radius"]
        and row["maximum_fibre_translation_over_D50"] <= guards["maximum_fibre_translation_over_D50"]
        and row["maximum_fibre_rotation_deg"] <= guards["maximum_fibre_rotation_deg"]
    )


def equilibrium_streak(streak, row, minimum_block, required, gates):
    equilibrium_pass = (
        min(row["distinct_sand_contacts_by_fibre"]) >= gates["minimum_distinct_sand_contacts_per_fibre"]
        and min(row["declared_support_contacts_by_fibre"]) >= gates["minimum_declared_support_contacts_per_fibre"]
        and row["fibre_fibre_real_interaction_count"] <= gates["maximum_fibre_fibre_real_interaction_count"]
        and row["intraclump_real_interaction_count"] <= gates["maximum_intraclump_real_interaction_count"]
        and row_sand_health_pass(row, gates)
    )
    if row["block"] < minimum_block or not equilibrium_pass:
        return []
    updated = list(streak) + [row["block"]]
    if len(updated) > required:
        updated = updated[-required:]
    return updated


def main():
    config_path = os.path.abspath(os.environ["STAGE26H_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26H_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26H_SCRIPT", __file__))
    cfg = load_json(config_path)
    assert_authority(cfg)
    bind_sources(cfg)
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    if sha256(script_path) != cfg["sources"]["runner_sha256"]:
        raise RuntimeError("runner hash mismatch")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26h output already exists")
    os.makedirs(output)

    trial = cfg["trial"]
    placement_path = windows_to_wsl(trial["placement"])
    if sha256(placement_path) != trial["placement_sha256"]:
        raise RuntimeError("placement hash mismatch")
    placement = load_json(placement_path)
    if placement.get("record_type") != "development_capture" or trial["candidate_index"] != 7:
        raise RuntimeError("pilot must use spent Stage26g development candidate 07")

    O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    sand_ids = sorted(
        int(body.id) for body in O.bodies
        if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember
    )
    if len(sand_ids) != int(cfg["network_export"]["required_sand_particle_count"]):
        raise RuntimeError("Stage25 sand-particle count mismatch")
    zero_motion(sand_ids)
    lengths = diagonal_lengths()
    initial = {
        "cell_volume_m3": float(O.cell.volume),
        "sand_fractional": dict(
            (str(body_id), [float(O.bodies[body_id].state.pos[k]) / lengths[k] for k in range(3)])
            for body_id in sand_ids
        ),
        "checkpoint_velocities_reset": True,
    }
    triax = next(engine for engine in O.engines if isinstance(engine, PeriTriaxController))
    target = float(cfg["frozen_physics"]["target_mean_effective_stress_pa"])
    triax.dead = False
    triax.goal = tuple(-target for _ in range(3))
    triax.maxStrainRate = tuple(float(cfg["conditioning_protocol"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["equilibrium_gates"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["equilibrium_gates"]["maximum_unbalanced_force"])
    for engine in O.engines:
        if isinstance(engine, GlobalStiffnessTimeStepper):
            engine.timestepSafetyCoefficient = float(cfg["frozen_physics"]["timestep_safety_coefficient"])
        if isinstance(engine, NewtonIntegrator):
            engine.damping = float(cfg["frozen_physics"]["newton_damping"])
            engine.gravity = Vector3(*cfg["frozen_physics"]["gravity_m_s2"])

    plastic_id = O.materials.append(FrictMat(
        young=float(cfg["frozen_physics"]["plastic_young_pa"]),
        poisson=float(cfg["frozen_physics"]["plastic_poisson"]),
        frictionAngle=math.atan(float(cfg["frozen_physics"]["plastic_friction_coefficient"])),
        density=float(cfg["frozen_physics"]["fibre_density_kg_m3"]),
        label="stage26h_f37_plastic",
    ))
    parent_ids, member_groups, declared_supports = [], [], []
    for fibre in placement["fibres"]:
        bodies = [
            sphere(Vector3(*centre), float(cfg["frozen_physics"]["fibre_member_radius_m"]),
                   material=plastic_id, color=(0.85, 0.12, 0.10))
            for centre in fibre["member_centres_m"]
        ]
        parent_id, member_ids = O.bodies.appendClumped(bodies, 20)
        parent_id, member_ids = int(parent_id), [int(value) for value in member_ids]
        parent = O.bodies[parent_id]
        mass_factor = float(cfg["frozen_physics"]["fibre_target_mass_kg"]) / float(parent.state.mass)
        parent.state.mass = float(cfg["frozen_physics"]["fibre_target_mass_kg"])
        parent.state.inertia = Vector3(*[float(value) * mass_factor for value in parent.state.inertia])
        parent.state.blockedDOFs = "xyzXYZ"
        parent_ids.append(parent_id)
        member_groups.append(member_ids)
        declared_supports.append([int(value) for value in fibre["support_sand_body_ids"]])
    zero_motion(sand_ids + parent_ids)
    O.step()
    initial_poses = [
        {"position": tuple(float(O.bodies[parent_id].state.pos[k]) for k in range(3)),
         "orientation": quaternion_tuple(O.bodies[parent_id])}
        for parent_id in parent_ids
    ]
    insertion = phase_row(0, "insertion_fixed", cfg, triax, sand_ids, member_groups, declared_supports, initial, parent_ids, initial_poses)
    if insertion["distinct_sand_contacts_by_fibre"] != [4, 4] or insertion["declared_support_contacts_by_fibre"] != [4, 4]:
        raise RuntimeError("exact four-support insertion failed")

    for parent_id in parent_ids:
        O.bodies[parent_id].state.blockedDOFs = ""
    zero_motion(parent_ids)
    history = []
    mobile_streak = []
    mobile_qualified = False
    stop_reason = "mobile_phase_resource_ceiling"
    protocol = cfg["conditioning_protocol"]
    for block in range(1, int(protocol["mobile_maximum_blocks"]) + 1):
        O.run(int(protocol["steps_per_block"]), True)
        row = phase_row(block, "bounded_mobile_conditioning", cfg, triax, sand_ids, member_groups, declared_supports, initial, parent_ids, initial_poses)
        history.append(row)
        if not bounded(row, cfg):
            stop_reason = "bounded_conditioning_guard_failed"
            break
        mobile_streak = equilibrium_streak(
            mobile_streak, row, int(protocol["mobile_minimum_block"]),
            int(protocol["required_consecutive_passing_blocks"]), cfg["equilibrium_gates"]
        )
        print("STAGE26H_MOBILE=" + json.dumps({
            "block": block,
            "streak": len(mobile_streak),
            "contacts": row["distinct_sand_contacts_by_fibre"],
            "declared_supports": row["declared_support_contacts_by_fibre"],
            "translation_D50": row["maximum_fibre_translation_over_D50"],
            "rotation_deg": row["maximum_fibre_rotation_deg"],
            "stress_pa": row["mean_effective_stress_pa_compression_positive"],
            "unbalanced": row["unbalanced_force"],
        }, sort_keys=True), flush=True)
        if len(mobile_streak) == int(protocol["required_consecutive_passing_blocks"]):
            mobile_qualified = True
            stop_reason = "mobile_conditioning_qualified"
            break

    fixed_qualified = False
    fixed_streak = []
    fixed_start = len(history)
    if mobile_qualified:
        for parent_id in parent_ids:
            O.bodies[parent_id].state.blockedDOFs = "xyzXYZ"
        zero_motion(parent_ids)
        stop_reason = "fixed_validation_resource_ceiling"
        for local_block in range(1, int(protocol["fixed_validation_maximum_blocks"]) + 1):
            O.run(int(protocol["steps_per_block"]), True)
            zero_motion(parent_ids)
            block = fixed_start + local_block
            row = phase_row(block, "fixed_validation", cfg, triax, sand_ids, member_groups, declared_supports, initial, parent_ids, initial_poses)
            history.append(row)
            if not bounded(row, cfg):
                stop_reason = "fixed_validation_guard_failed"
                break
            fixed_streak = equilibrium_streak(
                fixed_streak, row, fixed_start + 1,
                int(protocol["required_consecutive_passing_blocks"]), cfg["equilibrium_gates"]
            )
            print("STAGE26H_FIXED=" + json.dumps({
                "block": block, "streak": len(fixed_streak),
                "contacts": row["distinct_sand_contacts_by_fibre"],
                "declared_supports": row["declared_support_contacts_by_fibre"],
                "stress_pa": row["mean_effective_stress_pa_compression_positive"],
                "unbalanced": row["unbalanced_force"],
            }, sort_keys=True), flush=True)
            if len(fixed_streak) == int(protocol["required_consecutive_passing_blocks"]):
                fixed_qualified = True
                stop_reason = "fixed_validation_qualified"
                break

    history_path = os.path.join(output, "conditioning_history.csv")
    write_history(history_path, history)
    state_path = None
    state_digest = None
    if fixed_qualified:
        state_path = os.path.join(output, "qualified_conditioned_fixed_state.yade.gz")
        O.tags["stage26h_conditioning_metadata_json"] = json.dumps({
            "schema": "lbs.stage26h-conditioned-state-metadata.v1",
            "trial": trial,
            "mobile_streak": mobile_streak,
            "fixed_streak": fixed_streak,
            "config_sha256": sha256(config_path),
        }, sort_keys=True, separators=(",", ":"))
        O.save(state_path)
        state_digest = sha256(state_path)

    result = {
        "schema": "lbs.stage26h-bounded-mobile-conditioning-result.v1",
        "passed": True,
        "status": stop_reason,
        "trial": trial,
        "insertion": insertion,
        "protocol": {
            "mobile_conditioning_executed": True,
            "unbounded_free_release": False,
            "fixed_validation_required": True,
            "blocks_executed": len(history),
        },
        "mobile_conditioning_qualified": mobile_qualified,
        "fixed_validation_qualified": fixed_qualified,
        "qualified_conditioned_fixed_state_captured": fixed_qualified,
        "mobile_streak": mobile_streak,
        "fixed_streak": fixed_streak,
        "terminal_row": history[-1] if history else insertion,
        "artifacts": {
            "history_sha256": sha256(history_path),
            "state_sha256": state_digest,
        },
        "source_hashes": {
            "config": sha256(config_path),
            "runner": sha256(script_path),
            "placement": sha256(placement_path),
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26h-bounded-mobile-conditioning-completion.v1",
        "passed": True,
        "status": stop_reason,
        "mobile_conditioning_qualified": mobile_qualified,
        "fixed_validation_qualified": fixed_qualified,
        "qualified_conditioned_fixed_state_captured": fixed_qualified,
        "result_sha256": sha256(result_path),
        "state_sha256": state_digest,
        "wall_seconds": time.time() - START,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "authority": {
            "heldout_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26H_COMPLETION_SHA256=" + sha256(completion_path), flush=True)


if __name__ == "__main__":
    main()
