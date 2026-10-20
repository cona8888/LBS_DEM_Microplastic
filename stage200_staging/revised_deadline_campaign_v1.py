"""Fresh original six-case campaign after the composed-stack qualification.

Only output, clocks, measured resources, and safe producer concurrency differ
from the tested lifecycle. Three producers x two pending records preserves the
original six-record audit backlog bound. Scientific code and gates are frozen.
"""
from pathlib import Path
from types import FunctionType
import copy,importlib.util,os,sys,psutil
import revised_stack_preflight_v1 as pre
api,q,ROOT=pre.api,pre.q,pre.ROOT
spec=importlib.util.spec_from_file_location('_stage200_fresh_production_lifecycle',pre.job.__file__)
job=importlib.util.module_from_spec(spec);sys.modules[spec.name]=job;spec.loader.exec_module(job)
BASE='revised_deadline_campaign_20260927'
job.ROOT=Path('D:/MATDEM_MICROPLASTIC');job.SELF=Path(__file__).resolve();job.BASE=BASE
job.DESIGN=ROOT/'stage200_designs'/BASE/'design_01.json'
job.RUN=job.ROOT/'stage200_runs'/BASE/'run_01'
job.PREFLIGHT=job.ROOT/'stage200_runs'/BASE/'not_authorized'
job.OUT=ROOT/'stage200_evaluations'/BASE
job.WORK=ROOT/'stage200_designs/deadline_revision_20260927/authorization_01.json'
job.PREFLIGHT_SCRIPT=pre.job.PREFLIGHT_SCRIPT
job.codec=pre.storage.codec;job.kernel=pre.job.kernel;job.observer=pre.job.observer
raw_execute=FunctionType(pre.raw_execute.__code__,dict(job.__dict__),'execute_segment',pre.raw_execute.__defaults__,pre.raw_execute.__closure__)
AUDIT=pre.job.OUT/'independent_readiness_01/results.json'
RESOURCE=pre.job.OUT/'resource_schedule_01/results.json'
RESOURCE_AUDIT=pre.job.OUT/'resource_independent_01/results.json'
BRIDGE=job.OUT/'qualification_bridge_01'
ALLOWED={'stage','sources','inputs','binding','budget','agent_work_end_utc','simulation_cutoff_utc','final_audit_deadline_utc','resource_scenario','production_authorized','claim','guard','qualification_inheritance','provenance_transaction_hours_with_margin','provenance_bytes_with_margin'}
IDENTICAL=('worker','auditor','audit_one','evaluate','stopping','acknowledged','binding','commit','root_settings','start_child','paths','supervise')

def execute_segment(d,case,before,path,cap,prefix,stop):
    pre.candidate.warm()
    with pre.candidate.scope('compiled_direct'),pre.baseline.repair.scope(job.parent.engine.runtime,True,job.policy.utc(stop).timestamp()):
        return raw_execute(d,case,before,path,cap,prefix,stop)
job.execute_segment=execute_segment

def sealed(path):
    r=api.read(path);api.require(api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed prerequisite '+str(path));return r

def equivalence(d):
    old=api.read(pre.job.DESIGN);pre.verify(old);w=api.read(job.WORK);resource=sealed(RESOURCE)
    changed={k for k in set(d)|set(old) if d.get(k)!=old.get(k)}
    api.require(changed<=ALLOWED,'only declared administrative and resource changes')
    api.require({**d['budget'],'workers':6}==old['budget'] and d['budget']['workers']==resource['production_workers']==3,'three slots; all original caps unchanged')
    api.require(d['maximum_unverified_segments_per_case']*d['budget']['workers']<=d['maximum_unverified_segments_total']==6,'enforced six-record bound by dispatch capacity')
    api.require(d['simulation_cutoff_utc']==resource['simulation_cutoff_utc'] and d['final_audit_deadline_utc']==d['agent_work_end_utc']==resource['final_audit_deadline_utc'],'new measured schedule bound to production')
    api.require(d['cases']==old['cases'] and d['numerical_gates']==old['numerical_gates']==job.policy.GATES,'all six original cases and gates')
    api.require(d['production_authorized'] and d['fresh_start_required'] and not d['physical_changes'],'fresh unchanged physical model only')
    api.require(d['resource_scenario']==resource and d['provenance_transaction_hours_with_margin']==resource['hours_with_margin'] and d['provenance_bytes_with_margin']==resource['bytes_with_margin'],'one explicit complete measured resource scenario')
    api.require(all(d['sources'].get(p)==h for p,h in old['sources'].items()) and all(d['inputs'].get(p)==h for p,h in old['inputs'].items()),'all inherited frozen sources and inputs preserved')
    api.require(d['sources'].get(str(job.SELF))==api.sha(job.SELF) and d['inputs'].get(str(job.WORK))==api.sha(job.WORK),'current launcher and user authority bound')
    api.require(d['qualification_inheritance']=={'design_sha256':api.sha(pre.job.DESIGN),'preflight_result_sha256':api.sha(pre.job.OUT/'preflight_01/results.json'),'independent_result_sha256':api.sha(AUDIT),'new_qualification_steps_in_bridge':0,'preflight_steps':17000,'cumulative_recovery_steps':95488},'exact disclosed qualification ledger and lineage')
    proofs={}
    for name in IDENTICAL:
        a,b=getattr(job,name),getattr(pre.job,name)
        api.require(a.__code__==b.__code__ and q.campaign.code_sha(a)==q.campaign.code_sha(b),'identical lifecycle '+name);proofs[name]=q.campaign.code_sha(a)
    api.require(raw_execute.__code__ is pre.raw_execute.__code__ and q.campaign.code_sha(raw_execute)==d['integration_code_sha256'],'identical integration code')
    for key in ('parent','fast','prior','deadline','capture','observer'):
        api.require(raw_execute.__globals__[key] is pre.raw_execute.__globals__[key],'same physical dependency '+key)
    api.require(raw_execute.__globals__['codec'] is pre.storage.codec and raw_execute.__globals__['DESIGN']==job.DESIGN,'explicit new evidence binding')
    api.require(job.kernel is pre.job.kernel and job.codec is pre.job.codec and job.observer is pre.job.observer,'same qualified auditor codec observer')
    pre.storage.verify_bindings();pre.affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])
    return changed,proofs

