"""Six original labelled cases, short combined-optimization preflight only."""
from pathlib import Path
import copy,datetime,shutil,sys,time,traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage174_staging'))
import integrate_certified_sweep_v1 as previous
api,parent,p,fast=previous.api,previous.parent,previous.p,previous.fast
snapshot,candidate=previous.snapshot,previous.candidate
DESIGN=ROOT/'stage175_designs/combined_cost_20260924/design_01.json'
RUN=ROOT/'stage175_runs/combined_cost_20260924/preflight_01'
OUT=ROOT/'stage175_evaluations/combined_cost_20260924/evaluation_01'


def prepare():
    previous.unit.upstream.prior.unit.check_time();previous.verify(api.read(previous.DESIGN))
    audits=[ROOT/'stage172_evaluations/fast_contact_20260923/independent_audit_01',
            ROOT/'stage173_evaluations/immutable_field_20260923/independent_audit_01',previous.OUT.parent/'independent_audit_01']
    inputs=[parent.DESIGN,previous.DESIGN];cases=[];old=api.read(parent.DESIGN)
    for folder in audits:
        r=api.read(folder/'results.json');s=api.read(folder/'completion.json')
        api.require(r.get('integration_verified',r.get('passed',False)) and s['results_sha256']==api.sha(folder/'results.json'),'prerequisite audit')
        inputs.extend([folder/'results.json',folder/'completion.json'])
    for i,c in enumerate(old['cases']):
        source=None;source_design=None
        if i<2:
            factor=1. if i==0 else 2.;entries=next(x for x in api.read(previous.OUT/'results.json')['levels'] if x['factor']==factor and x['variant']=='certificate')['entries']
            source=Path(entries[-1]);source_design=previous.DESIGN
        elif i<4:
            factor=1. if i==2 else 2.;oldrun=previous.unit.upstream.prior
            entry=next(x for x in api.read(oldrun.OUT/'results.json')['levels'] if x['factor']==factor)['entries'][-1]
            source=Path(entry['path']);source_design=oldrun.DESIGN
        cp=None
        if source:
            raw=parent.storage.read_record(source,api.sha(source_design));cp=raw['result']['checkpoint']
            api.require(raw['spec']['config']==c['spec']['config'],'same frozen configuration')
            inputs.extend([source,source.with_suffix('.seal.json'),source_design])
        cases.append({'id':c['id'],'shape':c['shape'],'factor':c['factor'],'spec':c['spec'],
                      'source':str(source) if source else None,'source_design_sha256':api.sha(source_design) if source else None,
                      'initial_checkpoint_state_sha256':cp['state_sha256'] if cp else None})
    d={'stage':'Stage175','physical_changes':[],'purpose':'Combined bounded compute and integrity check, not production or full-path qualification.',
       'cases':cases,'blocks_per_case':3,'steps_per_block':1000,'maximum_new_steps':18000,'wall_s':600.,
       'runtime_margin':1.3,'stop_utc':api.read(previous.DESIGN)['stop_utc'],'simulation_cutoff_utc':'2026-09-25T18:59:00+00:00',
       'minimum_free_disk_bytes':20*1024**3,'sources':parent.source_map(),'inputs':{str(x):api.sha(x) for x in inputs},
       'minimum_gap_semantics':api.read(previous.DESIGN)['diagnostic_semantics'],
       'claim':'Two labelled placements only. Conditional measured-cost projection; no population release estimate, empirical validation or completion guarantee.'}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'combined design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);previous.verify(api.read(previous.DESIGN))


def check(rec,before,binding):
    spec=rec['spec'];r=rec['result'];cp=r['checkpoint'];rows=rec['rows']
    api.require(rec['input_checkpoint_sha256']==api.digest(before),'input hash')
    api.require(cp['state_sha256']==api.digest(cp['state']),'state seal')
    effective=parent.model.binding_for(binding,True)
    api.require(cp['contract']==parent.engine.prior.contracts.expected_contract(spec,effective) and rec['effective_binding']==effective,'runtime contract')
    rejected=before['state']['rejected'] if before else 0;t=before['state']['t'] if before else 0.;steps=before['state']['steps'] if before else 0
    api.require(r['rejected']==rejected==0 and parent.engine.prior.reference.independent_health(r,spec)['passed'],'zero rejects and numerical health')
    api.require(r['status']=='paused_checkpoint','bounded checkpoint outcome')
    for row in rows:
        api.require(row['dt_s']>0 and t+row['dt_s']==row['time_s'],'exact clock');t=row['time_s']
    api.require(t==r['time_s']==cp['state']['t'] and len(rows)==r['steps']-steps==rec['step_cap'],'complete accounting')
    api.require(len(rec['backend_calls'])==1 and rec['backend_calls'][0]['enabled'],'rigid backend')
    api.require(all(x['accepted'] for x in r['stage119_repair_calls']),'accepted fallback only')
    api.require(len(rec['sweep_certificates'])==len(rows),'one geometry record per accepted step')
    api.require(all(not x['certified'] or x['lower_bound_m']>=x['threshold_m'] for x in rec['sweep_certificates']),'original penetration limit')


