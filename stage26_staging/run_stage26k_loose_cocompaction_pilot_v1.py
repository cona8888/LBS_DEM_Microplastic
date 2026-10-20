"""Stage26k exact-fibre loose-state co-compaction development pilot."""

from __future__ import print_function

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(os.environ.get("STAGE26K_SCRIPT", __file__)))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from yade import config, utils

from stage26b_revision2_prefilter_common_v1 import load_json, sha256, windows_to_wsl, write_json_exclusive
from stage26h_common_v1 import diagnostic, diagonal_lengths, write_history, zero_motion


START = time.time()


def assert_authority(cfg):
    if cfg.get("status") != "authorized_stage26k_spent_development_loose_cocompaction_pilot":
        raise RuntimeError("configuration is not Stage26k-authorized")
    authority = cfg["authority"]
    if authority.get("loose_state_cocompaction_authorized") is not True:
        raise RuntimeError("loose-state co-compaction authority is false")
    forbidden = (
        "free_release_authorized", "heldout_execution_authorized", "reserve_execution_authorized",
        "flow_execution_authorized", "deformation_authorized", "production_parametric_study_authorized",
    )
    if any(authority.get(name, False) for name in forbidden):
        raise RuntimeError("Stage26k configuration exceeds authority")


def bind_sources(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def solid_volume(sand_ids):
    return sum(4.0 * math.pi * float(O.bodies[body_id].shape.radius) ** 3 / 3.0 for body_id in sand_ids)


def finite(value):
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return True


def enrich(row, cfg, sand_solid_volume):
    target = float(cfg["preparation"]["target_mean_effective_stress_pa"])
    volume = float(O.cell.volume)
    row["sand_skeleton_void_ratio"] = volume / sand_solid_volume - 1.0
    row["sand_skeleton_void_ratio_difference_from_reference"] = (
        row["sand_skeleton_void_ratio"] - float(cfg["sand"]["reference_void_ratio"])
    )
    row["normalized_kinetic_energy_pV"] = float(utils.kineticEnergy()) / (target * volume)
    row["exact_sand_radii_unchanged"] = True
    row["exact_fibre_member_radius_m"] = float(cfg["fibre"]["member_radius_m"])
    row["sand_particle_count"] = int(cfg["sand"]["particle_count"])
    return row


def gate(row, cfg):
    a = cfg["acceptance"]
    return {
        "finite_state": finite(row),
        "mean_stress": row["relative_mean_stress_error"] <= a["maximum_relative_mean_stress_error"],
        "principal_stress": row["maximum_principal_stress_error"] <= a["maximum_principal_stress_error"],
        "unbalanced_force": row["unbalanced_force_defined"] and row["unbalanced_force"] <= a["maximum_unbalanced_force"],
        "normalized_kinetic_energy": row["normalized_kinetic_energy_pV"] <= a["maximum_normalized_kinetic_energy_pV"],
        "sand_coordination": row["sand_coordination_excluding_degree_lt2_rattlers"] >= a["minimum_sand_coordination_excluding_rattlers"],
        "sand_rattlers": row["sand_rattler_fraction_degree_lt2_iterative"] <= a["maximum_sand_rattler_fraction"],
        "overlap": row["maximum_interobject_penetration_over_smaller_radius"] <= a["maximum_interobject_penetration_over_smaller_radius"],
        "void_ratio": abs(row["sand_skeleton_void_ratio_difference_from_reference"]) <= a["maximum_absolute_sand_skeleton_void_ratio_difference"],
        "fibre_contacts": min(row["distinct_sand_contacts_by_fibre"]) >= a["minimum_distinct_sand_contacts_per_fibre"],
        "no_isolated_fibre": row["isolated_fibre_count"] == 0,
        "no_fibre_fibre_contact": row["fibre_fibre_real_interaction_count"] <= a["maximum_fibre_fibre_real_interaction_count"],
        "no_intraclump_contact": row["intraclump_real_interaction_count"] <= a["maximum_intraclump_real_interaction_count"],
        "sand_particle_count": row["sand_particle_count"] == int(cfg["sand"]["particle_count"]),
        "exact_geometry": row["exact_sand_radii_unchanged"] is True,
    }


def main():
    config_path = os.path.abspath(os.environ["STAGE26K_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26K_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26K_SCRIPT", __file__))
    cfg = load_json(config_path)
    assert_authority(cfg)
    bind_sources(cfg)
    if sha256(script_path) != cfg["sources"]["runner_sha256"]:
        raise RuntimeError("runner hash mismatch")
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26k output already exists")
    os.makedirs(output)

    O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    sand_ids = sorted(
        int(body.id) for body in O.bodies
        if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember
    )
    if len(sand_ids) != int(cfg["sand"]["particle_count"]):
        raise RuntimeError("Stage25 sand-particle count mismatch")
    original_radii = dict((body_id, float(O.bodies[body_id].shape.radius)) for body_id in sand_ids)
    sand_solid = solid_volume(sand_ids)
    old_lengths = diagonal_lengths()
    old_volume = float(O.cell.volume)
    initial_e = float(cfg["preparation"]["initial_sand_skeleton_void_ratio"])
    desired_volume = sand_solid * (1.0 + initial_e)
    expansion = (desired_volume / old_volume) ** (1.0 / 3.0)
    fractional = dict(
        (body_id, [float(O.bodies[body_id].state.pos[k]) / old_lengths[k] for k in range(3)])
        for body_id in sand_ids
    )
    new_lengths = [value * expansion for value in old_lengths]
    O.cell.hSize = Matrix3(new_lengths[0], 0, 0, 0, new_lengths[1], 0, 0, 0, new_lengths[2])
    for body_id in sand_ids:
        O.bodies[body_id].state.pos = Vector3(*[fractional[body_id][k] * new_lengths[k] for k in range(3)])
    zero_motion(sand_ids)
    O.step()

    placement = load_json(windows_to_wsl(cfg["sources"]["placement"]))
    plastic_id = O.materials.append(FrictMat(
        young=float(cfg["fibre"]["young_pa"]), poisson=float(cfg["fibre"]["poisson"]),
        frictionAngle=math.atan(float(cfg["fibre"]["friction_coefficient"])),
        density=float(cfg["fibre"]["density_kg_m3"]), label="stage26k_f37_plastic",
    ))
    parent_ids, member_groups = [], []
    for fibre in placement["fibres"]:
        original_centres = [[float(value) for value in centre] for centre in fibre["member_centres_m"]]
        pivot = [sum(centre[k] for centre in original_centres) / len(original_centres) for k in range(3)]
        new_pivot = [pivot[k] * expansion for k in range(3)]
        centres = [
            [new_pivot[k] + centre[k] - pivot[k] for k in range(3)]
            for centre in original_centres
        ]
        bodies = [
            sphere(Vector3(*centre), float(cfg["fibre"]["member_radius_m"]), material=plastic_id, color=(0.85, 0.12, 0.10))
            for centre in centres
        ]
        parent_id, member_ids = O.bodies.appendClumped(bodies, 20)
        parent_id, member_ids = int(parent_id), [int(value) for value in member_ids]
        parent = O.bodies[parent_id]
        mass_factor = float(cfg["fibre"]["target_mass_kg"]) / float(parent.state.mass)
        parent.state.mass = float(cfg["fibre"]["target_mass_kg"])
        parent.state.inertia = Vector3(*[float(value) * mass_factor for value in parent.state.inertia])
        parent.state.blockedDOFs = "xyzXYZ"
        parent_ids.append(parent_id)
        member_groups.append(member_ids)
    zero_motion(sand_ids + parent_ids)
    O.step()

    triax = next(engine for engine in O.engines if isinstance(engine, PeriTriaxController))
    target = float(cfg["preparation"]["target_mean_effective_stress_pa"])
    triax.dead = False
    triax.goal = tuple(-target for _ in range(3))
    triax.maxStrainRate = tuple(float(cfg["preparation"]["maximum_strain_rate_s_inv"]) for _ in range(3))
    triax.relStressTol = float(cfg["acceptance"]["maximum_relative_mean_stress_error"])
    triax.maxUnbalanced = float(cfg["acceptance"]["maximum_unbalanced_force"])
    for engine in O.engines:
        if isinstance(engine, GlobalStiffnessTimeStepper):
            engine.timestepSafetyCoefficient = float(cfg["preparation"]["timestep_safety_coefficient"])
        if isinstance(engine, NewtonIntegrator):
            engine.damping = float(cfg["preparation"]["newton_damping"])
            engine.gravity = Vector3(*cfg["preparation"]["gravity_m_s2"])

    initial = {
        "cell_volume_m3": float(O.cell.volume),
        "sand_fractional": dict(
            (str(body_id), [float(O.bodies[body_id].state.pos[k]) / new_lengths[k] for k in range(3)])
            for body_id in sand_ids
        ),
        "checkpoint_velocities_reset": True,
    }
    declared_supports = [[] for _ in member_groups]
    insertion = enrich(diagnostic(0, cfg, triax, sand_ids, member_groups, declared_supports, initial), cfg, sand_solid)
    insertion["phase"] = "loose_exact_geometry_mixture"
    if insertion["maximum_interobject_penetration_over_smaller_radius"] > 0.02:
        raise RuntimeError("initial loose-state overlap exceeds pilot guard")
    if insertion["fibre_fibre_real_interaction_count"] or insertion["intraclump_real_interaction_count"]:
        raise RuntimeError("invalid fibre interaction in initial loose state")

    history, streak, final_checks = [], 0, None
    qualified = False
    status = "resource_ceiling_without_qualification"
    for block in range(1, int(cfg["preparation"]["maximum_check_blocks"]) + 1):
        O.run(int(cfg["preparation"]["steps_per_check_block"]), True)
        zero_motion(parent_ids)
        if any(abs(float(O.bodies[body_id].shape.radius) - original_radii[body_id]) > 1e-15 for body_id in sand_ids):
            raise RuntimeError("sand radius changed during Stage26k")
        row = enrich(diagnostic(block, cfg, triax, sand_ids, member_groups, declared_supports, initial), cfg, sand_solid)
        row["phase"] = "loose_state_isotropic_cocompaction"
        history.append(row)
        final_checks = gate(row, cfg)
        eligible = block >= int(cfg["preparation"]["minimum_check_blocks"])
        streak = streak + 1 if eligible and all(final_checks.values()) else 0
        if block == 1 or block % 20 == 0 or streak > 0:
            print("STAGE26K=" + json.dumps({
                "block": block, "void_ratio": row["sand_skeleton_void_ratio"],
                "stress_pa": row["mean_effective_stress_pa_compression_positive"],
                "unbalanced": row["unbalanced_force"], "sand_contacts": row["sand_sand_real_contact_count"],
                "fibre_contacts": row["distinct_sand_contacts_by_fibre"], "streak": streak,
            }, sort_keys=True), flush=True)
        if not final_checks["finite_state"] or row["maximum_interobject_penetration_over_smaller_radius"] > 0.05:
            status = "hard_guard_failed"
            break
        if streak >= int(cfg["preparation"]["required_consecutive_pass_blocks"]):
            qualified = True
            status = "fixed_fibre_loose_cocompaction_qualified"
            break

    history_path = os.path.join(output, "cocompaction_history.csv")
    write_history(history_path, history)
    state_path, state_digest = None, None
    if qualified:
        state_path = os.path.join(output, "qualified_fixed_fibre_cocompacted_state.yade.gz")
        O.tags["stage26k_metadata_json"] = json.dumps({
            "schema": "lbs.stage26k-qualified-state-metadata.v1", "config_sha256": sha256(config_path),
            "trial": cfg["trial"], "final_streak": streak,
        }, sort_keys=True, separators=(",", ":"))
        O.save(state_path)
        state_digest = sha256(state_path)
    result = {
        "schema": "lbs.stage26k-loose-state-exact-fibre-cocompaction-pilot-result.v1",
        "passed": True, "status": status, "qualified": qualified, "trial": cfg["trial"],
        "insertion": insertion, "terminal": history[-1], "terminal_checks": final_checks,
        "consecutive_pass_blocks": streak, "blocks_executed": len(history),
        "exact_sand_radii_unchanged": True, "exact_fibre_geometry_unchanged": True,
        "artifacts": {"history_sha256": sha256(history_path), "state_sha256": state_digest},
        "source_hashes": {"config": sha256(config_path), "runner": sha256(script_path),
                          "placement": cfg["sources"]["placement_sha256"],
                          "stage25_checkpoint": cfg["sources"]["stage25_checkpoint_sha256"]},
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {
        "schema": "lbs.stage26k-loose-state-exact-fibre-cocompaction-pilot-completion.v1",
        "passed": True, "status": status, "qualified": qualified,
        "result_sha256": sha256(result_path), "state_sha256": state_digest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.time() - START,
        "authority": {"free_release_authorized": False, "heldout_execution_authorized": False,
                      "reserve_execution_authorized": False, "flow_execution_authorized": False,
                      "deformation_authorized": False},
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26K_COMPLETION_SHA256=" + sha256(completion_path), flush=True)


if __name__ == "__main__":
    main()
