"""Zero-trajectory full six-case schedule, retaining conservative costs.

Three producer slots preserve the original six-outstanding-record bound.
The six-core qualification supplies a conservative contention envelope.
No diagnostic checkpoint or synthetic history is used as production state.
"""
from pathlib import Path
from datetime import timedelta
import heapq,math,shutil,sys,copy
import revised_stack_preflight_v1 as pre
api,job=pre.api,pre.job
ROOT=pre.ROOT
DESIGN=ROOT/'stage200_designs/deadline_revision_20260927/resource_protocol_01.json'
OUT=job.OUT/'resource_schedule_01'
AUDIT=job.OUT/'independent_readiness_01/results.json'
FINE=pre.boundary.current.OUT/'results.json'
HISTORY=FINE.parent.parent/'owned_late_history_01/results.json'

def schedule(cases,slots=3):
    n=len(cases);produced=[0]*n;audited=[0]*n;busy=[False]*n
    active=set();ready=[False]*n;events=[];cursor=0;audit_busy=False;now=0.;next_case=0;maxlag=0
    def launch(i):
        if i in active and not busy[i] and produced[i]<cases[i]['records'] and produced[i]-audited[i]<2:
            busy[i]=True;heapq.heappush(events,(now+cases[i]['producer_s'],'producer',i))
    def fill():
        nonlocal next_case
        while len(active)<slots and next_case<n:
            active.add(next_case);launch(next_case);next_case+=1
    fill()
    while events:
        now,kind,i=heapq.heappop(events)
        if kind=='producer':busy[i]=False;produced[i]+=1;launch(i)
        else:
            audit_busy=False;audited[i]+=1
            if audited[i]==cases[i]['records']:active.remove(i);fill()
            else:launch(i)
        maxlag=max(maxlag,sum(produced)-sum(audited))
        api.require(maxlag<=2*slots and len(active)<=slots,'actual outstanding and worker bounds')
        if not audit_busy:
            for delta in range(n):
                j=(cursor+delta)%n
                if produced[j]>audited[j]:
                    cursor=(j+1)%n;audit_busy=True
                    heapq.heappush(events,(now+cases[j]['auditor_s'],'audit',j));break
    api.require(produced==audited==[c['records'] for c in cases] and not active,'complete queue/accounting drain')
    return {'seconds':now,'maximum_outstanding_records':maxlag,'records_per_case':produced,'slots':slots}

def tests():
    c=lambda n,p,a:dict(records=n,producer_s=p,auditor_s=a)
    api.require(schedule([c(2,10,5)])['seconds']==25,'one-worker analytical overlap')
    api.require(schedule([c(2,1,10)])['seconds']==21,'auditor-bound analytical case')
    api.require(schedule([c(1,10,5)]*4)['seconds']==30,'three slots and acknowledged retirement')
    api.require(schedule([c(1,10,5)]*6,1)['seconds']==90,'serial queue analytical bound')
    checks=0
    for workers in (1,2,3):
        for n in range(1,7):
            for a in (.1,1.,20.):
                r=schedule([c(7+i,(i+1)*.7,a) for i in range(n)],workers)
                api.require(r['seconds']>0 and r['maximum_outstanding_records']<=2*workers,'bounded heterogeneous queue')
                checks+=1
    return checks+4

