"""Stage25a: prepare load-bearing periodic LBS sphere packings at low stress.

Run with YADE 2022.01a. This is a pure-sand preparation qualification only.
"""

from __future__ import print_function

import bisect
import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from yade import config, pack, utils


CONFIG_PATH = os.path.abspath(os.environ["STAGE25_CONFIG"])
OUTPUT_ROOT = os.path.abspath(os.environ["STAGE25_OUTPUT"])
SCRIPT_PATH = os.path.abspath(os.environ.get("STAGE25_SCRIPT", __file__))
START = time.time()
SMOKE_MAX_BLOCKS = int(os.environ.get("STAGE25_SMOKE_MAX_BLOCKS", "0"))


def sha256(path):
    result = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json_exclusive(path, payload):
    with open(path, "x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def windows_to_wsl(path):
    normalized = str(path).replace("\\", "/")
    if len(normalized) >= 3 and normalized[1:3] == ":/":
        return "/mnt/%s/%s" % (normalized[0].lower(), normalized[3:])
    return normalized


def spheres():
    return [body for body in O.bodies if body is not None and isinstance(body.shape, Sphere)]


def prescribed_cdf(diameter, sizes, cumulative):
    if diameter <= sizes[0]:
        return cumulative[0]
    if diameter >= sizes[-1]:
        return cumulative[-1]
    index = bisect.bisect_right(sizes, diameter) - 1
    fraction = (diameter - sizes[index]) / (sizes[index + 1] - sizes[index])
    return cumulative[index] + fraction * (cumulative[index + 1] - cumulative[index])


def empirical_mass_cdf_error(diameters, sizes, cumulative):
    masses = [value ** 3 for value in diameters]
    total = sum(masses)
    probes = list(sizes)
    for index in range(len(sizes) - 1):
        probes.extend(sizes[index] + (sizes[index + 1] - sizes[index]) * step / 32.0 for step in range(1, 32))
    return max(abs(sum(m for d, m in zip(diameters, masses) if d <= probe) / total -
                   prescribed_cdf(probe, sizes, cumulative)) for probe in probes)


def mass_quantile(diameters, probability):
    ordered = sorted((value, value ** 3) for value in diameters)
    target = probability * sum(mass for _, mass in ordered)
    cumulative = 0.0
    for diameter, mass in ordered:
        cumulative += mass
        if cumulative >= target:
            return diameter
    return ordered[-1][0]


def analytic_number_mean_volume(sizes, cumulative):
    denominator = 0.0
    for lower, upper, f0, f1 in zip(sizes[:-1], sizes[1:], cumulative[:-1], cumulative[1:]):
        slope = (f1 - f0) / (upper - lower)
        denominator += 0.5 * slope * (lower ** -2 - upper ** -2)
    return (math.pi / 6.0) / denominator


def cell_volume():
    return float(O.cell.hSize.determinant())


def maximum_overlap_ratio():
    value = 0.0
    for interaction in O.interactions:
        if not interaction.isReal or interaction.geom is None:
            continue
        first, second = O.bodies[int(interaction.id1)], O.bodies[int(interaction.id2)]
        if isinstance(first.shape, Sphere) and isinstance(second.shape, Sphere):
            value = max(value, max(float(interaction.geom.penetrationDepth), 0.0) /
                        min(float(first.shape.radius), float(second.shape.radius)))
    return value


def contact_network():
    ids = set(int(body.id) for body in spheres())
    edges = set()
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        if first in ids and second in ids:
            edges.add((min(first, second), max(first, second)))
    active = set(ids)
    changed = True
    while changed:
        degrees = dict((body_id, 0) for body_id in active)
        for first, second in edges:
            if first in active and second in active:
                degrees[first] += 1
                degrees[second] += 1
        remove = set(body_id for body_id, degree in degrees.items() if degree < 2)
        changed = bool(remove)
        active.difference_update(remove)
    degrees = dict((body_id, 0) for body_id in active)
    retained_edges = 0
    for first, second in edges:
        if first in active and second in active:
            retained_edges += 1
            degrees[first] += 1
            degrees[second] += 1
    coordination = (2.0 * retained_edges / len(active)) if active else 0.0
    raw_degree = dict((body_id, 0) for body_id in ids)
    for first, second in edges:
        raw_degree[first] += 1
        raw_degree[second] += 1
    return {
        "real_contact_count": len(edges),
        "load_bearing_particle_count_after_degree_lt2_pruning": len(active),
        "rattler_fraction_degree_lt2_iterative": 1.0 - len(active) / float(len(ids)),
        "coordination_excluding_degree_lt2_rattlers": coordination,
        "fraction_with_at_least_three_contacts": sum(1 for value in raw_degree.values() if value >= 3) / float(len(ids)),
    }


def finite_payload(value):
    if isinstance(value, dict):
        return all(finite_payload(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite_payload(item) for item in value)
    if isinstance(value, (float, int)):
        return math.isfinite(float(value))
    return True


def diagnostic(block, triax, solid_volume, target_stress, reference_e):
    volume = cell_volume()
    stress_tension_positive = [float(value) for value in triax.stress]
    compression = [-value for value in stress_tension_positive]
    mean_compression = sum(compression) / 3.0
    unbalanced = float(unbalancedForce())
    unbalanced_defined = math.isfinite(unbalanced)
    if not unbalanced_defined:
        unbalanced = 1.0
    network = contact_network()
    row = {
        "block": int(block),
        "iteration": int(O.iter),
        "time_s": float(O.time),
        "cell_volume_m3": volume,
        "cell_dimensions_m": [float(O.cell.hSize[i, i]) for i in range(3)],
        "void_ratio": volume / solid_volume - 1.0,
        "void_ratio_difference_from_reference": volume / solid_volume - 1.0 - reference_e,
        "principal_effective_stress_pa_compression_positive": compression,
        "mean_effective_stress_pa_compression_positive": mean_compression,
        "relative_mean_stress_error": abs(mean_compression - target_stress) / target_stress,
        "maximum_principal_stress_error": max(abs(value - target_stress) / target_stress for value in compression),
        "unbalanced_force": unbalanced,
        "unbalanced_force_defined": unbalanced_defined,
        "kinetic_energy_j": float(utils.kineticEnergy()),
        "normalized_kinetic_energy_pV": float(utils.kineticEnergy()) / (target_stress * volume),
        "maximum_overlap_over_smaller_radius": maximum_overlap_ratio(),
    }
    row.update(network)
    return row


def gates(row, acceptance, required_count, reference_e):
    return {
        "finite_state": finite_payload(row),
        "unbalanced_force_defined": bool(row["unbalanced_force_defined"]),
        "particle_count_retained": len(spheres()) == required_count,
        "mean_stress": row["relative_mean_stress_error"] <= float(acceptance["maximum_relative_mean_stress_error"]),
        "unbalanced_force": row["unbalanced_force"] <= float(acceptance["maximum_unbalanced_force"]),
        "normalized_kinetic_energy": row["normalized_kinetic_energy_pV"] <= float(acceptance["maximum_normalized_kinetic_energy_pV"]),
        "coordination": row["coordination_excluding_degree_lt2_rattlers"] >= float(acceptance["minimum_coordination_excluding_rattlers"]),
        "rattler_fraction": row["rattler_fraction_degree_lt2_iterative"] <= float(acceptance["maximum_rattler_fraction"]),
        "overlap": row["maximum_overlap_over_smaller_radius"] <= float(acceptance["maximum_overlap_over_smaller_radius"]),
        "void_ratio": abs(row["void_ratio"] - reference_e) <= float(acceptance["maximum_absolute_void_ratio_difference_from_reference"]),
    }


def write_history(path, rows):
    keys = list(rows[0].keys())
    with open(path, "x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["cell_dimensions_m"] = json.dumps(flat["cell_dimensions_m"])
            flat["principal_effective_stress_pa_compression_positive"] = json.dumps(flat["principal_effective_stress_pa_compression_positive"])
            writer.writerow(flat)


def run_case(cfg, friction):
    sand, contacts = cfg["sand"], cfg["contacts"]
    prep, acceptance = cfg["preparation"], cfg["acceptance"]
    reference_e = float(cfg["reference_state"]["void_ratio"])
    target_stress = float(prep["target_mean_effective_stress_pa_compression_positive"])
    count = int(sand["particle_count"])
    case_id = "mu_%0.2f" % friction
    case_dir = os.path.join(OUTPUT_ROOT, case_id)
    os.mkdir(case_dir)

    O.reset()
    O.periodic = True
    sizes = [float(value) for value in sand["psd_diameters_m"]]
    cumulative = [float(value) for value in sand["psd_cumulative_mass_fractions"]]
    nominal_solid = count * analytic_number_mean_volume(sizes, cumulative)
    initial_e = float(prep["initial_void_ratio"])
    initial_length = (nominal_solid * (1.0 + initial_e)) ** (1.0 / 3.0)
    O.cell.hSize = Matrix3(initial_length, 0, 0, 0, initial_length, 0, 0, 0, initial_length)
    material = O.materials.append(FrictMat(
        young=float(contacts["young_pa"]), poisson=float(contacts["poisson"]),
        frictionAngle=math.atan(float(friction)), density=float(sand["density_kg_m3"]),
        label="stage25a_lbs_spheres",
    ))
    cloud = pack.SpherePack()
    cloud.makeCloud(
        Vector3.Zero, Vector3(initial_length, initial_length, initial_length),
        num=count, periodic=True, porosity=initial_e / (1.0 + initial_e),
        psdSizes=sizes, psdCumm=cumulative, distributeMass=bool(sand["distribute_mass"]),
        seed=int(sand["random_seed"]),
    )
    cloud.toSimulation(material=material)
    if len(spheres()) != count:
        raise RuntimeError("unexpected particle count")
    diameters = [2.0 * float(body.shape.radius) for body in spheres()]
    if min(diameters) < sizes[0] or max(diameters) > sizes[-1]:
        raise RuntimeError("realized diameter outside source PSD bounds")
    solid_volume = sum((math.pi / 6.0) * value ** 3 for value in diameters)
    realized_initial_length = (solid_volume * (1.0 + initial_e)) ** (1.0 / 3.0)
    scale = realized_initial_length / initial_length
    for body in spheres():
        body.state.pos = body.state.pos * scale
    O.cell.hSize = Matrix3(realized_initial_length, 0, 0, 0, realized_initial_length, 0, 0, 0, realized_initial_length)

    triax = PeriTriaxController(
        goal=(-target_stress, -target_stress, -target_stress),
        stressMask=7,
        dynCell=True,
        maxStrainRate=tuple(float(prep["maximum_strain_rate_s_inv"]) for _ in range(3)),
        relStressTol=float(acceptance["maximum_relative_mean_stress_error"]),
        maxUnbalanced=float(acceptance["maximum_unbalanced_force"]),
        label="triax",
    )
    O.engines = [
        ForceResetter(),
        InsertionSortCollider([Bo1_Sphere_Aabb()], allowBiggerThanPeriod=True),
        InteractionLoop(
            [Ig2_Sphere_Sphere_ScGeom()],
            [Ip2_FrictMat_FrictMat_FrictPhys()],
            [Law2_ScGeom_FrictPhys_CundallStrack()],
        ),
        GlobalStiffnessTimeStepper(
            active=True, timeStepUpdateInterval=20,
            timestepSafetyCoefficient=float(prep["timestep_safety_coefficient"]),
            label="timeStepper",
        ),
        triax,
        NewtonIntegrator(damping=float(prep["newton_damping"]), gravity=Vector3(*prep["gravity_m_s2"])),
    ]
    O.trackEnergy = True
    O.step()
    history = []
    streak = 0
    passed = False
    final_checks = None
    maximum_blocks = SMOKE_MAX_BLOCKS if SMOKE_MAX_BLOCKS > 0 else int(prep["maximum_check_blocks"])
    for block in range(1, maximum_blocks + 1):
        O.run(int(prep["steps_per_check_block"]), True)
        row = diagnostic(block, triax, solid_volume, target_stress, reference_e)
        history.append(row)
        final_checks = gates(row, acceptance, count, reference_e)
        streak = streak + 1 if all(final_checks.values()) else 0
        if block == 1 or block % 10 == 0 or streak > 0:
            print("STAGE25_PROGRESS=" + json.dumps({
                "case_id": case_id, "block": block, "void_ratio": row["void_ratio"],
                "mean_stress_pa": row["mean_effective_stress_pa_compression_positive"],
                "stress_error": row["relative_mean_stress_error"],
                "unbalanced": row["unbalanced_force"],
                "coordination": row["coordination_excluding_degree_lt2_rattlers"],
                "rattler_fraction": row["rattler_fraction_degree_lt2_iterative"],
                "streak": streak,
            }, sort_keys=True), flush=True)
        if streak >= int(prep["required_consecutive_pass_blocks"]):
            passed = True
            break
        if not final_checks["finite_state"] or row["maximum_overlap_over_smaller_radius"] > 0.05:
            break

    triax.dead = True
    final = history[-1]
    checkpoint = os.path.join(case_dir, "load_bearing_state.yade.gz")
    O.save(checkpoint)
    particles = [{
        "body_id": int(body.id),
        "position_m": [float(body.state.pos[axis]) % float(O.cell.hSize[axis, axis]) for axis in range(3)],
        "radius_m": float(body.shape.radius),
    } for body in spheres()]
    particles.sort(key=lambda item: item["body_id"])
    history_path = os.path.join(case_dir, "history.csv")
    write_history(history_path, history)
    result = {
        "schema": "lbs.stage25a-load-bearing-pure-sand-pilot.v1.case",
        "case_id": case_id,
        "status": "passed_load_bearing_candidate" if passed else "completed_failed_acceptance",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "preparation_friction_coefficient": float(friction),
        "engine": {"yade_version": str(config.version), "features": list(config.features)},
        "source_hashes": {"config": sha256(CONFIG_PATH), "runner": sha256(SCRIPT_PATH)},
        "psd": {
            "minimum_diameter_m": min(diameters), "maximum_diameter_m": max(diameters),
            "D10_m": mass_quantile(diameters, 0.10), "D50_m": mass_quantile(diameters, 0.50),
            "D60_m": mass_quantile(diameters, 0.60),
            "empirical_mass_cdf_maximum_absolute_error": empirical_mass_cdf_error(diameters, sizes, cumulative),
        },
        "terminal": final,
        "checks": final_checks,
        "consecutive_pass_blocks": streak,
        "steps_completed": int(O.iter),
        "particles": particles,
        "artifacts": {
            "checkpoint_sha256": sha256(checkpoint),
            "history_csv_sha256": sha256(history_path),
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    result_path = os.path.join(case_dir, "result.json")
    write_json_exclusive(result_path, result)
    print("STAGE25_CASE=" + json.dumps({
        "case_id": case_id, "passed": passed, "result_sha256": sha256(result_path),
        "void_ratio": final["void_ratio"], "mean_stress_pa": final["mean_effective_stress_pa_compression_positive"],
        "coordination": final["coordination_excluding_degree_lt2_rattlers"],
    }, sort_keys=True), flush=True)
    return result, sha256(result_path)


def main():
    with open(CONFIG_PATH, "r") as stream:
        cfg = json.load(stream)
    if cfg.get("status") != "authorized_bounded_pure_sand_mechanics_qualification":
        raise RuntimeError("Stage25a configuration is not execution-authorized")
    if cfg["promotion"].get("stage25a_execution_authorized") is not True:
        raise RuntimeError("Stage25a execution flag is false")
    if str(config.version) != str(cfg["source"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    for name in ("stage24e_evaluation", "stage23a_primary_preparation"):
        path = windows_to_wsl(cfg["source"][name])
        if sha256(path) != cfg["source"][name + "_sha256"]:
            raise RuntimeError("source hash mismatch: " + name)
        with open(path, "r") as stream:
            source = json.load(stream)
        if source.get("passed") is not True:
            raise RuntimeError("source is not passed: " + name)
    parent = os.path.dirname(OUTPUT_ROOT)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    os.mkdir(OUTPUT_ROOT)
    case_records = {}
    cases = []
    for friction in cfg["contacts"]["preparation_friction_coefficients"]:
        result, result_sha = run_case(cfg, float(friction))
        cases.append(result)
        case_records[result["case_id"]] = result_sha
    passed_ids = [row["case_id"] for row in cases if row["passed"]]
    completion = {
        "schema": "lbs.stage25a-load-bearing-pure-sand-pilot.v1.completion",
        "status": "passed_at_least_one_candidate" if passed_ids else "completed_no_admissible_candidate",
        "passed": bool(passed_ids),
        "smoke_mode": SMOKE_MAX_BLOCKS > 0,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {
            "config": sha256(CONFIG_PATH), "runner": sha256(SCRIPT_PATH),
            "stage24e_evaluation": cfg["source"]["stage24e_evaluation_sha256"],
            "stage23a_primary_preparation": cfg["source"]["stage23a_primary_preparation_sha256"],
        },
        "case_records": case_records,
        "passed_case_ids": passed_ids,
        "cases": [{
            "case_id": row["case_id"], "passed": row["passed"],
            "preparation_friction_coefficient": row["preparation_friction_coefficient"],
            "terminal": row["terminal"], "checks": row["checks"],
        } for row in cases],
        "claim_boundary": cfg["claim_boundary"],
        "promotion": {
            "timestep_and_seed_qualification_authorized": bool(passed_ids),
            "fibre_mechanics_authorized": False,
            "flow_authorized": False,
            "deformation_coupled_flow_authorized": False,
        },
        "wall_seconds": time.time() - START,
    }
    completion_path = os.path.join(OUTPUT_ROOT, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE25_COMPLETION=" + json.dumps({
        "status": completion["status"], "passed_case_ids": passed_ids,
        "completion_sha256": sha256(completion_path), "wall_seconds": completion["wall_seconds"],
    }, sort_keys=True), flush=True)


main()
