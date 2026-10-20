"""Independent compressed, logical-record and history reconstruction, zero steps."""
from pathlib import Path
import hashlib, json, lzma
import qualify_budget_continuation_v1 as p
job,api,q=p.job,p.api,p.pre.q
OUT=p.OUT.parent/'independent_transport_01'

def main():
    protocol=api.read(p.DESIGN);p.verify(protocol);r=api.read(p.OUT/'results.json')
    api.require(api.read(p.OUT/'completion.json')['results_sha256']==api.sha(p.OUT/'results.json'),'result seal');api.verify_mapping(r['artifacts'])
    job.commit(OUT/'launch.json',{'source_sha256':api.sha(__file__),'protocol_sha256':api.sha(p.DESIGN),'source_results_sha256':api.sha(p.OUT/'results.json'),'new_trajectory_steps':0})
    inventory={x.resolve() for x in p.RUN.glob('*.json.xz')};states={};histories={};reports=[]
    def decode(path):
        path=path.resolve()
        if path in states:return
        api.require(path in inventory,'immutable declared raw inventory')
        seal=api.read(path.with_suffix('.seal.json'));packed=path.read_bytes();raw=lzma.decompress(packed)
        api.require(hashlib.sha256(packed).hexdigest()==seal['compressed_sha256'] and hashlib.sha256(raw).hexdigest()==seal['uncompressed_sha256'] and len(raw)==seal['uncompressed_bytes'],'independent compressed/uncompressed seals')
        env=q.independent_unpack(json.loads(raw));prefix=None;ref=None;history=None
        if env['history']['prefix'] is not None:
            parent=Path(env['history']['prefix']['path']).resolve();decode(parent);prefix=states[parent];ref=prefix.reference();history=histories[parent]
            api.require(env['history']['prefix']==ref,'exact independently resolved history ancestor')
        independent=q.independent_file(path,api.sha(job.DESIGN),history,ref);record,state=job.codec.read_record(path,api.sha(job.DESIGN),prefix)
        api.require(q.repair.base.raw_bytes(independent)==q.repair.base.raw_bytes(record),'separate decoder exact logical record')
        states[path]=state;histories[path]=independent['result']['history'];reports.append({'path':str(path),'steps':len(record['rows']),'logical_sha256':state.original_sha256,'raw_sha256':api.sha(path)})
    for path in sorted(inventory):decode(path)
    api.require(len(reports)==6 and sum(x['steps'] for x in reports)==r['new_accepted_steps'],'exact raw inventory and accepted step total')
    result={'passed':True,'records':reports,'new_trajectory_steps':0,'source_sha256':api.sha(__file__),'qualification_results_sha256':api.sha(p.OUT/'results.json')}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('INDEPENDENT_TRANSPORT_PASS',len(reports),flush=True)

if __name__=='__main__':main()
