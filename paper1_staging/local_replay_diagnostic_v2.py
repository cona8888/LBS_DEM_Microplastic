"""Prepared common-state diagnostic; numerical dispatch requires separate human approval.

The original transaction, producer, independent physical auditor and supervisor
are reused. Local observations cannot confer Paper1 full-path admission.
"""
from pathlib import Path
from types import FunctionType
from datetime import datetime,timezone,timedelta
import copy
import os
import sys
import time
import shutil
import traceback
import numpy as np
import psutil

sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_core_v2 as original
s=original.s;ROOT=s.ROOT;SELF=Path(__file__).resolve();PYTHON=s.PYTHON
DESIGNS=ROOT/'paper1_designs/local_common_state_20261015'
OUT=ROOT/'paper1_runs/local_common_state_20261015'
PLAN=DESIGNS/'design_01.json';AUTH=DESIGNS/'authorization_01.json'
PHYSICAL=DESIGNS/'physical_cases_01.json';PROPOSAL=DESIGNS/'proposal_02.json'
SEED_ROOT=ROOT/'paper1_evaluations/fibre_accuracy_diagnosis_20261015/local_replay_preparation_01'
sha,read,require,commit,seal=original.sha,original.read,original.require,original.commit,original.seal
DOC=original.DOC


def clone(fn,namespace):
    return FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)


def bound():
    s.environment();p=read(PLAN)
    require(time.time()<datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp(),'Numerical diagnostic cutoff')
    require(shutil.disk_usage(ROOT).free>20*1024**3,'Original free disk reserve')
    require(sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file())<1024**3,'1GiB local output ceiling')
    require(sum(x.stat().st_size for dirname in ('paper1_runs','paper1_designs','paper1_evaluations')
        for x in (ROOT/dirname).rglob('*') if x.is_file())<20*1024**3,'Approved total retention ceiling')
    return p


namespace={**vars(original),**globals()}
verify_inputs=clone(original.verify_inputs,namespace)
make_context=clone(original.make_context,namespace)
transaction=clone(original.transaction,namespace)


def seed_for(index):
    cp=DOC.read(DESIGNS/f'seed_{index}.json')
    # Cross-design history references are intentionally forbidden by the
    # original codec. The first local record stores the complete identical
    # seed history literally; subsequent records use its new-design prefix.
    return cp,None


def prepare():
    s.environment();require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'No numerical dispatch before separate approval')
    previous=read(DESIGNS/'proposal_01.json');s.api.verify_mapping(previous['source_files']);s.api.verify_mapping(previous['physical_inputs'])
    seed=DOC.read(SEED_ROOT/'checkpoint.json');codec=original.archives.build(s.q.job.codec,preset=9)
    ref=read(SEED_ROOT/'prefix.json');oldprefix=codec.HistoryState(**ref,history_bytes=codec.packed_history(seed['state']['history']))
    checks=dict(previous['checks'])
    try:codec.validate_prefix(oldprefix,sha(PHYSICAL))
    except ValueError:checks['cross_design_prefix_refused_by_original_codec']=True
    else:raise RuntimeError('An old-design prefix was accepted under a new design')
    for i in (0,1):
        cp,prefix=seed_for(i);require(prefix is None and cp['state']==seed['state'],'Identical state and full seed history; no cross-design prefix')
        record={'design_sha256':sha(PHYSICAL),'rows':[],'result':{'checkpoint':cp,'history':cp['state']['history']}}
        encoded,history=codec.encode(record,None);decoded,restored=codec.decode(encoded,None)
        require(s.api.digest(record)==s.api.digest(decoded) and history==restored,'Exact zero-step literal seed-history wire roundtrip')
    checks['both_seed_histories_lossless_without_cross_design_reference']=True
    require(transaction.__code__ is original.transaction.__code__,'Original numerical transaction unchanged')
    checks['no_authorization_and_no_numerical_output']=not PLAN.exists() and not AUTH.exists() and not OUT.exists()
    require(all(checks.values()),'All zero-advancement local preparation checks')
    seal(DESIGNS/'unlaunched_v1_diagnosis_01',dict(passed=False,source_files={str(SELF.with_name('local_replay_diagnostic_v1.py')):sha(SELF.with_name('local_replay_diagnostic_v1.py'))},
        new_transport_steps=0,zero_dispatch=True,original_inputs_preserved=True,
        reason='Original codec correctly refuses the v1 cross-design history-prefix object. Discovered by zero-step review before authorization or numerical dispatch.',utc=s.utc()))
    sources={**previous['source_files'],str(SELF):sha(SELF)}
    inputs={**previous['physical_inputs']}
    for path in (DESIGNS/'proposal_01.json',DESIGNS/'preparation_01/results.json',DESIGNS/'unlaunched_v1_diagnosis_01/results.json'):
        inputs[str(path)]=sha(path)
    body={**previous,'checks':checks,'source_files':sources,'physical_inputs':inputs,
          'history_storage':'First local record preserves the entire unchanged seed history literally; original codec and all later prefix rules unchanged.',
          'utc':s.utc()}
    seal(DESIGNS/'preparation_02',body);commit(PROPOSAL,body)
    print('LOCAL_DIAGNOSTIC_PREPARED_NO_DISPATCH',sha(PROPOSAL),len(checks),flush=True)


