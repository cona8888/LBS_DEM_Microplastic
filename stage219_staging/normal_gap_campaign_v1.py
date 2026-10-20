"""Fresh isolated production namespace; qualified operand adapter and unchanged gates."""
from pathlib import Path
from types import FunctionType,ModuleType,SimpleNamespace
import copy,inspect,os,psutil,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage216_staging'))
import same_policy_stack_preflight_v1 as stack
api,q=stack.api,stack.q
BASE='normal_gap_campaign_20261001';SELF=Path(__file__).resolve()
QUAL_DESIGN=stack.job.DESIGN;QUAL_NUM=stack.job.OUT/'failed_stack_independent_02/results.json'
QUAL_FIX=ROOT/'stage217_evaluations/isolated_drain_fixtures_20261001/independent_01/results.json'
RESOURCE=ROOT/'stage218_evaluations/normal_gap_resource_20261001/resource_01/results.json'
RESOURCE_AUDIT=RESOURCE.parent.parent/'independent_02/results.json'
OLD205=ROOT/'stage209_evaluations/cone_feasibility_campaign_20260930/old_terminal_accounting_01/results.json'
OLD205_AUDIT=OLD205.parent.parent/'old_accounting_independent_01/results.json'
OLD209=ROOT/'stage211_evaluations/terminal_accounting_20261001/independent_01/results.json'
job=ModuleType('_stage219_isolated_original_campaign');job.__dict__.update(vars(stack.job))
for name,f in list(vars(stack.job).items()):
    if inspect.isfunction(f) and f.__globals__ is vars(stack.job):setattr(job,name,FunctionType(f.__code__,vars(job),f.__name__,f.__defaults__,f.__closure__))
job.ROOT=Path('D:/MATDEM_MICROPLASTIC');job.SELF=SELF;job.BASE=BASE
job.DESIGN=ROOT/'stage219_designs'/BASE/'design_01.json';job.WORK=job.DESIGN.with_name('authorization_01.json')
job.RUN=job.ROOT/'stage219_runs'/BASE/'run_01';job.OUT=ROOT/'stage219_evaluations'/BASE
job.PREFLIGHT=job.RUN.parent/'preflight_not_authorized'
execute=FunctionType(stack.execute.__code__,{**stack.execute.__globals__,'job':job,'WORK':job.WORK},'execute_segment',stack.execute.__defaults__,stack.execute.__closure__)
acknowledged=FunctionType(stack.acknowledged.__code__,{**stack.acknowledged.__globals__,'job':job},'acknowledged',stack.acknowledged.__defaults__,stack.acknowledged.__closure__)
inner=FunctionType(stack._kernel.__code__,{**stack._kernel.__globals__,'job':job,'WORK':job.WORK},'inner_kernel',stack._kernel.__defaults__,stack._kernel.__closure__)
kernel=FunctionType(stack.kernel.__code__,{**stack.kernel.__globals__,'_kernel':inner},'kernel',stack.kernel.__defaults__,stack.kernel.__closure__)
job.execute_segment=execute;job.acknowledged=acknowledged;job.kernel=SimpleNamespace(evaluate=kernel)
LIFECYCLE=('worker','auditor','supervise','evaluate','start_child','root_for','paths','audit_one','binding','stopping')
sealed=stack.sealed

