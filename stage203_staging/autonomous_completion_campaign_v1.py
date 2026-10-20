"""Fresh original campaign using the independently qualified Stage202 stack.

Administrative bridge only: output, measured resource schedule and authority.
All integration, lifecycle, contact routing, codecs and scientific gates retain
their qualified code. Three producers preserve the global six-record bound.
"""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy,importlib.util,os,sys,psutil,shutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage202_staging'))
import contact_repaired_stack_preflight_v1 as pre
api,q=pre.api,pre.q
spec=importlib.util.spec_from_file_location('_stage203_fresh_lifecycle',pre.job.__file__)
job=importlib.util.module_from_spec(spec);sys.modules[spec.name]=job;spec.loader.exec_module(job)
BASE='autonomous_completion_20260929'
job.ROOT=Path('D:/MATDEM_MICROPLASTIC');job.SELF=Path(__file__).resolve();job.BASE=BASE
job.DESIGN=ROOT/'stage203_designs'/BASE/'design_01.json'
job.RUN=job.ROOT/'stage203_runs'/BASE/'run_01'
job.PREFLIGHT=job.ROOT/'stage203_runs'/BASE/'not_authorized'
job.OUT=ROOT/'stage203_evaluations'/BASE
job.WORK=ROOT/'stage203_designs'/BASE/'authorization_01.json'
job.PREFLIGHT_SCRIPT=pre.job.PREFLIGHT_SCRIPT
job.codec=pre.job.codec;job.kernel=pre.job.kernel;job.observer=pre.job.observer
raw_execute=FunctionType(pre.raw_execute.__code__,dict(job.__dict__),'execute_segment',pre.raw_execute.__defaults__,pre.raw_execute.__closure__)
job.execute_segment=FunctionType(pre.execute_segment.__code__,dict(pre.execute_segment.__globals__,job=job,raw_execute=raw_execute),'execute_segment',pre.execute_segment.__defaults__,pre.execute_segment.__closure__)
AUDIT=pre.job.OUT/'independent_readiness_02/results.json'
CLOSE=pre.job.OUT/'qualification_close_01/results.json'
OLD_RESOURCE=pre.job.OUT/'resource_reassessment_01/results.json'
OLD_RESOURCE_AUDIT=pre.job.OUT/'resource_independent_01/results.json'
DISPOSITION=job.OUT/'old_audit_disposition_01/results.json'
RESOURCE=job.OUT/'resource_schedule_01/results.json'
BRIDGE=job.OUT/'qualification_bridge_01'
ALLOWED={'stage','sources','inputs','binding','agent_work_end_utc','simulation_cutoff_utc','final_audit_deadline_utc','resource_scenario','production_authorized','claim','guard','qualification_inheritance','provenance_transaction_hours_with_margin','provenance_bytes_with_margin'}
IDENTICAL=('worker','auditor','audit_one','evaluate','stopping','acknowledged','binding','commit','root_settings','start_child','paths','supervise','clear_telemetry')


