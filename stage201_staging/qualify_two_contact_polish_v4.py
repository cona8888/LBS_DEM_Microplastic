"""27-system covariance and complete fixed-pose requalification, zero steps."""
from pathlib import Path
import copy,os,time,traceback
import numpy as np
import two_contact_seeded_polish_v4 as candidate
import audit_two_contact_polish_v4 as auditor
import qualify_two_contact_held_v1 as held
source=candidate.algebra.source;job,api,ROOT,frozen=source.job,source.api,source.ROOT,source.frozen
BASE=ROOT/'stage201_evaluations/contact_repair_20260928';OUT=BASE/'polish_qualification_04'
PROTOCOL=ROOT/'stage201_designs/eight_hour_contact_repair_20260928/polish_qualification_04.json'


def run():
    w=api.read(source.WORK);stop=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<stop,'work window');d=api.read(job.DESIGN);job.verify(d)
    inputs=[source.OUT/'failed_systems.json',BASE/'extension_failure_audit_01/failed_systems.json'];packs=[api.read(f) for f in inputs]
    for f in inputs:api.require(api.sha(f)==api.read(f.parent/'results.json')['failed_systems_sha256'],'failed systems seal')
    files=inputs+[source.WORK,job.DESIGN]+list(Path(__file__).parent.glob('*.py'))
    p={'stage':'Stage201 same-law failure-only coordinate refinement qualification','new_trajectory_steps':0,'systems':27,'variants':162,'outer_calls':27,'normalized_covariance_velocity_error_max':1e-8,'unchanged_original_contact_and_force_gates':True,'production_authorized':False,'inputs':{str(f):api.sha(f) for f in files},'auditor_identity':auditor.STRUCTURAL_IDENTITY}
    job.commit(PROTOCOL,p);OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'protocol_sha256':api.sha(PROTOCOL)})
    reports=[];outer=[];failure=None
    try:
        with job.parent.fix.scope():
            systems=packs[0]['failed_inner_systems']+packs[1]['failed_inner_systems']
            for index,item in enumerate(systems):
                s=item['system'];reference=None;variants=[]
                for label,t,factor in held.variants(s):
                    args=[np.asarray(t[k]) for k in ('vfree','mobility','jacobian','gaps_m')]+[t['dt_s'],t['friction'],t['tolerance'],t['maxiter'],stop]
                    try:
                        q,h=candidate.solve(*args);a=held.audit(t,q,h)
                        if reference is None:reference=q.copy()
                        error=float(np.linalg.norm(q/factor-reference)/max(np.linalg.norm(s['vfree']),1e-15))
                        row={'passed':a['passed'] and error<=1e-8,'label':label,'audit':a,'error':error,'velocity':q.tolist(),'health':h}
                        if index<22 and label=='identity':api.require(q.tolist()==api.read(BASE/'held_qualification_01'/('system_%02d.json'%index))['variants'][0]['velocity'],'original scalar success remains exact')
                    except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as error:row={'passed':False,'label':label,'failure':repr(error)}
                    variants.append(row);reports.append(row)
                job.commit(OUT/('system_%02d.json'%index),{'variants':variants});print('POLISH_COVARIANCE',index,sum(r['passed'] for r in variants),'/',len(variants),flush=True)
        api.require(len(reports)==162 and all(r['passed'] for r in reports),'complete covariance prerequisite before outer tests')
        runtime=job.parent.engine.runtime;job.parent.b.old.parent.configure();frozen.pre.candidate.warm()
        for index,t in enumerate(packs[0]['failed_outer_trials']+packs[1]['failed_outer_trials']):
            api.require(time.time()<stop,'work cutoff');job.clear_telemetry();runtime._calls.clear();candidate.telemetry.clear();job.fast.capture_systems=True;runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
            start=time.perf_counter()
            with candidate.scope(runtime,True,stop),frozen.pre.candidate.scope('compiled_direct'),frozen.pre.baseline.repair.scope(runtime,True,stop),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,w['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
                answer=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
                fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':answer[0].tolist(),'active_contact_ids':[int(c[0]) for c in t['outer_inputs'][6]]}],
                   'sweep_certificates':[{'dt_s':t['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                   'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
            before={'state':{'q':t['outer_inputs'][0]}};check=auditor.evaluate(fixture,before)
            if index<22:api.require(fixture['rows']==api.read(BASE/'dispatch_qualification_03'/('fixture_%02d.json'%index))['fixture']['rows'],'old outer results exact')
            job.commit(OUT/('fixture_%02d.json'%index),{'fixture':fixture,'before':before});outer.append({'index':index,'passed':check['passed'],'audit':check,'seconds':time.perf_counter()-start});print('POLISH_OUTER',index,check['passed'],flush=True)
    except Exception as error:failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(p['inputs']);job.verify(d)
    result={'passed':failure is None and len(reports)==162 and all(r['passed'] for r in reports) and len(outer)==27 and all(r['passed'] for r in outer),'new_trajectory_steps':0,'covariance':reports,'outer':outer,'failure':failure,'protocol_sha256':api.sha(PROTOCOL),'claim':'Local held-system qualification only; failed extension stays failed and no new trajectory yet.'}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')});print('POLISH_QUALIFICATION',result['passed'],flush=True)


if __name__=='__main__':run()
