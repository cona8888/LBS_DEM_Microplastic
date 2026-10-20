"""Run and preserve complete moving planar flow benchmarks, including failures."""
import argparse
import io
import json
import platform
import time
import unittest
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from translating_channel_v1 import boundary,advance,mask,run,C,OPP
from moving_wall_reference_v1 import equilibrium,moving_reflection,W64
from verify_stage36g_refill_screen_v1 import AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests
from verify_stage36d_wrench_transfer_v1 import ROOT,sha,check_parent

STAGING=ROOT/'stage36_staging'
PARENT=ROOT/'stage36_evaluations/stage36g_refill_screen_20260906/verification_01/verification.json'


def state(n=8,V=.01,U=0,L=None):
    L=n+np.sqrt(2)/10 if L is None else L;y=np.arange(4*n)+.5;a=mask(y,L,n)
    f=np.zeros((19,len(y)));u=np.zeros((3,n));u[0]=U*(y[a]-L)/n;u[1]=V
    f[:,a]=equilibrium(np.ones(n),u)
    return f,y,L


class ChannelTests(unittest.TestCase):
    def test_01_midpoint_matches_previous_wall(self):
        f,y,L=state();j=np.flatnonzero(mask(y,L,8))[0]
        k,g,dm,imp=boundary(f,f,j,1,.5,[.005,.01,0])
        ref,jref=moving_reflection(f[OPP[k],j],k,[.005,.01,0])
        np.testing.assert_allclose(g,ref,atol=1e-16);np.testing.assert_allclose(imp,jref.sum(axis=0),atol=1e-16)

    def test_02_uniform_both_distance_branches(self):
        f,y,L=state();a=mask(y,L,8)
        for q in (.01,.25,.5,.75,.99):
            for d,j in ((1,np.flatnonzero(a)[0]),(-1,np.flatnonzero(a)[-1])):
                k,g,_,_=boundary(f,f,j,d,q,[0,.01,0])
                np.testing.assert_allclose(g,f[k,j],atol=1e-16)

    def test_03_bad_boundary_parameters(self):
        f,y,L=state()
        for q in (-.01,1.01,np.nan):
            with self.assertRaises(ValueError):boundary(f,f,8,1,q,[0,0,0])
        with self.assertRaises(ValueError):boundary(f,f,8,1,.5,[0,.1,0])

    def test_04_complete_uniform_step(self):
        f,y,L=state();g,r=advance(f,y,L,8,.01,0)
        np.testing.assert_allclose(g,f,atol=1e-16)
        self.assertLess(abs(r['mass_ledger_residual']),1e-13)
        np.testing.assert_allclose(r['momentum_ledger_residual'],0,atol=1e-13)

    def test_05_mask_change_uniform_step(self):
        f,y,L=state(L=8+.499);g,r=advance(f,y,L,8,.01,0)
        self.assertEqual(len(r['refill_stencils']),1);self.assertEqual(len(r['covered_indices']),1)
        a=mask(y,L+.01,8)
        np.testing.assert_allclose(g[:,a],equilibrium(np.ones(8),np.tile([[0],[.01],[0]],(1,8))),atol=1e-16)
        self.assertTrue(np.all(g[:,~a]==0))

    def test_06_reverse_mask_change(self):
        f,y,L=state(V=-.01,L=8+.501);g,r=advance(f,y,L,8,-.01,0)
        self.assertEqual(len(r['refill_stencils']),1)
        self.assertLess(abs(g.sum()-f.sum()),1e-13)

    def test_07_nonuniform_scalar_streaming(self):
        f,y,L=state(U=.01);a=mask(y,L,8);ids=np.flatnonzero(a)
        # Independent scalar pull stream and scalar BFL formulas, no refill.
        rho=f[:,a].sum(axis=0);u=(C.T@f[:,a])/rho;post=np.zeros_like(f)
        post[:,a]=f[:,a]-(f[:,a]-equilibrium(rho,u))/.8;expected=np.zeros_like(f)
        for j in ids:
            for k in range(19):
                src=j-int(C[k,1])
                if a[src]:expected[k,j]=post[k,src]
                else:
                    low=src<ids[0];d=1 if low else -1;q=y[j]-L if low else L+8-y[j]
                    o=int(OPP[k]);wall=np.array([0 if low else .01,.01,0]);B=6*W64[k]*float(C[k]@wall)
                    expected[k,j]=2*q*post[o,j]+(1-2*q)*post[o,j+d]+B if q<=.5 else (post[o,j]+B)/(2*q)+(2*q-1)*f[k,j]/(2*q)
        got,r=advance(f,y,L,8,.01,.01)
        np.testing.assert_allclose(got,expected,rtol=0,atol=1e-16)

    def test_08_momentum_ledger_nonuniform_crossing(self):
        f,y,L=state(U=.01,L=8+.499);g,r=advance(f,y,L,8,.01,.01)
        self.assertLess(abs(r['mass_ledger_residual']),1e-13)
        np.testing.assert_allclose(r['momentum_ledger_residual'],0,atol=1e-13)
        self.assertGreater(np.max(np.abs(r['status_impulse'])),.001)

    def test_09_invalid_initial_solid(self):
        f,y,L=state();f[0,0]=.01
        with self.assertRaises(ValueError):advance(f,y,L,8,.01,0)

    def test_10_inputs_unchanged(self):
        f,y,L=state(U=.01,L=8+.499);old=f.copy();advance(f,y,L,8,.01,.01)
        np.testing.assert_array_equal(f,old)


