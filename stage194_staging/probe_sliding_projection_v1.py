"""Zero-step all-sliding force-elimination probe, original Coulomb equations."""
from pathlib import Path
import os,time
import numpy as np
from scipy.optimize import least_squares
import qualify_failure_codec_v1 as q

job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924';OUT=BASE/'sliding_projection_01'


def probe(s):
    v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    dt,mu=s['dt_s'],s['friction'];B=np.linalg.inv(M);load=B@v;fs=max(np.linalg.norm(load),1e-30)
    vs=max(np.linalg.norm(v),1e-15);qs=max(np.max(np.abs(g/dt)),vs*1e-15)
    A=J@M@J.T;z=J@v;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    C=J[::3];d=-g/dt/qs;u,sv,vh=np.linalg.svd(C,full_matrices=True)
    api.require(sv[-1]>sv[0]*1e-12,'three independent normals');q0=vh[:3].T@((u.T@d)/sv);N=vh[3:].T
    def both(y):
        vel=q0+N@y;vc=J@vel;E=np.zeros((9,3))
        for k in range(3):
            i=3*k;vt=vc[i+1:i+3];speed=np.linalg.norm(vt);E[i,k]=1.
            E[i+1:i+3,k]=-mu*vt/max(speed,1e-30)
        H=J.T@E;rhs=B@(vel*qs-v)/fs
        normal=np.linalg.lstsq(H,rhs,rcond=1e-12)[0]
        return H@normal-rhs,E@normal*fs
    rng=np.random.default_rng(194)
    seeds=[np.zeros(3),np.ones(3),-np.ones(3)]+[x for e in np.eye(3) for x in (e,-e)]+[rng.normal(size=3)*scale for scale in (.1,1.,10.,100.) for _ in range(12)]
    reports=[]
    for i,seed in enumerate(seeds):
        opt=least_squares(lambda y:both(y)[0],seed,jac='3-point',xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=1000,x_scale='jac')
        _,f=both(opt.x);gate=job.fast.gate
        e={'seed':i,'cost':float(opt.cost),'nfev':int(opt.nfev),'force':f.tolist(),'original_residual':float(gate._residual(f,z,A,g,dt,mu,steps)/vs)}
        try:answer=gate._finish(v,M,J,f,z,A,g,dt,mu,steps,int(opt.nfev),'stage194_sliding_projection_probe',{})
        except Exception as error:e.update(accepted=False,error=repr(error))
        else:e.update(accepted=True,velocity=answer[0].tolist(),health=answer[1])
        reports.append(e)
        if e['accepted']:break
    return reports


def run():
    work=api.read(q.WORK);api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work clock')
    systems=api.read(BASE/'contact_diagnosis_01/results.json')['captured_systems'];job.verify(api.read(job.DESIGN));OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(p):api.sha(p) for p in (Path(__file__),q.WORK,BASE/'contact_diagnosis_01/results.json')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'max_systems':5,'max_seeds_per_system':57,'max_nfev_per_call':1000})
    reports=[]
    with job.parent.fix.scope():
        for i,s in enumerate(systems):
            api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work cutoff');start=time.perf_counter()
            candidates=probe(s);passed=any(c['accepted'] for c in candidates)
            reports.append({'index':i,'input_sha256':api.digest(s),'candidates':candidates,'passed':passed,'seconds':time.perf_counter()-start})
            print('SLIDING_PROJECTION',i,passed,len(candidates),flush=True)
    api.verify_mapping(inputs);job.verify(api.read(job.DESIGN));job.commit(OUT/'results.json',{'new_trajectory_steps':0,'inputs':inputs,'systems':reports,'original_gates_unchanged':True})
    job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})


if __name__=='__main__':run()
