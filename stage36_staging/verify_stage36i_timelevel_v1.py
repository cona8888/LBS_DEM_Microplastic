"""Paired, frozen CPU time-level and wall-phase comparison."""
import argparse,io,json,platform,time,unittest
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import translating_channel_v1 as old
import translating_channel_timelevel_v1 as new
from moving_wall_reference_v1 import W64
from verify_stage36h_translating_channel_v2 import AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,state
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

STAGING=ROOT/'stage36_staging'
PARENT=ROOT/'stage36_evaluations/stage36h_translating_channel_20260906/verification_02/verification.json'


def manufactured(q,gamma=1e-4):
    j=4;y=np.arange(10)-j+q;tau=.8;c=new.C
    eq=W64[:,None]*(1+3*c[:,0,None]*gamma*y)
    correction=3*W64[:,None]*c[:,0,None]*c[:,1,None]*gamma
    return eq-tau*correction,eq-(tau-1)*correction,j


class TimeLevelTests(unittest.TestCase):
    def test_01_post_linearized_identity(self):
        for q in (.25,.5,.75,.9):
            f,p,j=manufactured(q);k,g,_,_=new.boundary(f,p,j,1,q,[0,0,0],'post')
            np.testing.assert_allclose(g,f[k,j],rtol=0,atol=1e-16)

    def test_02_old_defect_predicted_independently(self):
        for q in (.75,.9):
            f,p,j=manufactured(q);k,g,_,_=new.boundary(f,p,j,1,q,[0,0,0],'old')
            expected=-(2*q-1)/(2*q)*3*W64[k]*new.C[k,0]*1e-4
            np.testing.assert_allclose(g-f[k,j],expected,rtol=0,atol=1e-16)
            self.assertGreater(np.max(np.abs(g-f[k,j])),1e-7)

    def test_03_lower_branch_identical(self):
        for q in (.1,.25,.5):
            f,p,j=manufactured(q)
            np.testing.assert_array_equal(new.boundary(f,p,j,1,q,[0,0,0],'old')[1],new.boundary(f,p,j,1,q,[0,0,0],'post')[1])

    def test_04_explicit_invalid_mode(self):
        f,p,j=manufactured(.75)
        with self.assertRaises(ValueError):new.boundary(f,p,j,1,.75,[0,0,0],'implicit')

    def test_05_old_adapter_exact(self):
        for L in (8+.141421356,8+.499):
            f,y,L=state(U=.01,L=L)
            a,r=old.advance(f,y,L,8,.01,.01);b,s=new.advance(f,y,L,8,.01,.01,'old')
            np.testing.assert_array_equal(a,b);self.assertEqual(r,s)

    def test_06_uniform_post_crossing(self):
        f,y,L=state(L=8+.499);a,r=new.advance(f,y,L,8,.01,0,'post')
        b,s=old.advance(f,y,L,8,.01,0)
        np.testing.assert_allclose(a,b,atol=1e-16)

    def test_07_post_step_budget(self):
        f,y,L=state(U=.01,L=8+.499);a,r=new.advance(f,y,L,8,.01,.01,'post')
        self.assertLess(abs(r['mass_ledger_residual']),1e-13)
        np.testing.assert_allclose(r['momentum_ledger_residual'],0,atol=1e-13)

    def test_08_reject_unplanned_phase(self):
        with self.assertRaises(ValueError):new.run(8,.01,.01,phase=.123)


def bindings():
    parent=json.loads(PARENT.read_text())
    if not parent['execution_completed'] or not parent['unit_tests_passed'] or parent['all_planar_gates_passed']:
        raise ValueError('unexpected H status')
    checked={}
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for path,h in parent[group].items():
            if sha(path)!=h:raise ValueError('parent changed: '+path)
            checked[path]=h
    return checked


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);checked=bindings()
    classes=(AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests)
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes)
    log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    (out/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():
        (out/'failure.json').write_text(json.dumps({'reason':'tests failed'}));print(log.getvalue());raise SystemExit(1)
    plan=[]
    for n in (8,16,32):
        for mode,V,U in [('uniform',.08/n,0),('shear',.08/n,.08/n),('static_shear',0,.08/n)]:plan.append((f'{mode}_N{n}',n,V,U,0.))
    plan.extend([('reverse_motion_N16',16,-.005,.005,0.),('reverse_shear_N16',16,.005,-.005,0.),('rest_N16',16,0,0,0.)])
    for n in (8,16):
        for phase in (.25,.5,.75):plan.append((f'shear_N{n}_phase{phase:g}',n,.08/n,.08/n,phase))
    rows=[];start=time.monotonic();deadline=start+120
    for mode in ('old','post'):
        for base,n,V,U,phase in plan:
            name=mode+'_'+base
            try:
                r,h,s=new.run(n,V,U,deadline,incoming_level=mode,phase=phase)
                r.update(case_id=name,base_case=base)
                if mode=='old' and phase==0:
                    with np.load(PARENT.parent/(base+'_states.npz')) as archive:
                        for key in s:
                            if not np.array_equal(s[key],archive[key]):raise ValueError('OLD replay mismatch: '+key)
                    r['exact_H_state_replay']=True
                np.savez_compressed(out/(name+'_states.npz'),**s)
                (out/(name+'_history.json')).write_text(json.dumps(h,separators=(',',':')),encoding='utf-8')
            except Exception as exc:r={'case_id':name,'base_case':base,'incoming_level':mode,'phase_offset_lu':phase,'passed':False,'execution_error':repr(exc)}
            rows.append(r);print(name+' '+json.dumps({k:r.get(k) for k in ('passed','final_ux_normalized_error','wall_shear_relative_error','execution_error')}),flush=True)
    (out/'flow_results.json').write_text(json.dumps({'cases':rows},indent=2,default=lambda x:x.item()),encoding='utf-8')
    sources=[Path(__file__).resolve(),STAGING/'translating_channel_timelevel_v1.py',STAGING/'STAGE36I_TIME_LEVEL_CONTRACT.md',PARENT]
    report={'execution_completed':all('execution_error' not in r for r in rows),'unit_tests_passed':True,'unit_tests_run':tests.testsRun,
            'regression_tests':105,'new_tests':8,'flow_conditions':len(rows),'all_post_gates_passed':all(r['passed'] for r in rows if r['incoming_level']=='post'),
            'status':'diagnostic_comparison_no_curved_body_promotion','curved_moving_body_qualified':False,'soil_release_prediction':False,
            'elapsed_s':time.monotonic()-start,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'numpy':np.__version__,
            'source_hashes':{str(x):sha(x) for x in sources},'artifact_hashes':{str(x):sha(x) for x in out.iterdir()},'parent_binding_checks':checked}
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'tests':tests.testsRun,'completed':report['execution_completed'],'all_post_passed':report['all_post_gates_passed'],'elapsed_s':report['elapsed_s']},indent=2))


if __name__=='__main__':main()
