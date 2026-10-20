"""Fresh six-case campaign using the independently qualified Stage208 stack."""
from pathlib import Path
from types import FunctionType
import copy,os,sys,shutil,psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage208_staging'))
import cone_feasibility_stack_preflight_v1 as stack
api,job,q=stack.api,stack.job,stack.q
BASE='cone_feasibility_campaign_20260930'
QUAL_DESIGN=job.DESIGN
QUAL_OUT=job.OUT
OLD_DESIGN=ROOT/'stage205_designs/receipt_repaired_campaign_20260930/design_01.json'
OLD_RUN=Path('D:/MATDEM_MICROPLASTIC/stage205_runs/receipt_repaired_campaign_20260930/run_01')
OLD_OUT=ROOT/'stage205_evaluations/receipt_repaired_campaign_20260930'
RESOURCE=QUAL_OUT/'resource_schedule_01/results.json'
RESOURCE_AUDIT=QUAL_OUT/'resource_independent_01/results.json'
QUAL_CLOSE=QUAL_OUT/'qualification_close_01/results.json'
OLD_TERMINAL_PROOF=ROOT/'stage209_evaluations'/BASE/'old_terminal_accounting_01/results.json'
OLD_LAUNCH_PROOF=ROOT/'stage209_evaluations'/BASE/'old_audit_launch_disposition_01/results.json'
job.ROOT=Path('D:/MATDEM_MICROPLASTIC');job.SELF=Path(__file__).resolve();job.BASE=BASE
job.DESIGN=ROOT/'stage209_designs'/BASE/'design_01.json'
job.WORK=ROOT/'stage209_designs'/BASE/'authorization_01.json'
job.RUN=job.ROOT/'stage209_runs'/BASE/'run_01'
job.OUT=ROOT/'stage209_evaluations'/BASE
job.PREFLIGHT=job.RUN.parent/'not_authorized'
raw_execute=FunctionType(stack.raw_execute.__code__,dict(job.__dict__),'execute_segment',stack.raw_execute.__defaults__,stack.raw_execute.__closure__)
execute=FunctionType(stack.job.execute_segment.__code__,dict(stack.job.execute_segment.__globals__,raw_execute=raw_execute),'execute_segment',stack.job.execute_segment.__defaults__,stack.job.execute_segment.__closure__)
job.execute_segment=execute

def sealed(path):return stack.sealed(path)

def bindings():
    api.require(execute.__globals__['repair'] is stack.repair and execute.__globals__['raw_execute'] is raw_execute,'exact qualified numerical wrapper binding')
    api.require(execute.__code__ is stack.previous.execute_segment.__code__ and raw_execute.__code__ is stack.previous.raw_execute.__code__,'unchanged integration/scope bytecode')
    api.require(raw_execute.__globals__['DESIGN']==job.DESIGN and raw_execute.__globals__['codec'] is job.codec,'fresh evidence binding')
    for k in ('parent','fast','prior','deadline','capture','observer'):
        api.require(raw_execute.__globals__[k] is stack.previous.raw_execute.__globals__[k],'unchanged physics namespace '+k)
    api.require(job.worker.__globals__ is job.__dict__ and job.worker.__globals__['acknowledged'] is stack.acknowledged,'qualified real producer receipt adapter')
    api.require(job.kernel.evaluate is stack.auditor.kernel and stack.repair.bound.__globals__['solve'] is stack.repair.solve,'qualified independent audit/solver associations')
    return dict(integration_code_sha256=q.campaign.code_sha(raw_execute),scope_code_sha256=q.campaign.code_sha(execute),candidate_sha256=api.sha(stack.repair.__file__),auditor_sha256=api.sha(stack.auditor.__file__),receipt_helper_sha256=api.sha(stack.ack.__file__),lifecycle_code_sha256={n:q.campaign.code_sha(getattr(job,n)) for n in ('worker','auditor','supervise','evaluate','start_child','root_for','paths')})

def inherited():
    closed=sealed(QUAL_CLOSE); pf=sealed(QUAL_OUT/'preflight_01/results.json');audit=sealed(QUAL_OUT/'independent_readiness_01/results.json')
    api.require(closed['qualification_closed'] and closed['numerical_qualification_passed'] and closed['process_qualification_passed'] and closed['resource_gate_passed'],'fresh closed qualification')
    api.require(pf['new_steps']==audit['stage208_preflight_steps_verified']==closed['separate_stage208_saved_and_independently_passing_steps']==17000,'exact fresh full-stack ledger')
    api.require(closed['separate_stage207_saved_and_independently_passing_steps']==22456 and not closed['unresolved_reservations'],'separate diagnostic ledger disclosed')
    api.verify_mapping(closed['inputs']);api.verify_mapping(pf['artifacts']);api.verify_mapping(pf['sources'])
    return pf