def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'production design binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS/OpenMP1')
    equivalence(d)
job.verify=verify

def inherited():
    old=api.read(pre.job.DESIGN);pre.verify(old);r=pre.job.verify_preflight(old);a=sealed(AUDIT);ra=sealed(RESOURCE_AUDIT)
    api.require(r['new_steps']==17000 and r['cumulative_recovery_steps']==95488,'complete inclusive bounded qualification ledger')
    api.require(a['numerical_qualification_passed'] and a['process_qualification_passed'] and a['raw_records_independently_decoded']==35 and len(a['numerical_reaudits'])==27 and a['all_owned_processes_retired'],'full independently decoded and numerically audited preflight')
    api.require(ra['passed'] and ra['resource_result_sha256']==api.sha(RESOURCE),'independent complete resource audit')
    return r

def verify_preflight(d):
    verify(d);r=inherited();b=sealed(BRIDGE/'results.json')
    api.require(b['passed'] and b['design_sha256']==api.sha(job.DESIGN) and b['source_sha256']==api.sha(__file__) and b['function_identity_sha256']==equivalence(d)[1],'exact preflight inheritance bridge')
    return {**r,'refreshed_hours_with_margin':sealed(RESOURCE)['hours_with_margin']}
job.verify_preflight=verify_preflight

