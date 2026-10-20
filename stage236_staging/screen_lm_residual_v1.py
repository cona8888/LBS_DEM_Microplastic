"""Fresh bounded, nonadvancing screen of the two-contact LM callback.

Consumer: admission of a short separately bounded numerical equivalence test.
No transport integrator is called by this screen.
"""
from pathlib import Path
from types import ModuleType, FunctionType, SimpleNamespace
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json, os, shutil, statistics, subprocess, sys, time, traceback

ROOT=Path(__file__).resolve().parents[1]; SELF=Path(__file__).resolve()
sys.path[:0]=[str(SELF.parent),str(ROOT/'stage235_staging')]
import profile_difficult_contacts_v1 as prior
import lm_residual_kernel_v1 as kernel
import success_controls_v1 as success
b=prior.b; controller=prior.controller
BASE='lm_residual_20261009'
PLAN=ROOT/'stage236_designs'/BASE/'design_01.json'; AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage236_evaluations'/BASE
FIXTURES=ROOT/'stage235_evaluations/difficult_contact_profile_20261009/fixtures.json'
c=ModuleType('_fresh_lm_callback_screen');c.__dict__.update(vars(prior.c))
c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=OUT;c.DESIGNS=PLAN.parent
for name,fn in vars(prior.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(prior.c):
        setattr(c,name,FunctionType(fn.__code__,vars(c),fn.__name__,fn.__defaults__,fn.__closure__))

ACTIVE=False
@contextmanager
def observation_scope(runtime,enabled):
    assert runtime is b.RUNTIME and enabled is True
    with b.JOB.observer.scope(runtime,enabled) as trace:
        if ACTIVE:
            with kernel.scope():yield trace
        else:yield trace
observer=SimpleNamespace(**{**vars(b.JOB.observer),'scope':observation_scope})
job=SimpleNamespace(**{**vars(b.JOB),'observer':observer})
PRIVATE={**vars(b),'c':c,'JOB':job}
for name,fn in vars(b).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(b):
        PRIVATE[name]=FunctionType(fn.__code__,PRIVATE,fn.__name__,fn.__defaults__,fn.__closure__)
call=PRIVATE['call']

def resources():
    a=c.bound();c.environment()
    assert a['maximum_nonadvancing_outer_calls']==128 and a['maximum_direct_inner_calls']==16
    assert a['maximum_trajectory_steps']==a['maximum_saved_transport_steps']==0
    assert a['workers']==a['threads']==1 and not a['production_authorized']
    assert shutil.disk_usage(ROOT).free>a['minimum_free_disk_bytes']
    assert sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file())<a['maximum_output_bytes']
    return a

