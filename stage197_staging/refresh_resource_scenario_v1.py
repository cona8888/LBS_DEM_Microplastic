"""Zero-trajectory late-history stress and conservative queued resource model.

Never use synthetic resource fixtures as physical results or restart states.
The six producer / one round-robin auditor queue is evaluated with original
two-record per-case backpressure. Full ceilings bound storage; measured time
increments bound the planning scenario, not unseen future contact complexity.
"""
from pathlib import Path
import copy, math, heapq, sys, shutil, time
import qualify_budget_continuation_v1 as q
job,api=q.job,q.api
sys.path.insert(0,str(q.ROOT/'stage178_staging'))
import stress_history_storage_v1 as history_source
DESIGN=q.AUTH.with_name('resource_protocol_01.json')
RUN=q.RUN.parent/'resource_fixtures_01'
OUT=q.OUT.parent/'resource_scenario_01'
AUDIT=q.OUT.parent/'independent_continuation_01/results.json'
TRANSPORT=q.OUT.parent/'independent_transport_01/results.json'
PF=job.OUT/'preflight_01/results.json'
OLD=q.ROOT/'stage196_evaluations/deadline_recovery_20260925/long_transactions_01/results.json'

def prepare():
    r=api.read(AUDIT);api.require(r['passed'] and api.read(AUDIT.parent/'completion.json')['results_sha256']==api.sha(AUDIT),'independent continuation prerequisite')
    t=api.read(TRANSPORT);api.require(t['passed'] and api.read(TRANSPORT.parent/'completion.json')['results_sha256']==api.sha(TRANSPORT),'independent transport prerequisite')
    inputs=[q.AUTH,q.DESIGN,q.OUT/'results.json',q.OUT/'completion.json',AUDIT,AUDIT.parent/'completion.json',TRANSPORT,TRANSPORT.parent/'completion.json',job.DESIGN,PF,PF.parent/'completion.json',OLD,OLD.parent/'completion.json']
    p={'stage':'Stage197 refreshed measured resource scenario','new_trajectory_steps':0,'maximum_history_rows':80000,'history_increment_rows':40,'seed':19720260926,'wall_seconds':1200,
       'runtime_margin':1.3,'storage_margin':1.3,'startup_seconds':600,'per_receipt_seconds_allowance':1.0,
       'synthetic_fixture_only':True,'sources':{str(Path(__file__)):api.sha(__file__),str(Path(history_source.__file__)):api.sha(history_source.__file__)},'inputs':{str(p):api.sha(p) for p in inputs},
       'cost_rule':'Worst measured per-step costs within shape, including long repaired-fibre probes; apply equally to both original timesteps and both placements for that shape. Add complete late-history read/write/state-hash stress again conservatively. Never scale old forecasts by optimization ratios.',
       'claim':'Conservative measured-regime resource scenario, not a hard bound or completion promise. Existing numerical and storage qualification remains required.'}
    p['binding']=api.digest(p);job.commit(DESIGN,p);print('RESOURCE_PROTOCOL',api.sha(DESIGN),flush=True)

def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'resource protocol identity');api.verify_mapping(p['sources']);api.verify_mapping(p['inputs']);q.verify(api.read(q.DESIGN))

def schedule(cases):
    # Discrete event approximation: exact two-outstanding-record backpressure,
    # a single round-robin auditor, and one producer per case. No overlap of a
    # worker's own transactions, no early exits, final audit drain included.
    n=len(cases);produced=[0]*n;audited=[0]*n;busy=[False]*n;ready=[[] for _ in cases];events=[];cursor=0;audit_busy=False;now=0.;max_lag=0
    def launch(i):
        if not busy[i] and produced[i]<cases[i]['records_for_horizon'] and produced[i]-audited[i]<2:
            busy[i]=True;heapq.heappush(events,(now+cases[i]['producer_seconds_per_record'],'producer',i))
    for i in range(n):launch(i)
    while events:
        now,kind,i=heapq.heappop(events)
        if kind=='producer':
            busy[i]=False;produced[i]+=1;ready[i].append(produced[i]);launch(i)
        else:
            audit_busy=False;audited[i]+=1;launch(i)
        max_lag=max(max_lag,sum(produced)-sum(audited))
        if not audit_busy:
            for delta in range(n):
                j=(cursor+delta)%n
                if ready[j]:
                    ready[j].pop(0);cursor=(j+1)%n;audit_busy=True
                    heapq.heappush(events,(now+cases[j]['auditor_seconds_per_record'],'audit',j));break
    api.require(produced==audited==[c['records_for_horizon'] for c in cases],'simulated queue drains every planned record')
    return {'seconds':now,'records_per_case':produced,'maximum_ready_or_auditing_backlog':max_lag}