def sealed(path):
    r=api.read(path);api.require(api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed prerequisite '+str(path));return r


def active_owned(exclude_self=True):
    found=[]
    for proc in psutil.process_iter(['pid','name']):
        if exclude_self and proc.pid==os.getpid():continue
        if 'python' not in (proc.info['name'] or '').lower():continue
        try:
            argv=proc.cmdline()
            # Match actual script tokens, not a diagnostic -c string or PID alone.
            scripts=[x for x in argv if x.lower().endswith('.py') and 'matdem_microplastic' in x.lower()]
            if scripts:found.append(dict(pid=proc.pid,argv=argv,created=proc.create_time()))
        except psutil.NoSuchProcess:continue
    return found


def inherited():
    old=api.read(pre.job.DESIGN);pre.verify(old)
    r=pre.job.verify_preflight(old);a=sealed(AUDIT);c=sealed(CLOSE)
    api.require(api.sha(CLOSE)=='25ce489271f45666e16f376080c492288a06fe2d8e0e92eadfe387a5d58ed181','independent Stage202 closure anchor')
    api.require(r['new_steps']==17000 and a['stage202_preflight_steps_verified']==17000 and c['stage202_saved_and_independently_passing_steps']==17000 and c['unresolved_step_reservations']==0,'exact separate Stage202 accepted ledger')
    api.require(a['numerical_qualification_passed'] and a['process_qualification_passed'] and a['raw_records_independently_decoded']==35 and len(a['numerical_reaudits'])==27 and a['all_owned_processes_retired'],'complete independent full-stack qualification')
    api.verify_mapping(c['inputs']);api.verify_mapping(r['artifacts'])
    return r


def qualification_lineage():
    return dict(design_sha256=api.sha(pre.job.DESIGN),preflight_result_sha256=api.sha(pre.job.OUT/'preflight_01/results.json'),independent_result_sha256=api.sha(AUDIT),closure_sha256=api.sha(CLOSE),new_qualification_steps_in_bridge=0,preflight_steps=17000,stage201_saved_steps=48813,stage201_independently_passing_steps=48325,stage201_preserved_failed_steps=488)


def equivalence(d):
    old=api.read(pre.job.DESIGN);pre.verify(old);w=api.read(job.WORK);resource=sealed(RESOURCE)
    changed={k for k in set(d)|set(old) if d.get(k)!=old.get(k)}
    api.require(changed<=ALLOWED,'only administrative/output/resource fields changed')
    api.require(d['budget']==old['budget'] and d['budget']['workers']==w['production_workers']==3,'all budgets unchanged; three producer slots')
    api.require(d['maximum_unverified_segments_per_case']*3<=d['maximum_unverified_segments_total']==w['maximum_outstanding_records']==6,'global six pending bound')
    api.require(d['simulation_cutoff_utc']==resource['simulation_cutoff_utc']==w['simulation_cutoff_utc'] and d['final_audit_deadline_utc']==d['agent_work_end_utc']==resource['final_audit_deadline_utc']==w['final_audit_deadline_utc'],'new qualified clock scope')
    api.require(d['cases']==old['cases'] and d['numerical_gates']==old['numerical_gates']==job.policy.GATES and d['production_authorized'] and d['fresh_start_required'] and not d['physical_changes'],'same fresh six-case scientific contract')
    api.require(d['resource_scenario']==resource and d['provenance_transaction_hours_with_margin']==resource['hours_with_margin'] and d['provenance_bytes_with_margin']==resource['bytes_with_margin'],'exact resource plan')
    api.require(all(d['sources'].get(p)==h for p,h in old['sources'].items()) and all(d['inputs'].get(p)==h for p,h in old['inputs'].items()),'all frozen predecessor lineage retained')
    api.require(d['qualification_inheritance']==qualification_lineage(),'disclosed qualification inheritance')
    api.require(d['sources'].get(str(job.SELF))==api.sha(job.SELF) and d['inputs'].get(str(job.WORK))==api.sha(job.WORK),'launcher/authority bound')
    proofs={}
    for name in IDENTICAL:
        a,b=getattr(job,name),getattr(pre.job,name)
        api.require(a.__code__==b.__code__ and q.campaign.code_sha(a)==q.campaign.code_sha(b),'same lifecycle '+name);proofs[name]=q.campaign.code_sha(a)
    api.require(raw_execute.__code__ is pre.raw_execute.__code__ and q.campaign.code_sha(raw_execute)==d['integration_code_sha256'],'same integration bytecode')
    api.require(job.execute_segment.__code__ is pre.execute_segment.__code__,'same qualified two-contact routing wrapper')
    for key in ('parent','fast','prior','deadline','capture','observer'):
        api.require(raw_execute.__globals__[key] is pre.raw_execute.__globals__[key],'same physics dependency '+key)
    for key in ('repair','candidate','previous'):
        api.require(job.execute_segment.__globals__[key] is pre.execute_segment.__globals__[key],'same numerical routing dependency '+key)
    api.require(raw_execute.__globals__['codec'] is pre.job.codec and raw_execute.__globals__['DESIGN']==job.DESIGN,'new evidence identity only')
    api.require(job.kernel is pre.job.kernel and job.codec is pre.job.codec and job.observer is pre.job.observer,'same qualified kernel/codec/observer')
    pre.storage.verify_bindings();pre.affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])
    return changed,proofs


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    equivalence(d)
job.verify=verify


