import copy
import unittest

from steady_flow_gate_v1 import check_steady_flow


class SteadyFlowGateTests(unittest.TestCase):
    def setUp(self):
        row = {"field_change_relative_l2": 1e-7, "delta_mean_relative": 1e-9,
               "steady_force_balance_relative": 1e-8, "dynamic_momentum_residual_relative": 1e-9,
               "mean_density": 1., "maximum_speed_lu": .002, "fatal_health_code": 0}
        self.regular = [dict(row, step=257*i) for i in range(1, 5)]
        self.adjacent = [dict(row, step=2000+i) for i in range(8)]

    def run_gate(self, **kwargs):
        return check_steady_flow(self.regular, self.adjacent,
                                 export_exact=kwargs.get("export_exact", True),
                                 fatal_health_code=kwargs.get("fatal_health_code", 0))

    def test_stationary_passes(self):
        self.assertTrue(self.run_gate()["passed"])

    def test_old_even_interval_fails(self):
        for i, row in enumerate(self.regular): row["step"] = (i+1)*4000
        self.assertFalse(self.run_gate()["passed"])

    def test_mean_stable_local_cycle_fails(self):
        for row in self.adjacent: row["field_change_relative_l2"] = .17
        self.assertFalse(self.run_gate()["passed"])

    def test_dynamic_balance_does_not_replace_steady_balance(self):
        for row in self.adjacent: row["steady_force_balance_relative"] = .1
        self.assertFalse(self.run_gate()["passed"])

    def test_insufficient_data_fails(self):
        self.adjacent.pop()
        self.assertFalse(self.run_gate()["passed"])

    def test_gapped_steps_fail(self):
        self.adjacent[-1]["step"] += 1
        self.assertFalse(self.run_gate()["passed"])

    def test_missing_nan_and_negative_metrics_fail(self):
        base = copy.deepcopy(self.adjacent)
        for value in [None, float("nan"), -1.]:
            self.adjacent = copy.deepcopy(base)
            self.adjacent[-1]["steady_force_balance_relative"] = value
            self.assertFalse(self.run_gate()["passed"])

    def test_wrong_export_or_health_fails(self):
        self.assertFalse(self.run_gate(export_exact=False)["passed"])
        self.assertFalse(self.run_gate(fatal_health_code=1)["passed"])

    def test_missing_signed_metrics_fail(self):
        self.adjacent[-1]["delta_mean_relative"] = None
        self.assertFalse(self.run_gate()["passed"])
        self.adjacent[-1]["delta_mean_relative"] = 0.
        self.adjacent[-1]["mean_density"] = None
        self.assertFalse(self.run_gate()["passed"])

    def test_density_or_mach_fails(self):
        self.adjacent[-1]["mean_density"] = 1.001
        self.assertFalse(self.run_gate()["passed"])
        self.adjacent[-1]["mean_density"] = 1.
        self.adjacent[-1]["maximum_speed_lu"] = .1
        self.assertFalse(self.run_gate()["passed"])


if __name__ == "__main__":
    unittest.main()