def verify(d):
    old=api.read(OLD_DESIGN);qual=api.read(QUAL_DESIGN);w=api.read(job.WORK)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'fresh immutable design')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    allowed={'stage','binding','sources','inputs','resource_scenario','provenance_transaction_hours_with_margin','provenance_bytes_with_margin','guard','claim','qualification_inheritance','audit_source_sha256','audit_structure','qualified_numerical_bindings','qualified_full_stack_design_sha256','old_audit_launch_disposition_sha256'}
    api.require({k for k in set(d)|set(old) if d.get(k)!=old.get(k)}<=allowed,'only explicit qualified numerical/evidence/resource amendments')
    for k in ('cases','numerical_gates','budget','preflight','minimum_gap_semantics','worker_logical_cpus','auditor_logical_cpu','maximum_unverified_segments_per_case','maximum_unverified_segments_total','poll_seconds','stop_reserve_seconds'):
        api.require(d[k]==old[k]==qual[k],'original science and resource caps '+k)
    api.require(d['fresh_start_required'] and d['production_authorized'] and not d['physical_changes'],'fresh original physics only')
    for k in ('simulation_cutoff_utc','final_audit_deadline_utc','agent_work_end_utc'):api.require(d[k]==w[k],'unchanged approved calendar '+k)
    api.require(d['budget']['workers']==w['production_workers']==3 and d['maximum_unverified_segments_total']==w['maximum_outstanding_records']==6,'original concurrency/backlog')
    api.require(all(d['sources'].get(p)==h for p,h in old['sources'].items()) and all(d['inputs'].get(p)==h for p,h in old['inputs'].items()),'all old immutable lineage retained')
    api.require(d['qualified_numerical_bindings']==bindings() and d['qualified_full_stack_design_sha256']==api.sha(QUAL_DESIGN),'exact qualified full stack')
    api.require(d['audit_source_sha256']==api.sha(stack.auditor.__file__) and d['audit_structure']==stack.auditor.STRUCTURAL_IDENTITY,'new association only, original independent gates')
    api.require(d['sources'][str(job.SELF)]==api.sha(job.SELF) and d['inputs'][str(job.WORK)]==api.sha(job.WORK),'new launcher/authority sealed')
    resource=sealed(RESOURCE)
    api.require(d['resource_scenario']==dict(resource,hours_with_margin=resource['production_hours_with_margin'],bytes_with_margin=resource['storage_bytes_with_margin']) and d['old_audit_launch_disposition_sha256']==api.sha(OLD_LAUNCH_PROOF),'resource/pending-failure-accounting anchors')
    verify_old_disposition()
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
job.verify=verify

def verify_preflight(d):
    verify(d);pf=inherited();bridge=sealed(job.OUT/'independent_bridge_01/results.json')
    api.require(bridge['passed'] and bridge['design_sha256']==api.sha(job.DESIGN),'independent fresh launch bridge')
    return dict(pf,refreshed_hours_with_margin=sealed(RESOURCE)['production_hours_with_margin'])
job.verify_preflight=verify_preflight

