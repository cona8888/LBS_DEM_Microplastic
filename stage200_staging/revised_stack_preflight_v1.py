"""Fresh bounded six-worker instance; original lifecycle and physics retained.

Uses only the independently qualified composed implementation. Production is
deliberately disabled here. Every worker uses the same cooperative work clock.
"""
from pathlib import Path
from types import FunctionType
import copy,importlib.util,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage199_staging'))
import qualify_composed_boundary_v1 as boundary
import performance_stack_preflight_v1 as previous
candidate,storage=boundary.current.candidate,boundary.current.storage
ROOT=boundary.current.ROOT
baseline,q,api=previous.baseline,previous.q,previous.api
affinity=previous.affinity
spec=importlib.util.spec_from_file_location('_stage199_composed_lifecycle',previous.job.__file__)
job=importlib.util.module_from_spec(spec);sys.modules[spec.name]=job;spec.loader.exec_module(job)
WORK=ROOT/'stage200_designs/deadline_revision_20260927/authorization_01.json';BASE='composed_stack_20260927'
job.ROOT=Path('D:/MATDEM_MICROPLASTIC');job.SELF=Path(__file__).resolve();job.BASE=BASE
job.DESIGN=ROOT/'stage200_designs'/BASE/'design_01.json';job.WORK=WORK
job.PREFLIGHT=job.ROOT/'stage200_runs'/BASE/'preflight_01'
job.RUN=job.ROOT/'stage200_runs'/BASE/'production_not_authorized'
job.OUT=ROOT/'stage200_evaluations'/BASE
job.PREFLIGHT_SCRIPT=Path(__file__).with_name('qualify_revised_stack_v1.py')
job.codec=storage.codec;job.kernel=baseline.job.kernel;job.observer=baseline.job.observer
raw_execute=FunctionType(baseline.raw_execute.__code__,dict(job.__dict__),'execute_segment',baseline.raw_execute.__defaults__,baseline.raw_execute.__closure__)

def execute_segment(d,case,before,path,cap,prefix,stop):
    candidate.warm()
    with candidate.scope('compiled_direct'),baseline.repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):
        return raw_execute(d,case,before,path,cap,prefix,stop)
job.execute_segment=execute_segment

def ledger():
    names={'combined_fine_01':3580,'long_fine_01':7406,'current_prefix_01':3580,'native_prefix_01':3580,'combined_native_prefix_01':3580,'composed_boundary_01':3676}
    base=boundary.RUN.parent
    accounts=list(base.glob('*/*.accounting.json'))
    api.require(len(accounts)==10,'exact predecessor account inventory')
    for name,n in names.items():
        found=list((base/name).glob('*.accounting.json'))
        api.require(sum(api.read(x)['accepted_steps'] for x in found)==n,'resolved predecessor accepted steps')
        for x in found:
            raw=x.with_name(x.name.replace('.accounting.json','.xz'))
            api.require(api.read(x)['raw_sha256']==api.sha(raw),'predecessor original raw seal')
    api.require(53086+sum(names.values())==78488 and 78488+17000<=100000,'failure-inclusive preflight reservation')

def verify(d):
    old=api.read(previous.job.DESIGN);previous.verify(old);boundary.verify(api.read(boundary.DESIGN));w=api.read(WORK)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'fresh immutable preflight binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    api.require(d['cases']==old['cases'] and d['numerical_gates']==old['numerical_gates']==job.policy.GATES,'original six cases and gates')
    api.require(d['budget']==old['budget'] and d['budget']['workers']==6<=w['maximum_separately_frozen_parallel_preflight_workers'],'unchanged qualified parallel budget')
    api.require(d['preflight']==old['preflight'] and d['preflight']['maximum_new_steps']==17000 and not d['production_authorized'],'original bounded lifecycle tests only')
    api.require(d['maximum_unverified_segments_per_case']==old['maximum_unverified_segments_per_case'] and d['maximum_unverified_segments_total']==old['maximum_unverified_segments_total'],'unchanged backpressure')
    api.require(d['agent_work_end_utc']==w['work_end_utc'] and d['simulation_cutoff_utc']==w['simulation_cutoff_utc'] and d['final_audit_deadline_utc']==w['final_audit_deadline_utc'],'distinct explicit clocks')
    api.require(d['prior_recovery_steps']==78488 and 78488+17000<=w['cumulative_recovery_accepted_step_ceiling'],'bounded inclusive recovery ledger')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    api.require(raw_execute.__code__ is baseline.raw_execute.__code__ and q.campaign.code_sha(raw_execute)==d['integration_code_sha256'],'unchanged integration bytecode')
    for key in ('parent','fast','prior','deadline','capture','observer'):
        api.require(raw_execute.__globals__[key] is baseline.raw_execute.__globals__[key],'original integration dependency '+key)
    api.require(raw_execute.__globals__['codec'] is storage.codec and raw_execute.__globals__['DESIGN']==job.DESIGN,'explicit new transport and output bindings')
    storage.verify_bindings();affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])
