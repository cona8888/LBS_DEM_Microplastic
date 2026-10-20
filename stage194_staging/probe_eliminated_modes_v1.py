"""Zero-step all-closed mode feasibility, exact original gap corrections.

Eliminate linear kinematics and force balance before solving sliding equations.
This avoids weighting a tiny contact velocity against an O(1) force balance.
Only unchanged final physical gates can accept a candidate.
"""
from pathlib import Path
from itertools import product
import os,time
import numpy as np
from scipy.optimize import least_squares
import qualify_failure_codec_v1 as q

job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924';OUT=BASE/'eliminated_modes_01'


def probe(s,near):
    v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    dt,mu=s['dt_s'],s['friction'];B=np.linalg.inv(M);load=B@v;fs=max(np.linalg.norm(load),1e-30)
    vs=max(np.linalg.norm(v),1e-15);qs=max(np.max(np.abs(g/dt)),vs*1e-15)
    A=J@M@J.T;z=J@v;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    u,sv,vh=np.linalg.svd(J.T,full_matrices=True)
    api.require(sv[-1]>sv[0]*1e-12,'full row rank original Jacobian')
    P=(vh[:6].T/sv)@u.T;Z=vh[6:].T
    reports=[];rng=np.random.default_rng(194)
    for mode in sorted(product([1,2],repeat=3),key=lambda m:sum(x==2 for x in m)):
        ci=[];target=[]
        for k in range(3):
            ci.append(J[3*k]);target.append(-g[k]/dt/qs)
            if mode[k]==1:ci.extend(J[3*k+1:3*k+3]);target.extend([0.,0.])
        C,d=np.array(ci),np.array(target);cu,cs,cvh=np.linalg.svd(C,full_matrices=True);rank=sum(cs>cs[0]*1e-12)
        q0=cvh[:rank].T@((cu[:,:rank].T@d)/cs[:rank]);N=cvh[rank:].T;width=N.shape[1]
        if np.max(np.abs(C@q0-d))>1e-11*max(np.max(np.abs(d)),1e-15):
            reports.append({'mode':list(mode),'kinematically_compatible':False});continue
        f0=P@(B@(q0*qs)-load)/fs;F=P@B@N*qs/fs;D=np.column_stack([F,Z])
        Q=np.column_stack([N,np.zeros((6,Z.shape[1]))]);cq0=J@q0;QD=J@Q
        def both(y):
            f=f0+D@y;vc=cq0+QD@y;res=[];jac=[]
            for k in range(3):
                if mode[k]!=2:continue
                i=3*k;vt=vc[i+1:i+3];speed=np.linalg.norm(vt)
                if speed<1e-30:direction=np.zeros(2);direction_derivative=np.zeros((2,len(y)))
                else:
                    direction=vt/speed;direction_derivative=(np.eye(2)-np.outer(direction,direction))@QD[i+1:i+3]/speed
                res.extend(f[i+1:i+3]+mu*f[i]*direction)
                jac.extend(D[i+1:i+3]+mu*(np.outer(direction,D[i])+f[i]*direction_derivative))
            return np.array(res),np.array(jac)
        velocity_near=v+M@J.T@near
        seedq=N.T@(velocity_near/qs-q0)
        seeds=[seedq,np.zeros(width),np.ones(width),-np.ones(width)]
        if width:
            seeds += [x for row in np.eye(width) for x in (row,-row)]
            seeds += [rng.normal(size=width) for _ in range(12)]
        candidates=[]
        for sk,seed in enumerate(seeds):
            eta=Z.T@(near/fs-f0-F@seed);initial=np.r_[seed,eta]
            opt=least_squares(lambda y:both(y)[0],initial,jac=lambda y:both(y)[1],method='trf',
                              xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=1000,x_scale='jac')
            f=(f0+D@opt.x)*fs;gate=job.fast.gate
            e={'seed':sk,'force':f.tolist(),'nfev':int(opt.nfev),'cost':float(opt.cost),
               'original_residual':float(gate._residual(f,z,A,g,dt,mu,steps)/vs),
               'min_normal_relative':float(min(f[::3])/max(np.linalg.norm(f),1e-30)),
               'cone_excess_relative':float(max(np.linalg.norm(f[3*k+1:3*k+3])-mu*f[3*k] for k in range(3))/max(np.linalg.norm(f),1e-30))}
            try:answer=gate._finish(v,M,J,f,z,A,g,dt,mu,steps,int(opt.nfev),'stage194_eliminated_mode_probe',{'mode':list(mode)})
            except Exception as error:e.update(accepted=False,error=repr(error))
            else:e.update(accepted=True,velocity=answer[0].tolist(),health=answer[1])
            candidates.append(e)
            if e['accepted']:break
        reports.append({'mode':list(mode),'kinematically_compatible':True,'candidates':candidates})
        if any(c['accepted'] for c in candidates):break
    return reports


def run():
    work=api.read(q.WORK);api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work clock')
    systems=api.read(BASE/'contact_diagnosis_01/results.json')['captured_systems'];old=api.read(BASE/'primary_gate_02/results.json')['reports'][1:]
    job.verify(api.read(job.DESIGN));OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(p):api.sha(p) for p in (Path(__file__),q.WORK,BASE/'contact_diagnosis_01/results.json',BASE/'primary_gate_02/results.json')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,
                                 'max_systems':5,'max_modes_per_system':8,'max_seeds_per_mode':22,'max_nfev_per_call':1000})
    reports=[]
    with job.parent.fix.scope():
        for i,s in enumerate(systems):
            api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work cutoff');start=time.perf_counter()
            modes=probe(s,np.array(old[i]['candidates'][0]['force']))
            passed=any(c['accepted'] for m in modes for c in m.get('candidates',[]))
            reports.append({'index':i,'input_sha256':api.digest(s),'modes':modes,'passed':passed,'seconds':time.perf_counter()-start})
            print('ELIMINATED',i,passed,flush=True)
    api.verify_mapping(inputs);job.verify(api.read(job.DESIGN))
    job.commit(OUT/'results.json',{'new_trajectory_steps':0,'inputs':inputs,'systems':reports,'original_gates_unchanged':True})
    job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})


if __name__=='__main__':run()
