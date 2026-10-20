"""Fresh-process restart across the failed step, then one bounded transfer.

Uses original transaction/storage/physical auditors. Adds only the passing
Stage242 guard to the actual observer, with fresh per-pose history.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import ModuleType,SimpleNamespace,FunctionType
from contextlib import contextmanager
import os,sys,copy,time,subprocess,traceback,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage243_staging'),str(ROOT/'stage242_staging'),str(ROOT/'stage240_staging'),str(ROOT/'stage238_staging')]
import replay_original_context_v1 as reference
import continue_lm_case_v1 as old
import per_pose_guard_v1 as guard
api,job,kernel,controller=old.api,old.job,old.kernel,old.controller
SELF=Path(__file__).resolve();BASE='cycle_guard_restart_20261012'
PLAN=ROOT/'stage243_designs'/BASE/'design_01.json';AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage243_evaluations'/BASE;RUN=OUT/'records';NAME=old.NAME
def clone(fn,ns):return FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__)
c=ModuleType('_stage243_admin');c.__dict__.update(vars(reference.c));c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=RUN;c.DESIGNS=PLAN.parent
for key,fn in vars(reference.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(reference.c):setattr(c,key,clone(fn,vars(c)))

@contextmanager
def observation(runtime,enabled):
    api.require(enabled is True and runtime is job.parent.engine.runtime,'Exact original observed physical runtime')
    with old.ORIGINAL_OBSERVER.scope(runtime,enabled) as trace:
        with kernel.scope(),guard.scope(trace,datetime.fromisoformat(c.bound()['simulation_cutoff_utc']).timestamp()):yield trace

observer=SimpleNamespace(**{**vars(old.ORIGINAL_OBSERVER),'scope':observation})
private_job=ModuleType('_stage243_private_job');private_job.__dict__.update(vars(job));private_job.observer=observer
raw=clone(old.RAW,{**old.RAW.__globals__,'observer':observer})
frozen=SimpleNamespace(**{**vars(old.baseline.execute.__globals__['frozen']),'raw_execute':raw})
execute=clone(old.baseline.execute,{**old.baseline.execute.__globals__,'job':private_job,'frozen':frozen})
baseline=SimpleNamespace(**{**vars(old.baseline),'execute':execute})
private={**old.PRIVATE,'c':c,'PLAN':PLAN,'AUTH':AUTH,'RUN':RUN,'OUT':OUT,'baseline':baseline}
for name in old.old.NAMES:private[name]=clone(old.PRIVATE[name],private)
PREREQUISITE=ROOT/'stage242_evaluations/identical_inputs_20261012/final_disposition_01/results.json'
PREREQUISITE_SHA='58b55665d8177d6eb1eeb942e33b1071001865a2dfb6223939c48d7dc2508fe1'
SEED_ROOT=ROOT/'stage238_evaluations/fibre_lm_20261009/final_disposition_01'
SEED_SHA='b25d74a1d7b8baa305888d9fcc1e24949ddf1d01d6d3bddcbe20fcf44ee31626'

def require(v,m):api.require(v,m)
def controls():
    require(execute.__code__ is old.baseline.execute.__code__ and raw.__code__ is old.RAW.__code__,'Original integration/storage bytecode')
    require({k for k,v in execute.__globals__.items() if v is not old.baseline.execute.__globals__[k]}=={'job','frozen'},'Only consistent private observer views change')
    require(raw.__globals__['observer'] is private_job.observer is frozen.raw_execute.__globals__['observer'],'Actual observer views agree')
    return dict(passed=True,adapter=guard.controls(),outer_calls=0,contact_calls=0)

def seed():
    cp=c.read(SEED_ROOT/'recoverable/checkpoint.json');ref=c.read(SEED_ROOT/'recoverable/prefix.json')
    require(api.digest(cp)==SEED_SHA and cp['state']['rejected']==0 and cp['state']['steps']==1228885,'Only the accepted full seed, never rejected segment36')
    prefix=job.codec.HistoryState(**ref,history_bytes=job.codec.packed_history(cp['state']['history']))
    return cp,prefix

def prepare():
    c.environment();require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Create-only repair transfer qualification')
    require(c.sha(PREREQUISITE)==PREREQUISITE_SHA,'Exact passing same-input/covariance/repair gate')
    gate=c.sealed(PREREQUISITE);require(gate['fixed_pose_repair_qualified'] and not gate['transport_installed'],'Fixed-pose qualification, not existing transport promotion')
    reference.plain_verify(gate['artifacts']);pure=controls();cp,prefix=seed();previous_plan=c.read(old.PLAN)
    selected=[PREREQUISITE,PREREQUISITE.with_name('completion.json'),SEED_ROOT/'results.json',SEED_ROOT/'completion.json',
        SEED_ROOT/'recoverable/checkpoint.json',SEED_ROOT/'recoverable/prefix.json',Path(prefix.path),Path(prefix.path).with_suffix('.seal.json'),
        ROOT/'stage238_evaluations/fibre_lm_20261009/retirement_01/results.json',ROOT/'stage238_evaluations/fibre_lm_20261009/retirement_01/completion.json']
    reference.plain_verify({str(p):c.sha(p) for p in selected})
    retired=c.sealed(selected[-2]);require(retired['retirement_and_accounting_authenticated'] and retired['last_accepted_full_checkpoint_sha256']==SEED_SHA,
        'Authenticated accepted full history and original production ancestry')
    imported={str(Path(m.__file__).resolve()):c.sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    gateplan=c.read(ROOT/'stage242_designs/identical_inputs_20261012/design_01.json')
    sources=old.merge_frozen(previous_plan['source_files'],gateplan['source_files'],imported,{str(SELF):c.sha(SELF),str(Path(guard.__file__).resolve()):c.sha(guard.__file__)})
    inputs=old.merge_frozen(previous_plan['physical_inputs'],{str(p):c.sha(p) for p in selected})
    reference.plain_verify(sources);reference.plain_verify(inputs)
    start=datetime.now(timezone.utc);end=start+timedelta(seconds=1200);cut=end-timedelta(seconds=120);simcut=cut-timedelta(seconds=60)
    a=dict(stage='Stage243 cycle-guard fresh-process restart and short transfer',
        human_authorization='Human requested bottleneck resolution with physical and accuracy gates preserved. This bounded qualification and one short transfer are necessary before broader admission; no population or overnight campaign.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=cut.isoformat(),simulation_cutoff_utc=simcut.isoformat(),
        maximum_saved_steps_including_diagnostics=3072,discarded_diagnostic_steps_planned=2048,maximum_new_physical_steps=1024,
        maximum_new_production_calls=1,step_cap_per_call=1024,maximum_unverified_records=1,workers=1,threads=1,logical_cpu=14,
        maximum_output_bytes=256*1024**2,minimum_free_disk_bytes=20*1024**3,maximum_cumulative_physical_steps_per_case=5000000,
        maximum_cumulative_calls_per_case=1500,inherited_production_calls=156,
        one_active_solver_child=True,solver_children_sequential_and_fresh_process=True,
        source_files=sources,inputs=inputs,physical_inputs=previous_plan['physical_inputs'],
        candidate_production_authorized=True,production_admission='Only after fresh1024 versus512+512 rows/FULL checkpoint exact, all original independent audits pass, and canonical guard actually executes in serial and splitB. Discard diagnostics and reset original sealed seed.',
        physical_changes=[],accuracy_gate_changes=[],numerical_cap_changes=[],
        candidate_policy='Same tested original scalar primitive only after exact per-pose two-cycle; no guard state crosses poses/restarts.',
        claim='Late-seed restart and one bounded original-equation transfer; no full-path, population, validation or representative-cost claim.')
    c.commit(AUTH,a)
    p={**a,'authorization_sha256':c.sha(AUTH),'physical_design_sha256':c.sha(job.DESIGN),'numerical_policy_contract_sha256':c.sha(job.WORK),
        'checkpoint_contract':cp['contract'],'original_binding':previous_plan['original_binding'],'seed_sha256':SEED_SHA,'controls':pure,
        'parent_acceptance_and_history_proof_reused':True,'inherited_accepted_raw_chain_not_reexecuted':True}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,controls=pure,design_sha256=c.sha(PLAN),new_saved_steps=0,utc=c.utc()))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('STAGE243_PREPARED',c.sha(PLAN),end.isoformat(),flush=True)

def resources():
    a=c.bound();c.environment()
    require(a['maximum_saved_steps_including_diagnostics']==3072 and a['maximum_new_physical_steps']==1024
        and a['step_cap_per_call']==1024 and a['workers']==a['threads']==1 and a['maximum_unverified_records']==1,
        'Frozen small qualification/transfer budget')
    require(shutil.disk_usage(ROOT).free>a['minimum_free_disk_bytes'],'Disk reserve')
    require(sum(q.stat().st_size for folder in (OUT,PLAN.parent) for q in folder.rglob('*') if q.is_file())<a['maximum_output_bytes'],'Output cap')
    return a

def verify():
    a=resources();p=c.read(PLAN);require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH),'Immutable repair plan')
    require(all(p[k]==v for k,v in a.items()),'Exact bounded admission')
    c.verify(p['source_files']);c.verify(p['inputs']);require(c.sha(PREREQUISITE)==PREREQUISITE_SHA,'Unchanged qualified fixed-pose prerequisite')
    require(c.sealed(OUT/'preparation_01/results.json')['design_sha256']==c.sha(PLAN),'Passing preparation')
    return p

def call(label):
    p=verify();proc=reference.psutil.Process();proc.cpu_affinity([14]);d,case=old.original_case()
    cp,prefix=seed();previous=c.sha(SEED_ROOT/'results.json');cap=1024
    if label=='split_b':
        cp=c.read(RUN/'split_a/full_checkpoint.json');ref=c.read(RUN/'split_a/prefix.json')
        prefix=job.codec.HistoryState(**ref,history_bytes=job.codec.packed_history(cp['state']['history']))
        previous=c.sha(RUN/'split_a/results.json');cap=512
    elif label=='split_a':cap=512
    require(label in ('serial','split_a','split_b','transfer'),'Only frozen calls')
    if label=='transfer':require(c.sealed(OUT/'restart_01/results.json')['passed'],'No production before exact restart')
    reference.JOB.parent.b.old.parent.configure();kernel.warm();kernel.reset()
    geometry=baseline.geometry_for(case);before=api.digest(cp)
    rec,prefix,receipt=private['segment'](p,d,case,geometry,cp,prefix,RUN/label,cap,previous,
        'production' if label=='transfer' else 'restart_diagnostic')
    extra=guard.audit(rec)
    require(len(rec['rows'])==cap and rec['result']['rejected']==0 and api.digest(cp)==before,'Complete audited increment and unmodified seed')
    c.commit(RUN/label/'guard_audit.json',extra);c.commit(RUN/label/'full_checkpoint.json',rec['result']['checkpoint']);c.commit(RUN/label/'prefix.json',prefix.reference())
    print('STAGE243_CALL_VERIFIED',label,cap,extra['canonical_calls'],rec['result']['checkpoint']['state']['t'],flush=True)

def child(label):
    p=verify();folder=OUT/'children'/label;folder.mkdir(parents=True,exist_ok=False)
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'call',label]
    stop=clone(controller.stop_owned,{**vars(controller),'c':c});epoch=datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp()
    require(time.time()<epoch-60,'Complete child and audit time reserve')
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        process=subprocess.Popen(command,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        birth=reference.psutil.Process(process.pid).create_time();require(reference.psutil.Process(process.pid).cmdline()==command,'Exact fresh solver child identity')
        c.commit(folder/'launch.json',dict(pid=process.pid,created=birth,command=command,utc=c.utc(),reserved_steps=512 if label.startswith('split') else 1024))
        forced=False
        while process.poll() is None:
            if time.time()>=epoch:stop(process,birth,command,folder);forced=True;break
            time.sleep(.25)
        code=process.wait(timeout=10)
    identity=controller.inspect(process.pid,birth,command);require(identity['retired'],'Fresh solver process retired')
    c.commit(folder/'exit.json',dict(returncode=code,forced=forced,identity=identity,closed_logs={str(q):c.sha(q) for q in folder.glob('*.log')},utc=c.utc()))
    require(code==0 and not forced,'No dependent dispatch after child failure')

def decoded(label,parent):
    rec,prefix=job.codec.read_record(RUN/label/'call.json.xz',c.sha(job.DESIGN),parent)
    receipt=c.sealed(RUN/label/'results.json');require(receipt['artifacts'][str(RUN/label/'call.json.xz')]==c.sha(RUN/label/'call.json.xz'),'Original sealed transaction raw body')
    require(api.digest(rec['result']['checkpoint'])==api.digest(c.read(RUN/label/'full_checkpoint.json')),'Complete lossless checkpoint/history')
    extra=guard.audit(rec);require(extra==c.read(RUN/label/'guard_audit.json'),'Independent journal reconstruction')
    return rec,prefix

def run():
    p=verify();proc=reference.psutil.Process();proc.cpu_affinity([14])
    require(not (OUT/'launch.json').exists(),'No duplicate qualification orchestrator')
    c.commit(OUT/'launch.json',dict(pid=proc.pid,created=proc.create_time(),command=proc.cmdline(),utc=c.utc()))
    used=0;verified=[];active=None
    try:
        for label,cap in [('serial',1024),('split_a',512),('split_b',512)]:
            require(used+cap<=2048,'Diagnostic shared budget');active=dict(label=label,maximum_steps=cap)
            child(label);used+=cap;verified.append(label);active=None
        cp,prefix=seed();serial,_=decoded('serial',prefix);a,pa=decoded('split_a',prefix);b,pb=decoded('split_b',pa)
        exact_rows=serial['rows']==a['rows']+b['rows'];exact_cp=api.digest(serial['result']['checkpoint'])==api.digest(b['result']['checkpoint'])
        serial_guard=c.read(RUN/'serial/guard_audit.json');split_guard=c.read(RUN/'split_b/guard_audit.json')
        require(exact_rows and exact_cp and serial_guard['canonical_calls']>0 and split_guard['canonical_calls']>0,'Exact fresh-process restart actually crosses cycle repair')
        proof=dict(passed=True,diagnostic_saved_steps=2048,exact_serial_split_rows=True,exact_full_checkpoint=True,
            actual_canonical_calls_serial=serial_guard['canonical_calls'],actual_canonical_calls_split_b=split_guard['canonical_calls'],
            original_seed_unchanged=api.digest(cp)==SEED_SHA,diagnostic_trajectory_promoted=False,all_original_physical_audits_passed=True,
            artifacts={str(q):c.sha(q) for q in RUN.rglob('*') if q.is_file()},utc=c.utc())
        c.commit(OUT/'restart_01/results.json',proof);c.commit(OUT/'restart_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'restart_01/results.json')))
        require(used+1024<=3072,'One short production reservation');active=dict(label='transfer',maximum_steps=1024)
        child('transfer');used+=1024;verified.append('transfer');active=None
        transfer,_=decoded('transfer',prefix);require(transfer['rows']==serial['rows'] and api.digest(transfer['result']['checkpoint'])==api.digest(serial['result']['checkpoint']),
            'Production resets accepted original seed; discarded diagnostics cannot substitute')
        c.commit(OUT/'results.json',dict(passed=True,exact_restart_passed=True,accepted_physical_steps=1024,discarded_diagnostic_steps=2048,
            saved_steps_including_diagnostics=3072,time_s=transfer['result']['checkpoint']['state']['t'],final_checkpoint_sha256=api.digest(transfer['result']['checkpoint']),
            full_path_accuracy_passed=False,successor_cases_started=0,verified_calls=verified,unknown_saved_steps=0,utc=c.utc()))
        c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    except Exception as issue:
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(issue),traceback=traceback.format_exc(),verified_saved_steps=used,verified_calls=verified,
            unresolved_reservation=active,dependent_dispatch_stopped=True,all_failures_preserved=True,utc=c.utc()));raise

# Reviewed parent controller: one sequential numerical child at a time. The
# simulation children retire60s before the orchestrator cutoff to avoid orphans.
b=reference.b
launch=clone(reference.frozen.launch,globals())

def retire(code):
    p=verify();identities=[]
    for q in [OUT/'controller_01/launch.json',OUT/'controller_01/worker_launch.json',*sorted((OUT/'children').glob('*/launch.json'))]:
        x=c.read(q);inspection=controller.inspect(x['pid'],x['created'],x['command']);require(inspection['retired'],'Exact owned identity retired')
        identities.append(dict(path=str(q),sha256=c.sha(q),inspection=inspection))
    complete=(OUT/'completion.json').exists();cp,prefix=seed();known_unaccepted=0;unknown=0;discarded=accepted=0;records=[]
    for label,cap in [('serial',1024),('split_a',512),('split_b',512),('transfer',1024)]:
        folder=RUN/label
        if not (folder/'launch.json').exists():continue
        if not (folder/'call.json.xz').exists():unknown+=cap;records.append(dict(label=label,status='unknown',maximum_steps=cap));continue
        parent=prefix
        if label=='split_b':
            parent=job.codec.HistoryState(**c.read(RUN/'split_a/prefix.json'),history_bytes=job.codec.packed_history(c.read(RUN/'split_a/full_checkpoint.json')['state']['history']))
        rec,next_prefix=job.codec.read_record(folder/'call.json.xz',c.sha(job.DESIGN),parent);n=len(rec['rows'])
        good=(folder/'completion.json').exists() and (folder/'guard_audit.json').exists()
        if good:
            decoded(label,parent)
            if label=='transfer' and complete:accepted+=n;cp=rec['result']['checkpoint']
            else:discarded+=n
        else:known_unaccepted+=n
        records.append(dict(label=label,saved_steps=n,status='accepted' if good and label=='transfer' and complete else 'discarded_diagnostic' if good else 'known_unaccepted'))
    if complete:require(code==0 and accepted==1024 and discarded==2048 and known_unaccepted==unknown==0,'Complete exact qualification/transfer ledger')
    require(accepted+discarded+known_unaccepted+unknown<=3072,'All partial/unknown work within frozen shared budget')
    receipt=OUT/'final_disposition_01/results.json'
    c.commit(receipt.parent/'recoverable/checkpoint.json',cp)
    result=dict(passed=True,accounting_authenticated=True,exact_restart_and_transfer_passed=complete,
        accepted_physical_steps=accepted,discarded_diagnostic_steps=discarded,known_unaccepted_saved_steps=known_unaccepted,unknown_saved_steps_reservation_upper_bound=unknown,
        final_checkpoint_sha256=api.digest(cp),time_s=cp['state']['t'],cumulative_accepted_physical_steps=cp['state']['steps'],
        cumulative_accepted_production_calls=156+(1 if accepted else 0),records=records,identities=identities,controller_returncode_observed=code,
        source_count=len(p['source_files']),input_count=len(p['inputs']),design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
        artifacts={str(q):c.sha(q) for q in OUT.rglob('*') if q.is_file() and 'final_disposition_01' not in q.parts},
        full_path_accuracy_passed=False,population_campaign_started=False,all_old_failures_preserved=True,utc=c.utc())
    c.commit(receipt,result);c.commit(receipt.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(receipt)))
    print('STAGE243_RETIRED',c.sha(receipt),'exact_restart_and_transfer_passed=',complete,flush=True)

if __name__=='__main__':
    action=sys.argv[1]
    if action=='call':call(sys.argv[2])
    elif action=='retire':retire(int(sys.argv[2]))
    elif action=='controls':print(controls())
    else:{'prepare':prepare,'launch':launch,'run':run}[action]()
