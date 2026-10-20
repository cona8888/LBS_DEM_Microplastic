"""Zero-trajectory synthetic resource stress for cumulative checkpoint history.

Synthetic fixture objects are never written as simulation records or used as
restart states. Only sizes, timings, seeds and hashes are retained.
"""
from pathlib import Path
import copy,datetime,hashlib,lzma,math,shutil,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage177_staging'))
import extended_optimized_preflight_v1 as previous
import audit_extended_preflight_v1 as audit
api,codec=previous.api,previous.codec
DESIGN=ROOT/'stage178_designs/resource_readiness_20260924/history_design_01.json'
OUT=ROOT/'stage178_evaluations/resource_readiness_20260924/history_stress_01'


def prepare():
    a=api.read(audit.OUT/'results.json');api.require(a['integration_verified'],'extended independent audit')
    api.require(api.read(audit.OUT/'completion.json')['results_sha256']==api.sha(audit.OUT/'results.json'),'audit seal')
    d0=api.read(previous.DESIGN);previous.verify(d0);old=api.read(previous.parent.DESIGN);cases=[]
    inputs=[previous.DESIGN,audit.OUT/'results.json',audit.OUT/'completion.json',previous.parent.DESIGN]
    for c in d0['cases']:
        ceiling=next(x['step_ceiling'] for x in old['cases'] if x['id']==c['id']);p=previous.RUN/c['id']/'segment_002.json.xz'
        cases.append({'case':c['id'],'shape':c['shape'],'factor':c['factor'],'step_ceiling':ceiling,'source':str(p),'horizon_s':c['spec']['horizon_s']})
        inputs.extend([p,p.with_suffix('.seal.json'),p.with_suffix('.transaction.json')])
    d={'stage':'Stage178 history resource stress','purpose':'Synthetic high-entropy history scaling only. No trajectories or scientific observations generated.',
       'cases':cases,'fractions':[.25,.5,.75,1.],'seed':17820260924,'history_cadence_steps':250,'segment_steps':10000,
       'runtime_margin':1.3,'storage_margin':1.3,'wall_seconds':1200,'cutoff_utc':'2026-09-24T02:46:55+00:00',
       'sources':{str(Path(__file__).resolve()):api.sha(__file__),str(Path(codec.__file__).resolve()):api.sha(codec.__file__)},
       'inputs':{str(p):api.sha(p) for p in inputs},'new_trajectory_steps':0,
       'acceptance':'Resource scenarios must retain 20GiB disk reserve and original time margin; not a guarantee or production authority.'}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(exist_ok=True,parents=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])


def history(n,seed,horizon,L,U,b):
    rng=np.random.default_rng(seed);p=rng.normal(size=(n,3));p/=np.linalg.norm(p,axis=1)[:,None]
    q=rng.normal(size=(n,6))*U
    # Deliberately independent poses/velocities have substantially higher entropy
    # than the smooth/near-rest histories observed here. They are not trajectories.
    arr=np.c_[np.linspace(horizon/n,horizon,n),rng.uniform(0,L,(n,3)),p,q,
              rng.uniform(-1e-5*b,0,n),rng.uniform(-1e-8,0,n),np.arange(1,n+1)*250]
    out=arr.tolist()
    for row in out:row[-1]=int(row[-1])
    return out


