"""Stage26i temporary-radius-preload development screen on spent candidate 07.

Fibre members remain fixed.  Their contact radius is smoothly increased during
preparation, held while the sand reconsolidates, then restored to the exact
50 micrometre final radius.  Acceptance requires a subsequent final-geometry
fixed-fibre equilibrium window.  This is not a material calibration or flow run.
"""

from __future__ import print_function

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(os.environ.get("STAGE26I_SCRIPT", __file__)))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from yade import config

from stage26b_revision2_prefilter_common_v1 import load_json, sha256, windows_to_wsl, write_json_exclusive
from stage26d_adaptive_common_v1 import row_sand_health_pass
from stage26h_common_v1 import diagnostic, diagonal_lengths, write_history, zero_motion


START = time.time()


def assert_authority(cfg):
    if cfg.get("status") != "authorized_stage26i_spent_development_preload_screen":
        raise RuntimeError("configuration is not Stage26i preload-screen authorized")
    authority = cfg["authority"]
    if authority.get("temporary_radius_preload_authorized") is not True:
        raise RuntimeError("temporary-radius preload authority is false")
    forbidden = (
        "heldout_execution_authorized", "reserve_execution_authorized",
        "free_release_authorized", "flow_execution_authorized",
        "deformation_authorized", "production_parametric_study_authorized",
    )
    if any(authority.get(name, False) for name in forbidden):
        raise RuntimeError("Stage26i screen configuration exceeds authority")