def prepare():
    c.environment();assert not AUTH.exists() and not PLAN.exists() and not OUT.exists()
    inventory=c.read(FIXTURES)
    assert len(inventory['fixtures'])==2 and all(len(x['outer_inputs'][6])==2 for x in inventory['fixtures'])
    healthy_inventory=c.read(b.FIXTURE_DIR/'fixtures.json')
    healthy=next(row for row in healthy_inventory['fixtures'] if row['stratum']=='healthy_early_success')
    assert len(healthy['outer_inputs'][6])==3
    inventory['fixtures'].append(healthy)
    inventory['schema']='stage236-authenticated-mixed-fixed-pose-fixtures-v1'
    inventory['counts']=dict(fixtures=3,recorded_fallbacks=2,healthy_early_successes=1)
    inventory['claim']='Two original Stage233 two-contact fallback poses and one separate original three-contact healthy guard. Per-fixture original context and provenance retained; no current candidate qualification or transport claim.'
    inventory['parent_inventories']={str(FIXTURES):c.sha(FIXTURES),str(b.FIXTURE_DIR/'fixtures.json'):c.sha(b.FIXTURE_DIR/'fixtures.json')}
    inventory['context_by_id']={healthy['fixture_id']:{k:v for k,v in healthy_inventory.items() if k not in ('fixtures','sources','inputs')}}
    imported={str(p):c.sha(p) for p in b.source_files()}
    assert all(imported[path]==expected for path,expected in inventory['sources'].items() if path in imported),'Inherited source mismatch cannot be replaced'
    assert all(imported[path]==expected for path,expected in healthy_inventory['sources'].items() if path in imported),'Healthy source mismatch cannot be replaced'
    assert all(inventory['sources'][path]==expected for path,expected in healthy_inventory['sources'].items() if path in inventory['sources'])
    assert all(inventory['inputs'][path]==expected for path,expected in healthy_inventory['inputs'].items() if path in inventory['inputs']),'Conflicting original input expectations'
    sources={**inventory['sources'],**healthy_inventory['sources'],**imported}
    for path,expected in success.SOURCES.items():
        assert path not in sources or sources[path]==expected,'Success-control source conflict'
        sources[path]=expected
    inputs={**inventory['inputs'],**healthy_inventory['inputs'],str(FIXTURES):c.sha(FIXTURES)}
    for path,expected in success.INPUTS.items():
        assert path not in inputs or inputs[path]==expected,'Synthetic-control input conflict'
        inputs[path]=expected
    for path in (b.FIXTURE_DIR/'fixtures.json',b.FIXTURE_DIR/'results.json',b.FIXTURE_DIR/'completion.json'):
        inputs[str(path)]=c.sha(path)
    assert c.sealed(b.FIXTURE_DIR/'results.json')['passed']
    receipt=FIXTURES.parent/'final_disposition_01/results.json'
    assert c.sha(receipt)=='0a70f2982bd8540742f113dfe467159c78f0f94067f8bb8be2a9bad22fc7a620'
    inputs[str(receipt)]=c.sha(receipt)
    for p in (SELF,Path(kernel.__file__).resolve(),Path(success.__file__).resolve()):sources[str(p)]=c.sha(p)
    # Read-only source/evidence authentication precedes the fresh admission.
    for path,expected in {**sources,**inputs}.items():
        assert c.sha(path)==expected,'Pre-admission source/input mismatch: '+path
    start=datetime.now(timezone.utc);end=start+timedelta(minutes=30)
    a=dict(stage='Stage236 two-contact LM residual acceleration',
        human_authorization='Human9October: Please resolve bottleneck and move on to next. Targeted equation-preserving implementation and bounded qualification; previous windows remain closed.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=(end-timedelta(seconds=30)).isoformat(),
        maximum_nonadvancing_outer_calls=128,maximum_direct_inner_calls=16,maximum_trajectory_steps=0,maximum_saved_transport_steps=0,
        workers=1,threads=1,logical_cpu=14,maximum_output_bytes=128*1024**2,minimum_free_disk_bytes=20*1024**3,
        production_authorized=False,automatic_continuation_authorized=False,prior_windows_remain_closed=True,
        physical_changes=[],timestep_changes=[],accuracy_gate_changes=[],route_order_changes=[],
        source_files=sources,inputs=inputs,
        claim='Local fixed-pose arithmetic, route and complete-cost qualification. No trajectory throughput, full-path accuracy, physical validation or population shape/flow claim.',
        minimum_material_gain_fraction=.05,maximum_healthy_cost_ratio=1.05)
    c.commit(AUTH,a);resources();c.verify(sources);c.verify(inputs)
    inventory['sources']=sources;inventory['inputs']=inputs;c.commit(OUT/'fixtures.json',inventory)
    p={**a,'authorization_sha256':c.sha(AUTH),'fixtures_sha256':c.sha(OUT/'fixtures.json'),
        'fixture_ids':[x['fixture_id'] for x in inventory['fixtures']],
        'timing_pairs_per_fixture':20,'qualification_pairs_per_fixture':1,
        'pair_order':'Alternate original/candidate and candidate/original; compare scientific outputs including residuals exactly on every pair.',
        'timing_scope':'Unprofiled outer and full scope entry+outer+capture+exit measured separately. Original independent post-call physical audit and serialization are outside timed transaction.',
        'material_gate':'Each difficult fixture requires median candidate/original <=0.95 for both outer and complete scoped transaction. Healthy controls must not regress >5percent. No favorable aggregate can override a fixture failure.',
        'transport_admission':'Requires separate fresh short path arithmetic/physical and exact full-checkpoint restart qualification; this screen cannot promote transport by itself.'}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    print('LM_SCREEN_PREPARED',c.sha(PLAN),end.isoformat(),flush=True)

def verify():
    a=resources();p=c.read(PLAN)
    assert p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'})
    assert p['authorization_sha256']==c.sha(AUTH) and all(p[k]==v for k,v in a.items())
    assert c.sha(OUT/'fixtures.json')==p['fixtures_sha256']
    c.verify(p['source_files']);c.verify(p['inputs'])
    assert call.__code__ is b.call.__code__ and PRIVATE['ASSOCIATION'] is b.ASSOCIATION
    assert job.observer.backend is b.JOB.observer.backend
    return p

