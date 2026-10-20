"""Exactly 1,000 reserved diagnostic steps from an audited repaired state.

cProfile includes solver, observer, serializer and archive work. Timings are
instrumented and must not be promoted as an uninstrumented runtime forecast.
"""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import cProfile, io, os, pstats, shutil, sys, time, traceback
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage195_staging'))
import qualify_repaired_stack_v1 as pre
job,api,q=pre.job,pre.api,pre.q
WORK=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/contract_01.json'
DESIGN=WORK.with_name('segment_profile_01.json')
RUN=ROOT/'stage196_runs/deadline_recovery_20260925/segment_profile_01'
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/segment_profile_01'

def run():
    w=api.read(WORK);d=api.read(job.DESIGN);job.verify(d)
    api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc']),'launch clock')
    for p in psutil.process_iter(['pid','name','cmdline']):
        if p.pid!=os.getpid() and 'python' in (p.info['name'] or '').lower():
            api.require('matdem_microplastic' not in ' '.join(p.info['cmdline'] or []).lower(),'exclusive diagnostic')
    # This is the first accepted-step reservation of the new window.
    for root in [ROOT/'stage196_runs',Path('D:/MATDEM_MICROPLASTIC/stage196_runs')]:
        if root.exists():
            for p in root.rglob('launch.json'):
                api.require(api.read(p).get('reserved_new_accepted_steps',0)==0,'first diagnostic ledger is empty')
    api.require(shutil.disk_usage(ROOT).free>w['minimum_free_disk_bytes']+2*q.repair.base.MAX_RAW,'disk reserve')
    case,before=pre.stress_seed(d)
    paths=[WORK,Path(__file__),job.DESIGN,Path(d['stress_seed_design']),Path(d['stress_seed_raw']),Path(d['stress_oracle_design']),Path(d['stress_oracle_raw'])]
    protocol={'stage':'Stage196 full transaction profile','maximum_new_steps':1000,'input_checkpoint_sha256':api.digest(before),'case':case['id'],
        'inputs':{str(p):api.sha(p) for p in paths},'sources':d['sources'],'integration_code_sha256':q.campaign.code_sha(pre.wrapper.raw_execute),
        'physical_changes':[],'production_authorized':False}
    job.commit(DESIGN,protocol);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(minutes=20),job.policy.utc(w['last_diagnostic_launch_utc'])).isoformat()
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'stop_utc':stop,'reserved_new_accepted_steps':1000,'protocol_sha256':api.sha(DESIGN),'prior_window_accepted_steps':0})
    ns={**pre.wrapper.raw_execute.__globals__,'DESIGN':DESIGN}
    execute=FunctionType(pre.wrapper.raw_execute.__code__,ns,'execute_segment',pre.wrapper.raw_execute.__defaults__,pre.wrapper.raw_execute.__closure__)
    api.require(q.campaign.code_sha(execute)==protocol['integration_code_sha256'],'integration identity')
    prof=cProfile.Profile();actual=None;failure=None;summary=None
    try:
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            geo=pre.geometry();prof.enable()
            with pre.wrapper.repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):
                rec,_,_,elapsed=execute(d,case,before,RUN/'record.json.xz',1000,None,stop)
            prof.disable();actual=len(rec['rows'])
            job.commit(RUN/'accounting.json',{'accepted_steps':actual,'rejected':rec['result']['rejected'],'raw_sha256':api.sha(RUN/'record.json.xz')})
            restored=q.independent_file(RUN/'record.json.xz',api.sha(DESIGN))
            api.require(q.repair.base.raw_bytes(restored)==q.repair.base.raw_bytes(rec),'independent original bytes')
            summary=job.kernel.evaluate(restored,case['spec'],job.binding(d,case),before,geo,api.sha(DESIGN),d['minimum_gap_semantics'])
            oracle=q.independent_file(Path(d['stress_oracle_raw']),api.sha(d['stress_oracle_design']))
            api.require(actual==1000 and rec['rows']==oracle['rows'][:1000] and summary['passed'],'exact accepted prefix and numerical audit')
    except Exception as error:
        prof.disable();failure={'error':repr(error),'traceback':traceback.format_exc(),'known_accepted_steps':actual,'maximum_unresolved_steps':1000 if actual is None else 0};job.commit(OUT/'failure.json',failure)
    stream=io.StringIO();stats=pstats.Stats(prof,stream=stream).sort_stats('cumulative');stats.print_stats(80)
    text=stream.getvalue();job.commit(OUT/'profile.json',{'text':text,'instrumented':True})
    api.verify_mapping(protocol['inputs']);api.verify_mapping(protocol['sources'])
    report={'passed':failure is None,'new_accepted_steps':actual,'window_new_accepted_steps':actual,'unresolved_reservation':1000 if actual is None else 0,
        'audit':summary,'failure':failure,'protocol_sha256':api.sha(DESIGN),'profile_sha256':api.sha(OUT/'profile.json'),
        'artifacts':{str(p):api.sha(p) for p in RUN.iterdir() if p.is_file()},'complete_observation':False,'production_authorized':False}
    job.commit(OUT/'results.json',report);job.commit(OUT/'completion.json',{'passed':report['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('PROFILE_SEGMENT',report['passed'],actual,flush=True);print(text,flush=True)

if __name__=='__main__':run()
