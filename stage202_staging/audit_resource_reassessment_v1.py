"""Independent queue and cost arithmetic; a failed deadline gate stays failed."""
from pathlib import Path
import math
import resource_reassessment_v1 as s
import audit_resource_schedule_v1 as independent
job,api=s.job,s.api
OUT=job.OUT/'resource_independent_01'
def run():
    p=api.read(s.PROTOCOL);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);r=s.sealed(s.OUT/'results.json');d=api.read(job.DESIGN);job.verify(d)
    samples=r['samples'];prior=s.sealed(s.old.OUT/'results.json');api.require(len(samples)==31 and r['calculation_passed'],'complete planning input inventory')
    for sample in samples:api.require(api.sha(sample['raw'])==sample['raw_sha256'] and Path(sample['raw']).stat().st_size==sample['bytes'],'actual raw sample seal/size')
    costs={shape:{key:max(prior['shape_costs'][shape][key],max(x[value]/x['steps'] for x in samples if '_'+shape+'_' in x['case'])) for key,value in [('tx_per_step','tx'),('audit_per_step','audit')]} for shape in ('fibre','sphere')}
    api.require(costs==r['shape_costs'],'retained worst-within-shape floor and new measurements')
    hist=s.sealed(s.old.HISTORY);late={k:max(x[v] for x in hist['measurements']) for k,v in [('write','write_seconds'),('read','read_seconds'),('hash','state_hash_seconds'),('bytes','compressed_bytes')]}
    api.require(late==r['late_history_cost'] and p['planning_segment_yield']==min(4915,3756,3650),'complete late-history and observed yield allowance')
    perbyte=max(x['bytes']/x['steps'] for x in samples+prior['samples']);raw=0;cases=[];calls=True
    for c in d['cases']:
        dt=min(x['span']/x['steps'] for x in samples if x['case']==c['id']);steps=math.ceil(c['spec']['horizon_s']/dt);cost=costs['fibre' if '_fibre_' in c['id'] else 'sphere'];count=math.ceil(steps/3650);cap=math.ceil(c['step_ceiling']/3650)
        cases.append(dict(case=c['id'],planning_steps=steps,records=count,ceiling_records=cap,producer_s=cost['tx_per_step']*3650+late['write']+late['hash'],auditor_s=cost['audit_per_step']*3650+late['read']+late['hash']+1.,source_step_seconds=dt))
        raw+=c['step_ceiling']*perbyte+cap*late['bytes'];calls &= cap<=d['budget']['max_calls_per_case']
    api.require(cases==r['cases'],'independent six-case cost arithmetic')
    secs,peak=independent.independent_queue(cases,3);api.require(secs==r['queue']['seconds'] and peak==r['queue']['maximum_outstanding_records']<=6,'independent full queue/backlog closure')
    hours=(secs+600)*1.3/3600;audit_hours=math.ceil((sum(x['records']*x['auditor_s'] for x in cases)+600)*1.3/3600)
    need=math.ceil((raw+sum(c['step_ceiling'] for c in d['cases'])*13*8+sum(c['ceiling_records'] for c in cases)*8192+1024**3)*1.3)
    now=job.policy.utc(r['utc']);avail=(job.policy.utc(d['simulation_cutoff_utc'])-now).total_seconds()/3600;reserve=(job.policy.utc(d['final_audit_deadline_utc'])-job.policy.utc(d['simulation_cutoff_utc'])).total_seconds()/3600
    api.require(hours==r['production_hours_with_margin'] and audit_hours==r['required_final_audit_hours'] and need==r['storage_bytes_with_margin'] and avail==r['available_production_hours'] and reserve==r['available_final_audit_hours'],'runtime/storage/clock arithmetic')
    gate=hours<=avail and audit_hours<=reserve and need+r['minimum_reserve_bytes']<=r['free_D_bytes'] and calls
    api.require(gate==r['resource_gate_passed'],'preserve failed or passing resource classification')
    result={'independent_calculation_passed':True,'resource_gate_passed':bool(gate),'new_trajectory_steps':0,'required_production_hours':hours,'available_production_hours':avail,'required_final_audit_hours':audit_hours,'available_final_audit_hours':reserve,'storage_with_reserve_bytes':need+r['minimum_reserve_bytes'],'free_D_bytes':r['free_D_bytes'],'maximum_backlog':peak,'resource_result_sha256':api.sha(s.OUT/'results.json'),'resource_protocol_sha256':api.sha(s.PROTOCOL),'source_sha256':api.sha(__file__),'utc':job.utc().isoformat(),'production_authorized':False}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('RESOURCE_INDEPENDENT',gate,hours,avail,'audit',audit_hours,reserve,flush=True)
if __name__=='__main__':run()
