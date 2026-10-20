"""Zero-step exact-byte codec qualification and measured storage cost."""
from pathlib import Path
import copy
import hashlib
import json
import lzma
import os
import sys
import time
import traceback
import lossless_trial_references_v1 as compact

ROOT=compact.ROOT
sys.path.insert(0,str(ROOT/'stage190_staging'))
import qualify_known_transition_v1 as prior
api,job=prior.api,prior.job
BASE='lossless_trial_references_20260924'
DESIGN=ROOT/'stage191_designs'/BASE/'design_01.json'
RUN=ROOT/'stage191_runs'/BASE/'qualification_01'
OUT=ROOT/'stage191_evaluations'/BASE/'qualification_01'


def prepare():
    prior.verify(api.read(prior.DESIGN));r=api.read(prior.OUT/'results.json')
    api.require(r['passed'] and r['new_steps']==20000,'local repair prerequisite')
    api.require(api.read(prior.OUT/'completion.json')['results_sha256']==api.sha(prior.OUT/'results.json'),'local seal')
    api.verify_mapping(r['artifacts'])
    d={'stage':'Stage191 lossless evidence de-duplication','trajectory_steps_authorized':0,
       'cases':['serial','split_first','split_last'],'sources':job.source_map(),
       'inputs':{**r['artifacts'],**{str(p):api.sha(p) for p in (job.WORK,prior.DESIGN,prior.OUT/'results.json',prior.OUT/'completion.json')}},
       'claim':'Storage-only qualification. Every original logical record byte is preserved; no scientific result or failed stage is reclassified.'}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN_CODEC',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'codec design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);prior.verify(api.read(prior.DESIGN))


def independent_envelope(path,design):
    seal=json.loads(path.with_suffix('.seal.json').read_text())
    data=path.read_bytes();api.require(hashlib.sha256(data).hexdigest()==seal['compressed_sha256'],'independent compressed SHA')
    raw=lzma.decompress(data);api.require(len(raw)==seal['uncompressed_bytes'] and hashlib.sha256(raw).hexdigest()==seal['uncompressed_sha256'],'independent uncompressed SHA')
    w=json.loads(raw);e=w['packed_envelope'];p=e['payload'];api.require(w['design_sha256']==design==e['design_sha256'],'independent design')
    # Separate decoder; does not call compact.unpack or its list of key names.
    keys=['accepted','vfree','mobility','jacobian','gaps_m','dt_s','friction','velocity','health']
    for t in p['contact_trial_trace']['detailed_trials']:
        for s in t['inner_systems']:
            ref=s.pop('system_reference',None)
            if ref is not None:
                origin=p[{'early':'early_attempts','fallback':'fallback_systems'}[ref['kind']]][ref['index']]
                for k in keys:s[k]=copy.deepcopy(origin[k])
        if isinstance(t['velocity'],dict):t['velocity']=p['rows'][t['velocity']['accepted_row_reference']]['velocity_generalized']
        if t['health']['contact']=={'last_inner_health_reference':True}:t['health']['contact']=copy.deepcopy(t['inner_systems'][-1]['health'])
    canonical=(json.dumps(e,sort_keys=True,indent=2,allow_nan=True)+'\n').encode()
    api.require(hashlib.sha256(canonical).hexdigest()==w['original_envelope_sha256'] and len(canonical)==w['original_envelope_bytes'],'independent original envelope identity')
    return e


