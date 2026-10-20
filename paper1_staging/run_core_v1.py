"""Fresh bounded first Paper1 trajectory; original mechanics/auditors unchanged.

Raw/history and complete audit outputs are lossless. FULL checkpoints are
retained once at retirement and reconstructible from the contiguous raw chain;
no duplicate full checkpoint is emitted for each production segment.
"""
from pathlib import Path
from types import SimpleNamespace,FunctionType
from datetime import datetime,timezone,timedelta
import sys,os,time,shutil,traceback
import numpy as np
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cost_screen_v1 as old
import numeric_archive_v1 as archives
import document_archive_v1 as documents
s=old;ROOT=s.ROOT;SELF=Path(__file__).resolve();PYTHON=s.PYTHON
BASE='first_core_20261013';OUT=ROOT/'paper1_runs'/BASE;DESIGNS=ROOT/'paper1_designs'/BASE
PLAN=DESIGNS/'design_01.json';AUTH=DESIGNS/'authorization_01.json';PHYSICAL=DESIGNS/'physical_cases_01.json'
sha,read,require,commit,seal=s.sha,s.read,s.require,s.commit,s.seal
DOC=documents.build(s.q.job.codec,s.api)
CORE_ID='p1_i0_equal_volume_sphere_u0p5'


def bound():
    s.environment();p=read(PLAN)
    require(time.time()<datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp(),'Numerical cutoff')
    require(shutil.disk_usage(ROOT).free>20*1024**3,'Original disk reserve')
    require(sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file())<4*1024**3,'Window output cap')
    return p


def verify_inputs(p):
    bound();s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['physical_inputs'])
    require(p['binding']==s.api.digest({k:v for k,v in p.items() if k!='binding'})
        and p['physical_design_sha256']==sha(PHYSICAL) and p['authorization_sha256']==sha(AUTH),'Exact fresh authority/design')


