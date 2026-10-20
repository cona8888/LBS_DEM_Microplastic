"""Fixed-deadline, zero-step full six-case cost reassessment; no launch."""
from pathlib import Path
import math,shutil
import contact_repaired_stack_preflight_v1 as pre
import resource_schedule_v1 as old
job,api=pre.job,pre.api
OUT=job.OUT/'resource_reassessment_01'
PROTOCOL=pre.ROOT/'stage202_designs/full_stack_20260928/resource_protocol_01.json'


def sealed(p):
    r=api.read(p);api.require(api.read(p.parent/'completion.json')['results_sha256']==api.sha(p),'sealed resource input '+str(p));return r


def prepare():
    d=api.read(job.DESIGN);job.verify(d);ready=sealed(job.OUT/'independent_readiness_02/results.json')
    api.require(ready['numerical_qualification_passed'] and ready['process_qualification_passed'],'complete independent preflight first')
    audit_source=Path(__file__).with_name('audit_contact_repaired_stack_v2.py')
    identity=job.OUT/'independent_readiness_02/retirement_identity.json'
    api.require(api.sha(audit_source)==ready['source_sha256'] and api.sha(identity)==ready['retirement_identity_sha256'],'independent audit source and identity receipt unchanged')
    api.verify_mapping(api.read(identity)['inputs'])
    files=[job.DESIGN,pre.WORK,job.OUT/'preflight_01/results.json',job.OUT/'independent_readiness_02/results.json',old.FINE,old.HISTORY,pre.CLOSE,old.OUT/'results.json']
    files += [pre.local.RUNBASE/f'polish_extension_call{i:02d}_01/results.json' for i in (1,2,3)]
    for f in files[2:]:api.require(api.read(f.parent/'completion.json')['results_sha256']==api.sha(f),'input completion seal')
    p={'new_trajectory_steps':0,'producer_slots':3,'per_case_outstanding_limit':2,'global_outstanding_limit':6,'runtime_margin':1.3,'storage_margin':1.3,'startup_seconds':600,'per_receipt_allowance_s':1.,
       'planning_segment_yield':3650,'yield_basis':'Minimum of prior4915 and the two full-budget Stage201 v4 extension yields3756/3650; final capped2594 call excluded from yield estimate, retained in measured costs.',
       'fixed_simulation_cutoff_utc':d['simulation_cutoff_utc'],'fixed_final_audit_deadline_utc':d['final_audit_deadline_utc'],
       'rule':'Retain previous worst-within-shape producer/auditor costs, 80,000-row history overhead, fair three-slot queue, full step-ceiling storage and1.3 margins. Add new preflight and local repaired-contact measurements. Do not choose a new deadline, scale costs by an optimization ratio or assume early release.',
       'inputs':{str(f):api.sha(f) for f in files},'sources':{str(f):api.sha(f) for f in (Path(__file__),Path(old.__file__),audit_source,Path(__file__).with_name('audit_resource_reassessment_v1.py'),pre.ROOT/'stage200_staging/audit_resource_schedule_v1.py')}}
    p['binding']=api.digest(p);job.commit(PROTOCOL,p);print('RESOURCE_PROTOCOL',api.sha(PROTOCOL),flush=True)


