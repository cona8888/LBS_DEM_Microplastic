"""Independent steady regularized Stokes diagnostic, not production LBM.

Periodic incompressible Fourier mobility, mean flow prescribed. Same J as
the archived sphere. Two declared spatial operators, no radius fitting.
"""
import hashlib, json, time, platform
from pathlib import Path
import numpy as np
from scipy.sparse.linalg import LinearOperator, cg
from scipy.linalg import cho_solve
import periodic_drag_reference_fast_v1 as ref

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage36_evaluations/stage36ao_independent_stokes_20260910/diagnosis_01'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

class Mobility:
    def __init__(self,n,mu,kind):
        self.n=n; self.mu=mu
        k=2*np.pi*np.fft.fftfreq(n)
        ks=np.stack(np.meshgrid(k,k,k,indexing='ij'),axis=-1)
        if kind=='spectral':
            self.lap=np.sum(ks**2,axis=-1)
            self.q=ks.copy()
            self.q[np.abs(self.q)==np.pi]=0 # real, skew-adjoint Nyquist derivative
        elif kind=='centered_fd':
            self.lap=np.sum(4*np.sin(ks/2)**2,axis=-1)
            self.q=np.sin(ks)
            self.q[np.abs(self.q)<1e-14]=0
        else: raise ValueError(kind)
        self.q2=np.sum(self.q**2,axis=-1)
    def apply(self,force):
        h=np.fft.fftn(force.reshape(self.n,self.n,self.n,3),axes=(0,1,2))
        dot=np.sum(self.q*h,axis=-1)
        pressure=np.divide(dot,self.q2,out=np.zeros_like(dot),where=self.q2>0)
        transverse=h-self.q*pressure[...,None]
        velocity=np.divide(transverse,self.mu*self.lap[...,None],out=np.zeros_like(h),where=self.lap[...,None]>0)
        return np.fft.ifftn(velocity,axes=(0,1,2)).real.reshape(-1,3)

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    contract={'question':'Does excess drag persist without LBM/time stepping using the same regularized boundary?',
              'n':32,'radius':4,'mu':.1,'mean_ux':1e-4,'marker_count':256,
              'operators':['spectral','centered_fd'],'cg_rtol':1e-9,'max_iterations':1200,
              'symmetry_relative_tolerance':1e-10,'plane_wave_relative_tolerance':1e-12,
              'marker_slip_relative_tolerance':1e-7,
              'claim':'exploratory discretization diagnostic; no sharp-boundary validation or LBM equivalence claim'}
    (OUT/'contract.json').write_text(json.dumps(contract,indent=2))
    checkpoint=ROOT/'stage36_runs/stage36al_periodic_drag_n32_massclosed_20260910/run_01/final_state.npz'
    assert sha(checkpoint)=='dccb7f7f4d17018384c72a4d7144cd9362804ed5822cd132141a0b8db9e28dce'
    files=[Path(__file__),checkpoint]+[ROOT/'stage36_staging'/p for p in ['periodic_drag_reference_fast_v1.py','periodic_drag_reference_v1.py','immersed_interface_v1.py','body_link_extractor_v1.py','moving_wall_reference_v1.py']]
    hashes={str(p):sha(p) for p in files}
    state=ref.initialize(32);J=state['matrix'];JT=J.T.tocsr();dim=J.shape[0]*3
    rng=np.random.default_rng(3602);x=rng.normal(size=dim);y=rng.normal(size=dim)
    rows=[];checks={}
    for kind in contract['operators']:
        mob=Mobility(32,.1,kind)
        def action(v): return (J@mob.apply(JT@v.reshape(-1,3))).ravel()
        A=LinearOperator((dim,dim),matvec=action,dtype=float)
        M=LinearOperator((dim,dim),matvec=lambda v:cho_solve(state['factor'],v.reshape(-1,3)).ravel(),dtype=float)
        symmetry=abs(x@action(y)-y@action(x))/max(abs(x@action(y)),abs(y@action(x)),1.)
        # An independently known divergence-free plane wave: force_y=sin(k*x).
        forcing=np.zeros((32,32,32,3));forcing[...,1]=np.sin(2*np.pi*np.arange(32)/32)[:,None,None]
        wave_lap=(2*np.pi/32)**2 if kind=='spectral' else 4*np.sin(np.pi/32)**2
        analytic=forcing/(.1*wave_lap)
        wave_error=np.max(np.abs(mob.apply(forcing.reshape(-1,3)).reshape(forcing.shape)-analytic))/np.max(np.abs(analytic))
        rhs=np.zeros((256,3));rhs[:,0]=-1e-4;history=[]
        def callback(v): history.append(float(np.linalg.norm(action(v)-rhs.ravel())/np.linalg.norm(rhs)))
        start=time.perf_counter()
        lam,info=cg(A,rhs.ravel(),M=M,rtol=1e-9,atol=0,maxiter=1200,callback=callback)
        elapsed=time.perf_counter()-start
        u=mob.apply(JT@lam.reshape(-1,3));u[:,0]+=1e-4
        slip=float(np.max(np.abs(J@u))/1e-4)
        force=-lam.reshape(-1,3).sum(axis=0)
        fd=6*np.pi*.1*4*1e-4*1.530329436009
        checks[kind+'_operator']=bool(symmetry<1e-10 and wave_error<1e-12 and x@action(x)>0)
        checks[kind+'_solve']=bool(info==0 and slip<1e-7)
        rows.append({'operator':kind,'solver_info':info,'iterations':len(history),'seconds':elapsed,
                     'symmetry_error':symmetry,'plane_wave_relative_error':float(wave_error),
                     'relative_marker_slip':slip,'force':force.tolist(),'drag_ratio':float(force[0]/fd),
                     'residual_history':history,'mean_velocity':u.mean(axis=0).tolist()})
    # Bound the constant-density approximation using the archived state, no new trajectory.
    f=np.load(checkpoint,allow_pickle=False)['f'];flat=f.reshape(19,-1)
    rho=flat.sum(axis=0);vel=(ref.C.T@flat).T/rho[:,None]
    rhs=-(J@vel)
    approx=cho_solve(state['factor'],rhs)
    exact=np.linalg.solve((J.multiply(1/rho)@JT).toarray(),rhs)
    density_test={'constraint_rhs_max':float(np.max(np.abs(rhs))),
                  'approx_vs_exact_force_abs_difference':float(np.max(np.abs((approx-exact).sum(axis=0)))),
                  'note':'post-projection checkpoint: tiny residual correction, not an independent transient force test'}
    checks['hashes_unchanged']=all(sha(p)==hashes[str(p)] for p in files)
    result={'status':'diagnostics_pass' if all(checks.values()) else 'diagnostics_failed','checks':checks,'operators':rows,
            'density_probe':density_test,'input_hashes':hashes,'contract_sha256':sha(OUT/'contract.json'),
            'python':platform.python_version(),'numpy':np.__version__,
            'promotion':False,'physical_validation':False}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'status':result['status'],'checks':checks,'results':[{k:r[k] for k in ['operator','solver_info','iterations','seconds','drag_ratio','relative_marker_slip']} for r in rows]},indent=2))
    if not all(checks.values()): raise SystemExit(1)

if __name__=='__main__': main()
