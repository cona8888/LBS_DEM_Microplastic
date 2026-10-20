"""Storage-only repair: failed outer/inner trials remain literal evidence.

Only complete, exactly equal inner systems are factored. Outer velocity/health
are never indexed by trial_index: rejected trials need not map to accepted rows.
No solver, recorder, accepted state, tolerance or failure status is changed.
"""
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage179_staging'))
import lossless_history_prefix_v1 as original

base = original.base
SCHEMA = 'stage194-lossless-trial-references-v2'
SYSTEM_KEYS = ('accepted', 'vfree', 'mobility', 'jacobian', 'gaps_m', 'dt_s', 'friction', 'velocity', 'health')


def checked_range(item, key, length):
    span = item[key]
    if not isinstance(span, (list, tuple)) or len(span) != 2:
        raise ValueError('inner evidence range must have two endpoints')
    lo, hi = span
    if type(lo) is not int or type(hi) is not int or not 0 <= lo <= hi <= length:
        raise ValueError('inner evidence range outside archived source')
    return lo, hi


def pack(envelope):
    result = dict(envelope)
    payload = dict(envelope['payload']); result['payload'] = payload
    log = payload['contact_trial_trace']; out = dict(log); payload['contact_trial_trace'] = out
    trials = []
    for trial in log['detailed_trials']:
        tr = dict(trial); systems = []
        for item in trial['inner_systems']:
            if 'system_reference' in item:
                raise ValueError('reserved reference key in original inner system')
            system = dict(item); reference = None
            for kind, source_key, range_key in (
                ('early', 'early_attempts', 'early_range'),
                ('fallback', 'fallback_systems', 'fallback_range'),
            ):
                source = payload[source_key]
                lo, hi = checked_range(item, range_key, len(source))
                if reference is None and all(k in item for k in SYSTEM_KEYS):
                    for index in range(lo, hi):
                        saved = source[index]
                        if all(k in saved and base.raw_bytes(item[k]) == base.raw_bytes(saved[k]) for k in SYSTEM_KEYS):
                            reference = {'kind': kind, 'index': index}
                            break
            if reference is not None:
                for key in SYSTEM_KEYS:
                    del system[key]
                system['system_reference'] = reference
            systems.append(system)
        tr['inner_systems'] = systems
        # Missing/partial failure data and all outer fields are retained exactly.
        trials.append(tr)
    out['detailed_trials'] = trials
    raw = base.raw_bytes(envelope)
    if not 0 < len(raw) <= base.MAX_RAW:
        raise ValueError('original envelope resource ceiling')
    return {'design_sha256': envelope['design_sha256'], 'evidence_encoding': SCHEMA,
            'original_envelope_sha256': hashlib.sha256(raw).hexdigest(),
            'original_envelope_bytes': len(raw), 'packed_envelope': result}


def unpack(wrapper):
    if wrapper.get('evidence_encoding') != SCHEMA:
        raise ValueError('explicit stage194 lossless encoding required')
    size = wrapper.get('original_envelope_bytes')
    if type(size) is not int or not 0 < size <= base.MAX_RAW:
        raise ValueError('bounded original envelope')
    env = copy.deepcopy(wrapper['packed_envelope'])
    if env['design_sha256'] != wrapper['design_sha256']:
        raise ValueError('compact design binding')
    p = env['payload']
    for trial in p['contact_trial_trace']['detailed_trials']:
        for item in trial['inner_systems']:
            checked_range(item, 'early_range', len(p['early_attempts']))
            checked_range(item, 'fallback_range', len(p['fallback_systems']))
            if 'system_reference' not in item:
                continue
            ref = item.pop('system_reference')
            if not isinstance(ref, dict) or set(ref) != {'kind', 'index'} or type(ref['index']) is not int:
                raise ValueError('invalid inner reference')
            if ref['kind'] not in ('early', 'fallback') or any(k in item for k in SYSTEM_KEYS):
                raise ValueError('unknown or ambiguous inner reference')
            source = p['early_attempts'] if ref['kind'] == 'early' else p['fallback_systems']
            lo, hi = checked_range(item, ref['kind'] + '_range', len(source))
            if not lo <= ref['index'] < hi:
                raise ValueError('reference outside declared inner range')
            saved = source[ref['index']]
            if not all(k in saved for k in SYSTEM_KEYS):
                raise ValueError('incomplete referenced system')
            for key in SYSTEM_KEYS:
                item[key] = copy.deepcopy(saved[key])
    raw = base.raw_bytes(env)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != wrapper['original_envelope_sha256']:
        raise ValueError('exact original envelope reconstruction')
    return env


def write_envelope(path, envelope):
    return base.write_record(path, pack(envelope))


def read_envelope(path, design):
    return unpack(base.read_record(path, design))


spec = importlib.util.spec_from_file_location('_stage194_history_prefix', original.__file__)
codec = importlib.util.module_from_spec(spec); sys.modules[spec.name] = codec; spec.loader.exec_module(codec)
codec.base = SimpleNamespace(**vars(base))
codec.base.write_record = write_envelope
codec.base.read_record = read_envelope
