"""Side-effect-free diagnostics shared only by the Stage26h pilot runner."""

from __future__ import print_function

import csv
import json
import math

from yade import utils
from yade.minieigenHP import Vector3
from yade.wrapper import Sphere

from stage26b_revision2_prefilter_common_v1 import iterative_core


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
        "fibre_translation_m_by_fibre",
        "fibre_translation_over_D50_by_fibre",
        "fibre_rotation_deg_by_fibre",
    }
    with open(path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for name in json_fields:
                if name in encoded:
                    encoded[name] = json.dumps(encoded[name], separators=(",", ":"))
            writer.writerow(encoded)
