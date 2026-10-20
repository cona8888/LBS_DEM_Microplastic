"""Bounded fixed-pose attribution of the unchanged difficult contact path."""
from pathlib import Path
from types import ModuleType, FunctionType, SimpleNamespace
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import cProfile, copy, json, os, pstats, shutil, subprocess, sys, time, traceback

ROOT=Path(__file__).resolve().parents[1];SELF=Path(__file__).resolve()
sys.path[:0]=[str(SELF.parent),str(ROOT/'stage234_staging')]
import screen_observer_cache_v1 as infrastructure
import extract_difficult_fixtures_v1 as extraction
b= infrastructure.original
controller=infrastructure.controller
BASE='difficult_contact_profile_20261009'
PLAN=ROOT/'stage235_designs'/BASE/'design_01.json';AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage235_evaluations'/BASE
c=ModuleType('_fresh_nonadvancing_profile_administration');c.__dict__.update(vars(infrastructure.c))
c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=OUT;c.DESIGNS=PLAN.parent
for name,fn in vars(infrastructure.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(infrastructure.c):
        setattr(c,name,FunctionType(fn.__code__,vars(c),fn.__name__,fn.__defaults__,fn.__closure__))

@contextmanager
def profiled_observation(observer,profiler):
    """Profile exactly the original observed outer body; restore in finally."""
    with observer.scope(RUNTIME,True) as trace:
        original=observer.backend.inertial_contact_step
        if profiler is None:
            yield trace
            return
        def observed(*args,**kwargs):
            return profiler.runcall(original,*args,**kwargs)
        observer.backend.inertial_contact_step=observed
        try:yield trace
        finally:observer.backend.inertial_contact_step=original

RUNTIME=b.RUNTIME
ACTIVE_PROFILER=None
@contextmanager
def observation_scope(runtime,enabled):
    assert runtime is RUNTIME and enabled is True
    with profiled_observation(b.JOB.observer,ACTIVE_PROFILER) as trace:yield trace
observer=SimpleNamespace(**{**vars(b.JOB.observer),'scope':observation_scope})
job=SimpleNamespace(**{**vars(b.JOB),'observer':observer})
PRIVATE={**vars(b),'c':c,'JOB':job}
for name,fn in vars(b).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(b):
        PRIVATE[name]=FunctionType(fn.__code__,PRIVATE,fn.__name__,fn.__defaults__,fn.__closure__)
call=PRIVATE['call']

def resources():
    a=c.bound();c.environment()
    assert a['maximum_nonadvancing_outer_calls']==4 and a['maximum_trajectory_steps']==a['maximum_saved_transport_steps']==0
    assert a['workers']==a['threads']==1 and not a['production_authorized']
    assert shutil.disk_usage(ROOT).free>a['minimum_free_disk_bytes']
    assert sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file())<a['maximum_output_bytes']
    return a

def controls():
    assert call.__code__ is b.call.__code__ and call.__globals__ is PRIVATE
    assert job.observer.backend is b.JOB.observer.backend and b.JOB.observer.scope is not observation_scope
    assert PRIVATE['ASSOCIATION'] is b.ASSOCIATION and PRIVATE['candidate'] is b.candidate
    assert PRIVATE['STACK'] is b.STACK and PRIVATE['RUNTIME'] is b.RUNTIME
    # The profile hook forwards exact objects/results and restores on error.
    sentinel=object();events=[]
    def fn(*args,**kwargs):events.append((args,kwargs));return sentinel
    backend=SimpleNamespace(inertial_contact_step=fn)
    @contextmanager
    def scope(runtime,enabled):yield {'test':True}
    fake=SimpleNamespace(scope=scope,backend=backend)
    profiler=cProfile.Profile()
    with profiled_observation(fake,profiler):
        assert backend.inertial_contact_step(1,mode='exact') is sentinel
    assert backend.inertial_contact_step is fn and events==[((1,),{'mode':'exact'})]
    try:
        with profiled_observation(fake,profiler):raise RuntimeError('injected control')
    except RuntimeError as e:assert str(e)=='injected control'
    assert backend.inertial_contact_step is fn
    return dict(passed=True,original_call_code_unchanged=True,profile_forwards_exact_objects=True,
        profile_restores_on_success_and_error=True,original_independent_auditor_unchanged=True,
        prototype_not_installed=True,numerical_calls=0)

