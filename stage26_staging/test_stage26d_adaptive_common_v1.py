"""Dependency-free tests for Stage26d consecutive-window semantics."""

from stage26d_adaptive_common_v1 import continuous_engagement_pass, earliest_consecutive_window


ENGAGEMENT = {
    "minimum_distinct_sand_contacts_per_fibre_at_every_block": 1,
    "minimum_declared_anchor_contacts_per_fibre_at_every_block": 1,
    "maximum_isolated_fibre_count_at_every_block": 0,
}
GATE = {
    "minimum_distinct_sand_contacts_per_fibre": 2,
    "minimum_declared_anchor_contacts_per_fibre": 2,
    "maximum_relative_mean_stress_error": 0.02,
    "maximum_principal_stress_error": 0.03,
    "maximum_unbalanced_force": 0.05,
    "minimum_sand_coordination_excluding_rattlers": 3.0,
    "maximum_sand_rattler_fraction": 0.35,
    "minimum_sand_contact_retention_fraction": 0.9,
    "maximum_sand_displacement_over_D50": 0.1,
    "maximum_cell_volume_relative_drift": 0.005,
    "maximum_interobject_penetration_over_smaller_radius": 0.02,
    "maximum_fibre_fibre_real_interaction_count": 0,
    "maximum_intraclump_real_interaction_count": 0,
}


def row(block, good=True, contacts=2):
    return {
        "block": block,
        "distinct_sand_contacts_by_fibre": [contacts, contacts],
        "declared_anchor_contacts_by_fibre": [contacts, contacts],
        "isolated_fibre_count": 0 if contacts else 2,
        "relative_mean_stress_error": 0.01 if good else 0.03,
        "maximum_principal_stress_error": 0.02,
        "unbalanced_force_defined": True,
        "unbalanced_force": 0.04,
        "sand_coordination_excluding_degree_lt2_rattlers": 4.0,
        "sand_rattler_fraction_degree_lt2_iterative": 0.2,
        "sand_sand_contact_retention_fraction": 0.95,
        "maximum_nonaffine_sand_displacement_over_D50": 0.08,
        "cell_volume_relative_drift": 0.001,
        "maximum_interobject_penetration_over_smaller_radius": 0.001,
        "fibre_fibre_real_interaction_count": 0,
        "intraclump_real_interaction_count": 0,
    }


def main():
    history = [row(block, good=block >= 65) for block in range(1, 101)]
    assert continuous_engagement_pass(history, ENGAGEMENT)
    assert earliest_consecutive_window(history, 60, 10, GATE) == [65, 74]
    history[70] = row(71, good=False)
    assert earliest_consecutive_window(history, 60, 10, GATE) == [72, 81]
    history[20] = row(21, contacts=0)
    assert not continuous_engagement_pass(history, ENGAGEMENT)
    short = [row(block, good=block >= 95) for block in range(1, 101)]
    assert earliest_consecutive_window(short, 60, 10, GATE) is None
    print("stage26d adaptive common tests passed")


if __name__ == "__main__":
    main()
