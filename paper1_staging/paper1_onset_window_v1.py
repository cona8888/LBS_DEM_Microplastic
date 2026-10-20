"""Prepared three-level common-state onset diagnostic; no production promotion.

Only scheduling and checkpoint contracts differ from the original transport
transaction. Preparation advances zero steps; dispatch needs sealed approval.
"""
from pathlib import Path
from types import FunctionType
from datetime import datetime, timezone, timedelta
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
DESIGNS=ROOT/'paper1_designs/onset_common_state_20261015'
OUT=ROOT/'paper1_runs/onset_common_state_20261015'
PLAN=DESIGNS/'design_01.json';AUTH=DESIGNS/'authorization_01.json'
PHYSICAL=DESIGNS/'physical_cases_01.json';PROPOSAL=DESIGNS/'proposal_01.json'
DOC=original.DOC
sha,read,require,commit,seal=original.sha,original.read,original.require,original.commit,original.seal


def clone(fn,namespace):
    return FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)


def bound():
    s.environment();p=read(PLAN)
    require(time.time()<datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp(),'Onset numerical cutoff')
    require(shutil.disk_usage(ROOT).free>20*1024**3,'Original free disk reserve')
    require(sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file())<512*1024**2,'Onset output ceiling')
    require(sum(x.stat().st_size for name in ('paper1_runs','paper1_designs','paper1_evaluations')
                for x in (ROOT/name).rglob('*') if x.is_file())<20*1024**3,'Approved total retention ceiling')
    return p


namespace={**vars(original),**globals()}
verify_inputs=clone(original.verify_inputs,namespace)
make_context=clone(original.make_context,namespace)
transaction=clone(original.transaction,namespace)


def seed_for(index):
    return DOC.read(DESIGNS/f'seed_{index}.json'),None