def sealed(path):
    r=api.read(path);api.require(api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed result '+str(path));return r

def prepare():
    pre.verify(api.read(job.DESIGN));r=sealed(AUDIT)
    api.require(r['numerical_qualification_passed'] and r['process_qualification_passed'] and r['stage200_preflight_steps_verified']==17000,'independent full-stack prerequisite')
    f=sealed(FINE);h=sealed(HISTORY);api.require(f['passed'] and h['passed'],'qualified cost/history inputs')
    files=[job.DESIGN,pre.WORK,AUDIT,AUDIT.parent/'completion.json',FINE,FINE.parent/'completion.json',HISTORY,HISTORY.parent/'completion.json',job.OUT/'preflight_01/results.json',job.OUT/'preflight_01/completion.json',ROOT/'stage200_designs/deadline_revision_20260927/authorization_clock_erratum_01.json',ROOT/'stage200_designs/deadline_revision_20260927/audit_reserve_clarification_01.json']
    d={'stage':'Stage200 full six-case measured-regime schedule','new_trajectory_steps':0,'producer_slots':3,'per_case_outstanding_limit':2,'global_outstanding_limit':6,'runtime_margin':1.3,'storage_margin':1.3,'startup_seconds':600,'per_receipt_allowance_s':1.,'planning_segment_yield':4915,'launch_headroom_hours':6,'final_audit_hours':4,
       'rule':'Worst measured transaction and audit seconds/step within shape from all current full-stack probes/live records and the independently qualified difficult fine prefix. Add complete 80000-row late-history storage/hash overhead to every record. Original 4915 measured-regime yield retained conservatively; no assumed early export. Storage uses full step ceilings and maximum measured bytes/step plus full history per record. Never scale old runtime by an optimization ratio.',
       'scheduling_correction':'Six-worker preflight tests numerical identity/contention, not enforcement of the legacy global backlog metadata. Original scheduler bounds two records per active producer, with no separate global semaphore. Production uses three slots, so its original global bound six is guaranteed algebraically without changing lifecycle or physical code.',
       'claim':'Conservative measured-regime schedule, not a hard runtime bound or completion guarantee. Future unseen contact complexity may still fail; never lower scientific gates to meet the date.',
       'sources':{str(Path(__file__)):api.sha(__file__)},'inputs':{str(x):api.sha(x) for x in files}}
    d['binding']=api.digest(d);job.commit(DESIGN,d);print('RESOURCE_PROTOCOL',api.sha(DESIGN),flush=True)

def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'resource protocol binding');api.verify_mapping(p['sources']);api.verify_mapping(p['inputs'])
    api.require(p['producer_slots']*p['per_case_outstanding_limit']<=p['global_outstanding_limit']==6 and p['runtime_margin']==p['storage_margin']==1.3,'original bounds and margins')

