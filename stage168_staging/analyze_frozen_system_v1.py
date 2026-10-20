"""Independent bounded algebraic comparison; never loaded by a runner.

Use the captured, unchanged contact matrices. Analytical derivatives and
dimensionless force coordinates test whether finite-difference LM stagnation
is a solver limitation. Every candidate must pass the original physical gates.
"""
from pathlib import Path
import sys,time,collections
import numpy as np
from scipy.optimize import least_squares
import diagnose_frozen_contact_v3 as captured
c=captured.capture;api=c.api;hot=c.parent.b.old.hot
OUT=c.OUT.with_name('algebraic_analysis_01')


def metrics(p,f):
    v,M,J,z,A,g,steps=[np.asarray(p[k],float) for k in ['vfree','mobility','jacobian','z','A','gaps','steps']]
    dt,mu=p['dt'],p['friction'];vs=max(np.linalg.norm(v),1e-15)
    residual=hot.scalar.residual(f,z,A,g,dt,mu,steps)/vs
    vc=z+A@f;cone=[mu*f[3*k]-np.linalg.norm(f[3*k+1:3*k+3]) for k in range(len(g))]
    q=v+M@J.T@f
    closure=np.linalg.norm(np.linalg.solve(M,q-v)-J.T@f)/max(np.linalg.norm(J.T@f),1e-30)
    return {'residual':float(residual),'cone_margin_N':cone,'cone_allowance_N':1e-12*max(np.linalg.norm(f),1e-30),
        'normal_forces_N':f[::3],'normal_gap_rate_m_s':vc[::3]+g/dt,'tangent_speed_m_s':np.linalg.norm(vc.reshape(-1,3)[:,1:],axis=1),
        'force_closure':closure,'q':q,'force':f}


