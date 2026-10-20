"""Separate source, sample, queue, ceiling, storage and revised-clock arithmetic."""
from pathlib import Path
from datetime import timedelta
from types import FunctionType
import copy,math,shutil,sys
import resource_normal_gap_v1 as s
api,job=s.api,s.job
sys.path.insert(0,str(s.ROOT/'stage200_staging'))
import audit_resource_schedule_v1 as old_queue
independent_queue=FunctionType(old_queue.independent_queue.__code__,{**old_queue.independent_queue.__globals__,'api':api},'independent_queue')
OUT=s.OUT.parent/'independent_01'

def run():
    w=s.prerequisites();p=api.read(s.PROTOCOL);r=s.pre.sealed(s.OUT/'results.json');floor=s.pre.sealed(s.FLOOR)
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'protocol seal');api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    api.require(r['calculation_passed'] and len(r['samples'])==30,'all fresh cost measurements')
    controls=0
    for slots in (1,2,3):
        for n in range(1,7):
            for rate in (.125,1.,20.):
                rows=[dict(records=3+i,producer_s=(i+1)*.5,auditor_s=rate) for i in range(n)]
                planned=s.schedule(rows,slots);clock,peak=independent_queue(rows,slots)
                api.require(clock==planned['seconds'] and peak==planned['maximum_outstanding_records'],'independent heterogeneous queue/backlog identity');controls+=1
    for x in r['samples']:
        raw=Path(x['raw']);e=Path(x['evidence']);api.require(api.sha(raw)==x['raw_sha256'] and raw.stat().st_size==x['bytes'] and api.sha(e)==x['evidence_sha256'],'actual measured archive and cost receipt seals')
        a=api.read(e)
        if x['kind']=='probe':
            z=a['summary'];expected=(a['case'],a['steps'],a['transaction_seconds'],z['audit_seconds'],z['stop_s']-z['start_s'])
        elif x['kind']=='live':
            mark=api.read(raw.with_name(raw.name.replace('.json.xz','.ready.json')));z=a['summary'];api.require(a['status']=='independently_verified' and mark['raw_sha256']==api.sha(raw),'actual live publication')
            expected=(a['case'],mark['steps'],mark['transaction_seconds'],z['audit_seconds'],z['stop_s']-z['start_s'])
        elif x['kind']=='local':
            a=s.pre.sealed(e);z=a['audit'];api.require(a['steps']==a['total_saved_steps']==a['independently_accepted_steps'] and a['numerical_audit_passed'],'closed local steps')
            expected=('s2_i124_sphere_f0p0625',a['steps'],a['transaction_seconds'],z['audit_seconds'],z['stop_s']-z['start_s'])
        else:raise AssertionError('unrecognized sample kind')
        api.require((x['case'],x['steps'],x['tx'],x['audit'],x['span'])==expected and z['passed'],'unscaled independently passing measured cost')
    api.require(sum(x['kind']=='probe' for x in r['samples'])==15 and sum(x['kind']=='live' for x in r['samples'])==12 and sum(x['kind']=='local' for x in r['samples'])==3,'exact sample provenance inventory')
    hist=s.pre.sealed(s.HISTORY);api.verify_mapping(hist['artifacts'])
    late={k:max(floor['late_history_cost'][k],max(z[v] for z in hist['measurements'])) for k,v in [('write','write_seconds'),('read','read_seconds'),('hash','state_hash_seconds'),('bytes','compressed_bytes')]}
    costs={shape:{k:max(floor['shape_costs'][shape][k],max(x[v]/x['steps'] for x in r['samples'] if '_'+shape+'_' in x['case'])) for k,v in [('tx_per_step','tx'),('audit_per_step','audit')]} for shape in ('fibre','sphere')}
    api.require(costs==r['shape_costs'] and late==r['late_history_cost'],'old shape and full-history cost floors retained')
    y=min(3650,floor['planning_segment_yield']);api.require(y==p['planning_segment_yield']==r['planning_segment_yield'],'old conservative wall-budget yield, no new cap construed as measured throughput')
    d=api.read(job.DESIGN);allrows=r['samples']+floor['samples'];bytes_per_step=max(x['bytes']/x['steps'] for x in allrows);cases=[];rawbytes=0;calls=True
    for c in d['cases']:
        dt=min(x['span']/x['steps'] for x in allrows if x['case']==c['id']);n=math.ceil(c['spec']['horizon_s']/dt)
        api.require(n<=c['step_ceiling'],'unchanged six-case exact horizon and step ceiling')
        cost=costs['fibre' if '_fibre_' in c['id'] else 'sphere'];count=math.ceil(n/y);cap=math.ceil(c['step_ceiling']/y)
        cases.append(dict(case=c['id'],planning_steps=n,records=count,ceiling_records=cap,producer_s=cost['tx_per_step']*y+late['write']+late['hash'],auditor_s=cost['audit_per_step']*y+late['read']+late['hash']+1.,source_step_seconds=dt))
        rawbytes+=c['step_ceiling']*bytes_per_step+cap*late['bytes'];calls &= cap<=d['budget']['max_calls_per_case']
    api.require(cases==r['cases'] and len(cases)==6,'independent complete case/ceiling accounting')
    seconds,peak=independent_queue(cases,3);api.require(seconds==r['queue']['seconds'] and peak==r['queue']['maximum_outstanding_records']<=6,'independent full fair three-slot single-auditor queue')
    hours=max(floor['production_hours_with_margin'],(seconds+600)*1.3/3600)
    audit=max(floor['required_final_audit_hours'],math.ceil((sum(c['records']*c['auditor_s'] for c in cases)+600)*1.3/3600))
    need=max(floor['storage_bytes_with_margin'],math.ceil((rawbytes+sum(c['step_ceiling'] for c in d['cases'])*13*8+sum(c['ceiling_records'] for c in cases)*8192+1024**3)*1.3))
    now=job.policy.utc(r['utc']);old_cutoff=job.policy.utc(w['original_simulation_cutoff_utc']);old_final=job.policy.utc(w['original_final_audit_deadline_utc'])
    available=(old_cutoff-now).total_seconds()/3600;earliest=now+timedelta(hours=hours+6);cutoff=earliest.replace(hour=18,minute=59,second=0,microsecond=0)
    if cutoff<earliest:cutoff+=timedelta(days=1)
    reserve=max((old_final-old_cutoff).total_seconds()/3600,audit);final=cutoff+timedelta(hours=reserve)
    storage=need+w['minimum_free_disk_bytes']<=r['free_D_bytes'];oldfit=bool(hours<=available and audit<=(old_final-old_cutoff).total_seconds()/3600 and storage and calls)
    fit=bool(calls and storage and (cutoff-now).total_seconds()/3600>=hours and reserve>=audit)
    expected={'production_hours_with_margin':hours,'required_final_audit_hours':audit,'storage_bytes_with_margin':need,'original_available_production_hours':available,
        'proposed_simulation_cutoff_utc':cutoff.isoformat(),'proposed_final_audit_deadline_utc':final.isoformat(),'reserved_final_audit_hours':reserve,
        'original_calendar_fit_passed':oldfit,'call_limit_passed':bool(calls),'resource_gate_passed':fit}
    def verify_fields(record):
        api.require(all(type(record[k]) is type(v) and record[k]==v for k,v in expected.items()),'independent original-margin deadlines/resource arithmetic')
    verify_fields(r);negative=[]
    for k,v in expected.items():
        bad=copy.deepcopy(r);bad[k]=not v if type(v) is bool else (v+1 if type(v) in (int,float) else 'corrupt')
        try:verify_fields(bad)
        except RuntimeError:negative.append(k)
        else:raise AssertionError('bad forecast arithmetic accepted')
    api.require(need+w['minimum_free_disk_bytes']<=shutil.disk_usage('D:/MATDEM_MICROPLASTIC').free and (cutoff-job.utc()).total_seconds()/3600>=hours,'current disk and revised calendar still fit')
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    result=dict(passed=True,new_trajectory_steps=0,independent_calculation_passed=True,resource_gate_passed=fit,original_calendar_fit_passed=oldfit,
        proposed_simulation_cutoff_utc=cutoff.isoformat(),proposed_final_audit_deadline_utc=final.isoformat(),production_hours_with_margin=hours,required_final_audit_hours=audit,
        reserved_final_audit_hours=reserve,storage_with_reserve_bytes=need+w['minimum_free_disk_bytes'],free_D_bytes=shutil.disk_usage('D:/MATDEM_MICROPLASTIC').free,
        independent_queue_controls=controls,negative_arithmetic_controls=negative,maximum_backlog=peak,source_sha256=api.sha(__file__),
        resource_result_sha256=api.sha(s.OUT/'results.json'),protocol_sha256=api.sha(s.PROTOCOL),production_authorized=False,clock_revision_not_yet_bound_to_production=True,utc=job.utc().isoformat())
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
    print('INDEPENDENT_NORMAL_GAP_RESOURCE',fit,hours,audit,cutoff.isoformat(),final.isoformat(),flush=True)
if __name__=='__main__':run()
