"""Independent limits for the new validation-only refinement controls."""
import unittest
import numpy as np
from applications.rhizofield.field import Mesh,seed,DX,WIDTH,P0
from applications.rhizofield.refine import refined_geometry

class RefinementControls(unittest.TestCase):
    def test_defaults_unchanged(self):
        lab,x=seed();a=Mesh(lab);b=Mesh(lab,interface_width=WIDTH)
        self.assertEqual(a.energy_grad(x)[0],b.energy_grad(x)[0])
        np.testing.assert_array_equal(a.energy_grad(x)[1],b.energy_grad(x)[1])
        self.assertEqual(a.pressure_scale,P0)

    def test_width_scaling_virtual_work(self):
        lab,x=seed();lab,x=refined_geometry(lab,x);m=Mesh(lab,interface_width=1.25)
        s=m.solve(x,m.water(x));eps=.003
        lo=Mesh(lab,12-eps,interface_width=1.25).solve(s.phi,s.water)
        hi=Mesh(lab,12+eps,interface_width=1.25).solve(s.phi,s.water)
        fd=-(hi.energy-lo.energy)/(2*eps)*m.pressure_scale*DX
        self.assertLess(abs(fd/s.force-1),.001)
        self.assertLess(abs(s.water-m.water(x)),1e-8)

    def test_invalid_width_rejected(self):
        lab,_=seed()
        for width in [0.,-1.,np.nan,np.inf]:
            with self.assertRaises(ValueError):Mesh(lab,interface_width=width)

if __name__=='__main__':unittest.main()
