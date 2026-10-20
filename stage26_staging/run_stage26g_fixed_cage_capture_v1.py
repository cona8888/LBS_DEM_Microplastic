"""AUTO-DERIVED Stage26g fixed four-support cage runner.

Derived mechanically from the frozen Stage26e runner; no free release or flow.
"""

from __future__ import print_function

import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(os.environ.get("STAGE26G_CAGE_SCRIPT", __file__)))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from yade import config, utils

from stage26b_revision2_prefilter_common_v1 import (
    iterative_core,
    load_json,
    sha256,
    windows_to_wsl,
    write_json_exclusive,
)
from stage26g_capture_common_v1 import advance_equilibrium_streak


START = time.time()


def assert_authority(cfg):
    if cfg.get("status") != "authorized_stage26g_fixed_capture":
        raise RuntimeError("configuration is not Stage26g capture-authorized")
    authority = cfg["authority"]
    if authority.get("capture_yade_execution_authorized") is not True:
        raise RuntimeError("capture execution authority is false")
    forbidden = (
        "reload_verification_execution_authorized",
        "two_fibre_free_release_authorized",
        "legacy_revision3_candidate08_execution_authorized",
        "flow_execution_authorized",
        "deformation_authorized",
        "production_parametric_study_authorized",
    )
    if any(authority.get(name, False) for name in forbidden):
        raise RuntimeError("capture configuration exceeds fixed-development authority")
    protocol = cfg["capture_protocol"]
    if protocol.get("all_fibres_fixed") is not True or protocol.get("free_release") is not False:
        raise RuntimeError("capture protocol is not fixed-only")


