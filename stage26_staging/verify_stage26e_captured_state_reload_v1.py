"""Reload a Stage26e capture without stepping and independently verify its diagnostic."""

from __future__ import print_function

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(os.environ.get("STAGE26E_RELOAD_SCRIPT", __file__)))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from yade import config, utils

from stage26b_revision2_prefilter_common_v1 import (
    iterative_core,
    load_json,
    sha256,
    write_json_exclusive,
)


START = time.time()


def diagonal_lengths():
    return [float(O.cell.hSize[index, index]) for index in range(3)]


def vector_norm(value):
    return math.sqrt(sum(float(component) ** 2 for component in value))


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


def diagnostic(block, cfg, sand_ids, fibre_members, declared_anchors, initial):
    lengths = diagonal_lengths()
    triax = next(engine for engine in O.engines if isinstance(engine, PeriTriaxController))
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
    anchor_counts = [
        len(contacted[index].intersection(set(declared_anchors[index])))
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


def close_scalar(actual, expected, absolute, relative):
    return math.isclose(float(actual), float(expected), abs_tol=absolute, rel_tol=relative)


def compare_rows(actual, expected, tolerances):
    exact_fields = (
        "block", "iteration", "unbalanced_force_defined", "sand_sand_real_contact_count",
        "sand_load_bearing_particle_count_after_degree_lt2_pruning",
        "distinct_sand_contacts_by_fibre", "contacted_sand_body_ids_by_fibre",
        "declared_anchor_contacts_by_fibre", "minimum_distinct_sand_contacts_per_fibre",
        "minimum_declared_anchor_contacts_per_fibre", "isolated_fibre_count",
        "fibre_fibre_real_interaction_count", "intraclump_real_interaction_count",
    )
    scalar_fields = (
        "time_s", "cell_volume_m3", "cell_volume_relative_drift",
        "mean_effective_stress_pa_compression_positive", "relative_mean_stress_error",
        "maximum_principal_stress_error", "kinetic_energy_j",
        "sand_sand_contact_retention_fraction", "sand_rattler_fraction_degree_lt2_iterative",
        "sand_coordination_excluding_degree_lt2_rattlers",
        "maximum_nonaffine_sand_displacement_m",
        "maximum_nonaffine_sand_displacement_over_D50",
    )
    checks = {}
    for name in exact_fields:
        checks[name] = actual[name] == expected[name]
    for name in scalar_fields:
        checks[name] = close_scalar(
            actual[name], expected[name], tolerances["absolute_scalar"], tolerances["relative_scalar"]
        )
    checks["cell_dimensions_m"] = all(
        abs(float(a) - float(e)) <= tolerances["cell_dimension_absolute_m"]
        for a, e in zip(actual["cell_dimensions_m"], expected["cell_dimensions_m"])
    )
    checks["principal_effective_stress_pa_compression_positive"] = all(
        close_scalar(a, e, tolerances["absolute_scalar"], tolerances["relative_scalar"])
        for a, e in zip(
            actual["principal_effective_stress_pa_compression_positive"],
            expected["principal_effective_stress_pa_compression_positive"],
        )
    )
    return checks


def main():
    config_path = os.path.abspath(os.environ["STAGE26E_RELOAD_CONFIG"])
    state_path = os.path.abspath(os.environ["STAGE26E_RELOAD_STATE"])
    capture_result_path = os.path.abspath(os.environ["STAGE26E_RELOAD_CAPTURE_RESULT"])
    capture_completion_path = os.path.abspath(os.environ["STAGE26E_RELOAD_CAPTURE_COMPLETION"])
    output = os.path.abspath(os.environ["STAGE26E_RELOAD_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26E_RELOAD_SCRIPT", __file__))
    if os.path.exists(output):
        raise RuntimeError("immutable reload output already exists")
    os.makedirs(output)
    cfg = load_json(config_path)
    result = load_json(capture_result_path)
    completion = load_json(capture_completion_path)
    if str(config.version) != str(cfg["sources"]["expected_yade_version"]):
        raise RuntimeError("unexpected YADE version")
    if completion.get("passed") is not True or completion["authority"]["reload_verification_authorized"] is not True:
        raise RuntimeError("capture completion does not authorize reload verification")
    if result.get("qualified_fixed_state_captured") is not True:
        raise RuntimeError("capture did not publish a qualified state")
    if completion["result_sha256"] != sha256(capture_result_path):
        raise RuntimeError("completion/result binding mismatch")
    if result["artifacts"]["state_sha256"] != completion["state_sha256"] or sha256(state_path) != completion["state_sha256"]:
        raise RuntimeError("state binding mismatch")
    if result["source_hashes"]["config"] != sha256(config_path):
        raise RuntimeError("capture result/config binding mismatch")

    before_hash = sha256(state_path)
    O.load(state_path)
    try:
        metadata_text = O.tags["stage26e_capture_metadata_json"]
    except Exception as error:
        raise RuntimeError("captured state metadata is missing: " + str(error))
    metadata = json.loads(metadata_text)
    if metadata["config_sha256"] != sha256(config_path):
        raise RuntimeError("state metadata/config binding mismatch")
    if metadata["trial_id"] != result["trial"]["trial_id"]:
        raise RuntimeError("state metadata/trial mismatch")
    if metadata["captured_window"] != result["captured_window"]:
        raise RuntimeError("state metadata/window mismatch")
    actual = diagnostic(
        metadata["capture_row"]["block"], cfg, metadata["sand_ids"], metadata["fibre_members"],
        metadata["declared_anchors"], metadata["initial"],
    )
    checks = compare_rows(actual, metadata["capture_row"], cfg["reload_equivalence_tolerances"])
    checks["metadata_capture_row_matches_result"] = metadata["capture_row"] == result["capture_row"]
    checks["all_fibre_parents_fully_fixed"] = all(
        O.bodies[int(body_id)].state.blockedDOFs == "xyzXYZ" for body_id in metadata["fibre_parents"]
    )
    checks["zero_integration_steps"] = int(O.iter) == int(metadata["capture_row"]["iteration"])
    checks["state_hash_unchanged_by_reload"] = sha256(state_path) == before_hash
    checks["capture_time_unbalanced_force_passed_gate"] = (
        metadata["capture_row"]["unbalanced_force"]
        <= cfg["equilibrium_window_gates"]["maximum_unbalanced_force"]
    )
    checks["capture_time_penetration_passed_gate"] = (
        metadata["capture_row"]["maximum_interobject_penetration_over_smaller_radius"]
        <= cfg["equilibrium_window_gates"]["maximum_interobject_penetration_over_smaller_radius"]
    )
    checks["zero_step_unbalanced_force_cache_signature"] = actual["unbalanced_force"] == 0.0
    checks["zero_step_penetration_cache_signature"] = (
        actual["maximum_interobject_penetration_over_smaller_radius"] == 0.0
    )
    passed = all(checks.values())
    verification = {
        "schema": "lbs.stage26e-captured-state-reload-verification.v1",
        "passed": passed,
        "status": "structural_reload_equivalent_known_derived_caches_unserialized" if passed else "reload_equivalence_failed",
        "checks": checks,
        "captured_row": metadata["capture_row"],
        "reloaded_row": actual,
        "bindings": {
            "config_sha256": sha256(config_path),
            "capture_result_sha256": sha256(capture_result_path),
            "capture_completion_sha256": sha256(capture_completion_path),
            "state_sha256": before_hash,
            "reload_verifier_sha256": sha256(script_path),
        },
        "authority": {
            "development_capture_bundle_acceptance_authorized": passed,
            "heldout_capture_execution_authorized": False,
            "fixed_fibre_rehydration_design_authorized": passed,
            "free_release_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": "Zero-step structural reload verification of one fixed-fibre development state. YADE runtime force and penetration caches are explicitly excluded and must be rebuilt under a future fixed-fibre rehydration qualification; no release, promoted state, or flow.",
    }
    verification_path = os.path.join(output, "reload_verification.json")
    write_json_exclusive(verification_path, verification)
    reload_completion = {
        "schema": "lbs.stage26e-captured-state-reload-completion.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": verification["status"],
        "verification_sha256": sha256(verification_path),
        "wall_seconds": time.time() - START,
        "authority": verification["authority"],
        "claim_boundary": verification["claim_boundary"],
    }
    write_json_exclusive(os.path.join(output, "completion.json"), reload_completion)
    print("STAGE26E_RELOAD_COMPLETION=" + json.dumps({
        "passed": passed,
        "verification_sha256": sha256(verification_path),
        "failed_checks": sorted(name for name, value in checks.items() if not value),
    }, sort_keys=True), flush=True)
    if not passed:
        raise RuntimeError("captured state reload equivalence failed")


def failure_record(error):
    output = os.environ.get("STAGE26E_RELOAD_OUTPUT")
    if not output:
        return
    output = os.path.abspath(output)
    if os.path.isdir(output) and not os.path.exists(os.path.join(output, "failure.json")):
        write_json_exclusive(os.path.join(output, "failure.json"), {
            "schema": "lbs.stage26e-captured-state-reload-failure.v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
        })


try:
    main()
except Exception as error:
    failure_record(error)
    raise
