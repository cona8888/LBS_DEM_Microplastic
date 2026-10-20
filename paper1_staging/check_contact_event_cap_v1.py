"""Stdlib analytical/mock controls, NOT native DEM or trajectory qualification."""
from fractions import Fraction
from pathlib import Path
import ast
import copy
import math
import sys
import unittest

import contact_event_cap_v1 as candidate


# Literal operands at the failed SAME origin (not a replay or accepted seed).
# Source raw SHA c2552e0f3a0ed1a3daa2633ad342510aadec41aea8da0e9734096d1f8cd3796e.
SAVED = dict(time_s=.153581974378983, a=.0002, U=4.998299591081698e-5,
    q=[4.1230758739687625e-5,.0008995494415110137,-.0036452523104887787,
       -.0003198855226296632,-.0005567348768461245,-.0004476685929397495],
    position_m=[.004367093739704847,.0024665409880105095,.0041757695576120635],
    director=[.08122330202233566,.5688963943366095,-.8183884577139352],
    near=[
        [3,6.270235631586666e-5,[.9270096872555822,.11300891319954458,.35760596369714737],
         [-3.1849020022801836e-5,5.13212443836069e-5,-9.620092166730013e-5]],
        [15,5.728924279413405e-16,[-.6231560887683403,.7318273818271269,.27587165899924737],
         [1.9897599500674458e-5,-8.466655532789626e-5,6.339274563621167e-5]],
        [83,9.818664511012081e-5,[-.7487895928295701,-.6626138018372636,-.016034191120672014],
         [3.2890332771303614e-5,.00011134439397291176,-.00013499773234224865]]])
H_AT_F0P0625 = 3.886081611883874e-8
MINIMUM = 1e-14


def select(H=1., near=None, q=None, U=1., epsilon=.01, minimum=1e-14, t=0.):
    return candidate.select(H, [[15,.1,[1.,0.,0.],[0.,0.,0.]]] if near is None else near,
        [-1.,0.,0.,0.,0.,0.] if q is None else q, 1., U, epsilon, minimum, t)


def signorini(g, u, h):
    """Exact scalar closed-form backward-Euler Signorini map, no solver call."""
    new_u = max(u, -g/h)
    return g+h*new_u, new_u


def closed_form_defect(g, v, h):
    tau = g/v
    if h <= tau:
        return 0*h
    if h < 2*tau:
        return v-g/h
    return g/h


