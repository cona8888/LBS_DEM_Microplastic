"""Bounded zero-step open/stick/slide variable-projection diagnostic.

Each active mode imposes its exact original gap kinematics. Open reactions
are identically zero; sticking force components and sliding normal reactions
are eliminated by linear least squares. Only the original gate accepts.
"""
from pathlib import Path
from itertools import product
import os,time
import numpy as np
from scipy.optimize import least_squares
import qualify_sliding_projection_v1 as tests
q=tests.q;job,api=q.job,q.api;BASE=tests.BASE;OUT=BASE/'mixed_projection_probe_01'

def probe(system,end):
    v,M,J,g,dt,mu,tol,maxiter=tests.args(system);B=np.linalg.inv(M);fs=max(np.linalg.norm(B@v),1e-30);vs=max(np.linalg.norm(v),1e-15)
    A=J@M@J.T;z=J@v;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    modes=sorted([m for m in product((0,1,2),repeat=3) if 0<sum(3 if a==1 else a==2 for a in m)<=6],key=lambda m:(sum(a==0 for a in m),sum(a==1 for a in m)))
    reports=[];rng=np.random.default_rng(194)
    for mode in modes:
        for scale_id,qs in [('gap',max(np.max(np.abs(g/dt)),vs*1e-15)),('free',vs)]:
            api.require(time.time()<end,'bounded algebraic deadline')
            ci=[];target=[]
            for k,m in enumerate(mode):
                if m:
                    ci.append(J[3*k]);target.append(-g[k]/dt/qs)
                    if m==1:ci.extend(J[3*k+1:3*k+3]);target.extend([0.,0.])
            C=np.array(ci);target=np.array(target);u,sv,vh=np.linalg.svd(C,full_matrices=True);rank=int(sum(sv>sv[0]*1e-12))
            q0=vh[:rank].T@((u[:,:rank].T@target)/sv[:rank]);N=vh[rank:].T;width=N.shape[1]
            if np.linalg.norm(C@q0-target)>1e-11*max(np.linalg.norm(target),1e-15):continue
            JN=J@N;rhsD=B@N*qs/fs
            def both(y):
                vel=q0+N@y;vc=J@vel;cols=[];dcols=[]
                for k,m in enumerate(mode):
                    if m==0:continue
                    if m==1:
                        for a in range(3):
                            col=np.zeros(9);col[3*k+a]=1.;cols.append(col);dcols.append(np.zeros((9,width)))
                    else:
                        vt=vc[3*k+1:3*k+3];speed=np.linalg.norm(vt)
                        direction=vt/max(speed,1e-30)
                        derivative=JN[3*k+1:3*k+3]/1e-30 if speed<=1e-30 else (np.eye(2)-np.outer(direction,direction))@JN[3*k+1:3*k+3]/speed
                        col=np.zeros(9);col[3*k]=1.;col[3*k+1:3*k+3]=-mu*direction
                        dc=np.zeros((9,width));dc[3*k+1:3*k+3]=-mu*derivative;cols.append(col);dcols.append(dc)
                E=np.column_stack(cols);H=J.T@E;hp=np.linalg.pinv(H,rcond=1e-12);rhs=B@(vel*qs-v)/fs;normal=hp@rhs;res=H@normal-rhs
                derivative=np.empty((6,width));P=np.eye(6)-H@hp
                for j in range(width):
                    dH=J.T@np.column_stack([c[:,j] for c in dcols])
                    derivative[:,j]=P@(dH@normal-rhsD[:,j])-hp.T@dH.T@res
                return res,derivative,E@normal*fs
            seeds=[np.zeros(width),np.ones(width),-np.ones(width)]+[x for row in np.eye(width) for x in (row,-row)]+[rng.normal(size=width)*s for s in (.1,1.,10.,100.) for _ in range(2)]
            candidates=[]
            for si,seed in enumerate(seeds):
                api.require(time.time()<end,'bounded algebraic deadline')
                try:
                    if width:
                        opt=least_squares(lambda y:both(y)[0],seed,jac=lambda y:both(y)[1],xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=300,x_scale='jac')
                        y,nfev,cost=opt.x,int(opt.nfev),float(opt.cost)
                    else:y=seed;nfev=0;cost=float(np.linalg.norm(both(y)[0])**2/2)
                    f=both(y)[2]
                    entry={'seed_index':si,'nfev':nfev,'cost':cost,'force':f.tolist()}
                    try:
                        answer=job.fast.gate._finish(v,M,J,f,z,A,g,dt,mu,steps,nfev,'stage194_mixed_projection_probe',{'contact_modes':list(mode),'original_gaps_preserved':True})
                        check,row=tests.audit(tests.args(system),answer)
                    except RuntimeError as e:entry.update(passed=False,error=str(e))
                    else:entry.update(passed=True,audit=check,saved_system=row)
                except (np.linalg.LinAlgError,ValueError,FloatingPointError) as e:entry={'seed_index':si,'passed':False,'error':repr(e),'cost':None}
                candidates.append(entry)
                if entry['passed']:
                    reports.append({'mode':list(mode),'scale':scale_id,'candidates':candidates});return reports
            reports.append({'mode':list(mode),'scale':scale_id,'candidates':candidates})
    return reports

def run():
    work=api.read(q.WORK);end=min(job.policy.utc(work['work_end_utc']).timestamp(),time.time()+300);api.require(time.time()<end,'work clock');job.verify(api.read(job.DESIGN))
    source=BASE/'dispatch_failure_audit_01/failure_details.json';systems=api.read(source)['captured_systems'];OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(x):api.sha(x) for x in [Path(__file__),source,q.WORK,Path(tests.__file__)]}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'max_systems':3,'max_wall_seconds':300,'max_nfev_per_seed':300})
    reports=[];job.parent.b.old.parent.configure()
    with job.prior.p.hot.scope(),job.parent.fix.scope():
        for i,s in enumerate(systems):
            api.require(time.time()<end,'work clock');start=time.perf_counter()
            modes=probe(s,end);passed=any(c['passed'] for m in modes for c in m['candidates'])
            reports.append({'index':i,'passed':passed,'modes':modes,'seconds':time.perf_counter()-start})
            print('MIXED_PROJECTION',i,passed,modes[-1]['mode'],modes[-1]['scale'],reports[-1]['seconds'],flush=True)
            job.commit(OUT/f'system_{i:02d}.json',reports[-1])
    api.verify_mapping(inputs);job.commit(OUT/'results.json',{'new_trajectory_steps':0,'passed':all(r['passed'] for r in reports),'reports':reports,'inputs':inputs,'unchanged_gates':True})
    job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})

if __name__=='__main__':run()