def bindings():
    for name in LIFECYCLE:
        f=getattr(job,name);old=getattr(stack.job,name)
        api.require(f.__code__ is old.__code__ and f.__globals__ is vars(job),'exact isolated original lifecycle '+name)
    api.require(job.worker.__globals__['acknowledged'] is acknowledged and job.audit_one.__globals__['kernel'].evaluate is kernel,'actual qualified worker/auditor associations')
    api.require(execute.__code__ is stack.execute.__code__ and execute.__globals__['job'] is job and execute.__globals__['WORK']==job.WORK,'same executed numerical adapter with new immutable evidence contract')
    api.require(kernel.__code__ is stack.kernel.__code__ and kernel.__globals__['_kernel'] is inner
        and inner.__code__ is stack._kernel.__code__ and inner.__globals__['job'] is job and inner.__globals__['WORK']==job.WORK,'same complete independent operand/physical auditor')
    api.require(stack.job.DESIGN==QUAL_DESIGN and str(stack.old_job.DESIGN).find('stage209_designs')>=0,'old and qualification namespaces untouched')
    return dict(lifecycle_code_sha256={n:q.campaign.code_sha(getattr(job,n)) for n in LIFECYCLE},
        adapter_code_sha256=q.campaign.code_sha(execute),independent_kernel_code_sha256=q.campaign.code_sha(kernel),
        numerical_policy_source_sha256=api.sha(stack.local.policy_scope.policy.__file__),operand_scope_source_sha256=api.sha(stack.local.policy_scope.__file__),
        independent_gap_auditor_sha256=api.sha(stack.local.auditor.__file__),receipt_helper_sha256=api.sha(stack.frozen.stack.ack.__file__))

def inherited():
    n=sealed(QUAL_NUM);f=sealed(QUAL_FIX)
    api.require(api.sha(QUAL_NUM)=='d9cc0150e466d757e365338fa3cea7c338fe6c2f8b1d79e0307297646525f0c3' and not n['preflight_passed']
        and n['numerical_qualification_passed'] and n['failure_accounting_closed'] and n['saved_steps']==n['independently_physical_passing_steps']==17000,'explicit independently passing numerical evidence, failed preflight never promoted')
    api.require(api.sha(QUAL_FIX)=='50f2a2de99161ee3af40b4b70f2bc54fff9c505e15a40b1fd9ebd52843153d25' and f['passed']
        and f['complementary_full_stack_qualification_passed'] and f['stage216_failure_preserved'] and f['new_trajectory_steps']==0
        and f['total_saved_policy_qualification_steps']==27600,'independent complementary original drain/process gate')
    api.verify_mapping(n['inputs']);api.verify_mapping(f['inputs'])
    return dict(explicitly_reused_stage216_independently_passing_steps=17000,separate_previous_policy_saved_steps=10600,stage217_new_trajectory_steps=0,original_stage216_preflight_remains_failed=True)

def require_old_terminal_closure():
    a=sealed(OLD205);b=sealed(OLD205_AUDIT);c=sealed(OLD209)
    api.require(api.sha(OLD205)=='284917294d554eb60d0f9a83368f4c4caa443c515b2508f6e03a22297885ad15'
        and api.sha(OLD205_AUDIT)=='23b0d4a8293a2dc5a37e8fc071ff827fd62d976aa6d4d1558b0f582ec47c9149'
        and api.sha(OLD209)=='8aa737c3b2b2425d414c3a06e24c5efd6f7dad309718bfe2037b0f44585a67f2','existing old full independent closure seals')
    for r in (a,b,c):api.verify_mapping(r['inputs'])
    api.require(a['old_failed_run_fully_accounted'] and a['old_run_remains_failed'] and a['total_raw_records']==3100
        and a['producer_declared_saved_steps']==30631450 and a['independently_verified_steps']==30628462 and a['preserved_failed_saved_steps']==2988,'Stage205 failed-inclusive balance')
    api.require(c['full_failed_run_accounting_closed'] and c['independent_accounting_verified'] and not c['campaign_passed']
        and c['total_raw_records']==3319 and c['producer_declared_saved_steps']==32284748 and c['independently_verified_steps']==32284084
        and c['preserved_failed_saved_steps']==664 and c['failed_trace_is_labelled_derived'],'Stage209 failed-inclusive balance/derived trace')
    return dict(stage205_saved=30631450,stage205_rejected=2988,stage209_saved=32284748,stage209_rejected=664,old_campaigns_remain_failed=True)

