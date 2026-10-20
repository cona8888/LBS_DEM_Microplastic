"""One bounded scheduler for the approved three fresh timestep-repair paths.

Mechanics, raw/history encoding, independent physical transactions, selector
and accuracy gates are reused unchanged. This module owns only resources,
restart experiments, numerical windows and their immutable evidence ledger.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import FunctionType
import copy, json, os, shutil, subprocess, sys, time, traceback
import psutil
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_core_v2 as original
import onset_timecap_experiment_v1 as local
import contact_onset_timecap_v1 as selector
import evaluate_timecap_full_v1 as evaluator
import compare_core_v2 as comparator

s=original.s; ROOT=s.ROOT; SELF=Path(__file__).resolve(); PYTHON=s.PYTHON
DESIGNS=ROOT/'paper1_designs/full_horizon_timecap_20261016'
OUT=ROOT/'paper1_runs/full_horizon_timecap_20261016'
PROPOSAL=DESIGNS/'proposal_01.json'; PLAN=DESIGNS/'design_01.json'
AUTH=DESIGNS/'authorization_01.json'; PHYSICAL=DESIGNS/'physical_cases_01.json'
APPROVED='e293e344fedccfd5f47c8eca72fee3040b1caae9d71d4d708f7222cc09253f58'
sha,read,require,commit,seal=original.sha,original.read,original.require,original.commit,original.seal
DOC=original.DOC; CONFIG=dict(enabled=True,policy=copy.deepcopy(selector.POLICY))
IDS={.125:'f0p125',.0625:'f0p0625',.03125:'f0p03125'}
ORDER=['f0p0625','f0p03125','f0p125']
OLD={.125:'p1_i0_fibre_u0p5_20261014',.0625:'p1_i0_fibre_u0p5_fine_20261014',
     .03125:'p1_i0_fibre_u0p5_accuracy_recovery_20261014'}


def instant(value): return datetime.fromisoformat(value).timestamp()
def clone(fn,namespace):
    result=FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)
    result.__kwdefaults__=copy.copy(fn.__kwdefaults__);return result
def replace(path,value):
    """Mutable display only; never used as an acceptance or resource ledger."""
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.writing')
    tmp.write_text(json.dumps(value,sort_keys=True,allow_nan=False),encoding='utf-8');os.replace(tmp,path)
def sizes():
    own=sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file()) if OUT.exists() else 0
    total=sum(x.stat().st_size for name in ('paper1_runs','paper1_designs','paper1_evaluations')
              for x in (ROOT/name).rglob('*') if x.is_file())
    return own,total,shutil.disk_usage(ROOT).free
def shared_bound():
    s.environment();p=read(PLAN);require(time.time()<instant(p['end_utc']),'Shared36h absolute deadline')
    own,total,free=sizes();require(own<p['maximum_new_output_bytes'] and total<p['unchanged_total_retention_bytes']
        and free>p['unchanged_free_reserve_bytes'],'Unchanged output, retention and free-disk ceilings')
    return p
def verify(p):
    shared_bound();require(p['binding']==s.api.digest({k:v for k,v in p.items() if k!='binding'})
        and p['authorization_sha256']==sha(AUTH) and p['physical_design_sha256']==sha(PHYSICAL)
        and p['proposal_sha256']==sha(PROPOSAL)==APPROVED,'Immutable shared authority/design/proposal')
    s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['physical_inputs'])
def definitions():return {IDS[x['factor']]:x for x in read(PROPOSAL)['levels']}


def ledger():
    """Rebuild exact work totals from create-only reservations and admissions."""
    counts=dict(saved_steps=0,calls=0,diagnostic_steps=0,diagnostic_calls=0,accepted_saved_steps=0,
        accepted_new_physical_steps=0,accepted_discarded_diagnostic_steps=0,known_unaccepted_saved_steps=0,
        unknown_reserved_steps_upper_bound=0,unresolved=[],levels={k:dict(steps=0,calls=0,production_labels=[],diagnostic_labels=[]) for k in ORDER})
    reservations=sorted((OUT/'reservations').glob('*.json'))
    for index,path in enumerate(reservations,1):
        r=read(path);require(r['global_index']==index and path.name==f'{index:06d}.json','Contiguous reservation order')
        level=OUT/'levels'/r['level_id'];require(sha(path)==sha(level/'reservations'/f'{r["label"]}.json'),'Exact double ledger association')
        folder=OUT/'admissions'/f'{index:06d}'
        counts['calls']+=1;row=counts['levels'][r['level_id']];production=r['kind']=='production'
        if production:row['calls']+=1
        else:counts['diagnostic_calls']+=1
        if not (folder/'completion.json').exists():
            counts['unresolved'].append(r);account=level/'records'/r['label']/'accounting.json'
            if account.exists() and read(account).get('saved_steps_known'):
                n=read(account)['saved_steps'];require(type(n) is int and 0<=n<=r['maximum_saved_steps'],'Bounded known failed work')
                counts['known_unaccepted_saved_steps']+=n
            else:n=r['maximum_saved_steps'];counts['unknown_reserved_steps_upper_bound']+=n
        else:
            require(not counts['unresolved'],'No successor after any unverified reservation')
            a=s.fields.sealed(folder/'results.json');require(a['passed'] and a['reservation_sha256']==sha(path)
                and all(a[k]==r[k] for k in ('global_index','level_id','label','kind')),'Immutable complete admission')
            n=a['saved_steps'];require(type(n) is int and 0<n<=r['maximum_saved_steps']==a['cap'],'Bounded admitted work')
            counts['accepted_saved_steps']+=n
            counts['accepted_new_physical_steps' if production else 'accepted_discarded_diagnostic_steps']+=n
            row['production_labels' if production else 'diagnostic_labels'].append(r['label'])
        counts['saved_steps']+=n
        if production:row['steps']+=n
        else:counts['diagnostic_steps']+=n
    require(len(counts['unresolved'])<=1,'One unverified record')
    return counts
def budget(counts,level_id,kind,cap):
    p=read(PROPOSAL);r=p['request'];old=p['ledger'];production=kind=='production';level=definitions()[level_id]
    require(type(cap) is int and 0<cap<=5000,'Unchanged per-record step cap')
    require(counts['saved_steps']+cap<=r['maximum_new_saved_steps']
        and counts['calls']+1<=r['maximum_new_integration_calls']
        and old['conservative_prospective_baseline_saved_steps']+counts['saved_steps']+cap<=r['saved_step_ceiling_after']
        and old['conservative_prospective_baseline_integration_calls']+counts['calls']+1<=r['integration_call_ceiling_after'],
        'Shared and cumulative approved budgets include all old/new/partial work')
    if production:
        x=counts['levels'][level_id];require(x['steps']+cap<=level['maximum_new_production_steps']
            and x['calls']+1<=level['maximum_production_calls'],'Fixed per-level production budgets')
    else:require(counts['diagnostic_steps']+cap<=r['maximum_discarded_diagnostic_steps']
        and counts['diagnostic_calls']+1<=r['maximum_diagnostic_integration_calls'],'Shared diagnostic budgets')
    require(not counts['unresolved'],'Dependent dispatch requires every previous admission')
def progress(phase,**extra):
    c=ledger();levels={}
    for key in ORDER:
        path=OUT/'levels'/key
        levels[key]={**c['levels'][key], 'initial_qualified':(path/'restart_initial/completion.json').exists(),
            'active_qualified':(path/'restart_active/completion.json').exists(),
            'native_complete':(path/'native_completion_01/completion.json').exists()}
    replace(OUT/'state.json',dict(phase=phase,utc=s.utc(),window_count=len(list((OUT/'windows').glob('window_*'))),
        current_window=extra.pop('current_window',None),current_level=extra.pop('current_level',None),
        new_saved_steps=c['saved_steps'],new_calls=c['calls'],diagnostic_steps=c['diagnostic_steps'],diagnostic_calls=c['diagnostic_calls'],
        production_steps={k:c['levels'][k]['steps'] for k in ORDER},production_calls={k:c['levels'][k]['calls'] for k in ORDER},
        levels=levels,error=extra.pop('error',None),**extra))
def audit_reserve():
    c=ledger();pending=sum(c['levels'][k]['steps'] for k in ORDER if not (OUT/'levels'/k/'full_audit_01/completion.json').exists())
    # Full independent selector replay is hours of work, never a25min tail.
    return max(1800.,pending*.0065+3600.)


def controls():
    """Zero-solve negative controls on the actual scheduling predicates."""
    require(sha(PROPOSAL)==APPROVED,'Exact approved proposal');p=read(PROPOSAL);r=p['request']
    require(p['gates']==s.q.job.policy.GATES and p['controller']['policy']==selector.POLICY,'Original gates and frozen selector')
    require(p['ledger']['conservative_prospective_baseline_saved_steps']==5647912
        and p['ledger']['conservative_prospective_baseline_integration_calls']==1170,'Disclosed conservative prior costs')
    require(r['maximum_new_saved_steps']==5632768 and r['maximum_new_integration_calls']==1217
        and r['maximum_discarded_diagnostic_steps']==32768 and r['maximum_diagnostic_integration_calls']==27,'Exact approved limits')
    empty=dict(saved_steps=0,calls=0,diagnostic_steps=0,diagnostic_calls=0,unresolved=[],levels={k:dict(steps=0,calls=0) for k in ORDER})
    budget(empty,'f0p0625','production',5000);negative=[]
    for name,changes,kind in [('steps',{'saved_steps':5632768},'production'),('calls',{'calls':1217},'production'),
        ('diagsteps',{'diagnostic_steps':32768},'diagnostic'),('diagcalls',{'diagnostic_calls':27},'diagnostic'),
        ('unknown',{'unresolved':[{}]},'production')]:
        try:budget({**copy.deepcopy(empty),**changes},'f0p0625',kind,1)
        except Exception:negative.append(name)
    require(len(negative)==5,'Actual budget failures reject dispatch')
    for level_id in ORDER:
        limit=definitions()[level_id]
        for field,value in [('steps',limit['maximum_new_production_steps']),('calls',limit['maximum_production_calls'])]:
            trial=copy.deepcopy(empty);trial['levels'][level_id][field]=value
            try:budget(trial,level_id,'production',1)
            except Exception:negative.append(level_id+'_'+field)
    require(len(negative)==11,'Actual per-level step and call exhaustion rejects dispatch')
    localproof=selector.controls();require(localproof['passed'],'Frozen selector pure controls')
    require(clone(original.transaction,vars(original)).__code__ is original.transaction.__code__,'Original physical transaction code identity')
    check=object.__new__(NumericalWindow);check.context('f0p0625')
    require(check.ctx.raw.__code__ is s.context.qualified.raw.__code__
        and check.ctx.baseline.kernel.__code__ is s.context.qualified.baseline.kernel.__code__
        and check.transact.__code__ is local.transaction.__code__, 'Actual private producer/auditor/selector-wrapper code associations')
    for factor in (.125,.0625,.03125):
        expected,_,_=s.factory.load_case(p['logical_core_id'],.01,factor,'core');case=definitions()[IDS[factor]]['case']
        require(comparator.physical_signature(expected['spec'])==comparator.physical_signature(case['spec'])
            and expected['spec']['config']['numerics']==case['spec']['config']['numerics'],'Original resolved physics and numerical controls')
    return dict(passed=True,negative_budget_controls=negative,selector_controls=localproof,
        original_transaction_code_unchanged=True,new_transport_steps=0,new_native_solver_calls=0,
        full_path_execution_order=ORDER,original_accuracy_gate_values=p['gates'],utc=s.utc())


def prepare():
    s.environment();require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Never duplicate/reopen numerical authority')
    p=read(PROPOSAL);require(sha(PROPOSAL)==APPROVED,'Exact proposal approved in direct human reply')
    s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['physical_inputs'])
    result=controls()
    approval=DESIGNS/'human_approval_01'
    if not approval.exists():seal(approval,dict(passed=True,proposal_sha256=APPROVED,
        human_reply='Approve bounded qualification',question_reference='call_73438b6632b24b61b8400c091333e2d4',
        scope=p['request'],no_additional_budget_or_automatic_extension=True,utc=s.utc()))
    else:require(s.fields.sealed(approval/'results.json')['proposal_sha256']==APPROVED,'Same direct approval only')
    template=read(s.factory.contract()['physical_design_file'])
    physical=dict(schema='paper1.timecap-full-physical.v1',cases=[definitions()[k]['case'] for k in ORDER],
        minimum_gap_semantics=template['minimum_gap_semantics'],numerical_controller=CONFIG,
        numerical_controller_source_sha256=sha(selector.__file__),physical_equation_changes=[],accuracy_gate_changes=[])
    physical['binding']=s.api.digest(physical);commit(PHYSICAL,physical)
    sources={**p['source_files'],**evaluator.SOURCE_FILES}
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).suffix=='.py' and ROOT in Path(file).resolve().parents and Path(file).is_file():sources[str(Path(file).resolve())]=sha(file)
    for file in (SELF,ROOT/'paper1_staging/monitor_timecap_full_v1.py'):sources[str(file)]=sha(file)
    inputs={**p['physical_inputs'],str(PROPOSAL):sha(PROPOSAL),str(PHYSICAL):sha(PHYSICAL),
        str(approval/'results.json'):sha(approval/'results.json'),str(approval/'completion.json'):sha(approval/'completion.json')}
    s.api.verify_mapping(sources);s.api.verify_mapping(inputs)
    seal(DESIGNS/'scheduler_readiness_01',dict(**result,source_files=sources,physical_inputs=inputs,
        prototype_globally_installed=False,clock_or_numerical_launch_created=False))
    print('TIMECAP_SCHEDULER_READY_ZERO_STEPS',sha(DESIGNS/'scheduler_readiness_01/results.json'),flush=True)


def authorize():
    require(not PLAN.exists() and not AUTH.exists() and not OUT.exists(),'Fresh shared36h authorization once only')
    ready=s.fields.sealed(DESIGNS/'scheduler_readiness_01/results.json');require(ready['passed'],'Qualified scheduler')
    s.api.verify_mapping(ready['source_files']);s.api.verify_mapping(ready['physical_inputs'])
    p=read(PROPOSAL);start=datetime.now(timezone.utc);end=start+timedelta(hours=36)
    a=dict(**p['request'],start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=end.isoformat(),
        proposal_sha256=APPROVED,human_approval_sha256=sha(DESIGNS/'human_approval_01/results.json'),
        logical_core_id=p['logical_core_id'],step_cap_per_call=5000,maximum_cumulative_physical_steps_per_case=11300000,
        maximum_cumulative_calls_per_case=2400,maximum_output_bytes=p['request']['maximum_new_output_bytes'],
        minimum_free_disk_bytes=p['request']['unchanged_free_reserve_bytes'],successor_cases_authorized=False)
    commit(AUTH,a)
    design={**a, 'authorization_sha256':sha(AUTH),'physical_design_sha256':sha(PHYSICAL),
        'source_files':ready['source_files'],'physical_inputs':{**ready['physical_inputs'],
        str(DESIGNS/'scheduler_readiness_01/results.json'):sha(DESIGNS/'scheduler_readiness_01/results.json'),
        str(DESIGNS/'scheduler_readiness_01/completion.json'):sha(DESIGNS/'scheduler_readiness_01/completion.json')},
        'baseline':p['ledger'],'levels':p['levels'],'execution_order':p['execution_order'],
        'diagnostic_only':False,'accuracy_promotion_requires_both_original_full_pairs':True,
        'production_record_cap_before_active_restart':4096,'production_record_cap_after_active_restart':5000,
        'auditing_reserve_seconds_per_unreplayed_step':.0065,'auditing_fixed_reserve_seconds':3600}
    design['binding']=s.api.digest(design);commit(PLAN,design)
    print('TIMECAP_SHARED_AUTHORITY',a['start_utc'],a['end_utc'],sha(PLAN),flush=True)


class NumericalWindow:
    def __init__(self,index):
        self.index=index;self.folder=OUT/'windows'/f'window_{index:03d}';self.window=read(self.folder/'design_01.json')
        self.p=shared_bound();verify(self.p);self.d=read(PHYSICAL);self.ctx=None;self.level_id=None
    def bound(self):
        p=shared_bound();require(time.time()<instant(self.window['simulation_cutoff_utc']),'Closed numerical window cannot advance')
        require(time.time()+audit_reserve()<instant(p['end_utc']),'Reserve complete independent full replay within36h')
        # The original observer consumes this runtime bound every native call;
        # the frozen transport receipt continues to bind the shared PLAN bytes.
        return {**p,'simulation_cutoff_utc':self.window['simulation_cutoff_utc']}
    def room(self):
        return time.time()+180<instant(self.window['simulation_cutoff_utc']) and time.time()+audit_reserve()+180<instant(self.p['end_utc'])
    def context(self,level_id):
        self.level_id=level_id;out=OUT/'levels'/level_id
        namespace={**vars(original),**vars(local),'PLAN':PLAN,'AUTH':AUTH,'PHYSICAL':PHYSICAL,'OUT':out,
            'CONFIG':CONFIG,'bound':self.bound}
        namespace['verify_inputs']=clone(original.verify_inputs,namespace)
        namespace['make_context']=clone(original.make_context,namespace)
        namespace['physical_transaction']=clone(original.transaction,namespace)
        namespace['transaction']=clone(local.transaction,namespace)
        require(namespace['physical_transaction'].__code__ is original.transaction.__code__,'Original unchanged physical transaction')
        self.transact=namespace['transaction'];self.ctx=namespace['make_context']();return out
    def invoke(self,case,label,cap,before=None,prefix=None,previous=None,kind='diagnostic'):
        require(self.room(),'Transaction plus complete audit reserve before cutoff');self.bound();verify(self.p)
        c=ledger();budget(c,self.level_id,kind,cap);index=c['calls']+1;level=OUT/'levels'/self.level_id
        r=dict(global_index=index,level_id=self.level_id,label=label,kind=kind,maximum_saved_steps=cap,
            input_checkpoint_sha256=s.api.digest(before),previous_result_sha256=previous,window=self.index,utc=s.utc())
        commit(level/'reservations'/f'{label}.json',r);commit(OUT/'reservations'/f'{index:06d}.json',r)
        rec,nxt,row=self.transact(self.ctx,self.p,self.d,case,label,cap,before,prefix,previous)
        folder=level/'records'/label;n=len(rec['rows']);require(0<n<=cap,'Positive bounded complete record')
        # Lossless raw reconstruction must pass before admission/next dispatch.
        decoded,reconstructed=self.ctx.job.codec.read_record(folder/'call.json.xz',sha(PHYSICAL),prefix)
        require(s.api.digest(decoded)==s.api.digest(rec) and reconstructed.reference()==nxt.reference(),'Complete raw/history roundtrip before next call')
        seal(OUT/'admissions'/f'{index:06d}',dict(passed=True,**{k:r[k] for k in ('global_index','level_id','label','kind')},
            saved_steps=n,cap=cap,full_checkpoint_sha256=s.api.digest(rec['result']['checkpoint']),raw_sha256=sha(folder/'call.json.xz'),
            physical_guard_sha256=sha(folder/'guard_completion/results.json'),timecap_guard_sha256=sha(folder/'timecap_guard/results.json'),
            reservation_sha256=sha(OUT/'reservations'/f'{index:06d}.json'),utc=s.utc()))
        progress('numerical',current_window=self.index,current_level=self.level_id)
        print('TIMECAP_FULL_ACCEPTED',index,self.level_id,label,n,rec['result']['checkpoint']['state']['t'],flush=True)
        return rec,nxt,row
    def restart(self,case,name,before=None,prefix=None,previous=None,n=256,j=128,original_record=None,production_label=None):
        level=OUT/'levels'/self.level_id;labels={k:f'diag_{name}_{k}' for k in ('serial','split_a','split_b')}
        serial,_,_=self.invoke(case,labels['serial'],n,copy.deepcopy(before),prefix,previous)
        left,lp,_=self.invoke(case,labels['split_a'],j,copy.deepcopy(before),prefix,previous)
        right,_,_=self.invoke(case,labels['split_b'],n-j,left['result']['checkpoint'],lp,sha(level/'records'/labels['split_a']/'results.json'))
        require(len(serial['rows'])==n and len(left['rows'])==j and len(right['rows'])==n-j
            and s.api.digest(serial['rows'])==s.api.digest(left['rows']+right['rows'])
            and s.api.digest(serial['result']['checkpoint'])==s.api.digest(right['result']['checkpoint']),
            'Exact serial/split rows and FULL checkpoint/history')
        if original_record is not None:
            require(s.api.digest(serial['rows'])==s.api.digest(original_record['rows'])
                and s.api.digest(serial['result']['checkpoint'])==s.api.digest(original_record['result']['checkpoint'])
                and any(x['trigger_grain_ids'] for x in right['onset_timecap']['journal'][:len(right['rows'])]),
                'Triggered restart exactly reproduces first original triggered production record')
        artifacts={str(x):sha(x) for label in labels.values() for x in (level/'records'/label).rglob('*') if x.is_file()}
        seal(level/f'restart_{name}',dict(passed=True,kind='active' if original_record is not None else 'initial' if name=='initial' else 'handoff',
            exact_rows=True,exact_full_checkpoint_history=True,labels=labels,discarded_diagnostic_steps=2*n,
            original_production_label=production_label,first_trigger_index=j if original_record is not None else None,
            triggered_successor=original_record is not None,artifacts=artifacts,utc=s.utc()))
    def save(self,level,before,prefix,name):
        if before is None:return
        folder=level/name;folder.mkdir(parents=True,exist_ok=False);DOC.store(folder/'checkpoint.json',before,sha(PHYSICAL))
        commit(folder/'prefix.json',prefix.reference())
        seal(folder/'qualification',dict(passed=True,full_checkpoint_sha256=s.api.digest(before),
            prefix_sha256=sha(folder/'prefix.json'),design_sha256=sha(PLAN),utc=s.utc()))
    def load(self,level):
        checkpoints=sorted(level.glob('window_checkpoint_*'))
        if not checkpoints:return None,None,None
        folder=checkpoints[-1];gate=s.fields.sealed(folder/'qualification/results.json');before=DOC.read(folder/'checkpoint.json')
        require(gate['full_checkpoint_sha256']==s.api.digest(before) and gate['prefix_sha256']==sha(folder/'prefix.json')
            and gate['design_sha256']==sha(PLAN),'Authenticated full handoff checkpoint')
        labels=ledger()['levels'][self.level_id]['production_labels'];require(labels,'No synthetic inherited checkpoint')
        admission=s.fields.sealed(level/'records'/labels[-1]/'guard_completion/results.json')
        require(admission['full_checkpoint_sha256']==s.api.digest(before),'Handoff equals latest accepted production state')
        ref=read(folder/'prefix.json');prefix=self.ctx.job.codec.HistoryState(**ref,history_bytes=self.ctx.job.codec.packed_history(before['state']['history']))
        self.ctx.job.codec.validate_prefix(prefix,sha(PHYSICAL))
        return before,prefix,sha(level/'records'/labels[-1]/'results.json')
    def level(self,level_id):
        level=self.context(level_id);case=definitions()[level_id]['case'];before=prefix=previous=None
        initial=(level/'restart_initial/completion.json').exists()
        if not initial:
            smoke,_,_=self.invoke(case,'diag_smoke32',32)
            olddesign=ROOT/'paper1_designs'/OLD[case['factor']]/'physical_cases_01.json'
            oldpath=ROOT/'paper1_runs'/OLD[case['factor']]/'records/production_00001/call.json.xz'
            archived,_=self.ctx.job.codec.read_record(oldpath,sha(olddesign),None)
            require(len(smoke['rows'])==32 and not any(x['trigger_grain_ids'] for x in smoke['onset_timecap']['journal'])
                and s.api.digest(smoke['rows'])==s.api.digest(archived['rows'][:32]),'Actual fresh pretrigger32 rows agree with original same-factor bits')
            self.restart(case,'initial')
        else:
            before,prefix,previous=self.load(level);require(before is not None,'Continuing level needs authenticated full handoff')
            self.restart(case,f'handoff_{self.index:03d}',before,prefix,previous)
        try:
            while self.room():
                c=ledger()['levels'][level_id];label=f'production_{len(c["production_labels"])+1:05d}'
                # Existing local4096 qualification fits the unchanged45s
                # native cap with more headroom. Segmentation is not a dt or
                # physical change; every extra call still consumes its cap.
                record_cap=5000 if (level/'restart_active/completion.json').exists() else 4096
                cap=min(record_cap,definitions()[level_id]['maximum_new_production_steps']-c['steps'])
                record,nprefix,_=self.invoke(case,label,cap,before,prefix,previous,'production')
                original_before,original_prefix,original_previous=before,prefix,previous
                before,prefix=record['result']['checkpoint'],nprefix
                previous=sha(level/'records'/label/'results.json')
                accepted=record['onset_timecap']['journal'][:len(record['rows'])]
                triggers=[i for i,x in enumerate(accepted) if x['trigger_grain_ids']]
                if triggers and not (level/'restart_active/completion.json').exists():
                    j=triggers[0];require(j>0 and record['result']['checkpoint']['state']['pending_trial'] is None,
                        'First accepted active record must permit exact original FULL-output restart qualification')
                    # Save the admitted original output even if the diagnostic fails.
                    self.restart(case,'active',original_before,original_prefix,original_previous,len(record['rows']),j,record,label)
                before,prefix=record['result']['checkpoint'],nprefix;previous=sha(level/'records'/label/'results.json')
                if record['result']['status'] in ('present_at_horizon','full_window_exit'):
                    require((level/'restart_active/completion.json').exists(),'Real approaching-contact restart required over full path')
                    self.save(level,before,prefix,'recoverable');c=ledger()['levels'][level_id]
                    restarts=sorted(str(x) for x in level.glob('restart_*/results.json'))
                    seal(level/'native_completion_01',dict(passed=True,native_complete=True,level_id=level_id,case_id=case['id'],
                        production_labels=c['production_labels'],diagnostic_labels=c['diagnostic_labels'],accepted_physical_steps=c['steps'],
                        discarded_diagnostic_steps=sum(s.fields.sealed(level/'records'/x/'guard_completion/results.json')['saved_steps'] for x in c['diagnostic_labels']),
                        full_checkpoint_sha256=s.api.digest(before),known_unaccepted_saved_steps=0,unknown_reserved_steps_upper_bound=0,
                        restart_receipts=restarts,design_sha256=sha(PLAN),utc=s.utc()))
                    return True
            return False
        finally:
            if before is not None and not (level/'recoverable').exists():self.save(level,before,prefix,f'window_checkpoint_{self.index:03d}')


def window(index):
    me=psutil.Process();me.cpu_affinity([14]);w=NumericalWindow(index)
    expected=read(w.folder/'worker_launch.json');require(expected['pid']==me.pid and expected['created']==me.create_time()
        and expected['command']==me.cmdline() and expected['window_design_sha256']==sha(w.folder/'design_01.json'),'Exact own frozen window launch')
    s.q.reference.JOB.parent.b.old.parent.configure();s.q.kernel.warm();s.q.kernel.reset()
    reason='window_cutoff';error=None
    try:
        finepass=(OUT/'comparison_fine/results.json').exists() and s.fields.sealed(OUT/'comparison_fine/results.json')['passed']
        for level_id in (ORDER if finepass else ORDER[:2]):
            if (OUT/'levels'/level_id/'native_completion_01/completion.json').exists():continue
            if not w.room():break
            if not w.level(level_id):break
        if all((OUT/'levels'/k/'native_completion_01/completion.json').exists() for k in (ORDER if finepass else ORDER[:2])):
            reason='all_levels_ready' if finepass else 'fine_pair_ready'
    except Exception as exc:
        error=dict(message=repr(exc),traceback=traceback.format_exc());raise
    finally:
        seal(w.folder/'worker_disposition_01',dict(passed=error is None,reason=reason,error=error,ledger=ledger(),utc=s.utc()))


def run_window(index):
    p=shared_bound();verify(p);require(index<=3,'At most three12h numerical windows')
    folder=OUT/'windows'/f'window_{index:03d}';folder.mkdir(parents=True,exist_ok=False)
    start=datetime.now(timezone.utc);end=min(start+timedelta(hours=12),datetime.fromisoformat(p['end_utc']))
    require((end-start).total_seconds()>1800,'Enough remaining time for bounded numerical window')
    design=dict(index=index,start_utc=start.isoformat(),end_utc=end.isoformat(),
        simulation_cutoff_utc=(end-timedelta(minutes=15)).isoformat(),worker_cutoff_utc=(end-timedelta(minutes=5)).isoformat(),
        shared_design_sha256=sha(PLAN),authorization_sha256=sha(AUTH),controller_source_sha256=sha(SELF))
    commit(folder/'design_01.json',design);command=[str(PYTHON),'-B','-u',str(SELF),'window',str(index)]
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        proc=subprocess.Popen(command,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        launch=dict(pid=proc.pid,created=psutil.Process(proc.pid).create_time(),command=command,
            window_design_sha256=sha(folder/'design_01.json'),utc=s.utc());commit(folder/'worker_launch.json',launch)
        require(not s.identity(launch)['retired'],'Exact fresh worker birth and command')
        seal(folder/'launch_authentication_01',dict(passed=True,window_design_sha256=sha(folder/'design_01.json'),
            worker_launch_sha256=sha(folder/'worker_launch.json'),controller_source_sha256=sha(SELF),design_sha256=sha(PLAN),utc=s.utc()))
        while proc.poll() is None:
            if time.time()>=instant(design['worker_cutoff_utc']) or time.time()>=instant(p['end_utc'])-60:
                s.stop_owned(proc,launch);break
            time.sleep(1)
        code=proc.wait(timeout=15)
    require(s.identity(launch)['retired'],'Exact numerical worker retired before full replay')
    commit(folder/'exit.json',dict(returncode=code,identity=s.identity(launch),logs={str(x):sha(x) for x in folder.glob('*.log')},utc=s.utc()))
    require(code==0,'Worker failure stops all dependent dispatch')
    return s.fields.sealed(folder/'worker_disposition_01/results.json')


def full(level_id):
    level=OUT/'levels'/level_id;path=level/'full_audit_01/results.json'
    require(not path.exists(),'Each full post-exit audit exactly once')
    progress('full_evidence_replay',current_level=level_id)
    return evaluator.authenticate(level,definitions()[level_id]['case'],PLAN,PHYSICAL,CONFIG)


def owner():
    p=shared_bound();verify(p);require(not (OUT/'owner_launch.json').exists(),'No duplicate supervisor')
    me=psutil.Process();me.cpu_affinity([14]);commit(OUT/'owner_launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=s.utc()))
    seal(OUT/'launch_authentication_01',dict(passed=True,owner_identity_sha256=sha(OUT/'owner_launch.json'),controller_source_sha256=sha(SELF),
        design_sha256=sha(PLAN),authorization_sha256=sha(AUTH),proposal_sha256=APPROVED,utc=s.utc()))
    error=None;reason='approved_window_or_budget_exhausted';audited={};qualified=False
    try:
        for index in range(1,4):
            progress('opening_numerical_window',current_window=index);result=run_window(index)
            require(result['passed'] and not ledger()['unresolved'],'Window evidence and all reservations complete')
            if result['reason']=='fine_pair_ready':
                for key in ORDER[:2]:audited[key]=full(key)
                shared_bound();fine=comparator.compare(audited[ORDER[0]],audited[ORDER[1]],OUT/'comparison_fine')
                require(fine['passed'],'Original fine/finer full-path accuracy gate FAILED; stop dependent dispatch')
            elif result['reason']=='all_levels_ready':
                audited['f0p125']=full('f0p125');shared_bound()
                coarse=comparator.compare(audited['f0p125'],audited['f0p0625'],OUT/'comparison_coarse')
                require(coarse['passed'],'Original coarse/fine full-path accuracy gate FAILED; never promote coarse')
                qualified=True;reason='both_original_full_pair_gates_passed';break
            if time.time()+audit_reserve()+1800>=instant(p['end_utc']):break
        # Incomplete/negative paths remain preserved, never accuracy-promoted.
    except Exception as exc:
        error=dict(message=repr(exc),traceback=traceback.format_exc());reason='dependent_dispatch_stopped';print(traceback.format_exc(),flush=True)
    finally:
        c=ledger();verify(p)
        identities=[];logs={}
        for folder in sorted((OUT/'windows').glob('window_*')):
            identity=s.identity(read(folder/'worker_launch.json'));require(identity['retired'],'All exact numerical identities retired at final disposition')
            closed=read(folder/'exit.json');s.api.verify_mapping(closed['logs']);logs.update(closed['logs'])
            identities.append(dict(path=str(folder/'worker_launch.json'),sha256=sha(folder/'worker_launch.json'),inspection=identity))
        artifacts={str(x):sha(x) for x in OUT.rglob('*') if x.is_file() and x.name not in ('state.json','stdout.log','stderr.log')}
        own,total,free=sizes()
        seal(OUT/'final_disposition_01',dict(passed=error is None and qualified,reason=reason,error=error,
            qualification_passed=qualified,full_path_accuracy_passed=qualified,core_result_admitted=False,
            eligible_case_count_if_final_retirement_passes=2 if qualified else 1,paper1_dataset_complete=False,
            accepted_new_physical_steps=c['accepted_new_physical_steps'],
            discarded_diagnostic_steps=c['accepted_discarded_diagnostic_steps'],known_unaccepted_saved_steps=c['known_unaccepted_saved_steps'],
            unknown_reserved_steps_upper_bound=c['unknown_reserved_steps_upper_bound'],ledger=c,identities=identities,
            source_files=p['source_files'],physical_inputs=p['physical_inputs'],artifacts=artifacts,closed_worker_logs=logs,
            design_sha256=sha(PLAN),retained_bytes=own,total_retained_bytes=total,free_bytes=free,
            owner_live_logs_intentionally_unsealed=True,successor_cases_dispatched=False,utc=s.utc()))
        progress('owner_final_disposition',error=error,reason=reason,qualification_passed=qualified)


def retire():
    """Separate post-owner receipt; invoked only after exact owner exit."""
    p=shared_bound();verify(p);launch=read(OUT/'owner_launch.json');require(s.identity(launch)['retired'],'Exact owner retired')
    final=s.fields.sealed(OUT/'final_disposition_01/results.json');s.api.verify_mapping(final['artifacts'])
    s.api.verify_mapping(final['closed_worker_logs']);logs={str(x):sha(x) for x in (OUT/'owner').glob('*.log')}
    exitrow=read(OUT/'owner/exit.json');require(exitrow['identity']['retired'] and exitrow['returncode']==0,'Authenticated direct supervisor exit')
    seal(OUT/'final_retirement_01',dict(passed=True,qualification_passed=final['qualification_passed'],
        final_disposition_sha256=sha(OUT/'final_disposition_01/results.json'),owner_identity_sha256=sha(OUT/'owner_launch.json'),
        exact_owner_retired=s.identity(launch),closed_owner_logs=logs,owner_exit_sha256=sha(OUT/'owner/exit.json'),
        ledger=ledger(),source_files=p['source_files'],physical_inputs=p['physical_inputs'],
        administrative_supervisor_still_live=True,separate_supervisor_exit_receipt_required=True,utc=s.utc()))
    print('TIMECAP_FULL_RETIRED',sha(OUT/'final_retirement_01/results.json'),flush=True)


def supervise():
    """Hidden absolute watchdog; exact child exit/logs are sealed separately."""
    p=shared_bound();verify(p);folder=OUT/'supervisor';folder.mkdir(parents=True,exist_ok=False)
    me=psutil.Process();me.cpu_affinity([14]);commit(folder/'launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=s.utc()))
    owner_folder=OUT/'owner';owner_folder.mkdir(parents=True,exist_ok=False)
    command=[str(PYTHON),'-B','-u',str(SELF),'owner'];forced=False
    with (owner_folder/'stdout.log').open('xb') as stdout,(owner_folder/'stderr.log').open('xb') as stderr:
        proc=subprocess.Popen(command,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        launch=dict(pid=proc.pid,created=psutil.Process(proc.pid).create_time(),command=command,utc=s.utc());commit(owner_folder/'launch.json',launch)
        require(not s.identity(launch)['retired'],'Exact hidden owner launch')
        while proc.poll() is None:
            if time.time()>=instant(p['end_utc'])-180:
                # Only registered children are touched, with BOTH exact birth
                # and full accessible command checked by stop_owned.
                for path in sorted((OUT/'windows').glob('window_*/worker_launch.json')):
                    worker=read(path)
                    if not s.identity(worker)['retired']:s.stop_owned(psutil.Process(worker['pid']),worker)
                s.stop_owned(proc,launch);forced=True;break
            time.sleep(1)
        code=proc.wait(timeout=15)
    # Abnormal owner exit must never orphan its already registered worker.
    # Birth mismatch excludes an unrelated reused PID; access denial fails.
    for path in sorted((OUT/'windows').glob('window_*/worker_launch.json')):
        worker=read(path)
        if not s.identity(worker)['retired']:s.stop_owned(psutil.Process(worker['pid']),worker)
    commit(owner_folder/'exit.json',dict(returncode=code,forced=forced,identity=s.identity(launch),
        logs={str(x):sha(x) for x in owner_folder.glob('*.log')},utc=s.utc()))
    if not (OUT/'final_disposition_01/completion.json').exists():
        # Failure evidence only: no interrupted raw record is admitted here.
        c=ledger();artifacts={str(x):sha(x) for x in OUT.rglob('*') if x.is_file()
            and x.name not in ('state.json','stdout.log','stderr.log')}
        seal(OUT/'watchdog_failure_01',dict(passed=False,reason='owner_failed_or_absolute_watchdog',forced=forced,
            direct_owner_returncode=code,ledger=c,artifacts=artifacts,exact_owner_retired=s.identity(launch),utc=s.utc()))
    else:
        require(code==0 and not forced,'Final disposition requires directly successful owner retirement')
        retire()
    seal(folder/'completion_01',dict(passed=code==0 and not forced,owner_returncode=code,forced=forced,
        owner_exit_sha256=sha(owner_folder/'exit.json'),no_task_numerical_worker_live=all(s.identity(read(x))['retired']
        for x in (OUT/'windows').glob('window_*/worker_launch.json')),utc=s.utc()))


if __name__=='__main__':
    action=sys.argv[1]
    if action=='window':
        # Parent writes the immutable launch before the worker may proceed.
        path=OUT/'windows'/f'window_{int(sys.argv[2]):03d}'/'worker_launch.json'
        for _ in range(100):
            if path.exists():break
            time.sleep(.05)
        window(int(sys.argv[2]))
    else:{'controls':lambda:print(json.dumps(controls())), 'prepare':prepare,'authorize':authorize,'owner':owner,'supervise':supervise,'retire':retire}[action]()
