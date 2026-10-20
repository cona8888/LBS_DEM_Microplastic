"""28 held systems, six covariance variants each, with independent equations."""
from pathlib import Path
import os,time,traceback
import numpy as np
import authenticate_failed_system_v1 as source
import two_contact_cone_feasibility_v1 as candidate
import qualify_two_contact_held_v1 as independent
job,api,ROOT=source.job,source.api,source.ROOT
OUT=ROOT/'stage206_evaluations/contact_failure_20260930/held_qualification_01'
CONTRACT=ROOT/'stage206_designs/contact_failure_20260930/local_qualification_01.json'

def run():
    d=api.read(job.DESIGN);job.verify(d);contract=api.read(CONTRACT)
    packs=[ROOT/'stage201_evaluations/contact_repair_20260928/failed_evidence_01/failed_systems.json',
           ROOT/'stage201_evaluations/contact_repair_20260928/extension_failure_audit_01/failed_systems.json',source.OUT/'failed_systems.json']
    for p in packs:api.require(api.read(p.parent/'results.json')['failed_systems_sha256']==api.sha(p),'sealed held systems')
    systems=[x for p in packs for x in api.read(p)['failed_inner_systems']]
    api.require(len(systems)==contract['maximum_systems']==28 and contract['maximum_new_trajectory_steps']==0,'zero-step bounded held contract')
    inputs={str(p):api.sha(p) for p in packs+[CONTRACT,job.DESIGN,Path(__file__),Path(candidate.__file__),Path(independent.__file__)]}
    stop=time.time()+contract['maximum_wall_seconds_per_held_probe']
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs))
    rows=[];failed=None
    try:
        with job.parent.fix.scope():
            for index,item in enumerate(systems):
                s=item['system'];api.require(api.digest(s)==item['system_sha256'],'held equation digest')
                reference=None;group=[]
                for label,t,factor in independent.variants(s):
                    args=[np.asarray(t[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]+[t['dt_s'],t['friction'],t['tolerance'],t['maxiter'],stop]
                    try:
                        q,h=candidate.solve(*args);check=independent.audit(t,q,h)
                        if reference is None:reference=q.copy()
                        error=float(np.linalg.norm(q/factor-reference)/max(np.linalg.norm(s['vfree']),1e-15))
                        old_exact=True
                        if index<27:
                            oq,oh=candidate.prior.solve(*args)
                            old_exact=bool(np.array_equal(q,oq) and h==oh)
                        row=dict(passed=check['passed'] and error<=contract['normalized_covariance_velocity_error_max'] and old_exact,
                                 label=label,independent=check,covariance_error=error,old_success_exact=old_exact,velocity=q.tolist(),health=h)
                    except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as error:
                        row=dict(passed=False,label=label,error=repr(error))
                    group.append(row);rows.append(row)
                job.commit(OUT/('system_%02d.json'%index),dict(input_sha256=item['system_sha256'],variants=group))
                print('HELD_QUALIFICATION',index,sum(r['passed'] for r in group),'/',len(group),flush=True)
        api.require(len(rows)==contract['maximum_covariance_variants']==168 and all(r['passed'] for r in rows),'all original physical and covariance gates')
    except Exception as error:
        failed=dict(error=repr(error),traceback=traceback.format_exc());job.commit(OUT/'failure.json',failed)
    api.verify_mapping(inputs);job.verify(d)
    result=dict(passed=failed is None and len(rows)==168 and all(r['passed'] for r in rows),new_trajectory_steps=0,inputs=inputs,
                variants=rows,failure=failed,claim='Held-system qualification only. Outer route, adversarial provenance and trajectory tests remain pending; Stage205 remains failed.')
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=result['passed'],results_sha256=api.sha(OUT/'results.json')))
    print('HELD_QUALIFICATION_COMPLETE',result['passed'],sum(r['passed'] for r in rows),'/',len(rows),flush=True)

if __name__=='__main__':run()
