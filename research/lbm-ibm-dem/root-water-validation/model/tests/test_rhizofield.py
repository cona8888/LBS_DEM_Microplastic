"""Analytical, independent-discretisation, legacy, native and coupling checks."""
import csv
from dataclasses import replace
import subprocess
import unittest

import numpy as np
from applications.rhizofield.field import DX, P0, Mesh, seed, HERE
from applications.rhizofield.run import (Params, connected, membrane_flux, native,
                                          paired, water_exchange)


class FieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.labels, x = seed()
        cls.mesh = Mesh(cls.labels)
        cls.s = cls.mesh.solve(x, cls.mesh.water(x))

    def test_energy_gradient(self):
        m, x = self.mesh, self.s.phi
        d = np.random.default_rng(128).normal(size=len(x))
        y = x + .01*d
        h = 1e-5
        fd = (m.energy_grad(y+h*d)[0]-m.energy_grad(y-h*d)[0])/(2*h)
        self.assertAlmostEqual(fd, m.energy_grad(y)[1]@d, delta=3e-5)

    def test_force_is_fixed_water_energy_derivative(self):
        h = .003
        a,b = [Mesh(self.labels,12+q*h).solve(self.s.phi,self.s.water) for q in (-1,1)]
        fd = -(b.energy-a.energy)/(2*h)*P0*DX
        self.assertAlmostEqual(fd,self.s.force,delta=.00015*abs(fd))

    def test_chemical_potential_is_storage_derivative(self):
        h=.06
        a,b = [self.mesh.solve(self.s.phi,self.s.water+q*h) for q in (-1,1)]
        self.assertAlmostEqual((b.energy-a.energy)/(2*h), 2*self.s.mu, delta=1e-6)
        self.assertLess(self.s.psi,0.)

    def test_rigid_geometry_and_pore_area(self):
        for gap in (9.,11.,15.9):
            m=Mesh(self.labels,gap)
            self.assertAlmostEqual(sum(m.V),sum(self.mesh.V),places=8)
            self.assertAlmostEqual(m.root.sum(),self.mesh.root.sum(),places=8)
            self.assertAlmostEqual(m.wall.sum(),self.mesh.wall.sum(),places=8)
            self.assertGreater(m.V.min(),0.)

    def test_legacy_grain_contour_and_action_reaction(self):
        m,s=self.mesh,self.s
        grain=np.mean([m.contour(s,k,1) for k in (2,3,4,5)])
        root=np.mean([m.contour(s,k,2) for k in (2,3,4,5)])
        with (HERE/'seed/pore_traction.csv').open() as f:
            ref=next(float(r['Fx_star'])*P0*DX for r in csv.DictReader(f)
                     if r['gap_star']=='12' and r['body_id']=='1')
        self.assertLess(abs(grain/ref-1),.001)
        self.assertLess(abs(grain+root)/abs(grain),.005)
        self.assertLess(abs(s.force/grain-1),.025)
        self.assertTrue(connected(m,s))

    def test_uniform_gas_no_attraction_or_uptake(self):
        m=self.mesh;s=m.solve(-np.ones_like(self.s.phi),0.)
        self.assertLess(abs(s.force),1e-12)
        self.assertLess(abs(m.contour(s)),1e-12)
        self.assertEqual(membrane_flux(s,Params()),0.)
        self.assertFalse(connected(m,s))

    def test_wetted_membrane_pressure_gate(self):
        p=Params();s=self.s
        self.assertGreater(membrane_flux(s,p),0.)
        self.assertEqual(membrane_flux(s,replace(p,xylem=s.psi+1)),0.)
        self.assertEqual(membrane_flux(replace(s,wet_length=0),p),0.)
        self.assertEqual(membrane_flux(s,replace(p,membrane=0)),0.)

    def test_invalid_mesh_and_phase_fail_closed(self):
        for g in (8,17,np.nan):
            with self.assertRaises(ValueError): Mesh(self.labels,g)
        with self.assertRaises(ValueError): self.mesh.solve(self.s.phi,-1.)
        with self.assertRaises(ValueError): self.mesh.solve(self.s.phi[:2],1.)


class CouplingTests(unittest.TestCase):
    def test_native_mechanical_oracle(self):
        k=2500.;f=-.14;anchor=.00077
        g,res,n=native(.00066,anchor,f,k)
        self.assertAlmostEqual(g,anchor+f/k,delta=1e-12)
        self.assertLess(abs(res),2.1e-10);self.assertGreater(n,1)
        self.assertEqual(native(anchor,anchor,0,k),(anchor,0.,0))

    def test_native_rejects_contact_or_nonfinite_input(self):
        with self.assertRaises(subprocess.CalledProcessError): native(.0006,.00065,-2.,2500.)
        with self.assertRaises(subprocess.CalledProcessError): native(float('nan'),.00065,0,2500.)

    def test_water_ledger_and_no_overspend(self):
        near,far,qr,qo,dt=2e-7,2e-6,3e-11,5e-12,120.
        for q in (-2e-11,2e-11,0):
            a,b=water_exchange(near,far,q,qr,qo,dt)
            self.assertAlmostEqual(a+b+(qr+qo)*dt,near+far,delta=1e-21)
        for args in [(1.,1.,0.,2.,0.,1.),(np.nan,1.,0.,0.,0.,1.),(1.,1.,0.,-1.,0.,1.)]:
            with self.assertRaises(ValueError):water_exchange(*args)

    def test_matched_extraction_at_every_step(self):
        rows,_=paired(steps=3,nopen=2,p=Params(duration=900.,opening=50e-6))
        a,b,c=([r for r in rows if r['mode']==mode] for mode in ('root','outer','sealed'))
        for ra,rb,rc in zip(a,b,c):
            self.assertEqual(ra['uptake_m2'],rb['outer_drain_m2'])
            self.assertEqual(rc['uptake_m2']+rc['outer_drain_m2'],0.)
            self.assertAlmostEqual(ra['near_water_m2']+ra['outer_water_m2'],rb['near_water_m2']+rb['outer_water_m2'],delta=1e-19)
            for r in (ra,rb,rc):
                self.assertLess(abs(r['net_water_residual_m2']),1e-18)
                self.assertLess(abs(r['force_residual_N_m']),1.1e-7)
        self.assertLess(a[-1]['near_water_m2'],b[-1]['near_water_m2'])
        self.assertGreater(a[-1]['grain_capillary_N_m'],b[-1]['grain_capillary_N_m'])

    def test_identical_boundary_conditions_are_identical(self):
        rows,_=paired(steps=1,nopen=1,p=Params(membrane=0.,duration=1.,opening=0.))
        a,b,c=([r for r in rows if r['mode']==mode][-1] for mode in ('root','outer','sealed'))
        for key in ('grain_capillary_N_m','near_water_m2','outer_water_m2','wet_perimeter_m'):
            self.assertEqual(a[key],b[key]); self.assertEqual(a[key],c[key])

if __name__=='__main__': unittest.main()
