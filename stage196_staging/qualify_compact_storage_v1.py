"""Zero-step compact-wrapper checks; original logical bytes remain exact."""
from pathlib import Path
import copy, hashlib, json, os, sys, time, traceback
import lossless_compact_xz_v1 as candidate
import qualify_failure_codec_v1 as q
api, job, ROOT = q.api, q.job, q.ROOT
WORK = ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/contract_01.json'
DESIGN = WORK.with_name('compact_storage_01.json')
RUN = Path('D:/MATDEM_MICROPLASTIC/stage196_runs/deadline_recovery_20260925/compact_storage_01')
OUT = ROOT/'stage196_evaluations/deadline_recovery_20260925/compact_storage_01'
OLD = ROOT/'stage195_runs/repaired_stack_preflight_20260925/preflight_01'

def reject(fn, name):
    try: fn()
    except (ValueError, FileExistsError, KeyError, TypeError): return name
    raise AssertionError('accepted invalid evidence '+name)

def run():
    work=api.read(WORK); api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work cutoff')
    candidate.verify_bindings(); job.verify(api.read(job.DESIGN))
    sources=sorted((OLD/'probes').glob('*_contact.json.xz'))+[OLD/'probes/serial.json.xz',
        ROOT/'stage194_runs/evidence_repair_20260924/diagnostic_replay_01/diagnostic.json.xz']
    chains=[sorted(folder.glob('segment_*.json.xz')) for folder in sorted((OLD/'live').iterdir()) if folder.is_dir()]
    api.require(len(sources)==8 and len(chains)==6 and all(len(x)==2 for x in chains),'exact fixture inventory')
    files=sources+[p for chain in chains for p in chain]
    inputs={str(p):api.sha(p) for p in [WORK,Path(__file__),Path(candidate.__file__),Path(q.__file__),
        Path(candidate.original.__file__),Path(candidate.base.__file__),Path(candidate.original.original.__file__),Path(candidate.previous.__file__)]+files+[p.with_suffix('.seal.json') for p in files]}
    job.commit(DESIGN,{'stage':'Stage196 storage-only compact wrapper preset1 qualification','inputs':inputs,'new_trajectory_steps':0,
        'unchanged_canonical_bytes':True,'unchanged_bounded_reader':True,'production_authorized':False})
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'protocol_sha256':api.sha(DESIGN),'reserved_new_accepted_steps':0})
    synthetic=[];reports=[];rejections=[]
    try:
        for name,env in q.fixtures():
            before=candidate.base.raw_bytes(env); path=RUN/(name+'.json.xz')
            candidate.instance.write_envelope(path,env)
            plain=candidate.base.read_record(path,env['design_sha256'])
            api.require(candidate.base.raw_bytes(q.independent_unpack(plain))==before,'independent synthetic bytes '+name)
            api.require(candidate.base.raw_bytes(candidate.instance.read_envelope(path,env['design_sha256']))==before,'production synthetic bytes '+name)
            api.require(candidate.base.raw_bytes(env)==before,'no mutation')
            synthetic.append(name)
        for index,source in enumerate(sources):
            api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work cutoff')
            sha=api.read(source.with_suffix('.seal.json'))['design_sha256']
            record=q.independent_file(source,sha); before=candidate.base.raw_bytes(record)
            dest=RUN/f'real_{index:02d}.json.xz'; t=time.perf_counter()
            seal,_=candidate.codec.write_record(dest,record); write_s=time.perf_counter()-t
            t=time.perf_counter(); decoded,_=candidate.codec.read_record(dest,sha); read_s=time.perf_counter()-t
            independent=q.independent_file(dest,sha)
            api.require(candidate.base.raw_bytes(decoded)==before==candidate.base.raw_bytes(independent),'exact real bytes')
            reports.append({'source':str(source),'output':str(dest),'write_seconds':write_s,'read_seconds':read_s,'bytes':seal['compressed_bytes'],'original_bytes_sha256':hashlib.sha256(before).hexdigest()})
            print('FAST_STORAGE_REAL',index,round(write_s,3),round(read_s,3),flush=True)
        for ci,chain in enumerate(chains):
            old_prefix=new_prefix=None;old_rows=old_ref=new_rows=new_ref=None
            for si,source in enumerate(chain):
                sha=api.read(source.with_suffix('.seal.json'))['design_sha256']
                record=q.independent_file(source,sha,old_rows,old_ref)
                _,old_prefix=candidate.original.codec.read_record(source,sha,old_prefix)
                old_rows=record['result']['history'];old_ref=old_prefix.reference()
                dest=RUN/f'chain_{ci}_{si}.json.xz'; seal,new_state=candidate.codec.write_record(dest,record,new_prefix)
                decoded,_=candidate.codec.read_record(dest,sha,new_prefix)
                independent=q.independent_file(dest,sha,new_rows,new_ref)
                raw=candidate.base.raw_bytes(record)
                api.require(raw==candidate.base.raw_bytes(decoded)==candidate.base.raw_bytes(independent),'exact reference-chain original bytes')
                new_prefix=new_state;new_rows=record['result']['history'];new_ref=new_state.reference()
                if si==1:
                    rejections.append(reject(lambda:candidate.codec.read_record(dest,sha),'missing_parent_'+str(ci)))
                reports.append({'source':str(source),'output':str(dest),'exact_chain':True,'bytes':seal['compressed_bytes']})
        good=RUN/'healthy_reference.json.xz'; old_sha=api.sha(good)
        rejections.append(reject(lambda:candidate.instance.write_envelope(good,q.fixtures()[0][1]),'immutable_collision'))
        api.require(api.sha(good)==old_sha,'collision preserved bytes')
        # New corrupt fixtures only, each with a deliberately corresponding seal.
        data=good.read_bytes(); original_seal=api.read(good.with_suffix('.seal.json'))
        for label,buf,updates in [('wrong_compressed',data[:-1]+bytes([data[-1]^1]),{}),
            ('trailing',data+b'junk',{'compressed_sha256':hashlib.sha256(data+b'junk').hexdigest(),'compressed_bytes':len(data)+4}),
            ('wrong_raw',data,{'uncompressed_sha256':'0'*64}),('wrong_size',data,{'uncompressed_bytes':1}),
            ('wrong_design',data,{'design_sha256':'0'*64})]:
            dest=RUN/(label+'.json.xz')
            with dest.open('xb') as stream:stream.write(buf)
            job.commit(dest.with_suffix('.seal.json'),{**original_seal,**updates})
            rejections.append(reject(lambda:candidate.base.read_bytes(dest,'a'*64),label))
        api.verify_mapping(inputs);candidate.verify_bindings()
        result={'passed':True,'new_trajectory_steps':0,'inputs':inputs,'synthetic_fixtures':synthetic,'real_and_chain_records':reports,
            'rejections':rejections,'production_authorized':False,'artifacts':{str(p):api.sha(p) for p in RUN.iterdir() if p.is_file()}}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('FAST_STORAGE_PASS',len(synthetic),len(reports),len(rejections),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':run()