def authorize():
    require(not PLAN.exists() and not OUT.exists(),'Fresh separately authorized diagnostic window')
    proposal=read(PROPOSAL);human=s.fields.sealed(DESIGNS/'human_approval_01/results.json')
    require(human['passed'] and human['proposal_sha256']==sha(PROPOSAL) and human['local_replay_authorized'] is True,
            'Separate explicit authorization after full-path failure')
    start=datetime.now(timezone.utc);end=start+timedelta(hours=6)
    auth=dict(start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(minutes=90)).isoformat(),
        worker_cutoff_utc=(end-timedelta(minutes=45)).isoformat(),step_cap_per_call=5000,maximum_saved_steps=300000,
        maximum_cumulative_physical_steps_per_case=6000000,maximum_cumulative_calls_per_case=1500,
        workers=1,threads=1,logical_cpu=14,maximum_unverified_records=1,minimum_free_disk_bytes=20*1024**3,
        maximum_output_bytes=1024**3,accuracy_promotion_authorized=False,successor_cases_authorized=False)
    commit(AUTH,auth)
    inputs={**proposal['physical_inputs'],str(PROPOSAL):sha(PROPOSAL),
            str(DESIGNS/'human_approval_01/results.json'):sha(DESIGNS/'human_approval_01/results.json')}
    p={**auth,'authorization_sha256':sha(AUTH),'physical_design_sha256':sha(PHYSICAL),
       'physical_inputs':inputs,'source_files':proposal['source_files'],'logical_core_id':'p1_i0_rigid_prolate_ar4_u0p5',
       'diagnostic_only':True,'proposal_sha256':sha(PROPOSAL)}
    p['binding']=s.api.digest(p);commit(PLAN,p)


