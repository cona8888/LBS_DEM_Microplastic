"""Zero-step quartic candidates for one-stick/one-slide two-contact modes.

Linear equilibrium and kinematics are eliminated without changing the gaps.
Squaring the scalar direction equation may add roots; ONLY the unchanged
original finalizer can accept a reconstructed force, never the polynomial.
"""
from pathlib import Path
import os
import time
import traceback
import numpy as np
from numpy.polynomial import Polynomial as Poly
from scipy.optimize import least_squares
import diagnose_two_contact_v1 as prior

job, api, source, ROOT = prior.job, prior.api, prior.source, prior.ROOT
OUT = ROOT / 'stage201_evaluations/contact_repair_20260928/two_contact_scalar_01'


def det(a,b):return a[0]*b[1]-a[1]*b[0]


def solve_modes(s, stop):
    v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    dt,mu=s['dt_s'],s['friction'];B=np.linalg.inv(M);load=B@v
    fs=max(np.linalg.norm(load),1e-30);vs=max(np.linalg.norm(v),1e-15)
    qs=max(np.max(np.abs(g/dt)),vs*1e-12)
    U,S,Vh=np.linalg.svd(J.T,full_matrices=True);rank=int(sum(S>S[0]*1e-12))
    api.require(rank==5,'two-contact rank-five domain')
    P=(Vh[:rank].T/S[:rank])@U[:,:rank].T;Z=Vh[rank:].T[:,0];E=U[:,rank:]
    A,z=J@M@J.T,J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(2)])
    reports=[]
    for stick,slide in ((0,1),(1,0)):
        api.require(time.time()<stop,'work cutoff')
        rows=[J[0],J[3],J[3*stick+1],J[3*stick+2]]
        rhs=[-g[0]/dt/qs,-g[1]/dt/qs,0.,0.]
        for row,val in zip(E.T@B,E.T@load/qs):
            norm=np.linalg.norm(row);rows.append(row/norm);rhs.append(val/norm)
        C,rhs=np.array(rows),np.array(rhs);u,sv,vh=np.linalg.svd(C,full_matrices=True)
        cr=int(sum(sv>sv[0]*1e-12));api.require(cr==5,'mixed-mode one-velocity-coordinate domain')
        q0=vh[:cr].T@((u[:,:cr].T@rhs)/sv[:cr]);N=vh[cr:].T[:,0]
        f0=P@(B@(q0*qs)-load)/fs;F=P@B@N*qs/fs
        cq0,cN=J@q0,J@N;i=3*slide
        tang0,tangN=cq0[i+1:i+3],cN[i+1:i+3]
        center=-float(tang0@tangN)/float(tangN@tangN)
        width=max(np.linalg.norm(tang0+center*tangN)/np.linalg.norm(tangN),1.)
        # x=center+width*t keeps a possible near-zero slip point well scaled.
        ft=[Poly([f0[j]+F[j]*center,F[j]*width]) for j in (i+1,i+2)]
        fn=Poly([f0[i]+F[i]*center,F[i]*width])
        vt=[Poly([tang0[j]+tangN[j]*center,tangN[j]*width]) for j in range(2)]
        aa=det(ft,Z[i+1:i+3]);bb=fn*det(vt,Z[i+1:i+3])+Z[i]*det(ft,vt)
        quartic=aa*aa*(vt[0]*vt[0]+vt[1]*vt[1])-mu*mu*bb*bb
        coeff=quartic.coef/max(np.max(np.abs(quartic.coef)),1e-300)
        roots=Poly(coeff).roots()
        seeds=[]
        for root in roots:
            if abs(root.imag)<=1e-5*max(1.,abs(root.real)):
                seeds.append(center+width*float(root.real))
        # Additional logarithmic seeds are a bounded diagnostic, not an
        # assumption that all real roots or physical solutions were found.
        seeds += [center+sign*width*10.**k for k in (0,2,4,6,8,10) for sign in (-1,1)]
        candidates=[]
        for k,x in enumerate(seeds):
            api.require(time.time()<stop,'work cutoff')
            vel=tang0+tangN*x;speed=np.linalg.norm(vel)
            if not speed:continue
            direction=vel/speed;base=f0+F*x
            av=base[i+1:i+3]+mu*base[i]*direction
            bv=Z[i+1:i+3]+mu*Z[i]*direction
            eta=-float(av@bv)/max(float(bv@bv),1e-300)
            xscale=max(abs(x),width,1.)
            def both(y):
                xx=x+y[0]*xscale;ee=eta+y[1]
                f=f0+F*xx+Z*ee;vel=tang0+tangN*xx;speed=np.linalg.norm(vel)
                if speed<1e-30:
                    direction=np.zeros(2);direction_derivative=np.zeros(2)
                else:
                    direction=vel/speed;direction_derivative=(np.eye(2)-np.outer(direction,direction))@tangN/speed
                residual=f[i+1:i+3]+mu*f[i]*direction
                jac=np.column_stack(((F[i+1:i+3]+mu*F[i]*direction+mu*f[i]*direction_derivative)*xscale,Z[i+1:i+3]+mu*Z[i]*direction))
                return residual,jac
            opt=least_squares(lambda y:both(y)[0],np.zeros(2),jac=lambda y:both(y)[1],xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=1000,x_scale='jac')
            xx=x+opt.x[0]*xscale;ee=eta+opt.x[1];f=(f0+F*xx+Z*ee)*fs
            entry={'seed':k,'scalar':float(xx),'eta':float(ee),'nfev':int(opt.nfev),'cost':float(opt.cost),'force':f.tolist(),'residual':float(job.fast.gate._residual(f,z,A,g,dt,mu,steps)/vs)}
            try:answer=job.fast.gate._finish(v,M,J,f,z,A,g,dt,mu,steps,int(opt.nfev),'stage201_held_scalar_two_contact',{'contact_modes':[1 if k==stick else 2 for k in range(2)]})
            except RuntimeError as error:entry.update(accepted=False,error=str(error))
            else:entry.update(accepted=True,velocity=answer[0].tolist(),health=answer[1])
            candidates.append(entry)
            if entry['accepted']:break
        reports.append({'stick':stick,'slide':slide,'quartic_coefficients':coeff.tolist(),'roots':[[float(x.real),float(x.imag)] for x in roots],'candidates':candidates})
        if any(x['accepted'] for x in candidates):break
    return reports


