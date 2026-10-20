"""Adversarial method provenance, manufactured equations and dispatch controls."""
from pathlib import Path
import copy,os,time,traceback
import numpy as np
import two_contact_seeded_polish_v4 as candidate
import audit_two_contact_polish_v4 as auditor
import qualify_two_contact_held_v1 as held
source=candidate.algebra.source;job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage201_evaluations/contact_repair_20260928';OUT=BASE/'polish_controls_04'
PROTOCOL=ROOT/'stage201_designs/eight_hour_contact_repair_20260928/polish_controls_04.json'


def run():
    w=api.read(source.WORK);stop=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<stop,'work cutoff');d=api.read(job.DESIGN);job.verify(d)
    files=[source.WORK,job.DESIGN]+list(Path(__file__).parent.glob('*.py'))
    for sub in ('polish_qualification_04','manufactured_qualification_02'):
        files+=list((BASE/sub).glob('*.json'));r=api.read(BASE/sub/'results.json');api.require(r['passed'] and api.read(BASE/sub/'completion.json')['results_sha256']==api.sha(BASE/sub/'results.json'),'prerequisite seal')
    p={'stage':'Stage201 failure-only polisher independent controls','new_trajectory_steps':0,'inputs':{str(f):api.sha(f) for f in files},'manufactured_cases':24,'physical_changes':[],'production_authorized':False}
    job.commit(PROTOCOL,p);OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'protocol_sha256':api.sha(PROTOCOL)})
    checks={};manufactured=[];guards=[];failure=None
    try:
        checks['identical_dispatch_bytecode']=candidate.scope.__wrapped__.__code__ is candidate.prior.scope.__wrapped__.__code__
        a,b=candidate.scope.__wrapped__,candidate.prior.scope.__wrapped__
        changes=[n for n in a.__code__.co_names if n in a.__globals__ and a.__globals__[n] is not b.__globals__.get(n)]
        checks['dispatch_only_solve_binding_changed']=changes==['solve']
        checks['identical_kernel_bytecode']=auditor.kernel.__code__ is job.kernel.evaluate.__code__
        changes=[n for n in auditor.kernel.__code__.co_names if n in auditor.kernel.__globals__ and auditor.kernel.__globals__[n] is not job.kernel.evaluate.__globals__.get(n)]
        checks['only_audit_association_changed']=changes==['association']
        old=candidate.prior.solve;sentinel=(np.arange(6.),{'original_scalar_success':True})
        try:
            candidate.prior.solve=lambda *args:sentinel
            checks['original_scalar_success_object_retained']=candidate.solve(None,None,None,None,None,None,None,None,None) is sentinel
        finally:candidate.prior.solve=old
        with job.parent.fix.scope():
            for i in range(24):
                f=api.read(BASE/'manufactured_qualification_02'/('problem_%02d.json'%i));s=f['system']
                args=[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')]+[s['dt_s'],s['friction'],1e-10,25000,stop]
                q,h=candidate.solve(*args);audit=held.audit(s,q,h)
                e=float(np.linalg.norm(q-f['known_velocity']));passed=audit['passed'] and e/max(np.linalg.norm(s['vfree']),1e-15)<=1e-8 and e/max(np.linalg.norm(f['known_velocity']),1e-15)<=1e-6
                manufactured.append({'passed':passed,'audit':audit})
        good=api.read(BASE/'polish_qualification_04/fixture_22.json')
        def change(value,key,replace):
            if isinstance(value,dict):
                if value.get('solver')==candidate.NAME:value[key]=copy.deepcopy(replace)
                for x in value.values():change(x,key,replace)
            elif isinstance(value,list):
                for x in value:change(x,key,replace)
        mutations=[('wrong_system','seeded_system_sha256','0'*64),('unbounded_seed','elimination_seed_index',100),('unbounded_mode','elimination_mode_index',100),('unbounded_iterations','elimination_nfev',2001),('false_failure','scalar_first_error','unrelated'),('wrong_rank','force_map_rank',6),('nonfinite_seed','seed_reactions',[[float('nan')]*6]),('lost_gaps','original_gaps_preserved',False),('invented_mode','contact_modes',[9,9])]
        for label,key,value in mutations:
            bad=copy.deepcopy(good['fixture']);change(bad,key,value)
            try:auditor.evaluate(bad,good['before'])
            except (RuntimeError,ValueError,KeyError,IndexError,AssertionError):guards.append({'test':label,'rejected':True})
            else:guards.append({'test':label,'rejected':False})
    except Exception as error:failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(p['inputs']);job.verify(d)
    r={'passed':failure is None and all(checks.values()) and len(manufactured)==24 and all(x['passed'] for x in manufactured) and len(guards)==9 and all(x['rejected'] for x in guards),'new_trajectory_steps':0,'checks':checks,'manufactured':manufactured,'guards':guards,'failure':failure,'protocol_sha256':api.sha(PROTOCOL)}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')});print('POLISH_CONTROLS',r['passed'],checks,flush=True)


if __name__=='__main__':run()