def verify(d):
    qual=api.read(QUAL_DESIGN);w=api.read(job.WORK)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'new immutable production design')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    allowed={'stage','binding','sources','inputs','resource_scenario','provenance_transaction_hours_with_margin','provenance_bytes_with_margin','claim','qualification_inheritance','qualified_normal_gap_bindings','numerical_policy_contract_sha256','audit_source_sha256','production_authorized','agent_work_end_utc','simulation_cutoff_utc','final_audit_deadline_utc','guard'}
    api.require({k for k in set(d)|set(qual) if d.get(k)!=qual.get(k)}<=allowed,'only explicit policy/evidence/resource/clock/production amendments')
    for k in ('cases','numerical_gates','budget','preflight','minimum_gap_semantics','worker_logical_cpus','auditor_logical_cpu','maximum_unverified_segments_per_case','maximum_unverified_segments_total','poll_seconds','stop_reserve_seconds','fresh_start_required','physical_changes'):
        api.require(d[k]==qual[k],'original scientific/resource equality '+k)
    api.require(d['fresh_start_required'] and d['production_authorized'] and w['production_authorized'] and not d['physical_changes'],'all six fresh original initial states')
    r=sealed(RESOURCE);a=sealed(RESOURCE_AUDIT)
    api.require(r['resource_gate_passed'] and a['passed'] and a['independent_calculation_passed'] and a['resource_gate_passed'] and a['resource_result_sha256']==api.sha(RESOURCE),'independent measured fit')
    for k,v in [('simulation_cutoff_utc',a['proposed_simulation_cutoff_utc']),('final_audit_deadline_utc',a['proposed_final_audit_deadline_utc']),('agent_work_end_utc',a['proposed_final_audit_deadline_utc'])]:api.require(d[k]==w[k]==v,'independently justified explicit revised clock '+k)
    api.require(d['budget']['workers']==w['production_workers']==3 and d['maximum_unverified_segments_total']==w['maximum_outstanding_records']==6,'original producer/global-six bound')
    api.require(d['qualified_normal_gap_bindings']==bindings() and d['numerical_policy_contract_sha256']==api.sha(job.WORK)
        and d['audit_source_sha256']==api.sha(SELF),'actual new policy-contract and independent auditor identity')
    api.require(d['qualification_inheritance']==inherited(),'explicit qualified evidence reuse without old-pass fabrication')
    api.require(d['resource_scenario']==dict(r,hours_with_margin=r['production_hours_with_margin'],bytes_with_margin=r['storage_bytes_with_margin']),'exact original-margin resource scenario')
    api.require(all(d['sources'].get(p)==h for p,h in qual['sources'].items()) and all(d['inputs'].get(p)==h for p,h in qual['inputs'].items()),'all qualification/old immutable lineage retained')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    stack.storage.verify_bindings();stack.affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])
job.verify=verify

def verify_preflight(d):
    verify(d);i=inherited();b=sealed(job.OUT/'independent_bridge_01/results.json')
    api.require(b['passed'] and b['design_sha256']==api.sha(job.DESIGN),'new independent launch bridge')
    return dict(i,refreshed_hours_with_margin=sealed(RESOURCE)['production_hours_with_margin'])
job.verify_preflight=verify_preflight

