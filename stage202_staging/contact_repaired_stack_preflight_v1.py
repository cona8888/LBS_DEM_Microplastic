"""Stage202 numerical-route preflight; three-producer live bound, no production."""
from pathlib import Path
from types import FunctionType,SimpleNamespace
import copy,importlib.util,os,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage200_staging'))
sys.path.insert(0,str(ROOT/'stage201_staging'))
import revised_stack_preflight_v1 as previous
import two_contact_seeded_polish_v4 as repair
import audit_two_contact_polish_v4 as auditor
import bounded_contact_diagnostic_v1 as local
api=previous.api;candidate=previous.candidate;storage=previous.storage;affinity=previous.affinity
q=SimpleNamespace(**vars(previous.q))
spec=importlib.util.spec_from_file_location('_stage202_qualified_lifecycle',previous.job.__file__)
job=importlib.util.module_from_spec(spec);sys.modules[spec.name]=job;spec.loader.exec_module(job)
WORK=ROOT/'stage202_designs/full_stack_20260928/contract_01.json';BASE='full_stack_20260928'
job.ROOT=ROOT;job.SELF=Path(__file__).resolve();job.BASE=BASE;job.WORK=WORK
job.DESIGN=ROOT/'stage202_designs'/BASE/'design_01.json'
job.PREFLIGHT=ROOT/'stage202_runs'/BASE/'preflight_01';job.RUN=ROOT/'stage202_runs'/BASE/'production_not_authorized'
job.OUT=ROOT/'stage202_evaluations'/BASE;job.PREFLIGHT_SCRIPT=Path(__file__).with_name('qualify_contact_repaired_stack_v1.py')
job.codec=storage.codec;job.kernel=SimpleNamespace(evaluate=auditor.kernel);job.observer=previous.job.observer
raw_execute=FunctionType(previous.raw_execute.__code__,dict(job.__dict__),'execute_segment',previous.raw_execute.__defaults__,previous.raw_execute.__closure__)
LOCAL=ROOT/'stage201_runs/contact_repair_20260928';CLOSE=local.EVALBASE/'window_independent_close_01/results.json'


def execute_segment(d,case,before,path,cap,prefix,stop):
    candidate.warm()
    with repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()),candidate.scope('compiled_direct'),previous.baseline.repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):
        return raw_execute(d,case,before,path,cap,prefix,stop)
job.execute_segment=execute_segment


def local_record(path,design_sha,*args,**kwargs):
    path=Path(path)
    if path not in (LOCAL/'dispatch_full_01/call.json.xz',LOCAL/'polish_replay_01/call.json.xz'):
        return previous.q.independent_file(path,design_sha,*args,**kwargs)
    api.require(design_sha==api.sha(local.job.DESIGN),'exact Stage201 oracle design')
    prefix=local.prefix196()
    for name in ('dispatch_full_01','polish_replay_01'):
        folder=LOCAL/name;r=local.sealed_result(folder/'results.json');api.require(r['numerical_audit_passed'],'independently passing local seed/oracle')
        api.verify_mapping(r['artifacts']);record,prefix=storage.codec.read_record(folder/'call.json.xz',design_sha,prefix)
        if path==folder/'call.json.xz':return record
    raise AssertionError('unreachable local oracle')
q.independent_file=local_record


def ledger():
    api.require(api.sha(CLOSE)=='9e6f203f0167571e0c06233560554af43e8f6211b6e286bd749f574689973414','accepted independent Stage201 anchor')
    api.require(api.sha(repair.__file__)=='6814ae60c8cdd06de77072a79bea4afab45f3242092ea764e932bcc1c067742d' and api.sha(auditor.__file__)=='d4cf395bf6d0c873b824e41f9401d465d0763ec8213fe444b383b966724274e2','exact locally qualified candidate and auditor')
    r=local.sealed_result(CLOSE);api.require(r['passed'] and r['saved_steps']==48813 and r['independently_passing_steps']==48325 and not r['unresolved_reservations'],'sealed prior failure-inclusive ledger')
    api.verify_mapping(r['inputs']);api.require(not job.PREFLIGHT.exists(),'fresh qualification only')


