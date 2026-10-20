"""Fresh bounded full stack; frozen integration, qualified local route/metadata."""
from pathlib import Path
from types import FunctionType,SimpleNamespace
import copy,os,sys,psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage202_staging'),str(ROOT/'stage206_staging'),str(ROOT/'stage204_staging')]
import contact_repaired_stack_preflight_v1 as previous
import two_contact_cone_feasibility_v1 as repair
import audit_cone_feasibility_v1 as auditor
import receipt_ack_single_pass_v1 as ack
api,job,q,candidate,storage,affinity=previous.api,previous.job,previous.q,previous.candidate,previous.storage,previous.affinity
OLD_DESIGN=job.DESIGN
WORK=ROOT/'stage208_designs/cone_feasibility_stack_20260930/contract_01.json'
BASE='cone_feasibility_stack_20260930'
LOCAL=ROOT/'stage207_runs/feasibility_trajectory_20260930'
CLOSE=ROOT/'stage207_evaluations/feasibility_trajectory_20260930/trajectory_independent_close_01/results.json'
RECON=ROOT/'stage206_evaluations/contact_failure_20260930/reconstructed_window_01'
LOCAL_QUAL=ROOT/'stage206_evaluations/contact_failure_20260930/independent_local_01/results.json'
OLD_RAW_DESIGN=ROOT/'stage205_designs/receipt_repaired_campaign_20260930/design_01.json'
job.SELF=Path(__file__).resolve();job.BASE=BASE;job.WORK=WORK
job.DESIGN=ROOT/'stage208_designs'/BASE/'design_01.json'
job.PREFLIGHT=ROOT/'stage208_runs'/BASE/'preflight_01'
job.RUN=ROOT/'stage208_runs'/BASE/'production_not_authorized'
job.OUT=ROOT/'stage208_evaluations'/BASE
job.PREFLIGHT_SCRIPT=Path(__file__).with_name('qualify_cone_feasibility_stack_v1.py')
job.kernel=SimpleNamespace(evaluate=auditor.kernel)
raw_execute=FunctionType(previous.raw_execute.__code__,dict(job.__dict__),'execute_segment',previous.raw_execute.__defaults__,previous.raw_execute.__closure__)
job.execute_segment=FunctionType(previous.execute_segment.__code__,dict(previous.execute_segment.__globals__,repair=repair,raw_execute=raw_execute),'execute_segment',previous.execute_segment.__defaults__,previous.execute_segment.__closure__)

def acknowledged(d,pending):return ack.acknowledged(api,job.policy,job.DESIGN,d,pending)
job.acknowledged=acknowledged
old_independent=previous.q.independent_file

def sealed(path):
    r=api.read(path);api.require(api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed '+str(path));return r

def local_record(path,design_sha,*args,**kwargs):
    path=Path(path)
    if path not in (LOCAL/'split_a_01/call.json.xz',LOCAL/'split_b_01/call.json.xz'):
        return old_independent(path,design_sha,*args,**kwargs)
    api.require(design_sha==api.sha(OLD_RAW_DESIGN),'explicit old diagnostic checkpoint design')
    codec=storage.codec
    prefix=codec.HistoryState(**api.read(RECON/'prefix_00227.json'),history_bytes=codec.packed_history(api.read(RECON/'history_00227.json')))
    codec.validate_prefix(prefix,design_sha)
    for name in ('split_a_01','split_b_01'):
        r=sealed(LOCAL/name/'results.json');api.require(r['numerical_audit_passed'] and not r['rejected'],'passing new local oracle')
        api.verify_mapping(r['artifacts']);rec,prefix=codec.read_record(LOCAL/name/'call.json.xz',design_sha,prefix)
        if path==LOCAL/name/'call.json.xz':return rec
    raise AssertionError('oracle inventory')
q.independent_file=local_record

def ledger():
    r=sealed(CLOSE);api.require(r['passed'] and not r['unresolved_reservations'] and r['exact_restart_full_rows'] and r['exact_restart_full_checkpoint'],'new bounded local closure')
    api.verify_mapping(r['inputs']);api.require(sealed(LOCAL_QUAL)['passed'],'independent zero-step local qualification')
    api.require(not job.PREFLIGHT.exists(),'fresh preflight not restart')

def verify(d):
    old=api.read(OLD_DESIGN);w=api.read(WORK)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'immutable new design')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    allowed={'stage','binding','sources','inputs','agent_work_end_utc','simulation_cutoff_utc','final_audit_deadline_utc','stress_seed_raw','stress_seed_design','stress_oracle_raw','stress_oracle_design','audit_source_sha256','audit_structure','claim','receipt_adapter_sha256'}
    api.require({k for k in set(d)|set(old) if d.get(k)!=old.get(k)}<=allowed,'only declared verification inputs, numerical route, metadata and clocks changed')
    for k in ('cases','numerical_gates','budget','preflight','minimum_gap_semantics','maximum_unverified_segments_total','maximum_unverified_segments_per_case'):
        api.require(d[k]==old[k],'unchanged scientific/resource field '+k)
    api.require(d['numerical_gates']==job.policy.GATES and not d['production_authorized'] and d['budget']['workers']==3,'original gates/no production/three slots')
    api.require(d['preflight']['maximum_new_steps']==w['maximum_new_qualification_accepted_steps']==17000,'new explicit bounded ledger')
    api.require(d['agent_work_end_utc']==w['work_end_utc'] and d['simulation_cutoff_utc']==w['simulation_cutoff_utc'] and d['final_audit_deadline_utc']==w['final_audit_deadline_utc'],'separate clocks')
    api.require(d['stress_seed_raw']==str(LOCAL/'split_a_01/call.json.xz') and d['stress_oracle_raw']==str(LOCAL/'split_b_01/call.json.xz'),'repair exercised across failure time')
    api.require(d['stress_seed_design']==d['stress_oracle_design']==str(OLD_RAW_DESIGN),'exact diagnostic design identity')
    api.require(d['audit_source_sha256']==api.sha(auditor.__file__) and job.kernel.evaluate is auditor.kernel,'qualified original-gate numerical audit')
    api.require(d['receipt_adapter_sha256']==api.sha(ack.__file__)=='80d732079f2ef1a6f31c29a77394095ca6fabf9bcec27cb2df31ea65563fffd1','qualified metadata helper')
    api.require(job.worker.__globals__['acknowledged'] is acknowledged,'actual worker adapter binding')
    api.require(raw_execute.__code__ is previous.raw_execute.__code__ and job.execute_segment.__code__ is previous.execute_segment.__code__,'unchanged integration and scope bytecode')
    api.require(job.execute_segment.__globals__['repair'] is repair and repair.bound.__code__ is repair.prior.bound.__code__,'qualified new same-dispatch solver binding')
    api.require(repair.bound.__globals__['solve'] is repair.solve and d['audit_structure']==auditor.STRUCTURAL_IDENTITY,'actual qualified solver/auditor associations')
    for key in ('parent','fast','prior','deadline','capture','observer'):
        api.require(raw_execute.__globals__[key] is previous.raw_execute.__globals__[key],'unchanged physical dependency '+key)
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    storage.verify_bindings();affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])
job.verify=verify

