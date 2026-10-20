"""Conservative measured six-case resource fit; same deadlines/margins/queue."""
from pathlib import Path
import math,shutil,sys
import cone_feasibility_stack_preflight_v1 as pre
import resource_schedule_v1 as old
api,job=pre.api,pre.job
BASE=job.OUT/'resource_schedule_01'
PROTOCOL=pre.WORK.with_name('resource_protocol_01.json')
FLOOR=pre.ROOT/'stage205_evaluations/receipt_repaired_campaign_20260930/resource_schedule_01/results.json'
HISTORY=old.HISTORY

def prepare():
    d=api.read(job.DESIGN);job.verify(d);ready=pre.sealed(job.OUT/'independent_readiness_01/results.json')
    api.require(ready['numerical_qualification_passed'] and ready['process_qualification_passed'] and ready['stage208_preflight_steps_verified']==17000,'fresh independent full stack')
    calls=[pre.LOCAL/n/'results.json' for n in ('serial_01','split_a_01','split_b_01','extension_a_01','extension_b_01','extension_c_01','extension_d_01')]
    p=dict(new_trajectory_steps=0,producer_slots=3,per_case_outstanding_limit=2,global_outstanding_limit=6,runtime_margin=1.3,storage_margin=1.3,startup_seconds=600,per_receipt_allowance_s=1.,planning_segment_yield=min(3650,min(pre.sealed(x)['steps'] for x in calls if pre.sealed(x)['status']=='incomplete_budget')),inputs={str(x):api.sha(x) for x in [job.DESIGN,pre.WORK,job.OUT/'preflight_01/results.json',job.OUT/'independent_readiness_01/results.json',pre.CLOSE,FLOOR,HISTORY]+calls},sources={str(x):api.sha(x) for x in (Path(__file__),Path(__file__).with_name('audit_resource_cone_stack_v1.py'),Path(old.__file__))},rule='Retain old worst-within-shape producer/audit cost floors, all new measured costs, smallest observed wall-budget yield, late-history cost, original full ceiling storage, fair three-slot/global-six queue and1.3 margins. No assumed speedup, early release or deadline change.')
    p['binding']=api.digest(p);job.commit(PROTOCOL,p);print('CONE_RESOURCE_PROTOCOL',p['planning_segment_yield'],flush=True)