def main():
    d=api.read(c.DESIGN);c.verify(d)
    r=api.read(c.OUT/'results.json');done=api.read(c.OUT/'completion.json')
    api.require(r['diagnostic_integrity_passed'] and done['results_sha256']==api.sha(c.OUT/'results.json'),'verified exact capture')
    api.verify_mapping({x['path']:x['sha256'] for x in r['systems']})
    OUT.mkdir(exist_ok=False)
    p=api.read(c.OUT/'system_002.json')
    v,M,J,z,A,g,steps=[np.asarray(p[k],float) for k in ['vfree','mobility','jacobian','z','A','gaps','steps']]
    dt,mu=p['dt'],p['friction'];vs=max(np.linalg.norm(v),1e-15);fs=max(np.linalg.norm(np.linalg.solve(M,v)),1e-30)
    B=A*fs/vs;zz=z/vs;gg=g/dt/vs;diag=np.diag(B);step=steps*fs/vs;eye=np.eye(len(z))

    def equations_and_jac(x):
        w=zz+B@x;out=np.empty(len(x));jac=np.empty((len(x),len(x)))
        for k in range(len(g)):
            i=3*k;normal=diag[i]*x[i];vn=w[i]+gg[k];radius=np.hypot(normal,vn)
            # Rationalized Fischer-Burmeister expression avoids cancellation.
            denominator=radius+normal+vn
            out[i]=-2*normal*vn/denominator if normal+vn>=0 and denominator>0 else radius-normal-vn
            jac[i]=(normal/radius-1)*diag[i]*eye[i]+(vn/radius-1)*B[i] if radius>0 else -diag[i]*eye[i]-B[i]
            tang=x[i+1:i+3]-w[i+1:i+3]/step[k];length=np.linalg.norm(tang);limit=mu*x[i]
            derivative=eye[i+1:i+3]-B[i+1:i+3]/step[k]
            if length<=limit:
                proj=tang;projected_jac=derivative
            else:
                direction=tang/max(length,1e-300)
                proj=limit*direction
                projected_jac=mu*np.outer(direction,eye[i])+limit/max(length,1e-300)*(np.eye(2)-np.outer(direction,direction))@derivative
            out[i+1:i+3]=step[k]*(x[i+1:i+3]-proj)
            jac[i+1:i+3]=step[k]*(eye[i+1:i+3]-projected_jac)
        return out,jac

    # Freeze bounded diagnostics before the first solve.
    seeds=[('pgs_lm',np.asarray(p['force'])/fs),('zero_lm',np.asarray(api.read(c.OUT/'system_003.json')['force'])/fs),
           ('preceding_force',np.asarray(api.read(c.OUT/'system_001.json')['force'])/fs)]
    protocol={'captured_result_sha256':api.sha(c.OUT/'results.json'),'matrix_sha256':api.sha(c.OUT/'system_002.json'),
        'source_sha256':api.sha(__file__),'max_nfev_each':1200,'seeds':[name for name,_ in seeds],
        'equations':'unchanged normal complementarity and Coulomb disk projection; analytical Jacobian, nondimensional force',
        'gate_residual':1e-10,'cone_relative_allowance':1e-12,'trajectory_calls':0,'physical_changes':[]}
    api.write(OUT/'protocol.json',protocol)
    tests=[]
    # Central finite differences at a non-boundary state audit the derivative.
    test=seeds[0][1]+np.linspace(.002,.010,9)
    h=1e-7;numeric=np.column_stack([(equations_and_jac(test+h*e)[0]-equations_and_jac(test-h*e)[0])/(2*h) for e in eye])
    jacerror=np.linalg.norm(numeric-equations_and_jac(test)[1])/max(np.linalg.norm(numeric),1e-30)
    api.require(jacerror<1e-6,'analytic Jacobian finite-difference check')
    saved=hot.s50._residual;hot.s50._residual=hot.scalar.residual
    try:
        for name,seed in seeds:
            started=time.perf_counter()
            lower=np.full(9,-np.inf);lower[::3]=0
            seed=seed.copy();seed[::3]=np.maximum(seed[::3],1e-12)
            opt=least_squares(lambda x:equations_and_jac(x)[0],seed,jac=lambda x:equations_and_jac(x)[1],
                bounds=(lower,np.inf),xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=1200,x_scale='jac')
            force=opt.x*fs;report=metrics(p,force)
            try:
                q,health=c.parent.fix.finish(v,M,J,force,z,A,g,dt,mu,steps,opt.nfev,'diagnostic_analytic_jacobian',{})
            except RuntimeError as error: report.update(accepted=False,error=str(error))
            else:report.update(accepted=True,health=health)
            report.update(seed=name,nfev=opt.nfev,njev=opt.njev,optimizer_message=opt.message,optimizer_success=bool(opt.success),wall_s=time.perf_counter()-started)
            tests.append(report)
    finally:hot.s50._residual=saved
    summaries=[]
    for row in r['systems']:
        p0=api.read(row['path']);m=metrics(p0,np.asarray(p0['force']))
        summaries.append({'path':row['path'],'sha256':row['sha256'],'solver':p0['solver'],'probe':p0['probe_id'],
            'accepted':p0['accepted'],'error':p0.get('error'),'extra':p0['extra'],**m})
    matrices={'mobility_condition':np.linalg.cond(M),'mobility_eigenvalues':np.linalg.eigvalsh(M),'J_singular_values':np.linalg.svd(J,compute_uv=False),
              'A_singular_values':np.linalg.svd(A,compute_uv=False),'A_rank':int(np.linalg.matrix_rank(A)),'J_rank':int(np.linalg.matrix_rank(J)),
              'normal_J_condition':np.linalg.cond(J[::3,:3]),'gaps_m':g,'gap_rates_m_s':g/dt,'free_speed_m_s':vs,'force_scale_N':fs}
    result={'diagnostic_only':True,'production_changed':False,'trajectory_steps':0,'jacobian_relative_check':jacerror,
        'matrices':matrices,'original_candidates':summaries,'independent_candidates':tests,
        'admissible_candidate_found':any(t['accepted'] for t in tests),'protocol_sha256':api.sha(OUT/'protocol.json')}
    c.verify(d);api.verify_mapping({x['path']:x['sha256'] for x in r['systems']})
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'fixed_pose_only':True})
    print('ANALYSIS',[(t['seed'],t['accepted'],t['residual'],t['nfev']) for t in tests],flush=True)


if __name__=='__main__':main()