def bind_sources(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def diagonal_lengths():
    return [float(O.cell.hSize[index, index]) for index in range(3)]


def vector_norm(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


def zero_motion(body_ids):
    for body_id in body_ids:
        body = O.bodies[body_id]
        body.state.vel = Vector3.Zero
        body.state.angVel = Vector3.Zero


def sand_network(sand_ids):
    sand_set = set(sand_ids)
    edges = []
    for interaction in O.interactions:
        if interaction.isReal and interaction.id1 in sand_set and interaction.id2 in sand_set:
            edges.append((int(interaction.id1), int(interaction.id2)))
    _, _, active = iterative_core(sand_ids, edges, 2)
    retained_edges = sum(1 for first, second in edges if first in active and second in active)
    coordination = 2.0 * retained_edges / len(active) if active else 0.0
    return len(edges), len(active), 1.0 - len(active) / float(len(sand_ids)), coordination


def diagnostic(block, cfg, triax, sand_ids, fibre_members, declared_supports, initial):
    lengths = diagonal_lengths()
    volume = float(O.cell.volume)
    target = float(cfg["frozen_physics"]["target_mean_effective_stress_pa"])
    stress = [-float(value) for value in triax.stress]
    mean_stress = sum(stress) / 3.0
    unbalanced = float(utils.unbalancedForce())
    unbalanced_defined = math.isfinite(unbalanced)
    if not unbalanced_defined:
        unbalanced = 1.0
    sand_set = set(sand_ids)
    member_to_fibre = {}
    for fibre_index, members in enumerate(fibre_members):
        for body_id in members:
            member_to_fibre[int(body_id)] = fibre_index
    contacted = [set() for _ in fibre_members]
    maximum_penetration = 0.0
    fibre_fibre_contacts = 0
    intraclump_contacts = 0
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        first_fibre = member_to_fibre.get(first)
        second_fibre = member_to_fibre.get(second)
        if first in sand_set and second_fibre is not None:
            contacted[second_fibre].add(first)
        elif second in sand_set and first_fibre is not None:
            contacted[first_fibre].add(second)
        elif first_fibre is not None and second_fibre is not None:
            if first_fibre == second_fibre:
                intraclump_contacts += 1
            else:
                fibre_fibre_contacts += 1
        first_body, second_body = O.bodies[first], O.bodies[second]
        if isinstance(first_body.shape, Sphere) and isinstance(second_body.shape, Sphere):
            penetration = max(0.0, float(interaction.geom.penetrationDepth))
            maximum_penetration = max(
                maximum_penetration,
                penetration / min(float(first_body.shape.radius), float(second_body.shape.radius)),
            )
    displacements = []
    for body_id in sand_ids:
        fractional = [float(O.bodies[body_id].state.pos[index]) / lengths[index] for index in range(3)]
        delta = [fractional[index] - initial["sand_fractional"][str(body_id)][index] for index in range(3)]
        delta = [value - round(value) for value in delta]
        displacements.append(vector_norm([delta[index] * lengths[index] for index in range(3)]))
    sand_contacts, load_bearing, rattler_fraction, coordination = sand_network(sand_ids)
    distinct = [len(values) for values in contacted]
    support_counts = [
        len(contacted[index].intersection(set(declared_supports[index])))
        for index in range(len(contacted))
    ]
    d50 = float(cfg["candidate_generation"]["D50_m"])
    return {
        "block": int(block),
        "iteration": int(O.iter),
        "time_s": float(O.time),
        "cell_dimensions_m": lengths,
        "cell_volume_m3": volume,
        "cell_volume_relative_drift": abs(volume - initial["cell_volume_m3"]) / initial["cell_volume_m3"],
        "principal_effective_stress_pa_compression_positive": stress,
        "mean_effective_stress_pa_compression_positive": mean_stress,
        "relative_mean_stress_error": abs(mean_stress - target) / target,
        "maximum_principal_stress_error": max(abs(value - target) / target for value in stress),
        "unbalanced_force": unbalanced,
        "unbalanced_force_defined": unbalanced_defined,
        "kinetic_energy_j": float(utils.kineticEnergy()),
        "sand_sand_real_contact_count": sand_contacts,
        "sand_sand_contact_retention_fraction": sand_contacts / float(cfg["network_export"]["required_sand_contact_count"]),
        "sand_load_bearing_particle_count_after_degree_lt2_pruning": load_bearing,
        "sand_rattler_fraction_degree_lt2_iterative": rattler_fraction,
        "sand_coordination_excluding_degree_lt2_rattlers": coordination,
        "distinct_sand_contacts_by_fibre": distinct,
        "contacted_sand_body_ids_by_fibre": [sorted(values) for values in contacted],
        "declared_support_contacts_by_fibre": support_counts,
        "minimum_distinct_sand_contacts_per_fibre": min(distinct),
        "minimum_declared_support_contacts_per_fibre": min(support_counts),
        "isolated_fibre_count": sum(1 for value in distinct if value == 0),
        "fibre_fibre_real_interaction_count": fibre_fibre_contacts,
        "intraclump_real_interaction_count": intraclump_contacts,
        "maximum_interobject_penetration_over_smaller_radius": maximum_penetration,
        "maximum_nonaffine_sand_displacement_m": max(displacements),
        "maximum_nonaffine_sand_displacement_over_D50": max(displacements) / d50,
    }


def write_history(path, rows):
    json_fields = {
        "cell_dimensions_m",
        "principal_effective_stress_pa_compression_positive",
        "distinct_sand_contacts_by_fibre",
        "contacted_sand_body_ids_by_fibre",
        "declared_support_contacts_by_fibre",
    }
    with open(path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for name in json_fields:
                encoded[name] = json.dumps(encoded[name], separators=(",", ":"))
            writer.writerow(encoded)


def engaged(row, gates):
    return (
        min(row["distinct_sand_contacts_by_fibre"])
        >= gates["minimum_distinct_sand_contacts_per_fibre_at_every_block"]
        and min(row["declared_support_contacts_by_fibre"])
        >= gates["minimum_declared_support_contacts_per_fibre_at_every_block"]
        and row["isolated_fibre_count"] <= gates["maximum_isolated_fibre_count_at_every_block"]
    )


def main():
    config_path = os.path.abspath(os.environ["STAGE26G_CAGE_CONFIG"])
    trial_id = os.environ["STAGE26G_CAGE_TRIAL_ID"]
    output = os.path.abspath(os.environ["STAGE26G_CAGE_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26G_CAGE_SCRIPT", __file__))
    cfg = load_json(config_path)
    assert_authority(cfg)
    bind_sources(cfg)
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    trial = next((row for row in cfg["trials"] if row["trial_id"] == trial_id), None)
    if trial is None:
        raise RuntimeError("trial is outside the frozen capture schedule")
    role = trial.get("stage26g_role")
    if role not in ("development_capture", "heldout_capture"):
        raise RuntimeError("unexpected Stage26g evidence role")
    if role == "heldout_capture" and cfg["authority"].get("heldout_execution_authorized") is not True:
        raise RuntimeError("held-out execution authority is false")
    if role == "development_capture" and cfg["authority"].get("heldout_execution_authorized") is True:
        raise RuntimeError("development trial cannot use held-out authority")
    placement_path = windows_to_wsl(trial["placement"])
    if sha256(placement_path) != trial["placement_sha256"]:
        raise RuntimeError("placement hash mismatch")
    placement = load_json(placement_path)
    if placement.get("passed") is not True or placement.get("record_type") != role:
        raise RuntimeError("placement role mismatch")
    if os.path.exists(output):
        raise RuntimeError("immutable capture output already exists")
    os.makedirs(output)

    checkpoint = windows_to_wsl(cfg["sources"]["stage25_checkpoint"])
    O.load(checkpoint)
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
            (str(body_id), [float(O.bodies[body_id].state.pos[index]) / lengths[index] for index in range(3)])
            for body_id in sand_ids
        ),
        "checkpoint_velocities_reset": True,
    }
    triax = next(engine for engine in O.engines if isinstance(engine, PeriTriaxController))
    target = float(cfg["frozen_physics"]["target_mean_effective_stress_pa"])
    triax.dead = False
    triax.goal = tuple(-target for _ in range(3))
    triax.maxStrainRate = tuple(float(cfg["capture_protocol"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["equilibrium_window_gates"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["equilibrium_window_gates"]["maximum_unbalanced_force"])
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
        label="stage26g_f37_plastic",
    ))
    fibre_parents, fibre_members, declared_supports = [], [], []
    for fibre in placement["fibres"]:
        bodies = [
            sphere(Vector3(*centre), float(cfg["frozen_physics"]["fibre_member_radius_m"]),
                   material=plastic_id, color=(0.85, 0.12, 0.10))
            for centre in fibre["member_centres_m"]
        ]
        parent_id, member_ids = O.bodies.appendClumped(bodies, 20)
        parent_id, member_ids = int(parent_id), [int(value) for value in member_ids]
        if len(member_ids) != int(cfg["frozen_physics"]["fibre_members"]):
            raise RuntimeError("F37 member count mismatch")
        parent = O.bodies[parent_id]
        mass_factor = float(cfg["frozen_physics"]["fibre_target_mass_kg"]) / float(parent.state.mass)
        parent.state.mass = float(cfg["frozen_physics"]["fibre_target_mass_kg"])
        parent.state.inertia = Vector3(*[float(value) * mass_factor for value in parent.state.inertia])
        parent.state.blockedDOFs = "xyzXYZ"
        fibre_parents.append(parent_id)
        fibre_members.append(member_ids)
        declared_supports.append([int(value) for value in fibre["support_sand_body_ids"]])
    zero_motion(sand_ids + fibre_parents)
    O.step()
    insertion = diagnostic(0, cfg, triax, sand_ids, fibre_members, declared_supports, initial)
    if not all(value == 4 for value in insertion["distinct_sand_contacts_by_fibre"]):
        raise RuntimeError("exact four-support insertion failed")

    history, streak, captured_window, capture_row = [], [], None, None
    adaptive = cfg["adaptive_equilibration"]
    for block in range(1, int(adaptive["maximum_blocks"]) + 1):
        O.run(int(cfg["capture_protocol"]["steps_per_block"]), True)
        zero_motion(fibre_parents)
        row = diagnostic(block, cfg, triax, sand_ids, fibre_members, declared_supports, initial)
        history.append(row)
        if not engaged(row, cfg["continuous_engagement_gates"]):
            streak = []
            break
        streak, event = advance_equilibrium_streak(
            streak,
            row,
            int(adaptive["minimum_blocks_before_equilibrium_window"]),
            int(adaptive["required_consecutive_passing_blocks"]),
            cfg["equilibrium_window_gates"],
        )
        if event is not None:
            captured_window = event
            capture_row = row
            break
        print("STAGE26G_CAGE=" + json.dumps({
            "trial_id": trial_id,
            "block": block,
            "streak": len(streak),
            "contacts": row["distinct_sand_contacts_by_fibre"],
            "anchors": row["declared_support_contacts_by_fibre"],
            "stress_pa": row["mean_effective_stress_pa_compression_positive"],
            "unbalanced": row["unbalanced_force"],
        }, sort_keys=True), flush=True)

    history_path = os.path.join(output, "fixed_capture_history.csv")
    write_history(history_path, history)
    state_path, state_sha256 = None, None
    if captured_window is not None:
        metadata = {
            "schema": "lbs.stage26g-captured-state-metadata.v1",
            "trial_id": trial_id,
            "config_sha256": sha256(config_path),
            "placement_sha256": sha256(placement_path),
            "sand_ids": sand_ids,
            "fibre_parents": fibre_parents,
            "fibre_members": fibre_members,
            "declared_supports": declared_supports,
            "initial": initial,
            "captured_window": captured_window,
            "capture_row": capture_row,
        }
        O.tags["stage26g_capture_metadata_json"] = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        state_path = os.path.join(output, "qualified_fixed_state.yade.gz")
        if os.path.exists(state_path):
            raise RuntimeError("refusing to overwrite capture state")
        O.save(state_path)
        state_sha256 = sha256(state_path)

    result = {
        "schema": "lbs.stage26g-qualified-state-capture-result.v1",
        "passed": True,
        "status": "captured_first_qualifying_fixed_state" if captured_window else "no_qualifying_state_captured",
        "trial": trial,
        "engine": {"yade_version": str(config.version), "features": list(config.features)},
        "protocol": {
            "all_fibres_fixed": True,
            "free_release": False,
            "steps_per_block": int(cfg["capture_protocol"]["steps_per_block"]),
            "blocks_executed": len(history),
            "maximum_blocks": int(adaptive["maximum_blocks"]),
        },
        "insertion": insertion,
        "captured_window": captured_window,
        "capture_row": capture_row,
        "qualified_fixed_state_captured": captured_window is not None,
        "source_hashes": {
            "config": sha256(config_path),
            "runner": sha256(script_path),
            "stage25_checkpoint": sha256(checkpoint),
            "placement": sha256(placement_path),
            "network_export_completion": sha256(windows_to_wsl(cfg["sources"]["network_export_completion"])),
            "stage26d_adaptive_common": sha256(windows_to_wsl(cfg["sources"]["stage26d_adaptive_common"])),
            "capture_common": sha256(windows_to_wsl(cfg["sources"]["capture_common"])),
        },
        "artifacts": {
            "history_sha256": sha256(history_path),
            "state_sha256": state_sha256,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26g-qualified-state-capture-completion.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": result["status"],
        "trial_id": trial_id,
        "qualified_fixed_state_captured": captured_window is not None,
        "result_sha256": sha256(result_path),
        "state_sha256": state_sha256,
        "wall_seconds": time.time() - START,
        "authority": {
            "reload_verification_authorized": captured_window is not None,
            "free_release_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26G_CAGE_COMPLETION=" + json.dumps({
        "trial_id": trial_id,
        "captured_window": captured_window,
        "state_sha256": state_sha256,
        "completion_sha256": sha256(completion_path),
    }, sort_keys=True), flush=True)


def failure_record(error):
    output = os.environ.get("STAGE26G_CAGE_OUTPUT")
    if not output:
        return
    output = os.path.abspath(output)
    if os.path.isdir(output) and not os.path.exists(os.path.join(output, "failure.json")):
        write_json_exclusive(os.path.join(output, "failure.json"), {
            "schema": "lbs.stage26g-qualified-state-capture-failure.v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "trial_id": os.environ.get("STAGE26G_CAGE_TRIAL_ID"),
            "error_type": type(error).__name__,
            "error": str(error),
        })


try:
    main()
except Exception as error:
    failure_record(error)
    raise
