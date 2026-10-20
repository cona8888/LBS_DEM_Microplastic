"""Signed all-sliding branch search after exact translational elimination.

Original three normal constraints retained. Signed forces help expose roots
hidden by positivity-constrained minimization; only original full finalizer
and independent audit may admit a candidate. Bounded search, not root census.
"""
from pathlib import Path
import os,time,traceback
import numpy as np
from scipy.optimize import root
import authenticate_failed_system_v1 as source
import qualify_sliding_projection_v1 as tests
job,api,ROOT=source.job,source.api,source.ROOT
OUT=ROOT/'stage210_evaluations/three_contact_failure_20261001/signed_sliding_elimination_01'


def probe(s,end,gate):
    args=tests.args(s);v,M,J,g,dt,mu,tol,maxiter=args
    B=np.linalg.inv(M);N=J[::3];T=np.linalg.solve(N[:,:3],-g/dt);R=-np.linalg.solve(N[:,:3],N[:,3:])
    Q=np.vstack([R,np.eye(3)]);qs=max(np.max(abs(g/dt)),1e-30);vs=max(np.linalg.norm(v),1e-15)
    fs=max(np.linalg.norm(B@v),1e-30)
    z=J@v;A=J@M@J.T;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    candidates=[];attempts=[]
    rng=np.random.default_rng(210)
    directions=[*np.eye(3),*-np.eye(3),v[3:]/max(np.linalg.norm(v[3:]),1e-30)]
    directions += [r/np.linalg.norm(r) for r in rng.normal(size=(20,3))]
    for scale in (qs,vs):
        def evaluate(y):
            q=np.r_[T+R@(scale*y),scale*y];vc=J@q;E=np.zeros((9,3))
            for k in range(3):
                vt=vc[3*k+1:3*k+3];speed=np.linalg.norm(vt)
                if speed<1e-300:raise ValueError('undefined sliding direction')
                E[3*k,k]=1.;E[3*k+1:3*k+3,k]=-mu*vt/speed
            load=B@(q-v);F=J.T@E;fn=np.linalg.solve(F[:3],load[:3]);force=E@fn
            return (F[3:]@fn-load[3:])/fs,q,force
        for seed in directions:
            if time.time()>=end:raise RuntimeError('bounded held clock')
            def fun(y):
                try:return evaluate(y)[0]
                except (ValueError,np.linalg.LinAlgError):return np.full(3,1e6)
            sol=root(fun,seed,method='hybr',options={'xtol':1e-11,'maxfev':350})
            try:r,q,f=evaluate(sol.x)
            except (ValueError,np.linalg.LinAlgError):continue
            residual=float(np.linalg.norm(r));attempts.append(dict(rotation_scale=scale,nfev=int(sol.nfev),success=bool(sol.success),equilibrium_residual=residual))
            if residual>1e-8 or any(np.linalg.norm(q-c['velocity'])<1e-7*max(np.linalg.norm(q),qs) for c in candidates):continue
            c=dict(velocity=q.tolist(),force=f.tolist(),signed_normal_forces=f[::3].tolist(),equilibrium_residual=residual,original_gate_pass=False)
            # Enforce the exact disk rather than retaining tiny multiplication
            # overflow. Every original finalizer criterion still applies.
            projected=f.copy()
            if np.all(f[::3]>=0):
                for k in range(3):
                    i=3*k;length=np.linalg.norm(f[i+1:i+3]);radius=mu*f[i]
                    if length>radius:projected[i+1:i+3]*=radius/length
                c['relative_force_retraction']=float(np.linalg.norm(projected-f)/max(np.linalg.norm(f),1e-30))
            try:
                assert np.linalg.norm(projected-f)/max(np.linalg.norm(f),1e-30)<=1e-10
                answer=gate._finish(v,M,J,projected,z,A,g,dt,mu,steps,int(sol.nfev),'held_signed_sliding_elimination',{})
                audit,saved=tests.audit(args,answer);c.update(original_gate_pass=True,independent_audit=audit,saved_system=saved)
            except (AssertionError,RuntimeError,ValueError) as error:c['gate_error']=repr(error)
            candidates.append(c)
    return dict(attempts=attempts,candidates=candidates,original_gate_passes=sum(c['original_gate_pass'] for c in candidates))


def run():
    d=api.read(job.DESIGN);job.verify(d);w=api.read(source.WORK);assert w['maximum_new_trajectory_steps']==0
    fp=source.OUT/'failed_systems.json';proof=api.read(source.OUT/'results.json');assert api.sha(fp)==proof['failed_systems_sha256']
    inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,Path(tests.__file__))}
    OUT.mkdir(parents=True,exist_ok=False);end=time.time()+900
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0,maximum_wall_seconds=900,maximum_root_calls=162))
    rows=[]
    try:
        with job.parent.fix.scope():
            for item in api.read(fp)['failed_inner_systems'][:3]:
                assert api.digest(item['system'])==item['system_sha256']
                r=probe(item['system'],end,job.fast.gate);r.update(system_sha256=item['system_sha256'],dt_s=item['system']['dt_s']);rows.append(r)
                print('SIGNED_SLIDING',r['dt_s'],len(r['candidates']),r['original_gate_passes'],flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,systems=rows,no_repair_installed=True,
                    claim='Bounded signed all-sliding branch search only; no exhaustive root census/global infeasibility proof. Candidate admissibility requires unchanged original gates and independent audit; no production or trajectory qualification.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json')))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0,systems=rows));raise


if __name__=='__main__':run()
