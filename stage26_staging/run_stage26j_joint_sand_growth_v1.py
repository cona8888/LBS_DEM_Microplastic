"""Stage26j exact-fibre joint sand-growth co-compaction development screen."""

from __future__ import print_function

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(os.environ.get("STAGE26J_SCRIPT", __file__)))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from yade import config

from stage26b_revision2_prefilter_common_v1 import load_json, sha256, windows_to_wsl, write_json_exclusive
from stage26d_adaptive_common_v1 import row_sand_health_pass
from stage26h_common_v1 import diagnostic, diagonal_lengths, write_history, zero_motion


START = time.time()


def assert_authority(cfg):
    if cfg.get("status") != "authorized_stage26j_spent_development_joint_growth_screen":
        raise RuntimeError("configuration is not Stage26j-authorized")
    authority = cfg["authority"]
    if authority.get("joint_sand_growth_authorized") is not True:
        raise RuntimeError("joint sand-growth authority is false")
    forbidden = (
        "heldout_execution_authorized", "reserve_execution_authorized", "free_release_authorized",
        "temporary_fibre_radius_authorized", "flow_execution_authorized", "deformation_authorized",
        "production_parametric_study_authorized",
    )
    if any(authority.get(name, False) for name in forbidden):
        raise RuntimeError("Stage26j configuration exceeds authority")