def run():
    global ACTIVE
    p=verify();process=b.psutil.Process();process.cpu_affinity([14])
    c.commit(OUT/'launch.json',dict(pid=process.pid,created=process.create_time(),command=process.cmdline(),utc=c.utc(),design_sha256=c.sha(PLAN),
        runtime=dict(python=sys.version,executable=sys.executable,numpy=b.np.__version__,numba=sys.modules['numba'].__version__,scipy=sys.modules['scipy'].__version__),
        affinity=process.cpu_affinity(),threads={name:os.environ[name] for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')}))
    reports=[];calls=0;active=None;latest=None
    try:
        inventory=c.read(OUT/'fixtures.json')
        b.JOB.parent.b.old.parent.configure();b.STACK.candidate.warm();kernel.warm()
        pure=kernel.controls([x for x in inventory['fixtures'] if len(x['outer_inputs'][6])==2])
        pure['success_control_construction']=success.pure_controls(kernel)
        assert pure['passed'];c.commit(OUT/'arithmetic_controls.json',pure)
        c.commit(OUT/'synthetic_reservation.json',dict(maximum_inner_calls=16,utc=c.utc(),purpose='Labelled successful-primary controls; no saved-state substitution or transport advance'))
        synthetic=success.controls(kernel,c.bound)
        assert synthetic['passed'] and synthetic['inner_calls']<=16
        c.commit(OUT/'synthetic_controls.json',synthetic)
        costs=[]
        for row in inventory['fixtures']:
            samples={'original':[],'candidate':[]}
            for pair_index in range(1+p['timing_pairs_per_fixture']):
                pair=None
                modes=('original','candidate') if pair_index%2==0 else ('candidate','original')
                for mode in modes:
                    resources();assert calls<128;calls+=1
                    active=dict(call=calls,fixture_id=row['fixture_id'],mode=mode,pair_index=pair_index)
                    c.commit(OUT/'reservations'/f'{calls:03d}.json',active)
                    latest=None
                    ACTIVE=mode=='candidate'
                    kernel.telemetry(reset=True)
                    context=inventory.get('context_by_id',{}).get(row['fixture_id'],inventory)
                    item=call(context,row,'original',p['end_utc']);ACTIVE=False;resources()
                    latest=item
                    item['kernel_telemetry']=kernel.telemetry()
                    if mode=='candidate' and len(row['outer_inputs'][6])==2:
                        assert item['kernel_telemetry']['primary_callbacks']>0 and item['kernel_telemetry']['zero_callbacks']>0,'Actual difficult callbacks must use candidate'
                    elif mode=='original':
                        assert not any(item['kernel_telemetry'].values()),'No candidate installed in original control'
                    else:
                        assert item['kernel_telemetry']['compiled_callbacks']==0,'Three-contact arithmetic remains original'
                    item['kernel_mode']=mode;item['pair_index']=pair_index
                    current=PRIVATE['scientific'](item['force_audit_fixture'])
                    if pair is None:pair=current
                    else:assert c.digest(current)==c.digest(pair),'Exact scientific pair including residuals and all route records'
                    path=OUT/'calls'/f'{calls:03d}.json';c.commit(path,item)
                    report=dict(**active,path=str(path),sha256=c.sha(path),**{k:item[k] for k in ('seconds','scope_entry_seconds','scope_exit_seconds','telemetry_capture_seconds','scoped_transaction_seconds')})
                    reports.append(report)
                    if pair_index:samples[mode].append(report)
                    active=None
            result=dict(fixture_id=row['fixture_id'],stratum=row['stratum'],samples_per_mode=len(samples['original']))
            for key in ('seconds','scoped_transaction_seconds'):
                original=statistics.median(x[key] for x in samples['original'])
                candidate=statistics.median(x[key] for x in samples['candidate'])
                result[key]=dict(original_median=original,candidate_median=candidate,ratio=candidate/original,speedup=original/candidate)
            limit=1-p['minimum_material_gain_fraction'] if row['stratum']=='recorded_fallback' else p['maximum_healthy_cost_ratio']
            result['performance_passed']=all(result[key]['ratio']<=limit for key in ('seconds','scoped_transaction_seconds'))
            costs.append(result);print('LM_EXACT_PHYSICAL_FIXTURE',row['fixture_id'],json.dumps(result),flush=True)
        verify();assert active is None
        r=dict(passed=True,scientific_passed=True,performance_passed=all(x['performance_passed'] for x in costs),utc=c.utc(),
            design_sha256=c.sha(PLAN),attempted_outer_calls=calls,completed_outer_calls=len(reports),unknown_outer_calls=0,
            new_trajectory_steps=0,new_saved_transport_steps=0,original_independent_physical_audits_passed=True,
            exact_pairs_including_residuals=True,costs=costs,reports=reports,
            synthetic_inner_calls=synthetic['inner_calls'],synthetic_controls_passed=True,
            artifacts={**{x['path']:x['sha256'] for x in reports},str(OUT/'arithmetic_controls.json'):c.sha(OUT/'arithmetic_controls.json'),str(OUT/'synthetic_controls.json'):c.sha(OUT/'synthetic_controls.json')},
            production_authorized=False,claim=p['claim'])
        c.commit(OUT/'results.json',r);c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    except Exception as e:
        ACTIVE=False;observed=PRIVATE['failure_output'](e);artifacts={}
        if observed is None:observed=latest
        if observed is not None:
            path=OUT/'failed_call.json';c.commit(path,observed);artifacts[str(path)]=c.sha(path)
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(e),traceback=traceback.format_exc(),utc=c.utc(),
            attempted_outer_calls=calls,completed_outer_calls=len(reports),unresolved_call=active,reports=reports,artifacts=artifacts,
            synthetic_state=success.STATE,new_trajectory_steps=0))
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
        c.commit(folder/'worker_exit.json',dict(returncode=code,forced_cutoff_stop=forced,identity=identity,utc=c.utc(),launch_sha256=c.sha(folder/'worker_launch.json'),closed_logs={str(x):c.sha(x) for x in folder.glob('*.log')}))
        if code!=0 or forced:raise RuntimeError('LM screen failed; preserve negative; no dependent dispatch')
        resources();r=c.sealed(OUT/'results.json')
        c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json'),utc=c.utc()))
    except Exception as e:
        if child is not None and birth is not None:stop(child,birth,command,folder)
        c.commit(folder/'failure.json',dict(passed=False,error=repr(e),traceback=traceback.format_exc(),utc=c.utc()))
        raise

def retire():
    p=verify();folder=OUT/'controller_01';identities=[]
    for path in (folder/'launch.json',folder/'worker_launch.json'):
        saved=c.read(path);current=controller.inspect(saved['pid'],saved['created'],saved['command'])
        assert current['retired'],'Exact owned process is still active'
        identities.append(dict(launch_path=str(path),launch_sha256=c.sha(path),inspection=current))
    exit_record=c.read(folder/'worker_exit.json')
    assert not exit_record['forced_cutoff_stop'] and exit_record['returncode']==0
    c.verify(exit_record['closed_logs'])
    result=c.sealed(OUT/'results.json');assert result['scientific_passed']
    assert c.read(folder/'completion.json')['results_sha256']==c.sha(OUT/'results.json')
    c.verify(result['artifacts'])
    receipt=OUT/'final_disposition_01/results.json'
    artifacts={str(path):c.sha(path) for path in OUT.rglob('*') if path.is_file() and 'final_disposition_01' not in path.parts}
    r=dict(passed=True,utc=c.utc(),design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
        results_sha256=c.sha(OUT/'results.json'),scientific_passed=True,performance_passed=result['performance_passed'],
        exact_launch_identities_retired=True,identities=identities,worker_returncode=0,worker_forced=False,
        controller_completed_receipt_authenticated=True,controller_os_exit_code_independently_observed=False,
        closed_logs=exit_record['closed_logs'],source_count=len(p['source_files']),input_count=len(p['inputs']),
        attempted_outer_calls=result['attempted_outer_calls'],accepted_outer_calls=result['completed_outer_calls'],
        direct_inner_calls=result['synthetic_inner_calls'],known_unaccepted_outer_calls=0,unknown_outer_calls=0,
        new_trajectory_steps=0,new_saved_transport_steps=0,prototype_installed_in_transport=False,
        artifacts=artifacts,claim=p['claim'])
    c.commit(receipt,r);c.commit(receipt.parent/'completion.json',dict(passed=True,results_sha256=c.sha(receipt)))
    print('LM_SCREEN_RETIRED',c.sha(receipt),json.dumps(result['costs']),flush=True)

if __name__=='__main__':{'prepare':prepare,'run':run,'launch':launch,'retire':retire}[sys.argv[1]]()
