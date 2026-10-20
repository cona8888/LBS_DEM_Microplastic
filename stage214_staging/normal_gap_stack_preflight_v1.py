"""Isolated fresh lifecycle with approved gap operands; no old namespace edits."""
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
import copy, inspect, os, shutil, sys
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage213_staging'))
import bounded_normal_gap_trajectory_v1 as local
api=local.api;frozen=local.frozen;old_job=local.job
storage,affinity,candidate=frozen.stack.storage,frozen.stack.affinity,frozen.stack.candidate
BASE='normal_gap_stack_20261001'
WORK=ROOT/'stage214_designs'/BASE/'contract_01.json'
OLD_DESIGN=ROOT/'stage208_designs/cone_feasibility_stack_20260930/design_01.json'
CLOSE=local.EVALBASE/'local_qualification_close_01/results.json'
LOCAL_AUDIT=local.EVALBASE/'serial_split_independent_01/results.json'
SELF=Path(__file__).resolve()
job=ModuleType('_stage214_isolated_qualified_lifecycle')
job.__dict__.update(old_job.__dict__)
for name,fn in list(vars(old_job).items()):
    if inspect.isfunction(fn) and fn.__globals__ is vars(old_job):
        job.__dict__[name]=FunctionType(fn.__code__,job.__dict__,fn.__name__,fn.__defaults__,fn.__closure__)
job.ROOT=ROOT;job.SELF=SELF;job.BASE=BASE;job.WORK=WORK
job.DESIGN=ROOT/'stage214_designs'/BASE/'design_01.json'
job.PREFLIGHT=ROOT/'stage214_runs'/BASE/'preflight_01'
job.RUN=ROOT/'stage214_runs'/BASE/'production_not_authorized'
job.OUT=ROOT/'stage214_evaluations'/BASE
job.PREFLIGHT_SCRIPT=SELF.with_name('qualify_normal_gap_stack_v1.py')
q=SimpleNamespace(**vars(frozen.q))
old_independent=q.independent_file


def sealed(path):return local.sealed(Path(path))


def local_record(path,design_sha,*args,**kwargs):
    path=Path(path)
    if path not in (local.RUNBASE/'split_a_01/call.json.xz',local.RUNBASE/'split_b_01/call.json.xz'):
        return old_independent(path,design_sha,*args,**kwargs)
    api.require(design_sha==api.sha(old_job.DESIGN),'diagnostic seed lineage design only')
    codec=storage.codec;prefix=local.prefix(local.RECON,32)
    for name in ('split_a_01','split_b_01'):
        folder=local.RUNBASE/name;r=sealed(folder/'results.json')
        api.require(r['numerical_audit_passed'] and r['rejected']==0,'independently accepted new-policy oracle')
        api.verify_mapping(r['artifacts'])
        rec,prefix=codec.read_record(folder/'call.json.xz',design_sha,prefix)
        api.require(rec['numerical_policy_contract_sha256']==api.sha(local.WORK),'explicit oracle policy contract')
        if path==folder/'call.json.xz':return rec
    raise AssertionError('diagnostic oracle inventory')
q.independent_file=local_record


def kernel(record,spec,binding,before,geometry,design_sha256,gap_semantics):
    api.require(design_sha256==api.sha(job.DESIGN) and record['numerical_policy_contract_sha256']==api.sha(WORK),'exact new design and numerical-policy contract')
    api.require(record['fresh_stack_policy_contract_not_old_raw_gap_acceptance'] is True,'explicit revised-policy fresh record')
    return local.auditor.kernel(record,spec,binding,before,geometry,design_sha256,gap_semantics)
job.kernel=SimpleNamespace(evaluate=kernel)


def acknowledged(d,pending):return frozen.stack.ack.acknowledged(api,job.policy,job.DESIGN,d,pending)
job.acknowledged=acknowledged


def execute_segment(d,case,before,path,cap,prefix,stop):
    codec=job.codec;original_write=codec.write_record
    with local.policy_scope.scope(cap+31) as log:
        def write_record(raw,record,parent):
            record['normal_gap_operand_policy']=copy.deepcopy(log)
            record['numerical_policy_contract_sha256']=api.sha(WORK)
            record['fresh_stack_policy_contract_not_old_raw_gap_acceptance']=True
            return original_write(raw,record,parent)
        proxy=SimpleNamespace(**vars(codec));proxy.write_record=write_record
        raw=FunctionType(frozen.raw_execute.__code__,{**job.__dict__,'codec':proxy},'execute_segment',frozen.raw_execute.__defaults__,frozen.raw_execute.__closure__)
        outer=FunctionType(frozen.execute.__code__,{**frozen.execute.__globals__,'job':job,'raw_execute':raw},'execute_segment',frozen.execute.__defaults__,frozen.execute.__closure__)
        api.require(raw.__code__ is frozen.raw_execute.__code__ and outer.__code__ is frozen.execute.__code__,'unchanged integration/solver scope bytecode')
        for key in ('parent','fast','prior','deadline','capture','observer'):
            api.require(raw.__globals__[key] is frozen.raw_execute.__globals__[key],'unchanged physics dependency '+key)
        return outer(d,case,before,path,cap,prefix,stop)