def prepare():
    s.environment();require(not PROPOSAL.exists() and not PLAN.exists() and not OUT.exists(),'Create-only unlaunched onset package')
    root=ROOT/'paper1_runs/p1_i0_fibre_u0p5_fine_20261014'
    directory=ROOT/'paper1_designs'/root.name
    retired=s.fields.sealed(root/'retirement_01/results.json');require(retired['passed'],'Authenticated seed path retirement')
    prior=read(directory/'design_01.json');s.api.verify_mapping(prior['source_files']);s.api.verify_mapping(prior['physical_inputs'])
    inputs={**prior['physical_inputs'],str(root/'retirement_01/results.json'):sha(root/'retirement_01/results.json')}
    codec=original.archives.build(s.q.job.codec,preset=9);prefix=before=None
    for i in range(1,74):
        folder=root/'records'/f'production_{i:05d}';raw=folder/'call.json.xz'
        require(retired['artifacts'][str(raw)]==sha(raw),'Original retired raw identity')
        guard=s.fields.sealed(folder/'guard_completion/results.json');s.api.verify_mapping(guard['artifacts'])
        rec,prefix=codec.read_record(raw,sha(directory/'physical_cases_01.json'),prefix)
        require(guard['passed'] and rec['input_checkpoint_sha256']==s.api.digest(before),'Complete original seed raw ancestry')
        before=rec['result']['checkpoint'];require(guard['full_checkpoint_sha256']==s.api.digest(before),'Original FULL seed identity')
        inputs.update(guard['artifacts']);inputs[str(folder/'guard_completion/results.json')]=sha(folder/'guard_completion/results.json')
    require(before['state']['steps']==365000 and before['state']['pending_trial'] is None,'Exact pre-onset seed; no pending trial')
    start=before['state']['t'];stop=start+.01
    require(start<.22881248530444598<.2337866697675861<stop,'Fixed interval brackets previously localized episode')
    (DESIGNS/'seed_source').mkdir(parents=True,exist_ok=False)
    DOC.store(DESIGNS/'seed_source/checkpoint.json',before,sha(directory/'physical_cases_01.json'))
    commit(DESIGNS/'seed_source/prefix.json',prefix.reference())
    cases=[];physics=[]
    for factor in (.125,.0625,.03125):
        case,_,_=s.factory.load_case('p1_i0_rigid_prolate_ar4_u0p5',.01,factor,'core')
        case['id']+='__onset_diagnostic';case['role']='discarded_common_state_onset_diagnostic'
        case['spec']['case_id']=case['id'];case['spec']['horizon_s']=stop
        normalized=copy.deepcopy(case['spec']);normalized.pop('case_id');normalized.pop('refinement')
        for k in s.factory.SCALED_CONTROLS:normalized['config']['numerics'].pop(k)
        physics.append(normalized);cases.append(case)
    require(physics[0]==physics[1]==physics[2],'Identical physical models and local endpoint')
    for left,right in zip(cases,cases[1:]):
        require(right['spec']['refinement']==left['spec']['refinement']/2,'Exact original refinement halving')
        require(all(right['spec']['config']['numerics'][k]==left['spec']['config']['numerics'][k]/2
                    for k in s.factory.SCALED_CONTROLS),'Only the four original controls halve')
    physical=dict(cases=cases,diagnostic_only=True,seed_time_s=start,local_stop_s=stop,
        original_paper1_horizon_s=.9364396280429768,minimum_gap_semantics=read(directory/'physical_cases_01.json')['minimum_gap_semantics'],
        physical_equation_changes=[],accuracy_gate_changes=[])
    physical['binding']=s.api.digest(physical);commit(PHYSICAL,physical)
    for i,case in enumerate(cases):
        seed=s.q.job.parent.model.checkpoint(case['spec'],s.q.job.binding(physical,case),before,True)
        require(seed['state']==before['state'] and seed['state_sha256']==before['state_sha256'],'Identical FULL physical state/history')
        DOC.store(DESIGNS/f'seed_{i}.json',seed,sha(PHYSICAL))
        record={'design_sha256':sha(PHYSICAL),'rows':[],'result':{'checkpoint':seed,'history':seed['state']['history']}}
        encoded,h=codec.encode(record,None);decoded,hh=codec.decode(encoded,None)
        require(s.api.digest(record)==s.api.digest(decoded) and h==hh,'Lossless literal initial history; no cross-design prefix')
    for path in DESIGNS.rglob('*'):
        if path.is_file():inputs[str(path)]=sha(path)
    actual=ROOT/'paper1_runs/local_common_state_20261015/evaluation_01/results.json'
    require(s.fields.sealed(actual)['passed'],'Prior common-state diagnostic closed');inputs[str(actual)]=sha(actual)
    probe=ROOT/'paper1_evaluations/fibre_accuracy_diagnosis_20261015/two_contact_systems_01/retirement_01/results.json'
    require(s.fields.sealed(probe)['passed'],'Identical two-contact probes retired');inputs[str(probe)]=sha(probe)
    sources={**prior['source_files'],str(SELF):sha(SELF)}
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).suffix=='.py' and ROOT in Path(file).resolve().parents and Path(file).is_file():
            sources[str(Path(file).resolve())]=sha(file)
    s.api.verify_mapping(sources);s.api.verify_mapping(inputs)
    require(transaction.__code__ is original.transaction.__code__,'Original per-record transaction bytecode')
    commit(PROPOSAL,dict(passed=True,status='REQUIRES_SEPARATE_HUMAN_APPROVAL',dispatch_authorized=False,
        question='Does the first two-contact episode itself lose local timestep convergence when all three refinements start from the same FULL state?',
        factors=[.125,.0625,.03125],seed_time_s=start,local_stop_s=stop,local_duration_s=.01,
        branch_nonrestart_step_caps=[10000,20000,40000],branch_nonrestart_call_caps=[3,5,9],
        maximum_new_saved_steps=71536,fresh_restart_steps=1536,maximum_conservative_new_call_charges=26,
        prior_case_saved_steps=5515086,prior_conservative_calls=1114,maximum_case_saved_steps_after=5586622,
        maximum_conservative_calls_after=1140,maximum_window_minutes=90,maximum_output_bytes=512*1024**2,
        workers=1,threads=1,logical_cpu=14,step_cap_per_call=5000,native_call_seconds=45,
        minimum_free_disk_bytes=20*1024**3,maximum_total_retention_bytes=20*1024**3,
        source_files=sources,physical_inputs=inputs,physics_changes=[],accuracy_gate_changes=[],
        original_full_path_admission=False,successor_dispatch_authorized=False,
        limitations='No local result admits the0–0.01PV full path or establishes a rigorous error bound. Seed prefix is physically audited but not temporally admitted.',utc=s.utc()))
    print('ONSET_PREPARED_NO_DISPATCH',sha(PROPOSAL),start,stop,flush=True)


def authorize():
    require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Fresh separately authorized onset window')
    proposal=read(PROPOSAL);human=s.fields.sealed(DESIGNS/'human_approval_01/results.json')
    require(human['passed'] and human['proposal_sha256']==sha(PROPOSAL) and human['onset_replay_authorized'] is True,'Explicit onset experiment approval')
    s.api.verify_mapping(proposal['source_files']);s.api.verify_mapping(proposal['physical_inputs'])
    start=datetime.now(timezone.utc);end=start+timedelta(minutes=90)
    auth=dict(start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(minutes=30)).isoformat(),
        worker_cutoff_utc=(end-timedelta(minutes=15)).isoformat(),step_cap_per_call=5000,maximum_saved_steps=71536,
        maximum_cumulative_physical_steps_per_case=6000000,maximum_cumulative_calls_per_case=1500,
        maximum_unverified_records=1,workers=1,threads=1,logical_cpu=14,minimum_free_disk_bytes=20*1024**3,
        maximum_output_bytes=512*1024**2,accuracy_promotion_authorized=False,successor_cases_authorized=False)
    commit(AUTH,auth)
    inputs={**proposal['physical_inputs'],str(PROPOSAL):sha(PROPOSAL),str(DESIGNS/'human_approval_01/results.json'):sha(DESIGNS/'human_approval_01/results.json')}
    p={**auth,'authorization_sha256':sha(AUTH),'physical_design_sha256':sha(PHYSICAL),'physical_inputs':inputs,
        'source_files':proposal['source_files'],'logical_core_id':'p1_i0_rigid_prolate_ar4_u0p5',
        'diagnostic_only':True,'proposal_sha256':sha(PROPOSAL)}
    p['binding']=s.api.digest(p);commit(PLAN,p)