def verify_parent():
    data=json.loads(PARENT.read_text())
    if not data['execution_completed'] or not data['unit_tests_passed'] or data['refill_qualified_for_moving_body']:
        raise ValueError('unexpected Stage36G evidence status')
    bindings={}
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for name,value in data[group].items():
            if sha(name)!=value:raise ValueError('parent binding mismatch: '+name)
            bindings[name]=value
    check_parent(ROOT/'stage36_evaluations/stage36f_moving_wall_20260906/verification_01/verification.json')
    return bindings


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);bindings=verify_parent()
    classes=(AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests)
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes)
    buf=io.StringIO();tests=unittest.TextTestRunner(stream=buf,verbosity=2).run(suite)
    (out/'tests.txt').write_text(buf.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():
        (out/'failure.json').write_text(json.dumps({'reason':'unit tests failed'}));print(buf.getvalue());raise SystemExit(1)
    cases=[]
    for n in (8,16,32):
        for mode,V,U in [('uniform',.08/n,0),('shear',.08/n,.08/n),('static_shear',0,.08/n)]:cases.append((f'{mode}_N{n}',n,V,U))
    cases.extend([('reverse_motion_N16',16,-.005,.005),('reverse_shear_N16',16,.005,-.005),('rest_N16',16,0,0)])
    started=time.monotonic();deadline=started+120;results=[]
    for name,n,V,U in cases:
        try:
            row,history,states=run(n,V,U,deadline);row['case_id']=name
            np.savez_compressed(out/(name+'_states.npz'),**states)
            (out/(name+'_history.json')).write_text(json.dumps(history,separators=(',',':')),encoding='utf-8')
        except Exception as e:
            row={'case_id':name,'n':n,'V_lu':V,'U_lu':U,'passed':False,'execution_error':repr(e)}
        results.append(row);print(name+' '+json.dumps({k:row.get(k) for k in ('passed','max_mass_relative_drift','final_ux_normalized_error','wall_shear_relative_error','execution_error')}),flush=True)
    (out/'flow_results.json').write_text(json.dumps({'cases':results},indent=2,default=lambda x:x.item()),encoding='utf-8')
    sources=[Path(__file__).resolve(),STAGING/'translating_channel_v1.py',STAGING/'STAGE36H_TRANSLATING_CHANNEL_CONTRACT.md',PARENT]
    report={'execution_completed':all('execution_error' not in r for r in results),'unit_tests_passed':True,
            'unit_tests_run':tests.testsRun,'regression_tests':95,'new_tests':10,'cpu_flow_cases':len(results),
            'all_planar_gates_passed':all(r['passed'] for r in results),'case_gate_summary':{r['case_id']:r.get('gates',{}) for r in results},
            'curved_moving_body_qualified':False,'soil_release_prediction':False,'gpu_jobs_started':0,'production_cuda_modified':False,
            'elapsed_s':time.monotonic()-started,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'python':platform.python_version(),'numpy':np.__version__,'command_scope':'CPU prescribed planar motion only',
            'source_hashes':{str(x):sha(x) for x in sources},'artifact_hashes':{str(x):sha(x) for x in out.iterdir()},'parent_binding_checks':bindings}
    (out/'verification.json').write_text(json.dumps(report,indent=2,default=lambda x:x.item()),encoding='utf-8')
    print(json.dumps({'unit_tests':tests.testsRun,'execution_completed':report['execution_completed'],'all_planar_gates_passed':report['all_planar_gates_passed'],'elapsed_s':report['elapsed_s']},indent=2))


if __name__=='__main__':main()
