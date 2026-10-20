"""Frozen bounded sphere benchmark; failures are scientific results, not approvals."""
import argparse,io,json,time,unittest
from pathlib import Path
import numpy as np
import moving_sphere_reference_v1 as m
from verify_stage36i_timelevel_v1 import AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def state():
    n=12;x=m.coordinates(n);c=np.array([6.13,6.17,6.19]);U=np.array([.08/n,0,0]);a=m.fluid_mask(x,c,n/5)
    f=np.zeros((19,n**3));f[:,a]=m.equilibrium(np.ones(a.sum()),np.tile(U[:,None],(1,a.sum())))
    return f.reshape(19,n,n,n),x,c,n/5,U

class SphereTests(unittest.TestCase):
    def test_01_axis_root(self):
        np.testing.assert_allclose(m.intersection(np.array([[2.25,0,0]]),np.array([1,0,0]),np.zeros(3),2),[.25])
    def test_02_diagonal_root(self):
        x=np.array([[1.7,1.7,0.]])
        np.testing.assert_allclose(m.intersection(x,np.array([1,1,0]),np.zeros(3),2),[1.7-np.sqrt(2)])
    def test_03_uniform_reflection(self):
        U=np.array([.005,0,0]);f=m.equilibrium(np.ones(1),U[:,None])[:,0]
        for k in range(1,19):
            for q in (.2,.5,.7,.99):
                self.assertAlmostEqual(float(m.reflect(f[m.OPP[k]],f[k],f[m.OPP[k]],k,np.array(q),U)),f[k],places=15)
    def test_04_invalid_link(self):
        with self.assertRaises(ValueError):m.reflect(1,1,1,1,np.array(0.),np.zeros(3))
        with self.assertRaises(ValueError):m.intersection(np.array([[5.,5,0]]),np.array([1,0,0]),np.zeros(3),2)
    def test_05_uniform_step(self):
        f,x,c,R,U=state();g,r,e=m.step(f,x,c,R,U,True)
        self.assertLess(r['rho_max_error'],1e-12);self.assertLess(r['u_max_error'],1e-12)
        self.assertLess(abs(r['mass_ledger_residual']),1e-10)
        np.testing.assert_allclose(r['momentum_ledger_residual'],0,atol=1e-10)
    def test_06_scalar_boundary_inventory(self):
        f,x,c,R,U=state();g,r,e=m.step(f,x,c,R,U,True);a=m.fluid_mask(x,c,R);expected=set()
        for j in np.flatnonzero(a):
            p=np.array(np.unravel_index(j,(12,12,12)))
            for k in range(1,19):
                src=np.ravel_multi_index(tuple((p-m.C[k])%12),(12,12,12))
                if not a[src]:expected.add((k,int(j)))
        self.assertEqual(expected,{(int(v[0]),int(v[1])) for v in e['links']})
        for k,j,q,_,_ in e['links']:
            self.assertAlmostEqual(np.linalg.norm(x[int(j)]-q*m.C[int(k)]-c),R,places=12)
    def test_07_perturbed_budget(self):
        f,x,c,R,U=state();a=m.fluid_mask(x,c,R);f.reshape(19,-1)[:,a]*=(1+1e-5*np.sin(x[a,0]))
        g,r,e=m.step(f,x,c,R,U)
        self.assertLess(abs(r['mass_ledger_residual']),1e-10)
        np.testing.assert_allclose(r['momentum_ledger_residual'],0,atol=1e-10)
    def test_08_reject_negative(self):
        f,x,c,R,U=state();f[0,0,0,0]=-1
        with self.assertRaises(ValueError):m.step(f,x,c,R,U)

def dump(path,obj):path.write_text(json.dumps(obj,indent=2,default=lambda v:v.item()),encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);out=p.parse_args().output.resolve();out.mkdir(parents=True,exist_ok=False)
    selected=ROOT/'stage36_evaluations/stage36i_timelevel_20260908/render_02/selected_implementation.json'
    parent=ROOT/'stage36_evaluations/stage36i_timelevel_20260908/verification_01/verification.json'
    checked={};d=json.loads(parent.read_text());s=json.loads(selected.read_text())
    assert d['execution_completed'] and d['unit_tests_passed'] and d['all_post_gates_passed']
    assert sha(parent)=='d4d945d033bc0a85a6f24ed3de5dec0f6cf36cb1505a29c2b7bbce8d1acc380f'
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for path,h in d[group].items():
            assert sha(path)==h,path
            checked[path]=h
    for path in (parent,selected):checked[str(path)]=sha(path)
    render_manifest=selected.parent/'render_manifest.json'
    rd=json.loads(render_manifest.read_text())
    for group in ('source_hashes','artifact_hashes'):
        for path,h in rd.get(group,{}).items():assert sha(path)==h,path
    checked[str(render_manifest)]=sha(render_manifest)
    sources={str(p):sha(p) for p in (Path(__file__),ROOT/'stage36_staging/moving_sphere_reference_v1.py',ROOT/'stage36_staging/STAGE36J_MOVING_SPHERE_CONTRACT.md')}
    classes=(AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests,SphereTests)
    log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes))
    (out/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():dump(out/'failure.json',{'reason':'unit tests failed'});print(log.getvalue());raise SystemExit(1)
    plan=[(n,d,0.) for n in (12,16,24) for d in (1,-1)]+[(16,0,0.),(16,1,.5)]
    rows=[];start=time.monotonic()
    try:
        for n,d,phase in plan:
            name=f'N{n}_d{d}_phase{phase:g}';r,h,states,tr=m.run(n,d,phase,start+180);r['case_id']=name
            dump(out/(name+'_result.json'),r);dump(out/(name+'_history.json'),h);np.savez_compressed(out/(name+'_states.npz'),**states)
            if tr:np.savez_compressed(out/(name+'_transition.npz'),**tr)
            rows.append(r);print(name,r['gates'],flush=True)
    except Exception as e:
        dump(out/'failure.json',{'reason':repr(e),'completed_cases':len(rows)});raise
    for path,h in sources.items():assert sha(path)==h
    report={'execution_completed':True,'unit_tests_passed':True,'unit_tests_run':tests.testsRun,'flow_conditions':len(rows),'elapsed_seconds':time.monotonic()-start,
            'all_sphere_gates_passed':all(r['passed'] for r in rows),'moving_body_qualified':False,'release_prediction_qualified':False,
            'source_hashes':sources,'parent_binding_checks':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'cases':rows}
    dump(out/'verification.json',report);print('COMPLETE',report['all_sphere_gates_passed'],report['elapsed_seconds'])

if __name__=='__main__':main()