def resource_gate(d):
    verify_preflight(d);r=sealed(RESOURCE);available=(job.policy.utc(d['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    free=job.shutil.disk_usage(job.ROOT).free;need=r['bytes_with_margin']+d['budget']['minimum_free_disk_bytes']
    api.require(r['resource_gate_passed'] and available>=r['hours_with_margin'],'complete queue forecast fits revised deadline')
    api.require(free>=need,'full-ceiling storage with original margin and reserve')
    return dict(required_hours=r['hours_with_margin'],available_hours=available,required_storage_with_reserve_bytes=need,free_bytes=free,producer_workers=3)

def prepare():
    api.require(not job.RUN.exists() and not job.DESIGN.exists(),'one fresh exclusive campaign')
    r=inherited();resource=sealed(RESOURCE);d=copy.deepcopy(api.read(pre.job.DESIGN));d.pop('binding')
    d['budget']['workers']=3
    files=[Path(__file__),Path(pre.__file__),ROOT/'stage200_staging/resource_schedule_v1.py',ROOT/'stage200_staging/audit_resource_schedule_v1.py']
    inputs=[job.WORK,pre.job.DESIGN,AUDIT,AUDIT.parent/'completion.json',RESOURCE,RESOURCE.parent/'completion.json',RESOURCE_AUDIT,RESOURCE_AUDIT.parent/'completion.json',pre.job.OUT/'preflight_01/results.json',pre.job.OUT/'preflight_01/completion.json',ROOT/'stage200_designs/deadline_revision_20260927/authorization_clock_erratum_01.json']
    d.update(stage='Stage200 fresh original six-case campaign with measured revised deadline',sources={**d['sources'],**{str(x):api.sha(x) for x in files}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},simulation_cutoff_utc=resource['simulation_cutoff_utc'],final_audit_deadline_utc=resource['final_audit_deadline_utc'],agent_work_end_utc=resource['final_audit_deadline_utc'],resource_scenario=resource,production_authorized=True,provenance_transaction_hours_with_margin=resource['hours_with_margin'],provenance_bytes_with_margin=resource['bytes_with_margin'],qualification_inheritance={'design_sha256':api.sha(pre.job.DESIGN),'preflight_result_sha256':api.sha(pre.job.OUT/'preflight_01/results.json'),'independent_result_sha256':api.sha(AUDIT),'new_qualification_steps_in_bridge':0,'preflight_steps':17000,'cumulative_recovery_steps':95488},guard='Fresh only; exact qualified integration and original lifecycle; three producers guarantee original six-record backlog bound; original resource and scientific gates retained.',claim='Two labelled placements reported separately; full fresh common-clock comparisons required. No population release estimate or empirical validation.')
    d['binding']=api.digest(d);verify(d);changed,proofs=equivalence(d)
    rejects=[]
    mutations=[('cases',lambda x:x['cases'].pop()),('step',lambda x:x['cases'][0].update(factor=1)),('gates',lambda x:x['numerical_gates'].update(whole_position_over_b_max=.1)),('concurrency',lambda x:x['budget'].update(workers=6)),('budget',lambda x:x['budget'].update(step_cap_per_call=20000)),('deadline',lambda x:x.update(simulation_cutoff_utc='2030-01-01T00:00:00+00:00')),('lineage',lambda x:x['sources'].pop(next(iter(api.read(pre.job.DESIGN)['sources']))))]
    for label,mutate in mutations:
        bad=copy.deepcopy(d);mutate(bad)
        try:equivalence(bad)
        except (ValueError,RuntimeError,AssertionError):rejects.append(label)
        else:raise AssertionError('accepted corrupt amendment '+label)
    # Original pure dispatch/retire functions: every retirement permutation keeps
    # at most3 active workers, and stops all new dispatch following a failure.
    import itertools
    checks=0
    for order in itertools.permutations([c['id'] for c in d['cases']]):
        life=job.policy.initial([c['id'] for c in d['cases']]);remaining=list(order)
        while life.queued or life.active:
            while True:
                life,name=job.policy.dispatch(life,3,True)
                if name is None:break
                api.require(len(life.active)*2<=6,'dispatch backlog invariant')
            name=next(n for n in remaining if n in life.active);remaining.remove(name);life=job.policy.retire(life,name,0,True)
        api.require(len(life.retired)==6 and not life.stop_reasons,'all cases retired');checks+=1
    job.commit(job.DESIGN,d)
    result=dict(passed=True,design_sha256=api.sha(job.DESIGN),source_sha256=api.sha(__file__),changed_fields=sorted(changed),function_identity_sha256=proofs,corrupt_amendments_rejected=rejects,zero_step_dispatch_permutations=checks,new_trajectory_steps=0,preflight_reused_not_rerun=True,preflight_steps=17000,cumulative_recovery_steps=95488,producer_workers=3,backlog_bound=6,six_worker_preflight_scope='Numerical/process contention evidence; legacy global backlog metadata was not a semaphore. Production restores its literal bound through3slots.',utc=job.utc().isoformat())
    job.commit(BRIDGE/'results.json',result);job.commit(BRIDGE/'completion.json',{'passed':True,'results_sha256':api.sha(BRIDGE/'results.json')});print('CAMPAIGN_READY',api.sha(job.DESIGN),resource_gate(d),flush=True)

def owned(mode,name=None):
    api.require(mode=='campaign','no new qualification under production launcher');d=api.read(job.DESIGN);verify(d)
    core=d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i,c in enumerate(d['cases']) if c['id']==name)]
    info=pre.affinity.bind(core);job.commit(job.RUN/((name or 'auditor')+'.affinity.json'),{**info,'design_sha256':api.sha(job.DESIGN),'argv':sys.argv,'utc':job.utc().isoformat()})

if __name__=='__main__':
    args=sys.argv[1:]
    if args==['prepare']:prepare()
    elif args==['check']:print(resource_gate(api.read(job.DESIGN)),flush=True)
    elif args==['supervise','campaign']:
        resource_gate(api.read(job.DESIGN))
        for proc in psutil.process_iter(['pid','name','cmdline']):
            if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'no duplicate owned simulation')
        job.supervise('campaign')
    elif len(args)==3 and args[:2]==['worker','campaign']:owned('campaign',args[2]);job.worker('campaign',args[2])
    elif args==['auditor','campaign']:owned('campaign');job.auditor('campaign')
    elif args==['evaluate','campaign']:job.evaluate('campaign')
    else:raise ValueError('prepare | check | supervise campaign | worker campaign CASE | auditor campaign | evaluate campaign')