def run():
    p=api.read(DESIGN);verify(p);d=api.read(job.DESIGN);pre.verify(d);samples=[]
    pf=sealed(job.OUT/'preflight_01/results.json');f=sealed(FINE);hr=sealed(HISTORY)
    api.verify_mapping(pf['artifacts']);api.verify_mapping(f['artifacts']);api.verify_mapping(hr['artifacts'])
    for path in sorted((job.PREFLIGHT/'probes').glob('*.preflight_audit.json')):
        r=api.read(path);s=r['summary'];raw=Path(r['path'])
        api.require(api.sha(raw)==r['raw_sha256'] and s['passed'],'bound probe sample')
        samples.append(dict(case=r['case'],steps=r['steps'],tx=r['transaction_seconds'],audit=s['audit_seconds'],span=s['stop_s']-s['start_s'],raw=str(raw),bytes=raw.stat().st_size))
    for case in d['cases']:
        for i in (1,2):
            paths=job.paths(job.root_for('preflight'),case['id'],i);mark=api.read(paths['ready']);r=api.read(paths['receipt']);s=r['summary']
            api.require(s['passed'] and r['status']=='independently_verified' and mark['raw_sha256']==api.sha(paths['raw']),'bound live sample')
            samples.append(dict(case=case['id'],steps=mark['steps'],tx=mark['transaction_seconds'],audit=s['audit_seconds'],span=s['stop_s']-s['start_s'],raw=str(paths['raw']),bytes=paths['raw'].stat().st_size))
    raw=pre.boundary.current.RUN/'serial.json.xz'
    samples.append(dict(case='s2_i0_fibre_f0p03125',steps=f['new_accepted_steps'],tx=f['transaction_seconds'],audit=f['audit']['audit_seconds'],span=f['simulated_seconds'],raw=str(raw),bytes=raw.stat().st_size))
    api.require(len(samples)==28 and all(s['steps']>0 and s['span']>0 for s in samples),'complete nonzero measurement inventory')
    # Maximum of all three measured history-chain operations, not a favorable child alone.
    late={'write':max(x['write_seconds'] for x in hr['measurements']),'read':max(x['read_seconds'] for x in hr['measurements']),'hash':max(x['state_hash_seconds'] for x in hr['measurements']),'bytes':max(x['compressed_bytes'] for x in hr['measurements'])}
    costs={}
    for shape in ('fibre','sphere'):
        rows=[s for s in samples if '_'+shape+'_' in s['case']]
        costs[shape]={'tx_per_step':max(s['tx']/s['steps'] for s in rows),'audit_per_step':max(s['audit']/s['steps'] for s in rows)}
    bytes_per_step=max(s['bytes']/s['steps'] for s in samples);cases=[];raw_storage=0;calls_fit=True
    for c in d['cases']:
        dt=min(s['span']/s['steps'] for s in samples if s['case']==c['id']);n=math.ceil(c['spec']['horizon_s']/dt)
        api.require(n<=c['step_ceiling'],'measured-step scenario within original case ceiling')
        shape='fibre' if '_fibre_' in c['id'] else 'sphere';cost=costs[shape];count=math.ceil(n/p['planning_segment_yield']);ceil_count=math.ceil(c['step_ceiling']/p['planning_segment_yield'])
        prod=cost['tx_per_step']*p['planning_segment_yield']+late['write']+late['hash']
        aud=cost['audit_per_step']*p['planning_segment_yield']+late['read']+late['hash']+p['per_receipt_allowance_s']
        cases.append(dict(case=c['id'],planning_steps=n,records=count,ceiling_records=ceil_count,producer_s=prod,auditor_s=aud,source_step_seconds=dt,horizon_s=c['spec']['horizon_s']))
        raw_storage+=c['step_ceiling']*bytes_per_step+ceil_count*late['bytes'];calls_fit=calls_fit and ceil_count<=d['budget']['max_calls_per_case']
    checked=tests();sched=schedule(cases,p['producer_slots']);hours=(sched['seconds']+p['startup_seconds'])*p['runtime_margin']/3600
    total_steps=sum(c['step_ceiling'] for c in d['cases']);need=math.ceil((raw_storage+total_steps*13*8+sum(c['ceiling_records'] for c in cases)*8192+1024**3)*p['storage_margin']);free=shutil.disk_usage(job.ROOT).free
    now=job.utc();earliest=now+timedelta(hours=hours+p['launch_headroom_hours']);cutoff=earliest.replace(hour=18,minute=59,second=0,microsecond=0)
    if cutoff<earliest:cutoff+=timedelta(days=1)
    final_audit_hours=math.ceil(max(p['final_audit_hours'],(sum(c['records']*c['auditor_s'] for c in cases)+p['startup_seconds'])*p['runtime_margin']/3600))
    final=cutoff+timedelta(hours=final_audit_hours);available=(cutoff-now).total_seconds()/3600
    result={'passed':True,'resource_gate_passed':hours<=available and need+d['budget']['minimum_free_disk_bytes']<=free and calls_fit,'runtime_gate_passed':hours<=available,'storage_gate_passed':need+d['budget']['minimum_free_disk_bytes']<=free,'call_limit_gate_passed':calls_fit,'hours_with_margin':hours,'available_hours_at_freeze':available,'bytes_with_margin':need,'reserve_bytes':d['budget']['minimum_free_disk_bytes'],'free_bytes':free,'cases':cases,'samples':samples,'shape_costs':costs,'late_history_cost':late,'queue':sched,'zero_step_schedule_tests_passed':checked,'production_workers':p['producer_slots'],'simulation_cutoff_utc':cutoff.isoformat(),'final_audit_deadline_utc':final.isoformat(),'new_trajectory_steps':0,'protocol_sha256':api.sha(DESIGN),'utc':now.isoformat(),'claim':p['claim'],'scheduling_correction':p['scheduling_correction']}
    result['reserved_final_audit_hours']=final_audit_hours
    verify(p);job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('RESOURCE_SCHEDULE',result['resource_gate_passed'],hours,cutoff.isoformat(),need,'audit_hours',final_audit_hours,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    elif sys.argv[1:]==['test']:print(tests())
    else:raise ValueError('prepare | run | test')
