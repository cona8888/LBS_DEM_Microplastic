"""Independent zero-step arithmetic, queue and scheduling-bound audit."""
from pathlib import Path
from datetime import timedelta
import math,shutil,sys
import resource_schedule_v1 as source
api,job=source.api,source.job
OUT=job.OUT/'resource_independent_01'

def independent_queue(rows,slots):
    # No heap and no reuse of the planning simulator: advance to the next
    # worker completion or audit completion using independently held clocks.
    n=len(rows);made=[0]*n;done=[0]*n;workers={};live=[];waiting=list(range(n));cursor=0
    auditor=None;clock=0.;peak=0
    while waiting or live or workers or auditor:
        while waiting and len(live)<slots:
            i=waiting.pop(0);live.append(i)
        for i in live:
            if i not in workers and made[i]<rows[i]['records'] and made[i]-done[i]<2:
                workers[i]=clock+rows[i]['producer_s']
        if auditor is None:
            for offset in range(n):
                i=(cursor+offset)%n
                if made[i]>done[i]:
                    auditor=(clock+rows[i]['auditor_s'],i);cursor=(i+1)%n;break
        events=[(t,'producer',i) for i,t in workers.items()]
        if auditor is not None:events.append((auditor[0],'audit',auditor[1]))
        api.require(events,'no queue deadlock')
        clock,kind,i=min(events)
        if kind=='producer':workers.pop(i);made[i]+=1
        else:
            auditor=None;done[i]+=1
            if done[i]==rows[i]['records']:live.remove(i)
        peak=max(peak,sum(made)-sum(done))
        api.require(peak<=slots*2 and len(live)<=slots,'independent global backlog and active bounds')
    api.require(made==done==[r['records'] for r in rows],'every record independently drained')
    return clock,peak

