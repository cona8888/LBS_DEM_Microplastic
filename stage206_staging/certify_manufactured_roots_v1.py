"""Independently derive a second admissible root; do not change any gate.

The first root is prescribed in the manufactured fixture. A fully sticking
root is obtained from linear kinematic constraints, with feasible self-stress
chosen at the midpoint of analytically derived Coulomb-cone intervals.
No root is taken from a solver output or fitted to its velocity.
"""
from pathlib import Path
import os,time,traceback
import numpy as np
import authenticate_failed_system_v1 as source
import two_contact_cone_feasibility_v1 as candidate
import qualify_two_contact_held_v1 as independent
job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage206_evaluations/contact_failure_20260930'
OUT=BASE/'manufactured_root_certificate_01'

def run():
    d=api.read(job.DESIGN);job.verify(d)
    path=BASE/'controls_qualification_01/problem_31.json';problem=api.read(path)['problem'];s=problem['system']
    prior=api.read(path.parent/'results.json');api.require(not prior['passed'],'failed one-root comparison preserved')
    inputs={str(p):api.sha(p) for p in (path,path.parent/'results.json',job.DESIGN,Path(__file__),Path(candidate.__file__),Path(independent.__file__))}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs))
    try:
        v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')];mu,dt=s['friction'],s['dt_s']
        np.linalg.cholesky(M);A,z=J@M@J.T,J@v
        target=np.zeros(6);target[::3]=-g/dt
        fmin=np.linalg.lstsq(A,target-z,rcond=1e-12)[0]
        U,singular,Vh=np.linalg.svd(J.T);rank=int(sum(singular>singular[0]*1e-12));api.require(rank==5,'one-dimensional force self-stress')
        n=Vh[-1];scale=max(np.linalg.norm(fmin),1e-30);a=fmin/scale
        intervals=[];lo,hi=-np.inf,np.inf
        for k in range(2):
            i=3*k
            # mu^2 fn^2 - ||ft||^2 >= 0; each concave polynomial gives a closed interval.
            coeff=np.array([mu**2*a[i]**2-a[i+1:i+3]@a[i+1:i+3],
                            2*(mu**2*a[i]*n[i]-a[i+1:i+3]@n[i+1:i+3]),
                            mu**2*n[i]**2-n[i+1:i+3]@n[i+1:i+3]])
            api.require(coeff[2]<0,'bounded concave cone interval')
            roots=np.polynomial.Polynomial(coeff).roots();api.require(len(roots)==2 and np.isreal(roots).all(),'real cone boundaries')
            left,right=sorted(float(x.real) for x in roots)
            lo=max(lo,left);hi=min(hi,right)
            if n[i]>0:lo=max(lo,-a[i]/n[i])
            elif n[i]<0:hi=min(hi,-a[i]/n[i])
            else:api.require(a[i]>=0,'nonnegative constant normal force')
            intervals.append(dict(contact=k,quadratic_coefficients=coeff.tolist(),cone_interval=[left,right]))
        api.require(np.isfinite([lo,hi]).all() and lo<hi,'nonempty admissible self-stress interval')
        eta=(lo+hi)/2;fstick=(a+n*eta)*scale
        qstick=v+M@J.T@fstick
        fslide=np.asarray(problem['known_force']);qslide=v+M@J.T@fslide
        checks=[independent.audit(s,q,f) for q,f in ((qslide,dict(reactions=fslide)),(qstick,dict(reactions=fstick)))]
        steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(2)])
        with job.parent.fix.scope():
            gate=candidate.prior.algebra.job.fast.gate
            gate._finish(v,M,J,fslide,z,A,g,dt,mu,steps,0,'stage206_prescribed_root',{})
            gate._finish(v,M,J,fstick,z,A,g,dt,mu,steps,0,'stage206_linear_sticking_root',{})
            args=[v,M,J,g,dt,mu,1e-10,25000,time.time()+300]
            qo,ho=candidate.prior.solve(*args);qn,hn=candidate.solve(*args)
        exact=np.array_equal(qo,qn) and ho==hn
        error=float(np.linalg.norm(qn-qstick));err_free=error/max(np.linalg.norm(v),1e-15);err_known=error/max(np.linalg.norm(qstick),1e-15)
        api.require(all(c['passed'] for c in checks) and exact and err_free<=1e-8 and err_known<=1e-6,'both roots admissible; unchanged old branch agrees with independently derived sticking root')
        api.verify_mapping(inputs);job.verify(d)
        result=dict(passed=True,new_trajectory_steps=0,inputs=inputs,original_single_root_test_remains_failed=True,
                    prescribed_sliding_velocity=qslide.tolist(),linear_sticking_velocity=qstick.tolist(),prescribed_sliding_force=fslide.tolist(),linear_sticking_force=fstick.tolist(),
                    admissibility=checks,cone_intervals=intervals,common_interval=[lo,hi],self_stress_coordinate=eta,
                    root_separation=float(np.linalg.norm(qslide-qstick)),rank=rank,force_nullspace=n.tolist(),
                    old_new_solver_same_branch_exact=exact,selected_vs_linear_root_free_error=err_free,selected_vs_linear_root_known_error=err_known,
                    claim='Two admissible roots of the unchanged Coulomb system. A one-prescribed-root accuracy comparator assumed uniqueness incorrectly. No production gate relaxed; full selected/fine trajectory gates and an explicit root-selection limitation remain required.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
        print('MANUFACTURED_TWO_ROOTS_CERTIFIED',result['root_separation'],err_free,err_known,flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise

if __name__=='__main__':run()
