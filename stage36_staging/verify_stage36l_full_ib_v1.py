"""Frozen full CPU integration harness; preserves all failed physical gates."""
import io,json,platform,sys,time,unittest
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import scipy
import full_ib_sphere_v1 as m
from verify_stage36k_interface_v2 import AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests,SphereTests,InterfaceTests
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def state(nonuniform=False):
    n=12;c=np.array([6.13,6.17,6.19]);U=np.array([.08/n,0,0]);g=np.indices((n,n,n)).reshape(3,-1).T+.5;u=np.tile(U,(n**3,1))
    if nonuniform:u[:,0]+=.02/n*np.sin(2*np.pi*g[:,1]/n)
    f=m.equilibrium(np.ones(n**3),u.T).reshape(19,n,n,n)
    return f,c,n/5,U

class FullIBTests(unittest.TestCase):
    def test_01_impulse_moments(self):
        rho=np.array([1.,1.01]);u=np.array([[.002,-.003],[.001,0],[0,.001]]);du=np.ones((3,2))*.0001
        df=m.equilibrium(rho,u+du)-m.equilibrium(rho,u)
        np.testing.assert_allclose(df.sum(axis=0),0,atol=1e-15);np.testing.assert_allclose(m.C.T@df,rho*du,atol=1e-15)
    def test_02_uniform_full_step(self):
        f,c,R,U=state();g,r,_=m.step(f,c,R,U,32)
        np.testing.assert_allclose(g,f,atol=1e-14);self.assertLess(r['marker_slip'],1e-12)
    def test_03_active_nonuniform_step(self):
        f,c,R,U=state(True);g,r,e=m.step(f,c,R,U,32,capture=True)
        self.assertLess(r['marker_slip'],1e-12);self.assertGreater(np.linalg.norm(e['marker_impulses']),1e-4)
        np.testing.assert_allclose(r['momentum_ledger_residual'],0,atol=1e-11)
    def test_04_disabled_boundary_detected(self):
        f,c,R,U=state(True);g,r,_=m.step(f,c,R,U,32,enabled=False)
        self.assertGreater(r['marker_slip'],1e-5)
    def test_05_projection_energy(self):
        f,c,R,U=state(True);J=m.matrix(m.surface(R,32)+c,12);g,lam,imp,slip,cond=m.project(f,J,np.zeros(3))
        def ke(x):
            a=x.reshape(19,-1);return np.sum((m.C.T@a)**2/a.sum(axis=0))/2
        self.assertLessEqual(ke(g),ke(f)+1e-12)
    def test_06_geometric_quadrature(self):
        f,c,R,U=state();V=4*np.pi*R**3/3
        for fine in (False,True):
            mass,p=m.interior(f,c,R,fine);self.assertAlmostEqual(mass,V,places=11);np.testing.assert_allclose(p,V*U,atol=1e-12)
    def test_07_reject_invalid(self):
        f,c,R,U=state();f[0,0,0,0]=-1
        with self.assertRaises(ValueError):m.step(f,c,R,U,32)
    def test_08_stream_scalar(self):
        f,c,R,U=state(True);g,r,e=m.step(f,c,R,U,32,capture=True);a=f.reshape(19,-1);rho=a.sum(axis=0);p=(a-(a-m.equilibrium(rho,m.C.T@a/rho))/.8).reshape(f.shape)
        for k in range(19):
            for dest in ((0,0,0),(5,4,3),(11,11,11)):
                src=tuple((np.array(dest)-m.C[k])%12);self.assertAlmostEqual(e['streamed'][(k,)+dest],p[(k,)+src],places=15)

def dump(p,v):p.write_text(json.dumps(v,indent=2,default=lambda x:x.item()),encoding='utf-8')

def main():
    out=ROOT/'stage36_evaluations/stage36l_full_ib_sphere_20260908/verification_01';out.mkdir(parents=True,exist_ok=False)
    parent=ROOT/'stage36_evaluations/stage36k_immersed_interface_20260908/verification_02/verification.json';p=json.loads(parent.read_text())
    assert sha(parent)=='a805b69eff568821c933db1eb054646a82ebe87599ec8a56e6d466d5c9d0126a'
    assert p['operator_gates_passed'] and p['quadratic_integral_convergence_passed'];checked={str(parent):sha(parent)}
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for path,h in p[group].items():assert sha(path)==h,path;checked[path]=h
    manifest=parent.parent.parent/'render_01/render_manifest.json';d=json.loads(manifest.read_text());checked[str(manifest)]=sha(manifest)
    for group in ('source_hashes','artifact_hashes'):
        for path,h in d[group].items():assert sha(path)==h,path;checked[path]=h
    sources={str(Path(__file__).resolve()):sha(__file__)}
    for mod in list(sys.modules.values()):
        path=getattr(mod,'__file__',None)
        if path and Path(path).suffix=='.py' and Path(path).parent==ROOT/'stage36_staging':sources[str(Path(path).resolve())]=sha(path)
    contract=ROOT/'stage36_staging/STAGE36L_FULL_IB_SPHERE_CONTRACT.md';sources[str(contract)]=sha(contract)
    classes=(AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests,SphereTests,InterfaceTests,FullIBTests)
    log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes));(out/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():dump(out/'failure.json',{'reason':'unit tests failed'});print(log.getvalue());raise SystemExit(1)
    plan=[(n,d,0.,False,True) for n in (12,16,24) for d in (1,-1)]+[(16,0,0.,False,True),(16,1,.5,False,True)]+[(n,1,0.,True,True) for n in (12,16,24)]+[(16,1,0.,True,False)]
    dump(out/'resolved_plan.json',{'cases':plan,'cpu_flow_cap_seconds':180,'source_hashes':sources})
    rows=[];start=time.monotonic()
    try:
        for n,d,phase,perturb,enabled in plan:
            name=f'N{n}_d{d}_phase{phase:g}_p{int(perturb)}_ib{int(enabled)}';r,h,s,tr=m.run(n,d,phase,perturb,enabled,start+180);r['case_id']=name
            dump(out/(name+'_result.json'),r);dump(out/(name+'_history.json'),h);np.savez_compressed(out/(name+'_states.npz'),**s);np.savez_compressed(out/(name+'_firststep.npz'),**tr);rows.append(r)
            print(name,json.dumps(r['gates'],default=lambda x:x.item()),flush=True)
    except Exception as e:dump(out/'failure.json',{'reason':repr(e),'completed_cases':len(rows)});raise
    for path,h in sources.items():assert sha(path)==h
    dump(out/'verification.json',{'execution_completed':True,'unit_tests_run':tests.testsRun,'unit_tests_passed':True,'flow_conditions':len(rows),'elapsed_seconds':time.monotonic()-start,
         'all_enabled_integration_gates_passed':all(r['passed'] for r in rows if r['interface_enabled']),'disabled_control_detected':not rows[-1]['gates']['marker_no_slip'],
         'physical_drag_validated':False,'release_prediction_qualified':False,'source_hashes':sources,'parent_binding_checks':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'cases':rows,
         'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'utc':datetime.now(timezone.utc).isoformat(),'command':' '.join(sys.argv)}})
    print('COMPLETE',time.monotonic()-start)

if __name__=='__main__':main()
