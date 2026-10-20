"""Bounded continuation of the qualified per-pose cycle guard.

Reuses Stage243's physical transaction and observer adapter verbatim. Numerical
children are fresh, sequential, and audited before any dependent dispatch.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import ModuleType,SimpleNamespace,FunctionType
from contextlib import contextmanager
import os,sys,time,subprocess,traceback,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage243_staging'))
import qualify_guard_v1 as prior
api,job,kernel,controller,reference,guard=prior.api,prior.job,prior.kernel,prior.controller,prior.reference,prior.guard
SELF=Path(__file__).resolve();BASE='guard_continuation_20261012'
PLAN=ROOT/'stage244_designs'/BASE/'design_01.json';AUTH=PLAN.with_name('authorization_01.json')
OUT=ROOT/'stage244_evaluations'/BASE;RUN=OUT/'records'
SEED_ROOT=prior.OUT/'final_disposition_01';SEED_PREFIX=prior.RUN/'transfer/prefix.json'
SEED_SHA='9998feebdd40ca0eaa1fd8fa8f5609143ad272ff203319c3865e608e6f7390ab'
FINAL_SHA='e45fd3d52260908e7bb4aead690c53cf8b746109e39dc62bc80f0b5c2518c7e4'
RETIRE_SHA='1dc5745f3808deea684a39839832a6695b29a51668e99a267d5bb972b388831b'
CAPS={'serial':256,'split_a':128,'split_b':128,**{f'production_{i:02d}':5000 for i in range(1,5)}}
clone=prior.clone;require=prior.require
c=ModuleType('_stage244_admin');c.__dict__.update(vars(prior.c))
c.PLAN=PLAN;c.AUTH=AUTH;c.OUT=OUT;c.RUN=RUN;c.DESIGNS=PLAN.parent
for key,fn in vars(prior.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(prior.c):setattr(c,key,clone(fn,vars(c)))

observation=clone(prior.observation.__wrapped__,{**prior.observation.__wrapped__.__globals__,'c':c})
observation=contextmanager(observation)
observer=SimpleNamespace(**{**vars(prior.observer),'scope':observation})
private_job=ModuleType('_stage244_private_job');private_job.__dict__.update(vars(job));private_job.observer=observer
raw=clone(prior.old.RAW,{**prior.old.RAW.__globals__,'observer':observer})
frozen=SimpleNamespace(**{**vars(prior.old.baseline.execute.__globals__['frozen']),'raw_execute':raw})
execute=clone(prior.old.baseline.execute,{**prior.old.baseline.execute.__globals__,'job':private_job,'frozen':frozen})
baseline=SimpleNamespace(**{**vars(prior.old.baseline),'execute':execute})
private={**prior.old.PRIVATE,'c':c,'PLAN':PLAN,'AUTH':AUTH,'RUN':RUN,'OUT':OUT,'baseline':baseline}
for name in prior.old.old.NAMES:private[name]=clone(prior.old.PRIVATE[name],private)
controls=clone(prior.controls,{**prior.controls.__globals__,'execute':execute,'raw':raw,'private_job':private_job,'frozen':frozen})

def seed():
    cp=c.read(SEED_ROOT/'recoverable/checkpoint.json');ref=c.read(SEED_PREFIX)
    require(api.digest(cp)==SEED_SHA and cp['state']['rejected']==0 and cp['state']['steps']==1229909,'Accepted FULL Stage243 seed only')
    return cp,job.codec.HistoryState(**ref,history_bytes=job.codec.packed_history(cp['state']['history']))

def prepare():
    c.environment();require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Create-only bounded continuation')
    require(c.sha(SEED_ROOT/'results.json')==FINAL_SHA and c.sha(prior.OUT/'retirement_01/results.json')==RETIRE_SHA,'Exact accepted restart/transfer and retirement')
    gate=c.sealed(SEED_ROOT/'results.json');retired=c.sealed(prior.OUT/'retirement_01/results.json')
    require(gate['exact_restart_and_transfer_passed'] and gate['known_unaccepted_saved_steps']==gate['unknown_saved_steps_reservation_upper_bound']==0,'No unresolved seed work')
    require(retired['passed'] and retired['full_checkpoint_semantic_sha256']==SEED_SHA and retired['full_checkpoint_file_sha256']==c.sha(SEED_ROOT/'recoverable/checkpoint.json'),'Complete authenticated history')
    for x in retired['exact_owned_identities']:
        launch=c.read(x['path']);require(c.sha(x['path'])==x['launch_sha256'] and controller.inspect(launch['pid'],launch['created'],launch['command'])['retired'],'Old exact identities retired')
    cp,prefix=seed();previous=c.read(prior.PLAN);pure=controls()
    selected=[SEED_ROOT/'results.json',SEED_ROOT/'completion.json',SEED_ROOT/'recoverable/checkpoint.json',
        prior.OUT/'retirement_01/results.json',prior.OUT/'retirement_01/completion.json',SEED_PREFIX,
        prior.RUN/'transfer/results.json',prior.RUN/'transfer/completion.json',prior.RUN/'transfer/guard_audit.json',
        Path(prefix.path),Path(prefix.path).with_suffix('.seal.json')]
    imported={str(Path(m.__file__).resolve()):c.sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    sources=prior.old.merge_frozen(previous['source_files'],imported,{str(SELF):c.sha(SELF)})
    inputs=prior.old.merge_frozen(previous['physical_inputs'],{str(q):c.sha(q) for q in selected})
    reference.plain_verify(sources);reference.plain_verify(inputs)
    start=datetime.now(timezone.utc);end=start+timedelta(seconds=1800);cut=end-timedelta(seconds=180)
    a=dict(stage='Stage244 bounded qualified-guard continuation',human_authorization='Human requested next after exact restart and accepted transfer; conservative continuation of the same case, no overnight or population campaign.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),worker_cutoff_utc=(end-timedelta(seconds=120)).isoformat(),simulation_cutoff_utc=cut.isoformat(),
        maximum_saved_steps_including_diagnostics=20512,discarded_diagnostic_steps_planned=512,maximum_new_physical_steps=20000,
        maximum_new_production_calls=4,step_cap_per_call=5000,maximum_unverified_records=1,workers=1,threads=1,logical_cpu=14,
        maximum_output_bytes=512*1024**2,minimum_free_disk_bytes=20*1024**3,maximum_cumulative_physical_steps_per_case=5000000,
        maximum_cumulative_calls_per_case=1500,inherited_production_calls=157,inherited_physical_steps=1229909,
        source_files=sources,inputs=inputs,physical_inputs=previous['physical_inputs'],candidate_production_authorized=True,
        production_admission='Fresh256 versus128+128 accepted rows and FULL checkpoint/history exact. Discard diagnostics; reset authenticated Stage243 production seed. Each original transaction, lossless raw and guard provenance must pass before successor segment.',
        candidate_policy='Exact unchanged Stage243 per-pose guard and Stage242 stateless scalar after exact two-cycle.',
        physical_changes=[],accuracy_gate_changes=[],numerical_cap_changes=[],successor_cases_authorized=False,
        automatic_continuation_authorized=False,retain_all_failures=True,
        claim='Bounded numerical continuation only; complete horizon and original whole-path/event gates remain necessary.')
    c.commit(AUTH,a)
    p={**a,'authorization_sha256':c.sha(AUTH),'physical_design_sha256':c.sha(job.DESIGN),'numerical_policy_contract_sha256':c.sha(job.WORK),
        'checkpoint_contract':cp['contract'],'original_binding':previous['original_binding'],'seed_sha256':SEED_SHA,'controls':pure,
        'parent_raw_history_ancestry_proof_reused':True,'prior_ancestry_not_reexecuted':True}
    p['binding']=c.digest(p);c.commit(PLAN,p)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,controls=pure,design_sha256=c.sha(PLAN),new_saved_steps=0,utc=c.utc()))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('STAGE244_PREPARED',c.sha(PLAN),end.isoformat(),flush=True)

def resources():
    p=c.bound();c.environment()
    require(p['maximum_saved_steps_including_diagnostics']==20512 and p['maximum_new_physical_steps']==20000 and p['step_cap_per_call']==5000
        and p['workers']==p['threads']==p['maximum_unverified_records']==1,'Frozen bounded resources')
    require(shutil.disk_usage(ROOT).free>p['minimum_free_disk_bytes'],'Disk reserve')
    require(sum(q.stat().st_size for f in (OUT,PLAN.parent) for q in f.rglob('*') if q.is_file())<p['maximum_output_bytes'],'Output cap')
    return p

def verify():
    a=resources();p=c.read(PLAN)
    require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH) and all(p[k]==v for k,v in a.items()),'Immutable bounded design')
    c.verify(p['source_files']);c.verify(p['inputs'])
    require(c.sealed(OUT/'preparation_01/results.json')['design_sha256']==c.sha(PLAN),'Passing preparation')
    return p

def parent_for(label):
    if label=='split_b':folder=RUN/'split_a'
    elif label.startswith('production_') and int(label[-2:])>1:folder=RUN/f'production_{int(label[-2:])-1:02d}'
    else:return (*seed(),c.sha(prior.RUN/'transfer/results.json'))
    admission=c.sealed(folder/'guard_completion/results.json')
    require(admission['passed'],'Preceding complete guard admission');c.verify(admission['artifacts'])
    cp=c.read(folder/'full_checkpoint.json');ref=c.read(folder/'prefix.json')
    return cp,job.codec.HistoryState(**ref,history_bytes=job.codec.packed_history(cp['state']['history'])),c.sha(folder/'results.json')

def call(label):
    p=verify();require(label in CAPS,'Only declared calls');reference.psutil.Process().cpu_affinity([14])
    if label.startswith('production_'):require(c.sealed(OUT/'restart_01/results.json')['passed'],'Exact fresh restart before production')
    cp,prefix,previous=parent_for(label);d,case=prior.old.original_case();before=api.digest(cp)
    require(cp['state']['steps']+CAPS[label]<=5000000 and 157+(int(label[-2:]) if label.startswith('production_') else 0)<=1500,'Inherited cumulative ceilings')
    reference.JOB.parent.b.old.parent.configure();kernel.warm();kernel.reset();geometry=baseline.geometry_for(case)
    rec,prefix,receipt=private['segment'](p,d,case,geometry,cp,prefix,RUN/label,CAPS[label],previous,
        'production' if label.startswith('production_') else 'restart_diagnostic')
    extra=guard.audit(rec)
    require(0<len(rec['rows'])<=CAPS[label] and rec['result']['rejected']==0 and api.digest(cp)==before,'Audited increment and unchanged input seed')
    if not label.startswith('production_'):require(len(rec['rows'])==CAPS[label],'Complete restart diagnostic')
    c.commit(RUN/label/'guard_audit.json',extra);c.commit(RUN/label/'full_checkpoint.json',rec['result']['checkpoint']);c.commit(RUN/label/'prefix.json',prefix.reference())
    gate=RUN/label/'guard_completion/results.json'
    c.commit(gate,dict(passed=True,saved_steps=len(rec['rows']),input_checkpoint_sha256=before,final_checkpoint_sha256=api.digest(rec['result']['checkpoint']),
        original_physical_and_lossless_audits_passed=True,guard_audit=extra,artifacts={str(q):c.sha(q) for q in (RUN/label).glob('*') if q.is_file()},utc=c.utc()))
    c.commit(gate.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(gate)))
    print('STAGE244_CALL_VERIFIED',label,len(rec['rows']),extra['canonical_calls'],rec['result']['checkpoint']['state']['t'],flush=True)

def child(label):
    p=verify();folder=OUT/'children'/label;folder.mkdir(parents=True,exist_ok=False)
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'call',label]
    stop=clone(controller.stop_owned,{**vars(controller),'c':c});epoch=datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp()
    require(time.time()<epoch-60,'Child and audit time reserve')
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        process=subprocess.Popen(command,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        birth=reference.psutil.Process(process.pid).create_time();require(reference.psutil.Process(process.pid).cmdline()==command,'Exact child identity')
        c.commit(folder/'launch.json',dict(pid=process.pid,created=birth,command=command,utc=c.utc(),reserved_steps=CAPS[label]))
        forced=False
        while process.poll() is None:
            if time.time()>=epoch:stop(process,birth,command,folder);forced=True;break
            time.sleep(.25)
        code=process.wait(timeout=10)
    identity=controller.inspect(process.pid,birth,command);require(identity['retired'],'Fresh solver retired')
    c.commit(folder/'exit.json',dict(returncode=code,forced=forced,identity=identity,closed_logs={str(q):c.sha(q) for q in folder.glob('*.log')},utc=c.utc()))
    require(code==0 and not forced,'No dispatch after child failure')

def decoded(label,parent):
    rec,prefix=job.codec.read_record(RUN/label/'call.json.xz',c.sha(job.DESIGN),parent)
    original=c.sealed(RUN/label/'results.json');extra=c.sealed(RUN/label/'guard_completion/results.json')
    require(original['artifacts'][str(RUN/label/'call.json.xz')]==c.sha(RUN/label/'call.json.xz'),'Original sealed transaction body')
    c.verify(extra['artifacts']);require(api.digest(rec['result']['checkpoint'])==extra['final_checkpoint_sha256']==api.digest(c.read(RUN/label/'full_checkpoint.json')),'FULL lossless state')
    require(guard.audit(rec)==extra['guard_audit']==c.read(RUN/label/'guard_audit.json'),'Independent guard reconstruction')
    return rec,prefix

def run():
    p=verify();proc=reference.psutil.Process();proc.cpu_affinity([14]);require(not (OUT/'launch.json').exists(),'No duplicate worker')
    c.commit(OUT/'launch.json',dict(pid=proc.pid,created=proc.create_time(),command=proc.cmdline(),utc=c.utc()))
    used=0;accepted=0;active=None;verified=[]
    try:
        for label in ('serial','split_a','split_b'):
            active=dict(label=label,maximum_steps=CAPS[label]);child(label);used+=CAPS[label];verified.append(label);active=None
        cp,prefix=seed();serial,_=decoded('serial',prefix);a,pa=decoded('split_a',prefix);b,_=decoded('split_b',pa)
        require(serial['rows']==a['rows']+b['rows'] and api.digest(serial['result']['checkpoint'])==api.digest(b['result']['checkpoint']),'Fresh exact rows/FULL restart')
        gate=OUT/'restart_01/results.json'
        c.commit(gate,dict(passed=True,discarded_diagnostic_steps=512,exact_rows=True,exact_full_checkpoint=True,diagnostic_promoted=False,
            actual_guard_calls={q:c.read(RUN/q/'guard_audit.json')['canonical_calls'] for q in ('serial','split_a','split_b')},
            artifacts={str(q):c.sha(q) for q in RUN.rglob('*') if q.is_file()},utc=c.utc()))
        c.commit(gate.with_name('completion.json'),dict(passed=True,results_sha256=c.sha(gate)))
        for i in range(1,5):
            resources();label=f'production_{i:02d}';require(used+CAPS[label]<=20512 and accepted+CAPS[label]<=20000,'Shared saved-step budget')
            active=dict(label=label,maximum_steps=CAPS[label]);child(label)
            rec,prefix=decoded(label,prefix);n=len(rec['rows']);accepted+=n;used+=n;cp=rec['result']['checkpoint'];verified.append(label);active=None
            c.commit(OUT/f'progress_{i:02d}.json',dict(accepted_physical_steps=accepted,discarded_diagnostic_steps=512,cumulative_physical_steps=cp['state']['steps'],
                cumulative_production_calls=157+i,time_s=cp['state']['t'],full_checkpoint_sha256=api.digest(cp),utc=c.utc()))
            if n<CAPS[label] or cp['state']['t']>=4.682166803491474:break
        c.commit(OUT/'results.json',dict(passed=True,exact_restart_passed=True,accepted_physical_steps=accepted,discarded_diagnostic_steps=512,
            saved_steps_including_diagnostics=used,time_s=cp['state']['t'],final_checkpoint_sha256=api.digest(cp),verified_calls=verified,
            original_full_path_accuracy_passed=False,successor_cases_started=0,unknown_saved_steps=0,utc=c.utc()))
        c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    except Exception as issue:
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(issue),traceback=traceback.format_exc(),verified_saved_steps=used,verified_calls=verified,
            unresolved_reservation=active,dependent_dispatch_stopped=True,all_failures_preserved=True,utc=c.utc()));raise

def finalize(code):
    p=verify();cp,prefix=seed();accepted=discarded=known=unknown=calls=0;records=[];identities=[]
    for q in [OUT/'controller_01/worker_launch.json',*sorted((OUT/'children').glob('*/launch.json'))]:
        x=c.read(q);r=controller.inspect(x['pid'],x['created'],x['command']);require(r['retired'],'Exact owned numerical identities retired');identities.append(dict(path=str(q),sha256=c.sha(q),inspection=r))
    for label,cap in CAPS.items():
        folder=RUN/label;launch=OUT/'children'/label/'launch.json'
        if not launch.exists():continue
        if not (folder/'call.json.xz').exists():unknown+=cap;records.append(dict(label=label,status='unknown',reservation_upper_bound=cap));continue
        parent=parent_for(label)[1] if label=='split_b' else prefix
        rec,next_prefix=job.codec.read_record(folder/'call.json.xz',c.sha(job.DESIGN),parent);n=len(rec['rows'])
        exitfile=launch.with_name('exit.json');exitrow=c.read(exitfile) if exitfile.exists() else {}
        good=(folder/'guard_completion/completion.json').exists() and exitrow.get('returncode')==0 and exitrow.get('forced') is False
        if good:
            decoded(label,parent)
            if label.startswith('production_'):accepted+=n;calls+=1;cp=rec['result']['checkpoint'];prefix=next_prefix;status='accepted'
            else:discarded+=n;status='discarded_diagnostic'
        else:known+=n;status='known_unaccepted'
        records.append(dict(label=label,saved_steps=n,status=status))
    require(accepted+discarded+known+unknown<=20512 and accepted<=20000 and calls<=4,'Complete partial/unknown ledger')
    folder=OUT/'final_disposition_01';c.commit(folder/'recoverable/checkpoint.json',cp);c.commit(folder/'recoverable/prefix.json',prefix.reference())
    result=dict(passed=True,accounting_authenticated=True,run_completed=(OUT/'completion.json').exists() and code==0,
        accepted_physical_steps=accepted,discarded_diagnostic_steps=discarded,known_unaccepted_saved_steps=known,unknown_saved_steps_reservation_upper_bound=unknown,
        cumulative_accepted_physical_steps=cp['state']['steps'],cumulative_accepted_production_calls=157+calls,time_s=cp['state']['t'],
        final_checkpoint_sha256=api.digest(cp),full_checkpoint_file_sha256=c.sha(folder/'recoverable/checkpoint.json'),records=records,identities=identities,
        observed_worker_returncode=code,source_count=len(p['source_files']),input_count=len(p['inputs']),source_and_input_hashes_authenticated=True,
        prior_accepted_ancestry_proof_reused=True,prior_ancestry_not_reexecuted=True,original_full_path_accuracy_passed=False,successor_cases_started=0,
        all_failures_preserved=True,supervisor_own_live_logs_unsealed=True,
        artifacts={str(q):c.sha(q) for q in OUT.rglob('*') if q.is_file() and 'final_disposition_01' not in q.parts and q.parent!=OUT/'supervisor_01'},utc=c.utc())
    c.commit(folder/'results.json',result);c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
    print('STAGE244_FINALIZED',accepted,discarded,known,unknown,cp['state']['t'],flush=True)

b=reference.b
frozen_launch=clone(reference.frozen.launch,globals())
def launch():
    try:frozen_launch()
    finally:
        path=OUT/'controller_01/worker_exit.json'
        if path.exists():finalize(c.read(path)['returncode'])

def retirement(code):
    p=verify();closed=c.sealed(OUT/'final_disposition_01/results.json');identities=[]
    for q in [OUT/'controller_01/launch.json',OUT/'controller_01/worker_launch.json',*sorted((OUT/'children').glob('*/launch.json'))]:
        x=c.read(q);r=controller.inspect(x['pid'],x['created'],x['command']);require(r['retired'],'Every exact owned identity retired');identities.append(dict(path=str(q),sha256=c.sha(q),inspection=r))
    c.verify(closed['artifacts']);require(api.digest(c.read(OUT/'final_disposition_01/recoverable/checkpoint.json'))==closed['final_checkpoint_sha256'],'Sealed final FULL history')
    folder=OUT/'retirement_01';logs={str(q):c.sha(q) for f in (OUT/'controller_01',OUT/'supervisor_01') for q in f.glob('*.log')}
    c.commit(folder/'results.json',dict(passed=True,observed_supervisor_returncode=code,identities=identities,closed_logs=logs,
        final_disposition_sha256=c.sha(OUT/'final_disposition_01/results.json'),full_checkpoint_file_sha256=c.sha(OUT/'final_disposition_01/recoverable/checkpoint.json'),
        source_and_input_hashes_reauthenticated=True,no_new_numerical_calls=True,utc=c.utc()))
    c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
    print('STAGE244_RETIRED',c.sha(folder/'results.json'),flush=True)

if __name__=='__main__':
    action=sys.argv[1]
    if action=='call':call(sys.argv[2])
    elif action=='retirement':retirement(int(sys.argv[2]))
    elif action=='controls':print(controls())
    else:{'prepare':prepare,'launch':launch,'run':run}[action]()