def prepare():
    s.environment();require(not PLAN.exists() and not OUT.exists(),'Create-only new core window')
    decision=s.fields.sealed(s.factory.EXPOSURE);require(decision['passed'] and decision['selected_pv']==.01,'Prospective frozen exposure')
    for path in [ROOT/'paper1_runs/storage_qualification_20261013/results.json',
                 ROOT/'paper1_runs/storage_qualification_20261013/documents_01/qualification_01/results.json']:
        r=s.fields.sealed(path);require(r['passed'],'Qualified lossless storage');s.api.verify_mapping(r['artifacts']);s.api.verify_mapping(r['source_files'])
    case,field,data=s.factory.load_case(CORE_ID,.01,mode='core');del field,data
    template=s.factory.contract();d=read(template['physical_design_file'])
    physical=dict(schema='paper1.first-core-physical.v1',cases=[case],minimum_gap_semantics=d['minimum_gap_semantics'],
        original_template_sha256=template['physical_design_sha256'],exposure_decision_sha256=sha(s.factory.EXPOSURE),
        physical_equation_changes=[],accuracy_gate_changes=[])
    physical['binding']=s.api.digest(physical)
    inputs=dict(read(s.PLAN)['physical_inputs'])
    for path in [s.factory.EXPOSURE,s.factory.EXPOSURE.with_name('completion.json'),
        s.factory.EXPOSURE.parent/'measurement_provenance_01/results.json',
        ROOT/'paper1_runs/storage_qualification_20261013/results.json',
        ROOT/'paper1_runs/storage_qualification_20261013/documents_01/qualification_01/results.json',
        s.OUT/'retirement_01/results.json']:
        inputs[str(path)]=sha(path)
    inputs.update(s.context.fields.dependencies(case['spec']['field_metadata']))
    sources={str(Path(m.__file__).resolve()):sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py'
        and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    prior=read(s.PLAN)['source_files'];sources={**prior,**sources}
    s.api.verify_mapping(inputs);s.api.verify_mapping(sources)
    start=datetime.now(timezone.utc);end=start+timedelta(hours=2)
    auth=dict(human_authorization='Complete agreed12-case Paper1 dataset under prospective0.01PV decision; fresh bounded first-core window, no closed run resumed.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(minutes=15)).isoformat(),
        worker_cutoff_utc=(end-timedelta(minutes=8)).isoformat(),step_cap_per_call=5000,
        maximum_saved_steps=500512,maximum_production_steps=500000,maximum_production_calls=125,
        maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,
        workers=1,threads=1,maximum_unverified_records=1,logical_cpu=14,minimum_free_disk_bytes=20*1024**3,
        maximum_output_bytes=4*1024**3,no_timestep_escalation=True,retain_all_failures=True,
        accuracy_promotion_authorized=False,successor_cases_authorized=False)
    commit(AUTH,auth);commit(PHYSICAL,physical);inputs[str(PHYSICAL)]=sha(PHYSICAL)
    p={**auth,'authorization_sha256':sha(AUTH),'physical_design_sha256':sha(PHYSICAL),
       'source_files':sources,'physical_inputs':inputs,'case_id':case['id'],
       'numerical_policy_contract_sha256':sha(s.q.job.WORK),'logical_core_id':CORE_ID,
       'storage_protocol':'Original complete raw/history + lossless full audit document references + native NPY traces; terminal FULL checkpoint only.'}
    p['binding']=s.api.digest(p);commit(PLAN,p)
    seal(OUT/'preparation_01',dict(passed=True,design_sha256=sha(PLAN),new_steps=0,utc=s.utc()))
    print('PAPER1_FIRST_CORE_PREPARED',sha(PLAN),p['end_utc'],flush=True)


def make_context():
    def write(path,value):
        if Path(path).name=='results.json' and isinstance(value,dict) and 'summary' in value:
            return DOC.store(path,value,sha(PHYSICAL))
        return commit(path,value)
    admin=SimpleNamespace(bound=bound,commit=write,sha=sha,utc=s.utc)
    ctx=s.context.build(PLAN,AUTH,PHYSICAL,admin,verify_inputs)
    ctx.job.codec=archives.build(ctx.job.codec,preset=9)
    return ctx


def transaction(ctx,p,d,case,label,cap,before=None,prefix=None,previous=None):
    geometry=ctx.geometry_for(case)
    rec,updated,row=ctx.segment(p,d,case,geometry,before,prefix,OUT/'records'/label,cap,previous,
                               'restart_diagnostic' if not label.startswith('production') else 'core_pending_accuracy')
    extra=s.q.guard.audit(rec);require(rec['result']['rejected']==0,'Original zero-rejection gate')
    gate=OUT/'records'/label/'guard_completion'
    seal(gate,dict(passed=True,saved_steps=len(rec['rows']),guard_audit=extra,
        full_checkpoint_sha256=s.api.digest(rec['result']['checkpoint']),
        artifacts={str(x):sha(x) for x in (OUT/'records'/label).glob('*') if x.is_file()},utc=s.utc()))
    return rec,updated,row


def run():
    p=bound();verify_inputs(p);proc=psutil.Process();proc.cpu_affinity([14])
    require(not (OUT/'worker_launch.json').exists(),'No duplicate worker')
    commit(OUT/'worker_launch.json',dict(pid=proc.pid,created=proc.create_time(),command=proc.cmdline(),utc=s.utc()))
    ctx=make_context();d=read(PHYSICAL);case=d['cases'][0]
    s.q.reference.JOB.parent.b.old.parent.configure();s.q.kernel.warm();s.q.kernel.reset()
    before=prefix=None;accepted=diagnostic=0;labels=[];error=None;reason=None
    try:
        serial,_,_=transaction(ctx,p,d,case,'serial',256);diagnostic+=len(serial['rows'])
        a,pa,_=transaction(ctx,p,d,case,'split_a',128);diagnostic+=len(a['rows'])
        b,_,_=transaction(ctx,p,d,case,'split_b',128,a['result']['checkpoint'],pa,sha(OUT/'records/split_a/results.json'));diagnostic+=len(b['rows'])
        require(len(serial['rows'])==256 and len(a['rows'])==len(b['rows'])==128
            and s.api.digest(serial['rows'])==s.api.digest(a['rows']+b['rows'])
            and s.api.digest(serial['result']['checkpoint'])==s.api.digest(b['result']['checkpoint']),
            'Exact fresh rows/FULL checkpoint/history with new storage')
        seal(OUT/'restart_01',dict(passed=True,discarded_diagnostic_steps=512,exact_rows=True,exact_full_checkpoint_history=True,utc=s.utc()))
        del serial,a,b,pa
        previous=None
        for index in range(1,126):
            if time.time()>=datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp()-90:reason='cutoff_reserve';break
            if accepted>=500000:reason='window_step_cap';break
            verify_inputs(p);label=f'production_{index:05d}'
            rec,prefix,row=transaction(ctx,p,d,case,label,min(5000,500000-accepted),before,prefix,previous)
            accepted+=len(rec['rows']);before=rec['result']['checkpoint'];labels.append(label)
            previous=sha(OUT/'records'/label/'results.json')
            print('PAPER1_CORE_SEGMENT_ACCEPTED',index,len(rec['rows']),before['state']['t'],flush=True)
            if rec['result']['status'] in ('present_at_horizon','full_window_exit'):
                reason='native_complete_pending_original_accuracy';break
    except Exception as exc:
        error=dict(message=repr(exc),traceback=traceback.format_exc());raise
    finally:
        # Authenticate every contiguous admitted production raw/history again.
        verified=None;full=None
        for label in labels:
            gate=s.fields.sealed(OUT/'records'/label/'guard_completion/results.json');s.api.verify_mapping(gate['artifacts'])
            rr,verified=ctx.job.codec.read_record(OUT/'records'/label/'call.json.xz',sha(PHYSICAL),verified)
            full=rr['result']['checkpoint']
        require(full==before,'Last sealed complete checkpoint reconstructed from all production records')
        if full is not None:
            DOC.store(OUT/'recoverable/checkpoint.json',full,sha(PHYSICAL))
            commit(OUT/'recoverable/prefix.json',prefix.reference())
        unknown=known=0
        for folder in (OUT/'records').glob('*'):
            if folder.is_dir() and not (folder/'guard_completion/completion.json').exists():
                if (folder/'accounting.json').exists():known+=read(folder/'accounting.json')['saved_steps']
                else:unknown+=5000 if folder.name.startswith('production') else 256 if folder.name=='serial' else 128
        seal(OUT/'final_disposition_01',dict(passed=error is None,reason=reason,error=error,
            accepted_physical_steps=accepted,discarded_diagnostic_steps=diagnostic,known_unaccepted_saved_steps=known,
            unknown_reserved_steps_upper_bound=unknown,production_labels=labels,full_checkpoint_sha256=s.api.digest(before),
            native_complete=reason=='native_complete_pending_original_accuracy',full_path_accuracy_passed=False,
            core_result_admitted=False,design_sha256=sha(PLAN),utc=s.utc()))


namespace={**s.__dict__,**globals()}
supervise=FunctionType(s.supervise.__code__,namespace,s.supervise.__name__,s.supervise.__defaults__,s.supervise.__closure__)
if __name__=='__main__':{'prepare':prepare,'run':run,'supervise':supervise}[sys.argv[1]]()
