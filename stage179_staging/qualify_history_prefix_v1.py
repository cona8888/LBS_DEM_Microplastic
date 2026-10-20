"""Zero-step lossless prefix-codec tests on every Stage177 branch and record."""
from pathlib import Path
from dataclasses import replace,FrozenInstanceError
import copy,datetime,hashlib,sys,time
import lossless_history_prefix_v1 as codec
sys.path.insert(0,str(codec.ROOT/'stage177_staging'))
import extended_optimized_preflight_v1 as prior
import audit_extended_preflight_v1 as independent
api,ROOT=codec.api,codec.ROOT
DESIGN=ROOT/'stage179_designs/history_prefix_20260924/design_01.json'
RUN=ROOT/'stage179_runs/history_prefix_20260924/qualification_01'
OUT=ROOT/'stage179_evaluations/history_prefix_20260924/qualification_01'


def prepare():
    d0=api.read(prior.DESIGN);prior.verify(d0);a=api.read(independent.OUT/'results.json');api.require(a['integration_verified'],'independent trajectory evidence')
    inputs=[prior.DESIGN,independent.OUT/'results.json',independent.OUT/'completion.json'];cases=[]
    for c in d0['cases']:
        paths=[prior.RUN/c['id']/n for n in ['segment_001.json.xz','segment_002.json.xz','restart_full.json.xz','restart_first.json.xz','restart_last.json.xz']]
        cases.append({'case':c['id'],'paths':[str(p) for p in paths],'parent_indices':[None,0,1,1,3]})
        for p in paths:inputs.extend([p,p.with_suffix('.seal.json')])
    d={'stage':'Stage179 lossless history prefix','purpose':'Eliminate repeated cumulative history in storage only. Full original canonical bytes must be restored.',
       'physical_changes':[],'new_trajectory_steps':0,'cases':cases,'original_design_sha256':api.sha(prior.DESIGN),
       'inputs':{str(p):api.sha(p) for p in inputs},'sources':{str(Path(p).resolve()):api.sha(p) for p in [__file__,codec.__file__,codec.base.__file__]},
       'codec':codec.ENCODING,'cutoff_utc':'2026-09-24T02:46:55+00:00','maximum_wall_seconds':900,
       'limitations':'Prefix-linked storage is not standalone per segment. A complete verified ancestor chain is mandatory; missing parents fail closed.'}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(exist_ok=True,parents=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False);start=time.perf_counter();rows=[];guards=[];first_examples=None
    for case in d['cases']:
        folder=RUN/case['case'];folder.mkdir();states=[];decoded_states=[]
        for i,(path,pi) in enumerate(zip(case['paths'],case['parent_indices'])):
            api.require(time.perf_counter()-start<d['maximum_wall_seconds'] and datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(d['cutoff_utc']),'bounded work')
            rec=independent.independent_read(path,d['original_design_sha256']);expected=codec.base.read_bytes(Path(path),d['original_design_sha256']);original_hash=hashlib.sha256(expected).hexdigest()
            before=codec.base.raw_bytes(rec);prefix=states[pi] if pi is not None else None;dest=folder/Path(path).name;t=time.perf_counter()
            seal,state=codec.write_record(dest,rec,prefix);write_s=time.perf_counter()-t;t=time.perf_counter()
            decoded,ds=codec.read_record(dest,d['original_design_sha256'],decoded_states[pi] if pi is not None else None);read_s=time.perf_counter()-t
            api.require(codec.base.raw_bytes(decoded)==expected==before==codec.base.raw_bytes(rec),'exact original bytes, no input mutation')
            api.require(ds==state and state.original_sha256==original_hash,'independent reader state identity')
            states.append(state);decoded_states.append(ds)
            rows.append({'source':path,'output':str(dest),'parent_index':pi,'source_compressed_bytes':Path(path).stat().st_size,'encoded_compressed_bytes':dest.stat().st_size,
                         'original_raw_sha256':original_hash,'original_raw_bytes':len(expected),'history_rows':state.history_length,'write_s':write_s,'read_s':read_s,'steps':len(rec['rows'])})
            if first_examples is None and i==1:first_examples=(rec,prefix,dest,state)
            print('PREFIX_EXACT',case['case'],i,'bytes',dest.stat().st_size,'history',state.history_length,flush=True)
    rec,prefix,path,state=first_examples;env,hist=codec.encode(rec,prefix)
    def reject(label,fn):
        try:fn()
        except (ValueError,RuntimeError,FileExistsError,FileNotFoundError,FrozenInstanceError):guards.append(label);return
        raise AssertionError('guard accepted '+label)
    reject('missing_prefix',lambda:codec.read_record(path,d['original_design_sha256']))
    reject('wrong_prefix',lambda:codec.read_record(path,d['original_design_sha256'],state))
    reject('wrong_design',lambda:codec.read_record(path,'0'*64,prefix))
    reject('overwrite',lambda:codec.write_record(path,rec,prefix))
    reject('mutable_prefix_bytes',lambda:codec.validate_prefix(replace(prefix,history_bytes=bytearray(prefix.history_bytes)),d['original_design_sha256']))
    reject('forged_prefix_bytes',lambda:codec.validate_prefix(replace(prefix,history_bytes=b'[]',history_sha256=hashlib.sha256(b'[]').hexdigest(),history_length=0),d['original_design_sha256']))
    reject('changed_parent_hash',lambda:codec.validate_prefix(replace(prefix,compressed_sha256='0'*64),d['original_design_sha256']))
    reject('missing_parent',lambda:codec.validate_prefix(replace(prefix,path=str(RUN/'does_not_exist.json.xz')),d['original_design_sha256']))
    reject('frozen_context',lambda:setattr(prefix,'history_length',0))
    for label,edit in [('wrong_original_hash',lambda e:e.update(original_uncompressed_sha256='0'*64)),
                       ('oversize_original',lambda e:e.update(original_uncompressed_bytes=codec.base.MAX_RAW+1)),
                       ('wrong_history_hash',lambda e:e['history'].update(sha256='0'*64)),
                       ('wrong_history_count',lambda e:e['history'].update(length=0)),
                       ('wrong_prefix_metadata',lambda e:e['history']['prefix'].update(original_sha256='0'*64)),
                       ('duplicate_history',lambda e:e['payload']['result'].update(history=[]))]:
        bad=copy.deepcopy(env);edit(bad);reject(label,lambda bad=bad:codec.decode(bad,prefix))
    for label,change in [('disagreeing_history_copies',lambda r:r['result'].update(history=[])),('not_append_only',lambda r:(r['result']['history'][0].__setitem__(0,-123.),r['result']['checkpoint']['state']['history'][0].__setitem__(0,-123.)))]:
        bad=copy.deepcopy(rec);change(bad);reject(label,lambda bad=bad:codec.encode(bad,prefix))
    # Bit-sensitive edge history, including a zero-length extension.
    fixture={'codec_test_only':True,'design_sha256':d['original_design_sha256'],'result':{'history':[[0.,-0.,5e-324,float('inf'),float('nan'),2**100,'\u03bc']],
             'checkpoint':{'state':{'history':[[0.,-0.,5e-324,float('inf'),float('nan'),2**100,'\u03bc']]}}}}
    edge_dir=RUN/'edges';edge_dir.mkdir();_,es=codec.write_record(edge_dir/'first.json.xz',fixture)
    _,es2=codec.write_record(edge_dir/'zero_delta.json.xz',fixture,es);back,bs=codec.read_record(edge_dir/'zero_delta.json.xz',d['original_design_sha256'],es)
    api.require(codec.base.raw_bytes(back)==codec.base.raw_bytes(fixture) and bs==es2,'float-bit edge and empty extension')
    verify(d);report={'passed':True,'exact_original_records':len(rows),'records':rows,'guard_rejections':guards,'guard_count':len(guards),'primitive_edges_and_empty_delta_passed':True,
        'artifacts':{str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()},'design_sha256':api.sha(DESIGN),'wall_s':time.perf_counter()-start,
        'new_trajectory_steps':0,'production_ready':False,'claim':d['limitations']}
    api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('PREFIX_QUALIFIED',len(rows),len(guards),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
