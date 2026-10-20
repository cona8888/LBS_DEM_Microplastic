"""CPU-only dispatch, units, refinements, binding and health tests."""
import copy
import unittest

import corrected_transport_v1 as api


class Capture:
    @staticmethod
    def integrate(*args,**kwargs):
        return args,kwargs


class CorrectedTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=api.prepare_spec(2,1.,2,"rigid_prolate_ar4",1.)

    def test_achieved_flow_not_nominal(self):
        s=self.spec
        self.assertEqual(s["config"]["target_mean_interstitial_velocity_m_s"],s["field_metadata"]["achieved_mean_interstitial_velocity_m_s"])
        self.assertNotEqual(s["nominal_speed_m_s"],s["config"]["target_mean_interstitial_velocity_m_s"])

    def test_pv_convention(self):
        s=self.spec
        self.assertEqual(s["horizon_pv"],s["horizon_s"]*s["field_metadata"]["pv_per_second"])
        self.assertAlmostEqual(s["field_metadata"]["two_pore_volume_horizon_s"]*s["field_metadata"]["pv_per_second"],2)

    def test_initial_iid_sentinel_unchanged(self):
        self.assertEqual(self.spec["sample_id"],0)
        starts=api.read(api.ROOT/"stage95_designs/common_admissible_population_01/starts_s2.json")
        self.assertEqual(self.spec["initial_state"]["position_m"],starts[0]["position_m"])

    def test_dispatch_all_controls_and_physics(self):
        marker1,marker2=object(),object()
        a,k=api.dispatch(Capture,self.spec,marker1,marker2,wall_budget=10)
        self.assertIs(a[0],marker1)
        self.assertIs(a[1],marker2)
        self.assertEqual(a[5:10],(.0002,.00005,.001002,1380.,998.2))
        self.assertEqual(a[10],[0.,0.,-9.80665])
        self.assertEqual(a[11],.3)
        self.assertEqual(a[-1],.25)
        self.assertEqual(k["added_mass_fraction"],1.)
        self.assertEqual(k["cutoff_ratio"],.2)
        self.assertEqual(k["roughness_ratio"],.01)
        self.assertFalse(k["stop_on_trap"])
        self.assertEqual(k["trap_reference_speed"],self.spec["field_metadata"]["achieved_mean_interstitial_velocity_m_s"])

    def test_refinement_changes_all_dt_controls_only(self):
        refined=api.prepare_spec(2,1.,2,"rigid_prolate_ar4",.25)
        cfg=copy.deepcopy(refined["config"])
        for name in api.DT_CONTROLS:
            self.assertEqual(cfg["numerics"][name],self.spec["config"]["numerics"][name]/4)
            cfg["numerics"][name]*=4
        self.assertEqual(cfg,self.spec["config"])

    def test_sphere_volume_and_paired_start(self):
        sphere=api.prepare_spec(2,1.,2,"equal_volume_sphere",1.)
        r=sphere["config"]["prolate_semiaxes_m"][0]
        self.assertAlmostEqual(r**3/(.0002*.00005**2),1,places=12)
        self.assertEqual(sphere["initial_state"],self.spec["initial_state"])

    def test_unsupported_flow_refinement_horizon_rejected(self):
        for args in [(1,.5,2,"rigid_prolate_ar4",1.,.25),(2,1.,2,"rigid_prolate_ar4",.1,.25),(2,1.,2,"rigid_prolate_ar4",1.,1000)]:
            with self.assertRaises(RuntimeError):api.prepare_spec(*args)

    def test_budget_guard(self):
        with self.assertRaises(RuntimeError):api.execute(self.spec,"unused",46)

    def test_case_ids_unique(self):
        ids=[api.case_id(s,f,c,shape,r) for s,f,c in api.FLOW_COMBINATIONS for shape in api.SHAPES for r in api.REFINEMENTS]
        self.assertEqual(len(set(ids)),36)

    def test_hash_survives_json_roundtrip(self):
        value={"x":api.np.array([1.,2.]),"bad_initial_gap":float("inf")}
        self.assertEqual(api.digest(value),api.digest(api.normalized(value)))

    def test_health_gate_rejects_bad_contact_and_nan(self):
        r={"position_m":[0.,0.,0.],"orientation":[1.,0.,0.],"velocity_generalized":[0.]*6,
           "minimum_gap_m":0.,"max_contact_residual":0.,"max_force_residual":0.,"max_momentum_residual":0.,"max_reynolds":1.,
           "dwell_is_absorbing":False,"time_s":.25}
        self.assertTrue(api.health(r,self.spec)["passed"])
        for key,value in [("max_contact_residual",1.1e-10),("max_force_residual",float("nan")),("minimum_gap_m",-1e-8)]:
            bad=copy.deepcopy(r);bad[key]=value
            self.assertFalse(api.health(bad,self.spec)["passed"])


if __name__=="__main__":unittest.main(verbosity=2)
