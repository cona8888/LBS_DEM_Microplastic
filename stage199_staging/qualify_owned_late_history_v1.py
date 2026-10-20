"""Zero-step late-history lossless qualification and unscaled timing evidence.

Synthetic history is storage-only, never a physical result or restart state.
Retains the prior80,000-row/40-row-increment stress contract and independent
original decoder. This is not a complete six-worker resource forecast.
"""
from pathlib import Path
import copy,os,sys,shutil,time,traceback
import owned_decode_storage_v1 as storage
import qualify_owned_decode_v1 as qualified
api,job,q,WORK=qualified.api,qualified.job,qualified.q,qualified.WORK
ROOT=storage.ROOT
sys.path.insert(0,str(ROOT/'stage178_staging'))
import stress_history_storage_v1 as history_source
DESIGN=WORK.with_name('owned_late_history_01.json')
RUN=qualified.RUN.with_name('owned_late_history_01');OUT=qualified.OUT.with_name('owned_late_history_01')
RAW=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/current_prefix_01/serial.json.xz')

def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'frozen stress binding')
    api.verify_mapping(p['sources']);api.verify_mapping(p['inputs']);storage.verify_bindings()
    api.require(p['new_trajectory_steps']==0 and p['maximum_history_rows']==80000 and p['history_increment_rows']==40,'unchanged synthetic resource stress size')

def prepare():
    p0=qualified.OUT/'benchmark.json';r=api.read(p0)
    api.require(r['passed'] and r['material_reader_gain_passed'] and api.read(p0.parent/'benchmark_completion.json')['benchmark_sha256']==api.sha(p0),'qualified owned reader')
    api.verify_mapping(r['inputs'])
    files=[Path(__file__),Path(storage.__file__),Path(history_source.__file__),Path(q.__file__)]
    inputs=[WORK,RAW,RAW.with_suffix('.seal.json'),qualified.OUT/'results.json',qualified.OUT/'completion.json',p0,p0.parent/'benchmark_completion.json']
    p={'stage':'Stage199 owned-reader original late-history storage stress','new_trajectory_steps':0,'maximum_history_rows':80000,'history_increment_rows':40,'seed':19720260926,'wall_seconds':1200,
       'history_counts':[79920,79960,80000],'synthetic_fixture_only':True,'production_authorized':False,
       'sources':{str(x):api.sha(x) for x in files},'inputs':{str(x):api.sha(x) for x in inputs},
       'criterion':'Every original canonical byte, whole record and prefix state reconstruct exactly in both candidate and separately imported original decoder. Preserve every failure. Timings measured directly; no scaling old costs by optimizer ratios.'}
    api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work clock')
    p['binding']=api.digest(p);job.commit(DESIGN,p);verify(p);print('OWNED_LATE_HISTORY_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    p=api.read(DESIGN);verify(p);w=api.read(WORK)
    from datetime import timedelta
    api.require(job.utc()+timedelta(seconds=p['wall_seconds'])<job.policy.utc(w['work_end_utc']),'full zero-step stress fits work clock')
    import psutil
    for proc in psutil.process_iter(['name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'one owned benchmark worker')
    api.require(shutil.disk_usage(RUN.anchor).free>w['minimum_disk_reserve_bytes']+4*storage.base.MAX_COMPRESSED,'disk reserve')
    info=__import__('qualify_performance_stack_v1').wrapper.affinity.bind(14)
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'protocol_sha256':api.sha(DESIGN),'new_trajectory_steps':0,'affinity':info})
    started=time.perf_counter()
    try:
        source_design=api.read(RAW.with_suffix('.seal.json'))['design_sha256'];original=q.independent_file(RAW,source_design)
        cfg=original['spec']['config'];meta=original['spec']['field_metadata']
        histories=history_source.history(p['maximum_history_rows'],p['seed'],original['spec']['horizon_s'],meta['cell_length_m'],cfg['target_mean_interstitial_velocity_m_s'],cfg['prolate_semiaxes_m'][1])
        prefix=None;previous_history=None;measurements=[]
        for label,n in zip(('bootstrap','parent','child'),p['history_counts']):
            api.require(time.perf_counter()-started<p['wall_seconds'] and job.utc()<job.policy.utc(w['work_end_utc']),'bounded zero-step clock')
            record=copy.deepcopy(original);record['design_sha256']=api.sha(DESIGN);record['synthetic_resource_fixture_only']=True;record['result']['status']='synthetic_resource_fixture'
            h=histories[:n];record['result']['history']=h;record['result']['checkpoint']['state']['history']=h
            tick=time.perf_counter();record['result']['checkpoint']['state_sha256']=api.digest(record['result']['checkpoint']['state']);hash_s=time.perf_counter()-tick
            path=RUN/(label+'.json.xz');tick=time.perf_counter();seal,state=storage.codec.write_record(path,record,prefix);write_s=time.perf_counter()-tick
            tick=time.perf_counter();decoded,recovered=storage.codec.read_record(path,api.sha(DESIGN),prefix);read_s=time.perf_counter()-tick
            expected=storage.base.raw_bytes(record)
            api.require(storage.base.raw_bytes(decoded)==expected and state==recovered,'complete candidate record and history identity')
            reference=prefix.reference() if prefix is not None else None
            tick=time.perf_counter();ind=q.independent_file(path,api.sha(DESIGN),previous_history,reference);independent_s=time.perf_counter()-tick
            api.require(storage.base.raw_bytes(ind)==expected,'separate original decoder full canonical reconstruction')
            row={'label':label,'history_rows':n,'compressed_bytes':path.stat().st_size,'write_seconds':write_s,'read_seconds':read_s,'state_hash_seconds':hash_s,'independent_read_seconds':independent_s,'raw_sha256':api.sha(path),'original_canonical_bytes':len(expected)}
            measurements.append(row);print('OWNED_LATE_HISTORY',label,n,write_s,read_s,hash_s,flush=True)
            prefix=state;previous_history=h
            del record,decoded,ind,expected,recovered
        verify(p)
        result={'passed':True,'new_trajectory_steps':0,'synthetic_fixture_only':True,'measurements':measurements,'protocol_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in RUN.iterdir() if x.is_file()},'production_authorized':False,'full_resource_forecast':False,'claim':'Lossless storage and measured late-history costs only; no new physical observation or production readiness.'}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('OWNED_LATE_HISTORY_PASS',flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