def prepare():
    c.environment();assert not AUTH.exists() and not PLAN.exists() and not OUT.exists()
    start=datetime.now(timezone.utc);end=start+timedelta(minutes=15)
    def preparation_bound():
        assert time.time()<end.timestamp()-30,'Fresh preparation deadline reached'
    pure=controls();pure['extraction_controls']=extraction.controls()
    inventory,sources,inputs=extraction.prepare_fixtures(codec=b.JOB.codec,fresh_bound=preparation_bound)
    assert len(inventory['fixtures'])==2 and all(len(x['outer_inputs'][6])==2 for x in inventory['fixtures'])
    imported={str(x):c.sha(x) for x in b.source_files()}
    assert all(imported[path]==expected for path,expected in sources.items() if path in imported), 'Never substitute a changed inherited source hash'
    sources={**sources,**imported,str(SELF):c.sha(SELF)}
    preparation_bound()
    authority=dict(stage='Stage235 difficult two-contact baseline attribution',human_authorization='Fresh human next9October; targeted profile after the negative Stage234 cost gate.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=(end-timedelta(seconds=30)).isoformat(),
        maximum_nonadvancing_outer_calls=4,maximum_trajectory_steps=0,maximum_saved_transport_steps=0,
        workers=1,threads=1,logical_cpu=14,maximum_output_bytes=64*1024**2,minimum_free_disk_bytes=20*1024**3,
        production_authorized=False,automatic_continuation_authorized=False,prior_windows_remain_closed=True,
        physical_changes=[],timestep_changes=[],accuracy_gate_changes=[],
        source_files=sources,inputs=inputs,
        claim='Two prospectively selected saved difficult two-contact poses. Exact unprofiled/profiled paired baseline outputs and unchanged independent physical audits. Profiled cumulative costs overlap and include profiler overhead; no speedup, representative campaign timing or transport/full-path/population qualification.',
        research_decision='Determine whether three-contact reuse metadata is on the actual two-contact bottleneck path, then target the measured original cost without weakening physics or evidence.')
    c.commit(AUTH,authority);resources();c.verify(sources);c.verify(inputs)
    c.commit(OUT/'fixtures.json',inventory)
    p={**authority,'authorization_sha256':c.sha(AUTH),'fixtures_sha256':c.sha(OUT/'fixtures.json'),
        'modes':['qualification_unprofiled','outer_profiled'],'fixture_ids':[x['fixture_id'] for x in inventory['fixtures']],
        'profiling_scope':'Only original observed outer body; entry/capture/exit and independent post-call auditing are outside profiler. Report their measured component times separately.',
        'controls':pure,'prototype_installed':False,'paired_comparator':'Exact entire scientific fixture including residuals; exclude only original wall_s/certificate_seconds timing fields.'}
    p['binding']=c.digest(p);resources();c.commit(PLAN,p)
    print('BASELINE_PROFILE_PREPARED',c.sha(PLAN),end.isoformat(),flush=True)

def verify():
    a=resources();p=c.read(PLAN)
    assert p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH)
    assert all(p[k]==x for k,x in a.items()) and c.sha(OUT/'fixtures.json')==p['fixtures_sha256']
    c.verify(p['source_files']);c.verify(p['inputs']);controls()
    return p

def profile_rows(profiler):
    stats=pstats.Stats(profiler)
    rows=[dict(file=k[0],line=k[1],function=k[2],primitive_calls=v[0],calls=v[1],self_seconds=v[2],cumulative_seconds=v[3]) for k,v in stats.stats.items()]
    return dict(total_seconds=stats.total_tt,total_calls=stats.total_calls,
        functions=sorted(rows,key=lambda x:x['cumulative_seconds'],reverse=True),
        caution='Nested cumulative rows overlap. Profile overhead changes costs; this is attribution, not unprofiled throughput or a speedup.')

