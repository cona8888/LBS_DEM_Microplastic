"""Stage26r clean periodic radius restoration with explicit fixed-cell kinematics."""
from __future__ import print_function

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade import config, utils


START = time.time()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def windows_to_wsl(path):
    path = str(path)
    if len(path) >= 3 and path[1:3] in (":\\", ":/"):
        return "/mnt/%s/%s" % (path[0].lower(), path[3:].replace("\\", "/"))
    return path


def write_json_exclusive(path, data):
    with open(path, "x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def find_engine(name):
    matches = [engine for engine in O.engines if engine.__class__.__name__ == name]
    if len(matches) != 1:
        raise RuntimeError("expected one %s, found %d" % (name, len(matches)))
    return matches[0]


def set_friction(sand_ids, coefficient):
    sand_set = set(sand_ids)
    for material_id in {int(O.bodies[body_id].material.id) for body_id in sand_ids}:
        O.materials[material_id].frictionAngle = math.atan(float(coefficient))
    for interaction in O.interactions:
        if interaction.isReal and int(interaction.id1) in sand_set and int(interaction.id2) in sand_set:
            interaction.phys.tangensOfFrictionAngle = float(coefficient)


def network(sand_ids):
    sand_set = set(sand_ids)
    edges = [
        (int(i.id1), int(i.id2))
        for i in O.interactions
        if i.isReal and int(i.id1) in sand_set and int(i.id2) in sand_set
    ]
    active = set(sand_ids)
    changed = True
    while changed:
        degree = {body_id: 0 for body_id in active}
        for first, second in edges:
            if first in active and second in active:
                degree[first] += 1
                degree[second] += 1
        remove = {body_id for body_id, value in degree.items() if value < 2}
        changed = bool(remove)
        active.difference_update(remove)
    retained = sum(1 for first, second in edges if first in active and second in active)
    return len(edges), len(active), 1.0 - len(active) / float(len(sand_ids)), 2.0 * retained / len(active) if active else 0.0


def diagnostic(record, phase, phase_index, cfg, sand_ids, original_radii, original_cell, original_solid):
    cell = [float(value) for value in O.cell.size]
    volume = cell[0] * cell[1] * cell[2]
    stress = utils.getStress(volume)
    principal = [-float(stress[0, 0]), -float(stress[1, 1]), -float(stress[2, 2])]
    mean_stress = sum(principal) / 3.0
    target_stress = float(cfg["target_state"]["isotropic_stress_pa_compression_positive"])
    current_solid = sum(4.0 * math.pi * float(O.bodies[body_id].shape.radius) ** 3 / 3.0 for body_id in sand_ids)
    contacts, active, rattlers, coordination = network(sand_ids)
    sand_set = set(sand_ids)
    maximum_overlap = 0.0
    for interaction in O.interactions:
        if not interaction.isReal or int(interaction.id1) not in sand_set or int(interaction.id2) not in sand_set:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        denominator = min(float(O.bodies[first].shape.radius), float(O.bodies[second].shape.radius))
        maximum_overlap = max(maximum_overlap, max(0.0, float(interaction.geom.penetrationDepth)) / denominator)
    unbalanced = float(utils.unbalancedForce())
    if not math.isfinite(unbalanced):
        unbalanced = 1.0
    kinetic = float(utils.kineticEnergy())
    radius_errors = [abs(float(O.bodies[body_id].shape.radius) - original_radii[body_id]) / original_radii[body_id] for body_id in sand_ids]
    return {
        "record": int(record),
        "phase": phase,
        "phase_index": int(phase_index),
        "iteration": int(O.iter),
        "time_s": float(O.time),
        "cell_dimensions_m": cell,
        "maximum_relative_cell_dimension_change": max(abs(cell[i] - original_cell[i]) / original_cell[i] for i in range(3)),
        "void_ratio_using_current_radii": volume / current_solid - 1.0,
        "void_ratio_using_final_radii": volume / original_solid - 1.0,
        "maximum_relative_radius_error": max(radius_errors),
        "principal_stress_pa_compression_positive": principal,
        "mean_stress_pa_compression_positive": mean_stress,
        "relative_mean_stress_error": abs(mean_stress - target_stress) / target_stress,
        "maximum_principal_stress_error": max(abs(value - target_stress) / target_stress for value in principal),
        "unbalanced_force": unbalanced,
        "kinetic_energy_j": kinetic,
        "normalized_kinetic_energy_pV": kinetic / (target_stress * volume),
        "real_contact_count": contacts,
        "load_bearing_particle_count": active,
        "rattler_fraction": rattlers,
        "coordination_excluding_rattlers": coordination,
        "maximum_overlap_over_smaller_radius": maximum_overlap,
        "sand_friction_coefficient": math.tan(float(O.bodies[sand_ids[0]].material.frictionAngle)),
        "particle_count": len(sand_ids),
    }


def checks(row, cfg):
    limits = cfg["acceptance"]
    values = [row["void_ratio_using_current_radii"], row["mean_stress_pa_compression_positive"], row["unbalanced_force"], row["kinetic_energy_j"], row["maximum_overlap_over_smaller_radius"]]
    return {
        "finite_state": all(math.isfinite(float(value)) for value in values),
        "exact_radii": row["maximum_relative_radius_error"] <= float(limits["maximum_relative_radius_error"]),
        "unchanged_cell": row["maximum_relative_cell_dimension_change"] <= float(limits["maximum_relative_cell_dimension_change"]),
        "void_ratio": abs(row["void_ratio_using_current_radii"] - float(cfg["target_state"]["void_ratio"])) <= float(limits["maximum_void_ratio_error"]),
        "mean_stress": row["relative_mean_stress_error"] <= float(limits["maximum_relative_mean_stress_error"]),
        "principal_stress": row["maximum_principal_stress_error"] <= float(limits["maximum_principal_stress_error"]),
        "unbalanced_force": row["unbalanced_force"] <= float(limits["maximum_unbalanced_force"]),
        "kinetic_energy": row["normalized_kinetic_energy_pV"] <= float(limits["maximum_normalized_kinetic_energy_pV"]),
        "overlap": row["maximum_overlap_over_smaller_radius"] <= float(limits["maximum_overlap_over_smaller_radius"]),
        "coordination": row["coordination_excluding_rattlers"] >= float(limits["minimum_coordination_excluding_rattlers"]),
        "rattlers": row["rattler_fraction"] <= float(limits["maximum_rattler_fraction"]),
        "particle_count": row["particle_count"] == int(limits["required_particle_count"]),
    }


def write_history(path, rows):
    with open(path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            encoded["cell_dimensions_m"] = json.dumps(encoded["cell_dimensions_m"], separators=(",", ":"))
            encoded["principal_stress_pa_compression_positive"] = json.dumps(encoded["principal_stress_pa_compression_positive"], separators=(",", ":"))
            writer.writerow(encoded)


def main():
    config_path = os.path.abspath(os.environ["STAGE26R_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26R_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26R_SCRIPT", __file__))
    with open(config_path, "r") as stream:
        cfg = json.load(stream)
    if cfg.get("status") != "authorized_stage26r_clean_periodic_radius_restoration":
        raise RuntimeError("configuration is not Stage26r-authorized")
    if cfg.get("authority", {}).get("clean_radius_restoration_authorized") is not True:
        raise RuntimeError("clean restoration lacks authority")
    if any(cfg["authority"].get(key, False) for key in ("fibre_execution_authorized", "flow_execution_authorized", "permeability_claim_authorized", "production_parametric_study_authorized")):
        raise RuntimeError("Stage26r authority exceeded")
    if sha256(script_path) != cfg["sources"]["runner"]["sha256"]:
        raise RuntimeError("runner hash mismatch")
    for name in ("stage25_checkpoint", "stage25_state_probe", "stage26q_nonacceptance", "research_contract", "cell_drift_failure", "design01_config", "fixed_cell_smoke", "input_state"):
        binding = cfg["sources"][name]
        if sha256(windows_to_wsl(binding["path"])) != binding["sha256"]:
            raise RuntimeError("source hash mismatch: " + name)
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("YADE version mismatch")
    if os.path.exists(output):
        raise RuntimeError("immutable Stage26r output exists")
    os.makedirs(output)

    O.load(windows_to_wsl(cfg["sources"]["input_state"]["path"]))
    if not O.periodic:
        raise RuntimeError("input state is not periodic")
    controller = find_engine("PeriTriaxController")
    newton = find_engine("NewtonIntegrator")
    stepper = find_engine("GlobalStiffnessTimeStepper")
    controller.dead = True
    O.cell.velGrad = Matrix3.Zero
    newton.gravity = Vector3(0.0, 0.0, 0.0)
    newton.damping = float(cfg["restoration"]["newton_damping"])
    stepper.timestepSafetyCoefficient = float(cfg["restoration"]["timestep_safety_coefficient"])
    sand_ids = [int(body.id) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
    if len(sand_ids) != int(cfg["acceptance"]["required_particle_count"]):
        raise RuntimeError("particle count mismatch")
    original_radii = {body_id: float(O.bodies[body_id].shape.radius) for body_id in sand_ids}
    original_cell = [float(value) for value in O.cell.size]
    original_solid = sum(4.0 * math.pi * radius ** 3 / 3.0 for radius in original_radii.values())
    for body_id in sand_ids:
        O.bodies[body_id].state.vel = Vector3.Zero
        O.bodies[body_id].state.angVel = Vector3.Zero

    restoration = cfg["restoration"]
    scale = float(restoration["initial_radius_scale"])
    for body_id in sand_ids:
        utils.growParticle(body_id, scale, True)
    set_friction(sand_ids, float(restoration["preparation_friction_coefficient"]))
    O.step()
    history = []
    record = 0
    blocks = int(restoration["growth_blocks"])
    factor = (1.0 / scale) ** (1.0 / blocks)
    status = "radius_restoration_not_qualified"
    hard_guard = float(cfg["acceptance"]["hard_guard_overlap_over_smaller_radius"])
    for block in range(1, blocks + 1):
        for body_id in sand_ids:
            multiplier = original_radii[body_id] / float(O.bodies[body_id].shape.radius) if block == blocks else factor
            utils.growParticle(body_id, multiplier, True)
        O.run(int(restoration["steps_per_growth_block"]), True)
        record += 1
        row = diagnostic(record, "radius_restoration", block, cfg, sand_ids, original_radii, original_cell, original_solid)
        history.append(row)
        if block == 1 or block % 10 == 0 or block == blocks:
            print("STAGE26R_GROW=" + json.dumps({"block": block, "e": row["void_ratio_using_current_radii"], "stress": row["principal_stress_pa_compression_positive"], "overlap": row["maximum_overlap_over_smaller_radius"], "radius_error": row["maximum_relative_radius_error"]}, sort_keys=True), flush=True)
        if row["maximum_relative_cell_dimension_change"] > float(cfg["acceptance"]["maximum_relative_cell_dimension_change"]):
            status = "radius_restoration_fixed_cell_guard_failed"
            break
        if row["maximum_overlap_over_smaller_radius"] > hard_guard:
            status = "radius_restoration_hard_guard_failed"
            break

    final = history[-1]
    final_checks = checks(final, cfg)
    if status != "radius_restoration_hard_guard_failed" and final_checks["exact_radii"]:
        set_friction(sand_ids, float(restoration["restored_friction_coefficient"]))
        streak = 0
        status = "fixed_cell_hold_not_qualified"
        hold = cfg["hold"]
        for block in range(1, int(hold["maximum_blocks"]) + 1):
            O.run(int(hold["steps_per_block"]), True)
            record += 1
            row = diagnostic(record, "restored_friction_fixed_cell_hold", block, cfg, sand_ids, original_radii, original_cell, original_solid)
            history.append(row)
            final_checks = checks(row, cfg)
            eligible = block >= int(hold["minimum_blocks"])
            streak = streak + 1 if eligible and all(final_checks.values()) else 0
            if block == 1 or block % 20 == 0 or streak:
                print("STAGE26R_HOLD=" + json.dumps({"block": block, "e": row["void_ratio_using_current_radii"], "stress": row["principal_stress_pa_compression_positive"], "unbalanced": row["unbalanced_force"], "ke_pV": row["normalized_kinetic_energy_pV"], "streak": streak}, sort_keys=True), flush=True)
            if row["maximum_relative_cell_dimension_change"] > float(cfg["acceptance"]["maximum_relative_cell_dimension_change"]):
                status = "fixed_cell_hold_boundary_guard_failed"
                break
            if row["maximum_overlap_over_smaller_radius"] > hard_guard:
                status = "fixed_cell_hold_hard_guard_failed"
                break
            if streak >= int(hold["required_consecutive_pass_blocks"]):
                status = "qualified_periodic_radius_restoration"
                break
        final = history[-1]
        final_checks = checks(final, cfg)

    passed = status == "qualified_periodic_radius_restoration" and all(final_checks.values())
    history_path = os.path.join(output, "history.csv")
    write_history(history_path, history)
    state_path = os.path.join(output, "qualified_restored_periodic_state.yade.gz")
    if passed:
        O.save(state_path)
    result = {
        "schema": "lbs.stage26r-periodic-radius-restoration-result.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "passed": bool(passed),
        "claim_boundary": cfg["claim_boundary"],
        "checks": final_checks,
        "terminal": final,
        "records": len(history),
        "source_hashes": {"config": sha256(config_path), "runner": sha256(script_path), "input_state": cfg["sources"]["input_state"]["sha256"]},
        "artifacts": {"history": {"path": history_path, "sha256": sha256(history_path)}},
        "authority": cfg["authority"],
        "elapsed_wall_s": time.time() - START,
    }
    if passed:
        result["artifacts"]["state"] = {"path": state_path, "sha256": sha256(state_path)}
    result_path = os.path.join(output, "result.json")
    write_json_exclusive(result_path, result)
    completion = {"schema": "lbs.stage26r-periodic-radius-restoration-completion.v2", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "status": status, "passed": bool(passed), "result": {"path": result_path, "sha256": sha256(result_path)}, "terminal": final, "checks": final_checks, "authority": cfg["authority"]}
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26R_COMPLETION=" + completion_path, flush=True)
    print("STAGE26R_COMPLETION_SHA256=" + sha256(completion_path), flush=True)
    raise SystemExit(0 if passed else 2)


main()
