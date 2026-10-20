"""Configuration-driven continuation of the admitted guarded physical stack.

Original numerical, storage, independent physical and whole-path comparison
code objects are reused. Only fresh authority, ancestry, scheduling and ledger
administration live here. Retired earlier attempts are immutable inputs.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import ModuleType,SimpleNamespace,FunctionType
from contextlib import contextmanager
import os,sys,time,subprocess,traceback,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage244_staging'))
import continue_guard_v2 as prior
base=prior.original
api,job,kernel,controller,reference,guard=prior.api,prior.job,prior.kernel,prior.controller,prior.reference,prior.guard
clone=prior.clone;require=prior.require;SELF=Path(__file__).resolve()
PLAN=Path(os.environ.get('DEM_GUARD_PLAN',str(ROOT/'stage245_designs/guard_tail_20261013/design_01.json'))).resolve()
AUTH=PLAN.with_name('authorization_01.json');OUT=ROOT/'stage245_evaluations'/PLAN.parent.name;RUN=OUT/'records'
SEED_ROOT=prior.OUT/'final_disposition_01';SEED_PREFIX=SEED_ROOT/'recoverable/prefix.json'
SEED_SHA='d284321fb19590dbd0c64a6ba91ee5c176165a37c8a52d655549207a2a1026d9'
FINAL_SHA='8d8a10058d57e3c463c97ae0fda64232c8928ddb1936691ce7d6643e6b4ee4c2'
RETIRE_SHA='07a864aa63536d57182a7115eb2c8c1d7cb685604a44e56bef512df43e248672'
SHARED_SHA='6ee27f85ef4c01f400057343c1c5df32b0a8e74d09cfae70c9a33bfad0706802'
c=ModuleType('_guard_continuation_admin');c.__dict__.update(vars(prior.c));c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=RUN;c.DESIGNS=PLAN.parent
for key,fn in vars(prior.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(prior.c):setattr(c,key,clone(fn,vars(c)))
observation=contextmanager(clone(base.prior.observation.__wrapped__,{**base.prior.observation.__wrapped__.__globals__,'c':c}))
observer=SimpleNamespace(**{**vars(base.prior.observer),'scope':observation})
private_job=ModuleType('_guard_continuation_private_job');private_job.__dict__.update(vars(job));private_job.observer=observer
raw=clone(base.prior.old.RAW,{**base.prior.old.RAW.__globals__,'observer':observer})
frozen=SimpleNamespace(**{**vars(base.prior.old.baseline.execute.__globals__['frozen']),'raw_execute':raw})
execute=clone(base.prior.old.baseline.execute,{**base.prior.old.baseline.execute.__globals__,'job':private_job,'frozen':frozen})
baseline=SimpleNamespace(**{**vars(base.prior.old.baseline),'execute':execute})
private={**base.private,'c':c,'PLAN':PLAN,'AUTH':AUTH,'RUN':RUN,'OUT':OUT,'baseline':baseline}
for name in base.prior.old.old.NAMES:private[name]=clone(base.private[name],private)
controls=clone(base.controls,{**base.controls.__globals__,'execute':execute,'raw':raw,'private_job':private_job,'frozen':frozen})

def seed():
    cp=c.read(SEED_ROOT/'recoverable/checkpoint.json');ref=c.read(SEED_PREFIX)
    require(api.digest(cp)==SEED_SHA and cp['state']['steps']==1248166 and cp['state']['t']==1.5521519811801294 and cp['state']['rejected']==0,'Only authenticated accepted FULL seed')
    return cp,job.codec.HistoryState(**ref,history_bytes=job.codec.packed_history(cp['state']['history']))

def resources():
    a=c.bound();c.environment()
    require(a['maximum_new_physical_steps']==400000 and a['maximum_saved_steps_including_diagnostics']==400512 and a['maximum_new_production_calls']==80
        and a['step_cap_per_call']==5000 and a['maximum_cumulative_physical_steps_per_case']==5000000 and a['maximum_cumulative_calls_per_case']==1500
        and a['workers']==a['threads']==a['maximum_unverified_records']==1,'Prospective bounded numerical work and original cumulative ceilings')
    require(shutil.disk_usage(ROOT).free>a['minimum_free_disk_bytes'],'Disk reserve')
    require(sum(q.stat().st_size for f in (OUT,PLAN.parent) for q in f.rglob('*') if q.is_file())<a['maximum_output_bytes'],'Own retained output cap')
    return a

def verify():
    a=resources();p=c.read(PLAN)
    require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH) and all(p[k]==v for k,v in a.items()),'Immutable authority and design')
    c.verify(p['source_files']);c.verify(p['inputs'])
    require(c.sealed(OUT/'preparation_01/results.json')['design_sha256']==c.sha(PLAN),'Passing preparation')
    return p

def trace_inventory():
    oldplan=c.read(base.prior.old.PLAN)
    paths=list(oldplan['inherited']['trace_paths'])
    root=base.prior.old.RUN/base.prior.old.NAME
    first=c.sealed(base.prior.old.OUT/'final_disposition_01/results.json')
    for i in range(1,36):
        receipt=c.sealed(root/f'segment_{i:05d}'/'results.json')
        require(receipt['passed'],'Every original accepted Stage238 segment')
        path=root/f'segment_{i:05d}'/'trace.npy';require(receipt['artifacts'][str(path)]==c.sha(path),'Original production trace')
        paths.append(str(path))
    require(first['accepted_physical_steps']==158543,'Preserved Stage238 accepted-only prefix')
    paths.append(str(base.prior.RUN/'transfer/trace.npy'))
    paths.append(str(base.RUN/'production_01/trace.npy'))
    paths.extend(str(prior.RUN/f'production_{i:02d}'/'trace.npy') for i in range(1,4))
    require(len(paths)==len(set(paths))==161,'Exactly ordered accepted production-only ancestry, no diagnostics or failed segment36')
    # Original sealed receipts authenticate new-family traces; old inherited
    # trace hashes are retained from their previously accepted ancestry proof.
    for folder in (base.prior.RUN/'transfer',base.RUN/'production_01',*(prior.RUN/f'production_{i:02d}' for i in range(1,4))):
        row=c.sealed(folder/'results.json');require(row['passed'] and row['artifacts'][str(folder/'trace.npy')]==c.sha(folder/'trace.npy'),'Accepted later production trace')
    mapping={q:c.sha(q) for q in paths}
    for q in oldplan['inherited']['trace_paths']:
        require(oldplan['inherited']['inputs'][q]==mapping[q],'Original inherited production trace seal')
    return dict(trace_paths=paths,inputs=mapping,inherited_segments=161,inherited_physical_steps=1248166)

def prepare():
    c.environment();require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Fresh create-only continuation; no old authorization resumed')
    require(c.sha(SEED_ROOT/'results.json')==FINAL_SHA and c.sha(prior.OUT/'retirement_01/results.json')==RETIRE_SHA
        and c.sha(prior.OUT/'shared_closure_01/results.json')==SHARED_SHA,'Exact selected closed prerequisites')
    shared=c.sealed(prior.OUT/'shared_closure_01/results.json');reference.plain_verify(shared['inputs'])
    require(shared['passed'] and shared['known_unaccepted_saved_steps']==shared['unknown_saved_steps']==0 and shared['all_exact_owned_identities_retired'],'No unresolved inherited work')
    for parent in (base.OUT,prior.OUT):
        retired=c.sealed(parent/'retirement_01/results.json')
        for x in retired['identities']:
            launch=c.read(x['path']);require(c.sha(x['path'])==x['sha256'] and controller.inspect(launch['pid'],launch['created'],launch['command'])['retired'],'Fresh old exact identity retirement')
    cp,prefix=seed();pure=controls();inherited=trace_inventory();parent=c.read(prior.PLAN)
    selected=[SEED_ROOT/'results.json',SEED_ROOT/'completion.json',SEED_ROOT/'recoverable/checkpoint.json',SEED_PREFIX,
        prior.OUT/'retirement_01/results.json',prior.OUT/'retirement_01/completion.json',prior.OUT/'shared_closure_01/results.json',
        prior.OUT/'shared_closure_01/completion.json',prior.RUN/'production_03/results.json',prior.RUN/'production_03/completion.json',
        prior.RUN/'production_03/guard_completion/results.json',prior.RUN/'production_03/guard_completion/completion.json',
        Path(prefix.path),Path(prefix.path).with_suffix('.seal.json')]
    imported={str(Path(m.__file__).resolve()):c.sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    sources=base.prior.old.merge_frozen(parent['source_files'],imported,{str(SELF):c.sha(SELF)})
    inputs=base.prior.old.merge_frozen(parent['physical_inputs'],inherited['inputs'],{str(q):c.sha(q) for q in selected})
    reference.plain_verify(sources);reference.plain_verify(inputs)
    start=datetime.now(timezone.utc);end=start+timedelta(seconds=7200)
    a=dict(stage='Stage245 guarded full-observation continuation',human_authorization='Human requested continue from accepted checkpoint toward full observation horizon while keeping physics and accuracy gates unchanged. Fresh two-hour bounded local continuation; no population/successor or recurring campaign.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(seconds=1200)).isoformat(),
        worker_cutoff_utc=(end-timedelta(seconds=1080)).isoformat(),launcher_cutoff_utc=(end-timedelta(seconds=300)).isoformat(),
        maximum_new_physical_steps=400000,maximum_saved_steps_including_diagnostics=400512,discarded_diagnostic_steps_planned=512,
        maximum_new_production_calls=80,step_cap_per_call=5000,maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,
        inherited_physical_steps=1248166,inherited_production_calls=161,workers=1,threads=1,maximum_unverified_records=1,logical_cpu=14,
        maximum_output_bytes=2*1024**3,minimum_free_disk_bytes=20*1024**3,source_files=sources,inputs=inputs,physical_inputs=parent['physical_inputs'],
        candidate_production_authorized=True,successor_cases_authorized=False,automatic_continuation_authorized=False,retain_all_failures=True,
        physical_changes=[],accuracy_gate_changes=[],numerical_cap_changes=[],
        production_admission='Fresh256 versus128+128 exact rows/FULL history, discard512 diagnostics, reset accepted seed; unchanged independent physical and lossless raw plus guard provenance before each dependent dispatch.',
        native_stopping_policy='Continue only audited incomplete_budget/paused_checkpoint; stop at original native COMPLETE and run unchanged original full-path/event comparison.',
        claim='Labelled-case numerical verification at one packing/flow, with no representative-cost, validation or population ranking claim.')
    c.commit(AUTH,a);p={**a,'authorization_sha256':c.sha(AUTH),'physical_design_sha256':parent['physical_design_sha256'],
        'numerical_policy_contract_sha256':parent['numerical_policy_contract_sha256'],'checkpoint_contract':cp['contract'],'original_binding':parent['original_binding'],
        'seed_sha256':SEED_SHA,'controls':pure,'inherited':inherited,'prior_accepted_ancestry_proof_reused':True,'prior_ancestry_not_reexecuted':True}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,controls=pure,design_sha256=c.sha(PLAN),new_saved_steps=0,ordered_production_traces=len(inherited['trace_paths']),utc=c.utc()))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('GUARD_TAIL_PREPARED',c.sha(PLAN),a['end_utc'],flush=True)

def caps(label):return 256 if label=='serial' else 128 if label in ('split_a','split_b') else 5000

def parent_for(label):
    if label=='split_b':folder=RUN/'split_a'
    elif label.startswith('production_') and int(label.split('_')[1])>1:folder=RUN/f"production_{int(label.split('_')[1])-1:05d}"
    else:return (*seed(),c.sha(prior.RUN/'production_03/results.json'))
    admission=c.sealed(folder/'guard_completion/results.json');require(admission['passed'],'Preceding complete guard admission');c.verify(admission['artifacts'])
    cp=c.read(folder/'full_checkpoint.json');ref=c.read(folder/'prefix.json')
    return cp,job.codec.HistoryState(**ref,history_bytes=job.codec.packed_history(cp['state']['history'])),c.sha(folder/'results.json')

def call(label):
    p=verify();reference.psutil.Process().cpu_affinity([p['logical_cpu']]);production=label.startswith('production_')
    require(label in ('serial','split_a','split_b') or production and 1<=int(label.split('_')[1])<=p['maximum_new_production_calls'],'Only frozen diagnostic/production calls')
    if production:require(c.sealed(OUT/'restart_01/results.json')['passed'],'Exact restart before production')
    cp,prefix,previous=parent_for(label);cap=caps(label);d,case=base.prior.old.original_case();before=api.digest(cp)
    require(cp['state']['steps']+cap<=p['maximum_cumulative_physical_steps_per_case'] and
        p['inherited_production_calls']+(int(label.split('_')[1]) if production else 0)<=p['maximum_cumulative_calls_per_case'],'Original cumulative budgets include inherited work')
    reference.JOB.parent.b.old.parent.configure();kernel.warm();kernel.reset();geometry=baseline.geometry_for(case)
    rec,prefix,row=private['segment'](p,d,case,geometry,cp,prefix,RUN/label,cap,previous,'production' if production else 'restart_diagnostic')
    extra=guard.audit(rec);require(0<len(rec['rows'])<=cap and rec['result']['rejected']==0 and api.digest(cp)==before,'Bounded audited increment and unchanged input')
    if not production:require(len(rec['rows'])==cap,'Full declared restart record')
    c.commit(RUN/label/'guard_audit.json',extra);c.commit(RUN/label/'full_checkpoint.json',rec['result']['checkpoint']);c.commit(RUN/label/'prefix.json',prefix.reference())
    gate=RUN/label/'guard_completion/results.json'
    c.commit(gate,dict(passed=True,saved_steps=len(rec['rows']),input_checkpoint_sha256=before,final_checkpoint_sha256=api.digest(rec['result']['checkpoint']),
        original_physical_and_lossless_audits_passed=True,guard_audit=extra,artifacts={str(q):c.sha(q) for q in (RUN/label).glob('*') if q.is_file()},utc=c.utc()))
    c.commit(gate.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(gate)))
    print('GUARD_TAIL_CALL_VERIFIED',label,len(rec['rows']),extra['canonical_calls'],rec['result']['checkpoint']['state']['t'],flush=True)

decoded=clone(base.decoded,{**vars(base),**globals()})

def child(label):
    p=verify();folder=OUT/'children'/label;folder.mkdir(parents=True,exist_ok=False)
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'call',label];stop=clone(controller.stop_owned,{**vars(controller),'c':c})
    sim=datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp();require(time.time()<sim-90,'Numerical call and audit reserve')
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        proc=subprocess.Popen(command,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        birth=reference.psutil.Process(proc.pid).create_time();require(reference.psutil.Process(proc.pid).cmdline()==command,'Exact fresh solver birth/command')
        c.commit(folder/'launch.json',dict(pid=proc.pid,created=birth,command=command,reserved_steps=caps(label),utc=c.utc()))
        forced=False
        while proc.poll() is None:
            if time.time()>=sim+60:stop(proc,birth,command,folder);forced=True;break
            time.sleep(.25)
        code=proc.wait(timeout=10)
    identity=controller.inspect(proc.pid,birth,command);require(identity['retired'],'Fresh solver retired')
    c.commit(folder/'exit.json',dict(returncode=code,forced=forced,identity=identity,closed_logs={str(q):c.sha(q) for q in folder.glob('*.log')},utc=c.utc()))
    require(code==0 and not forced,'No dependent dispatch after numerical child failure')

def full_path(p,d,case,terminal,labels):
    paths=[*p['inherited']['trace_paths'],*[str(RUN/q/'trace.npy') for q in labels if q.startswith('production_')]]
    mapping={q:c.sha(q) for q in paths};reference.plain_verify(p['inherited']['inputs'])
    for q in labels:
        if q.startswith('production_'):
            receipt=c.sealed(RUN/q/'results.json');require(receipt['passed'] and receipt['artifacts'][str(RUN/q/'trace.npy')]==mapping[str(RUN/q/'trace.npy')],'All new accepted whole-path traces sealed')
    comparison_plan={**p,'inherited':{**p['inherited'],'inputs':mapping}}
    # Every new trace is already independently admitted, so all are inherited
    # by this unchanged comparison; no artificial folder/copy or new gate.
    return private['compare'](comparison_plan,d,case,terminal,[],paths)

def run():
    p=verify();proc=reference.psutil.Process();proc.cpu_affinity([p['logical_cpu']]);require(not (OUT/'launch.json').exists(),'No duplicate worker')
    c.commit(OUT/'launch.json',dict(pid=proc.pid,created=proc.create_time(),command=proc.cmdline(),utc=c.utc()))
    used=accepted=0;active=None;verified=[];reason='production_call_limit';comparison=None
    try:
        for label in ('serial','split_a','split_b'):
            active=dict(label=label,maximum_steps=caps(label));child(label);used+=caps(label);verified.append(label);active=None
        cp,prefix=seed();serial,_=decoded('serial',prefix);a,pa=decoded('split_a',prefix);b,_=decoded('split_b',pa)
        require(serial['rows']==a['rows']+b['rows'] and api.digest(serial['result']['checkpoint'])==api.digest(b['result']['checkpoint']),'Exact fresh rows/FULL checkpoint/history restart')
        gate=OUT/'restart_01/results.json';c.commit(gate,dict(passed=True,discarded_diagnostic_steps=512,exact_rows=True,exact_full_checkpoint=True,diagnostic_promoted=False,production_seed_sha256=SEED_SHA,
            artifacts={str(q):c.sha(q) for q in RUN.rglob('*') if q.is_file()},utc=c.utc()));c.commit(gate.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(gate)))
        d,case=base.prior.old.original_case()
        for i in range(1,p['maximum_new_production_calls']+1):
            resources()
            if time.time()>=datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp()-90:reason='numerical_cutoff_reserve';break
            if used+5000>p['maximum_saved_steps_including_diagnostics'] or accepted+5000>p['maximum_new_physical_steps']:reason='saved_step_ceiling';break
            label=f'production_{i:05d}';active=dict(label=label,maximum_steps=5000,input_checkpoint_sha256=api.digest(cp));child(label)
            rec,prefix=decoded(label,prefix);n=len(rec['rows']);accepted+=n;used+=n;cp=rec['result']['checkpoint'];verified.append(label);active=None
            c.commit(OUT/f'progress_{i:05d}.json',dict(accepted_physical_steps=accepted,discarded_diagnostic_steps=512,cumulative_physical_steps=cp['state']['steps'],cumulative_production_calls=p['inherited_production_calls']+i,
                time_s=cp['state']['t'],native_status=rec['result']['status'],full_checkpoint_sha256=api.digest(cp),utc=c.utc()))
            if rec['result']['status'] in job.policy.COMPLETE:
                comparison=full_path(p,d,case,rec['result'],verified);reason='full_path_accuracy_passed' if comparison['passed'] else 'full_path_accuracy_failed';break
            require(rec['result']['status'] in ('incomplete_budget','paused_checkpoint'),'No dependent dispatch after any other native status')
        scientific_failure=reason=='full_path_accuracy_failed'
        c.commit(OUT/'results.json',dict(passed=not scientific_failure,bounded_execution_completed=True,reason=reason,exact_restart_passed=True,accepted_physical_steps=accepted,discarded_diagnostic_steps=512,saved_steps_including_diagnostics=used,
            time_s=cp['state']['t'],final_checkpoint_sha256=api.digest(cp),verified_calls=verified,original_full_path_accuracy_passed=comparison is not None and comparison['passed'],
            original_comparison=None if comparison is None else str(OUT/case['id']/'comparison_01/results.json'),successor_cases_started=0,unknown_saved_steps=0,utc=c.utc()))
        c.commit(OUT/'completion.json',dict(passed=not scientific_failure,results_sha256=c.sha(OUT/'results.json')))
    except Exception as issue:
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(issue),traceback=traceback.format_exc(),verified_saved_steps=used,verified_calls=verified,
            unresolved_reservation=active,dependent_dispatch_stopped=True,all_failures_preserved=True,utc=c.utc()));raise

def finalize(code):
    c.bound();p=c.read(PLAN);verification_error=None
    try:verify()
    except Exception as issue:verification_error=repr(issue)
    cp,prefix=seed();raw_parent=prefix;accepted=discarded=known=unknown=calls=0;records=[];contiguous=True;identities=[]
    for q in [OUT/'controller_01/worker_launch.json',*sorted((OUT/'children').glob('*/launch.json'))]:
        x=c.read(q);r=controller.inspect(x['pid'],x['created'],x['command']);require(r['retired'],'Exact numerical identities retired');identities.append(dict(path=str(q),sha256=c.sha(q),inspection=r))
    labels=['serial','split_a','split_b',*[f'production_{i:05d}' for i in range(1,p['maximum_new_production_calls']+1)]]
    for label in labels:
        folder=RUN/label;launch=OUT/'children'/label/'launch.json'
        if not launch.exists():continue
        if not (folder/'call.json.xz').exists():unknown+=caps(label);records.append(dict(label=label,status='unknown',reservation_upper_bound=caps(label)));contiguous=False;continue
        try:
            parent=parent_for(label)[1] if label=='split_b' else raw_parent
            rec,next_prefix=job.codec.read_record(folder/'call.json.xz',p['physical_design_sha256'],parent);n=len(rec['rows'])
            if label.startswith('production_'):raw_parent=next_prefix
        except Exception as issue:
            unknown+=caps(label);records.append(dict(label=label,status='unknown',reservation_upper_bound=caps(label),decode_error=repr(issue)));contiguous=False;continue
        exitfile=launch.with_name('exit.json');exitrow=c.read(exitfile) if exitfile.exists() else {}
        good=(folder/'guard_completion/completion.json').exists() and exitrow.get('returncode')==0 and exitrow.get('forced') is False
        if good:
            try:decoded(label,parent)
            except Exception as issue:good=False;records.append(dict(label=label,admission_error=repr(issue)))
        if verification_error is not None:good=False
        if good and contiguous:
            if label.startswith('production_'):accepted+=n;calls+=1;cp=rec['result']['checkpoint'];prefix=next_prefix;status='accepted'
            else:discarded+=n;status='discarded_diagnostic'
        else:known+=n;status='known_unaccepted';contiguous=False
        records.append(dict(label=label,saved_steps=n,status=status))
    require(accepted+discarded+known+unknown<=p['maximum_saved_steps_including_diagnostics'] and accepted<=p['maximum_new_physical_steps'] and calls<=p['maximum_new_production_calls'],'Every complete/partial/unknown reservation accounted')
    folder=OUT/'final_disposition_01';c.commit(folder/'recoverable/checkpoint.json',cp);c.commit(folder/'recoverable/prefix.json',prefix.reference())
    outcome=c.sealed(OUT/'results.json') if (OUT/'completion.json').exists() else None
    closure_consistent=verification_error is None and contiguous and known==unknown==0 and code==0 and outcome is not None and \
        outcome['accepted_physical_steps']==accepted and outcome['discarded_diagnostic_steps']==discarded and \
        outcome['saved_steps_including_diagnostics']==accepted+discarded and outcome['final_checkpoint_sha256']==api.digest(cp)
    accuracy_passed=False;accuracy_error=None
    if closure_consistent and outcome['original_full_path_accuracy_passed']:
        try:
            comparison=c.sealed(outcome['original_comparison']);c.verify(comparison['path_artifacts'])
            require(comparison['passed'] and comparison['full_path_gates']['passed'] and comparison['case']==base.prior.old.NAME
                and comparison['full_original_start_to_terminal_path'] and comparison['transport_design_sha256']==c.sha(PLAN)
                and comparison['physical_design_sha256']==p['physical_design_sha256'],'Unchanged original full-path gate authenticates')
            accuracy_passed=True
        except Exception as issue:accuracy_error=repr(issue)
    c.commit(folder/'results.json',dict(passed=True,accounting_authenticated=True,run_completed=closure_consistent and outcome['passed'],
        bounded_execution_accounting_complete=closure_consistent,original_accuracy_authentication_error=accuracy_error,
        accepted_physical_steps=accepted,discarded_diagnostic_steps=discarded,known_unaccepted_saved_steps=known,unknown_saved_steps_reservation_upper_bound=unknown,
        cumulative_accepted_physical_steps=cp['state']['steps'],cumulative_accepted_production_calls=p['inherited_production_calls']+calls,time_s=cp['state']['t'],
        final_checkpoint_sha256=api.digest(cp),full_checkpoint_file_sha256=c.sha(folder/'recoverable/checkpoint.json'),records=records,identities=identities,observed_worker_returncode=code,
        source_count=len(p['source_files']),input_count=len(p['inputs']),source_evidence_reauthenticated=verification_error is None,verification_error=verification_error,
        original_full_path_accuracy_passed=accuracy_passed,
        reason='failure_preserved' if outcome is None else outcome['reason'],prior_accepted_ancestry_proof_reused=True,prior_ancestry_not_reexecuted=True,successor_cases_started=0,
        own_live_log_unsealed=True,all_failures_preserved=True,artifacts={str(q):c.sha(q) for q in OUT.rglob('*') if q.is_file() and 'final_disposition_01' not in q.parts and q.parent not in (OUT/'ownership_01',OUT/'supervisor_01')},utc=c.utc()))
    c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
    print('GUARD_TAIL_FINALIZED',accepted,discarded,known,unknown,cp['state']['t'],flush=True)

b=reference.b
frozen_launch=clone(reference.frozen.launch,globals())
def launch():
    try:frozen_launch()
    finally:
        q=OUT/'controller_01/worker_exit.json'
        if q.exists():finalize(c.read(q)['returncode'])

def retirement(code):
    c.bound();problem=None
    try:p=verify()
    except Exception as issue:p=c.read(PLAN);problem=repr(issue)
    closed=c.sealed(OUT/'final_disposition_01/results.json');identities=[]
    for q in [OUT/'controller_01/launch.json',OUT/'controller_01/worker_launch.json',*sorted((OUT/'children').glob('*/launch.json'))]:
        x=c.read(q);r=controller.inspect(x['pid'],x['created'],x['command']);require(r['retired'],'All exact numerical/controller identities retired');identities.append(dict(path=str(q),sha256=c.sha(q),inspection=r))
    try:
        c.verify(closed['artifacts']);require(api.digest(c.read(OUT/'final_disposition_01/recoverable/checkpoint.json'))==closed['final_checkpoint_sha256'],'Final sealed FULL checkpoint')
    except Exception as issue:problem=repr(issue)
    folder=OUT/'retirement_01';c.commit(folder/'results.json',dict(passed=problem is None,exact_owned_work_retired=True,verification_error=problem,
        observed_launcher_returncode=code,identities=identities,closed_logs={str(q):c.sha(q) for f in (OUT/'controller_01',OUT/'ownership_01') for q in f.glob('*.log')},
        final_disposition_sha256=c.sha(OUT/'final_disposition_01/results.json'),full_checkpoint_file_sha256=c.sha(OUT/'final_disposition_01/recoverable/checkpoint.json'),
        own_process_exit_requires_external_observation=True,no_new_numerical_calls=True,utc=c.utc()))
    c.commit(folder/'completion.json',dict(passed=problem is None,results_sha256=c.sha(folder/'results.json')))
    print('GUARD_TAIL_RETIRED',c.sha(folder/'results.json'),problem,flush=True)

def own():
    p=verify();folder=OUT/'ownership_01';folder.mkdir(parents=True,exist_ok=False);me=reference.psutil.Process()
    c.commit(folder/'launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=c.utc()))
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'launch'];stop=clone(controller.stop_owned,{**vars(controller),'c':c})
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        proc=subprocess.Popen(command,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        birth=reference.psutil.Process(proc.pid).create_time();require(reference.psutil.Process(proc.pid).cmdline()==command,'Exact supervised launcher')
        c.commit(folder/'launcher.json',dict(pid=proc.pid,created=birth,command=command,utc=c.utc()))
        while proc.poll() is None:
            if time.time()>=datetime.fromisoformat(p['launcher_cutoff_utc']).timestamp():stop(proc,birth,command,folder);break
            time.sleep(.5)
        code=proc.wait(timeout=10)
    c.commit(folder/'launcher_exit.json',dict(returncode=code,identity=controller.inspect(proc.pid,birth,command),closed_logs={str(q):c.sha(q) for q in folder.glob('*.log')},utc=c.utc()))
    require((OUT/'final_disposition_01/completion.json').exists(),'Final disposition required; retain any incomplete finalizer failure')
    retirement(code)
    print('GUARD_TAIL_OWNED_WORK_RETIRED',code,flush=True)

if __name__=='__main__':
    action=sys.argv[1]
    if action=='call':call(sys.argv[2])
    elif action=='retirement':retirement(int(sys.argv[2]))
    elif action=='controls':print(controls())
    else:{'prepare':prepare,'launch':launch,'run':run,'own':own}[action]()
