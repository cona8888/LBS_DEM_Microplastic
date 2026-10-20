"""Try qualified two-contact solves as full-three-contact candidates only.

Omitted reaction is exactly zero. Original full gap/normal/tangential gates and
independent audit are applied before any candidate can be reported accepted.
No altered physics, gap, finalizer, production installation or trajectory.
"""
from pathlib import Path
import itertools, os, time, traceback
import numpy as np
import authenticate_failed_system_v1 as source
import qualify_sliding_projection_v1 as tests
job,api,ROOT,frozen=source.job,source.api,source.ROOT,source.frozen
repair=frozen.stack.repair
OUT=ROOT/'stage210_evaluations/three_contact_failure_20261001/inactive_contact_elimination_01'


def run():
    d=api.read(job.DESIGN);job.verify(d);w=api.read(source.WORK);assert w['maximum_new_trajectory_steps']==0
    fp=source.OUT/'failed_systems.json';proof=api.read(source.OUT/'results.json');assert api.sha(fp)==proof['failed_systems_sha256']
    inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,Path(repair.__file__),Path(tests.__file__))}
    OUT.mkdir(parents=True,exist_ok=False);end=time.time()+900
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0,maximum_calls=9,maximum_wall_seconds=900))
    reports=[]
    try:
        with job.parent.fix.scope():
            gate=job.fast.gate
            for item in api.read(fp)['failed_inner_systems'][:3]:
                s=item['system'];assert api.digest(s)==item['system_sha256']
                args=tests.args(s);v,M,J,g,dt,mu,tol,maxiter=args
                z=J@v;A=J@M@J.T;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
                for keep in itertools.combinations(range(3),2):
                    assert time.time()<end
                    indices=np.array([3*k+j for k in keep for j in range(3)])
                    row=dict(system_sha256=item['system_sha256'],dt_s=dt,retained_contacts=list(keep),omitted_contact=next(k for k in range(3) if k not in keep),full_candidate_accepted=False)
                    begin=time.perf_counter()
                    try:
                        q,h=repair.solve(v,M,J[indices],g[list(keep)],dt,mu,tol,maxiter,end)
                        f=np.zeros(9);f[indices]=h['reactions']
                        row.update(reduced_solver_passed=True,reduced_health=h,embedded_force=f.tolist(),normal_next_velocities=(J[::3]@q+g/dt).tolist())
                        answer=gate._finish(v,M,J,f,z,A,g,dt,mu,steps,h['iterations'],'held_inactive_contact_candidate',{})
                        audit,saved=tests.audit(args,answer)
                        row.update(full_candidate_accepted=True,independent_audit=audit,full_saved_system=saved)
                    except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as error:row.update(error=repr(error))
                    row['wall_s']=time.perf_counter()-begin;reports.append(row)
                    print('EMBEDDED_PAIR',dt,keep,row['full_candidate_accepted'],row.get('error'),flush=True)
        api.verify_mapping(inputs);job.verify(d)
        r=dict(new_trajectory_steps=0,inputs=inputs,reports=reports,no_repair_installed=True,full_candidates_accepted=sum(z['full_candidate_accepted'] for z in reports),
               claim='Held candidates obtained by eliminating a zero-reaction contact. Any pass requires unchanged full three-contact finalizer and independent physical audit, not reduced-system success alone. No trajectory or campaign qualification.')
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json')))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0,reports=reports));raise


if __name__=='__main__':run()
