"""One-at-a-time exclusive independent-policy reference calls; inclusive ledger."""
from datetime import timedelta
from pathlib import Path
from types import FunctionType,ModuleType,SimpleNamespace
from fractions import Fraction
import math
import copy,inspect,os,shutil,sys,time,traceback
import psutil
import independent_gap_reference_v1 as reference
ROOT=reference.ROOT
sys.path.insert(0,str(ROOT/'stage214_staging'))
import normal_gap_stack_preflight_v1 as prior
import qualify_normal_gap_stack_v1 as original_preflight
api=prior.api
BASE='independent_policy_references_20261001'
WORK=ROOT/'stage215_designs'/BASE/'contract_01.json'
DESIGN=WORK.with_name('design_01.json')
RUN=ROOT/'stage215_runs'/BASE
OUT=ROOT/'stage215_evaluations'/BASE
SELF=Path(__file__).resolve()
FAIL=prior.job.OUT/'failed_preflight_independent_03/results.json'
job=ModuleType('_stage215_reference_namespace');job.__dict__.update(vars(prior.job))
for name,fn in list(vars(prior.job).items()):
    if inspect.isfunction(fn) and fn.__globals__ is vars(prior.job):
        setattr(job,name,FunctionType(fn.__code__,vars(job),fn.__name__,fn.__defaults__,fn.__closure__))
job.DESIGN=DESIGN;job.WORK=WORK;job.ROOT=ROOT
_reference_local=SimpleNamespace(**vars(prior.local));_reference_local.policy_scope=reference
_execution=FunctionType(prior.execute_segment.__code__,{**prior.execute_segment.__globals__,'job':job,'WORK':WORK,'local':_reference_local},
                        prior.execute_segment.__name__,prior.execute_segment.__defaults__,prior.execute_segment.__closure__)


def sealed(path):return prior.sealed(Path(path))


def bindings():
    api.require(_execution.__code__ is prior.execute_segment.__code__ and reference._reference_gen.__code__ is reference._gen.__code__,'unchanged adapter/integration/provenance scope bytecode')
    api.require(reference._reference_gen.__globals__['policy'].classify is reference.classify,'actual independent classifier bound')
    return dict(adapter_code_sha256=prior.q.campaign.code_sha(_execution),scope_generator_code_sha256=prior.q.campaign.code_sha(reference._reference_gen),
                classifier_source_sha256=api.sha(reference.__file__),producer_classifier_used=False)


def verify(d):
    w=api.read(WORK);old=api.read(prior.job.DESIGN);prior.job.verify(old)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'immutable new diagnostic design')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    allowed={'stage','binding','sources','inputs','claim','audit_source_sha256','audit_structure','numerical_policy_contract_sha256','independent_reference_bindings'}
    api.require({k for k in set(d)|set(old) if d.get(k)!=old.get(k)}<=allowed,'only numerical-reference metadata bindings changed')
    for k in ('cases','numerical_gates','budget','preflight','minimum_gap_semantics','physical_changes','simulation_cutoff_utc','final_audit_deadline_utc','agent_work_end_utc'):
        api.require(d[k]==old[k],'original reference physical/gate/clock field '+k)
    api.require(not d['production_authorized'] and not w['production_authorized'] and not w['full_stack_pass_claim'],'reference only, not production or full-stack pass')
    api.require(d['numerical_policy_contract_sha256']==api.sha(WORK) and d['independent_reference_bindings']==bindings(),'new diagnostic policy bindings')
    api.require(d['audit_source_sha256']==api.sha(SELF) and d['audit_structure']==dict(explicit_reference_contract=True,physical_gate_changes=0,independent_gap_auditor=prior.local.auditor.NAME),'exact reference audit association')
    api.require(w['diagnostic_workers']==w['threads']==1 and w['maximum_new_saved_trajectory_steps']==sum(w['planned_calls'].values())==3600,'one worker fixed inclusive reference budget')
    api.require(4000+3000+3600+17000<=w['maximum_combined_policy_qualification_saved_steps']==50000,'failed-inclusive combined repair allowance')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    return w


