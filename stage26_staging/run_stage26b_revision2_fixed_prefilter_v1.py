"""YADE single-trial fixed-fibre prefilter for Stage26b Revision 2.

The script never releases a fibre and never saves a promoted DEM checkpoint. A
future immutable execution configuration must explicitly authorize this exact
prefilter trial.
"""

from __future__ import print_function

import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(os.environ.get("STAGE26B_R2_PREFILTER_SCRIPT", __file__)))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from yade import config, utils

from stage26b_revision2_prefilter_common_v1 import (
    candidate_contact_pass,
    iterative_core,
    load_json,
    sand_terminal_pass,
    sha256,
    windows_to_wsl,
    write_json_exclusive,
)


START = time.time()


def assert_prefilter_authority(cfg):
    if cfg.get("status") != "authorized_stage26b_revision2_fixed_prefilter":
        raise RuntimeError("configuration is not fixed-prefilter authorized")
    authority = cfg["authority"]
    if authority.get("prefilter_yade_execution_authorized") is not True:
        raise RuntimeError("prefilter authority is false")
    forbidden = (
        "network_export_execution_authorized",
        "placement_generation_authorized",
        "two_fibre_free_release_authorized",
        "four_fibre_execution_authorized",
        "eight_or_more_fibre_execution_authorized",
        "flow_execution_authorized",
        "deformation_coupled_flow_authorized",
        "transient_two_way_coupling_authorized",
        "production_parametric_study_authorized",
    )
    if any(authority.get(name, False) for name in forbidden):
        raise RuntimeError("prefilter configuration exceeds its authority")
    protocol = cfg["prefilter"]
    if protocol.get("all_fibres_fixed") is not True or protocol.get("free_release") is not False:
        raise RuntimeError("fixed-only prefilter protocol is not frozen")


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
    _, core_degree, active = iterative_core(sand_ids, edges, 2)
    retained_edges = sum(1 for first, second in edges if first in active and second in active)
    coordination = 2.0 * retained_edges / len(active) if active else 0.0
    return len(edges), len(active), 1.0 - len(active) / float(len(sand_ids)), coordination, core_degree


