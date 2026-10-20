"""Zero-step feasibility probe, not a qualified repair.

Retract failed candidate tangential forces into the ORIGINAL Coulomb cone,
then require every unchanged finalizer and independently calculated gate.
No source solver, physics, input or tolerance is modified.
"""
from pathlib import Path
import copy,os,time,traceback
import numpy as np
import probe_held_system_v1 as prior
job,api,ROOT=prior.job,prior.api,prior.ROOT
import qualify_two_contact_held_v1 as independent
OUT=ROOT/'stage206_evaluations/contact_failure_20260930/cone_feasibility_01'

def run():
    d=api.read(job.DESIGN);job.verify(d)
    source=prior.source.OUT/'failed_systems.json';report=prior.OUT/'system_00.json'
    api.require(api.read(prior.OUT/'completion.json')['results_sha256']==api.sha(prior.OUT/'results.json'),'diagnostic seal')
    api.require(api.read(prior.OUT/'results.json')['inputs'][str(source)]==api.sha(source),'held source binding')
    s=api.read(source)['failed_inner_systems'][0]['system'];v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    dt,mu=s['dt_s'],s['friction'];A,z=J@M@J.T,J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(2)])
    unique=[]
    for c in api.read(report)['finalizer_candidates']:
        if c.get('error')=='direct contact cone violation' and c['force'] not in unique:unique.append(c['force'])
    api.require(0<len(unique)<=4,'bounded near-feasible candidates')
    inputs={str(p):api.sha(p) for p in (Path(__file__),source,report,Path(independent.__file__),job.DESIGN)}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs))
    rows=[]
    try:
        with job.parent.fix.scope():
            gate=prior.candidate.algebra.job.fast.gate
            for index,original in enumerate(unique):
                f0=np.asarray(original);cone=max(np.linalg.norm(f0[3*k+1:3*k+3])-mu*f0[3*k] for k in range(2))/np.linalg.norm(f0)
                for inward in (0.,np.finfo(float).eps,1e-14,1e-12):
                    f=f0.copy()
                    for k in range(2):
                        i=3*k;limit=mu*f[i]*(1-inward);tn=np.linalg.norm(f[i+1:i+3])
                        if tn>limit:f[i+1:i+3]*=limit/tn
                    row=dict(index=index,inward_fraction=inward,old_relative_cone_excess=float(cone),force=f.tolist(),relative_force_change=float(np.linalg.norm(f-f0)/np.linalg.norm(f0)))
                    try:
                        q,h=gate._finish(v,M,J,f,z,A,g,dt,mu,steps,0,'stage206_held_cone_feasibility',{})
                        check=independent.audit(s,q,h);row.update(accepted=check['passed'],velocity=q.tolist(),health=h,independent=check)
                    except RuntimeError as error:row.update(accepted=False,error=str(error))
                    rows.append(row)
                    print('CONE_FEASIBILITY',index,inward,row['accepted'],row.get('error',row.get('independent')),flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,rows=rows,accepted_candidates=sum(r['accepted'] for r in rows),
                    original_gates_unchanged=True,claim='A bounded held feasibility probe only. Not a qualified solver, covariance result, trajectory or campaign acceptance.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise

if __name__=='__main__':run()