def run():
    global ACTIVE_PROFILER
    p=verify();process=b.psutil.Process();process.cpu_affinity([14])
    c.commit(OUT/'launch.json',dict(pid=process.pid,created=process.create_time(),command=process.cmdline(),utc=c.utc(),design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH)))
    inventory=c.read(OUT/'fixtures.json');reports=[];calls=0;active=None
    try:
        b.JOB.parent.b.old.parent.configure();b.STACK.candidate.warm()
        for row in inventory['fixtures']:
            previous=None
            for mode in p['modes']:
                resources();assert calls<4;calls+=1
                active=dict(call=calls,fixture_id=row['fixture_id'],mode=mode)
                c.commit(OUT/'reservations'/f'{calls:02d}.json',active)
                ACTIVE_PROFILER=cProfile.Profile() if mode=='outer_profiled' else None
                item=call(inventory,row,'original',p['end_utc']);resources()
                item['profile_mode']=mode
                if ACTIVE_PROFILER is not None:item['profile']=profile_rows(ACTIVE_PROFILER)
                current=PRIVATE['scientific'](item['force_audit_fixture'])
                if previous is None:previous=current
                else:assert c.digest(current)==c.digest(previous),'Exact pair including all residuals and retained route rows'
                path=OUT/'calls'/f'{calls:02d}.json';c.commit(path,item)
                reports.append(dict(fixture_id=row['fixture_id'],mode=mode,path=str(path),sha256=c.sha(path),
                    **{k:item[k] for k in ('seconds','scope_entry_seconds','scope_exit_seconds','telemetry_capture_seconds','scoped_transaction_seconds')}))
                active=None;ACTIVE_PROFILER=None
                print('DIFFICULT_ORIGINAL_CALL',calls,row['fixture_id'],mode,flush=True)
        assert calls==len(reports)==4 and active is None;verify()
        r=dict(passed=True,utc=c.utc(),design_sha256=c.sha(PLAN),completed_outer_calls=4,attempted_outer_calls=4,
            unknown_outer_calls=0,new_trajectory_steps=0,new_saved_transport_steps=0,prototype_installed=False,
            exact_unprofiled_profiled_pairs_including_residuals=True,independent_original_physical_audits_passed=True,
            reports=reports,artifacts={x['path']:x['sha256'] for x in reports},claim=p['claim'])
        resources();c.commit(OUT/'results.json',r);resources();c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    except Exception as e:
        ACTIVE_PROFILER=None;observed=PRIVATE['failure_output'](e);artifacts={}
        if observed is not None:
            path=OUT/'failed_call.json';c.commit(path,observed);artifacts[str(path)]=c.sha(path)
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(e),traceback=traceback.format_exc(),utc=c.utc(),attempted_outer_calls=calls,
            completed_outer_calls=len(reports),unresolved_call=active,reports=reports,artifacts=artifacts,new_trajectory_steps=0))
        raise

def launch():
    p=verify();folder=OUT/'controller_01';folder.mkdir(parents=True,exist_ok=False);parent=b.psutil.Process()
    c.commit(folder/'launch.json',dict(pid=parent.pid,created=parent.create_time(),command=parent.cmdline(),utc=c.utc(),design_sha256=c.sha(PLAN)))
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'run'];env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):env[key]='1'
    stop=FunctionType(controller.stop_owned.__code__,{**vars(controller),'c':c},controller.stop_owned.__name__,controller.stop_owned.__defaults__,controller.stop_owned.__closure__)
    child=birth=None;forced=False
    try:
        with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            birth=b.psutil.Process(child.pid).create_time();assert b.psutil.Process(child.pid).cmdline()==command
            c.commit(folder/'worker_launch.json',dict(pid=child.pid,created=birth,command=command,utc=c.utc()))
            while child.poll() is None:
                if time.time()>=datetime.fromisoformat(p['worker_cutoff_utc']).timestamp():stop(child,birth,command,folder);forced=True;break
                time.sleep(.25)
            code=child.wait(timeout=10)
        identity=controller.inspect(child.pid,birth,command);assert identity['retired']
        c.commit(folder/'worker_exit.json',dict(returncode=code,forced_cutoff_stop=forced,identity=identity,utc=c.utc(),
            launch_sha256=c.sha(folder/'worker_launch.json'),closed_logs={str(x):c.sha(x) for x in folder.glob('*.log')}))
        if code!=0 or forced:raise RuntimeError('Baseline attribution failed; preserve negative, no dependent dispatch')
        resources();r=c.sealed(OUT/'results.json');assert r['completed_outer_calls']==4
        c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json'),utc=c.utc()))
    except Exception as e:
        if child is not None and birth is not None:stop(child,birth,command,folder)
        c.commit(folder/'failure.json',dict(passed=False,error=repr(e),traceback=traceback.format_exc(),utc=c.utc()))
        raise

if __name__=='__main__':{'prepare':prepare,'launch':launch,'run':run}[sys.argv[1]]()