class EventCapControls(unittest.TestCase):
    def test_exact_scalar_piecewise_map_explains_nonmonotone_halving(self):
        g, v = Fraction(1), Fraction(1)
        for h in (Fraction(1,4),Fraction(1,2),Fraction(1),Fraction(3,2),Fraction(2),Fraction(3),Fraction(10)):
            coarse = signorini(g,-v,h)
            first = signorini(g,-v,h/2)
            fine = signorini(*first,h/2)
            self.assertEqual(abs(coarse[1]-fine[1]),closed_form_defect(g,v,h))
        self.assertLess(closed_form_defect(g,v,Fraction(10)),closed_form_defect(g,v,Fraction(5)))
        self.assertEqual(closed_form_defect(g,v,Fraction(1)),0)

    def test_fixed_release_half_same_saved_origin_all_three_levels(self):
        original = copy.deepcopy(SAVED)
        results = []
        for factor in (.125,.0625,.03125):
            # Homogeneous-cap proxy inputs, not a new native own-cap evaluation.
            # ALL other physical operands and the actual frozen minima agree.
            H = H_AT_F0P0625*(factor/.0625)
            epsilon = 5e-5*(factor/.125)**2
            near = copy.deepcopy(SAVED['near']);t=SAVED['time_s'];count=0;half_intervals=[]
            while True:
                h,w = candidate.select(H,near,SAVED['q'],SAVED['a'],SAVED['U'],epsilon,MINIMUM,t)
                c = next(x for x in w['passes'][0]['contact_witnesses'] if x['grain_id']==15)['closing_m_s']
                self.assertGreater(c,0.)
                if h == H:
                    g=near[1][1]
                    self.assertLessEqual(g/(SAVED['U']*H),epsilon/2)
                    self.assertLessEqual(closed_form_defect(g,c,H)/SAVED['U'],epsilon/2)
                    break
                self.assertGreaterEqual(h,MINIMUM)
                half_intervals.extend((w['literal_clock']['first_interval_s'],w['literal_clock']['second_interval_s']))
                g=near[1][1]
                coarse=signorini(g,-c,h);first=signorini(g,-c,h/2);fine=signorini(*first,h/2)
                self.assertEqual(coarse[1],-c);self.assertEqual(fine[1],-c)
                self.assertAlmostEqual(fine[0]/g,.5,places=14)
                near[1][1]=fine[0];t=w['literal_clock']['end_time_s'];count+=1
                self.assertLess(count,20)
            self.assertGreaterEqual(min(half_intervals),MINIMUM)
            results.append(count)
        self.assertEqual(results,[3,6,9])
        self.assertEqual(SAVED,original)

    def test_original_operands_and_immutable_policy_are_not_modified(self):
        value=copy.deepcopy(SAVED);before=copy.deepcopy(value)
        h,w=candidate.select(H_AT_F0P0625,value['near'],value['q'],value['a'],value['U'],1.25e-5,MINIMUM,value['time_s'])
        self.assertEqual(value,before);self.assertLessEqual(h,H_AT_F0P0625)
        self.assertEqual(w['passes'][0]['contact_witnesses'][1]['raw_gap_m'],value['near'][1][1])
        self.assertFalse(w['actual_accuracy_override']);self.assertFalse(w['numerical_launch_ready'])
        self.assertTrue(w['scalar_proxy_is_not_sixD_error_bound'])
        with self.assertRaises(TypeError):candidate.POLICY['release_proxy_fraction']=1.
        w['policy']['release_proxy_fraction']=100.
        self.assertEqual(candidate.POLICY['release_proxy_fraction'],.5)

    def test_zero_negative_diverging_below_floor_and_far_return_original_cap(self):
        for g,q in ((0.,-1.),(-1e-12,-1.),(.1,1.),(.1,-.005),(2.,-1.)):
            h,w=select(near=[[15,g,[1.,0.,0.],[0.,0.,0.]]],q=[q,0.,0.,0.,0.,0.])
            self.assertEqual(h,1.)
            self.assertEqual(w['passes'][0]['contact_witnesses'][0]['raw_gap_m'],g)

    def test_strict_release_boundary_and_original_cap_bound(self):
        h,w=select(near=[[15,.005,[1.,0.,0.],[0.,0.,0.]]])
        self.assertEqual(h,1.)
        h,w=select(near=[[15,math.nextafter(.005,math.inf),[1.,0.,0.],[0.,0.,0.]]])
        self.assertLess(h,1.);self.assertGreater(h,0.)
        self.assertLessEqual(len(w['passes']),2)

    def test_multiple_contact_release_is_recomputed_until_fixed_point(self):
        near=[[1,.001,[1.,0.,0.],[0.,0.,0.]],[2,.2,[0.,1.,0.],[0.,0.,0.]]]
        h,w=select(near=near,q=[-1.,-10.,0.,0.,0.,0.],epsilon=.1)
        self.assertEqual(h,.0005)
        self.assertEqual([x['output_cap_s'] for x in w['passes']],[.01,.0005,.0005])
        self.assertEqual(w['passes'][0]['contact_witnesses'][0]['action'],'released_for_current_cap')
        self.assertEqual(w['passes'][1]['contact_witnesses'][0]['action'],'precontact_cap_candidate')
        reverse,_=select(near=list(reversed(near)),q=[-1.,-10.,0.,0.,0.,0.],epsilon=.1)
        self.assertEqual(reverse,h);self.assertLessEqual(len(w['passes']),len(near)+1)

    def test_below_minimum_fails_without_flooring_or_gap_change(self):
        near=[[15,1e-15,[1.,0.,0.],[0.,0.,0.]]];before=copy.deepcopy(near)
        with self.assertRaises(candidate.EventCapError) as result:
            select(H=1e-6,near=near,q=[-.1,0.,0.,0.,0.,0.],epsilon=1e-12,minimum=1e-14)
        self.assertIn('below unchanged minimum',str(result.exception))
        self.assertEqual(near,before);self.assertFalse(result.exception.witness['actual_accuracy_override'])

    def test_unrepresentable_half_clocks_fail_without_time_rewrite(self):
        with self.assertRaises(candidate.EventCapError) as result:
            select(H=1e-20,near=[],minimum=1e-30,t=1.)
        self.assertIn('unrepresentable',str(result.exception))

    def test_sixD_coupling_counterexample_cannot_be_called_an_accuracy_bound(self):
        epsilon=.01;H=1.;g=epsilon/2
        h,w=select(H=H,near=[[15,g,[1.,0.,0.],[0.,0.,0.]]],epsilon=epsilon)
        self.assertEqual(h,H)
        # SPD mobility [[1,3],[3,10]], J=(1,0): response P=(1,3),
        # determinant=1>0. Its normal defect g/H becomes ||P||*g/H.
        amplification=math.sqrt(10.)
        self.assertGreater(amplification,2.)
        self.assertGreater(amplification*g/(H*1.),epsilon)
        self.assertFalse(w['actual_accuracy_override'])

    def test_underestimated_closing_counterexample_is_left_to_actual_gate(self):
        h,w=select(H=.1,near=[[15,.001,[1.,0.,0.],[0.,0.,0.]]],q=[-.1,0.,0.,0.,0.,0.],epsilon=.001)
        self.assertAlmostEqual(h,.005)
        actual_v=1.
        self.assertGreater(closed_form_defect(.001,actual_v,h),.001)
        self.assertFalse(w['numerical_or_physical_qualification'])

    def test_varying_original_H_can_prevent_release_and_fails_at_minimum(self):
        g=1.;count=0
        with self.assertRaises(candidate.EventCapError):
            for _ in range(60):
                H=2*g
                h,w=select(H=H,near=[[15,g,[1.,0.,0.],[0.,0.,0.]]],epsilon=1e-5,minimum=1e-12)
                self.assertLess(h,H);g=signorini(g,-1.,h)[0];count+=1
        self.assertGreater(count,20)  # Finite within-call bound is not across-state progress.

    def test_invalid_and_nonfinite_inputs_fail_closed(self):
        for kwargs in ({'H':0.},{'U':float('nan')},{'minimum':-1.},{'epsilon':float('inf')},
                       {'q':[0.]*5},{'near':[[15,1.,[1.,0.],[0.,0.,0.]]]},
                       {'near':[[15,1.,[1.,0.,0.],[0.,0.,0.]]]*2}):
            with self.assertRaises(candidate.EventCapError):select(**kwargs)

    def test_module_is_stdlib_only_and_has_no_native_or_mutation_interface(self):
        tree=ast.parse(Path(candidate.__file__).read_text(encoding='utf-8'))
        imported={node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
        imported|={v.name.split('.')[0] for node in ast.walk(tree) if isinstance(node,ast.Import) for v in node.names}
        self.assertLessEqual(imported,{'types','hashlib','json','math'})
        called={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
        self.assertFalse(called & {'Popen','write_text','write_bytes','open','advance_packet','inertial_contact_step','solve'})
        self.assertNotIn('full_state_integration_adapter_v3',sys.modules)


if __name__=='__main__':
    unittest.main(verbosity=2)
