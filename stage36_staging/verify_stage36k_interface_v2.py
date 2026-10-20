"""CPU operator verification only; deliberately no LBM time integration."""
import io,json,platform,sys,time,unittest
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import immersed_interface_v1 as ib
from verify_stage36j_moving_sphere_v1 import AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests,SphereTests
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def grid(n,h):return (np.array(list(np.ndindex(n,n,n)))+.5)*h
def small():
    X=np.array([[3.21,3.77,4.19],[4.73,2.91,3.46]])*.5;n=12;h=.5
    return X,n,h,*ib.stencil(X,n,h)

class InterfaceTests(unittest.TestCase):
    def test_01_kernel_values(self):np.testing.assert_allclose(ib.phi(np.array([-2,-1,0,1,2])),[0,.25,.5,.25,0],atol=1e-15)
    def test_02_kernel_moments(self):
        for s in np.linspace(-2,2,101):
            j=np.arange(-5,6);w=ib.phi(j-s)
            self.assertAlmostEqual(w.sum(),1,places=14);self.assertAlmostEqual(np.sum((j-s)*w),0,places=14)
            self.assertAlmostEqual(w@w,3/8,places=14)
    def test_03_affine_interpolation(self):
        X,n,h,ids,w,pos=small();A=np.array([[1,2,3],[-1,4,2],[.5,-2,1]])
        np.testing.assert_allclose(ib.interpolate(grid(n,h)@A.T+.3,ids,w),X@A.T+.3,atol=1e-13)
    def test_04_force_and_units(self):
        for h in (1.,.5,.25):
            X=np.array([[4.13,5.17,6.19]])*h;ids,w,pos=ib.stencil(X,12,h);F=np.array([[.2,-.3,.4]])
            np.testing.assert_allclose(h**3*ib.spread(F,ids,w,12,h).sum(axis=0),F[0],atol=1e-14)
    def test_05_torque(self):
        X,n,h,ids,w,pos=small();F=np.array([[.1,.2,-.4],[-.3,.7,.2]]);f=ib.spread(F,ids,w,n,h)
        np.testing.assert_allclose(np.cross(grid(n,h),f).sum(axis=0)*h**3,np.cross(X,F).sum(axis=0),atol=1e-13)
    def test_06_adjoint_power(self):
        X,n,h,ids,w,pos=small();rng=np.random.default_rng(3611);u=rng.normal(size=(n**3,3));F=rng.normal(size=(len(X),3))
        self.assertAlmostEqual(h**3*np.sum(u*ib.spread(F,ids,w,n,h)),np.sum(ib.interpolate(u,ids,w)*F),places=13)
    def test_07_sphere_moments(self):
        x,v=ib.sphere_quadrature(.2);V=4*np.pi*.2**3/3
        self.assertAlmostEqual(v.sum(),V,places=14);np.testing.assert_allclose(v@x,0,atol=1e-15)
        np.testing.assert_allclose(x.T@(v[:,None]*x),np.eye(3)*V*.2**2/5,atol=1e-15)
    def test_08_interior_acceleration(self):
        X,n,h,ids,w,pos=small();v=np.array([.02,.03]);U=np.array([.03,-.02,.01]);a=np.array([.2,-.1,.3]);dt=.01
        p0=ib.interior_momentum(np.tile(U,(n**3,1)),ids,w,v);p1=ib.interior_momentum(np.tile(U+a*dt,(n**3,1)),ids,w,v)
        np.testing.assert_allclose((p1-p0)/dt,v.sum()*a,atol=1e-13)
    def test_09_force_sign_and_correction(self):
        Fh=np.array([.1,-.2,.3]);dp=np.array([.2,.3,-.4]);dt=.03;Ffluid=dp-Fh
        np.testing.assert_allclose(ib.hydrodynamic_force(Ffluid,np.zeros(3),dp*dt,dt),Fh,atol=1e-14)
        self.assertGreater(np.linalg.norm(-Ffluid-Fh),.1)
    def test_10_reject_seam_and_nan(self):
        with self.assertRaises(ValueError):ib.stencil(np.array([[.01,.5,.5]]),12,1/12)
        with self.assertRaises(ValueError):ib.phi(np.nan)
        with self.assertRaises(ValueError):ib.hydrodynamic_force([0,0,0],[0,0,0],[0,0,0],0)
    def test_11_scalar_kernel_independence(self):
        X,n,h,ids,w,pos=small()
        def scalar(r):
            a=abs(r)
            if a>=2:return 0.
            if a>1:return (5-2*a-(-7+12*a-4*a*a)**.5)/8
            return (3-2*a+(1+4*a-4*a*a)**.5)/8
        for l in range(len(X)):
            dense=np.array([np.prod([scalar(t) for t in (p-X[l])/h]) for p in grid(n,h)])
            sparse=np.zeros(n**3);sparse[ids[l]]=w[l];np.testing.assert_allclose(dense,sparse,atol=1e-15)
    def test_12_unscaled_spread_negative_control(self):
        X,n,h,ids,w,pos=small();F=np.ones((2,3));f=ib.spread(F,ids,w,n,h)
        self.assertGreater(np.max(np.abs((h**3*f).sum(axis=0)*h**3-F.sum(axis=0))),1.)

def dump(p,obj):p.write_text(json.dumps(obj,indent=2,default=lambda v:v.item()),encoding='utf-8')

