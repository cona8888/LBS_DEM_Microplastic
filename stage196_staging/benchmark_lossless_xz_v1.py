"""Zero-step lossless archive benchmark: same sealed bytes, lower XZ effort.

CPU/storage test only. Fresh per-mode files are retained; old artifacts are not
modified. Data always round-trips to the old uncompressed SHA256 and CRC64.
"""
from pathlib import Path
import hashlib, json, lzma, os, shutil, sys, time, traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage194_staging'))
import qualify_failure_codec_v1 as q
job,api=q.job,q.api
WORK=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/contract_01.json'
RUN=Path('D:/MATDEM_MICROPLASTIC/stage196_runs/deadline_recovery_20260925/lossless_xz_01')
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/lossless_xz_01'
BASE=ROOT/'stage194_runs/evidence_repair_20260924'
SOURCES=[BASE/'broader_early_dispatch_01/healthy_prefix.json.xz',
         BASE/'early_semismooth_restart_01/call_01.json.xz',
         BASE/'diagnostic_replay_01/call_01.json.xz',
         ROOT/'stage195_runs/repaired_stack_preflight_20260925/preflight_01/probes/s2_i0_sphere_f0p03125_contact.json.xz',
         ROOT/'stage195_runs/repaired_stack_preflight_20260925/preflight_01/probes/s2_i124_sphere_f0p0625_contact.json.xz']

def run():
    w=api.read(WORK); end=job.policy.utc(w['work_end_utc']).timestamp()
    api.require(time.time()<end,'work clock');job.verify(api.read(job.DESIGN))
    inputs={str(p):api.sha(p) for p in [WORK,Path(__file__)]+SOURCES+[p.with_suffix('.seal.json') for p in SOURCES]}
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'maximum_archive_writes':25})
    rows=[]
    try:
        for i,source in enumerate(SOURCES):
            seal=api.read(source.with_suffix('.seal.json'))
            api.require(api.sha(source)==seal['compressed_sha256'],'source compressed seal')
            payload=lzma.decompress(source.read_bytes())
            api.require(len(payload)==seal['uncompressed_bytes'] and hashlib.sha256(payload).hexdigest()==seal['uncompressed_sha256'],'source raw seal')
            # Enforce the unchanged schema/independent envelope reconstruction.
            q.independent_unpack(json.loads(payload))
            for preset in (9,6,3,1,0):
                api.require(time.time()<end and shutil.disk_usage(RUN).free>w['minimum_free_disk_bytes']+4*q.repair.base.MAX_COMPRESSED,'time/disk reserve')
                dest=RUN/f'fixture_{i:02d}_preset{preset}.json.xz'
                start=time.perf_counter(); comp=lzma.LZMACompressor(format=lzma.FORMAT_XZ,check=lzma.CHECK_CRC64,preset=preset)
                with dest.open('xb') as f:
                    for at in range(0,len(payload),q.repair.base.CHUNK): f.write(comp.compress(payload[at:at+q.repair.base.CHUNK]))
                    f.write(comp.flush()); f.flush(); os.fsync(f.fileno())
                write_s=time.perf_counter()-start
                api.require(dest.stat().st_size<=q.repair.base.MAX_COMPRESSED,'unchanged compressed-size gate')
                out_seal={**seal,'compression':f'XZ/LZMA2 preset{preset} CRC64','compressed_sha256':api.sha(dest),'compressed_bytes':dest.stat().st_size}
                job.commit(dest.with_suffix('.seal.json'),out_seal)
                start=time.perf_counter(); recovered=q.repair.base.read_bytes(dest,seal['design_sha256']);read_s=time.perf_counter()-start
                api.require(recovered==payload,'exact frozen bytes under existing bounded decoder')
                item={'fixture':i,'source':str(source),'preset':preset,'raw_bytes':len(payload),'archive_bytes':dest.stat().st_size,'write_seconds':write_s,'read_seconds':read_s,'raw_sha256':seal['uncompressed_sha256'],'path':str(dest)}
                rows.append(item);job.commit(OUT/f'fixture_{i:02d}_preset{preset}.json',item)
                print('XZ_BENCH',i,preset,round(write_s,3),round(read_s,3),dest.stat().st_size,flush=True)
        api.verify_mapping(inputs)
        r={'passed':len(rows)==25,'new_trajectory_steps':0,'inputs':inputs,'measurements':rows,'free_disk_bytes':shutil.disk_usage(RUN).free,
            'artifacts':{str(p):api.sha(p) for p in RUN.iterdir() if p.is_file()},'production_authorized':False,'claim':'Exact lossless storage benchmark only; no numerical or full-campaign readiness claim.'}
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')})
        print('XZ_BENCH_PASS',r['passed'],flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':run()