def run():
    d=api.read(job.DESIGN);job.verify(d);p=api.read(PROTOCOL);api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'resource protocol');api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    samples=[]
    def add(case,steps,tx,audit,span,raw):
        raw=Path(raw);api.require(steps>0 and span>0,'positive measured cost span')
        samples.append(dict(case=case,steps=steps,tx=tx,audit=audit,span=span,raw=str(raw),raw_sha256=api.sha(raw),bytes=raw.stat().st_size))
    for path in sorted((job.PREFLIGHT/'probes').glob('*.preflight_audit.json')):
        r=api.read(path);s=r['summary'];api.require(s['passed'] and r['raw_sha256']==api.sha(r['path']),'sealed probe')
        add(r['case'],r['steps'],r['transaction_seconds'],s['audit_seconds'],s['stop_s']-s['start_s'],r['path'])
    for c in d['cases']:
        for index in (1,2):
            paths=job.paths(job.root_for('preflight'),c['id'],index);mark=api.read(paths['ready']);receipt=api.read(paths['receipt']);s=receipt['summary']
            api.require(receipt['status']=='independently_verified' and s['passed'] and mark['raw_sha256']==api.sha(paths['raw']),'sealed live record')
            add(c['id'],mark['steps'],mark['transaction_seconds'],s['audit_seconds'],s['stop_s']-s['start_s'],paths['raw'])
    for name in ('serial_01','split_a_01','split_b_01','extension_a_01','extension_b_01','extension_c_01','extension_d_01'):
        folder=pre.LOCAL/name;r=pre.sealed(folder/'results.json');api.require(r['numerical_audit_passed'] and r['rejected']==0,'passing bounded local measurement');api.verify_mapping(r['artifacts'])
        plan=api.read(pre.ROOT/'stage207_designs/feasibility_trajectory_20260930'/(name+'.json'))
        seed=pre.LOCAL/plan['seed'] if plan['seed'] else pre.RECON
        before=api.read(seed/('checkpoint.json' if plan['seed'] else 'checkpoint_00227.json'))['state']['t']
        add(d['stress_case'],r['steps'],r['transaction_seconds'],r['audit']['audit_seconds'],r['time_s']-before,folder/'call.json.xz')
    api.require(len(samples)==34,'all27 full-stack and7 local measurements')
    floor=pre.sealed(FLOOR);hist=pre.sealed(HISTORY);api.verify_mapping(hist['artifacts'])
    late={k:max(x[v] for x in hist['measurements']) for k,v in [('write','write_seconds'),('read','read_seconds'),('hash','state_hash_seconds'),('bytes','compressed_bytes')]}
    costs={shape:{k:max(floor['shape_costs'][shape][k],max(x[v]/x['steps'] for x in samples if '_'+shape+'_' in x['case'])) for k,v in [('tx_per_step','tx'),('audit_per_step','audit')]} for shape in ('fibre','sphere')}
    all_samples=samples+floor['samples'];perbyte=max(x['bytes']/x['steps'] for x in all_samples);cases=[];raw_storage=0;calls=True;yield_steps=p['planning_segment_yield']
    for c in d['cases']:
        dt=min(x['span']/x['steps'] for x in all_samples if x['case']==c['id']);steps=math.ceil(c['spec']['horizon_s']/dt);api.require(steps<=c['step_ceiling'],'original ceiling')
        cost=costs['fibre' if '_fibre_' in c['id'] else 'sphere'];records=math.ceil(steps/yield_steps);ceiling=math.ceil(c['step_ceiling']/yield_steps)
        cases.append(dict(case=c['id'],planning_steps=steps,records=records,ceiling_records=ceiling,producer_s=cost['tx_per_step']*yield_steps+late['write']+late['hash'],auditor_s=cost['audit_per_step']*yield_steps+late['read']+late['hash']+p['per_receipt_allowance_s'],source_step_seconds=dt))
        raw_storage+=c['step_ceiling']*perbyte+ceiling*late['bytes'];calls &= ceiling<=d['budget']['max_calls_per_case']
    queue=old.schedule(cases,3);hours=(queue['seconds']+600)*1.3/3600;audit_hours=math.ceil((sum(c['records']*c['auditor_s'] for c in cases)+600)*1.3/3600)
    need=math.ceil((raw_storage+sum(c['step_ceiling'] for c in d['cases'])*13*8+sum(c['ceiling_records'] for c in cases)*8192+1024**3)*1.3)
    now=job.utc();available=(job.policy.utc(d['simulation_cutoff_utc'])-now).total_seconds()/3600;reserve=(job.policy.utc(d['final_audit_deadline_utc'])-job.policy.utc(d['simulation_cutoff_utc'])).total_seconds()/3600;free=shutil.disk_usage('D:/MATDEM_MICROPLASTIC').free
    passed=hours<=available and audit_hours<=reserve and need+d['budget']['minimum_free_disk_bytes']<=free and calls
    result=dict(calculation_passed=True,resource_gate_passed=bool(passed),new_trajectory_steps=0,production_authorized=False,production_hours_with_margin=hours,available_production_hours=available,required_final_audit_hours=audit_hours,available_final_audit_hours=reserve,storage_bytes_with_margin=need,minimum_reserve_bytes=d['budget']['minimum_free_disk_bytes'],free_D_bytes=free,call_limit_passed=bool(calls),samples=samples,cases=cases,shape_costs=costs,late_history_cost=late,queue=queue,planning_segment_yield=yield_steps,protocol_sha256=api.sha(PROTOCOL),utc=now.isoformat(),claim='Conservative measured planning, not a hard runtime guarantee or permission to alter scientific gates.')
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    job.commit(BASE/'results.json',result);job.commit(BASE/'completion.json',dict(passed=True,results_sha256=api.sha(BASE/'results.json')))
    print('CONE_RESOURCE_FIT',passed,hours,available,audit_hours,reserve,flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
