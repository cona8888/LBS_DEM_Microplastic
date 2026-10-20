"""Lossless storage only: factor duplicate observer/legacy solver evidence.

The reconstructed Stage179 envelope AND original canonical record are sealed.
No diagnostic field is discarded, quantized, rounded, or recomputed. References
point only to exactly equal saved JSON values within this one record.
"""
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage179_staging'))
import lossless_history_prefix_v1 as original

base = original.base
SCHEMA = 'stage191-lossless-trial-references-v1'
SYSTEM_KEYS = ('accepted','vfree','mobility','jacobian','gaps_m','dt_s','friction','velocity','health')


def equal(a, b):
    return base.raw_bytes(a) == base.raw_bytes(b)


def pack(envelope):
    result = dict(envelope);payload=dict(envelope['payload']);result['payload']=payload
    log=envelope['payload']['contact_trial_trace'];out=dict(log);payload['contact_trial_trace']=out
    early=payload['early_attempts'];fallback=payload['fallback_systems'];rows=payload['rows'];trials=[]
    for trial in log['detailed_trials']:
        tr=dict(trial);systems=[]
        for item in trial['inner_systems']:
            system=dict(item);ref=None
            for kind,source,key in [('early',early,'early_range'),('fallback',fallback,'fallback_range')]:
                lo,hi=item[key]
                for index in range(lo,hi):
                    saved=source[index]
                    if all(k in saved and k in item and equal(item[k],saved[k]) for k in SYSTEM_KEYS):
                        ref={'kind':kind,'index':index};break
                if ref:break
            if ref:
                for k in SYSTEM_KEYS:del system[k]
                system['system_reference']=ref
            systems.append(system)
        tr['inner_systems']=systems
        if equal(tr['velocity'],rows[tr['trial_index']]['velocity_generalized']):
            tr['velocity']={'accepted_row_reference':tr['trial_index']}
        if equal(tr['health']['contact'],trial['inner_systems'][-1]['health']):
            tr['health']=dict(tr['health']);tr['health']['contact']={'last_inner_health_reference':True}
        trials.append(tr)
    out['detailed_trials']=trials
    raw=base.raw_bytes(envelope)
    return {'design_sha256':envelope['design_sha256'],'evidence_encoding':SCHEMA,
            'original_envelope_sha256':hashlib.sha256(raw).hexdigest(),'original_envelope_bytes':len(raw),'packed_envelope':result}


def unpack(wrapper):
    if wrapper.get('evidence_encoding')!=SCHEMA:raise ValueError('explicit compact trial encoding required')
    env=wrapper['packed_envelope']
    if env['design_sha256']!=wrapper['design_sha256']:raise ValueError('compact envelope design')
    env=copy.deepcopy(env);payload=env['payload'];early=payload['early_attempts'];fallback=payload['fallback_systems'];rows=payload['rows']
    for trial in payload['contact_trial_trace']['detailed_trials']:
        for item in trial['inner_systems']:
            if 'system_reference' not in item:continue
            ref=item.pop('system_reference')
            if set(ref)!= {'kind','index'} or type(ref['index']) is not int or ref['index']<0:raise ValueError('invalid inner reference')
            if ref['kind'] not in ('early','fallback'):raise ValueError('unknown inner reference kind')
            source=early if ref['kind']=='early' else fallback
            if ref['index']>=len(source) or any(k in item for k in SYSTEM_KEYS):raise ValueError('out-of-range or ambiguous reference')
            for k in SYSTEM_KEYS:item[k]=copy.deepcopy(source[ref['index']][k])
        if isinstance(trial['velocity'],dict):
            ref=trial['velocity']
            if set(ref)!={'accepted_row_reference'} or type(ref['accepted_row_reference']) is not int or not 0<=ref['accepted_row_reference']<len(rows):raise ValueError('invalid row reference')
            trial['velocity']=copy.deepcopy(rows[ref['accepted_row_reference']]['velocity_generalized'])
        if isinstance(trial['health']['contact'],dict) and 'last_inner_health_reference' in trial['health']['contact']:
            if trial['health']['contact']!={'last_inner_health_reference':True} or not trial['inner_systems']:raise ValueError('invalid final health reference')
            trial['health']['contact']=copy.deepcopy(trial['inner_systems'][-1]['health'])
    raw=base.raw_bytes(env)
    if len(raw)!=wrapper['original_envelope_bytes'] or hashlib.sha256(raw).hexdigest()!=wrapper['original_envelope_sha256']:raise ValueError('exact original envelope reconstruction')
    return env


def write_envelope(path, envelope):
    compact=pack(envelope)
    # Do not let compression hide a record exceeding the original size bound.
    if compact['original_envelope_bytes']>base.MAX_RAW:raise ValueError('original envelope resource ceiling')
    return base.write_record(path,compact)


def read_envelope(path, design):
    wrapper=base.read_record(path,design)
    if type(wrapper.get('original_envelope_bytes')) is not int or not 0<wrapper['original_envelope_bytes']<=base.MAX_RAW:raise ValueError('bounded original envelope')
    return unpack(wrapper)


# Independent module namespace: no frozen original codec or source mutation.
spec=importlib.util.spec_from_file_location('_stage191_history_prefix',original.__file__)
codec=importlib.util.module_from_spec(spec);sys.modules[spec.name]=codec;spec.loader.exec_module(codec)
codec.base=SimpleNamespace(**vars(base))
codec.base.write_record=write_envelope
codec.base.read_record=read_envelope
