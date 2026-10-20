"""Read-only evaluator regressions using a bound completed reference record."""
import copy
import unittest

import evaluate_corrected_diagnostics_v1 as evaluation

api=evaluation.api


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design=api.read(api.DESIGN)
        api.verify_design(cls.design)
        cls.spec=cls.design["cases"][0]
        path=api.ROOT/"stage115_runs/corrected_flow_short_time_20260915/diagnostic_01"/cls.spec["case_id"]/"record.json"
        cls.record=api.read(path)
        if api.sha(path)!=api.read(path.parent/"completion.json")["record_sha256"]:
            raise RuntimeError("test fixture digest drift")

    def test_completed_reference_health(self):
        self.assertTrue(evaluation.independent_health(self.record["result"],self.spec)["passed"])

    def test_contact_failure_not_hidden(self):
        result=copy.deepcopy(self.record["result"])
        result["max_contact_residual"]=1.01e-10
        self.assertFalse(evaluation.independent_health(result,self.spec)["passed"])

    def test_nonfinite_residual_not_hidden(self):
        result=copy.deepcopy(self.record["result"])
        result["max_force_residual"]=float("nan")
        self.assertFalse(evaluation.independent_health(result,self.spec)["passed"])

    def test_incomplete_cannot_claim_horizon(self):
        result=copy.deepcopy(self.record["result"])
        result["time_s"]-=.01
        self.assertFalse(evaluation.independent_health(result,self.spec)["checks"]["horizon_status"])

    def test_time_outside_query_is_rejected(self):
        result=copy.deepcopy(self.record["result"])
        result.update(status="incomplete_budget",time_s=1.)
        self.assertFalse(evaluation.independent_health(result,self.spec)["checks"]["time_inside_horizon"])

    def test_absorbing_dwell_is_rejected(self):
        result=copy.deepcopy(self.record["result"])
        result["dwell_is_absorbing"]=True
        self.assertFalse(evaluation.independent_health(result,self.spec)["passed"])

    def test_outlet_label_uses_whole_body(self):
        result=copy.deepcopy(self.record["result"])
        result["status"]="full_window_exit"
        self.assertFalse(evaluation.independent_health(result,self.spec)["checks"]["whole_body_outlet_status"])

    def test_sphere_orientation_does_not_create_error(self):
        other=copy.deepcopy(self.record)
        other["result"]["orientation"]=[0.,1.,0.]
        self.assertEqual(evaluation.difference(self.record,other,self.spec)["apolar_axis_angle_rad"],0.)

    def test_position_normalized_by_minor_radius(self):
        other=copy.deepcopy(self.record)
        other["result"]["position_m"][0]+=.02*self.spec["config"]["prolate_semiaxes_m"][1]
        self.assertAlmostEqual(evaluation.difference(self.record,other,self.spec)["position_difference_over_b"],.02,places=12)

    def test_fibre_is_apolar(self):
        spec=copy.deepcopy(self.spec);spec["shape"]="rigid_prolate_ar4"
        other=copy.deepcopy(self.record)
        other["result"]["orientation"]=[-v for v in self.record["result"]["orientation"]]
        self.assertLess(evaluation.difference(self.record,other,spec)["apolar_axis_angle_rad"],1e-7)

    def test_analytical_outlet_cases(self):
        result=evaluation.exit_benchmarks()
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["rows"]),13)


if __name__=="__main__":
    unittest.main(verbosity=2)
