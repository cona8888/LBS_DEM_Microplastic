"""Zero-step analytic-Jacobian solution of unchanged contact complementarity.

No trajectory or production installation. All candidates face Stage158/50 gates.
"""
from pathlib import Path
import os
import time
import numpy as np
from scipy.optimize import least_squares, root
import qualify_failure_codec_v1 as q

job,api=q.job,q.api
BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924'
OUT=BASE/'analytic_contact_01'


def system(v,M,J,g,dt,mu):
    A=J@M@J.T;z=J@v;vs=max(np.linalg.norm(v),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(g))])
    scales=np.repeat(steps,3);scales[::3]=A.diagonal()[::3]
    H=A/scales[None,:]; zv=z/vs; gap=g/dt/vs; eye=np.eye(len(z))
    def both(y):
        vc=zv+H@y;result=np.empty(len(y));jac=np.empty_like(H)
        for k in range(len(g)):
            i=3*k;n=y[i];vn=vc[i]+gap[k];norm=np.hypot(n,vn)
            if norm:
                result[i]=norm-n-vn;jac[i]=(n/norm-1)*eye[i]+(vn/norm-1)*H[i]
            else:result[i]=0.;jac[i]=-eye[i]-H[i]
            # Tangential force coordinates multiplied by each contact's mobility.
            x=y[i+1:i+3]-vc[i+1:i+3];r=mu*y[i]*steps[k]/scales[i];speed=np.linalg.norm(x)
            dx=eye[i+1:i+3]-H[i+1:i+3]
            if r<=0:
                result[i+1:i+3]=y[i+1:i+3];jac[i+1:i+3]=eye[i+1:i+3]
            elif speed<=r:
                result[i+1:i+3]=vc[i+1:i+3];jac[i+1:i+3]=H[i+1:i+3]
            else:
                direction=x/speed; dr=mu*steps[k]/scales[i]*eye[i]
                result[i+1:i+3]=y[i+1:i+3]-r*direction
                jac[i+1:i+3]=eye[i+1:i+3]-np.outer(direction,dr)-r/speed*(np.eye(2)-np.outer(direction,direction))@dx
        return result,jac
    return both,A,z,steps,scales,vs


def run():
    work=api.read(q.WORK);api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work clock')
    systems=api.read(BASE/'contact_diagnosis_01/results.json')['captured_systems']
    old=api.read(BASE/'primary_gate_02/results.json')['reports'][1:]
    job.verify(api.read(job.DESIGN));OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(p):api.sha(p) for p in (Path(__file__),q.WORK,BASE/'contact_diagnosis_01/results.json',BASE/'primary_gate_02/results.json')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'maximum_optimizer_calls':20,'maximum_nfev_per_call':2000})
    reports=[]
    with job.parent.fix.scope():
        for index,s in enumerate(systems):
            v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
            dt,mu=s['dt_s'],s['friction'];both,A,z,steps,scales,vs=system(v,M,J,g,dt,mu)
            closest=np.asarray(old[index]['candidates'][0]['force'])*scales/vs
            outputs=[]
            for seedname,seed in [('zero',np.zeros(len(z))),('existing_failed',closest)]:
                for method in ['lm','trf']:
                    api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work cutoff')
                    start=time.perf_counter()
                    opt=least_squares(lambda y:both(y)[0],seed,jac=lambda y:both(y)[1],method=method,
                                      xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=2000,x_scale='jac')
                    f=opt.x*vs/scales;gate=job.fast.gate
                    e={'seed':seedname,'method':method,'nfev':int(opt.nfev),'optimality':float(opt.optimality),'cost':float(opt.cost),
                       'force':f.tolist(),'original_residual':float(gate._residual(f,z,A,g,dt,mu,steps)/vs)}
                    try:answer=gate._finish(v,M,J,f,z,A,g,dt,mu,steps,int(opt.nfev),'stage194_analytic_probe',{})
                    except Exception as error:e.update(accepted=False,error=repr(error))
                    else:e.update(accepted=True,velocity=answer[0].tolist(),health=answer[1])
                    e['seconds']=time.perf_counter()-start;outputs.append(e)
                    print('ANALYTIC',index,seedname,method,e['accepted'],e['original_residual'],flush=True)
            reports.append({'index':index,'input_sha256':api.digest(s),'candidates':outputs})
    api.verify_mapping(inputs);job.verify(api.read(job.DESIGN))
    job.commit(OUT/'results.json',{'new_trajectory_steps':0,'inputs':inputs,'systems':reports,'original_gates_unchanged':True})
    job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})


if __name__=='__main__':run()