def resource_gate(d):
    verify(d);r=sealed(RESOURCE);a=sealed(RESOURCE_AUDIT)
    available=(job.policy.utc(d['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600;reserve=(job.policy.utc(d['final_audit_deadline_utc'])-job.policy.utc(d['simulation_cutoff_utc'])).total_seconds()/3600
    free=shutil.disk_usage(job.ROOT).free;need=r['storage_bytes_with_margin']+d['budget']['minimum_free_disk_bytes']
    api.require(available>=r['production_hours_with_margin'] and reserve>=r['required_final_audit_hours'] and free>=need and r['call_limit_passed'],'current time/audit/disk/call fit')
    return dict(required_hours=r['production_hours_with_margin'],available_hours=available,required_audit_hours=r['required_final_audit_hours'],reserved_audit_hours=reserve,storage_with_reserve_bytes=need,free_D_bytes=free)

def active_owned():return stack.frozen.active_owned(False)

def prepare():
    inherited();old=require_old_terminal_closure();api.require(not active_owned(),'no competing workspace simulation/evaluation')
    api.require(not job.DESIGN.exists() and not job.RUN.exists(),'exclusive new production design/run')
    w=api.read(job.WORK);r=sealed(RESOURCE);d=copy.deepcopy(api.read(QUAL_DESIGN));d.pop('binding')
    paths=[job.WORK,QUAL_DESIGN,QUAL_NUM,QUAL_NUM.parent/'completion.json',QUAL_FIX,QUAL_FIX.parent/'completion.json',RESOURCE,RESOURCE.parent/'completion.json',RESOURCE_AUDIT,RESOURCE_AUDIT.parent/'completion.json',OLD205,OLD205_AUDIT,OLD209]
    files=list(SELF.parent.glob('*.py'))+list((ROOT/'stage218_staging').glob('*.py'))
    d.update(stage='Stage219 fresh original six-case fixed numerical-gap policy campaign',production_authorized=True,
        sources={**d['sources'],**{str(p):api.sha(p) for p in files}},inputs={**d['inputs'],**{str(p):api.sha(p) for p in paths}},
        simulation_cutoff_utc=w['simulation_cutoff_utc'],final_audit_deadline_utc=w['final_audit_deadline_utc'],agent_work_end_utc=w['agent_work_end_utc'],
        resource_scenario=dict(r,hours_with_margin=r['production_hours_with_margin'],bytes_with_margin=r['storage_bytes_with_margin']),
        provenance_transaction_hours_with_margin=r['production_hours_with_margin'],provenance_bytes_with_margin=r['storage_bytes_with_margin'],
        audit_source_sha256=api.sha(SELF),qualified_normal_gap_bindings=bindings(),numerical_policy_contract_sha256=api.sha(job.WORK),qualification_inheritance=inherited(),
        guard='Fresh original six initial states; approved fixed sphere solver-gap operands only, explicit raw/effective provenance. Full old failure closures remain failed and mandatory. No restart/overwrite/gate relaxation/new physics.',
        claim='All six full observations and unchanged full-path selected/fine common-clock gates required; placements0/124 separate. No population release or empirical validation.')
    d['binding']=api.digest(d);verify(d);fit=resource_gate(d);job.commit(job.DESIGN,d)
    out=job.OUT/'preparation_binding_01';result=dict(passed=True,new_trajectory_steps=0,design_sha256=api.sha(job.DESIGN),qualified_bindings=bindings(),resource_fit=fit,old_failure_balance=old)
    job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')))
    print('NORMAL_GAP_CAMPAIGN_PREPARED',api.sha(job.DESIGN),fit,flush=True)

def owned(name=None):
    d=api.read(job.DESIGN);verify(d);cpu=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=stack.affinity.bind(cpu);job.commit(job.RUN/((name or 'auditor')+'.affinity.json'),dict(info,design_sha256=api.sha(job.DESIGN),argv=sys.argv,utc=job.utc().isoformat(),created=psutil.Process().create_time()))

if __name__=='__main__':
    args=sys.argv[1:]
    if args==['prepare']:prepare()
    elif args==['check']:print(resource_gate(api.read(job.DESIGN)),flush=True)
    elif args==['supervise','campaign']:
        d=api.read(job.DESIGN);resource_gate(d);verify_preflight(d);require_old_terminal_closure();api.require(not active_owned(),'no competing simulation or evaluator');job.supervise('campaign')
    elif len(args)==3 and args[:2]==['worker','campaign']:owned(args[2]);job.worker('campaign',args[2])
    elif args==['auditor','campaign']:owned();job.auditor('campaign')
    elif args==['evaluate','campaign']:require_old_terminal_closure();job.evaluate('campaign')
    else:raise ValueError('prepare | check | supervise campaign | worker campaign CASE | auditor campaign | evaluate campaign')
