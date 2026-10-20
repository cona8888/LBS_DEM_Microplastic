"""Independent materialization using stdlib LZMA/JSON, no candidate decoder."""
from pathlib import Path
import hashlib,json,lzma
import qualify_history_prefix_v1 as job
api=job.api
OUT=job.OUT.parent/'independent_audit_01'


def raw(record):return (json.dumps(record,sort_keys=True,indent=2,allow_nan=True)+'\n').encode('utf-8')
def compact(history):return json.dumps(history,separators=(',',':'),allow_nan=True).encode('utf-8')
def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    d=api.read(job.DESIGN);job.verify(d);r=api.read(job.OUT/'results.json');api.verify_mapping(r['artifacts'])
    api.require(r['passed'] and api.read(job.OUT/'completion.json')['results_sha256']==api.sha(job.OUT/'results.json'),'qualified result seal')
    cache={};checks=[]
    for row in r['records']:
        p=Path(row['output']);encoded=p.read_bytes();s=api.read(p.with_suffix('.seal.json'));blob=lzma.decompress(encoded)
        api.require(sha(encoded)==s['compressed_sha256'] and sha(blob)==s['uncompressed_sha256'] and len(blob)==s['uncompressed_bytes'],'independent envelope seals')
        e=json.loads(blob);meta=e['history'];prefix=meta['prefix'];history=[]
        if prefix is not None:
            api.require(prefix['path'] in cache,'ordered explicit ancestor')
            previous=cache[prefix['path']]
            api.require(previous['compressed_sha256']==prefix['compressed_sha256'] and previous['original_sha256']==prefix['original_sha256'],'ancestor archive/raw binding')
            api.require(len(previous['history'])==prefix['history_length'] and sha(compact(previous['history']))==prefix['history_sha256'],'ancestor history binding')
            history=list(previous['history'])
        history=history+meta['appended_rows'];api.require(len(history)==meta['length'] and sha(compact(history))==meta['sha256'],'history reconstruction')
        record=e['payload'];record['result']['history']=history;record['result']['checkpoint']['state']['history']=history
        reconstructed=raw(record);original=lzma.decompress(Path(row['source']).read_bytes())
        api.require(reconstructed==original and sha(reconstructed)==e['original_uncompressed_sha256']==row['original_raw_sha256'],'every original byte independently recovered')
        api.require(len(reconstructed)==e['original_uncompressed_bytes']==row['original_raw_bytes'],'original length')
        cache[str(p.resolve())]={'compressed_sha256':s['compressed_sha256'],'original_sha256':sha(reconstructed),'history':history}
        checks.append({'source':row['source'],'output':str(p),'parent':prefix['path'] if prefix else None,'exact_original_sha256':sha(reconstructed),
                       'history_rows':len(history),'appended_rows':len(meta['appended_rows'])})
    api.require(len(checks)==r['exact_original_records']==30,'six complete five-record branches')
    verdict={'passed':True,'exact_original_records':len(checks),'checks':checks,'candidate_decoder_used':False,'new_trajectory_steps':0,
             'design_sha256':api.sha(job.DESIGN),'qualification_result_sha256':api.sha(job.OUT/'results.json'),'audit_source_sha256':api.sha(__file__),
             'claim':'Representation-only evidence: original canonical JSON is exactly recoverable with its hash-bound parent chain.'}
    job.verify(d);OUT.mkdir(exist_ok=False);api.write(OUT/'results.json',verdict);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('PREFIX_INDEPENDENT',len(checks),flush=True)


if __name__=='__main__':main()
