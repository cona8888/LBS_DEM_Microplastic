"""Fresh unchanged stack; explicit independently qualified sphere comparators."""
from pathlib import Path
from types import FunctionType,ModuleType,SimpleNamespace
from fractions import Fraction
import copy,inspect,math,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage214_staging'),str(ROOT/'stage215_staging')]
import normal_gap_stack_preflight_v1 as base
import bounded_policy_references_v1 as refs
api,storage,affinity,candidate=base.api,base.storage,base.affinity,base.candidate
local,old_job,frozen=base.local,base.old_job,base.frozen
BASE='same_policy_stack_20261001';SELF=Path(__file__).resolve()
WORK=ROOT/'stage216_designs'/BASE/'contract_01.json'
REFERENCE=refs.OUT/'independent_01/results.json'
job=ModuleType('_stage216_same_policy_lifecycle');job.__dict__.update(vars(base.job))
for name,fn in list(vars(base.job).items()):
    if inspect.isfunction(fn) and fn.__globals__ is vars(base.job):
        setattr(job,name,FunctionType(fn.__code__,vars(job),fn.__name__,fn.__defaults__,fn.__closure__))
job.ROOT=ROOT;job.SELF=SELF;job.BASE=BASE;job.WORK=WORK
job.DESIGN=ROOT/'stage216_designs'/BASE/'design_01.json'
job.PREFLIGHT=ROOT/'stage216_runs'/BASE/'preflight_01'
job.RUN=ROOT/'stage216_runs'/BASE/'production_not_authorized'
job.OUT=ROOT/'stage216_evaluations'/BASE
job.PREFLIGHT_SCRIPT=SELF.with_name('qualify_same_policy_stack_v1.py')
q=SimpleNamespace(**vars(base.q))
sealed=base.sealed;no_competing_trajectory=base.no_competing_trajectory
acknowledged=FunctionType(base.acknowledged.__code__,{**base.acknowledged.__globals__,'job':job},'acknowledged',base.acknowledged.__defaults__,base.acknowledged.__closure__)
job.acknowledged=acknowledged
execute=FunctionType(base.execute_segment.__code__,{**base.execute_segment.__globals__,'job':job,'WORK':WORK},'execute_segment',base.execute_segment.__defaults__,base.execute_segment.__closure__)
job.execute_segment=execute
_kernel=FunctionType(base.kernel.__code__,{**base.kernel.__globals__,'job':job,'WORK':WORK},'kernel',base.kernel.__defaults__,base.kernel.__closure__)


def kernel(record,spec,binding,before,geometry,design_sha256,gap_semantics):
    for call in record['normal_gap_operand_policy']['prepare_calls']:
        for item in call['metadata']:
            c=item['context'];m=item['classification']
            if c['a']==c['b']:
                value=sum((abs(Fraction.from_float(float(z))) for z in [*c['x'],*c['c'],c['a'],c['r']]),Fraction(0))
                api.require(m['absolute_operand_scale_m']==math.nextafter(float(value),math.inf),'full independent operand scale declaration')
    return _kernel(record,spec,binding,before,geometry,design_sha256,gap_semantics)
job.kernel=SimpleNamespace(evaluate=kernel)
_bindings=FunctionType(base.bindings.__code__,{**base.bindings.__globals__,'job':job,'kernel':kernel,'acknowledged':acknowledged},'bindings',base.bindings.__defaults__,base.bindings.__closure__)


def bindings():return dict(_bindings(),independent_sphere_reference_sha256=api.sha(REFERENCE),independent_sphere_reference_design_sha256=api.sha(refs.DESIGN))
_verify=FunctionType(base.verify.__code__,{**base.verify.__globals__,'job':job,'WORK':WORK,'SELF':SELF,'bindings':bindings},'verify',base.verify.__defaults__,base.verify.__closure__)


def verify(d):
    _verify(d);w=api.read(WORK)
    api.require(api.sha(REFERENCE)==w['independent_reference_sha256'] and api.sha(refs.DESIGN)==w['independent_reference_design_sha256'],'exact qualified reference contracts')
    api.require(w['prior_total_saved_policy_qualification_steps']==4000+3000+3600==10600
        and 10600+17000<=w['maximum_combined_policy_qualification_saved_steps']==50000,'actual failed-inclusive combined saved ledger')
