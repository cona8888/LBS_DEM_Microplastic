"""Pure-Python graph, gate, and ranking helpers for Stage26b Revision 2."""

from __future__ import print_function

import hashlib
import json
import math


def sha256(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with open(path, "r") as stream:
        return json.load(stream)


def write_json_exclusive(path, payload):
    with open(path, "x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def windows_to_wsl(path):
    value = str(path).replace("\\", "/")
    if len(value) >= 3 and value[1:3] == ":/":
        return "/mnt/%s/%s" % (value[0].lower(), value[3:])
    return value


def iterative_core(node_ids, undirected_edges, minimum_degree=2):
    """Return initial degrees, retained core degrees, and retained node IDs."""
    nodes = set(int(value) for value in node_ids)
    adjacency = dict((node, set()) for node in nodes)
    for first, second in undirected_edges:
        first, second = int(first), int(second)
        if first == second or first not in nodes or second not in nodes:
            continue
        adjacency[first].add(second)
        adjacency[second].add(first)
    initial_degree = dict((node, len(adjacency[node])) for node in nodes)
    active = set(nodes)
    while True:
        removed = [node for node in active if sum(1 for other in adjacency[node] if other in active) < minimum_degree]
        if not removed:
            break
        active.difference_update(removed)
    core_degree = dict(
        (node, sum(1 for other in adjacency[node] if other in active) if node in active else 0)
        for node in nodes
    )
    return initial_degree, core_degree, active


def all_finite(values):
    return all(math.isfinite(float(value)) for value in values)


def candidate_contact_pass(history, contact_gates):
    if not history:
        return False
    minimum_contacts = int(contact_gates["minimum_distinct_sand_contacts_per_fibre_at_every_block"])
    minimum_anchors = int(contact_gates["minimum_declared_anchor_contacts_per_fibre_at_every_block"])
    terminal_anchors = int(contact_gates["required_declared_anchor_contacts_per_fibre_at_terminal_block"])
    for row in history:
        if min(row["distinct_sand_contacts_by_fibre"]) < minimum_contacts:
            return False
        if min(row["declared_anchor_contacts_by_fibre"]) < minimum_anchors:
            return False
        if int(row["isolated_fibre_count"]) > int(contact_gates["maximum_isolated_fibre_count"]):
            return False
    return min(history[-1]["declared_anchor_contacts_by_fibre"]) >= terminal_anchors


def sand_terminal_pass(row, gates):
    values = [
        row["relative_mean_stress_error"],
        row["maximum_principal_stress_error"],
        row["unbalanced_force"],
        row["sand_coordination_excluding_degree_lt2_rattlers"],
        row["sand_rattler_fraction_degree_lt2_iterative"],
        row["sand_sand_contact_retention_fraction"],
        row["maximum_nonaffine_sand_displacement_over_D50"],
        row["cell_volume_relative_drift"],
        row["maximum_interobject_penetration_over_smaller_radius"],
    ]
    return all_finite(values) and (
        row["relative_mean_stress_error"] <= gates["maximum_relative_mean_stress_error"]
        and row["maximum_principal_stress_error"] <= gates["maximum_principal_stress_error"]
        and row["unbalanced_force_defined"] is True
        and row["unbalanced_force"] <= gates["maximum_unbalanced_force"]
        and row["sand_coordination_excluding_degree_lt2_rattlers"] >= gates["minimum_sand_coordination_excluding_rattlers"]
        and row["sand_rattler_fraction_degree_lt2_iterative"] <= gates["maximum_sand_rattler_fraction"]
        and row["sand_sand_contact_retention_fraction"] >= gates["minimum_sand_contact_retention_fraction"]
        and row["maximum_nonaffine_sand_displacement_over_D50"] <= gates["maximum_sand_displacement_over_D50"]
        and row["cell_volume_relative_drift"] <= gates["maximum_cell_volume_relative_drift"]
        and row["maximum_interobject_penetration_over_smaller_radius"] <= gates["maximum_interobject_penetration_over_smaller_radius"]
    )


def candidate_rank_key(summary):
    """Smaller tuple is better; exact order is frozen in the design contract."""
    return (
        -int(summary["minimum_contacts_over_all_fibres_and_blocks"]),
        -int(summary["minimum_anchor_degree"]),
        float(summary["maximum_sand_displacement_over_D50"]),
        float(summary["maximum_force_residual_relative"]),
        float(summary["maximum_moment_residual_relative"]),
        int(summary["candidate_index"]),
    )
