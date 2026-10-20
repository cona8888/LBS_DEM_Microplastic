"""Qualify exact-byte XZ storage on original records and adversarial copies."""
from pathlib import Path
import copy,gzip,hashlib,json,lzma,sys,time
import lossless_record_xz_v1 as codec
import benchmark_lossless_storage_v1 as prior
api=codec.api;ROOT=codec.ROOT
DESIGN=ROOT/'stage176_designs/lossless_storage_20260924/codec_design_01.json'
RUN=ROOT/'stage176_runs/lossless_storage_20260924/qualification_01'
OUT=ROOT/'stage176_evaluations/lossless_storage_20260924/qualification_01'


def prepare():
    r=api.read(prior.OUT/'results.json');api.require(r['passed'] and r['all_bytes_exact'],'codec benchmark prerequisite')
    paths=[Path(x['path']) for x in r['entries']]
    d={'stage':'Stage176 exact-byte XZ','physical_changes':[],'new_trajectory_steps':0,'codec_sha256':api.sha(codec.__file__),
       'source_sha256':api.sha(__file__),'inputs':{str(p):api.sha(p) for p in [prior.DESIGN,prior.OUT/'results.json',prior.previous.DESIGN]+paths+[p.with_suffix('.seal.json') for p in paths]},
       'records':[str(p) for p in paths],'source_design_sha256':api.sha(prior.previous.DESIGN),'format':codec.FORMAT,
       'maximum_raw_bytes':codec.MAX_RAW,'maximum_compressed_bytes':codec.MAX_COMPRESSED,'decoder_memlimit_bytes':codec.MEMLIMIT,
       'purpose':'A new storage adapter, no existing evidence rewritten. All canonical JSON bytes exactly preserved.'}
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}) and d['codec_sha256']==api.sha(codec.__file__) and d['source_sha256']==api.sha(__file__),'code/design seals')
    api.verify_mapping(d['inputs'])


def main():
    d=api.read(DESIGN);verify(d);RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);rows=[];artifacts={}
    for i,source in enumerate(d['records']):
        src=Path(source);raw=gzip.decompress(src.read_bytes());rec=codec.legacy.read_record(src,d['source_design_sha256'])
        dest=RUN/f'record_{i:02d}.json.xz';start=time.perf_counter();seal=codec.write_record(dest,rec);write_s=time.perf_counter()-start
        start=time.perf_counter();decoded=codec.read_bytes(dest,d['source_design_sha256']);read_s=time.perf_counter()-start
        api.require(decoded==raw==codec.raw_bytes(codec.read_record(dest,d['source_design_sha256'])),'exact byte reconstruction')
        rows.append({'source':source,'output':str(dest),'steps':len(rec['rows']),'bytes':dest.stat().st_size,'write_s':write_s,'read_s':read_s,'source_raw_sha256':hashlib.sha256(raw).hexdigest()})
        print('XZ_EXACT',i,len(rec['rows']),dest.stat().st_size,flush=True)
    guards=[];tests=RUN/'guards';tests.mkdir();original=Path(rows[0]['output']);s=api.read(original.with_suffix('.seal.json'));z=original.read_bytes();raw=codec.read_bytes(original,d['source_design_sha256'])
    def expect(label,action):
        try:action()
        except (ValueError,RuntimeError,FileNotFoundError,FileExistsError,lzma.LZMAError,EOFError):guards.append(label);return
        raise AssertionError('guard did not reject: '+label)
    def fixture(label,payload,seal):
        p=tests/(label+'.json.xz')
        with p.open('xb') as f:f.write(payload)
        api.write(p.with_suffix('.seal.json'),seal);return p
    expect('wrong_design',lambda:codec.read_record(original,'0'*64))
    expect('overwrite_record',lambda:codec.write_record(original,rec))
    expect('wrong_suffix',lambda:codec.read_record(original.with_suffix('.gz'),d['source_design_sha256']))
    for label,payload,edit in [('bit_flip',z[:32]+bytes([z[32]^1])+z[33:],{}),('truncated',z[:-20],{}),
                               ('wrong_raw_hash',z,{'uncompressed_sha256':'0'*64}),('wrong_length',z,{'uncompressed_bytes':len(raw)-1}),
                               ('oversized_declaration',z,{'uncompressed_bytes':codec.MAX_RAW+1}),('bad_format',z,{'format':'unknown'}),
                               ('concatenated',z+lzma.compress(b'',preset=9),{})]:
        seal={**s,**edit}
        if label=='concatenated':seal.update(compressed_sha256=hashlib.sha256(payload).hexdigest(),compressed_bytes=len(payload))
        path=fixture(label,payload,seal);expect(label,lambda p=path:codec.read_record(p,d['source_design_sha256']))
    partial=tests/'unsealed.json.xz'
    with partial.open('xb') as f:f.write(z)
    expect('unsealed_partial',lambda:codec.read_record(partial,d['source_design_sha256']))
    orphan=tests/'orphan.json.xz';api.write(orphan.with_suffix('.seal.json'),s)
    expect('orphan_seal_no_overwrite',lambda:codec.write_record(orphan,rec))
    # All JSON primitive edge cases preserve the original canonical bytes, including negative zero and exponent notation.
    edge={'design_sha256':d['source_design_sha256'],'floats':[0.,-0.,5e-324,1e308,-1e-300,float('inf'),-float('inf'),float('nan')],
          'ints':[0,-1,2**100,-2**100],'text':['','UTF-8: \u03bc\u00b5\u7e8a','line\n\t"\\'], 'nested':[{},[],None,True,False]}
    ep=tests/'edge.json.xz';codec.write_record(ep,edge);api.require(codec.read_bytes(ep,d['source_design_sha256'])==codec.raw_bytes(edge),'edge exact bytes')
    for p in RUN.rglob('*'):
        if p.is_file():artifacts[str(p)]=api.sha(p)
    report={'passed':True,'all_original_json_bytes_exact':True,'records':rows,'guard_rejections':guards,'guard_count':len(guards),'primitive_edges_passed':True,
            'artifacts':artifacts,'design_sha256':api.sha(DESIGN),'new_trajectory_steps':0,'production_ready':False,
            'claim':'Encoding qualification only; cumulative history and realistic block sizes still require cost/storage assessment.'}
    verify(d);api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('QUALIFIED_XZ',len(rows),len(guards),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:main()
    else:raise ValueError('prepare | run')