def verify_preflight(d):
    verify(d);r=inherited();b=sealed(BRIDGE/'results.json')
    api.require(b['passed'] and b['design_sha256']==api.sha(job.DESIGN) and b['source_sha256']==api.sha(__file__) and b['function_identity_sha256']==equivalence(d)[1],'zero-step qualified administrative bridge')
    return {**r,'refreshed_hours_with_margin':sealed(RESOURCE)['hours_with_margin']}
job.verify_preflight=verify_preflight


def resource_gate(d):
    verify_preflight(d);r=sealed(RESOURCE)
    available=(job.policy.utc(d['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    audit_available=(job.policy.utc(d['final_audit_deadline_utc'])-job.policy.utc(d['simulation_cutoff_utc'])).total_seconds()/3600
    free=shutil.disk_usage(job.ROOT).free;need=r['bytes_with_margin']+d['budget']['minimum_free_disk_bytes']
    api.require(available>=r['hours_with_margin'] and audit_available>=r['required_final_audit_hours'],'measured production and audit windows fit')
    api.require(free>=need and r['call_limit_passed'],'full ceiling storage/reserve and call caps')
    return dict(required_hours=r['hours_with_margin'],available_hours=available,required_final_audit_hours=r['required_final_audit_hours'],audit_hours_available=audit_available,storage_with_reserve_bytes=need,free_D_bytes=free,production_workers=3)


def disposition():
    inherited();api.require(not active_owned(),'no existing owned worker/evaluator')
    old_design=ROOT/'stage200_designs/revised_deadline_campaign_20260927/design_01.json'
    old_eval=ROOT/'stage200_evaluations/revised_deadline_campaign_20260927/evaluation_01'
    api.require(not old_eval.exists(),'old full evaluator absent; no inferred pass')
    old=api.read(old_design);api.verify_mapping(old['sources']);api.verify_mapping(old['inputs'])
    terminal=Path('D:/MATDEM_MICROPLASTIC/stage200_runs/revised_deadline_campaign_20260927/run_01/completion.json')
    t=api.read(terminal);api.require(t['all_owned_processes_retired'] and t['stop_reasons'],'old campaign failed and retired')
    files=[old_design,terminal,ROOT/'stage200_evaluations/revised_deadline_campaign_20260927/terminal_blocker_snapshot_01/results.json',pre.CLOSE,CLOSE,AUDIT,job.WORK,Path(__file__)]
    # Every local qualification input was fully authenticated by the Stage201
    # closure; a fresh campaign does not consume an old production checkpoint.
    local=sealed(pre.CLOSE);api.verify_mapping(local['inputs'])
    result=dict(passed=True,utc=job.utc().isoformat(),new_trajectory_steps=0,old_campaign_status='failed_incomplete',old_terminal_audit='interrupted_unresolved',old_evaluator_pid=40572,old_evaluation_output_exists=False,old_audit_cause='unknown',old_audit_exit_status='unavailable',old_audit_restarted=False,old_failure_promoted=False,fresh_production_checkpoint_source='original initial states only',qualification_lineage=qualification_lineage(),disposition='Preserve the interrupted old terminal audit as unresolved evidence. Retain its failed/incomplete campaign. Independently sealed Stage201/202 qualification and fresh initial states support the new campaign without an old terminal-pass claim.',inputs={str(f):api.sha(f) for f in files})
    job.commit(DISPOSITION,result);job.commit(DISPOSITION.parent/'completion.json',dict(passed=True,results_sha256=api.sha(DISPOSITION)))
    print('OLD_AUDIT_DISPOSITION',api.sha(DISPOSITION),flush=True)


def resource():
    r=sealed(OLD_RESOURCE);a=sealed(OLD_RESOURCE_AUDIT);w=api.read(job.WORK)
    api.require(a['independent_calculation_passed'] and a['resource_result_sha256']==api.sha(OLD_RESOURCE) and r['call_limit_passed'],'independently checked measured costs and caps')
    api.require(a['required_production_hours']==r['production_hours_with_margin'] and a['required_final_audit_hours']==r['required_final_audit_hours'] and a['storage_with_reserve_bytes']==r['storage_bytes_with_margin']+r['minimum_reserve_bytes'],'exact cost inheritance')
    now=job.utc();available=(job.policy.utc(w['simulation_cutoff_utc'])-now).total_seconds()/3600
    reserve=(job.policy.utc(w['final_audit_deadline_utc'])-job.policy.utc(w['simulation_cutoff_utc'])).total_seconds()/3600
    free=shutil.disk_usage(job.ROOT).free
    api.require(available>=a['required_production_hours'] and reserve>=a['required_final_audit_hours'] and free>=a['storage_with_reserve_bytes'],'revised time/storage gates fit')
    result={**r,'hours_with_margin':a['required_production_hours'],'bytes_with_margin':r['storage_bytes_with_margin'],'simulation_cutoff_utc':w['simulation_cutoff_utc'],'final_audit_deadline_utc':w['final_audit_deadline_utc'],'resource_gate_passed':True,'production_workers':3,'available_production_hours':available,'available_final_audit_hours':reserve,'free_D_bytes':free,'new_trajectory_steps':0,'utc':now.isoformat(),'inherited_resource_result_sha256':api.sha(OLD_RESOURCE),'inherited_independent_resource_sha256':api.sha(OLD_RESOURCE_AUDIT),'authority_sha256':api.sha(job.WORK),'source_sha256':api.sha(__file__),'claim':'Same independently checked costs/margins/storage; updated calendar only. Estimate is not a hard runtime guarantee.'}
    job.commit(RESOURCE,result);job.commit(RESOURCE.parent/'completion.json',dict(passed=True,results_sha256=api.sha(RESOURCE)));print('RESOURCE_REVISION',available,reserve,flush=True)


def prepare():
    api.require(not job.RUN.exists() and not job.DESIGN.exists(),'fresh exclusive campaign')
    inherited();sealed(DISPOSITION);r=sealed(RESOURCE)
    d=copy.deepcopy(api.read(pre.job.DESIGN));d.pop('binding')
    files=[Path(__file__),Path(pre.__file__),ROOT/'stage202_staging/audit_contact_repaired_stack_v2.py',ROOT/'stage202_staging/resource_reassessment_v1.py',ROOT/'stage202_staging/audit_resource_reassessment_v1.py',Path(__file__).with_name('audit_completion_bridge_v1.py')]
    inputs=[job.WORK,CLOSE,CLOSE.parent/'completion.json',AUDIT,AUDIT.parent/'completion.json',pre.job.DESIGN,RESOURCE,RESOURCE.parent/'completion.json',DISPOSITION,DISPOSITION.parent/'completion.json',OLD_RESOURCE,OLD_RESOURCE_AUDIT]
    d.update(stage='Stage203 autonomous fresh original six-case completion campaign',sources={**d['sources'],**{str(x):api.sha(x) for x in files}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},simulation_cutoff_utc=r['simulation_cutoff_utc'],final_audit_deadline_utc=r['final_audit_deadline_utc'],agent_work_end_utc=r['final_audit_deadline_utc'],resource_scenario=r,production_authorized=True,qualification_inheritance=qualification_lineage(),provenance_transaction_hours_with_margin=r['hours_with_margin'],provenance_bytes_with_margin=r['bytes_with_margin'],guard='Fresh original initial states; exact qualified Stage202 numerical/integration/lifecycle/codec stack. Three producers preserve six pending records. Original scientific/resource caps retained.',claim='Two labelled placements separately; require complete fresh selected/fine comparisons. All historical failures and interrupted audits preserved.')
    d['binding']=api.digest(d);verify(d);changed,proofs=equivalence(d)
    rejects=[]
    mutations=[('cases',lambda x:x['cases'].pop()),('step',lambda x:x['cases'][0].update(factor=1)),('gates',lambda x:x['numerical_gates'].update(whole_position_over_b_max=.1)),('concurrency',lambda x:x['budget'].update(workers=6)),('budget',lambda x:x['budget'].update(step_cap_per_call=20000)),('deadline',lambda x:x.update(simulation_cutoff_utc='2030-01-01T00:00:00+00:00')),('lineage',lambda x:x['sources'].pop(next(iter(api.read(pre.job.DESIGN)['sources']))))]
    for label,mutate in mutations:
        bad=copy.deepcopy(d);mutate(bad)
        try:equivalence(bad)
        except (ValueError,RuntimeError,AssertionError):rejects.append(label)
        else:raise AssertionError('accepted corrupt amendment '+label)
    import itertools
    checks=0
    for order in itertools.permutations([c['id'] for c in d['cases']]):
        life=job.policy.initial([c['id'] for c in d['cases']]);remaining=list(order)
        while life.queued or life.active:
            while True:
                life,name=job.policy.dispatch(life,3,True)
                if name is None:break
                api.require(len(life.active)*2<=6,'bounded producer dispatch')
            name=next(n for n in remaining if n in life.active);remaining.remove(name);life=job.policy.retire(life,name,0,True)
        api.require(len(life.retired)==6 and not life.stop_reasons,'complete dispatch drain');checks+=1
    job.commit(job.DESIGN,d)
    result=dict(passed=True,design_sha256=api.sha(job.DESIGN),source_sha256=api.sha(__file__),changed_fields=sorted(changed),function_identity_sha256=proofs,contact_route_bytecode_sha256=q.campaign.code_sha(job.execute_segment),corrupt_amendments_rejected=rejects,zero_step_dispatch_permutations=checks,new_trajectory_steps=0,preflight_reused_not_rerun=True,qualification_inheritance=qualification_lineage(),utc=job.utc().isoformat())
    job.commit(BRIDGE/'results.json',result);job.commit(BRIDGE/'completion.json',dict(passed=True,results_sha256=api.sha(BRIDGE/'results.json')))
    print('CAMPAIGN_PREPARED',api.sha(job.DESIGN),resource_gate(d),flush=True)


def owned(name=None):
    d=api.read(job.DESIGN);verify(d)
    core=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=pre.affinity.bind(core);job.commit(job.RUN/((name or 'auditor')+'.affinity.json'),{**info,'design_sha256':api.sha(job.DESIGN),'argv':sys.argv,'utc':job.utc().isoformat()})


if __name__=='__main__':
    args=sys.argv[1:]
    if args==['disposition']:disposition()
    elif args==['resource']:resource()
    elif args==['prepare']:prepare()
    elif args==['check']:print(resource_gate(api.read(job.DESIGN)),flush=True)
    elif args==['supervise','campaign']:
        resource_gate(api.read(job.DESIGN))
        a=sealed(job.OUT/'independent_bridge_01/results.json');api.require(a['passed'] and a['design_sha256']==api.sha(job.DESIGN),'independent administrative bridge')
        api.require(not active_owned(),'no duplicate simulation or evaluator')
        job.supervise('campaign')
    elif len(args)==3 and args[:2]==['worker','campaign']:owned(args[2]);job.worker('campaign',args[2])
    elif args==['auditor','campaign']:owned();job.auditor('campaign')
    elif args==['evaluate','campaign']:job.evaluate('campaign')
    else:raise ValueError('disposition | resource | prepare | check | supervise campaign | worker campaign CASE | auditor campaign | evaluate campaign')