def main():
    out=ROOT/'stage36_evaluations/stage36k_immersed_interface_20260908/verification_02';out.mkdir(parents=True,exist_ok=False)
    parent=ROOT/'stage36_evaluations/stage36j_moving_sphere_20260908/verification_01/verification.json';p=json.loads(parent.read_text());assert p['execution_completed'] and not p['all_sphere_gates_passed']
    checked={str(parent):sha(parent)}
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for f,h in p[group].items():assert sha(f)==h,f;checked[f]=h
    handoff=parent.parent.parent/'render_02/render_manifest.json';d=json.loads(handoff.read_text())
    for group in ('source_hashes','artifact_hashes'):
        for f,h in d[group].items():assert sha(f)==h,f;checked[f]=h
    checked[str(handoff)]=sha(handoff)
    sources={str(p.resolve()):sha(p) for p in (Path(__file__),Path(ib.__file__),ROOT/'stage36_staging/STAGE36K_IMMERSED_INTERFACE_CONTRACT.md')}
    # Record imported regression dependencies, not just the new entry point.
    for mod in list(sys.modules.values()):
        f=getattr(mod,'__file__',None)
        if f and Path(f).suffix=='.py' and Path(f).parent==ROOT/'stage36_staging':sources[str(Path(f).resolve())]=sha(f)
    classes=(AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests,ChannelTests,TimeLevelTests,SphereTests,InterfaceTests)
    log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes))
    (out/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():dump(out/'failure.json',{'reason':'unit tests failed'});print(log.getvalue());raise SystemExit(1)
    rows=[];body,v=ib.sphere_quadrature(.2);V=4*np.pi*.2**3/3;rng=np.random.default_rng(3611);F=rng.normal(size=(len(body),3))*.001
    for n in (12,16,24):
        h=1/n;g=grid(n,h);u=rng.normal(size=(n**3,3))*.01
        for phase in np.linspace(0,1,9):
            c=(np.array([n/2-.4+phase,n/2+.17,n/2+.19]))/n;X=body+c;ids,w,pos=ib.stencil(X,n,h);sf=ib.spread(F,ids,w,n,h)
            volume_density=np.zeros(n**3);np.add.at(volume_density,ids.ravel(),(v[:,None]*w/h**3).ravel())
            interp=ib.interpolate(u,ids,w);quad=v@ib.interpolate(g*g,ids,w);exact=V*(c*c+.2**2/5)
            U=np.array([.08,-.02,.01]);a=np.array([.2,-.1,.3]);dt=.01;P0=ib.interior_momentum(np.tile(U,(n**3,1)),ids,w,v)
            ids1,w1,_=ib.stencil(X+U*dt,n,h);P1=ib.interior_momentum(np.tile(U+a*dt,(n**3,1)),ids1,w1,v)
            Fh=np.array([.004,-.002,.003]);Ffluid=V*a-Fh;extracted=ib.hydrodynamic_force(Ffluid,P0,P1,dt)
            metrics={'partition_error':np.max(np.abs(w.sum(axis=1)-1)),'first_moment_error':np.max(np.abs(np.sum((pos-X[:,None,:])*w[:,:,None],axis=1))),
                     'volume_relative_error':abs(volume_density.sum()*h**3-V)/V,'centroid_error':np.max(np.abs(volume_density@g*h**3/V-c)),
                     'force_error':np.max(np.abs(sf.sum(axis=0)*h**3-F.sum(axis=0))),'torque_error':np.max(np.abs(np.cross(g,sf).sum(axis=0)*h**3-np.cross(X,F).sum(axis=0))),
                     'power_error':abs(np.sum(u*sf)*h**3-np.sum(interp*F)),'uniform_interior_momentum_error':np.max(np.abs(P0-V*U)),
                     'manufactured_force_error':np.max(np.abs(extracted-Fh)),'quadratic_integral_error_per_volume':np.max(np.abs(quad-exact))/V,
                     'smoothed_volume_density_min':volume_density.min(),'smoothed_volume_density_max':volume_density.max()}
            gate=all(metrics[k]<=1e-11 for k in metrics if k.endswith('error'))
            rows.append({'n':n,'phase':float(phase),'centre':c.tolist(),**metrics,'operator_gates_passed':gate})
            if n==16 and phase==.5:np.savez_compressed(out/'representative_operators.npz',grid=g,markers=X,body_points=body,volume_weights=v,ids=ids,kernel_weights=w,marker_forces=F,grid_force_density=sf,grid_velocity=u,interpolated_velocity=interp,smoothed_volume_density=volume_density)
    worst=[max(r['quadratic_integral_error_per_volume'] for r in rows if r['n']==n) for n in (12,16,24)]
    orders=[float(np.log(worst[i]/worst[i+1])/np.log((16,24)[i]/(12,16)[i])) for i in (0,1)]
    converged=all(o>=1.5 for o in orders) and worst[0]>worst[1]>worst[2]
    for f,h in sources.items():assert sha(f)==h
    dump(out/'phase_results.json',rows)
    report={'execution_completed':True,'unit_tests_run':tests.testsRun,'unit_tests_passed':True,'operator_positions':27,'new_flow_runs':0,'operator_gates_passed':all(r['operator_gates_passed'] for r in rows),
            'quadratic_integral_convergence_passed':converged,'quadratic_worst_errors':worst,'quadratic_orders':orders,'flow_solver_qualified':False,'release_prediction_qualified':False,
            'environment':{'python':platform.python_version(),'numpy':np.__version__,'utc':datetime.now(timezone.utc).isoformat(),'command':' '.join(sys.argv)},
            'source_hashes':sources,'parent_binding_checks':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()}}
    dump(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if not k.endswith('hashes') and k!='parent_binding_checks'},indent=2,default=lambda v:v.item()))

if __name__=='__main__':main()
