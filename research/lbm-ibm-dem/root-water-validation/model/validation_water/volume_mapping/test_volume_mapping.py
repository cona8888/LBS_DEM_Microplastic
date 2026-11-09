"""Independent numerical checks for the bridge-area diagnostic."""
import unittest
import numpy as np

from volume_mapping import geometric_area, positive_fraction


class TestLiquidArea(unittest.TestCase):
    def test_fraction_closed_form(self):
        # Unit side, x+y>0 selects half; x+y>0.5 selects a 0.5-by-0.5 triangle.
        np.testing.assert_allclose(positive_fraction(np.array([0.,-.5,.5]), .5, .5),
                                   [.5,.125,.875],atol=1.e-14)
        np.testing.assert_allclose(positive_fraction(np.array([0.,-.25,.25]), .5, 0.),
                                   [.5,.25,.75],atol=1.e-14)

    def test_plane_cut_in_stretched_cells(self):
        xe = np.array([0.,.11,.31,.56,.62,1.])
        ye = np.array([0.,.12,.6,.71,.93,1.])
        x,y=np.meshgrid((xe[:-1]+xe[1:])/2,(ye[:-1]+ye[1:])/2)
        np.testing.assert_allclose(geometric_area(x+y-1.2,xe,ye),.8*.8/2,atol=1.e-14)
        # Missing top-right cell is entirely liquid.
        phi=x+y-1.2
        phi[-1,-1]=np.nan
        np.testing.assert_allclose(geometric_area(phi,xe,ye),.8*.8/2-.38*.07,atol=1.e-14)

    def test_curved_contour_refinement(self):
        errors=[]
        for n in (32,64,128):
            edge=np.linspace(0.,1.,n+1)
            x,y=np.meshgrid((edge[:-1]+edge[1:])/2,(edge[:-1]+edge[1:])/2)
            # Centre deliberately off-grid; zero set is a circle for all W.
            phi=np.tanh((.272-np.hypot(x-.508,y-.484))/.074)
            errors.append(abs(geometric_area(phi,edge,edge)-np.pi*.272**2))
        self.assertLess(errors[-1],1.e-4)
        self.assertLess(errors[-1],.18*errors[0])


if __name__=='__main__':
    unittest.main()
