"""Runner-only repair: native cooperative returns are resumable, not terminal.

Same absolute Stage244 window and shared budgets; no source is overwritten.
The qualified observer, numerical integration, archive and physical audits are
cloned verbatim from the frozen first runner. Only administration is replaced.
"""
from pathlib import Path
from datetime import datetime,timezone
from types import ModuleType,FunctionType
import sys,os,time,subprocess,traceback,shutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
import continue_guard_v1 as original
api,job,kernel,controller,reference,guard=original.api,original.job,original.kernel,original.controller,original.reference,original.guard
ROOT=original.ROOT;SELF=Path(__file__).resolve();BASE=original.BASE+'_repair_02'
PLAN=ROOT/'stage244_designs'/BASE/'design_02.json';AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage244_evaluations'/BASE;RUN=OUT/'records'
SEED_ROOT=original.OUT/'final_disposition_01';SEED_PREFIX=SEED_ROOT/'recoverable/prefix.json'
SEED_SHA='a58df46575d14d53b8c6f5124c568eafa722ec3bfbf40bf2b2e4e95abff77de9'
FINAL_SHA='c52aec7b5fcc663f1f6df95bebead416f5002333e8450826390c87bb0ca21626'
RETIRE_SHA='5547e1bea27d823053419a08daaf69a3946fee89edb3c10c7e1b5cbbdace61b9'
CAPS={'serial':256,'split_a':128,'split_b':128,'production_01':5000,'production_02':5000,'production_03':4903}
clone=original.clone;require=original.require
c=ModuleType('_stage244_repair_admin');c.__dict__.update(vars(original.c));c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=RUN;c.DESIGNS=PLAN.parent
for key,fn in vars(original.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(original.c):setattr(c,key,clone(fn,vars(c)))
# Consistent private observer views and original code objects are constructed by
# the same admitted runner, rebinding only its administrative deadline context.
ns={**vars(original),**globals()}
observation=original.contextmanager(clone(original.prior.observation.__wrapped__,{**original.prior.observation.__wrapped__.__globals__,'c':c}))
observer=original.SimpleNamespace(**{**vars(original.prior.observer),'scope':observation})
private_job=ModuleType('_stage244_repair_private_job');private_job.__dict__.update(vars(job));private_job.observer=observer
raw=clone(original.prior.old.RAW,{**original.prior.old.RAW.__globals__,'observer':observer})
frozen=original.SimpleNamespace(**{**vars(original.prior.old.baseline.execute.__globals__['frozen']),'raw_execute':raw})
execute=clone(original.prior.old.baseline.execute,{**original.prior.old.baseline.execute.__globals__,'job':private_job,'frozen':frozen})
baseline=original.SimpleNamespace(**{**vars(original.prior.old.baseline),'execute':execute})
private={**original.private,'c':c,'PLAN':PLAN,'AUTH':AUTH,'RUN':RUN,'OUT':OUT,'baseline':baseline}
for name in original.prior.old.old.NAMES:private[name]=clone(original.private[name],private)
controls=clone(original.controls,{**original.controls.__globals__,'execute':execute,'raw':raw,'private_job':private_job,'frozen':frozen})

def seed():
    cp=c.read(SEED_ROOT/'recoverable/checkpoint.json');ref=c.read(SEED_PREFIX)
    require(api.digest(cp)==SEED_SHA and cp['state']['steps']==1234494 and cp['state']['rejected']==0,'Accepted first-attempt FULL seed')
    return cp,job.codec.HistoryState(**ref,history_bytes=job.codec.packed_history(cp['state']['history']))

def prepare():
    c.environment();require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Create-only runner repair')
    parent=c.read(original.PLAN);require(time.time()<datetime.fromisoformat(parent['simulation_cutoff_utc']).timestamp()-120,'Same original remaining window')
    require(c.sha(SEED_ROOT/'results.json')==FINAL_SHA and c.sha(original.OUT/'retirement_01/results.json')==RETIRE_SHA,'Sealed first attempt and exact retirement')
    closed=c.sealed(SEED_ROOT/'results.json');retired=c.sealed(original.OUT/'retirement_01/results.json')
    require(closed['accepted_physical_steps']==4585 and closed['discarded_diagnostic_steps']==512 and closed['known_unaccepted_saved_steps']==closed['unknown_saved_steps_reservation_upper_bound']==0,'Initial shared saved ledger5097')
    for x in retired['identities']:
        launch=c.read(x['path']);require(c.sha(x['path'])==x['sha256'] and controller.inspect(launch['pid'],launch['created'],launch['command'])['retired'],'All old exact identities retired')
    cp,prefix=seed();receipt=c.sealed(original.RUN/'production_01/results.json')
    require(receipt['summary']['status']=='incomplete_budget' and not receipt['summary']['complete_observation'] and receipt['new_saved_steps']==4585,'Short cooperative return is not a terminal observation')
    selected=[SEED_ROOT/'results.json',SEED_ROOT/'completion.json',SEED_ROOT/'recoverable/checkpoint.json',SEED_PREFIX,
        original.OUT/'retirement_01/results.json',original.OUT/'retirement_01/completion.json',original.RUN/'production_01/results.json',
        original.RUN/'production_01/completion.json',original.RUN/'production_01/guard_completion/results.json',
        original.RUN/'production_01/guard_completion/completion.json',Path(prefix.path),Path(prefix.path).with_suffix('.seal.json')]
    imported={str(Path(m.__file__).resolve()):c.sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    sources=original.prior.old.merge_frozen(parent['source_files'],imported,{str(SELF):c.sha(SELF)})
    inputs=original.prior.old.merge_frozen(parent['physical_inputs'],{str(q):c.sha(q) for q in selected})
    reference.plain_verify(sources);reference.plain_verify(inputs);pure=controls()
    a={**{k:v for k,v in parent.items() if k in c.read(original.AUTH)},'stage':'Stage244 runner repair within original window',
        'human_authorization':'Same next-authorized continuation; runner-only correction of premature short-segment stop; no new window or enlarged budgets.',
        'start_utc':datetime.now(timezone.utc).isoformat(),'maximum_saved_steps_including_diagnostics':15415,
        'maximum_new_physical_steps':14903,'maximum_new_production_calls':3,'inherited_production_calls':158,'inherited_physical_steps':1234494,
        'source_files':sources,'inputs':inputs,'prior_attempt_saved_steps':5097,'shared_original_saved_ceiling':20512,
        'prior_attempt_physical_steps':4585,'shared_original_physical_ceiling':20000,'shared_original_production_calls':4,
        'physical_inputs':parent['physical_inputs'],'original_authorization_sha256':c.sha(original.AUTH),
        'runner_repair':'Resume audited incomplete_budget irrespective of row count; stop dependent dispatch at any other nonterminal status. No native45second limit is changed.',
        'production_admission':'Fresh256 versus128+128 exact rows/FULL checkpoint; discard512 new diagnostics and reset accepted first-attempt seed; original physical/lossless plus guard audit before every next segment.'}
    c.commit(AUTH,a);p={**a,'authorization_sha256':c.sha(AUTH),'physical_design_sha256':parent['physical_design_sha256'],
        'numerical_policy_contract_sha256':parent['numerical_policy_contract_sha256'],'checkpoint_contract':cp['contract'],
        'original_binding':parent['original_binding'],'seed_sha256':SEED_SHA,'controls':pure,'prior_ancestry_not_reexecuted':True}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,controls=pure,design_sha256=c.sha(PLAN),source_repair_only=True,new_saved_steps=0,
        diagnosis=dict(native_status='incomplete_budget',native_returned_rows=4585,native_runtime_seconds=45.044630299904384,
            incorrect_rule='n < cap interpreted as terminal',correct_rule='only native terminal statuses end observation'),utc=c.utc()))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('STAGE244_REPAIR_PREPARED',c.sha(PLAN),a['end_utc'],flush=True)

