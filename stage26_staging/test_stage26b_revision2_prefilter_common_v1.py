"""Dependency-free unit tests for Stage26b Revision-2 shared logic."""

import unittest

from stage26b_revision2_prefilter_common_v1 import (
    candidate_contact_pass,
    candidate_rank_key,
    iterative_core,
    sand_terminal_pass,
)


class Revision2CommonTests(unittest.TestCase):
    def test_iterative_degree_two_core_removes_tail(self):
        initial, core, active = iterative_core(
            [1, 2, 3, 4], [(1, 2), (2, 3), (3, 1), (3, 4)], 2
        )
        self.assertEqual(initial, {1: 2, 2: 2, 3: 3, 4: 1})
        self.assertEqual(active, {1, 2, 3})
        self.assertEqual(core, {1: 2, 2: 2, 3: 2, 4: 0})

    def test_contact_gate_requires_persistence_and_terminal_anchors(self):
        gates = {
            "minimum_distinct_sand_contacts_per_fibre_at_every_block": 2,
            "minimum_declared_anchor_contacts_per_fibre_at_every_block": 1,
            "required_declared_anchor_contacts_per_fibre_at_terminal_block": 2,
            "maximum_isolated_fibre_count": 0,
        }
        passing = [
            {"distinct_sand_contacts_by_fibre": [2, 3], "declared_anchor_contacts_by_fibre": [1, 2], "isolated_fibre_count": 0},
            {"distinct_sand_contacts_by_fibre": [2, 2], "declared_anchor_contacts_by_fibre": [2, 2], "isolated_fibre_count": 0},
        ]
        failing = [dict(passing[0]), dict(passing[1])]
        failing[0]["distinct_sand_contacts_by_fibre"] = [1, 3]
        self.assertTrue(candidate_contact_pass(passing, gates))
        self.assertFalse(candidate_contact_pass(failing, gates))

    def test_sand_terminal_gate(self):
        gates = {
            "maximum_relative_mean_stress_error": 0.02,
            "maximum_principal_stress_error": 0.03,
            "maximum_unbalanced_force": 0.05,
            "minimum_sand_coordination_excluding_rattlers": 3.0,
            "maximum_sand_rattler_fraction": 0.35,
            "minimum_sand_contact_retention_fraction": 0.90,
            "maximum_sand_displacement_over_D50": 0.10,
            "maximum_cell_volume_relative_drift": 0.005,
            "maximum_interobject_penetration_over_smaller_radius": 0.02,
        }
        row = {
            "relative_mean_stress_error": 0.01,
            "maximum_principal_stress_error": 0.02,
            "unbalanced_force": 0.04,
            "unbalanced_force_defined": True,
            "sand_coordination_excluding_degree_lt2_rattlers": 3.5,
            "sand_rattler_fraction_degree_lt2_iterative": 0.2,
            "sand_sand_contact_retention_fraction": 0.95,
            "maximum_nonaffine_sand_displacement_over_D50": 0.08,
            "cell_volume_relative_drift": 0.003,
            "maximum_interobject_penetration_over_smaller_radius": 0.01,
        }
        self.assertTrue(sand_terminal_pass(row, gates))
        row["unbalanced_force"] = 0.0500001
        self.assertFalse(sand_terminal_pass(row, gates))

    def test_rank_is_lexicographic_and_deterministic(self):
        base = {
            "minimum_contacts_over_all_fibres_and_blocks": 2,
            "minimum_anchor_degree": 3,
            "maximum_sand_displacement_over_D50": 0.05,
            "maximum_force_residual_relative": 0.04,
            "maximum_moment_residual_relative": 0.01,
            "candidate_index": 2,
        }
        better_contacts = dict(base, minimum_contacts_over_all_fibres_and_blocks=3, candidate_index=12)
        tie_earlier = dict(base, candidate_index=1)
        self.assertLess(candidate_rank_key(better_contacts), candidate_rank_key(base))
        self.assertLess(candidate_rank_key(tie_earlier), candidate_rank_key(base))


if __name__ == "__main__":
    unittest.main()