def run():
    d=api.read(DESIGN);verify(d);previous.unit.upstream.prior.unit.check_time();RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();parent.b.old.parent.configure();fast.capture_systems=True;ledger=[];artifacts={};total=0
    try:
        with snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            api.fields.load(2,1.,6)
            for c in d['cases']:
                spec=c['spec'];binding=api.digest([d['binding'],c['id']]);cp=None
                if c['source']:
                    raw=parent.storage.read_record(Path(c['source']),c['source_design_sha256'])
                    api.require(raw['result']['checkpoint']['state_sha256']==c['initial_checkpoint_state_sha256'],'selected source')
                    cp=parent.model.checkpoint(spec,binding,raw['result']['checkpoint'],True)
                folder=RUN/c['id'];folder.mkdir();entries=[]
                for block in range(d['blocks_per_case']):
                    previous.unit.upstream.prior.unit.check_time()
                    api.require(time.perf_counter()-start<d['wall_s'] and total+d['steps_per_block']<=d['maximum_new_steps'],'combined work budget')
                    api.require(shutil.disk_usage(ROOT).free>=d['minimum_free_disk_bytes'],'disk reserve')
                    before=copy.deepcopy(cp);t0=cp['state']['t'] if cp else 0.;step0=cp['state']['steps'] if cp else 0
                    n0=len(fast.attempts);n1=len(fast.old.telemetry);nc=len(parent.model.calls);nf=len(parent.fix.telemetry);ng=len(candidate.records)
                    started=time.perf_counter()
                    with p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),fast.scope(parent.engine.runtime,True),candidate.scope():
                        result,rows=parent.engine.runtime.execute(spec,binding,checkpoint=cp,pause=step0+d['steps_per_block'])
                    compute=time.perf_counter()-started
                    rec={'spec':spec,'result':result,'rows':rows,'input_checkpoint_sha256':api.digest(before),'effective_binding':parent.model.binding_for(binding,True),
                         'design_sha256':api.sha(DESIGN),'step_cap':d['steps_per_block'],'compute_call_wall_s':compute,
                         'early_attempts':copy.deepcopy(fast.attempts[n0:]),'repairs':copy.deepcopy(fast.old.telemetry[n1:]),
                         'backend_calls':copy.deepcopy(parent.model.calls[nc:]),'certificates':copy.deepcopy(parent.fix.telemetry[nf:]),
                         'sweep_certificates':copy.deepcopy(candidate.records[ng:]),'minimum_gap_semantics':d['minimum_gap_semantics']}
                    path=folder/f'segment_{block+1:03d}.json.gz';parent.storage.write_record(path,rec);total+=len(rows)
                    check(rec,before,binding);cp=result['checkpoint']
                    transaction={'record_path':str(path),'record_sha256':api.sha(path),'compute_s':compute,'transaction_wall_s':time.perf_counter()-started,
                                 'simulated_s':cp['state']['t']-t0,'steps':len(rows),'compressed_bytes':path.stat().st_size,
                                 'early_contacts':sum(x['accepted'] for x in rec['early_attempts']),'clearance_certificates':sum(x['certified'] for x in rec['sweep_certificates'])}
                    tx=folder/f'transaction_{block+1:03d}.json';api.write(tx,transaction)
                    for x in [path,path.with_suffix('.seal.json'),tx]:artifacts[str(x)]=api.sha(x)
                    entries.append(transaction)
                    print(c['id'],block+1,'steps',len(rows),'time',cp['state']['t'],'compute',round(compute,3),'wall',round(transaction['transaction_wall_s'],3),flush=True)
                    # Diagnostics are already losslessly sealed; never physical history.
                    fast.attempts.clear();fast.telemetry.clear();fast.old.telemetry.clear();candidate.records.clear();parent.fix.telemetry.clear();parent.model.calls.clear()
                ledger.append({'case':c['id'],'entries':entries,'final':result})
        rates={}
        for c,record in zip(d['cases'],ledger):
            key=(c['shape'],c['factor']);rate=max(x['transaction_wall_s']/x['simulated_s'] for x in record['entries'])
            rates[key]=max(rates.get(key,0.),rate)
        loads=[0.,0.,0.];schedule=[]
        for c in d['cases']:
            hours=c['spec']['horizon_s']*rates[c['shape'],c['factor']]*d['runtime_margin']/3600
            worker=min(range(3),key=lambda i:loads[i]);loads[worker]+=hours;schedule.append({'case':c['id'],'worker':worker,'compute_hours_with_margin':hours,'finish_hours':loads[worker]})
        now=datetime.datetime.now(datetime.timezone.utc);available=(datetime.datetime.fromisoformat(d['simulation_cutoff_utc'])-now).total_seconds()/3600
        # A 10-minute startup reserve is larger than measured field-load/audit overhead.
        makespan=max(loads)+1/6
        result={'passed':True,'new_steps':total,'wall_s':time.perf_counter()-start,'ledger':ledger,'artifacts':artifacts,'design_sha256':api.sha(DESIGN),
                'family_rates':[{'shape':shape,'factor':factor,'seconds_per_sim_second':rate} for (shape,factor),rate in rates.items()],
                'projected_schedule':schedule,'projected_makespan_hours':makespan,'available_hours':available,'budget_passed':makespan<=available,
                'evaluated_utc':now.isoformat(),'campaign_launched':False,'full_path_qualified':False,'claim':d['claim']}
        verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':True,'budget_passed':result['budget_passed'],'results_sha256':api.sha(OUT/'results.json')})
        print('COMBINED',True,'STEPS',total,'BUDGET',result['budget_passed'],'MAKESPAN_H',makespan,'AVAILABLE_H',available,flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'saved_steps':total,'wall_s':time.perf_counter()-start});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