def resources():
    p=c.bound();c.environment()
    require(p['maximum_saved_steps_including_diagnostics']==15415 and p['maximum_new_physical_steps']==14903 and p['maximum_new_production_calls']==3
        and p['prior_attempt_saved_steps']+15415==20512 and p['prior_attempt_physical_steps']+14903<=20000
        and p['step_cap_per_call']==5000 and p['workers']==p['threads']==p['maximum_unverified_records']==1,'Unchanged shared ceilings')
    require(shutil.disk_usage(ROOT).free>p['minimum_free_disk_bytes'],'Disk reserve')
    size=sum(q.stat().st_size for f in (OUT,PLAN.parent,original.OUT,original.PLAN.parent) for q in f.rglob('*') if q.is_file())
    require(size<p['maximum_output_bytes'],'Shared original output cap')
    return p

def parent_for(label):
    if label=='split_b':folder=RUN/'split_a'
    elif label.startswith('production_') and int(label[-2:])>1:folder=RUN/f'production_{int(label[-2:])-1:02d}'
    else:return (*seed(),c.sha(original.RUN/'production_01/results.json'))
    admission=c.sealed(folder/'guard_completion/results.json');require(admission['passed'],'Previous complete admission');c.verify(admission['artifacts'])
    cp=c.read(folder/'full_checkpoint.json');ref=c.read(folder/'prefix.json')
    return cp,job.codec.HistoryState(**ref,history_bytes=job.codec.packed_history(cp['state']['history'])),c.sha(folder/'results.json')