def run():
    p=api.read(DESIGN);verify(p);d=api.read(job.DESIGN);auth=api.read(q.AUTH)
    q.pre.wrapper.affinity.bind(14);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    job.commit(RUN/'launch.json',{'utc':job.utc().isoformat(),'pid':__import__('os').getpid(),'protocol_sha256':api.sha(DESIGN),'new_trajectory_steps':0})
    cr=api.read(q.OUT/'results.json');pf=api.read(PF);old=api.read(OLD)
    samples=[]
    for x in pf['cases']:
        path=job.PREFLIGHT/'probes'/(x['case']+'_contact.json.xz');receipt=api.read(path.with_suffix('.preflight_audit.json'))
        samples.append({'case':x['case'],'steps':1000,'tx':x['transaction_seconds'],'dt':x['simulated_seconds'],'audit':receipt['summary']['audit_seconds'],'read':0.,'path':str(path)})
    for x in cr['calls']:
        if x['label'] in ('selected_long','conditional_fine'):
            samples.append({'case':x['case'],'steps':x['steps'],'tx':x['transaction_seconds'],'dt':x['simulated_seconds'],'audit':x['audit_seconds'],'read':x['read_seconds'],'path':x['path']})
    for x in old['measurements']:
        samples.append({'case':x['case'],'steps':x['accepted_steps'],'tx':x['transaction_seconds'],'dt':x['simulated_seconds'],'audit':x['audit_seconds'],'read':x['read_seconds'],'path':x['path']})
    # The largest observed archive per accepted step supplies the conservative
    # telemetry payload; no trajectory rows are invented or integrated.
    src=max(samples,key=lambda x:Path(x['path']).stat().st_size/x['steps']);source=Path(src['path'])
    original,_=job.codec.read_record(source,api.sha(job.DESIGN));cfg=original['spec']['config'];meta=original['spec']['field_metadata']
    histories=history_source.history(p['maximum_history_rows'],p['seed'],original['spec']['horizon_s'],meta['cell_length_m'],cfg['target_mean_interstitial_velocity_m_s'],cfg['prolate_semiaxes_m'][1])
    prefix=None;measurements=[]
    for label,n in [('bootstrap',79920),('parent',79960),('child',80000)]:
        api.require(time.perf_counter()-started<p['wall_seconds'],'bounded zero-step resource test')
        f=copy.deepcopy(original);f['design_sha256']=api.sha(DESIGN);f['synthetic_resource_fixture_only']=True;f['result']['status']='synthetic_resource_fixture'
        h=histories[:n];f['result']['history']=h;f['result']['checkpoint']['state']['history']=h
        t=time.perf_counter();f['result']['checkpoint']['state_sha256']=api.digest(f['result']['checkpoint']['state']);hash_s=time.perf_counter()-t
        path=RUN/(label+'.json.xz');t=time.perf_counter();seal,state=job.codec.write_record(path,f,prefix);write_s=time.perf_counter()-t
        t=time.perf_counter();decoded,recovered=job.codec.read_record(path,api.sha(DESIGN),prefix);read_s=time.perf_counter()-t
        api.require(job.codec.base.raw_bytes(decoded)==job.codec.base.raw_bytes(f) and state==recovered,'full original canonical record and history identity')
        measurements.append({'label':label,'history_rows':n,'compressed_bytes':path.stat().st_size,'write_seconds':write_s,'read_seconds':read_s,'hash_seconds':hash_s,'raw_sha256':api.sha(path)})
        prefix=state;print('LATE_HISTORY',label,n,round(write_s+read_s+hash_s,3),flush=True)
        del f,decoded,recovered
    late=measurements[-1];shape_cost={}
    for shape in ('fibre','sphere'):
        rows=[x for x in samples if '_'+shape+'_' in x['case']]
        shape_cost[shape]={'tx_per_step':max(x['tx']/x['steps'] for x in rows),'audit_per_step':max((x['audit']+x['read'])/x['steps'] for x in rows)}
    long_counts=[x['steps'] for x in cr['calls'] if x['requested_steps']==10000]+[4915]
    segment_yield=min(long_counts);cases=[];raw_storage=0;calls_fit=True
    # Charge the maximum sampled raw bytes/step plus maximum synthetic history
    # archive size to every segment, deliberately double-counting fixture body.
    raw_bytes_per_step=max(Path(x['path']).stat().st_size/x['steps'] for x in samples)
    for c in d['cases']:
        row=next(x for x in samples if x['case']==c['id']);dt=row['dt']/row['steps'];n=math.ceil(c['spec']['horizon_s']/dt)
        api.require(n<=c['step_ceiling'],'planning horizon within unchanged step ceiling')
        shape='fibre' if '_fibre_' in c['id'] else 'sphere';cost=shape_cost[shape];count=math.ceil(n/segment_yield);ceil_count=math.ceil(c['step_ceiling']/segment_yield)
        prod=cost['tx_per_step']*segment_yield+late['write_seconds']+late['hash_seconds']
        aud=cost['audit_per_step']*segment_yield+late['read_seconds']+late['hash_seconds']+p['per_receipt_seconds_allowance']
        raw_storage+=c['step_ceiling']*raw_bytes_per_step+ceil_count*max(x['compressed_bytes'] for x in measurements)
        calls_fit=calls_fit and ceil_count<=d['budget']['max_calls_per_case']
        cases.append({'case':c['id'],'planning_steps':n,'records_for_horizon':count,'records_for_step_ceiling':ceil_count,'producer_seconds_per_record':prod,'auditor_seconds_per_record':aud,'full_horizon_s':c['spec']['horizon_s'],'source_step_seconds':dt})
    sched=schedule(cases);hours=(sched['seconds']+p['startup_seconds'])*p['runtime_margin']/3600
    total_steps=sum(c['step_ceiling'] for c in d['cases']);storage=math.ceil((raw_storage+total_steps*13*8+sum(c['records_for_step_ceiling'] for c in cases)*8192+1024**3)*p['storage_margin'])
    free=shutil.disk_usage(RUN.anchor).free;available=(job.policy.utc(auth['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    report={'passed':True,'resource_gate_passed':hours<=available and storage+auth['minimum_free_disk_bytes']<=free and calls_fit,'runtime_gate_passed':hours<=available,'storage_gate_passed':storage+auth['minimum_free_disk_bytes']<=free,'call_limit_gate_passed':calls_fit,
        'hours_with_margin':hours,'available_simulation_hours':available,'bytes_with_margin':storage,'free_bytes':free,'reserve_bytes':auth['minimum_free_disk_bytes'],'cases':cases,'samples':samples,'shape_cost':shape_cost,'planning_segment_yield':segment_yield,'queue':sched,'late_history':measurements,'new_trajectory_steps':0,'production_authorized':False,
        'protocol_sha256':api.sha(DESIGN),'raw_payload_source':src,'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()},'claim':p['claim'],'utc':job.utc().isoformat()}
    verify(p);job.commit(OUT/'results.json',report);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json'),'resource_gate_passed':report['resource_gate_passed']});print('RESOURCE_SCENARIO',report['resource_gate_passed'],'hours',hours,'available',available,'GB',storage/1e9,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
