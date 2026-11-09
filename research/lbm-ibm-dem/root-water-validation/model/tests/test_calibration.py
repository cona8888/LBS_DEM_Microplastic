import math,unittest
from types import SimpleNamespace
from dataclasses import replace
from calibration.fit import cup_fit,trees,wet
from calibration.tissue import profiles
from calibration.probe_wetting import apparent,state
from applications.rhizofield.field import Mesh,seed
from applications.rhizofield.run import Params,membrane_flux,uptake_rate

class CalibrationTests(unittest.TestCase):
    def test_SI_and_surface_convention(self):
        L=4.3e-14; self.assertAlmostEqual(uptake_rate(L,0.001,0,-20000)*1e12,0.86,places=10)
        self.assertEqual(uptake_rate(L,0,0,-20000),0);self.assertEqual(uptake_rate(L,1,-100,-10),0)
        p=replace(Params(),membrane=L,xylem=-20000);s=SimpleNamespace(psi=0,wet_length=.001)
        self.assertEqual(membrane_flux(s,p),uptake_rate(L,.001,0,-20000))
    def test_cup_geometry_holdout(self):
        p,t=cup_fit();self.assertAlmostEqual(p['lateral']['large_pred_cm3'],5.76);self.assertAlmostEqual(t[1]['area_transfer_large_min'],34/4.8)
    def test_species_date_block_and_missing_value(self):
        p,r=trees();self.assertEqual(len(r),11);self.assertEqual([(k['species'],k['n_train_dates']) for k in p],[('beech',3),('oak',3),('spruce',2)])
        self.assertTrue(all(k['error_pct']>0 for k in p));self.assertAlmostEqual(p[2]['Lp_fit_m_Pa_s']*1e14,2.5)
        self.assertTrue(all(k['date']=='1999-09-09' for k in r if k['split']=='holdout'))
    def test_tissue_conversion_and_pressure_scale(self):
        p=profiles();ratio=p['soaked_24h']['Lp_m_Pa_s']/p['not_soaked']['Lp_m_Pa_s'];self.assertAlmostEqual(ratio,3.5e-7/4.3e-8)
    def test_legacy_and_fitted_angle_are_not_equivalent(self):
        m,s=state(60);self.assertAlmostEqual(apparent(m,s)[0],49.4005,delta=.05)
        m,s=state(52.7772);self.assertAlmostEqual(apparent(m,s)[0],31,delta=.05)
    def test_readout_is_not_allowed_at_altered_gap(self):
        lab,x=seed();m=Mesh(lab,13);s=m.solve(x,m.water(x));self.assertRaises(ValueError,apparent,m,s)
    def test_refuse_invalid_inputs(self):
        for z in [0.,180.,float('nan')]:
            with self.assertRaises(ValueError):replace(Params(),root_deg=z)
        with self.assertRaises(ValueError):uptake_rate(-1,1,0,-10)
