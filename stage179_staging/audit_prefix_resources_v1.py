"""Independent seals, reconstruction and arithmetic for resource-only fixtures."""
from pathlib import Path
import hashlib,json,lzma,math,time
import stress_prefix_resources_v1 as job
api=job.api
OUT=job.OUT.parent/'resource_independent_audit_01'


def sha(data):return hashlib.sha256(data).hexdigest()
def compact(rows):return json.dumps(rows,separators=(',',':'),allow_nan=True).encode()
def raw(record):return (json.dumps(record,sort_keys=True,indent=2,allow_nan=True)+'\n').encode()


def main():
    start=time.perf_counter();d=api.read(job.DESIGN);job.verify(d);r=api.read(job.OUT/'results.json');api.verify_mapping(r['artifacts'])
    api.require(api.read(job.OUT/'completion.json')['results_sha256']==api.sha(job.OUT/'results.json'),'resource result seal')
    checks=[];families={};bootstrap_bytes=0
    for case,row in zip(d['cases'],r['cases']):
        api.require(case['case']==row['case'],'frozen case order');previous=None
        for measure in row['measurements']:
            path=Path(measure['path']);s=api.read(path.with_suffix('.seal.json'));compressed=path.read_bytes();blob=lzma.decompress(compressed)
            api.require(s['design_sha256']==api.sha(job.DESIGN) and sha(compressed)==s['compressed_sha256'] and len(compressed)==s['compressed_bytes']==measure['compressed_bytes'],'compressed seal')
            api.require(sha(blob)==s['uncompressed_sha256'] and len(blob)==s['uncompressed_bytes'],'envelope seal')
            env=json.loads(blob);meta=env['history'];parent=meta['prefix'];history=[]
            if parent is not None:
                api.require(previous is not None and parent==previous['reference'],'explicit parent binding');history=previous['history']
            else:api.require(previous is None and measure['label']=='bootstrap','standalone bootstrap')
            history=history+meta['appended_rows'];hs=sha(compact(history))
            api.require(len(history)==meta['length']==measure['history_rows'] and hs==meta['sha256']==measure['original_history_sha256'],'complete history seal')
            rec=env['payload'];rec['result']['history']=history;rec['result']['checkpoint']['state']['history']=history
            api.require(rec['synthetic_resource_fixture_only'] is True and rec['result']['status']=='synthetic_resource_fixture','never actual physics evidence')
            api.require(api.digest(rec['result']['checkpoint']['state'])==rec['result']['checkpoint']['state_sha256'],'synthetic state checksum')
            materialized=raw(rec);rs=sha(materialized)
            api.require(rs==env['original_uncompressed_sha256']==measure['original_uncompressed_sha256'] and len(materialized)==env['original_uncompressed_bytes'],'exact full canonical reconstruction')
            previous={'history':history,'reference':{'path':str(path.resolve()),'design_sha256':api.sha(job.DESIGN),'compressed_sha256':s['compressed_sha256'],
                'original_sha256':rs,'history_sha256':hs,'history_length':len(history)}}
            checks.append({'case':case['case'],'label':measure['label'],'rows':len(history),'original_sha256':rs})
            if measure['label']=='bootstrap':bootstrap_bytes+=len(compressed)
        child=row['measurements'][-1];rate=(row['baseline_transaction_s']+child['write_s']+child['read_s']+child['state_hash_s'])/row['baseline_simulated_s']
        api.require(rate==row['seconds_per_sim_s_conservative'],'local timing arithmetic')
        key=case['shape'],case['factor'];size=max(x['compressed_bytes'] for x in row['measurements'][1:]);old=families.get(key,(0,0.))
        families[key]=(max(old[0],size),max(old[1],rate));print('RESOURCE_AUDIT',case['case'],flush=True)
    workers=[0.,0.,0.];amount=bootstrap_bytes+2*max(x[0] for x in families.values());costs=[]
    for c in d['cases']:
        size,rate=families[c['shape'],c['factor']];n=math.ceil(c['step_ceiling']/10000);amount+=n*size
        hours=c['horizon_s']*rate*1.3/3600;w=min(range(3),key=lambda i:workers[i]);workers[w]+=hours
        costs.append({'case':c['case'],'worker':w,'hours':hours,'raw_bytes':n*size,'records':n})
    api.require(costs==r['costs'] and amount==r['raw_storage_before_margin'],'fixed-order scheduler and storage arithmetic')
    trace=80_020_000*13*8+math.ceil(80_020_000/10000)*8192+1024**3;storage=math.ceil((amount+trace)*1.3);hours=max(workers)+1/6
    api.require(storage==r['bytes_with_margin'] and trace==r['audit_storage_before_margin'] and hours==r['time_hours_with_margin'],'complete margin arithmetic')
    api.require((storage<=r['free_bytes']-r['reserve_bytes'])==r['storage_scenario_passed'] and (hours<=r['available_hours'])==r['time_scenario_passed'],'unchanged resource verdicts')
    api.require(len(checks)==18,'all stress fixtures');job.verify(d)
    report={'passed':True,'fixtures':checks,'storage_bytes_with_margin':storage,'time_hours_with_margin':hours,'storage_scenario_passed':r['storage_scenario_passed'],
       'time_scenario_passed':r['time_scenario_passed'],'source_result_sha256':api.sha(job.OUT/'results.json'),'design_sha256':api.sha(job.DESIGN),
       'audit_source_sha256':api.sha(__file__),'candidate_decoder_used':False,'new_trajectory_steps':0,'wall_seconds':time.perf_counter()-start,
       'claim':'Independent representation and arithmetic audit of measured synthetic resource scenarios, not a runtime guarantee or launch authority.'}
    OUT.mkdir(exist_ok=False);api.write(OUT/'results.json',report);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
    print('RESOURCE_INDEPENDENT_PASS',storage,hours,flush=True)


if __name__=='__main__':main()
