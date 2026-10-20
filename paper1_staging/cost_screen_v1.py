"""Bounded 12-domain cost/restart screen; all trajectories are discarded diagnostics.

No exposure decision, core comparison or full-path accuracy promotion is made
here. Each transaction uses the original integration/storage/auditor code and
qualified per-pose guard. Late-horizon affordability remains uncertain.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta
import os, sys, time, shutil, subprocess, traceback, copy, json
import numpy as np
import psutil
sys.path.insert(0, str(Path(__file__).resolve().parent))
import transport_context_v1 as context
import transport_cases_v1 as factory
fields = factory.fields
api, q = context.api, context.qualified
ROOT = context.ROOT
SELF = Path(__file__).resolve()
BASE = 'initial_cost_screen_20261013'
DESIGNS = ROOT/'paper1_designs'/BASE
PLAN = DESIGNS/'design_01.json'
AUTH = DESIGNS/'authorization_01.json'
PHYSICAL = DESIGNS/'physical_cases_01.json'
OUT = ROOT/'paper1_runs'/BASE
PYTHON = Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
sha, read, require = fields.sha, fields.read, fields.require
commit = q.c.commit
LABELS = dict(serial=256, split_a=128, split_b=128, cost=2048, fine=512)


def utc(): return datetime.now(timezone.utc).isoformat()


def seal(folder, body):
    commit(folder/'results.json', body)
    commit(folder/'completion.json', dict(results_sha256=sha(folder/'results.json'), passed=body['passed']))


def environment():
    require(sys.version_info[:2] == (3,12) and Path(sys.executable).resolve() == PYTHON.resolve(), 'Qualified Python312')
    require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')), 'One CPU thread')


def bound():
    environment(); p = read(PLAN)
    require(time.time() < datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp(), 'Numerical cutoff')
    require(shutil.disk_usage(ROOT).free > 20*1024**3, '20GiB free reserve')
    require(sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file()) < 4*1024**3, '4GiB retained-output ceiling')
    return p


def verify_inputs(p):
    bound(); api.verify_mapping(p['source_files']); api.verify_mapping(p['physical_inputs'])
    require(p['authorization_sha256'] == sha(AUTH) and p['physical_design_sha256'] == sha(PHYSICAL)
            and p['numerical_policy_contract_sha256'] == sha(q.job.WORK), 'Frozen authority/design/original policy')
    require(p['binding'] == api.digest({k:v for k,v in p.items() if k != 'binding'}), 'Frozen screen design')


def prepare():
    environment(); require(not PLAN.exists() and not OUT.exists(), 'Fresh create-only screen')
    contract = factory.contract(); require(fields.sealed(fields.REGISTRY)['passed'], 'Retired direct-field registry required')
    metadata = {}
    for flow in (.5,1.,2.):
        field, data, meta = fields.load(2,flow,6); metadata[flow] = meta
        del field, data
    original = read(contract['physical_design_file'])
    core_cases = []; fine_cases = []
    for row in contract['cases']:
        core_cases.append(factory.case_for(row['id'], metadata[row['nominal_flow_level']], .1))
        fine_cases.append(factory.case_for(row['id'], metadata[row['nominal_flow_level']], .1, .0625))
    physical = dict(schema='paper1.physical-screen-cases.v1', cases=core_cases+fine_cases,
                original_physical_template=dict(path=contract['physical_design_file'],sha256=contract['physical_design_sha256']),
                minimum_gap_semantics=original['minimum_gap_semantics'],
                numerical_policy_contract=dict(path=str(q.job.WORK),sha256=sha(q.job.WORK)),
                experimental_configuration_changes=['qualified direct flow', 'prospective observation exposure', 'explicit paired placement metadata'],
                physical_equation_changes=[],accuracy_gate_changes=[],
                claim='Discarded prefix cost/restart screen in the prospective Paper1 domain; no completed core evidence.',
                binding=None)
    physical['binding'] = api.digest({k:v for k,v in physical.items() if k != 'binding'})
    sources = {str(Path(m.__file__).resolve()): sha(m.__file__) for m in list(sys.modules.values())
               if getattr(m,'__file__',None) and Path(m.__file__).suffix == '.py'
               and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    inputs = {str(factory.CONTRACT):factory.CONTRACT_SHA,
              contract['physical_design_file']:contract['physical_design_sha256'], str(q.job.WORK):sha(q.job.WORK),
              str(fields.REGISTRY):sha(fields.REGISTRY), str(fields.REGISTRY.with_name('completion.json')):sha(fields.REGISTRY.with_name('completion.json'))}
    for meta in metadata.values(): inputs.update(context.fields.dependencies(meta))
    registry = fields.sealed(fields.REGISTRY); direct = read(registry['design_path'])
    sources.update(direct['source_files']); inputs.update(direct['inputs'])
    api.verify_mapping(sources); api.verify_mapping(inputs)
    start = datetime.now(timezone.utc); end = start+timedelta(hours=2)
    a = dict(schema='paper1.cost-screen.v1', human_authorization='Agreed12-case conditional study and bounded cost/accuracy screen; fresh at-most2h local diagnostic window within two-week target.',
        start_utc=start.isoformat(), end_utc=end.isoformat(), simulation_cutoff_utc=(end-timedelta(minutes=15)).isoformat(),
        worker_cutoff_utc=(end-timedelta(minutes=8)).isoformat(), workers=1,threads=1,logical_cpu=14,
        maximum_saved_steps=36864, maximum_unverified_records=1, step_cap_per_call=2048,
        maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,
        minimum_free_disk_bytes=20*1024**3,maximum_output_bytes=4*1024**3,
        no_particle_core_dispatch=True, no_exposure_selection=True, no_full_path_accuracy_promotion=True,
        discard_all_screen_trajectories=True, retain_all_failures=True)
    commit(AUTH,a); commit(PHYSICAL,physical)
    inputs[str(PHYSICAL)] = sha(PHYSICAL)
    p = {**a,'source_files':sources,'physical_inputs':inputs,'authorization_sha256':sha(AUTH),
         'physical_design_sha256':sha(PHYSICAL),'numerical_policy_contract_sha256':sha(q.job.WORK),
         'labels':LABELS,'core_ids':[x['id'] for x in contract['cases']],
         'case_ids':[x['id'] for x in core_cases],'fine_case_ids':[x['id'] for x in fine_cases],
         'claim':'Early-prefix cost/restart and independent physics screen only. No representative full-horizon speed or accuracy inference.'}
    p['binding']=api.digest(p); commit(PLAN,p)
    seal(OUT/'preparation_01',dict(passed=True,design_sha256=sha(PLAN),saved_steps=0,utc=utc()))
    print('PAPER1_COST_SCREEN_PREPARED',sha(PLAN),p['end_utc'],flush=True)


def make_context():
    admin=SimpleNamespace(bound=bound,commit=commit,sha=sha,utc=utc)
    return context.build(PLAN,AUTH,PHYSICAL,admin,verify_inputs)


def call(index,label):
    p=bound();verify_inputs(p);require(label in LABELS and 0<=index<12,'Declared screen transaction')
    psutil.Process().cpu_affinity([14]); ctx=make_context(); d=read(PHYSICAL)
    ident=p['fine_case_ids'][index] if label=='fine' else p['case_ids'][index]
    case=next(x for x in d['cases'] if x['id']==ident)
    root=OUT/'records'/f'case_{index:02d}';folder=root/label
    before=prefix=None; previous=None
    if label=='split_b':
        predecessor=fields.sealed(root/'split_a/guard_completion/results.json')
        require(predecessor['passed'],'Accepted split predecessor')
        api.verify_mapping(predecessor['artifacts'])
        before=read(root/'split_a/full_checkpoint.json');ref=read(root/'split_a/prefix.json')
        prefix=ctx.job.codec.HistoryState(**ref,history_bytes=ctx.job.codec.packed_history(before['state']['history']))
        previous=sha(root/'split_a/results.json')
    if label in ('cost','fine'):require(fields.sealed(root/'restart_01/results.json')['passed'],'Exact fresh restart before cost/fine prefix')
    q.reference.JOB.parent.b.old.parent.configure();q.kernel.warm();q.kernel.reset()
    geometry=ctx.geometry_for(case)
    rec,prefix,receipt=ctx.segment(p,d,case,geometry,before,prefix,folder,LABELS[label],previous,'discarded_screen_diagnostic')
    audit=q.guard.audit(rec)
    require(0<len(rec['rows'])<=LABELS[label] and rec['result']['rejected']==0,'Positive bounded audited diagnostic increment')
    if label in ('serial','split_a','split_b'):
        require(len(rec['rows'])==LABELS[label],'Full declared restart increment')
    commit(folder/'full_checkpoint.json',rec['result']['checkpoint']);commit(folder/'prefix.json',prefix.reference())
    commit(folder/'guard_audit.json',audit)
    seal(folder/'guard_completion',dict(passed=True,saved_steps=len(rec['rows']),guard_audit=audit,
        artifacts={str(x):sha(x) for x in folder.glob('*') if x.is_file()},utc=utc()))
    print('PAPER1_SCREEN_CALL_ACCEPTED',index,label,len(rec['rows']),rec['result']['checkpoint']['state']['t'],flush=True)


def identity(launch):
    try:
        proc=psutil.Process(launch['pid']);birth=proc.create_time()
        if birth!=launch['created']:return dict(retired=True,different_birth=True,observed_birth=birth)
        require(proc.cmdline()==launch['command'],'Matching birth requires exact accessible command')
        return dict(retired=False,different_birth=False)
    except psutil.NoSuchProcess:return dict(retired=True,no_such_process=True)


def stop_owned(proc,launch):
    observed=identity(launch)
    if not observed['retired']:
        proc.terminate();proc.wait(timeout=15)
    require(identity(launch)['retired'],'Exact owned child retirement')


def child(index,label):
    started=time.perf_counter()
    p=bound();verify_inputs(p);folder=OUT/'children'/f'{index:02d}_{label}';folder.mkdir(parents=True,exist_ok=False)
    cmd=[str(PYTHON),'-B','-u',str(SELF),'call',str(index),label]
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        proc=subprocess.Popen(cmd,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        launch=dict(pid=proc.pid,created=psutil.Process(proc.pid).create_time(),command=cmd,
                    reserved_steps=LABELS[label],utc=utc())
        require(not identity(launch)['retired'],'Exact fresh child identity');commit(folder/'launch.json',launch)
        cutoff=min(time.time()+180,datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp())
        while proc.poll() is None:
            if time.time()>=cutoff:stop_owned(proc,launch);break
            time.sleep(.25)
        code=proc.wait(timeout=10)
    require(identity(launch)['retired'],'Closed numerical child')
    commit(folder/'exit.json',dict(returncode=code,identity=identity(launch),utc=utc(),
                                 complete_child_transaction_seconds=time.perf_counter()-started,
                                 logs={str(x):sha(x) for x in folder.glob('*.log')}))
    require(code==0,'Dependent dispatch stops after screen child failure')
    require(fields.sealed(OUT/'records'/f'case_{index:02d}'/label/'guard_completion/results.json')['passed'],'Sealed complete physical admission')


def restart(index):
    root=OUT/'records'/f'case_{index:02d}'
    serial=np.load(root/'serial/trace.npy',allow_pickle=False)
    split=np.concatenate([np.load(root/'split_a/trace.npy',allow_pickle=False),np.load(root/'split_b/trace.npy',allow_pickle=False)])
    a=read(root/'serial/full_checkpoint.json');b=read(root/'split_b/full_checkpoint.json')
    require(np.array_equal(serial,split) and api.digest(a)==api.digest(b),'Exact rows and FULL checkpoint/history restart')
    seal(root/'restart_01',dict(passed=True,exact_rows=True,exact_full_checkpoint_history=True,discarded_steps=512,
         full_checkpoint_sha256=api.digest(a),artifacts={str(x):sha(x) for label in ('serial','split_a','split_b')
         for x in (root/label).rglob('*') if x.is_file()},utc=utc()))


def finalize(error=None):
    p=read(PLAN);accepted=known=unknown=0; receipts=[];cases=[]
    for i in range(12):
        for label,cap in LABELS.items():
            folder=OUT/'records'/f'case_{i:02d}'/label;gate=folder/'guard_completion/results.json'
            launch=OUT/'children'/f'{i:02d}_{label}/launch.json'
            if gate.exists():
                row=fields.sealed(gate);api.verify_mapping(row['artifacts']);require(row['passed'],'Accepted record seal')
                accepted+=row['saved_steps'];receipts.append(dict(path=str(gate),sha256=sha(gate)))
            elif launch.exists():
                accounting=folder/'accounting.json'
                if accounting.exists():known+=read(accounting)['saved_steps']
                else:unknown+=cap
        root=OUT/'records'/f'case_{i:02d}'
        if (root/'cost/results.json').exists():
            r=fields.sealed(root/'cost/results.json'); cp=read(root/'cost/full_checkpoint.json')
            closed=read(OUT/'children'/f'{i:02d}_cost/exit.json')
            cases.append(dict(core_id=p['core_ids'][i],transaction_seconds=r['transaction_seconds'],
                complete_child_transaction_seconds=closed['complete_child_transaction_seconds'],
                advanced_physical_seconds=cp['state']['t'],saved_steps=r['new_saved_steps'],
                retained_record_bytes=sum(x.stat().st_size for x in root.rglob('*') if x.is_file())))
    require(accepted+known+unknown<=p['maximum_saved_steps'],'Complete shared reservation ledger')
    api.verify_mapping(p['source_files']);api.verify_mapping(p['physical_inputs'])
    passed=error is None and len(receipts)==60 and len(cases)==12 and known==unknown==0
    seal(OUT/'final_disposition_01',dict(passed=passed,error=error,accepted_discarded_diagnostic_steps=accepted,
        known_unaccepted_saved_steps=known,unknown_reserved_steps_upper_bound=unknown,core_transport_steps=0,
        completed_domain_prefixes=cases,receipts=receipts,design_sha256=sha(PLAN),
        exposure_selected=False,full_path_accuracy_passed=False,representative_campaign_speed_claim=False,
        claim=p['claim'],utc=utc()))


def run():
    p=bound();verify_inputs(p);require(not (OUT/'worker_launch.json').exists(),'No duplicate worker')
    proc=psutil.Process();commit(OUT/'worker_launch.json',dict(pid=proc.pid,created=proc.create_time(),command=proc.cmdline(),utc=utc()))
    error=None
    try:
        for index in range(12):
            for label in ('serial','split_a','split_b'):child(index,label)
            restart(index)
            for label in ('cost','fine'):child(index,label)
    except Exception as exc:
        error=dict(message=repr(exc),traceback=traceback.format_exc());raise
    finally:finalize(error)


def supervise():
    p=bound();verify_inputs(p);folder=OUT/'controller_01';folder.mkdir(parents=True,exist_ok=False)
    me=psutil.Process();commit(folder/'launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=utc()))
    cmd=[str(PYTHON),'-B','-u',str(SELF),'run']
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        proc=subprocess.Popen(cmd,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        launch=dict(pid=proc.pid,created=psutil.Process(proc.pid).create_time(),command=cmd,utc=utc())
        require(not identity(launch)['retired'],'Exact worker identity');commit(folder/'worker_launch.json',launch)
        cutoff=datetime.fromisoformat(p['worker_cutoff_utc']).timestamp()
        while proc.poll() is None:
            if time.time()>=cutoff:
                # Child commands are separately registered; stop them first.
                for item in (OUT/'children').glob('*/launch.json'):
                    child_launch=read(item)
                    if not identity(child_launch)['retired']:
                        stop_owned(psutil.Process(child_launch['pid']),child_launch)
                stop_owned(proc,launch);break
            time.sleep(.25)
        code=proc.wait(timeout=10)
    require(identity(launch)['retired'],'Exact screen worker retired')
    commit(folder/'exit.json',dict(returncode=code,identity=identity(launch),utc=utc(),
                                  logs={str(x):sha(x) for x in folder.glob('*.log')}))
    require(code==0,'Screen negative preserved; no core dispatch')


if __name__=='__main__':
    action=sys.argv[1]
    if action=='call':call(int(sys.argv[2]),sys.argv[3])
    else:{'prepare':prepare,'run':run,'supervise':supervise}[action]()