def run():
    p=api.read(source.DESIGN);source.verify(p);r=source.sealed(source.OUT/'results.json');d=api.read(job.DESIGN);source.pre.verify(d)
    api.require(r['passed'] and r['resource_gate_passed'],'full scenario passed');checked=0
    for n in range(1,7):
        for slots in (1,2,3):
            for rate in (.125,1.,20.):
                cases=[dict(records=3+i,producer_s=(i+1)*.5,auditor_s=rate) for i in range(n)]
                a=source.schedule(cases,slots);b,peak=independent_queue(cases,slots)
                api.require(a['seconds']==b and a['maximum_outstanding_records']==peak,'independent event ordering and backlog agreement');checked+=1
    # Binding of every directly measured cost and independent preflight seals.
    samples=r['samples'];api.require(len(samples)==28,'all current measured records included')
    for s in samples:
        raw=Path(s['raw']);api.require(raw.stat().st_size==s['bytes'],'measured archive size')
        if raw==source.pre.boundary.current.RUN/'serial.json.xz':
            f=source.sealed(source.FINE);expected=(f['new_accepted_steps'],f['transaction_seconds'],f['audit']['audit_seconds'],f['simulated_seconds'])
        elif raw.parent==job.PREFLIGHT/'probes':
            x=api.read(raw.with_suffix('.preflight_audit.json'));a=x['summary'];expected=(x['steps'],x['transaction_seconds'],a['audit_seconds'],a['stop_s']-a['start_s']);api.require(api.sha(raw)==x['raw_sha256'],'probe raw seal')
        else:
            stem=raw.name.replace('.json.xz','');m=api.read(raw.with_name(stem+'.ready.json'));x=api.read(raw.with_name(stem+'.audit.json'));a=x['summary'];expected=(m['steps'],m['transaction_seconds'],a['audit_seconds'],a['stop_s']-a['start_s']);api.require(api.sha(raw)==m['raw_sha256']==x['raw_sha256'],'live raw seal')
        api.require((s['steps'],s['tx'],s['audit'],s['span'])==expected,'unscaled measured cost and physical increment')
    history=source.sealed(source.HISTORY);api.verify_mapping(history['artifacts'])
    late=dict(write=max(x['write_seconds'] for x in history['measurements']),read=max(x['read_seconds'] for x in history['measurements']),hash=max(x['state_hash_seconds'] for x in history['measurements']),bytes=max(x['compressed_bytes'] for x in history['measurements']))
    api.require(late==r['late_history_cost'],'largest measured full history cost')
    costs={shape:dict(tx_per_step=max(x['tx']/x['steps'] for x in samples if '_'+shape+'_' in x['case']),audit_per_step=max(x['audit']/x['steps'] for x in samples if '_'+shape+'_' in x['case'])) for shape in ('sphere','fibre')}
    api.require(costs==r['shape_costs'],'worst within-shape measurements')
    reconstructed=[];raw_storage=0;bytes_per_step=max(x['bytes']/x['steps'] for x in samples)
    for c in d['cases']:
        dt=min(x['span']/x['steps'] for x in samples if x['case']==c['id']);steps=math.ceil(c['spec']['horizon_s']/dt);shape='fibre' if '_fibre_' in c['id'] else 'sphere';cost=costs[shape]
        count=math.ceil(steps/p['planning_segment_yield']);ceiling=math.ceil(c['step_ceiling']/p['planning_segment_yield'])
        api.require(steps<=c['step_ceiling'] and ceiling<=d['budget']['max_calls_per_case'],'unchanged step and call ceilings')
        row=dict(case=c['id'],planning_steps=steps,records=count,ceiling_records=ceiling,producer_s=cost['tx_per_step']*p['planning_segment_yield']+late['write']+late['hash'],auditor_s=cost['audit_per_step']*p['planning_segment_yield']+late['read']+late['hash']+p['per_receipt_allowance_s'],source_step_seconds=dt,horizon_s=c['spec']['horizon_s'])
        reconstructed.append(row);raw_storage+=c['step_ceiling']*bytes_per_step+ceiling*late['bytes']
    api.require(reconstructed==r['cases'],'all six case cost and horizon accounting')
    seconds,peak=independent_queue(reconstructed,3);api.require(seconds==r['queue']['seconds'] and peak==r['queue']['maximum_outstanding_records']<=6,'complete independent three-slot queue')
    hours=(seconds+600)*1.3/3600;api.require(hours==r['hours_with_margin'],'runtime margin')
    total_steps=sum(c['step_ceiling'] for c in d['cases']);need=math.ceil((raw_storage+total_steps*13*8+sum(c['ceiling_records'] for c in reconstructed)*8192+1024**3)*1.3)
    api.require(need==r['bytes_with_margin'] and need+r['reserve_bytes']<=shutil.disk_usage(job.ROOT).free,'complete storage allowance and live reserve')
    audit_hours=math.ceil(max(4,(sum(x['records']*x['auditor_s'] for x in reconstructed)+600)*1.3/3600))
    now=job.policy.utc(r['utc']);earliest=now+timedelta(hours=hours+6);cutoff=earliest.replace(hour=18,minute=59,second=0,microsecond=0)
    if cutoff<earliest:cutoff+=timedelta(days=1)
    api.require(cutoff.isoformat()==r['simulation_cutoff_utc'] and (cutoff+timedelta(hours=audit_hours)).isoformat()==r['final_audit_deadline_utc'] and audit_hours==r['reserved_final_audit_hours'],'complete measured revised deadlines')
    api.require((cutoff-job.utc()).total_seconds()/3600>=hours,'forecast still fits at independent audit')
    # Original lifecycle pure functions guarantee3 active producers. Each may
    # hold at most2 records; successful workers wait for receipts before retiring.
    api.require(3*d['maximum_unverified_segments_per_case']<=d['maximum_unverified_segments_total']==6,'original global budget retained')
    result=dict(passed=True,new_trajectory_steps=0,independent_schedule_tests=checked,source_sha256=api.sha(__file__),resource_protocol_sha256=api.sha(source.DESIGN),resource_result_sha256=api.sha(source.OUT/'results.json'),full_case_count=len(reconstructed),producer_workers=3,maximum_backlog=peak,hours_with_margin=hours,bytes_with_margin=need,simulation_cutoff_utc=cutoff.isoformat(),reserved_final_audit_hours=audit_hours,final_audit_deadline_utc=r['final_audit_deadline_utc'],utc=job.utc().isoformat(),claim=r['claim'])
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('RESOURCE_INDEPENDENT_PASS',hours,'audit_hours',audit_hours,flush=True)

if __name__=='__main__':run()
