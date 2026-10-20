"""Bounded fixed-grid time-scale and independent marker sensitivity."""
import io,json,platform,sys,time,unittest
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import scipy
import refined_ib_sphere_v1 as m
import full_ib_sphere_v1 as old
from verify_stage36l_full_ib_v1 import AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests,SphereTests,InterfaceTests,FullIBTests,state
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def scaling(s):
    if s not in (1,2,4):raise ValueError('outside time plan')
    return {'dx':1/16,'dt':1/(256*s),'tau':{1:.8,2:.65,4:.575}[s],'U_lu':.005/s,'amplitude_lu':.00125/s,'steps':256*s,'velocity_scale':16*s,'force_scale':s*s,'impulse_scale':s/256}

def initial(s):
    p=scaling(s);n=16;c=np.array([8.13,8.17,8.19]);U=np.array([p['U_lu'],0,0]);g=np.indices((n,n,n)).reshape(3,-1).T+.5;wave=np.sin(2*np.pi*g[:,1]/n)
    u=np.tile(U,(n**3,1));u[:,0]+=p['amplitude_lu']*wave
    return m.equilibrium(np.ones(n**3),u.T).reshape(19,n,n,n),c,U,wave,p

class RefinementTests(unittest.TestCase):
    def test_01_viscosity_scaling(self):
        for s in (1,2,4):
            p=scaling(s);self.assertAlmostEqual((p['tau']-.5)/3*p['dx']**2/p['dt'],.1,places=14)
    def test_02_motion_duration(self):
        for s in (1,2,4):
            p=scaling(s);self.assertAlmostEqual(p['U_lu']*p['steps']*p['dx'],.08);self.assertEqual(p['steps']*p['dt'],1.)
    def test_03_force_impulse_units(self):
        for s in (1,2,4):
            p=scaling(s);self.assertEqual(p['force_scale']*p['dt'],p['impulse_scale'])
            self.assertAlmostEqual(p['force_scale'],p['dx']**4/p['dt']**2)
    def test_04_exact_baseline_step(self):
        f,c,U,w,p=initial(1);a,r,e=old.step(f,c,3.2,U,56,capture=True);b,t,q=m.step(f,c,3.2,U,56,capture=True,tau=.8)
        np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(e['marker_impulses'],q['marker_impulses'])
    def test_05_uniform_refined(self):
        for s in (2,4):
            f,c,U,w,p=initial(s);f=m.equilibrium(np.ones(4096),np.tile(U[:,None],(1,4096))).reshape(f.shape);g,r,_=m.step(f,c,3.2,U,56,tau=p['tau'])
            np.testing.assert_allclose(g,f,rtol=0,atol=1e-14)
    def test_06_invalid_tau(self):
        f,c,U,w,p=initial(1)
        with self.assertRaises(ValueError):m.step(f,c,3.2,U,56,tau=.51)

def dump(p,d):p.write_text(json.dumps(d,indent=2,default=lambda x:x.item()),encoding='utf-8')

def run(s,count,deadline):
    f,c0,U,w,p=initial(s);initial_f=f.copy();M=float(f.sum());mi,_=m.interior(f,c0,3.2);ME=M-mi;history=[];states={'initial':initial_f,'centre_initial':c0};first=None
    for t in range(p['steps']):
        if time.monotonic()>deadline:raise TimeoutError('CPU cap')
        f,r,e=m.step(f,c0+t*U,3.2,U,count,tau=p['tau'],capture=t==0)
        r.update(step=t+1,time=(t+1)*p['dt'],total_mass_drift=abs(r['mass_after']-M)/M,exterior_mass_drift=abs(r['exterior_mass_after']-ME)/ME,
                 force_physical=(np.array(r['force_candidate'])*p['force_scale']).tolist())
        history.append(r)
        if t==0:first=e
        if (t+1)%(64*s)==0:states[f'quarter_{(t+1)//(64*s)}']=f.copy()
    states['centre_final']=c0+p['steps']*U;fine,_=m.interior(f,states['centre_final'],3.2,True)
    metrics={'max_total_mass_drift':max(r['total_mass_drift'] for r in history),'max_exterior_mass_drift':max(r['exterior_mass_drift'] for r in history),
             'max_momentum_ledger_relative':max(np.max(np.abs(r['momentum_ledger_residual']))/M for r in history),'max_marker_slip':max(r['marker_slip'] for r in history),
             'max_probe_slip_normalized':max(r['probe_slip'] for r in history)/p['amplitude_lu'],'max_density_error':max(r['density_error'] for r in history),
             'max_condition_number':max(r['condition_number'] for r in history),'fine_quadrature_discrepancy':abs(fine-history[-1]['interior_mass_after'])/ME}
    gates={'total_mass':metrics['max_total_mass_drift']<=1e-10,'exterior_mass_estimate':metrics['max_exterior_mass_drift']<=1e-6,'momentum':metrics['max_momentum_ledger_relative']<=1e-12,
           'marker_slip':metrics['max_marker_slip']<=1e-10,'probe_slip':metrics['max_probe_slip_normalized']<=.05,'density':metrics['max_density_error']<=.01,'quadrature':metrics['fine_quadrature_discrepancy']<=1e-6}
    return {'s':s,'markers':count,**p,**metrics,'gates':gates,'passed':all(gates.values())},history,states,first

