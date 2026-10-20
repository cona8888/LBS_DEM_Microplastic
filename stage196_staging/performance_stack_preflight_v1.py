"""Private six-performance-core preflight instance; production disabled.

Frozen Stage195 integration/lifecycle and numerical auditor are reused. Only
pure analytic evaluation, transport encoding, owned affinity, output location,
explicit qualification protocol and authorized worker count are different.
"""
from pathlib import Path
from types import FunctionType
import copy, importlib.util, os, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage195_staging'))
import repaired_stack_campaign_v1 as baseline
import constant_analytic_pair_v1 as opt
import lossless_compact_xz_v1 as storage
import owned_performance_affinity_v1 as affinity
q,api=baseline.q,baseline.api
spec=importlib.util.spec_from_file_location('_stage196_performance_lifecycle',q.campaign.qualified.instance.historical.__file__)
job=importlib.util.module_from_spec(spec);sys.modules[spec.name]=job;spec.loader.exec_module(job)
WORK=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/contract_01.json'
BASE='performance_stack_20260925'
job.ROOT=Path('D:/MATDEM_MICROPLASTIC')
job.SELF=Path(__file__).resolve();job.BASE=BASE
job.DESIGN=ROOT/'stage196_designs'/BASE/'design_01.json';job.WORK=WORK
job.PREFLIGHT=job.ROOT/'stage196_runs'/BASE/'preflight_01'
job.RUN=job.ROOT/'stage196_runs'/BASE/'production_not_authorized'
job.OUT=ROOT/'stage196_evaluations'/BASE
job.PREFLIGHT_SCRIPT=Path(__file__).with_name('qualify_performance_stack_v1.py')
job.codec=storage.codec;job.kernel=baseline.job.kernel;job.observer=baseline.job.observer
raw_execute=FunctionType(baseline.raw_execute.__code__,dict(job.__dict__),'execute_segment',baseline.raw_execute.__defaults__,baseline.raw_execute.__closure__)


def execute_segment(d,case,before,path,cap,prefix,stop):
    with opt.scope(True),baseline.repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):
        return raw_execute(d,case,before,path,cap,prefix,stop)


job.execute_segment=execute_segment


def verify(d):
    old=api.read(baseline.job.DESIGN);baseline.job.verify(old);w=api.read(WORK)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'new design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    api.require(d['cases']==old['cases'] and d['numerical_gates']==old['numerical_gates']==job.policy.GATES,'frozen cases and scientific gates')
    api.require({**d['budget'],'workers':3}==old['budget'] and d['budget']['workers']==6<=w['parallel_preflight_workers_maximum'],'only separately authorized worker count changes')
    api.require(not d['production_authorized'] and d['preflight']['maximum_new_steps']==17000,'bounded preflight only')
    api.require(d['maximum_unverified_segments_per_case']==old['maximum_unverified_segments_per_case'] and d['maximum_unverified_segments_total']==old['maximum_unverified_segments_total'],'unchanged backpressure')
    api.require(d['agent_work_end_utc']==w['work_end_utc'] and d['simulation_cutoff_utc']==w['simulation_cutoff_utc'] and d['final_audit_deadline_utc']==w['final_audit_deadline_utc'],'explicit separate clocks')
    api.require(d['prior_stage196_steps']==8326 and d['prior_stage196_steps']+17000<=w['maximum_new_qualification_accepted_steps'],'bounded cumulative qualification ledger')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    api.require(raw_execute.__code__ is baseline.raw_execute.__code__ and q.campaign.code_sha(raw_execute)==d['integration_code_sha256'],'unchanged integration code')
    for key in ('parent','fast','prior','deadline','capture','observer'):
        api.require(raw_execute.__globals__[key] is baseline.raw_execute.__globals__[key],'frozen integration dependency '+key)
    api.require(raw_execute.__globals__['codec'] is storage.codec and raw_execute.__globals__['DESIGN']==job.DESIGN,'explicit transport/output binding')
    storage.verify_bindings();affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])


job.verify=verify


def prepare():
    old=api.read(baseline.job.DESIGN);baseline.job.verify(old);w=api.read(WORK)
    api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc']),'preparation clock')
    prereqs=[ROOT/'stage196_evaluations/deadline_recovery_20260925'/s/'results.json' for s in ('combined_segments_01','constant_pair_01','compact_storage_01','owned_cpu_benchmark_01')]
    for path in prereqs:
        r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed qualification '+str(path))
        api.verify_mapping(r['inputs'])
        if 'artifacts' in r:api.verify_mapping(r['artifacts'])
    files=[Path(__file__),job.PREFLIGHT_SCRIPT,Path(opt.__file__),Path(storage.__file__),Path(storage.previous.__file__),Path(affinity.__file__),ROOT/'stage196_staging/windows_cpu_topology_v1.py']
    d=copy.deepcopy(old);d.pop('binding');d['budget']['workers']=6
    d.update(stage='Stage196 performance-core full-stack bounded qualification',
        sources={**old['sources'],**{str(p):api.sha(p) for p in files}},
        inputs={**old['inputs'],**{str(p):api.sha(p) for p in [WORK,baseline.job.DESIGN,*prereqs]}},
        agent_work_end_utc=w['work_end_utc'],simulation_cutoff_utc=w['simulation_cutoff_utc'],final_audit_deadline_utc=w['final_audit_deadline_utc'],
        preflight={'maximum_new_steps':17000,'wall_seconds':3600,'steps_per_live_segment':500,'segments_per_live_case':2,'contact_probe_steps':1000,
            'parallel_probe_steps':500,'parallel_probe_workers':6,'split_steps':[500,500],'fresh_controls':'first 200 live rows compared to frozen Stage195 controls'},
        worker_logical_cpus=[2,4,6,8,10,12],auditor_logical_cpu=14,prior_stage196_steps=8326,
        transport_serialization='compact JSON wrapper; unchanged original canonical reconstruction hashes',production_authorized=False,
        claim='Exact bounded algorithm/storage/affinity/process qualification only; no full-path result and no production permission from this preflight.')
    d['binding']=api.digest(d);job.commit(job.DESIGN,d);verify(d)
    print('PERFORMANCE_STACK_FROZEN',api.sha(job.DESIGN),flush=True)


def owned(mode,name=None):
    api.require(mode=='preflight','production deliberately disabled')
    d=api.read(job.DESIGN);verify(d)
    core=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=affinity.bind(core);root=job.root_for(mode)
    job.commit(root/((name or 'auditor')+'.affinity.json'),{**info,'design_sha256':api.sha(job.DESIGN),'argv':sys.argv,'utc':job.utc().isoformat()})


if __name__=='__main__':
    a=sys.argv[1:]
    if a==['prepare']:prepare()
    elif len(a)==2 and a[0]=='supervise':
        api.require(a[1]=='preflight','production disabled');job.supervise(a[1])
    elif len(a)==3 and a[0]=='worker':owned(a[1],a[2]);job.worker(a[1],a[2])
    elif len(a)==2 and a[0]=='auditor':owned(a[1]);job.auditor(a[1])
    elif len(a)==2 and a[0]=='evaluate':
        api.require(a[1]=='preflight','production disabled');job.evaluate(a[1])
    else:raise ValueError('prepare | supervise preflight | worker preflight CASE | auditor preflight | evaluate preflight')