def resource_gate(d):
    verify(d);r=sealed(RESOURCE);a=sealed(RESOURCE_AUDIT)
    api.require(r['resource_gate_passed'] and a['independent_calculation_passed'] and a['resource_gate_passed'] and a['resource_result_sha256']==api.sha(RESOURCE),'fresh independent measured resource fit')
    available=(job.policy.utc(d['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    reserve=(job.policy.utc(d['final_audit_deadline_utc'])-job.policy.utc(d['simulation_cutoff_utc'])).total_seconds()/3600
    free=shutil.disk_usage(job.ROOT).free;need=r['storage_bytes_with_margin']+d['budget']['minimum_free_disk_bytes']
    api.require(available>=r['production_hours_with_margin'] and reserve>=r['required_final_audit_hours'] and free>=need and r['call_limit_passed'],'current measured time/audit/disk/call fit')
    return dict(required_hours=r['production_hours_with_margin'],available_hours=available,required_audit_hours=r['required_final_audit_hours'],reserved_audit_hours=reserve,required_storage_with_reserve_bytes=need,free_D_bytes=free)

def verify_old_disposition():
    proof=sealed(OLD_LAUNCH_PROOF);api.verify_mapping(proof['inputs'])
    api.require(proof['old_run_remains_failed'] and not proof['old_failed_run_fully_accounted'] and proof['full_old_accounting_required_before_final_acceptance'],'pending old audit disclosed, not promoted')
    api.require(proof['new_trajectory_steps']==0 and proof['fresh_old_observations_reused']==0 and len(proof['allowed_read_only_processes'])==2,'only independently qualified fresh trajectories')
    api.require(proof['stage208_qualification_sha256']==api.sha(QUAL_CLOSE),'measured coexistence qualification bound')
    return proof

def allowed_old_identity(info,allowed):
    return any(x['pid']==info['pid'] and x['argv']==info['argv'] and abs(x['created']-info['created'])<.001 and api.sha(x['source_path'])==x['source_sha256'] for x in allowed)

def active_owned(allow_old_read_only=True):
    live=[]
    allowed=verify_old_disposition()['allowed_read_only_processes'] if allow_old_read_only else []
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:
            argv=p.cmdline()
            scripts=[x for x in argv if x.lower().endswith('.py') and (ROOT/x).resolve().is_relative_to(ROOT)]
            if scripts:
                info=dict(pid=p.pid,argv=argv,created=p.create_time())
                if not allowed_old_identity(info,allowed):live.append(info)
        except psutil.NoSuchProcess:continue
    return live

def prepare():
    inherited();proof=verify_old_disposition()
    api.require(not active_owned(),'only exact old read-only audit may coexist; no existing simulation')
    api.require(not job.DESIGN.exists() and not job.RUN.exists(),'fresh exclusive campaign')
    d=copy.deepcopy(api.read(OLD_DESIGN));d.pop('binding');qual=api.read(QUAL_DESIGN);r=sealed(RESOURCE)
    files=list(Path(__file__).parent.glob('*.py'))+list((ROOT/'stage208_staging').glob('*.py'))
    inputs=[job.WORK,QUAL_DESIGN,QUAL_CLOSE,QUAL_CLOSE.parent/'completion.json',RESOURCE,RESOURCE.parent/'completion.json',RESOURCE_AUDIT,RESOURCE_AUDIT.parent/'completion.json',OLD_LAUNCH_PROOF,OLD_LAUNCH_PROOF.parent/'completion.json']
    d.update(stage='Stage209 fresh original six-case qualified cone-feasibility campaign',sources={**d['sources'],**qual['sources'],**{str(p):api.sha(p) for p in files}},inputs={**d['inputs'],**qual['inputs'],**{str(p):api.sha(p) for p in inputs}},resource_scenario=dict(r,hours_with_margin=r['production_hours_with_margin'],bytes_with_margin=r['storage_bytes_with_margin']),provenance_transaction_hours_with_margin=r['production_hours_with_margin'],provenance_bytes_with_margin=r['storage_bytes_with_margin'],audit_source_sha256=api.sha(stack.auditor.__file__),audit_structure=stack.auditor.STRUCTURAL_IDENTITY,qualified_numerical_bindings=bindings(),qualified_full_stack_design_sha256=api.sha(QUAL_DESIGN),old_audit_launch_disposition_sha256=api.sha(OLD_LAUNCH_PROOF),qualification_inheritance=dict(new_stage208_full_stack_steps=17000,separate_stage207_local_steps=22456,stage205_failed_evidence_preserved=True,manufactured_root_nonuniqueness_disclosed=True),guard='Fresh original initial states only. Qualified new numerical trial-force feasibility route and unchanged original finalizer; all physical/timestep/horizon/scientific gates retained. Pending old failed-run full audit remains mandatory before final acceptance.',claim='Two labelled placements separately; all six observations and fresh full-path selected/fine gates required. No population release or empirical validation.')
    d['binding']=api.digest(d);verify(d);fit=resource_gate(d);job.commit(job.DESIGN,d)
    out=job.OUT/'preparation_binding_01';result=dict(passed=True,new_trajectory_steps=0,design_sha256=api.sha(job.DESIGN),qualified_bindings=bindings(),resource_fit_at_preparation=fit,source_sha256=api.sha(__file__))
    job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')));print('CONE_CAMPAIGN_PREPARED',api.sha(job.DESIGN),fit,flush=True)

def owned(name=None):
    d=api.read(job.DESIGN);verify(d);core=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=stack.affinity.bind(core);job.commit(job.RUN/((name or 'auditor')+'.affinity.json'),dict(info,design_sha256=api.sha(job.DESIGN),argv=sys.argv,utc=job.utc().isoformat()))

def require_old_terminal_closure():
    proof=sealed(OLD_TERMINAL_PROOF);api.verify_mapping(proof['inputs'])
    api.require(proof['old_failed_run_fully_accounted'] and proof['old_run_remains_failed'] and proof['failed_raw_history_trace_authenticated'],'old failed-run final accounting independently closed')
    api.require(proof['total_raw_records']==3100 and proof['producer_declared_saved_steps']==30631450 and proof['independently_verified_steps']==30628462 and proof['preserved_failed_saved_steps']==2988,'old exact saved/passing/failed ledger')
    old_scripts={str(ROOT/'stage205_staging/receipt_repaired_campaign_v2.py'),str(ROOT/'stage205_staging/run_terminal_evaluator_v1.py')}
    for process in psutil.process_iter(['name']):
        if process.pid==os.getpid() or 'python' not in (process.info['name'] or '').lower():continue
        try:api.require(not old_scripts.intersection(process.cmdline()),'old terminal audit/witness retired before final audit')
        except psutil.NoSuchProcess:continue
    return proof

if __name__=='__main__':
    args=sys.argv[1:]
    if args==['prepare']:prepare()
    elif args==['check']:print(resource_gate(api.read(job.DESIGN)),flush=True)
    elif args==['supervise','campaign']:
        d=api.read(job.DESIGN);resource_gate(d);verify_preflight(d);api.require(not active_owned(),'no competing simulation/evaluator');job.supervise('campaign')
    elif len(args)==3 and args[:2]==['worker','campaign']:owned(args[2]);job.worker('campaign',args[2])
    elif args==['auditor','campaign']:owned();job.auditor('campaign')
    elif args==['evaluate','campaign']:require_old_terminal_closure();job.evaluate('campaign')
    else:raise ValueError('prepare | check | supervise campaign | worker campaign CASE | auditor campaign | evaluate campaign')
