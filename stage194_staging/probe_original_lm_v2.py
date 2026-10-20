"""Nonadvancing probes; correct observer binding and explicit original zero LM.

The zero-LM equations are the existing Stage53 equations, not a new contact law.
This does not install a production fallback or advance any trajectory.
"""
from pathlib import Path
import copy
import os
import time
import numpy as np
from scipy.optimize import root
import qualify_failure_codec_v1 as q

job, api = q.job, q.api
OUT = q.ROOT / 'stage194_evaluations/evidence_repair_20260924/primary_gate_02'
SOURCE = q.ROOT / 'stage194_evaluations/evidence_repair_20260924/contact_diagnosis_01/results.json'


def zero_lm(s):
    gate=job.fast.gate
    v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    dt,mu=s['dt_s'],s['friction']; A=J@M@J.T; z=J@v
    scale=max(np.linalg.norm(v),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(g))])
    scales=np.repeat(steps,3); scales[::3]=A.diagonal()[::3]
    def equations(u):
        f=u/scales; vc=z+A@f; residual=np.empty_like(u)
        for k in range(len(g)):
            i=3*k; vn=vc[i]+g[k]/dt
            residual[i]=np.hypot(u[i],vn)-u[i]-vn
            residual[i+1:i+3]=u[i+1:i+3]-steps[k]*gate._project(f[i+1:i+3],vc[i+1:i+3],steps[k],mu*f[i])
        return residual/scale
    opt=root(equations,np.zeros(len(z)),method='lm',options={'ftol':1e-14,'xtol':1e-14,'gtol':1e-14,'maxiter':50000})
    return gate._finish(v,M,J,opt.x/scales,z,A,g,dt,mu,steps,int(opt.nfev),'explicit_original_zero_lm',{'success':bool(opt.success),'message':str(opt.message)})


def run():
    work=api.read(q.WORK); api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work clock')
    api.require(api.read(SOURCE.parent/'completion.json')['results_sha256']==api.sha(SOURCE),'input seal')
    job.verify(api.read(job.DESIGN)); systems=api.read(SOURCE)['captured_systems']
    OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(p):api.sha(p) for p in (Path(__file__),q.WORK,SOURCE,q.ROOT/'stage53_staging/inertial_contact_multistart_lm_v1.py')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'maximum_solve_calls':6})
    reports=[]; hot=job.prior.p.hot; gate=job.fast.gate
    job.parent.b.old.parent.configure(); runtime=job.parent.engine.runtime
    runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
    with hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,work['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope():
        original=gate._finish; compiled=hot.PRIMARY.__globals__['_finish']; candidates=[]
        def observe(v,M,J,f,z,A,g,dt,mu,steps,it,solver,extra):
            scale=max(np.linalg.norm(v),1e-15); fs=max(np.linalg.norm(f),1e-30)
            e={'solver':solver,'force':f.tolist(),'extra':copy.deepcopy(extra),'residual':float(gate._residual(f,z,A,g,dt,mu,steps)/scale),
               'min_normal_relative':float(min(f[::3])/fs),'cone_excess_relative':float(max(np.linalg.norm(f[3*k+1:3*k+3])-mu*f[3*k] for k in range(len(g)))/fs)}
            try: answer=original(v,M,J,f,z,A,g,dt,mu,steps,it,solver,extra)
            except Exception as error:e.update(accepted=False,error=repr(error));raise
            else:e.update(accepted=True,health=answer[1]);return answer
            finally:candidates.append(e)
        gate._finish=observe;hot.PRIMARY.__globals__['_finish']=observe
        try:
            for method,index in [('portfolio',0)]+[('zero_lm',i) for i in range(5)]:
                api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work cutoff')
                candidates=[];s=systems[index];start=time.perf_counter()
                try:
                    if method=='zero_lm':answer=zero_lm(s)
                    else:
                        v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
                        answer=runtime.probe.RECOVERY.portfolio._solve(v,M,J,g,s['dt_s'],s['friction'],s['tolerance'],s['maxiter'])
                except Exception as error:outcome={'accepted':False,'error':repr(error)}
                else:outcome={'accepted':True,'velocity':answer[0].tolist(),'health':answer[1]}
                reports.append({'method':method,'system_index':index,'input_sha256':api.digest(s),'outcome':outcome,'candidates':copy.deepcopy(candidates),'seconds':time.perf_counter()-start})
                print('PROBE',method,index,outcome['accepted'],len(candidates),flush=True)
        finally:gate._finish=original;hot.PRIMARY.__globals__['_finish']=compiled
    api.verify_mapping(inputs);job.verify(api.read(job.DESIGN))
    job.commit(OUT/'results.json',{'new_trajectory_steps':0,'original_gates_unchanged':True,'inputs':inputs,'reports':reports,
                                 'claim':'Algebraic diagnostic only; primary probe is not a complete trajectory/runtime reproduction.'})
    job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})


if __name__=='__main__':run()