def bind_sources(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def set_member_radius(member_groups, radius):
    for members in member_groups:
        for body_id in members:
            O.bodies[body_id].shape.radius = float(radius)


def screen_row(block, phase, radius_scale, cfg, triax, sand_ids, member_groups, supports, initial):
    row = diagnostic(block, cfg, triax, sand_ids, member_groups, supports, initial)
    row["phase"] = phase
    row["temporary_fibre_radius_scale"] = float(radius_scale)
    row["temporary_fibre_member_radius_m"] = (
        float(cfg["frozen_physics"]["fibre_member_radius_m"]) * float(radius_scale)
    )
    return row


def contact_gate(row, cfg, final=False):
    gates = cfg["final_equilibrium_gates"] if final else cfg["inflated_equilibrium_gates"]
    return (
        min(row["distinct_sand_contacts_by_fibre"]) >= gates["minimum_distinct_sand_contacts_per_fibre"]
        and min(row["declared_support_contacts_by_fibre"]) >= gates["minimum_declared_support_contacts_per_fibre"]
        and row["fibre_fibre_real_interaction_count"] <= gates["maximum_fibre_fibre_real_interaction_count"]
        and row["intraclump_real_interaction_count"] <= gates["maximum_intraclump_real_interaction_count"]
        and row_sand_health_pass(row, gates)
    )


def guard(row, cfg, final=False):
    guards = cfg["preparation_guards"]
    maximum_penetration = (
        cfg["final_equilibrium_gates"]["maximum_interobject_penetration_over_smaller_radius"]
        if final else guards["maximum_temporary_interobject_penetration_over_smaller_radius"]
    )
    return (
        row["isolated_fibre_count"] <= guards["maximum_isolated_fibre_count"]
        and min(row["distinct_sand_contacts_by_fibre"]) >= guards["minimum_distinct_contacts_per_fibre"]
        and row["maximum_interobject_penetration_over_smaller_radius"] <= maximum_penetration
        and row["fibre_fibre_real_interaction_count"] == 0
        and row["intraclump_real_interaction_count"] == 0
    )


def append_and_print(history, row, trial_id):
    history.append(row)
    print("STAGE26I=" + json.dumps({
        "trial_id": trial_id,
        "block": row["block"],
        "phase": row["phase"],
        "radius_scale": row["temporary_fibre_radius_scale"],
        "contacts": row["distinct_sand_contacts_by_fibre"],
        "supports": row["declared_support_contacts_by_fibre"],
        "penetration_ratio": row["maximum_interobject_penetration_over_smaller_radius"],
        "stress_pa": row["mean_effective_stress_pa_compression_positive"],
        "unbalanced": row["unbalanced_force"],
    }, sort_keys=True), flush=True)


def main():
    config_path = os.path.abspath(os.environ["STAGE26I_CONFIG"])
    trial_id = os.environ["STAGE26I_TRIAL_ID"]
    output = os.path.abspath(os.environ["STAGE26I_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26I_SCRIPT", __file__))
    cfg = load_json(config_path)
    assert_authority(cfg)
    bind_sources(cfg)
    if sha256(script_path) != cfg["sources"]["runner_sha256"]:
        raise RuntimeError("runner hash mismatch")
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    trial = next((row for row in cfg["trials"] if row["trial_id"] == trial_id), None)
    if trial is None or trial["candidate_index"] != 7 or trial["record_type"] != "spent_development_preload_screen":
        raise RuntimeError("trial is outside the Stage26i spent-development screen")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26i output already exists")
    os.makedirs(output)

    placement_path = windows_to_wsl(trial["placement"])
    if sha256(placement_path) != trial["placement_sha256"]:
        raise RuntimeError("placement hash mismatch")
    placement = load_json(placement_path)
    if placement.get("record_type") != "development_capture":
        raise RuntimeError("Stage26i may use only the spent development placement")

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
    triax.maxStrainRate = tuple(float(cfg["preload_protocol"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["final_equilibrium_gates"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["final_equilibrium_gates"]["maximum_unbalanced_force"])
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
        label="stage26i_f37_plastic",
    ))
    parent_ids, member_groups, declared_supports = [], [], []
    final_radius = float(cfg["frozen_physics"]["fibre_member_radius_m"])
    for fibre in placement["fibres"]:
        bodies = [
            sphere(Vector3(*centre), final_radius, material=plastic_id, color=(0.85, 0.12, 0.10))
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
    insertion = screen_row(0, "final_radius_insertion", 1.0, cfg, triax, sand_ids, member_groups, declared_supports, initial)
    if insertion["distinct_sand_contacts_by_fibre"] != [4, 4] or insertion["declared_support_contacts_by_fibre"] != [4, 4]:
        raise RuntimeError("exact four-support insertion failed")

    history = []
    block = 0
    stop_reason = "inflation_ramp_completed"
    protocol = cfg["preload_protocol"]
    target_scale = float(trial["temporary_radius_scale"])
    for ramp_index in range(1, int(protocol["inflation_ramp_blocks"]) + 1):
        scale = 1.0 + (target_scale - 1.0) * ramp_index / float(protocol["inflation_ramp_blocks"])
        set_member_radius(member_groups, final_radius * scale)
        O.run(int(protocol["steps_per_block"]), True)
        zero_motion(parent_ids)
        block += 1
        row = screen_row(block, "inflation_ramp", scale, cfg, triax, sand_ids, member_groups, declared_supports, initial)
        append_and_print(history, row, trial_id)
        if not guard(row, cfg, final=False):
            stop_reason = "inflation_ramp_guard_failed"
            break

    inflated_qualified = False
    inflated_streak = []
    if stop_reason == "inflation_ramp_completed":
        stop_reason = "inflated_hold_resource_ceiling"
        for hold_block in range(1, int(protocol["inflated_hold_maximum_blocks"]) + 1):
            O.run(int(protocol["steps_per_block"]), True)
            zero_motion(parent_ids)
            block += 1
            row = screen_row(block, "inflated_equilibrium_hold", target_scale, cfg, triax, sand_ids, member_groups, declared_supports, initial)
            append_and_print(history, row, trial_id)
            if not guard(row, cfg, final=False):
                stop_reason = "inflated_hold_guard_failed"
                break
            if hold_block >= int(protocol["inflated_hold_minimum_blocks"]) and contact_gate(row, cfg, final=False):
                inflated_streak.append(block)
            else:
                inflated_streak = []
            if len(inflated_streak) == int(protocol["required_consecutive_passing_blocks"]):
                inflated_qualified = True
                stop_reason = "inflated_hold_qualified"
                break

    final_radius_restored = False
    if inflated_qualified:
        stop_reason = "deflation_ramp_completed"
        for ramp_index in range(1, int(protocol["deflation_ramp_blocks"]) + 1):
            scale = target_scale - (target_scale - 1.0) * ramp_index / float(protocol["deflation_ramp_blocks"])
            set_member_radius(member_groups, final_radius * scale)
            O.run(int(protocol["steps_per_block"]), True)
            zero_motion(parent_ids)
            block += 1
            row = screen_row(block, "deflation_ramp", scale, cfg, triax, sand_ids, member_groups, declared_supports, initial)
            append_and_print(history, row, trial_id)
            if not guard(row, cfg, final=(ramp_index == int(protocol["deflation_ramp_blocks"]))):
                stop_reason = "deflation_ramp_guard_failed"
                break
        final_radius_restored = all(
            abs(float(O.bodies[body_id].shape.radius) - final_radius) <= 1e-15
            for members in member_groups for body_id in members
        )

    final_qualified = False
    final_streak = []
    if inflated_qualified and stop_reason == "deflation_ramp_completed" and final_radius_restored:
        stop_reason = "final_geometry_validation_resource_ceiling"
        for validation_block in range(1, int(protocol["final_validation_maximum_blocks"]) + 1):
            O.run(int(protocol["steps_per_block"]), True)
            zero_motion(parent_ids)
            block += 1
            row = screen_row(block, "final_geometry_fixed_validation", 1.0, cfg, triax, sand_ids, member_groups, declared_supports, initial)
            append_and_print(history, row, trial_id)
            if not guard(row, cfg, final=True):
                stop_reason = "final_geometry_validation_guard_failed"
                break
            if contact_gate(row, cfg, final=True):
                final_streak.append(block)
            else:
                final_streak = []
            if len(final_streak) == int(protocol["required_consecutive_passing_blocks"]):
                final_qualified = True
                stop_reason = "final_geometry_fixed_validation_qualified"
                break

    history_path = os.path.join(output, "preload_history.csv")
    write_history(history_path, history)
    state_path = None
    state_digest = None
    if final_qualified:
        state_path = os.path.join(output, "qualified_preloaded_final_geometry_state.yade.gz")
        O.tags["stage26i_preload_metadata_json"] = json.dumps({
            "schema": "lbs.stage26i-preloaded-final-state-metadata.v1",
            "trial": trial,
            "inflated_streak": inflated_streak,
            "final_streak": final_streak,
            "final_radius_m": final_radius,
            "config_sha256": sha256(config_path),
        }, sort_keys=True, separators=(",", ":"))
        O.save(state_path)
        state_digest = sha256(state_path)

    result = {
        "schema": "lbs.stage26i-radius-preload-screen-result.v1",
        "passed": True,
        "status": stop_reason,
        "trial": trial,
        "insertion": insertion,
        "inflated_hold_qualified": inflated_qualified,
        "final_radius_restored_exactly": final_radius_restored,
        "final_geometry_fixed_validation_qualified": final_qualified,
        "qualified_state_captured": final_qualified,
        "inflated_streak": inflated_streak,
        "final_streak": final_streak,
        "blocks_executed": len(history),
        "terminal_row": history[-1] if history else insertion,
        "artifacts": {"history_sha256": sha256(history_path), "state_sha256": state_digest},
        "source_hashes": {
            "config": sha256(config_path), "runner": sha256(script_path),
            "placement": sha256(placement_path),
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26i-radius-preload-screen-completion.v1",
        "passed": True,
        "status": stop_reason,
        "trial_id": trial_id,
        "temporary_radius_scale": target_scale,
        "inflated_hold_qualified": inflated_qualified,
        "final_radius_restored_exactly": final_radius_restored,
        "final_geometry_fixed_validation_qualified": final_qualified,
        "qualified_state_captured": final_qualified,
        "result_sha256": sha256(result_path),
        "state_sha256": state_digest,
        "wall_seconds": time.time() - START,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "authority": {
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26I_COMPLETION_SHA256=" + sha256(completion_path), flush=True)


if __name__ == "__main__":
    main()