def run():
    p=verify();proc=reference.psutil.Process();proc.cpu_affinity([14]);require(not (OUT/'launch.json').exists(),'No duplicate repair worker')
    c.commit(OUT/'launch.json',dict(pid=proc.pid,created=proc.create_time(),command=proc.cmdline(),utc=c.utc()))
    used=accepted=0;active=None;verified=[]
    try:
        for label in ('serial','split_a','split_b'):
            active=dict(label=label,maximum_steps=CAPS[label]);child(label);used+=CAPS[label];verified.append(label);active=None
        cp,prefix=seed();serial,_=decoded('serial',prefix);a,pa=decoded('split_a',prefix);b,_=decoded('split_b',pa)
        require(serial['rows']==a['rows']+b['rows'] and api.digest(serial['result']['checkpoint'])==api.digest(b['result']['checkpoint']),'Exact fresh repair restart')
        gate=OUT/'restart_01/results.json';c.commit(gate,dict(passed=True,discarded_diagnostic_steps=512,exact_rows=True,exact_full_checkpoint=True,diagnostic_promoted=False,utc=c.utc()))
        c.commit(gate.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(gate)))
        for i in range(1,4):
            resources();label=f'production_{i:02d}';require(used+CAPS[label]<=15415 and accepted+CAPS[label]<=14903,'Remaining shared budget')
            active=dict(label=label,maximum_steps=CAPS[label]);child(label);rec,prefix=decoded(label,prefix)
            n=len(rec['rows']);accepted+=n;used+=n;cp=rec['result']['checkpoint'];verified.append(label);active=None
            c.commit(OUT/f'progress_{i:02d}.json',dict(accepted_physical_steps=accepted,cumulative_physical_steps=cp['state']['steps'],cumulative_production_calls=158+i,
                time_s=cp['state']['t'],native_status=rec['result']['status'],full_checkpoint_sha256=api.digest(cp),utc=c.utc()))
            if rec['result']['status'] in job.policy.COMPLETE:break
            require(rec['result']['status'] in ('incomplete_budget','paused_checkpoint'),'No dependent dispatch after any other native status')
        c.commit(OUT/'results.json',dict(passed=True,exact_restart_passed=True,accepted_physical_steps=accepted,discarded_diagnostic_steps=512,
            saved_steps_including_diagnostics=used,verified_calls=verified,time_s=cp['state']['t'],final_checkpoint_sha256=api.digest(cp),
            original_full_path_accuracy_passed=False,successor_cases_started=0,unknown_saved_steps=0,utc=c.utc()))
        c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    except Exception as issue:
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(issue),traceback=traceback.format_exc(),verified_saved_steps=used,verified_calls=verified,
            unresolved_reservation=active,dependent_dispatch_stopped=True,all_failures_preserved=True,utc=c.utc()));raise

# Only numerical-budget/accounting literals differ in these administrative
# clones. The qualified model, observer, raw storage and transaction code objects
# remain identical; call checks inherited158 rather than157 production calls.
def admin_clone(fn,changes):
    code=fn.__code__.replace(co_consts=tuple(changes.get(x,x) if type(x) is int else x for x in fn.__code__.co_consts))
    return FunctionType(code,ns,fn.__name__,fn.__defaults__,fn.__closure__)
ns.update(globals())
for name in ('verify','child','decoded','retirement','launch'):
    ns[name]=globals()[name]=clone(getattr(original,name),ns)
call=admin_clone(original.call,{157:158});ns['call']=call
finalize=admin_clone(original.finalize,{20512:15415,20000:14903,4:3,157:158});ns['finalize']=finalize
b=reference.b;frozen_launch=clone(reference.frozen.launch,ns);ns['frozen_launch']=frozen_launch
ns.update(globals())

if __name__=='__main__':
    action=sys.argv[1]
    if action=='call':call(sys.argv[2])
    elif action=='retirement':retirement(int(sys.argv[2]))
    elif action=='controls':print(controls())
    else:{'prepare':prepare,'launch':launch,'run':run}[action]()