job.verify=verify

def prepare():
    w=api.read(WORK);api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc']),'preparation cutoff');ledger()
    readiness=boundary.OUT.with_name('composed_readiness_audit_01')/'results.json'
    audit=api.read(readiness)
    api.require(audit['evidence_and_accounting_passed'] and api.read(readiness.parent/'completion.json')['results_sha256']==api.sha(readiness),'complete independent local evidence audit')
    available=(job.policy.utc(w['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    api.require(audit['resource_screen']['producer_only_hours_with_margin']<=available,'unchanged late-history screen recomputed against explicitly revised deadline; old failure preserved')
    br=api.read(boundary.OUT/'results.json')
    api.require(br['passed'] and br['new_accepted_steps']==3676 and br['cumulative_recovery_steps']==78488 and api.read(boundary.OUT/'completion.json')['results_sha256']==api.sha(boundary.OUT/'results.json'),'complete exact pending/split restart prerequisite')
    r=api.read(boundary.current.OUT/'results.json')
    api.require(r['passed'] and api.read(boundary.current.OUT/'completion.json')['results_sha256']==api.sha(boundary.current.OUT/'results.json'),'exact current hard prefix')
    available=(job.policy.utc(w['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    api.require(r['fine_transaction_hours_with_margin']<=available,'original hard-prefix gate with current time')
    old=api.read(previous.job.DESIGN);previous.verify(old);d=copy.deepcopy(old);d.pop('binding');d.pop('prior_stage196_steps')
    current=api.read(boundary.DESIGN)
    files=[Path(__file__),job.PREFLIGHT_SCRIPT,Path(previous.__file__),Path(candidate.__file__),Path(storage.__file__),Path(affinity.__file__)]
    inputs=[WORK,previous.job.DESIGN,boundary.DESIGN,boundary.OUT/'results.json',boundary.OUT/'completion.json',boundary.current.OUT/'results.json',boundary.current.OUT/'completion.json',readiness,readiness.parent/'completion.json']
    d.update(stage='Stage200 renewed-clock composed six-worker bounded lifecycle qualification',sources={**old['sources'],**current['sources'],**{str(x):api.sha(x) for x in files}},inputs={**old['inputs'],**current['inputs'],**{str(x):api.sha(x) for x in inputs}},
        agent_work_end_utc=w['work_end_utc'],simulation_cutoff_utc=w['simulation_cutoff_utc'],final_audit_deadline_utc=w['final_audit_deadline_utc'],prior_recovery_steps=78488,
        transport_serialization='Qualified exact canonical memo and uniquely owned fresh-decoder tree; all original byte hashes and prefix checks retained.',production_authorized=False,
        claim='Exact bounded numerical/storage/restart/process qualification only. Resource forecast and full observation remain unverified.')
    d['binding']=api.digest(d);job.commit(job.DESIGN,d);verify(d);print('COMPOSED_STACK_PROTOCOL',api.sha(job.DESIGN),flush=True)

def owned(mode,name=None):
    api.require(mode=='preflight','production disabled');d=api.read(job.DESIGN);verify(d)
    core=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=affinity.bind(core);root=job.root_for(mode)
    job.commit(root/((name or 'auditor')+'.affinity.json'),{**info,'design_sha256':api.sha(job.DESIGN),'argv':sys.argv,'utc':job.utc().isoformat()})

if __name__=='__main__':
    a=sys.argv[1:]
    if a==['prepare']:prepare()
    elif a==['supervise','preflight']:job.supervise('preflight')
    elif len(a)==3 and a[:2]==['worker','preflight']:owned(a[1],a[2]);job.worker(a[1],a[2])
    elif a==['auditor','preflight']:owned(a[1]);job.auditor(a[1])
    elif a==['evaluate','preflight']:job.evaluate(a[1])
    else:raise ValueError('prepare | supervise preflight | worker preflight CASE | auditor preflight | evaluate preflight')
