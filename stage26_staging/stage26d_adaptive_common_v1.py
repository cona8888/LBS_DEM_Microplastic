"""Pure-Python Stage26d engagement and consecutive-equilibrium-window logic."""

from stage26b_revision2_prefilter_common_v1 import all_finite


def row_sand_health_pass(row, gates):
    names = (
        "relative_mean_stress_error", "maximum_principal_stress_error", "unbalanced_force",
        "sand_coordination_excluding_degree_lt2_rattlers", "sand_rattler_fraction_degree_lt2_iterative",
        "sand_sand_contact_retention_fraction", "maximum_nonaffine_sand_displacement_over_D50",
        "cell_volume_relative_drift", "maximum_interobject_penetration_over_smaller_radius",
    )
    return all_finite(row[name] for name in names) and (
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


def continuous_engagement_pass(history, gates):
    return bool(history) and all(
        min(row["distinct_sand_contacts_by_fibre"]) >= gates["minimum_distinct_sand_contacts_per_fibre_at_every_block"]
        and min(row["declared_anchor_contacts_by_fibre"]) >= gates["minimum_declared_anchor_contacts_per_fibre_at_every_block"]
        and row["isolated_fibre_count"] <= gates["maximum_isolated_fibre_count_at_every_block"]
        for row in history
    )


def row_equilibrium_pass(row, gates):
    return (
        min(row["distinct_sand_contacts_by_fibre"]) >= gates["minimum_distinct_sand_contacts_per_fibre"]
        and min(row["declared_anchor_contacts_by_fibre"]) >= gates["minimum_declared_anchor_contacts_per_fibre"]
        and row["fibre_fibre_real_interaction_count"] <= gates["maximum_fibre_fibre_real_interaction_count"]
        and row["intraclump_real_interaction_count"] <= gates["maximum_intraclump_real_interaction_count"]
        and row_sand_health_pass(row, gates)
    )


def earliest_consecutive_window(history, minimum_block, required_consecutive, gates):
    streak = []
    for row in history:
        if row["block"] < minimum_block:
            continue
        if row_equilibrium_pass(row, gates):
            streak.append(row["block"])
            if len(streak) == required_consecutive:
                return [streak[0], streak[-1]]
        else:
            streak = []
    return None