def prerequisites():
    d=api.read(DESIGN);w=verify(d)
    api.require(shutil.disk_usage(ROOT).free>=w['minimum_free_disk_bytes'],'20GiB current reserve')
    failed=sealed(FAIL);api.require(api.sha(FAIL)==w['failed_preflight_independent_sha256'] and failed['failed_preflight_fully_accounted'] and not failed['preflight_passed'],'failed preflight independently closed, never promoted')
    api.verify_mapping(failed['inputs'])
    return w,d


def no_worker():prior.no_competing_trajectory()


def ledger():
    saved=0;pending=[]
    for path in RUN.glob('*/launch.json'):
        account=path.parent/'accounting.json'
        if not account.exists():pending.append(str(path));continue
        row=api.read(account);api.require(row['launch_sha256']==api.sha(path),'exact immutable inclusive ledger')
        if not row['saved_steps_known']:pending.append(str(path));continue
        saved+=row['saved_steps']
    return saved,pending


def prepare():
    w=api.read(WORK);no_worker();api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'new preparation clock')
    api.require(not DESIGN.exists() and not RUN.exists(),'new exclusive reference namespace')
    failed=sealed(FAIL);api.require(api.sha(FAIL)==w['failed_preflight_independent_sha256'] and failed['failed_preflight_fully_accounted'],'authenticated failed-control diagnosis')
    api.verify_mapping(failed['inputs']);old=api.read(prior.job.DESIGN);prior.job.verify(old)
    files=list(SELF.parent.glob('*.py'));inputs=[WORK,prior.job.DESIGN,FAIL,FAIL.parent/'completion.json']
    d=copy.deepcopy(old);d.pop('binding')
    d.update(stage='Stage215 independently computed fixed-policy diagnostic references',sources={**d['sources'],**{str(p):api.sha(p) for p in files}},
        inputs={**d['inputs'],**{str(p):api.sha(p) for p in inputs}},numerical_policy_contract_sha256=api.sha(WORK),
        audit_source_sha256=api.sha(SELF),audit_structure=dict(explicit_reference_contract=True,physical_gate_changes=0,independent_gap_auditor=prior.local.auditor.NAME),
        independent_reference_bindings=bindings(),claim='New fixed-policy references, original physical gates. Old Stage214 comparator and old campaigns remain failed. No production, full-horizon or empirical validation claim.')
    d['binding']=api.digest(d);verify(d);job.commit(DESIGN,d);RUN.mkdir(parents=True,exist_ok=False)
    print('INDEPENDENT_REFERENCE_DESIGN',api.sha(DESIGN),flush=True)


def seed(d,name):
    tag='contact' if name.endswith('_contact') else 'fresh';case_id=name.rsplit('_',1)[0]
    case=next(c for c in d['cases'] if c['id']==case_id)
    api.require(case['shape']=='equal_volume_sphere','only the declared original sphere reference cases')
    if tag=='contact':before,_=original_preflight.ns['seed'](d,case)
    else:before=None
    return case,before


def kernel(record,d,case,before,geometry):
    api.require(record['design_sha256']==api.sha(DESIGN) and record['numerical_policy_contract_sha256']==api.sha(WORK),'exact new reference design/contract')
    api.require(record['independent_policy_reference'] is True and record['reference_classifier_sha256']==api.sha(reference.__file__),'explicit independent reference implementation')
    for call in record['normal_gap_operand_policy']['prepare_calls']:
        for item in call['metadata']:
            context=item['context'];metadata=item['classification']
            if context['a']==context['b']:
                value=sum((abs(Fraction.from_float(float(z))) for z in [*context['x'],*context['c'],context['a'],context['r']]),Fraction(0))
                scale=math.nextafter(float(value),math.inf)
                api.require(metadata['absolute_operand_scale_m']==scale,'complete independent recorded operand-scale provenance')
    return prior.local.auditor.kernel(record,case['spec'],job.binding(d,case),before,geometry,api.sha(DESIGN),d['minimum_gap_semantics'])


def execute(d,case,before,path,cap,stop):
    codec=job.codec;original_write=codec.write_record
    def write(raw,record,prefix):
        record['independent_policy_reference']=True;record['reference_classifier_sha256']=api.sha(reference.__file__)
        return original_write(raw,record,prefix)
    proxy=SimpleNamespace(**vars(codec));proxy.write_record=write
    ref_job=SimpleNamespace(**vars(job));ref_job.codec=proxy
    call=FunctionType(_execution.__code__,{**_execution.__globals__,'job':ref_job},_execution.__name__,_execution.__defaults__,_execution.__closure__)
    with reference.forbid_producer():return call(d,case,before,path,cap,None,stop)


