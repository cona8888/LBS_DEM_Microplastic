"""Benchmark exact-byte codecs against all sealed Stage175 records. No DEM work."""
from pathlib import Path
import datetime,gzip,hashlib,json,lzma,math,shutil,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage175_staging'))
import combined_cost_preflight_v1 as previous
api,parent=previous.api,previous.parent
DESIGN=ROOT/'stage176_designs/lossless_storage_20260924/design_01.json'
OUT=ROOT/'stage176_evaluations/lossless_storage_20260924/benchmark_01'


def prepare():
    previous.verify(api.read(previous.DESIGN))
    audit=previous.OUT.parent/'independent_audit_01/results.json'
    api.require(api.read(audit)['integration_verified'],'independent integration prerequisite')
    paths=sorted(previous.RUN.rglob('*.json.gz'))
    inputs=[previous.DESIGN,previous.OUT/'results.json',audit,audit.parent/'completion.json']+paths+[p.with_suffix('.seal.json') for p in paths]
    d={'stage':'Stage176','purpose':'Lossless raw evidence compression only; exact original uncompressed bytes required.',
       'physical_changes':[],'trajectory_steps':0,'codecs':['gzip3','gzip6','gzip9','xz3','xz6','xz9'],
       'records':[str(p) for p in paths],'inputs':{str(p):api.sha(p) for p in inputs},'source_sha256':api.sha(__file__),
       'end_utc':'2026-09-24T02:46:55+00:00','disk_reserve_bytes':20*1024**3,'storage_margin':1.3,'runtime_margin':1.3,
       'scope':'No existing evidence rewrite. Codec qualification does not authorize production.'}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(exist_ok=True,parents=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}) and d['source_sha256']==api.sha(__file__),'frozen benchmark')
    api.verify_mapping(d['inputs'])


def main():
    d=api.read(DESIGN);verify(d);OUT.mkdir(parents=True,exist_ok=False);entries=[]
    old=api.read(previous.DESIGN);lookup={c['id']:c for c in old['cases']};parent.b.old.parent.configure()
    for name in d['records']:
        api.require(datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(d['end_utc']),'work cutoff')
        path=Path(name);seal=api.read(path.with_suffix('.seal.json'));raw=gzip.decompress(path.read_bytes())
        api.require(hashlib.sha256(raw).hexdigest()==seal['uncompressed_sha256'] and len(raw)==seal['uncompressed_bytes'],'independent source raw seal')
        rec=parent.storage.read_record(path,api.sha(previous.DESIGN));tx=api.read(path.parent/path.name.replace('segment_','transaction_').replace('.json.gz','.json'))
        timings=[]
        for codec in d['codecs']:
            start=time.perf_counter()
            compressed=gzip.compress(raw,compresslevel=int(codec[4:]),mtime=0) if codec.startswith('gzip') else lzma.compress(raw,preset=int(codec[2:]))
            compress_s=time.perf_counter()-start;start=time.perf_counter()
            decoded=gzip.decompress(compressed) if codec.startswith('gzip') else lzma.decompress(compressed)
            decode_s=time.perf_counter()-start
            api.require(decoded==raw,'byte-for-byte reversible codec')
            timings.append({'codec':codec,'bytes':len(compressed),'compress_s':compress_s,'decode_s':decode_s,'steps':len(rec['rows']),
                            'seconds_per_sim_second':(tx['transaction_wall_s']+compress_s+decode_s)/tx['simulated_s'],
                            'sha256':hashlib.sha256(compressed).hexdigest(),'uncompressed_sha256':hashlib.sha256(decoded).hexdigest()})
        entries.append({'path':name,'case':path.parent.name,'timings':timings,'exact':True})
        print('CODECS',path.parent.name,path.name,[(x['codec'],x['bytes'],round(x['compress_s'],3)) for x in timings],flush=True)
    projections=[];free=shutil.disk_usage(ROOT).free;now=datetime.datetime.now(datetime.timezone.utc)
    available=(datetime.datetime.fromisoformat(old['simulation_cutoff_utc'])-now).total_seconds()/3600
    for codec in d['codecs']:
        rates={};sizes={}
        for e in entries:
            c=lookup[e['case']];x=next(x for x in e['timings'] if x['codec']==codec);key=c['shape'],c['factor']
            rates[key]=max(rates.get(key,0.),x['seconds_per_sim_second']);sizes[key]=max(sizes.get(key,0.),x['bytes']/x['steps'])
        loads=[0.,0.,0.];bytes_total=20_000*max(sizes.values());rows=[]
        for c in old['cases']:
            key=c['shape'],c['factor'];steps=20_000_000 if c['factor']==api.read(parent.DESIGN)['reference_factor'] else 10_000_000
            amount=steps*sizes[key];bytes_total+=amount;hours=c['spec']['horizon_s']*rates[key]*d['runtime_margin']/3600
            worker=min(range(3),key=lambda i:loads[i]);loads[worker]+=hours;rows.append({'case':c['id'],'max_steps':steps,'bytes':amount,'hours':hours})
        projected=math.ceil(bytes_total*d['storage_margin']);makespan=max(loads)+1/6
        projections.append({'codec':codec,'cases':rows,'bytes_with_margin':projected,'time_hours_with_margin':makespan,
                            'storage_passed':projected<=free-d['disk_reserve_bytes'],'time_passed':makespan<=available})
    report={'passed':True,'all_bytes_exact':True,'entries':entries,'projections':projections,'free_bytes':free,'available_hours':available,
            'storage_margin':d['storage_margin'],'disk_reserve_bytes':d['disk_reserve_bytes'],'design_sha256':api.sha(DESIGN),
            'limits':'Cost and byte projections are observed-sample scenarios, not hard bounds on future state complexity. Keep runtime/disk guards.',
            'new_trajectory_steps':0,'campaign_authorized':False,'evaluated_utc':now.isoformat()}
    verify(d);api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
    print('PROJECTIONS',projections,flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:main()
    else:raise ValueError('prepare | run')
