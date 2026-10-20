"""Exact one-dimensional cone-feasibility intervals; no nonlinear optimizer."""
from pathlib import Path
import os,time
import numpy as np
import qualify_sliding_projection_v1 as tests
q=tests.q;job,api=q.job,q.api;BASE=tests.BASE;OUT=BASE/'cone_intervals_probe_01'

def probe(s):
    v,M,J,g,dt,mu,_,_=tests.args(s);B=np.linalg.inv(M);vs=max(np.linalg.norm(v),1e-15);fs=max(np.linalg.norm(B@v),1e-30)
    A=J@M@J.T;z=J@v;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)]);reports=[]
    for other in (2,0):
        for kother in range(3):
            mode=[other if k==kother else 1 for k in range(3)];ci=[];target=[]
            for k,m in enumerate(mode):
                if m:
                    ci.append(J[3*k]);target.append(-g[k]/dt/vs)
                    if m==1:ci.extend(J[3*k+1:3*k+3]);target.extend([0.,0.])
            C=np.asarray(ci);d=np.asarray(target);u,sv,vh=np.linalg.svd(C,full_matrices=True);rank=int(sum(sv>sv[0]*1e-12));q0=vh[:rank].T@((u[:,:rank].T@d)/sv[:rank]);N=vh[rank:].T
            mismatch=float(np.linalg.norm(C@q0-d));entry={'mode':mode,'constraint_rank':rank,'kinematic_mismatch':mismatch}
            if mismatch>1e-11*max(np.linalg.norm(d),1e-15):entry['incompatible']=True;reports.append(entry);continue
            cols=[];w=J@q0
            for k,m in enumerate(mode):
                if m==0:continue
                if m==1:
                    for j in range(3):a=np.zeros(9);a[3*k+j]=1.;cols.append(a)
                else:
                    a=np.zeros(9);a[3*k]=1.;a[3*k+1:3*k+3]=-mu*w[3*k+1:3*k+3]/max(np.linalg.norm(w[3*k+1:3*k+3]),1e-300);cols.append(a)
            E=np.column_stack(cols);H=J.T@E;u,sv,vh=np.linalg.svd(H,full_matrices=True);rank=int(sum(sv>sv[0]*1e-12));left=u[:,rank:].T;Z=vh[rank:].T
            if N.shape[1]:
                coef=np.linalg.lstsq(left@B@N*vs/fs,left@B@(v-q0*vs)/fs,rcond=1e-12)[0];q0=q0+N@coef
            rhs=B@(q0*vs-v)/fs;coeff=vh[:rank].T@((u[:,:rank].T@rhs)/sv[:rank]);f0=E@coeff;F=E@Z
            entry.update(force_rank=rank,force_nullity=Z.shape[1],left_balance=float(np.linalg.norm(left@rhs)),q0=q0.tolist())
            if Z.shape[1]!=1:reports.append(entry);continue
            fd=F[:,0];roots=[];polynomials=[]
            for k,m in enumerate(mode):
                if not m:continue
                i=3*k
                if fd[i]:roots.append(-f0[i]/fd[i])
                if m==1:
                    a=mu**2*fd[i]**2-np.dot(fd[i+1:i+3],fd[i+1:i+3]);b=2*(mu**2*f0[i]*fd[i]-np.dot(f0[i+1:i+3],fd[i+1:i+3]));c=mu**2*f0[i]**2-np.dot(f0[i+1:i+3],f0[i+1:i+3])
                    poly=[float(a),float(b),float(c)];polynomials.append({'contact':k,'quadratic':poly})
                    for r in np.roots(poly if a else poly[1:]):
                        if abs(np.imag(r))<1e-12:roots.append(float(np.real(r)))
            roots=sorted(set(roots));points=roots+[(a+b)/2 for a,b in zip(roots[:-1],roots[1:])]+([roots[0]-max(1,abs(roots[0])),roots[-1]+max(1,abs(roots[-1]))] if roots else [0.])
            candidates=[]
            for y in points:
                f=(f0+fd*y)*fs
                try:
                    answer=job.fast.gate._finish(v,M,J,f,z,A,g,dt,mu,steps,1,'stage194_cone_interval_probe',{'contact_modes':mode,'original_gaps_preserved':True})
                    check,row=tests.audit(tests.args(s),answer)
                except RuntimeError as e:candidates.append({'y':y,'passed':False,'error':str(e)})
                else:candidates.append({'y':y,'passed':True,'audit':check,'saved_system':row})
            entry.update(polynomials=polynomials,roots=roots,candidates=candidates);reports.append(entry)
    return reports

def run():
    w=api.read(q.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work clock');job.verify(api.read(job.DESIGN))
    source=BASE/'dispatch_failure_audit_01/failure_details.json';systems=api.read(source)['captured_systems'];OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(x):api.sha(x) for x in (Path(__file__),source,q.WORK)};job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'inputs':inputs})
    reports=[]
    with job.prior.p.hot.scope(),job.parent.fix.scope():
        for i,s in enumerate(systems):
            modes=probe(s);passed=any(c['passed'] for m in modes for c in m.get('candidates',[]));reports.append({'index':i,'passed':passed,'modes':modes});print('CONE_INTERVALS',i,passed,flush=True)
    api.verify_mapping(inputs);job.commit(OUT/'results.json',{'new_trajectory_steps':0,'inputs':inputs,'reports':reports});job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})

if __name__=='__main__':run()