job.execute_segment=execute_segment


def bindings():
    names=('worker','auditor','supervise','evaluate','start_child','root_for','paths','audit_one','binding','stopping')
    for name in names:
        api.require(getattr(job,name).__code__ is getattr(old_job,name).__code__ and getattr(job,name).__globals__ is vars(job),'isolated unchanged lifecycle '+name)
    api.require(job.worker.__globals__['acknowledged'] is acknowledged and job.audit_one.__globals__['kernel'].evaluate is kernel,'actual producer/auditor policy association')
    api.require(old_job.DESIGN==local.job.DESIGN and str(old_job.DESIGN).find('stage209_designs')>=0,'old campaign namespace stays untouched')
    return dict(lifecycle_code_sha256={n:q.campaign.code_sha(getattr(job,n)) for n in names},
                integration_code_sha256=q.campaign.code_sha(frozen.raw_execute),solver_scope_code_sha256=q.campaign.code_sha(frozen.execute),
                numerical_policy_source_sha256=api.sha(local.policy_scope.policy.__file__),
                operand_scope_source_sha256=api.sha(local.policy_scope.__file__),independent_gap_auditor_sha256=api.sha(local.auditor.__file__))


def ledger():
    r=sealed(CLOSE)
    api.require(api.sha(CLOSE)=='03e1eb984b786b110acb59fd1f31d04be52c6f4cb8c5e87020a1b8ba494508c7'
        and r['local_numerical_qualification_passed'] and r['launched_qualification_accounting_closed']
        and r['all_owned_diagnostics_retired'],'independent closed local policy qualification')
    api.require(r['saved_new_trajectory_steps']==r['independently_accepted_new_trajectory_steps']==4000
        and r['failed_or_rejected_new_saved_steps']==0,'separate prior saved/accepted ledger')
    api.verify_mapping(r['inputs']);a=sealed(LOCAL_AUDIT)
    api.require(api.sha(LOCAL_AUDIT)=='0a403408fe3dc7f02216da42b1ade40b56615ec71a4123b039ba50f059852087' and a['passed'],'fresh independent local replay')
    api.require(not job.PREFLIGHT.exists(),'new exclusive stack, never restart')


def no_competing_trajectory():
    api.require(not frozen.active_owned(False),'no competing workspace simulation or evaluation')


def verify(d):
    old=api.read(OLD_DESIGN);w=api.read(WORK)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'immutable new design')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    allowed={'stage','binding','sources','inputs','agent_work_end_utc','simulation_cutoff_utc','final_audit_deadline_utc',
             'stress_case','stress_seed_raw','stress_seed_design','stress_oracle_raw','stress_oracle_design','audit_source_sha256','audit_structure','claim','qualified_normal_gap_bindings','numerical_policy_contract_sha256'}
    api.require({k for k in set(d)|set(old) if d.get(k)!=old.get(k)}<=allowed,'only explicit new policy/evidence/clock verification fields')
    for k in ('cases','numerical_gates','budget','preflight','minimum_gap_semantics','worker_logical_cpus','auditor_logical_cpu','maximum_unverified_segments_total','maximum_unverified_segments_per_case'):
        api.require(d[k]==old[k],'unchanged original scientific/resource field '+k)
    api.require(d['numerical_gates']==job.policy.GATES and not d['production_authorized'] and not d['physical_changes'],'original gates/physics; no production')
    api.require(d['preflight']['maximum_new_steps']==w['maximum_new_saved_steps']==w['maximum_new_qualification_accepted_steps']==17000,'separate bounded full-stack ledger')
    api.require(17000+w['prior_stage213_saved_and_independently_accepted_steps']<=w['maximum_combined_policy_qualification_saved_steps']==50000,'inclusive disclosed policy verification ledger')
    api.require(d['budget']['workers']==w['live_pipeline_workers']==3 and d['maximum_unverified_segments_total']==w['maximum_outstanding_records']==6,'original live bound')
    api.require(w['maximum_separately_frozen_parallel_preflight_workers']==6,'original isolated parallel qualification')
    api.require(d['agent_work_end_utc']==w['work_end_utc'] and d['simulation_cutoff_utc']==w['simulation_cutoff_utc'] and d['final_audit_deadline_utc']==w['final_audit_deadline_utc'],'qualification/production/audit clocks distinct')
    api.require(d['stress_case']=='s2_i124_sphere_f0p0625' and d['stress_seed_raw']==str(local.RUNBASE/'split_a_01/call.json.xz') and d['stress_oracle_raw']==str(local.RUNBASE/'split_b_01/call.json.xz'),'new policy failure-crossing accepted seed/oracle')
    api.require(d['stress_seed_design']==d['stress_oracle_design']==str(old_job.DESIGN),'old design is diagnostic lineage only')
    api.require(d['audit_source_sha256']==api.sha(SELF) and d['audit_structure']==dict(independent_gap_auditor=local.auditor.NAME,original_physical_gates_changed=0,explicit_new_gap_contract=True),'full policy-contract checking audit identity')
    api.require(d['qualified_normal_gap_bindings']==bindings() and d['numerical_policy_contract_sha256']==api.sha(WORK),'exact new numerical bindings')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    storage.verify_bindings();affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])
