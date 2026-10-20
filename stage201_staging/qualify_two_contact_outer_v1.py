"""Full fixed-pose outer/contact association and adversarial audit; zero steps."""
from pathlib import Path
import copy,os,time,traceback
import two_contact_scalar_repair_v1 as candidate
import audit_two_contact_routes_v1 as auditor
source=candidate.algebra.source
job,api,ROOT,frozen=source.job,source.api,source.ROOT,source.frozen
OUT=ROOT/'stage201_evaluations/contact_repair_20260928/outer_qualification_01'
PROTOCOL=ROOT/'stage201_designs/eight_hour_contact_repair_20260928/outer_qualification_01.json'


def run():
    w=api.read(source.WORK);stop=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<stop,'work window')
    d=api.read(job.DESIGN);job.verify(d)
    sysfile=source.OUT/'failed_systems.json';api.require(api.sha(sysfile)==api.read(source.OUT/'results.json')['failed_systems_sha256'],'input seal')
    held=ROOT/'stage201_evaluations/contact_repair_20260928/held_qualification_01/results.json'
    api.require(api.read(held)['passed'] and api.read(held.parent/'completion.json')['results_sha256']==api.sha(held),'held independent qualification')
    paths=[source.WORK,job.DESIGN,sysfile,held]+list(Path(__file__).parent.glob('*.py'))
    p={'stage':'Stage201 zero-step full outer contact qualification','maximum_outer_calls':22,'new_trajectory_steps':0,'inputs':{str(x):api.sha(x) for x in paths},'sources':d['sources'],'original_numerical_and_physical_gates_unchanged':True,'auditor_route_identity':auditor.STRUCTURAL_IDENTITY,'production_authorized':False}
    job.commit(PROTOCOL,p);OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'protocol_sha256':api.sha(PROTOCOL),'new_trajectory_steps':0})
    runtime=job.parent.engine.runtime;job.parent.b.old.parent.configure();frozen.pre.candidate.warm()
    reports=[];fixtures=[];guards=[];failure=None
    try:
        for i,t in enumerate(api.read(sysfile)['failed_outer_trials']):
            api.require(time.time()<stop,'work cutoff');job.clear_telemetry();runtime._calls.clear();candidate.telemetry.clear();job.fast.capture_systems=True;runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
            started=time.perf_counter()
            with candidate.scope(runtime,True,stop),frozen.pre.candidate.scope('compiled_direct'),frozen.pre.baseline.repair.scope(runtime,True,stop),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,w['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
                answer=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
                fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':answer[0].tolist(),'active_contact_ids':[int(c[0]) for c in t['outer_inputs'][6]]}],
                   'sweep_certificates':[{'dt_s':t['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                   'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
            before={'state':{'q':t['outer_inputs'][0]}};check=auditor.evaluate(fixture,before)
            reports.append({'index':i,'passed':check['passed'],'seconds':time.perf_counter()-started,'audit':check,'new_candidate_calls':copy.deepcopy(candidate.telemetry)})
            fixtures.append({'fixture':fixture,'before':before});job.commit(OUT/('fixture_%02d.json'%i),fixtures[-1]);print('OUTER',i,check['passed'],len(candidate.telemetry),flush=True)
        good=fixtures[0]
        # Mutate every health copy so that metadata equality alone cannot reject
        # a corrupt method identity; route validation must catch it explicitly.
        def health_change(record,key,value):
            if isinstance(record,dict):
                if record.get('solver')==candidate.NAME:record[key]=value
                for item in record.values():health_change(item,key,value)
            elif isinstance(record,list):
                for item in record:health_change(item,key,value)
        changes=[('wrong_modes',lambda r:health_change(r,'contact_modes',[2,2])),('wrong_seed',lambda r:health_change(r,'scalar_mode_seed',999)),
          ('wrong_original_gaps',lambda r:health_change(r,'original_gaps_preserved',False)),('wrong_stateless',lambda r:health_change(r,'stateless_same_system',False)),
          ('drop_fallback',lambda r:r['fallback_systems'].pop()),('drop_primary_failure',lambda r:r['result']['stage119_repair_calls'][0].update(original_exception='unrelated')),
          ('corrupt_velocity',lambda r:r['rows'][0]['velocity_generalized'].__setitem__(0,1.))]
        for name,mutate in changes:
            bad=copy.deepcopy(good['fixture']);mutate(bad)
            try:auditor.evaluate(bad,good['before'])
            except (RuntimeError,ValueError,KeyError,IndexError,AssertionError):guards.append({'test':name,'passed':True})
            else:guards.append({'test':name,'passed':False})
    except Exception as error:
        failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    r={'passed':failure is None and len(reports)==22 and all(x['passed'] for x in reports+guards),'new_trajectory_steps':0,'reports':reports,'guards':guards,'failure':failure,'protocol_sha256':api.sha(PROTOCOL),'artifacts':{str(x):api.sha(x) for x in OUT.glob('*.json')},'claim':'Fixed-pose qualification only; no trajectory or production acceptance.'}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')});print('OUTER_QUALIFICATION',r['passed'],len(reports),flush=True)


if __name__=='__main__':run()