def control(s,deadline):
    f,c,U,w,p=initial(s);history=[];M=float(f.sum())
    for t in range(p['steps']):
        if time.monotonic()>deadline:raise TimeoutError('CPU cap')
        a=f.reshape(19,-1);rho=a.sum(axis=0);u=m.C.T@a/rho;post=(a-(a-m.equilibrium(rho,u))/p['tau']).reshape(f.shape)
        f=np.stack([np.roll(post[k],tuple(m.C[k]),axis=(0,1,2)) for k in range(19)])
        a=f.reshape(19,-1);u=m.C.T@a/a.sum(axis=0);amplitude=float(np.dot(u[0]-U[0],w)/(w@w))/p['amplitude_lu'];exact=float(np.exp(-.1*(2*np.pi)**2*(t+1)*p['dt']))
        if not np.isfinite(f).all() or np.any(f<=0):raise ValueError('shear control health')
        history.append({'time':(t+1)*p['dt'],'amplitude_normalized':amplitude,'exact':exact,'absolute_normalized_error':abs(amplitude-exact),'mass_drift':abs(f.sum()-M)/M})
    error=max(r['absolute_normalized_error'] for r in history)
    return {'s':s,**p,'max_shear_amplitude_error':error,'passed':error<=.02},history,f

def main():
    out=ROOT/'stage36_evaluations/stage36m_refinement_20260908/verification_01';out.mkdir(parents=True,exist_ok=False)
    parent=ROOT/'stage36_evaluations/stage36l_full_ib_sphere_20260908/verification_01/verification.json';p=json.loads(parent.read_text());assert p['all_enabled_integration_gates_passed'] and p['disabled_control_detected']
    assert sha(parent)=='5c7f69bb10d85d4d736df860beb65e9ada5cc7146a92fd35d5e7e00089dd3721';checked={str(parent):sha(parent)}
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for path,h in p[group].items():assert sha(path)==h,path;checked[path]=h
    rm=parent.parent.parent/'render_01/render_manifest.json';d=json.loads(rm.read_text());checked[str(rm)]=sha(rm)
    for group in ('source_hashes','artifact_hashes'):
        for path,h in d[group].items():assert sha(path)==h,path;checked[path]=h
    contract=ROOT/'stage36_staging/STAGE36M_REFINEMENT_CONTRACT.md';sources={str(contract):sha(contract)}
    for mod in list(sys.modules.values()):
        path=getattr(mod,'__file__',None)
        if path and Path(path).suffix=='.py' and Path(path).parent==ROOT/'stage36_staging':sources[str(Path(path).resolve())]=sha(path)
    classes=(AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests,SphereTests,InterfaceTests,FullIBTests,RefinementTests)
    log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes));(out/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():dump(out/'failure.json',{'reason':'unit tests'});print(log.getvalue());raise SystemExit(1)
    plan=[(1,56),(2,56),(4,56),(1,32),(1,80)];dump(out/'resolved_plan.json',{'immersed_cases':plan,'shear_controls':[1,2,4],'fixed_grid_n':16,'independent_probes':256,'cpu_cap_seconds':180,'source_hashes':sources})
    rows=[];controls=[];start=time.monotonic()
    try:
        for s,count in plan:
            name=f's{s}_m{count}';r,h,states,first=run(s,count,start+180);r['case_id']=name
            if (s,count)==(1,56):
                with np.load(parent.parent/'N16_d1_phase0_p1_ib1_states.npz') as z:
                    np.testing.assert_array_equal(states['initial'],z['initial']);np.testing.assert_array_equal(states['quarter_4'],z['final'])
                r['exact_stage36l_reproduction']=True
            dump(out/(name+'_result.json'),r);dump(out/(name+'_history.json'),h);np.savez_compressed(out/(name+'_states.npz'),**states);np.savez_compressed(out/(name+'_firststep.npz'),**first);rows.append(r);print(name,json.dumps(r['gates'],default=lambda x:x.item()),flush=True)
        for s in (1,2,4):
            name=f'shear_s{s}';r,h,f=control(s,start+180);r['case_id']=name;dump(out/(name+'_result.json'),r);dump(out/(name+'_history.json'),h);np.savez_compressed(out/(name+'_final.npz'),final=f);controls.append(r);print(name,r['max_shear_amplitude_error'],flush=True)
    except Exception as e:dump(out/'failure.json',{'reason':repr(e),'completed_immersed':len(rows),'completed_controls':len(controls)});raise
    for path,h in sources.items():assert sha(path)==h
    dump(out/'verification.json',{'execution_completed':True,'unit_tests_run':tests.testsRun,'unit_tests_passed':True,'flow_conditions':8,'cases':rows,'controls':controls,'integration_gates_passed':all(r['passed'] for r in rows),'shear_controls_passed':all(r['passed'] for r in controls),
         'refinement_comparison_pending':True,'physical_drag_validated':False,'release_prediction_qualified':False,'elapsed_seconds':time.monotonic()-start,'source_hashes':sources,'parent_binding_checks':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},
         'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'utc':datetime.now(timezone.utc).isoformat(),'command':' '.join(sys.argv)}})
    print('COMPLETE',time.monotonic()-start)

if __name__=='__main__':main()
