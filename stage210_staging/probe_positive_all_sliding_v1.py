"""Bounded independent all-sliding equilibrium search with positive normals.

Normal kinematics are eliminated exactly. Six unknowns (three velocity-mode
coordinates and three normal forces) face the original force/velocity gates.
This is held algebra only, not a trajectory or production installation.
"""
from pathlib import Path
import os, time, traceback
import numpy as np
from scipy.optimize import least_squares
import authenticate_failed_system_v1 as source
import probe_exact_gap_modes_v1 as old_modes
job, api, ROOT=source.job,source.api,source.ROOT
OUT=ROOT/'stage210_evaluations/three_contact_failure_20261001/positive_all_sliding_01'


def probe(s, normals, end):
    v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')];dt,mu=s['dt_s'],s['friction']
    B=np.linalg.inv(M);fs=max(np.linalg.norm(B@v),1e-30);vs=max(np.linalg.norm(v),1e-15)
    A=J@M@J.T;z=J@v;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    C=J[::3];u,sv,vh=np.linalg.svd(C,full_matrices=True);api.require(sum(sv>sv[0]*1e-12)==3,'three independent original normal constraints')
    N=vh[3:].T;reports=[];rng=np.random.default_rng(210)
    for scale_name,qs in [('gap',max(np.max(np.abs(g/dt)),1e-30)),('free',vs)]:
        q0=vh[:3].T@((u.T@(-g/dt/qs))/sv);D=N*qs;contact_D=J@D
        def both(x):
            q=(q0+N@x[:3])*qs;vc=J@q;E=np.zeros((9,3));dE=[]
            for k in range(3):
                vt=vc[3*k+1:3*k+3];speed=np.linalg.norm(vt)
                direction=vt/max(speed,1e-30);gradient=(np.eye(2)-np.outer(direction,direction))@contact_D[3*k+1:3*k+3]/max(speed,1e-30)
                E[3*k,k]=1.;E[3*k+1:3*k+3,k]=-mu*direction
                derivative=np.zeros((9,3));derivative[3*k+1:3*k+3]=-mu*gradient;dE.append(derivative)
            rhs=B@(q-v)/fs;res=rhs-J.T@E@x[3:]
            jac=np.empty((6,6));jac[:,:3]=B@D/fs
            for k in range(3):jac[:,:3]-=J.T@dE[k]*x[3+k]
            jac[:,3:]=-J.T@E
            return res,jac,E@x[3:]*fs,q
        seeds=[np.zeros(3),np.ones(3),-np.ones(3)]+[a for row in np.eye(3) for a in (row,-row)]
        seeds.extend(rng.normal(size=3)*scale for scale in (.1,1.,10.,100.,1e4,1e6) for _ in range(2))
        for seed_index,y in enumerate(seeds):
            api.require(time.time()<end,'bounded all-sliding deadline')
            seed=np.r_[y,np.maximum(normals/fs,1e-6)]
            opt=least_squares(lambda x:both(x)[0],seed,jac=lambda x:both(x)[1],bounds=(np.r_[[-np.inf]*3,[0.]*3],np.full(6,np.inf)),
                              xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=1000,x_scale='jac')
            residual,_,f,prescribed=both(opt.x)
            row=dict(scale=scale_name,seed_index=seed_index,nfev=int(opt.nfev),cost=float(opt.cost),force=f.tolist(),prescribed_velocity=prescribed.tolist(),
                     original_residual=float(job.fast.gate._residual(f,z,A,g,dt,mu,steps)/vs),normalized_equilibrium_residual=float(np.linalg.norm(residual)))
            try:
                answer=job.fast.gate._finish(v,M,J,f,z,A,g,dt,mu,steps,int(opt.nfev),'stage210_held_positive_all_sliding',dict(original_gaps_preserved=True))
                audit,saved=old_modes.mixed.tests.audit(old_modes.mixed.tests.args(s),answer)
            except RuntimeError as error:row.update(passed=False,error=str(error))
            else:row.update(passed=True,audit=audit,saved_system=saved)
            reports.append(row)
            if row['passed']:return reports
    return reports


def run():
    d=api.read(job.DESIGN);job.verify(d);fp=source.OUT/'failed_systems.json';pp=source.OUT/'results.json';proof=api.read(pp)
    api.require(api.read(pp.parent/'completion.json')['results_sha256']==api.sha(pp) and api.sha(fp)==proof['failed_systems_sha256'],'authenticated held equations')
    stat=ROOT/'stage210_evaluations/three_contact_failure_20261001/static_force_feasibility_01/results.json'
    api.require(api.read(stat.parent/'completion.json')['results_sha256']==api.sha(stat),'static diagnostic sealed')
    inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,pp,stat,Path(old_modes.mixed.tests.independent.__file__))}
    OUT.mkdir(parents=True,exist_ok=False);end=time.time()+900
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0,maximum_wall_seconds=900,maximum_systems=3,maximum_calls_per_system=42,maximum_nfev_per_call=1000))
    reports=[]
    try:
        with job.parent.fix.scope():
            for index,item in enumerate(api.read(fp)['failed_inner_systems'][:3]):
                s=item['system'];api.require(api.digest(s)==item['system_sha256'],'unchanged original held system')
                static=api.read(stat)['reports'][index]['candidates'];normal=np.asarray(next(c for c in static if c['static_force_feasible'])['force'])[::3]
                candidates=probe(s,normal,end);passed=any(c['passed'] for c in candidates)
                row=dict(index=index,system_sha256=item['system_sha256'],passed=passed,candidates=candidates);reports.append(row)
                job.commit(OUT/('system_%02d.json'%index),row)
                print('POSITIVE_ALL_SLIDING',index,passed,len(candidates),min(c['normalized_equilibrium_residual'] for c in candidates),flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,original_gates_unchanged=True,reports=reports,passed=all(r['passed'] for r in reports),
                    claim='Bounded positive-force all-sliding equation search; unsuccessful search is not a global infeasibility proof. No trajectory, installed repair or gate amendment.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
