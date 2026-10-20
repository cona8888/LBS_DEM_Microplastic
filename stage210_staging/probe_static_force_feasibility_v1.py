"""Held static-load cone feasibility, explicitly not a timestep solution.

Original gap constraints are retained for the subsequent original-gate check.
This separates a force-equilibrium candidate from an admissible contact update.
"""
from pathlib import Path
import os, traceback
import numpy as np
from scipy.optimize import minimize
import authenticate_failed_system_v1 as source
job, api, ROOT = source.job, source.api, source.ROOT
OUT=ROOT/'stage210_evaluations/three_contact_failure_20261001/static_force_feasibility_01'


def run():
    d=api.read(job.DESIGN);job.verify(d);fp=source.OUT/'failed_systems.json';pp=source.OUT/'results.json';proof=api.read(pp)
    api.require(api.read(pp.parent/'completion.json')['results_sha256']==api.sha(pp) and api.sha(fp)==proof['failed_systems_sha256'],'authenticated held inputs')
    inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,pp)}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0,maximum_systems=3,maximum_optimizer_calls_per_system=7,maximum_iterations=1000))
    reports=[]
    try:
        with job.parent.fix.scope():
            for index,item in enumerate(api.read(fp)['failed_inner_systems'][:3]):
                s=item['system'];api.require(api.digest(s)==item['system_sha256'],'exact saved system')
                v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')];mu,dt=s['friction'],s['dt_s']
                load=-np.linalg.solve(M,v);fs=max(np.linalg.norm(load),1e-30);H=J.T
                u,sv,vh=np.linalg.svd(H,full_matrices=True);api.require(sum(sv>sv[0]*1e-12)==6,'six independent load equations')
                f0=vh[:6].T@((u.T@(load/fs))/sv);N=vh[6:].T
                def constraints(y):
                    f=f0+N@y[:3];tau=y[3];ft=f.reshape(3,3)
                    return np.r_[ft[:,0]-tau,mu*ft[:,0]-np.linalg.norm(ft[:,1:],axis=1)-tau]
                candidates=[]
                for seed in [np.zeros(4)]+[np.r_[a,0.] for row in np.eye(3) for a in (row,-row)]:
                    opt=minimize(lambda y:-y[3],seed,method='SLSQP',bounds=[(-100,100)]*3+[(-100,100)],
                                 constraints=[dict(type='ineq',fun=constraints)],options=dict(maxiter=1000,ftol=1e-14))
                    f=(f0+N@opt.x[:3])*fs;cone=s['friction']*f[::3]-np.linalg.norm(f.reshape(3,3)[:,1:],axis=1)
                    balance=float(np.linalg.norm(J.T@f-load)/fs)
                    row=dict(optimizer_success=bool(opt.success),optimizer_message=str(opt.message),force=f.tolist(),static_force_balance=balance,
                             minimum_normal_force=float(min(f[::3])),minimum_cone_slack=float(min(cone)),normalized_minimum_slack=float(min(np.r_[f[::3],cone])/fs),
                             static_force_feasible=bool(min(f[::3])>=0 and min(cone)>=0 and balance<=1e-8))
                    A=J@M@J.T;z=J@v;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
                    try:answer=job.fast.gate._finish(v,M,J,f,z,A,g,dt,mu,steps,int(opt.nit),'stage210_static_force_diagnostic',dict(original_gaps_preserved=True))
                    except RuntimeError as error:row.update(original_timestep_gate_passed=False,original_timestep_error=str(error))
                    else:row.update(original_timestep_gate_passed=True,velocity=answer[0].tolist(),health=answer[1])
                    candidates.append(row)
                    if row['static_force_feasible']:break
                report=dict(index=index,system_sha256=item['system_sha256'],candidates=candidates,original_gaps_m=g.tolist())
                reports.append(report);job.commit(OUT/('system_%02d.json'%index),report)
                print('STATIC_FORCE',index,any(c['static_force_feasible'] for c in candidates),'original_timestep_pass',any(c['original_timestep_gate_passed'] for c in candidates),flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,reports=reports,
                    claim='Static load/cone feasibility alone is not a time-step contact solution; the unchanged original gap/residual finalizer remains required. No installed repair or production qualification.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
