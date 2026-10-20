"""Independent dispatch controls and repeated manufactured/outer audits."""
from pathlib import Path
import copy,os,time,traceback
import numpy as np
import two_contact_scalar_dispatch_v3 as candidate
import audit_two_contact_dispatch_v3 as auditor
import qualify_two_contact_held_v1 as held
source=candidate.algebra.source;job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage201_evaluations/contact_repair_20260928';OUT=BASE/'dispatch_controls_03'
PROTOCOL=ROOT/'stage201_designs/eight_hour_contact_repair_20260928/dispatch_controls_03.json'


def run():
    w=api.read(source.WORK);stop=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<stop,'work cutoff');d=api.read(job.DESIGN);job.verify(d)
    files=[source.WORK,job.DESIGN]+list(Path(__file__).parent.glob('*.py'))
    for sub in ('dispatch_qualification_03','outer_qualification_02','manufactured_qualification_02'):
        files+=list((BASE/sub).glob('*.json'));r=api.read(BASE/sub/'results.json');api.require(r['passed'] and api.read(BASE/sub/'completion.json')['results_sha256']==api.sha(BASE/sub/'results.json'),'prerequisite seal '+sub)
    p={'stage':'Stage201 primary-failure scalar dispatch control qualification','new_trajectory_steps':0,'manufactured_systems':24,'outer_reaudits':22,'original_primary_success_must_be_unchanged':True,'equation_or_gate_changes':[],
       'inputs':{str(f):api.sha(f) for f in files},'production_authorized':False}
    job.commit(PROTOCOL,p);OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'protocol_sha256':api.sha(PROTOCOL),'new_trajectory_steps':0})
    checks={};manufactured=[];outer=[];failure=None
    try:
        checks['identical_numerical_solver_bytecode']=candidate.solve.__code__ is candidate.prior.solve.__code__
        changed=[n for n in candidate.solve.__code__.co_names if n in candidate.solve.__globals__ and candidate.solve.__globals__[n] is not candidate.prior.solve.__globals__.get(n)]
        checks['only_solver_name_global_changed']=changed==['NAME']
        checks['identical_kernel_bytecode']=auditor.kernel.__code__ is job.kernel.evaluate.__code__
        changed=[n for n in auditor.kernel.__code__.co_names if n in auditor.kernel.__globals__ and auditor.kernel.__globals__[n] is not job.kernel.evaluate.__globals__.get(n)]
        checks['only_association_global_changed']=changed==['association']
        runtime=job.parent.engine.runtime;portfolio=runtime.probe.RECOVERY.portfolio;saved=portfolio._solve
        sentinel=(np.arange(6.),{'unaltered_primary':True})
        try:
            portfolio._solve=lambda *args:sentinel;candidate.telemetry.clear()
            with candidate.scope(runtime,True,stop),runtime.repair_scope():
                checks['successful_primary_exact_object']=portfolio._solve(None,None,None,[0.,0.],1.,.3,1e-10,25000) is sentinel and not candidate.telemetry
            def unrelated(*args):raise RuntimeError('unrelated primary failure')
            portfolio._solve=unrelated;candidate.telemetry.clear()
            try:
                with candidate.scope(runtime,True,stop),runtime.repair_scope():portfolio._solve(None,None,None,[0.,0.],1.,.3,1e-10,25000)
            except RuntimeError as error:checks['unrelated_primary_failure_preserved']=str(error)=='unrelated primary failure' and not candidate.telemetry
            else:checks['unrelated_primary_failure_preserved']=False
        finally:portfolio._solve=saved
        for i in range(22):
            f=api.read(BASE/'dispatch_qualification_03'/('fixture_%02d.json'%i));a=auditor.evaluate(f['fixture'],f['before']);outer.append(a)
        with job.parent.fix.scope():
            for i in range(24):
                f=api.read(BASE/'manufactured_qualification_02'/('problem_%02d.json'%i));s=f['system']
                args=[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')]+[s['dt_s'],s['friction'],1e-10,25000,stop]
                q,h=candidate.solve(*args);a=held.audit(s,q,h)
                ev=float(np.linalg.norm(q-f['known_velocity'])/max(np.linalg.norm(s['vfree']),1e-15));eq=float(np.linalg.norm(q-f['known_velocity'])/max(np.linalg.norm(f['known_velocity']),1e-15))
                manufactured.append({'passed':a['passed'] and ev<=1e-8 and eq<=1e-6,'audit':a,'relative_free_error':ev,'relative_known_error':eq})
        old=api.read(BASE/'outer_qualification_02/results.json');new=api.read(BASE/'dispatch_qualification_03/results.json')
        speedup=sum(r['seconds'] for r in old['reports'])/sum(r['seconds'] for r in new['reports'])
        checks['unchanged_exact_22_outer_velocities']=all(api.read(BASE/'dispatch_qualification_03'/('fixture_%02d.json'%i))['fixture']['rows']==api.read(BASE/'outer_qualification_02'/('fixture_%02d.json'%i))['fixture']['rows'] for i in range(22))
    except Exception as error:failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure);speedup=None
    api.verify_mapping(p['inputs']);job.verify(d)
    r={'passed':failure is None and all(checks.values()) and len(manufactured)==24 and all(x['passed'] for x in manufactured) and len(outer)==22 and all(x['passed'] for x in outer),'new_trajectory_steps':0,'checks':checks,'manufactured':manufactured,'outer':outer,'held_outer_speedup':speedup,'failure':failure,'protocol_sha256':api.sha(PROTOCOL),'claim':'Numerical ordering/equation verification only. Trajectory comparison remains required.'}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')});print('DISPATCH_CONTROLS',r['passed'],'held speedup',speedup,flush=True)


if __name__=='__main__':run()