job.verify=verify
# Restore the original local preflight verifier, not the Stage209 production bridge.
# All inherited lifecycle verifiers use this same unchanged original bytecode;
# select it directly from its on-disk lifecycle module, without rerunning it.
import importlib.util
spec=importlib.util.spec_from_file_location('_stage214_original_lifecycle_reference',old_job.__file__)
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
fn=reference.verify_preflight
job.verify_preflight=FunctionType(fn.__code__,job.__dict__,fn.__name__,fn.__defaults__,fn.__closure__)


def prepare():
    w=api.read(WORK);api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc']),'bounded preparation clock')
    ledger();no_competing_trajectory();api.require(shutil.disk_usage(ROOT).free>w['minimum_free_disk_bytes'],'20GiB reserve')
    api.require(not job.DESIGN.exists() and not job.RUN.exists(),'fresh design/no production')
    d=copy.deepcopy(api.read(OLD_DESIGN));d.pop('binding')
    files=list(SELF.parent.glob('*.py'))+[Path(local.policy_scope.__file__),Path(local.policy_scope.policy.__file__),Path(local.auditor.__file__)]
    inputs=[WORK,OLD_DESIGN,CLOSE,CLOSE.parent/'completion.json',LOCAL_AUDIT,LOCAL_AUDIT.parent/'completion.json',local.WORK,old_job.DESIGN]
    inputs+=list(local.RECON.glob('*.json'))
    inputs+=[local.RUNBASE/n/f for n in ('split_a_01','split_b_01') for f in ('results.json','completion.json','checkpoint.json','prefix.json','history.json','call.json.xz','call.json.seal.json')]
    d.update(stage='Stage214 explicitly revised normal-gap bounded full-stack qualification',
        sources={**d['sources'],**{str(p):api.sha(p) for p in files}},inputs={**d['inputs'],**{str(p):api.sha(p) for p in inputs}},
        agent_work_end_utc=w['work_end_utc'],simulation_cutoff_utc=w['simulation_cutoff_utc'],final_audit_deadline_utc=w['final_audit_deadline_utc'],
        stress_case='s2_i124_sphere_f0p0625',stress_seed_raw=str(local.RUNBASE/'split_a_01/call.json.xz'),stress_seed_design=str(old_job.DESIGN),
        stress_oracle_raw=str(local.RUNBASE/'split_b_01/call.json.xz'),stress_oracle_design=str(old_job.DESIGN),
        audit_source_sha256=api.sha(SELF),audit_structure=dict(independent_gap_auditor=local.auditor.NAME,original_physical_gates_changed=0,explicit_new_gap_contract=True),
        qualified_normal_gap_bindings=bindings(),numerical_policy_contract_sha256=api.sha(WORK),
        claim='Explicit new sphere solver-gap numerical contract; original raw contact membership and physical gates. Stage205/209 stay failed/incomplete. Bounded qualification only, not production/full-horizon completion/population release/empirical validation.')
    d['binding']=api.digest(d);verify(d);job.commit(job.DESIGN,d);print('NORMAL_GAP_STACK_DESIGN',api.sha(job.DESIGN),flush=True)


def owned(mode,name=None):
    api.require(mode=='preflight','production disabled');d=api.read(job.DESIGN);verify(d)
    cpu=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=affinity.bind(cpu);p=psutil.Process()
    job.commit(job.root_for(mode)/((name or 'auditor')+'.affinity.json'),dict(info,design_sha256=api.sha(job.DESIGN),argv=p.cmdline(),pid=p.pid,created=p.create_time(),utc=job.utc().isoformat()))


if __name__=='__main__':
    args=sys.argv[1:]
    if args==['prepare']:prepare()
    elif len(args)==3 and args[:2]==['worker','preflight']:owned(args[1],args[2]);job.worker(args[1],args[2])
    elif args==['auditor','preflight']:owned(args[1]);job.auditor(args[1])
    elif args==['evaluate','preflight']:job.evaluate(args[1])
    else:raise ValueError('new bounded preflight only')