def no_competing_trajectory():
    logs=ROOT/'stage205_evaluations/receipt_repaired_campaign_20260930/terminal_evaluator_01'
    permitted=[api.read(logs/x) for x in ('evaluator_launch.json','witness_launch.json')]
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:
            cmd=p.cmdline()
            local_scripts=[x for x in cmd if x.lower().endswith('.py') and ((ROOT/x).resolve().is_relative_to(ROOT) or Path(x).resolve().is_relative_to(ROOT))]
            if not local_scripts and 'matdem_microplastic' not in ' '.join(cmd).lower():continue
            matches=[r for r in permitted if r['pid']==p.pid]
            api.require(matches,'no competing simulation/benchmark')
            r=matches[0]
            if 'created' in r:
                identity=cmd==r['argv'] and p.create_time()==r['created']
            else:
                identity=cmd==[sys.executable,'-B','-u',r['argv'][0]] and abs(p.create_time()-job.policy.utc(r['utc']).timestamp())<2.
            script=Path(r['argv'][-3] if 'created' in r else r['argv'][0])
            api.require(identity and api.sha(script)==r['source_sha256'],'only authenticated existing read-only evaluator/witness may coexist')
        except psutil.NoSuchProcess:continue

def prepare():
    ledger();w=api.read(WORK);api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc']),'bounded preparation clock')
    d=copy.deepcopy(api.read(OLD_DESIGN));d.pop('binding')
    files=list(Path(__file__).parent.glob('*.py'))+[Path(repair.__file__),Path(auditor.__file__),Path(ack.__file__)]
    inputs=[WORK,OLD_DESIGN,CLOSE,CLOSE.parent/'completion.json',LOCAL_QUAL,LOCAL_QUAL.parent/'completion.json',OLD_RAW_DESIGN]
    inputs+=list(RECON.glob('*.json'))
    inputs+=[LOCAL/n/f for n in ('split_a_01','split_b_01') for f in ('results.json','completion.json','checkpoint.json','prefix.json','history.json','call.json.xz','call.json.seal.json')]
    d.update(stage='Stage208 bounded cone-feasibility repaired full stack',sources={**d['sources'],**{str(f):api.sha(f) for f in files}},inputs={**d['inputs'],**{str(f):api.sha(f) for f in inputs}},agent_work_end_utc=w['work_end_utc'],simulation_cutoff_utc=w['simulation_cutoff_utc'],final_audit_deadline_utc=w['final_audit_deadline_utc'],stress_seed_raw=str(LOCAL/'split_a_01/call.json.xz'),stress_seed_design=str(OLD_RAW_DESIGN),stress_oracle_raw=str(LOCAL/'split_b_01/call.json.xz'),stress_oracle_design=str(OLD_RAW_DESIGN),audit_source_sha256=api.sha(auditor.__file__),audit_structure=auditor.STRUCTURAL_IDENTITY,receipt_adapter_sha256=api.sha(ack.__file__),claim='Separately bounded local numerical/process verification only; preserve failed Stage205 and disclosed root ambiguity. No production/full-path/release claim.')
    d['binding']=api.digest(d);verify(d);job.commit(job.DESIGN,d);print('STAGE208_DESIGN',api.sha(job.DESIGN),flush=True)

def owned(mode,name=None):
    api.require(mode=='preflight','production disabled');d=api.read(job.DESIGN);verify(d)
    core=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=affinity.bind(core);job.commit(job.root_for(mode)/((name or 'auditor')+'.affinity.json'),dict(info,design_sha256=api.sha(job.DESIGN),argv=sys.argv,utc=job.utc().isoformat()))

if __name__=='__main__':
    a=sys.argv[1:]
    if a==['prepare']:prepare()
    elif len(a)==3 and a[:2]==['worker','preflight']:owned(a[1],a[2]);job.worker(a[1],a[2])
    elif a==['auditor','preflight']:owned(a[1]);job.auditor(a[1])
    elif a==['evaluate','preflight']:job.evaluate(a[1])
    else:raise ValueError('bounded preflight only')