job.verify=verify


def ledger():
    r=sealed(REFERENCE);w=api.read(WORK)
    api.require(api.sha(REFERENCE)==w['independent_reference_sha256'] and r['passed'] and r['reference_qualification_closed']
        and r['saved_steps']==r['independently_physical_passing_steps']==3600 and not r['unresolved_reservations'],'all independently qualified sphere reference calls')
    api.require(r['producer_classifier_never_called'] and r['all_owned_processes_retired'] and r['old_failed_preflight_remains_failed'],'independent source/retirement/nonpromotion')
    api.verify_mapping(r['inputs']);prior=sealed(base.CLOSE);api.verify_mapping(prior['inputs'])
    failed=sealed(refs.FAIL);api.verify_mapping(failed['inputs'])
    api.require(prior['saved_new_trajectory_steps']==4000 and failed['saved_steps']==3000 and not failed['preflight_passed'],'exact separate old qualification/failure ledger')
    api.require(not job.PREFLIGHT.exists() and not job.RUN.exists(),'new preflight, no production')


def reference_record(case,tag):
    path=refs.RUN/(case['id']+'_'+tag)/'call.json.xz';record=q.independent_file(path,api.sha(refs.DESIGN))
    api.require(record['independent_policy_reference'] and record['reference_classifier_sha256']==api.sha(refs.reference.__file__)
        and record['numerical_policy_contract_sha256']==api.sha(refs.WORK),'explicit accepted independent same-policy reference')
    return record


def prepare():
    w=api.read(WORK);ledger();no_competing_trajectory()
    api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc']) and shutil.disk_usage(ROOT).free>=w['minimum_free_disk_bytes'],'clock and disk reserve')
    api.require(not job.DESIGN.exists(),'exclusive design')
    old=api.read(base.job.DESIGN);base.job.verify(old);d=copy.deepcopy(old);d.pop('binding')
    files=list(SELF.parent.glob('*.py'));reference_design=api.read(refs.DESIGN);close=sealed(REFERENCE)
    inputs=[WORK,base.job.DESIGN,refs.DESIGN,REFERENCE,REFERENCE.parent/'completion.json',refs.WORK]
    d.update(stage='Stage216 fresh same-policy six-case bounded stack verification',
        sources={**d['sources'],**reference_design['sources'],**{str(p):api.sha(p) for p in files}},
        inputs={**d['inputs'],**reference_design['inputs'],**close['inputs'],**{str(p):api.sha(p) for p in inputs}},
        agent_work_end_utc=w['work_end_utc'],simulation_cutoff_utc=w['simulation_cutoff_utc'],final_audit_deadline_utc=w['final_audit_deadline_utc'],
        audit_source_sha256=api.sha(SELF),qualified_normal_gap_bindings=bindings(),numerical_policy_contract_sha256=api.sha(WORK),
        claim='Explicit independent same-new-policy exact sphere references; original exact fibre/fresh controls and all physical/restart/concurrent/scientific gates. Stage214 stays failed; prior10600 saved diagnostics disclosed. No production/full-horizon/population/validation claim.')
    d['binding']=api.digest(d);verify(d);job.commit(job.DESIGN,d);job.PREFLIGHT.parent.mkdir(parents=True,exist_ok=False)
    print('SAME_POLICY_STACK_DESIGN',api.sha(job.DESIGN),flush=True)


owned=FunctionType(base.owned.__code__,{**base.owned.__globals__,'job':job,'verify':verify},'owned',base.owned.__defaults__,base.owned.__closure__)
if __name__=='__main__':
    args=sys.argv[1:]
    if args==['prepare']:prepare()
    elif len(args)==3 and args[:2]==['worker','preflight']:owned(args[1],args[2]);job.worker(args[1],args[2])
    elif args==['auditor','preflight']:owned(args[1]);job.auditor(args[1])
    elif args==['evaluate','preflight']:job.evaluate(args[1])
    else:raise ValueError('bounded new preflight only')