def run():
    w=api.read(source.WORK);stop=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<stop,'work window')
    d=api.read(job.DESIGN);job.verify(d)
    path=source.OUT/'failed_systems.json';r=api.read(source.OUT/'results.json')
    api.require(api.sha(path)==r['failed_systems_sha256'],'system seal')
    inputs={str(p):api.sha(p) for p in (source.WORK,Path(__file__),path,job.DESIGN)}
    OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'inputs':inputs,'maximum_modes':2,'maximum_seeds_per_mode':16,'maximum_nfev':1000})
    reports=[]
    try:
        with job.parent.fix.scope():
            for index,item in enumerate(api.read(path)['failed_inner_systems']):
                start=time.perf_counter();modes=solve_modes(item['system'],stop)
                passed=any(x['accepted'] for m in modes for x in m['candidates'])
                row={'index':index,'input_sha256':item['system_sha256'],'passed':passed,'modes':modes,'seconds':time.perf_counter()-start}
                reports.append(row);job.commit(OUT/('system_%02d.json'%index),row);print('SCALAR',index,passed,flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result={'new_trajectory_steps':0,'inputs':inputs,'accepted_systems':sum(r['passed'] for r in reports),'systems':reports,'original_gates_unchanged':True,'claim':'Held-system candidates only; no claim of exhaustive root isolation or trajectory qualification.'}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')});print('SCALAR_COMPLETE',result['accepted_systems'],flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0,'completed_systems':len(reports)});raise


if __name__=='__main__':run()