def run():
    p=api.read(PROTOCOL);api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'resource binding');api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    d=api.read(job.DESIGN);job.verify(d);pf=sealed(job.OUT/'preflight_01/results.json');api.verify_mapping(pf['artifacts'])
    samples=[]
    def add(case,n,tx,audit,span,raw):
        raw=Path(raw);api.require(n>0 and span>0,'nonzero resource sample')
        samples.append({'case':case,'steps':n,'tx':tx,'audit':audit,'span':span,'raw':str(raw),'raw_sha256':api.sha(raw),'bytes':raw.stat().st_size})
    for path in sorted((job.PREFLIGHT/'probes').glob('*.preflight_audit.json')):
        r=api.read(path);s=r['summary'];api.require(s['passed'] and r['raw_sha256']==api.sha(r['path']),'bound passing probe')
        add(r['case'],r['steps'],r['transaction_seconds'],s['audit_seconds'],s['stop_s']-s['start_s'],r['path'])
    for c in d['cases']:
        for i in (1,2):
            paths=job.paths(job.root_for('preflight'),c['id'],i);mark=api.read(paths['ready']);receipt=api.read(paths['receipt']);s=receipt['summary']
            api.require(s['passed'] and receipt['status']=='independently_verified' and mark['raw_sha256']==api.sha(paths['raw']),'bound live sample')
            add(c['id'],mark['steps'],mark['transaction_seconds'],s['audit_seconds'],s['stop_s']-s['start_s'],paths['raw'])
    fine=sealed(old.FINE);api.verify_mapping(fine['artifacts'])
    add('s2_i0_fibre_f0p03125',fine['new_accepted_steps'],fine['transaction_seconds'],fine['audit']['audit_seconds'],fine['simulated_seconds'],old.pre.boundary.current.RUN/'serial.json.xz')
    before=api.read(pre.local.RUNBASE/'polish_long_01/checkpoint.json')['state']['t']
    for i in (1,2,3):
        folder=pre.local.RUNBASE/f'polish_extension_call{i:02d}_01';r=sealed(folder/'results.json');api.verify_mapping(r['artifacts']);api.require(r['numerical_audit_passed'] and r['rejected']==0,'passing local extension cost')
        add(pre.local.source.NAME,r['steps'],r['transaction_seconds'],r['audit']['audit_seconds'],r['time_s']-before,folder/'call.json.xz');before=r['time_s']
    api.require(len(samples)==31,'all27 preflight, one inherited fine, three repaired-contact samples')
    history=sealed(old.HISTORY);api.require(history['passed'],'same qualified late-history codec');api.verify_mapping(history['artifacts'])
    late={k:max(x[v] for x in history['measurements']) for k,v in [('write','write_seconds'),('read','read_seconds'),('hash','state_hash_seconds'),('bytes','compressed_bytes')]}
    costs={}
    # Include the prior accepted schedule's maxima as a conservative floor:
    # the numerical repair does not establish a general speedup elsewhere.
    prior=sealed(old.OUT/'results.json')
    for shape in ('fibre','sphere'):
        rows=[s for s in samples if '_'+shape+'_' in s['case']]
        costs[shape]={k:max(prior['shape_costs'][shape][k],max(s[v]/s['steps'] for s in rows)) for k,v in [('tx_per_step','tx'),('audit_per_step','audit')]}
    bytes_per_step=max(max(s['bytes']/s['steps'] for s in samples),max(s['bytes']/s['steps'] for s in prior['samples']))
    cases=[];raw_storage=0;calls_fit=True
    for c in d['cases']:
        dt=min(s['span']/s['steps'] for s in samples if s['case']==c['id']);n=math.ceil(c['spec']['horizon_s']/dt)
        api.require(n<=c['step_ceiling'],'unchanged case ceiling');cost=costs['fibre' if '_fibre_' in c['id'] else 'sphere'];count=math.ceil(n/p['planning_segment_yield']);ceiling=math.ceil(c['step_ceiling']/p['planning_segment_yield'])
        cases.append({'case':c['id'],'planning_steps':n,'records':count,'ceiling_records':ceiling,'producer_s':cost['tx_per_step']*p['planning_segment_yield']+late['write']+late['hash'],'auditor_s':cost['audit_per_step']*p['planning_segment_yield']+late['read']+late['hash']+p['per_receipt_allowance_s'],'source_step_seconds':dt})
        raw_storage+=c['step_ceiling']*bytes_per_step+ceiling*late['bytes'];calls_fit &= ceiling<=d['budget']['max_calls_per_case']
    checks=old.tests();queue=old.schedule(cases,3);hours=(queue['seconds']+p['startup_seconds'])*p['runtime_margin']/3600
    audit_hours=math.ceil((sum(c['records']*c['auditor_s'] for c in cases)+p['startup_seconds'])*p['runtime_margin']/3600)
    total_steps=sum(c['step_ceiling'] for c in d['cases']);need=math.ceil((raw_storage+total_steps*13*8+sum(c['ceiling_records'] for c in cases)*8192+1024**3)*p['storage_margin'])
    now=job.utc();available=(job.policy.utc(d['simulation_cutoff_utc'])-now).total_seconds()/3600;audit_available=(job.policy.utc(d['final_audit_deadline_utc'])-job.policy.utc(d['simulation_cutoff_utc'])).total_seconds()/3600
    free=shutil.disk_usage('D:/MATDEM_MICROPLASTIC').free
    result={'calculation_passed':True,'resource_gate_passed':hours<=available and audit_hours<=audit_available and need+d['budget']['minimum_free_disk_bytes']<=free and calls_fit,
       'production_hours_with_margin':hours,'available_production_hours':available,'required_final_audit_hours':audit_hours,'available_final_audit_hours':audit_available,'storage_bytes_with_margin':need,'free_D_bytes':free,'minimum_reserve_bytes':d['budget']['minimum_free_disk_bytes'],'call_limit_passed':bool(calls_fit),
       'samples':samples,'cases':cases,'shape_costs':costs,'late_history_cost':late,'queue':queue,'schedule_tests':checks,'new_trajectory_steps':0,'protocol_sha256':api.sha(PROTOCOL),'utc':now.isoformat(),
       'claim':'Conservative measured-regime planning, not a hard runtime bound or completion promise. Fixed deadlines not revised. Unresolved Stage200 terminal audit remains separate. No production launch.'}
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('RESOURCE_FIXED_DEADLINE',result['resource_gate_passed'],hours,available,'audit',audit_hours,audit_available,flush=True)
if __name__=='__main__':
    import sys
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