def run():
    d=api.read(DESIGN);verify(d)
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_steps':0,'design_sha256':api.sha(DESIGN)})
    reports=[];source_prefix=next_prefix=None;fixture=None
    try:
        for name in d['cases']:
            api.require(job.utc()<job.policy.utc(api.read(job.WORK)['agent_work_end_utc']),'work cutoff')
            if name!='split_last':source_prefix=next_prefix=None
            source=prior.RUN/(name+'.json.xz')
            rec,source_prefix=job.codec.read_record(source,api.sha(job.DESIGN),source_prefix)
            original=compact.base.raw_bytes(rec)
            path=RUN/(name+'.json.xz');start=time.perf_counter()
            seal,encoded_prefix=compact.codec.write_record(path,rec,next_prefix)
            write_s=time.perf_counter()-start;start=time.perf_counter()
            decoded,decoded_prefix=compact.codec.read_record(path,api.sha(job.DESIGN),next_prefix)
            read_s=time.perf_counter()-start
            api.require(compact.base.raw_bytes(decoded)==original,'every original canonical record byte')
            env=independent_envelope(path,api.sha(job.DESIGN))
            api.require(env['original_uncompressed_sha256']==hashlib.sha256(original).hexdigest(),'original logical SHA')
            next_prefix=encoded_prefix
            reports.append({'name':name,'exact_original_bytes':True,'independent_decoder_passed':True,
                            'original_canonical_sha256':hashlib.sha256(original).hexdigest(),'logical_bytes':len(original),
                            'old_archive_bytes':source.stat().st_size,'new_archive_bytes':path.stat().st_size,
                            'write_s':write_s,'read_s':read_s,'path':str(path)})
            print('CODEC_IDENTITY',name,reports[-1],flush=True)
            if name=='serial':
                # Tiny, explicitly synthetic format fixture, not a physical run.
                tr=copy.deepcopy(next(t for t in rec['contact_trial_trace']['detailed_trials'] if t['trial_index']==2794))
                lo=tr['early_range'][0];tr['trial_index']=0
                for item in tr['inner_systems']:item['early_range']=[v-lo for v in item['early_range']]
                tr['early_range']=[v-lo for v in tr['early_range']]
                fake={'design_sha256':rec['design_sha256'],'payload':{'rows':[rec['rows'][2794]],'early_attempts':[rec['early_attempts'][lo]],
                      'fallback_systems':[],'contact_trial_trace':{'detailed_trials':[tr]}}}
                fixture=compact.pack(fake)
        def first(w):return w['packed_envelope']['payload']['contact_trial_trace']['detailed_trials'][0]
        mutations=[('wrong_source_index',lambda w:first(w)['inner_systems'][0]['system_reference'].update(index=3)),
                   ('negative_source_index',lambda w:first(w)['inner_systems'][0]['system_reference'].update(index=-1)),
                   ('unknown_source_kind',lambda w:first(w)['inner_systems'][0]['system_reference'].update(kind='unknown')),
                   ('ambiguous_duplicate_value',lambda w:first(w)['inner_systems'][0].update(velocity=[0]*6)),
                   ('corrupt_legacy_value',lambda w:w['packed_envelope']['payload']['early_attempts'][0]['velocity'].__setitem__(0,1.)),
                   ('corrupt_row_ref',lambda w:first(w)['velocity'].update(accepted_row_reference=4)),
                   ('corrupt_health_ref',lambda w:first(w)['health']['contact'].update(last_inner_health_reference=False)),
                   ('drop_inner',lambda w:first(w)['inner_systems'].pop()),
                   ('wrong_envelope_hash',lambda w:w.update(original_envelope_sha256='0'*64)),
                   ('wrong_envelope_size',lambda w:w.update(original_envelope_bytes=1)),
                   ('wrong_schema',lambda w:w.update(evidence_encoding='wrong')),
                   ('wrong_design',lambda w:w.update(design_sha256='0'*64))]
        guards=[]
        for name,mutation in mutations:
            bad=copy.deepcopy(fixture);mutation(bad)
            try:compact.unpack(bad)
            except (ValueError,KeyError,IndexError):guards.append(name)
            else:raise AssertionError('codec accepted '+name)
        api.require(equal_fixture(compact.unpack(fixture),fixture),'valid tiny fixture')
        try:compact.codec.write_record(RUN/'serial.json.xz',rec)
        except FileExistsError:guards.append('occupied_output')
        else:raise AssertionError('occupied output overwritten')
        verify(d)
        result={'passed':True,'new_trajectory_steps':0,'reports':reports,'rejections':guards,
                'design_sha256':api.sha(DESIGN),'artifacts':{str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()},'claim':d['claim']}
        api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('CODEC_PASS',len(reports),len(guards),flush=True)
    except Exception as error:
        api.write(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise


def equal_fixture(e,w):
    return hashlib.sha256(compact.base.raw_bytes(e)).hexdigest()==w['original_envelope_sha256']


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare or run')
