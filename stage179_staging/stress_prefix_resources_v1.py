"""Same high-entropy late-history stress, now with lossless prefix storage.

Fixtures have a dedicated resource design, explicit synthetic flags and an
unsupported-for-physics status. They are never passed to a DEM integrator.
"""
from pathlib import Path
import copy,datetime,hashlib,math,shutil,sys,time
import qualify_history_prefix_v1 as qualification
import audit_history_prefix_v1 as audit
import lossless_history_prefix_v1 as codec
ROOT=codec.ROOT;api=codec.api
sys.path.insert(0,str(ROOT/'stage178_staging'))
import stress_history_storage_v1 as previous
DESIGN=ROOT/'stage179_designs/history_prefix_20260924/resource_design_01.json'
RUN=ROOT/'stage179_runs/history_prefix_20260924/resource_fixtures_01'
OUT=ROOT/'stage179_evaluations/history_prefix_20260924/resource_stress_01'


def prepare():
    q=api.read(audit.OUT/'results.json');api.require(q['passed'],'independent codec prerequisite')
    api.require(api.read(audit.OUT/'completion.json')['results_sha256']==api.sha(audit.OUT/'results.json'),'independent codec seal')
    sd=api.read(previous.DESIGN);previous.verify(sd)
    inputs=[previous.DESIGN,previous.OUT/'results.json',previous.OUT/'completion.json',qualification.DESIGN,audit.OUT/'results.json',audit.OUT/'completion.json']
    d={'stage':'Stage179 prefix resource stress','cases':sd['cases'],'seed':sd['seed'],'new_trajectory_steps':0,'physical_changes':[],
       'history_cadence_steps':250,'segment_steps':10000,'margins':{'runtime':1.3,'storage':1.3},'wall_seconds':1200,
       'cutoff_utc':'2026-09-24T02:46:55+00:00','sources':{str(Path(p).resolve()):api.sha(p) for p in [__file__,codec.__file__,codec.base.__file__,previous.__file__]},
       'inputs':{str(p):api.sha(p) for p in inputs},'claim':'Synthetic resource fixtures only, not numerical trajectories or physical observations.'}
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);previous.verify(api.read(previous.DESIGN))


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);started=time.perf_counter();rows=[];artifacts={}
    for ci,c in enumerate(d['cases']):
        api.require(time.perf_counter()-started<d['wall_seconds'] and datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(d['cutoff_utc']),'bounded work')
        original=previous.codec.read_record(Path(c['source']),api.sha(previous.previous.DESIGN));cfg=original['spec']['config'];tx=api.read(Path(c['source']).with_suffix('.transaction.json'))
        n=c['step_ceiling']//d['history_cadence_steps'];increment=d['segment_steps']//d['history_cadence_steps'];folder=RUN/c['case'];folder.mkdir()
        all_history=previous.history(n,d['seed']+ci,c['horizon_s'],original['spec']['field_metadata']['cell_length_m'],cfg['target_mean_interstitial_velocity_m_s'],cfg['prolate_semiaxes_m'][1])
        prefix=None;stage_rows=[];last_fixture=None
        for label,length in [('bootstrap',n-2*increment),('parent',n-increment),('child',n)]:
            fixture=copy.deepcopy(original);fixture['design_sha256']=api.sha(DESIGN);fixture['synthetic_resource_fixture_only']=True
            fixture['result']['status']='synthetic_resource_fixture';h=all_history[:length]
            fixture['result']['history']=h;fixture['result']['checkpoint']['state']['history']=h
            hs=time.perf_counter();fixture['result']['checkpoint']['state_sha256']=api.digest(fixture['result']['checkpoint']['state']);hash_s=time.perf_counter()-hs
            path=folder/(label+'.json.xz');t=time.perf_counter();seal,state=codec.write_record(path,fixture,prefix);write_s=time.perf_counter()-t;t=time.perf_counter()
            decoded,reader_state=codec.read_record(path,api.sha(DESIGN),prefix);read_s=time.perf_counter()-t
            api.require(codec.base.raw_bytes(decoded)==codec.base.raw_bytes(fixture) and reader_state==state,'same full canonical bytes after prefix recovery')
            item={'label':label,'path':str(path),'history_rows':length,'compressed_bytes':path.stat().st_size,'write_s':write_s,'read_s':read_s,'state_hash_s':hash_s,
                  'original_uncompressed_sha256':state.original_sha256,'original_history_sha256':state.history_sha256}
            stage_rows.append(item);prefix=state
            for f in [path,path.with_suffix('.seal.json')]:artifacts[str(f)]=api.sha(f)
            print('PREFIX_STRESS',c['case'],label,'history',length,'MB',round(path.stat().st_size/1e6,3),'seconds',round(write_s+read_s+hash_s,3),flush=True)
            del fixture,decoded,reader_state
        child=stage_rows[-1]
        rows.append({'case':c['case'],'measurements':stage_rows,'baseline_transaction_s':tx['transaction_s'],'baseline_simulated_s':tx['simulated_s'],
                     'seconds_per_sim_s_conservative':(tx['transaction_s']+child['write_s']+child['read_s']+child['state_hash_s'])/tx['simulated_s'],
                     'steady_segment_bytes':max(stage_rows[-1]['compressed_bytes'],stage_rows[-2]['compressed_bytes'])})
        del original,all_history,prefix
    families={}
    for c,row in zip(d['cases'],rows):
        key=c['shape'],c['factor'];old=families.get(key,{'bytes':0,'rate':0})
        families[key]={'bytes':max(old['bytes'],row['steady_segment_bytes']),'rate':max(old['rate'],row['seconds_per_sim_s_conservative'])}
    loads=[0.,0.,0.];amount=0.;costs=[]
    for c in d['cases']:
        f=families[c['shape'],c['factor']];count=math.ceil(c['step_ceiling']/d['segment_steps']);size=count*f['bytes'];amount+=size
        hours=c['horizon_s']*f['rate']*d['margins']['runtime']/3600;worker=min(range(3),key=lambda i:loads[i]);loads[worker]+=hours
        costs.append({'case':c['case'],'worker':worker,'hours':hours,'raw_bytes':size,'records':count})
    # Include two reserve records, all synthetic bootstrap sizes conservatively,
    # complete 13-float trace blocks, 8-KiB receipts, and 1GiB final artifacts.
    amount+=2*max(v['bytes'] for v in families.values())+sum(x['measurements'][0]['compressed_bytes'] for x in rows)
    total_steps=80_020_000;audit_storage=total_steps*13*8+math.ceil(total_steps/10000)*8192+1024**3
    projected=math.ceil((amount+audit_storage)*d['margins']['storage']);free=shutil.disk_usage(ROOT).free
    now=datetime.datetime.now(datetime.timezone.utc);available=(datetime.datetime.fromisoformat(api.read(previous.previous.prior.DESIGN)['simulation_cutoff_utc'])-now).total_seconds()/3600
    report={'passed':True,'exact_lossless_stress':True,'cases':rows,'costs':costs,'raw_storage_before_margin':amount,'audit_storage_before_margin':audit_storage,
            'bytes_with_margin':projected,'time_hours_with_margin':max(loads)+1/6,'available_hours':available,'free_bytes':free,'reserve_bytes':codec.base.RESERVE,
            'storage_scenario_passed':projected<=free-codec.base.RESERVE,'time_scenario_passed':max(loads)+1/6<=available,
            'wall_seconds':time.perf_counter()-started,'new_trajectory_steps':0,'artifacts':artifacts,'design_sha256':api.sha(DESIGN),
            'basis':'Worst measured late-history child cost per family; unchanged 30% margins. Baseline transaction plus new write/read/hash cost deliberately double-counts old I/O.',
            'limitations':'Synthetic high-entropy stress is not a hard bound on unseen contacts. Requires incremental audits and live time/disk guards. No production authority.'}
    verify(d);api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
    print('PREFIX_RESOURCE_FINAL','GB',projected/1e9,'H',report['time_hours_with_margin'],'STORAGE',report['storage_scenario_passed'],'TIME',report['time_scenario_passed'],flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
