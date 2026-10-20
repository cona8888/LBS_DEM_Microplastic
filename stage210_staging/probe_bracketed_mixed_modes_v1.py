"""Global bounded scalar bracketing for three closed one-stick/two-slip modes.

Exact original gap kinematics remove five velocity coordinates. The remaining
scalar is searched with signed equilibrium cofactors, avoiding least-squares
local minima. No change to original equations, contacts or acceptance gates.
"""
from pathlib import Path
import os, time, traceback
import numpy as np
from scipy.optimize import brentq
import authenticate_failed_system_v1 as source
import probe_exact_gap_modes_v1 as old_modes
job, api, ROOT = source.job, source.api, source.ROOT
OUT = ROOT/'stage210_evaluations/three_contact_failure_20261001/bracketed_mixed_modes_01'


def probe(s, end):
    v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    dt,mu=s['dt_s'],s['friction'];B=np.linalg.inv(M);fs=max(np.linalg.norm(B@v),1e-30)
    A=J@M@J.T;z=J@v;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    qs=max(np.max(np.abs(g/dt)),1e-30);reports=[]
    for sticking in range(3):
        rows=[];targets=[]
        for k in range(3):
            rows.append(J[3*k]);targets.append(-g[k]/dt/qs)
            if k==sticking:rows.extend(J[3*k+1:3*k+3]);targets.extend([0.,0.])
        C=np.asarray(rows);targets=np.asarray(targets);u,sv,vh=np.linalg.svd(C,full_matrices=True)
        api.require(sum(sv>sv[0]*1e-12)==5,'one-dimensional exact velocity mode')
        q0=vh[:5].T@((u[:,:5].T@targets)/sv);N=vh[5]
        def state(y):
            q=(q0+N*y)*qs;vc=J@q;columns=[]
            for k in range(3):
                if k==sticking:
                    for a in range(3):
                        e=np.zeros(9);e[3*k+a]=1.;columns.append(e)
                else:
                    vt=vc[3*k+1:3*k+3];speed=np.linalg.norm(vt)
                    if speed<=qs*1e-14:raise ValueError('sliding direction degenerate')
                    e=np.zeros(9);e[3*k]=1.;e[3*k+1:3*k+3]=-mu*vt/speed;columns.append(e)
            E=np.column_stack(columns);H=J.T@E;rhs=B@(q-v)/fs
            cofactor=np.array([(-1.)**i*np.linalg.det(np.delete(H,i,axis=0)) for i in range(6)])
            norm=np.linalg.norm(cofactor)
            if norm<=1e-14:raise ValueError('equilibrium basis rank deficient')
            signed=float(cofactor@rhs/norm)
            return signed,q,E,H,rhs
        grid=np.unique(np.r_[0.,np.logspace(-12,12,721),-np.logspace(-12,12,721)])
        # Include minima of each sliding tangential speed to resolve narrow
        # direction transitions in the scalar coordinate.
        extra=[]
        for k in range(3):
            if k==sticking:continue
            a=J[3*k+1:3*k+3]@q0;b=J[3*k+1:3*k+3]@N
            if b@b>0:
                y=-float(a@b/(b@b));extra.extend([y,y-1e-10,y+1e-10,y-1e-7,y+1e-7])
        grid=np.unique(np.r_[grid,extra]);values=[];roots=[];candidates=[]
        for y in grid:
            api.require(time.time()<end,'bounded scalar scan deadline')
            try:value=state(float(y))[0]
            except ValueError:value=None
            values.append(value)
        for left,right,fl,fr in zip(grid[:-1],grid[1:],values[:-1],values[1:]):
            if fl is None or fr is None or fl*fr>0:continue
            api.require(time.time()<end,'bounded scalar root deadline')
            try:
                y=brentq(lambda y:state(y)[0],float(left),float(right),xtol=1e-14,rtol=1e-14,maxiter=200)
                signed,q,E,H,rhs=state(y);f=E@np.linalg.lstsq(H,rhs,rcond=1e-13)[0]*fs
                if any(abs(y-r)<=1e-10*max(1.,abs(y)) for r in roots):continue
                roots.append(y)
                row=dict(y=y,signed_equilibrium_residual=signed,force=f.tolist(),prescribed_velocity=q.tolist(),
                         original_residual=float(job.fast.gate._residual(f,z,A,g,dt,mu,steps)/max(np.linalg.norm(v),1e-15)))
                try:
                    answer=job.fast.gate._finish(v,M,J,f,z,A,g,dt,mu,steps,0,'stage210_held_bracketed_mixed_mode',dict(original_gaps_preserved=True,sticking_contact=sticking))
                    audit,saved=old_modes.mixed.tests.audit(old_modes.mixed.tests.args(s),answer)
                except RuntimeError as error:row.update(passed=False,error=str(error))
                else:row.update(passed=True,audit=audit,saved_system=saved)
                candidates.append(row)
            except (ValueError,np.linalg.LinAlgError) as error:candidates.append(dict(passed=False,error=repr(error),bracket=[float(left),float(right)]))
        report=dict(sticking_contact=sticking,grid_points=len(grid),bounded_scalar_domain=[float(grid[0]),float(grid[-1])],roots=candidates,
                    passed=any(r['passed'] for r in candidates),exact_original_kinematic_constraint_residual=float(np.linalg.norm(C@q0-targets)))
        reports.append(report)
        if report['passed']:break
    return reports


def run():
    d=api.read(job.DESIGN);job.verify(d);fp=source.OUT/'failed_systems.json';pp=source.OUT/'results.json'
    proof=api.read(pp);api.require(api.read(pp.parent/'completion.json')['results_sha256']==api.sha(pp) and api.sha(fp)==proof['failed_systems_sha256'],'authenticated systems')
    inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,pp,Path(old_modes.mixed.tests.independent.__file__))}
    OUT.mkdir(parents=True,exist_ok=False);end=time.time()+900
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0,maximum_wall_seconds=900,maximum_systems=3,maximum_modes_per_system=3))
    reports=[]
    try:
        with job.parent.fix.scope():
            for index,item in enumerate(api.read(fp)['failed_inner_systems'][:3]):
                api.require(api.digest(item['system'])==item['system_sha256'],'exact unchanged held input')
                modes=probe(item['system'],end);passed=any(m['passed'] for m in modes)
                row=dict(index=index,system_sha256=item['system_sha256'],passed=passed,modes=modes)
                reports.append(row);job.commit(OUT/('system_%02d.json'%index),row)
                print('BRACKETED_MODE',index,passed,'roots',sum(len(m['roots']) for m in modes),flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,original_gates_unchanged=True,reports=reports,passed=all(r['passed'] for r in reports),
                    claim='Bounded scalar-root diagnosis of exact original one-stick/two-slip modes only. No global infeasibility proof, installed repair or trajectory qualification.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