def bind_sources(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def set_sand_radius_scale(sand_ids, original_radii, scale):
    for body_id in sand_ids:
        O.bodies[body_id].shape.radius = float(original_radii[str(body_id)]) * float(scale)


def growth_row(block, phase, scale, cfg, triax, sand_ids, member_groups, supports, initial):
    row = diagnostic(block, cfg, triax, sand_ids, member_groups, supports, initial)
    row["phase"] = phase
    row["temporary_sand_radius_scale"] = float(scale)
    row["sand_radius_deficit_percent"] = (1.0 - float(scale)) * 100.0
    return row


def preparation_guard(row, cfg):
    guards = cfg["preparation_guards"]
    return (
        row["maximum_interobject_penetration_over_smaller_radius"]
        <= guards["maximum_interobject_penetration_over_smaller_radius"]
        and row["fibre_fibre_real_interaction_count"] == 0
        and row["intraclump_real_interaction_count"] == 0
    )


def final_gate(row, cfg):
    gates = cfg["final_equilibrium_gates"]
    return (
        min(row["distinct_sand_contacts_by_fibre"]) >= gates["minimum_distinct_sand_contacts_per_fibre"]
        and min(row["declared_support_contacts_by_fibre"]) >= gates["minimum_declared_support_contacts_per_fibre"]
        and row["isolated_fibre_count"] <= 0
        and row["fibre_fibre_real_interaction_count"] <= gates["maximum_fibre_fibre_real_interaction_count"]
        and row["intraclump_real_interaction_count"] <= gates["maximum_intraclump_real_interaction_count"]
        and row_sand_health_pass(row, gates)
    )


def log_row(history, row, trial_id):
    history.append(row)
    print("STAGE26J=" + json.dumps({
        "trial_id": trial_id, "block": row["block"], "phase": row["phase"],
        "sand_scale": row["temporary_sand_radius_scale"],
        "contacts": row["distinct_sand_contacts_by_fibre"],
        "supports": row["declared_support_contacts_by_fibre"],
        "sand_contacts": row["sand_sand_real_contact_count"],
        "stress_pa": row["mean_effective_stress_pa_compression_positive"],
        "unbalanced": row["unbalanced_force"],
    }, sort_keys=True), flush=True)


def main():
    config_path = os.path.abspath(os.environ["STAGE26J_CONFIG"])
    trial_id = os.environ["STAGE26J_TRIAL_ID"]
    output = os.path.abspath(os.environ["STAGE26J_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26J_SCRIPT", __file__))
    cfg = load_json(config_path)
    assert_authority(cfg)
    bind_sources(cfg)
    if sha256(script_path) != cfg["sources"]["runner_sha256"]:
        raise RuntimeError("runner hash mismatch")
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    trial = next((row for row in cfg["trials"] if row["trial_id"] == trial_id), None)
    if trial is None or trial["candidate_index"] != 7:
        raise RuntimeError("trial is outside the Stage26j spent-development screen")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26j output already exists")
    os.makedirs(output)
    placement_path = windows_to_wsl(trial["placement"])
    if sha256(placement_path) != trial["placement_sha256"]:
        raise RuntimeError("placement hash mismatch")
    placement = load_json(placement_path)
    if placement.get("record_type") != "development_capture":
        raise RuntimeError("Stage26j may use only the spent development placement")

    O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    sand_ids = sorted(
        int(body.id) for body in O.bodies
        if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember
    )
    if len(sand_ids) != int(cfg["network_export"]["required_sand_particle_count"]):
        raise RuntimeError("Stage25 sand-particle count mismatch")
    original_radii = dict((str(body_id), float(O.bodies[body_id].shape.radius)) for body_id in sand_ids)
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
    triax.maxStrainRate = tuple(float(cfg["growth_protocol"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["final_equilibrium_gates"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["final_equilibrium_gates"]["maximum_unbalanced_force"])
    for engine in O.engines:
        if isinstance(engine, GlobalStiffnessTimeStepper):
            engine.timestepSafetyCoefficient = float(cfg["frozen_physics"]["timestep_safety_coefficient"])
        if isinstance(engine, NewtonIntegrator):
            engine.damping = float(cfg["frozen_physics"]["newton_damping"])
            engine.gravity = Vector3(*cfg["frozen_physics"]["gravity_m_s2"])

    initial_scale = float(trial["initial_sand_radius_scale"])
    set_sand_radius_scale(sand_ids, original_radii, initial_scale)
    zero_motion(sand_ids)
    O.step()

    plastic_id = O.materials.append(FrictMat(
        young=float(cfg["frozen_physics"]["plastic_young_pa"]),
        poisson=float(cfg["frozen_physics"]["plastic_poisson"]),
        frictionAngle=math.atan(float(cfg["frozen_physics"]["plastic_friction_coefficient"])),
        density=float(cfg["frozen_physics"]["fibre_density_kg_m3"]),
        label="stage26j_f37_plastic",
    ))
    parent_ids, member_groups, declared_supports = [], [], []
    final_fibre_radius = float(cfg["frozen_physics"]["fibre_member_radius_m"])
    for fibre in placement["fibres"]:
        bodies = [
            sphere(Vector3(*centre), final_fibre_radius, material=plastic_id, color=(0.85, 0.12, 0.10))
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
    insertion = growth_row(0, "shrunken_sand_exact_fibre_insertion", initial_scale, cfg, triax, sand_ids, member_groups, declared_supports, initial)
    if insertion["fibre_fibre_real_interaction_count"] != 0 or insertion["intraclump_real_interaction_count"] != 0:
        raise RuntimeError("invalid fibre interaction at shrunken insertion")

    history = []
    protocol = cfg["growth_protocol"]
    block = 0
    stop_reason = "sand_growth_completed"
    for growth_index in range(1, int(protocol["sand_growth_blocks"]) + 1):
        scale = initial_scale + (1.0 - initial_scale) * growth_index / float(protocol["sand_growth_blocks"])
        set_sand_radius_scale(sand_ids, original_radii, scale)
        O.run(int(protocol["steps_per_block"]), True)
        zero_motion(parent_ids)
        block += 1
        row = growth_row(block, "joint_sand_growth", scale, cfg, triax, sand_ids, member_groups, declared_supports, initial)
        log_row(history, row, trial_id)
        if not preparation_guard(row, cfg):
            stop_reason = "sand_growth_guard_failed"
            break

    final_sand_radii_restored = all(
        abs(float(O.bodies[body_id].shape.radius) - original_radii[str(body_id)]) <= 1e-15
        for body_id in sand_ids
    )
    final_qualified = False
    final_streak = []
    if stop_reason == "sand_growth_completed" and final_sand_radii_restored:
        stop_reason = "exact_geometry_hold_resource_ceiling"
        for hold_index in range(1, int(protocol["final_hold_maximum_blocks"]) + 1):
            O.run(int(protocol["steps_per_block"]), True)
            zero_motion(parent_ids)
            block += 1
            row = growth_row(block, "exact_geometry_fixed_hold", 1.0, cfg, triax, sand_ids, member_groups, declared_supports, initial)
            log_row(history, row, trial_id)
            if not preparation_guard(row, cfg):
                stop_reason = "exact_geometry_hold_guard_failed"
                break
            if hold_index >= int(protocol["final_hold_minimum_blocks"]) and final_gate(row, cfg):
                final_streak.append(block)
            else:
                final_streak = []
            if len(final_streak) == int(protocol["required_consecutive_passing_blocks"]):
                final_qualified = True
                stop_reason = "exact_geometry_fixed_hold_qualified"
                break

    history_path = os.path.join(output, "joint_growth_history.csv")
    write_history(history_path, history)
    state_path = None
    state_digest = None
    if final_qualified:
        state_path = os.path.join(output, "qualified_jointly_compacted_exact_geometry_state.yade.gz")
        O.tags["stage26j_joint_growth_metadata_json"] = json.dumps({
            "schema": "lbs.stage26j-joint-growth-state-metadata.v1", "trial": trial,
            "final_streak": final_streak, "config_sha256": sha256(config_path),
        }, sort_keys=True, separators=(",", ":"))
        O.save(state_path)
        state_digest = sha256(state_path)
    result = {
        "schema": "lbs.stage26j-joint-sand-growth-result.v1",
        "passed": True, "status": stop_reason, "trial": trial, "insertion": insertion,
        "final_sand_radii_restored_exactly": final_sand_radii_restored,
        "exact_geometry_fixed_hold_qualified": final_qualified,
        "qualified_state_captured": final_qualified, "final_streak": final_streak,
        "blocks_executed": len(history), "terminal_row": history[-1] if history else insertion,
        "artifacts": {"history_sha256": sha256(history_path), "state_sha256": state_digest},
        "source_hashes": {"config": sha256(config_path), "runner": sha256(script_path), "placement": sha256(placement_path)},
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26j-joint-sand-growth-completion.v1",
        "passed": True, "status": stop_reason, "trial_id": trial_id,
        "initial_sand_radius_scale": initial_scale,
        "final_sand_radii_restored_exactly": final_sand_radii_restored,
        "exact_geometry_fixed_hold_qualified": final_qualified,
        "qualified_state_captured": final_qualified,
        "result_sha256": sha256(result_path), "state_sha256": state_digest,
        "wall_seconds": time.time() - START, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "authority": {"heldout_execution_authorized": False, "reserve_execution_authorized": False,
                      "flow_execution_authorized": False, "deformation_authorized": False},
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26J_COMPLETION_SHA256=" + sha256(completion_path), flush=True)


if __name__ == "__main__":
    main()