def diagnostic(block, cfg, triax, sand_ids, fibre_members, declared_anchors, initial):
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
    sand_contacts, load_bearing, rattler_fraction, coordination, _ = sand_network(sand_ids)
    distinct = [len(values) for values in contacted]
    anchor_counts = [len(contacted[index].intersection(set(declared_anchors[index]))) for index in range(len(contacted))]
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
        "declared_anchor_contacts_by_fibre": anchor_counts,
        "minimum_distinct_sand_contacts_per_fibre": min(distinct),
        "minimum_declared_anchor_contacts_per_fibre": min(anchor_counts),
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
        "declared_anchor_contacts_by_fibre",
    }
    with open(path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for name in json_fields:
                encoded[name] = json.dumps(encoded[name], separators=(",", ":"))
            writer.writerow(encoded)


def main():
    config_path = os.path.abspath(os.environ["STAGE26B_R2_PREFILTER_CONFIG"])
    trial_id = os.environ["STAGE26B_R2_TRIAL_ID"]
    output = os.path.abspath(os.environ["STAGE26B_R2_PREFILTER_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26B_R2_PREFILTER_SCRIPT", __file__))
    common_path = os.path.join(os.path.dirname(script_path), "stage26b_revision2_prefilter_common_v1.py")
    cfg = load_json(config_path)
    assert_prefilter_authority(cfg)
    bind_sources(cfg)
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    trial = next((row for row in cfg["trials"] if row["trial_id"] == trial_id), None)
    if trial is None:
        raise RuntimeError("trial is outside the frozen prefilter schedule")
    placement_path = windows_to_wsl(trial["placement"])
    if sha256(placement_path) != trial["placement_sha256"]:
        raise RuntimeError("placement hash mismatch")
    if trial["record_type"] == "candidate":
        control_path = windows_to_wsl(cfg["sources"]["control_checkpoint"])
        controls = load_json(control_path)
        if controls.get("passed") is not True or controls.get("both_controls_reproduced") is not True:
            raise RuntimeError("candidate prefilter is blocked by control checkpoint")
    network_completion = load_json(windows_to_wsl(cfg["sources"]["network_export_completion"]))
    if network_completion.get("passed") is not True or network_completion.get("status") != "passed_read_only_network_export":
        raise RuntimeError("accepted Stage25 network export is unavailable")
    placement = load_json(placement_path)
    if placement.get("passed") is not True or int(placement["fibre_count"]) != int(trial["fibre_count"]):
        raise RuntimeError("placement is not accepted or fibre count mismatches")
    if os.path.exists(output):
        raise RuntimeError("immutable prefilter output already exists")
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
    triax.maxStrainRate = tuple(float(cfg["prefilter"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["sand_health_gates_at_terminal_block"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["sand_health_gates_at_terminal_block"]["maximum_unbalanced_force"])
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
        label="stage26b_revision2_f37_plastic",
    ))
    fibre_parents = []
    fibre_members = []
    declared_anchors = []
    for fibre in placement["fibres"]:
        bodies = [
            sphere(Vector3(*centre), float(cfg["frozen_physics"]["fibre_member_radius_m"]), material=plastic_id, color=(0.85, 0.12, 0.10))
            for centre in fibre["member_centres_m"]
        ]
        parent_id, member_ids = O.bodies.appendClumped(bodies, 20)
        parent_id = int(parent_id)
        member_ids = [int(value) for value in member_ids]
        if len(member_ids) != int(cfg["frozen_physics"]["fibre_members"]):
            raise RuntimeError("F37 member count mismatch")
        parent = O.bodies[parent_id]
        mass_factor = float(cfg["frozen_physics"]["fibre_target_mass_kg"]) / float(parent.state.mass)
        parent.state.mass = float(cfg["frozen_physics"]["fibre_target_mass_kg"])
        parent.state.inertia = Vector3(*[float(value) * mass_factor for value in parent.state.inertia])
        parent.state.blockedDOFs = "xyzXYZ"
        fibre_parents.append(parent_id)
        fibre_members.append(member_ids)
        declared_anchors.append([int(value) for value in fibre["anchor_sand_body_ids"]])
    zero_motion(sand_ids + fibre_parents)
    O.step()
    insertion = diagnostic(0, cfg, triax, sand_ids, fibre_members, declared_anchors, initial)
    history = []
    for block in range(1, int(cfg["prefilter"]["blocks"]) + 1):
        O.run(int(cfg["prefilter"]["steps_per_block"]), True)
        zero_motion(fibre_parents)
        row = diagnostic(block, cfg, triax, sand_ids, fibre_members, declared_anchors, initial)
        history.append(row)
        print("STAGE26B_R2_PREFILTER=" + json.dumps({
            "trial_id": trial_id,
            "block": block,
            "contacts": row["distinct_sand_contacts_by_fibre"],
            "anchors": row["declared_anchor_contacts_by_fibre"],
            "stress_pa": row["mean_effective_stress_pa_compression_positive"],
            "unbalanced": row["unbalanced_force"],
        }, sort_keys=True), flush=True)
    terminal = history[-1]
    insertion_exact = all(value == 2 for value in insertion["distinct_sand_contacts_by_fibre"])
    if trial["record_type"] == "control" and trial_id == "positive_stage26a":
        control_reproduced = insertion_exact and all(min(row["distinct_sand_contacts_by_fibre"]) >= 2 for row in history)
        candidate_passed = False
    elif trial["record_type"] == "control" and trial_id == "negative_stage26b_failure":
        control_reproduced = insertion_exact and history[0]["distinct_sand_contacts_by_fibre"][0] == 0
        candidate_passed = False
    elif trial["record_type"] == "candidate":
        control_reproduced = None
        candidate_passed = (
            insertion_exact
            and candidate_contact_pass(history, cfg["candidate_contact_gates"])
            and sand_terminal_pass(terminal, cfg["sand_health_gates_at_terminal_block"])
            and terminal["fibre_fibre_real_interaction_count"] == 0
            and terminal["intraclump_real_interaction_count"] == 0
        )
    else:
        raise RuntimeError("invalid trial role")
    minimum_contacts = min(min(row["distinct_sand_contacts_by_fibre"]) for row in history)
    summary = {
        "candidate_index": trial.get("candidate_index"),
        "minimum_contacts_over_all_fibres_and_blocks": minimum_contacts,
        "minimum_anchor_degree": int(trial["minimum_anchor_degree"]),
        "maximum_sand_displacement_over_D50": max(row["maximum_nonaffine_sand_displacement_over_D50"] for row in history),
        "maximum_force_residual_relative": float(placement["maximum_initial_force_residual_relative"]),
        "maximum_moment_residual_relative": float(placement["maximum_initial_moment_residual_relative"]),
    }
    history_path = os.path.join(output, "fixed_conditioning_history.csv")
    write_history(history_path, history)
    result = {
        "schema": "lbs.stage26b-revision2-fixed-prefilter-result.v1",
        "passed": True,
        "status": "completed_fixed_prefilter_without_release",
        "trial": trial,
        "engine": {"yade_version": str(config.version), "features": list(config.features)},
        "protocol": {
            "all_fibres_fixed": True,
            "free_release": False,
            "steps_per_block": int(cfg["prefilter"]["steps_per_block"]),
            "blocks": len(history),
        },
        "insertion": insertion,
        "terminal": terminal,
        "control_reproduced": control_reproduced,
        "candidate_passed_prefilter": candidate_passed,
        "prefilter_summary": summary,
        "source_hashes": {
            "config": sha256(config_path),
            "runner": sha256(script_path),
            "common": sha256(common_path),
            "stage25_checkpoint": sha256(checkpoint),
            "placement": sha256(placement_path),
            "network_export_completion": sha256(windows_to_wsl(cfg["sources"]["network_export_completion"])),
        },
        "artifacts": {"fixed_conditioning_history_csv_sha256": sha256(history_path)},
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26b-revision2-fixed-prefilter-completion.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "completed_control_prefilter" if trial["record_type"] == "control" else "completed_candidate_prefilter",
        "trial": trial,
        "control_reproduced": control_reproduced,
        "candidate_passed_prefilter": candidate_passed,
        "result_sha256": sha256(result_path),
        "wall_seconds": time.time() - START,
        "authority": {
            "candidate_selection_authorized": trial["record_type"] == "candidate",
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26B_R2_PREFILTER_COMPLETION=" + json.dumps({
        "trial_id": trial_id,
        "control_reproduced": control_reproduced,
        "candidate_passed_prefilter": candidate_passed,
        "completion_sha256": sha256(completion_path),
    }, sort_keys=True), flush=True)


def failure_record(error):
    output = os.environ.get("STAGE26B_R2_PREFILTER_OUTPUT")
    if not output:
        return
    output = os.path.abspath(output)
    if os.path.isdir(output) and not os.path.exists(os.path.join(output, "failure.json")):
        write_json_exclusive(os.path.join(output, "failure.json"), {
            "schema": "lbs.stage26b-revision2-fixed-prefilter-failure.v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "trial_id": os.environ.get("STAGE26B_R2_TRIAL_ID"),
            "error_type": type(error).__name__,
            "error": str(error),
        })


try:
    main()
except Exception as error:
    failure_record(error)
    raise
