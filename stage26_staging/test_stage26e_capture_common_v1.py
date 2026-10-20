"""Unit tests for the Stage26e online capture event."""

import unittest

from stage26e_capture_common_v1 import advance_equilibrium_streak


GATES = {
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


def passing_row(block):
    return {
        "block": block,
        "distinct_sand_contacts_by_fibre": [2, 2],
        "declared_anchor_contacts_by_fibre": [2, 2],
        "fibre_fibre_real_interaction_count": 0,
        "intraclump_real_interaction_count": 0,
        "relative_mean_stress_error": 0.01,
        "maximum_principal_stress_error": 0.02,
        "unbalanced_force_defined": True,
        "unbalanced_force": 0.04,
        "sand_coordination_excluding_degree_lt2_rattlers": 3.5,
        "sand_rattler_fraction_degree_lt2_iterative": 0.2,
        "sand_sand_contact_retention_fraction": 0.95,
        "maximum_nonaffine_sand_displacement_over_D50": 0.08,
        "cell_volume_relative_drift": 0.004,
        "maximum_interobject_penetration_over_smaller_radius": 0.01,
    }


class CaptureEventTests(unittest.TestCase):
    def test_no_streak_before_minimum_block(self):
        streak, event = advance_equilibrium_streak([50], passing_row(59), 60, 10, GATES)
        self.assertEqual(streak, [])
        self.assertIsNone(event)

    def test_exact_ten_row_event(self):
        streak, event = [], None
        for block in range(60, 70):
            streak, event = advance_equilibrium_streak(streak, passing_row(block), 60, 10, GATES)
        self.assertEqual(event, [60, 69])

    def test_failure_resets_streak(self):
        streak = []
        for block in range(60, 65):
            streak, _ = advance_equilibrium_streak(streak, passing_row(block), 60, 10, GATES)
        failed = passing_row(65)
        failed["unbalanced_force"] = 0.051
        streak, event = advance_equilibrium_streak(streak, failed, 60, 10, GATES)
        self.assertEqual(streak, [])
        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