def verify(d):
    old=api.read(previous.job.DESIGN);previous.verify(old);w=api.read(WORK)
    allowed={'stage','binding','sources','inputs','budget','agent_work_end_utc','simulation_cutoff_utc','final_audit_deadline_utc','prior_recovery_steps','prior_stage202_steps','stress_case','stress_seed_raw','stress_seed_design','stress_oracle_raw','stress_oracle_design','audit_source_sha256','audit_structure','claim'}
    api.require({k for k in set(d)|set(old) if d.get(k)!=old.get(k)}<=allowed,'only declared clock, route, verification-input, ledger and output changes')
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'new immutable design')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    api.require(d['cases']==old['cases'] and d['numerical_gates']==old['numerical_gates']==job.policy.GATES,'unchanged six cases and all scientific gates')
    api.require({**d['budget'],'workers':6}==old['budget'] and d['budget']['workers']==3,'only live producer slots change from preflight to original production layout')
    api.require(d['budget']['workers']*d['maximum_unverified_segments_per_case']<=d['maximum_unverified_segments_total']==6,'global six-record bound')
    api.require(d['preflight']==old['preflight'] and d['preflight']['maximum_new_steps']==17000 and not d['production_authorized'],'same exact bounded test sizes')
    api.require(d['agent_work_end_utc']==w['work_end_utc'] and d['simulation_cutoff_utc']==w['simulation_cutoff_utc'] and d['final_audit_deadline_utc']==w['final_audit_deadline_utc'],'distinct bounded clocks')
    api.require(d['stress_case']==local.source.NAME and d['stress_seed_raw']==str(LOCAL/'dispatch_full_01/call.json.xz') and d['stress_oracle_raw']==str(LOCAL/'polish_replay_01/call.json.xz'),'explicit repaired two-contact verification domain')
    api.require(d['prior_stage202_steps']==0 and w['maximum_new_qualification_accepted_steps']==17000,'new separately bounded ledger')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    api.require(raw_execute.__code__ is previous.raw_execute.__code__ and q.campaign.code_sha(raw_execute)==d['integration_code_sha256'],'unchanged integration bytecode')
    for key in ('parent','fast','prior','deadline','capture','observer'):
        api.require(raw_execute.__globals__[key] is previous.raw_execute.__globals__[key],'unchanged physics dependency '+key)
    api.require(d['audit_source_sha256']==api.sha(auditor.__file__) and job.kernel.evaluate is auditor.kernel,'qualified independent numerical routing')
    storage.verify_bindings();affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])
job.verify=verify


def prepare():
    w=api.read(WORK);api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc']),'preparation clock');ledger()
    d=copy.deepcopy(api.read(previous.job.DESIGN));d.pop('binding');d.pop('prior_recovery_steps')
    d['budget']['workers']=3
    files=[Path(__file__),job.PREFLIGHT_SCRIPT,Path(__file__).with_name('audit_contact_repaired_stack_v1.py')]+list((ROOT/'stage201_staging').glob('*.py'))
    inputs=[WORK,previous.job.DESIGN,CLOSE,CLOSE.parent/'completion.json']
    inputs+= [LOCAL/name/f for name in ('dispatch_full_01','polish_replay_01') for f in ('results.json','completion.json','checkpoint.json','history.json','prefix.json','call.json.xz','call.json.seal.json')]
    inputs += [local.RECON/f for f in ('results.json','completion.json','prefix_00196.json','history_00196.json')]
    d.update(stage='Stage202 bounded same-physics repaired six-case stack qualification',sources={**d['sources'],**{str(x):api.sha(x) for x in files}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},
        agent_work_end_utc=w['work_end_utc'],simulation_cutoff_utc=w['simulation_cutoff_utc'],final_audit_deadline_utc=w['final_audit_deadline_utc'],prior_stage202_steps=0,
        stress_case=local.source.NAME,stress_seed_raw=str(LOCAL/'dispatch_full_01/call.json.xz'),stress_seed_design=str(local.job.DESIGN),stress_oracle_raw=str(LOCAL/'polish_replay_01/call.json.xz'),stress_oracle_design=str(local.job.DESIGN),
        audit_source_sha256=api.sha(auditor.__file__),audit_structure=auditor.STRUCTURAL_IDENTITY,production_authorized=False,
        claim='Bounded numerical/process qualification only; Stage200 terminal audit unresolved, production and resource readiness not established.')
    d['binding']=api.digest(d);verify(d);job.commit(job.DESIGN,d);print('STAGE202_DESIGN',api.sha(job.DESIGN),flush=True)


def owned(mode,name=None):
    api.require(mode=='preflight','production disabled');d=api.read(job.DESIGN);verify(d)
    core=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=affinity.bind(core);job.commit(job.root_for(mode)/((name or 'auditor')+'.affinity.json'),{**info,'design_sha256':api.sha(job.DESIGN),'argv':sys.argv,'utc':job.utc().isoformat()})


if __name__=='__main__':
    a=sys.argv[1:]
    if a==['prepare']:prepare()
    elif a==['supervise','preflight']:job.supervise('preflight')
    elif len(a)==3 and a[:2]==['worker','preflight']:owned(a[1],a[2]);job.worker(a[1],a[2])
    elif a==['auditor','preflight']:owned(a[1]);job.auditor(a[1])
    elif a==['evaluate','preflight']:job.evaluate(a[1])
    else:raise ValueError('bounded preflight only')
