"""Bounded original-gap contact-mode feasibility, no trajectory integration."""
from pathlib import Path
import sys,time
import numpy as np
from scipy.optimize import brentq,least_squares
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage168_staging'))
import diagnose_frozen_contact_v3 as previous
c=previous.capture;api=c.api;hot=c.parent.b.old.hot
OUT=ROOT/'stage169_evaluations/original_gap_repair_20260923/reduced_probe_01'


def constraints(J,g,dt,mode,vs):
    rows=[];target=[]
    for k,m in enumerate(mode):
        if m:
            rows.append(J[3*k]);target.append(-g[k]/dt/vs)
        if m==1:
            rows.extend(J[3*k+1:3*k+3]);target.extend([0.,0.])
    C=np.asarray(rows);target=np.asarray(target)
    u,s,vh=np.linalg.svd(C,full_matrices=True);rank=sum(s>s[0]*1e-12)
    q0=vh[:rank].T@((u[:,:rank].T@target)/s[:rank]);N=vh[rank:].T
    if np.linalg.norm(C@q0-target)>1e-11*max(np.linalg.norm(target),1e-15):return None
    return q0,N


def force_basis(J,q,mode,mu):
    cols=[];mapping=[]
    w=J@q
    for k,m in enumerate(mode):
        if m==1:
            for j in range(3):
                col=np.zeros(len(w));col[3*k+j]=1;cols.append(col)
        elif m==2:
            col=np.zeros(len(w));col[3*k]=1
            vt=w[3*k+1:3*k+3];col[3*k+1:3*k+3]=-mu*vt/max(np.linalg.norm(vt),1e-300)
            cols.append(col)
    E=np.column_stack(cols)
    return E,J.T@E


def run():
    c.verify(api.read(c.DESIGN));r=api.read(c.OUT/'results.json')
    api.require(r['diagnostic_integrity_passed'],'matching capture')
    api.verify_mapping({s['path']:s['sha256'] for s in r['systems']})
    OUT.mkdir(parents=True,exist_ok=False)
    p=api.read(c.OUT/'system_002.json')
    v,M,J,A,z,g,steps=[np.asarray(p[k],float) for k in ['vfree','mobility','jacobian','A','z','gaps','steps']]
    dt,mu=p['dt'],p['friction'];B=np.linalg.inv(M);vs=np.linalg.norm(v);fs=np.linalg.norm(B@v)
    protocol={'source_sha256':api.sha(__file__),'matrix_sha256':api.sha(c.OUT/'system_002.json'),
        'original_gaps':g.tolist(),'unchanged_residual_gate':1e-10,'physical_changes':[],
        'one_stick_modes':3,'bracket_grid':'0 and +/- logspace(-11,2,79) in free-speed-scaled nullspace velocity',
        'all_slide_seed_count_max':24,'max_nfev_each':1000,'trajectory_steps':0}
    api.write(OUT/'protocol.json',protocol)
    reports=[];count=0
    def judge(f,mode,details):
        nonlocal count
        try:q,h=c.parent.fix.finish(v,M,J,f,z,A,g,dt,mu,steps,0,'reduced_mode_feasibility',{'mode':mode})
        except RuntimeError as error:record={'accepted':False,'error':str(error)}
        else:record={'accepted':True,'velocity':q,'health':h}
        record.update(force=f,mode=mode,**details);reports.append(record);count+=1
        return record['accepted']
    saved=hot.s50._residual;hot.s50._residual=hot.scalar.residual
    try:
        grid=np.sort(np.r_[0.,np.logspace(-11,2,79),-np.logspace(-11,2,79)])
        for stick in range(3):
            mode=[2,2,2];mode[stick]=1
            cn=constraints(J,g,dt,mode,vs)
            if cn is None:continue
            q0,N=cn;api.require(N.shape[1]==1,'one stick one null mode')
            def evaluate(beta):
                q=q0+N[:,0]*beta;E,H=force_basis(J,q,mode,mu);target=B@(vs*q-v)/fs
                determinant=float(np.linalg.det(np.column_stack([H,target])))
                return determinant,E,H,target
            values=[evaluate(b)[0] for b in grid];brackets=[]
            for j in range(len(grid)-1):
                if values[j]*values[j+1]<0:
                    beta=brentq(lambda x:evaluate(x)[0],grid[j],grid[j+1],xtol=1e-20,rtol=1e-14,maxiter=200)
                    val,E,H,target=evaluate(beta);f=E@np.linalg.lstsq(H,target,rcond=1e-12)[0]*fs
                    judge(f,mode,{'beta':beta,'determinant':val,'bracket':[grid[j],grid[j+1]]})
        # All sliding: eliminate velocity normal constraints and tangential forces.
        mode=[2,2,2];q0,N=constraints(J,g,dt,mode,vs)
        def fun(y):
            q=q0+N@y[:3];E,H=force_basis(J,q,mode,mu)
            return B@(vs*q-v)/fs-H@y[3:]
        def jac(y):
            q=q0+N@y[:3];w=J@q;JN=J@N;E,H=force_basis(J,q,mode,mu)
            D=B@N*vs/fs
            for k in range(3):
                vt=w[3*k+1:3*k+3];length=max(np.linalg.norm(vt),1e-300);direction=vt/length
                derivative=(np.eye(2)-np.outer(direction,direction))@JN[3*k+1:3*k+3]/length
                D+=mu*y[3+k]*J[3*k+1:3*k+3].T@derivative
            return np.column_stack([D,-H])
        seeds=[np.zeros(3),N.T@(v/vs-q0)]
        for magnitude in [1e-7,1e-3,1.]:
            seeds.extend([sign*magnitude*axis for axis in np.eye(3) for sign in [-1,1]])
        for idx,seed in enumerate(seeds):
            q=q0+N@seed;E,H=force_basis(J,q,mode,mu)
            fn=np.maximum(np.linalg.lstsq(H,B@(vs*q-v)/fs,rcond=1e-12)[0],1e-6)
            opt=least_squares(fun,np.r_[seed,fn],jac=jac,bounds=(np.r_[[-np.inf]*3,[0.]*3],np.inf),
                max_nfev=1000,ftol=1e-14,xtol=1e-14,gtol=1e-14,x_scale='jac')
            q=q0+N@opt.x[:3];E,H=force_basis(J,q,mode,mu);f=E@opt.x[3:]*fs
            judge(f,mode,{'seed':idx,'nfev':opt.nfev,'cost':opt.cost,'coordinates':opt.x,'velocity_parameter':q*vs})
    finally:hot.s50._residual=saved
    result={'accepted':any(r['accepted'] for r in reports),'candidates':reports,'production_changed':False,'trajectory_steps':0,
        'protocol_sha256':api.sha(OUT/'protocol.json')}
    c.verify(api.read(c.DESIGN));api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print('REDUCED',result['accepted'],'candidates',len(reports))
    for x in reports:
        if x['accepted']:print('PASS',x['mode'],x.get('beta'),x.get('seed'),x['health']['residual'])


if __name__=='__main__':run()