def run(name):
    w,d=prerequisites();no_worker();api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'no new reference after cutoff')
    api.require(name in w['planned_calls'] and not (RUN/name).exists(),'declared exclusive reference call')
    saved,pending=ledger();cap=w['planned_calls'][name]
    api.require(not pending and 0<cap<=w['maximum_saved_steps_per_call'] and saved+cap<=w['maximum_new_saved_trajectory_steps'],'complete inclusive reservation ledger')
    case,before=seed(d,name);job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):geometry=original_preflight.tests.prior.geometry()
    folder=RUN/name;folder.mkdir(exist_ok=False);process=psutil.Process()
    stop=min(job.utc()+timedelta(seconds=w['maximum_call_wall_seconds']),job.policy.utc(w['work_end_utc'])).isoformat()
    job.commit(folder/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=job.utc().isoformat(),
        design_sha256=api.sha(DESIGN),contract_sha256=api.sha(WORK),prior_saved_steps=saved,reserved_max_steps=cap,
        input_checkpoint_sha256=api.digest(before),stop_utc=stop))
    job.commit(folder/'input_checkpoint.json',before);raw=folder/'call.json.xz'
    try:
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):record,prefix,seal,elapsed=execute(d,case,copy.deepcopy(before),raw,cap,stop)
        steps=record['result']['steps']-(before['state']['steps'] if before else 0)
        api.require(0<=steps<=cap,'exact inclusive saved-step delta')
        job.commit(folder/'accounting.json',dict(launch_sha256=api.sha(folder/'launch.json'),saved_steps_known=True,saved_steps=steps,
            total_saved_steps=saved+steps,raw_sha256=api.sha(raw),rejected=record['result']['rejected']))
        job.commit(folder/'checkpoint.json',record['result']['checkpoint']);job.commit(folder/'prefix.json',prefix.reference());job.commit(folder/'history.json',record['result']['history'])
        independent=prior.q.independent_file(raw,api.sha(DESIGN));decoded,state=job.codec.read_record(raw,api.sha(DESIGN))
        api.require(api.digest(independent)==api.digest(record)==api.digest(decoded) and state.reference()==prefix.reference(),'complete independent decode and original canonical record identity')
        with reference.forbid_producer():check=kernel(independent,d,case,before,geometry)
        api.require(check['passed'] and steps==len(record['rows'])==cap and record['result']['rejected']==0,'exact count, zero rejection and unchanged physical gates')
        verify(d);api.require(shutil.disk_usage(ROOT).free>=w['minimum_free_disk_bytes'],'post-reference disk reserve')
        result=dict(passed=True,saved_steps=steps,independently_physical_passing_steps=steps,rejected_trials=0,
            reference_name=name,case=case['id'],design_sha256=api.sha(DESIGN),contract_sha256=api.sha(WORK),
            compute_seconds=record['compute_call_wall_s'],transaction_seconds=elapsed,numerical_audit=check,
            producer_classifier_never_called=True,production_authorized=False,artifacts={str(p):api.sha(p) for p in folder.glob('*') if p.is_file()},
            claim='Independent fixed-policy numerical reference only, not campaign observation or old comparator promotion.')
        job.commit(folder/'results.json',result);job.commit(folder/'completion.json',dict(passed=True,results_sha256=api.sha(folder/'results.json')))
        print('INDEPENDENT_REFERENCE_COMPLETE',name,steps,record['result']['time_s'],flush=True)
    except Exception as exc:
        if not (folder/'accounting.json').exists():job.commit(folder/'accounting.json',dict(launch_sha256=api.sha(folder/'launch.json'),saved_steps_known=False,saved_steps=None,reserved_max_steps=cap,raw_exists=raw.exists()))
        job.commit(folder/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),new_trajectory_steps_declared_unknown_unless_accounting_exists=True));raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif len(sys.argv)==3 and sys.argv[1]=='run':run(sys.argv[2])
    else:raise ValueError('prepare | run NAME; one worker only')