def run():
    p=bound();verify_inputs(p);psutil.Process().cpu_affinity([14]);d=read(PHYSICAL);ctx=make_context()
    me=psutil.Process();commit(OUT/'worker_launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=s.utc()))
    used=0;admitted=[];branches=[];latest={};error=None
    def invoke(case,index,label,cap,before,prefix,previous):
        nonlocal used
        require(used+cap<=300000,'All local restart/continuation steps share the same ceiling')
        commit(OUT/'reservations'/f'{label}.json',dict(label=label,maximum_saved_steps=cap))
        rec,nxt,row=transaction(ctx,p,d,case,label,cap,before,prefix,previous)
        used+=len(rec['rows']);admitted.append(label)
        if '_local_' in label:latest[index]=(rec['result']['checkpoint'],nxt)
        return rec,nxt,row
    try:
        s.q.reference.JOB.parent.b.old.parent.configure();s.q.kernel.warm();s.q.kernel.reset()
        for i,case in enumerate(d['cases']):
            initial,prefix=seed_for(i);geometry=ctx.geometry_for(case)
            # The original transaction resolves exactly the same geometry;
            # keep this explicit construction as a source/field preflight.
            del geometry
            serial,_,_=invoke(case,i,f'branch{i}_serial',256,copy.deepcopy(initial),prefix,None)
            a,pa,_=invoke(case,i,f'branch{i}_split_a',128,copy.deepcopy(initial),prefix,None)
            b,_,_=invoke(case,i,f'branch{i}_split_b',128,a['result']['checkpoint'],pa,sha(OUT/'records'/f'branch{i}_split_a'/'results.json'))
            require(s.api.digest(serial['rows'])==s.api.digest(a['rows']+b['rows'])
                and s.api.digest(serial['result']['checkpoint'])==s.api.digest(b['result']['checkpoint'])
                and len(serial['rows'])==256 and len(a['rows'])==len(b['rows'])==128,'Fresh exact late-seed restart')
            seal(OUT/f'restart_{i}',dict(passed=True,new_discarded_steps=512,exact_full_checkpoint_history=True))
            before=copy.deepcopy(initial);current=prefix;previous=None;labels=[];count=0
            limit=(100000,198976)[i]
            for call in range(1,(25,45)[i]+1):
                if before['state']['t']>=case['spec']['horizon_s']:break
                require(count<limit,'Local branch saved-step cap')
                label=f'branch{i}_local_{call:05d}'
                rec,current,_=invoke(case,i,label,min(5000,limit-count),before,current,previous)
                count+=len(rec['rows']);before=rec['result']['checkpoint'];labels.append(label)
                previous=sha(OUT/'records'/label/'results.json')
                if rec['result']['status'] in ('present_at_horizon','full_window_exit'):break
            require(before['state']['t']==case['spec']['horizon_s'],'Complete declared local interval; no extrapolation')
            (OUT/f'recoverable_{i}').mkdir(exist_ok=False);DOC.store(OUT/f'recoverable_{i}/checkpoint.json',before,sha(PHYSICAL))
            commit(OUT/f'recoverable_{i}/prefix.json',current.reference())
            branches.append(dict(case_id=case['id'],new_steps=count,labels=labels,checkpoint_sha256=s.api.digest(before)))
    except Exception as exc:
        error=dict(message=repr(exc),traceback=traceback.format_exc());raise
    finally:
        for i,(checkpoint,prefix) in latest.items():
            folder=OUT/f'recoverable_{i}'
            if not folder.exists():
                folder.mkdir(exist_ok=False);DOC.store(folder/'checkpoint.json',checkpoint,sha(PHYSICAL));commit(folder/'prefix.json',prefix.reference())
        known=unknown=0
        for path in (OUT/'reservations').glob('*.json'):
            reservation=read(path);label=reservation['label']
            if label not in admitted:
                accounting=OUT/'records'/label/'accounting.json'
                if accounting.exists():known+=read(accounting)['saved_steps']
                else:unknown+=reservation['maximum_saved_steps']
        require(used+known+unknown<=300000,'Complete conservative local saved-step accounting')
        seal(OUT/'final_disposition_01',dict(passed=error is None and known==unknown==0,error=error,
            diagnostic_only=True,accepted_physical_steps=0,discarded_diagnostic_steps=used,
            known_unaccepted_saved_steps=known,unknown_reserved_steps_upper_bound=unknown,
            production_labels=admitted,conservative_call_charges=len(admitted),branches=branches,
            native_complete=len(branches)==2,original_paper1_horizon_complete=False,full_path_accuracy_passed=False,
            core_result_admitted=False,design_sha256=sha(PLAN),utc=s.utc()))


namespace.update(globals())
supervise=clone(original.supervise,{**original.supervise.__globals__,**namespace})
if __name__=='__main__':
    {'prepare':prepare,'authorize':authorize,'run':run,'supervise':supervise}[sys.argv[1]]()