def run():
    d=api.read(DESIGN);verify(d);OUT.mkdir(exist_ok=False,parents=True);started=time.perf_counter();rows=[]
    for ci,c in enumerate(d['cases']):
        raw=codec.read_record(Path(c['source']),api.sha(previous.DESIGN));tx=api.read(Path(c['source']).with_suffix('.transaction.json'));cfg=raw['spec']['config'];baseline_history=len(raw['result']['history'])
        for fraction in d['fractions']:
            api.require(time.perf_counter()-started<d['wall_seconds'] and datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(d['cutoff_utc']),'work/time guard')
            n=math.ceil(c['step_ceiling']*fraction/d['history_cadence_steps']);t=time.perf_counter()
            synthetic=history(n,d['seed']+ci,c['horizon_s']*fraction,raw['spec']['field_metadata']['cell_length_m'],cfg['target_mean_interstitial_velocity_m_s'],cfg['prolate_semiaxes_m'][1])
            fixture=copy.deepcopy(raw);fixture['synthetic_resource_fixture_only']=True
            fixture['result']['history']=synthetic;fixture['result']['checkpoint']['state']['history']=synthetic
            fixture['result']['checkpoint']['state_sha256']=api.digest(fixture['result']['checkpoint']['state'])
            data=codec.raw_bytes(fixture);prepare_s=time.perf_counter()-t;t=time.perf_counter()
            z=lzma.compress(data,preset=9,check=lzma.CHECK_CRC64);encode_s=time.perf_counter()-t;t=time.perf_counter();decoded=lzma.decompress(z);decode_s=time.perf_counter()-t
            api.require(decoded==data and len(data)<=codec.MAX_RAW and len(z)<=codec.MAX_COMPRESSED,'exact bounded stress encoding')
            out={'case':c['case'],'fraction_of_step_ceiling':fraction,'history_rows':n,'baseline_history_rows':baseline_history,
                 'raw_bytes':len(data),'compressed_bytes':len(z),'prepare_seconds':prepare_s,'compress_seconds':encode_s,'decode_seconds':decode_s,
                 'fixture_raw_sha256':hashlib.sha256(data).hexdigest(),'fixture_compressed_sha256':hashlib.sha256(z).hexdigest(),
                 'baseline_compute_s':tx['compute_s'],'baseline_transaction_s':tx['transaction_s'],'baseline_simulated_s':tx['simulated_s']}
            rows.append(out);api.write(OUT/f'measurement_{ci}_{fraction}.json',out)
            print('HISTORY_STRESS',c['case'],fraction,'rows',n,'MB',round(len(z)/1e6,3),'seconds',round(prepare_s+encode_s+decode_s,3),flush=True)
            del synthetic,fixture,data,z,decoded
    families={}
    for c in d['cases']:
        key=(c['shape'],c['factor']);part=[x for x in rows if x['case']==c['case']]
        # Worst measured history size/cost is applied to EVERY block (not just
        # the last quarter). Deliberately conservative, with an additional 30%.
        size=max(x['compressed_bytes'] for x in part)
        cost=max((x['baseline_transaction_s']+x['prepare_seconds']+x['compress_seconds']+x['decode_seconds'])/x['baseline_simulated_s'] for x in part)
        old=families.get(key,{'size':0,'rate':0});families[key]={'size':max(old['size'],size),'rate':max(old['rate'],cost)}
    bytes_total=0.;loads=[0.,0.,0.];costs=[]
    for c in d['cases']:
        f=families[c['shape'],c['factor']];blocks=math.ceil(c['step_ceiling']/d['segment_steps']);amount=blocks*f['size'];bytes_total+=amount
        hours=c['horizon_s']*f['rate']*d['runtime_margin']/3600;worker=min(range(3),key=lambda i:loads[i]);loads[worker]+=hours
        costs.append({'case':c['case'],'blocks':blocks,'bytes':amount,'hours':hours,'worker':worker})
    bytes_total+=2*max(x['size'] for x in families.values());storage=math.ceil(bytes_total*d['storage_margin']);free=shutil.disk_usage(ROOT).free
    now=datetime.datetime.now(datetime.timezone.utc);available=(datetime.datetime.fromisoformat(api.read(previous.prior.DESIGN)['simulation_cutoff_utc'])-now).total_seconds()/3600
    report={'passed':True,'lossless_stress_passed':True,'measurements':rows,'costs':costs,'bytes_with_margin':storage,'time_hours_with_margin':max(loads)+1/6,
            'free_bytes':free,'reserve_bytes':codec.RESERVE,'available_hours':available,'storage_scenario_passed':storage<=free-codec.RESERVE,
            'time_scenario_passed':max(loads)+1/6<=available,'wall_seconds':time.perf_counter()-started,'new_trajectory_steps':0,
            'basis':'Highest measured synthetic high-entropy end-history cost applied to every record, maximum within each shape/timestep family, then 30% margin.',
            'limitations':'Stress scenario, not mathematical upper bound on future encoding or contact cost. Disk/time/step guards remain mandatory. No production authority.',
            'design_sha256':api.sha(DESIGN),'evaluated_utc':now.isoformat()}
    verify(d);api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
    print('HISTORY_FINAL','GB',storage/1e9,'H',report['time_hours_with_margin'],'STORAGE',report['storage_scenario_passed'],'TIME',report['time_scenario_passed'],flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
