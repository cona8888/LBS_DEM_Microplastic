"""Independent queue, sample provenance, horizon and budget arithmetic."""
from pathlib import Path
import math
import resource_cone_stack_v1 as s
import audit_resource_schedule_v1 as queue
api,job=s.api,s.job

def run():
    p=api.read(s.PROTOCOL);api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'protocol binding');api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    d=api.read(job.DESIGN);job.verify(d);r=s.pre.sealed(s.BASE/'results.json');floor=s.pre.sealed(s.FLOOR)
    api.require(r['calculation_passed'] and len(r['samples'])==34,'complete sample inventory')
    for x in r['samples']:
        raw=Path(x['raw']);api.require(api.sha(raw)==x['raw_sha256'] and raw.stat().st_size==x['bytes'],'actual raw size/seal')
        if raw.parent==job.PREFLIGHT/'probes':
            a=api.read(raw.with_suffix('.preflight_audit.json'));z=a['summary'];expected=(a['steps'],a['transaction_seconds'],z['audit_seconds'],z['stop_s']-z['start_s'])
        elif raw.is_relative_to(s.pre.LOCAL):
            a=s.pre.sealed(raw.parent/'results.json');plan=api.read(s.pre.ROOT/'stage207_designs/feasibility_trajectory_20260930'/(raw.parent.name+'.json'));seed=s.pre.LOCAL/plan['seed'] if plan['seed'] else s.pre.RECON
            before=api.read(seed/('checkpoint.json' if plan['seed'] else 'checkpoint_00227.json'))['state']['t'];expected=(a['steps'],a['transaction_seconds'],a['audit']['audit_seconds'],a['time_s']-before)
        else:
            stem=raw.name.replace('.json.xz','');a=api.read(raw.with_name(stem+'.ready.json'));z=api.read(raw.with_name(stem+'.audit.json'))['summary'];expected=(a['steps'],a['transaction_seconds'],z['audit_seconds'],z['stop_s']-z['start_s'])
        api.require((x['steps'],x['tx'],x['audit'],x['span'])==expected,'unscaled authentic measured sample')
    costs={shape:{k:max(floor['shape_costs'][shape][k],max(x[v]/x['steps'] for x in r['samples'] if '_'+shape+'_' in x['case'])) for k,v in [('tx_per_step','tx'),('audit_per_step','audit')]} for shape in ('fibre','sphere')};api.require(costs==r['shape_costs'],'original worst-within-shape floors')
    hist=s.pre.sealed(s.HISTORY);late={k:max(x[v] for x in hist['measurements']) for k,v in [('write','write_seconds'),('read','read_seconds'),('hash','state_hash_seconds'),('bytes','compressed_bytes')]};api.require(late==r['late_history_cost'],'late full-history costs')
    measured=[s.pre.sealed(s.pre.LOCAL/n/'results.json') for n in ('serial_01','extension_a_01','extension_b_01','extension_c_01','extension_d_01')];y=min([3650]+[x['steps'] for x in measured]);api.require(y==p['planning_segment_yield']==r['planning_segment_yield'],'independent wall-budget yield')
    samples=r['samples']+floor['samples'];perbyte=max(x['bytes']/x['steps'] for x in samples);cases=[];rawbytes=0;calls=True
    for c in d['cases']:
        dt=min(x['span']/x['steps'] for x in samples if x['case']==c['id']);n=math.ceil(c['spec']['horizon_s']/dt);api.require(n<=c['step_ceiling'],'original case ceiling');cost=costs['fibre' if '_fibre_' in c['id'] else 'sphere'];records=math.ceil(n/y);cap=math.ceil(c['step_ceiling']/y)
        cases.append(dict(case=c['id'],planning_steps=n,records=records,ceiling_records=cap,producer_s=cost['tx_per_step']*y+late['write']+late['hash'],auditor_s=cost['audit_per_step']*y+late['read']+late['hash']+1.,source_step_seconds=dt));rawbytes+=c['step_ceiling']*perbyte+cap*late['bytes'];calls &= cap<=d['budget']['max_calls_per_case']
    api.require(cases==r['cases'],'six independent horizon/step/storage cases')
    seconds,peak=queue.independent_queue(cases,3);api.require(seconds==r['queue']['seconds'] and peak==r['queue']['maximum_outstanding_records']<=6,'independent global-six queue')
    hours=(seconds+600)*1.3/3600;audit=math.ceil((sum(c['records']*c['auditor_s'] for c in cases)+600)*1.3/3600);need=math.ceil((rawbytes+sum(c['step_ceiling'] for c in d['cases'])*13*8+sum(c['ceiling_records'] for c in cases)*8192+1024**3)*1.3)
    now=job.policy.utc(r['utc']);available=(job.policy.utc(d['simulation_cutoff_utc'])-now).total_seconds()/3600;reserve=(job.policy.utc(d['final_audit_deadline_utc'])-job.policy.utc(d['simulation_cutoff_utc'])).total_seconds()/3600
    api.require((hours,audit,need,available,reserve)==(r['production_hours_with_margin'],r['required_final_audit_hours'],r['storage_bytes_with_margin'],r['available_production_hours'],r['available_final_audit_hours']),'independent original-margin calendar arithmetic')
    fit=hours<=available and audit<=reserve and need+r['minimum_reserve_bytes']<=r['free_D_bytes'] and calls;api.require(fit==r['resource_gate_passed'],'passing or failed fit preserved')
    out=job.OUT/'resource_independent_01';result=dict(independent_calculation_passed=True,resource_gate_passed=bool(fit),new_trajectory_steps=0,required_production_hours=hours,available_production_hours=available,required_final_audit_hours=audit,available_final_audit_hours=reserve,storage_with_reserve_bytes=need+r['minimum_reserve_bytes'],free_D_bytes=r['free_D_bytes'],maximum_backlog=peak,resource_result_sha256=api.sha(s.BASE/'results.json'),resource_protocol_sha256=api.sha(s.PROTOCOL),source_sha256=api.sha(__file__),production_authorized=False)
    job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')));print('CONE_RESOURCE_INDEPENDENT',fit,hours,available,audit,reserve,flush=True)
if __name__=='__main__':run()