def run():
    p=bound();verify_inputs(p);psutil.Process().cpu_affinity([14]);d=read(PHYSICAL);proposal=read(PROPOSAL);ctx=make_context()
    me=psutil.Process();commit(OUT/'worker_launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=s.utc()))
    used=0;admitted=[];branches=[];latest={};error=None
    def invoke(case,index,label,cap,before,prefix,previous):
        nonlocal used
        require(used+cap<=71536,'All new saved work, including restart diagnostics, shares the onset cap')
        commit(OUT/'reservations'/f'{label}.json',dict(label=label,maximum_saved_steps=cap))
        rec,nxt,row=transaction(ctx,p,d,case,label,cap,before,prefix,previous)
        used+=len(rec['rows']);admitted.append(label)
        if '_local_' in label:latest[index]=(rec['result']['checkpoint'],nxt)
        return rec,nxt,row
    try:
        s.q.reference.JOB.parent.b.old.parent.configure();s.q.kernel.warm();s.q.kernel.reset()
        for i,case in enumerate(d['cases']):
            initial,prefix=seed_for(i)
            serial,_,_=invoke(case,i,f'branch{i}_serial',256,copy.deepcopy(initial),prefix,None)
            a,pa,_=invoke(case,i,f'branch{i}_split_a',128,copy.deepcopy(initial),prefix,None)
            b,_,_=invoke(case,i,f'branch{i}_split_b',128,a['result']['checkpoint'],pa,sha(OUT/'records'/f'branch{i}_split_a'/'results.json'))
            require(s.api.digest(serial['rows'])==s.api.digest(a['rows']+b['rows'])
                and s.api.digest(serial['result']['checkpoint'])==s.api.digest(b['result']['checkpoint'])
                and len(serial['rows'])==256 and len(a['rows'])==len(b['rows'])==128,'Exact rows and FULL checkpoint/history restart')
            seal(OUT/f'restart_{i}',dict(passed=True,new_discarded_steps=512,exact_full_checkpoint_history=True))
            before=copy.deepcopy(initial);current=prefix;previous=None;labels=[];count=0
            limit=proposal['branch_nonrestart_step_caps'][i]
            for call in range(1,proposal['branch_nonrestart_call_caps'][i]+1):
                if before['state']['t']>=case['spec']['horizon_s']:break
                require(count<limit,'Frozen branch saved-step cap')
                label=f'branch{i}_local_{call:05d}'
                rec,current,_=invoke(case,i,label,min(5000,limit-count),before,current,previous)
                count+=len(rec['rows']);before=rec['result']['checkpoint'];labels.append(label)
                previous=sha(OUT/'records'/label/'results.json')
                if rec['result']['status'] in ('present_at_horizon','full_window_exit'):break
            require(before['state']['t']==case['spec']['horizon_s'],'Entire declared local onset interval; no extrapolation')
            (OUT/f'recoverable_{i}').mkdir(exist_ok=False);DOC.store(OUT/f'recoverable_{i}/checkpoint.json',before,sha(PHYSICAL))
            commit(OUT/f'recoverable_{i}/prefix.json',current.reference())
            branches.append(dict(case_id=case['id'],factor=case['factor'],new_steps=count,labels=labels,checkpoint_sha256=s.api.digest(before)))
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
        require(used+known+unknown<=71536,'Complete conservative saved-step ledger')
        seal(OUT/'final_disposition_01',dict(passed=error is None and known==unknown==0,error=error,diagnostic_only=True,
            accepted_physical_steps=0,discarded_diagnostic_steps=used,known_unaccepted_saved_steps=known,
            unknown_reserved_steps_upper_bound=unknown,production_labels=admitted,conservative_call_charges=len(admitted),branches=branches,
            native_complete=len(branches)==3,original_paper1_horizon_complete=False,full_path_accuracy_passed=False,
            core_result_admitted=False,design_sha256=sha(PLAN),utc=s.utc()))


namespace.update(globals())
supervise=clone(original.supervise,{**original.supervise.__globals__,**namespace})
if __name__=='__main__':{'prepare':prepare,'authorize':authorize,'run':run,'supervise':supervise}[sys.argv[1]]()
