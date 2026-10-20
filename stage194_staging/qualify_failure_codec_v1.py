"""Zero-step qualification, including independent decoder and failed schemas."""
from pathlib import Path
import copy
import hashlib
import json
import lzma
import os
import sys
import time
import traceback
import lossless_trial_references_v2 as repair

ROOT = repair.ROOT
sys.path[:0] = [str(ROOT / 'stage193_staging'), str(ROOT / 'stage191_staging')]
import deadline_extended_campaign_v2 as campaign
import qualify_trial_references_v1 as previous
import lossless_trial_references_v1 as old_codec

job, api = campaign.job, campaign.api
WORK = ROOT / 'stage194_designs/eight_hour_repair_20260924/contract_01.json'
DESIGN = ROOT / 'stage194_designs/evidence_repair_20260924/codec_qualification_01.json'
RUN = ROOT / 'stage194_runs/evidence_repair_20260924/codec_qualification_01'
OUT = ROOT / 'stage194_evaluations/evidence_repair_20260924/codec_qualification_01'


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()


def independent_unpack(w):
    """Separate implementation, no calls to production pack/unpack/range helpers."""
    if w['evidence_encoding'] != 'stage194-lossless-trial-references-v2':
        raise ValueError('independent schema')
    e = copy.deepcopy(w['packed_envelope']); p = e['payload']
    if e['design_sha256'] != w['design_sha256']:
        raise ValueError('independent design')
    fields = ['accepted', 'vfree', 'mobility', 'jacobian', 'gaps_m', 'dt_s', 'friction', 'velocity', 'health']
    for t in p['contact_trial_trace']['detailed_trials']:
        for s in t['inner_systems']:
            for kind, src in [('early', p['early_attempts']), ('fallback', p['fallback_systems'])]:
                span = s[kind + '_range']
                if len(span) != 2 or any(type(x) is not int for x in span) or not 0 <= span[0] <= span[1] <= len(src):
                    raise ValueError('independent source interval')
            if 'system_reference' in s:
                ref = s.pop('system_reference')
                if set(ref) != {'kind', 'index'} or type(ref['index']) is not int or ref['kind'] not in ['early', 'fallback']:
                    raise ValueError('independent reference format')
                start, end = s[ref['kind'] + '_range']
                if not start <= ref['index'] < end or any(k in s for k in fields):
                    raise ValueError('independent ambiguous/out-of-range reference')
                src = p['early_attempts' if ref['kind'] == 'early' else 'fallback_systems'][ref['index']]
                for k in fields:
                    s[k] = copy.deepcopy(src[k])
    b = canonical(e)
    if type(w['original_envelope_bytes']) is not int or len(b) != w['original_envelope_bytes'] or hashlib.sha256(b).hexdigest() != w['original_envelope_sha256']:
        raise ValueError('independent canonical identity')
    return e


def independent_file(path, design, prior_rows=None, prior_ref=None):
    seal = api.read(path.with_suffix('.seal.json')); data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != seal['compressed_sha256']:
        raise ValueError('independent compressed seal')
    raw = lzma.decompress(data)
    if len(raw) != seal['uncompressed_bytes'] or hashlib.sha256(raw).hexdigest() != seal['uncompressed_sha256']:
        raise ValueError('independent uncompressed seal')
    envelope = independent_unpack(json.loads(raw))
    if envelope['design_sha256'] != design or envelope['history']['prefix'] != prior_ref:
        raise ValueError('independent history parent binding')
    rows = (prior_rows or []) + envelope['history']['appended_rows']
    hist = json.dumps(rows, separators=(',', ':'), allow_nan=True).encode()
    if len(rows) != envelope['history']['length'] or hashlib.sha256(hist).hexdigest() != envelope['history']['sha256']:
        raise ValueError('independent history identity')
    rec = copy.deepcopy(envelope['payload'])
    rec['result']['history'] = rows
    rec['result']['checkpoint']['state']['history'] = rows
    b = canonical(rec)
    if len(b) != envelope['original_uncompressed_bytes'] or hashlib.sha256(b).hexdigest() != envelope['original_uncompressed_sha256']:
        raise ValueError('independent logical-record identity')
    return rec


def fixtures():
    inner = {'accepted': True, 'vfree': [0., -0., 2.], 'mobility': [[1., 0.], [0., 1.]],
             'jacobian': [[1., 0.]], 'gaps_m': [0.], 'dt_s': 1e-6, 'friction': .3,
             'velocity': [1., 2., 3.], 'health': {'passed': True},
             'inner_index': 0, 'early_range': [0, 1], 'fallback_range': [0, 0]}
    outer = {'accepted': True, 'trial_index': 0, 'velocity': [1., 2., 3.],
             'health': {'contact': {'passed': True}}, 'inner_systems': [inner]}
    basic = {'design_sha256': 'a' * 64, 'payload': {'rows': [{'velocity_generalized': [1., 2., 3.]}],
             'early_attempts': [copy.deepcopy(inner)], 'fallback_systems': [],
             'contact_trial_trace': {'detailed_trials': [outer]}}}
    cases = [('healthy_reference', copy.deepcopy(basic))]
    def add(name, change):
        e = copy.deepcopy(basic); change(e['payload'], e['payload']['contact_trial_trace']['detailed_trials'][0]); cases.append((name, e))
    def fail_outer(p, t):
        t.pop('velocity'); t.pop('health'); t.update(accepted=False, error="RuntimeError('contact nonconvergence')")
    add('outer_failure_missing_outputs', fail_outer)
    add('outer_failure_with_accepted_inner', fail_outer)
    def fail_inner(p, t):
        fail_outer(p, t); s = t['inner_systems'][0]; s.pop('velocity'); s.pop('health'); s.update(accepted=False, error='inner failure')
    add('inner_exception_missing_outputs', fail_inner)
    add('outer_failure_no_inner', lambda p, t: (fail_outer(p, t), t.update(inner_systems=[])))
    add('trial_index_beyond_accepted_rows', lambda p, t: t.update(trial_index=99))
    add('no_accepted_rows', lambda p, t: (fail_outer(p, t), p.update(rows=[])))
    add('outer_partial_velocity_only', lambda p, t: t.pop('health'))
    add('outer_partial_health_only', lambda p, t: t.pop('velocity'))
    add('outer_health_without_contact', lambda p, t: t.update(health={'error': 'failed before contact'}))
    add('outer_literal_dict_velocity', lambda p, t: t.update(velocity={'diagnostic': 'not an accepted row reference'}))
    add('inner_empty_ranges', lambda p, t: t['inner_systems'][0].update(early_range=[0, 0]))
    add('inner_unequal_velocity', lambda p, t: t['inner_systems'][0].update(velocity=[-0., 4., 5.]))
    add('inner_missing_health', lambda p, t: t['inner_systems'][0].pop('health'))
    add('inner_missing_velocity', lambda p, t: t['inner_systems'][0].pop('velocity'))
    add('no_detailed_trials', lambda p, t: p['contact_trial_trace'].update(detailed_trials=[]))
    add('floating_edge_values', lambda p, t: t.update(diagnostic=[float('nan'), float('inf'), -0., 1e-300]))
    def fallback(p, t):
        p['fallback_systems'] = p['early_attempts']; p['early_attempts'] = []
        t['inner_systems'][0].update(early_range=[0, 0], fallback_range=[0, 1])
    add('fallback_exact_reference', fallback)
    def reject_then_accept(p, t):
        later = copy.deepcopy(t); later['trial_index'] = 1; fail_outer(p, t)
        p['contact_trial_trace']['detailed_trials'].append(later)
    add('rejected_before_accepted', reject_then_accept)
    return cases


def run():
    api.require(job.utc() < job.policy.utc(api.read(WORK)['work_end_utc']), 'work clock')
    job.verify(api.read(job.DESIGN))
    inputs = {str(p): api.sha(p) for p in [WORK, job.DESIGN, Path(repair.__file__), Path(__file__), Path(old_codec.__file__)]}
    protocol = {'stage': 'Stage194 lossless failure-schema repair qualification', 'new_trajectory_steps': 0,
                'inputs': inputs, 'scope': 'Exact storage only; no numerical acceptance or failed historical promotion',
                'real_fixtures': ['serial', 'split_first', 'split_last']}
    job.commit(DESIGN, protocol); RUN.mkdir(parents=True, exist_ok=False); OUT.mkdir(parents=True, exist_ok=False)
    job.commit(RUN / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'utc': job.utc().isoformat(), 'design_sha256': api.sha(DESIGN), 'new_trajectory_steps': 0})
    tests = []; reports = []; rejects = []; old_failure = None
    try:
        for name, fixture in fixtures():
            before = canonical(fixture); packed = repair.pack(fixture)
            api.require(canonical(repair.unpack(packed)) == before == canonical(independent_unpack(packed)), 'both decoders ' + name)
            api.require(canonical(fixture) == before, 'no input mutation')
            tests.append(name)
            if name == 'outer_failure_missing_outputs':
                try: old_codec.pack(fixture)
                except KeyError as e: old_failure = repr(e)
                else: raise AssertionError('original defect not reproduced')
        api.require(old_failure == "KeyError('velocity')", 'original writer failure reproduced without physics')
        good = repair.pack(fixtures()[0][1])
        def first(w): return w['packed_envelope']['payload']['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0]
        changes = [
            ('negative_reference', lambda w: first(w)['system_reference'].update(index=-1)),
            ('past_end_reference', lambda w: first(w)['system_reference'].update(index=1)),
            ('bool_reference', lambda w: first(w)['system_reference'].update(index=True)),
            ('unknown_source', lambda w: first(w)['system_reference'].update(kind='rows')),
            ('extra_reference_field', lambda w: first(w)['system_reference'].update(extra=1)),
            ('ambiguous_value', lambda w: first(w).update(velocity=[1., 2., 3.])),
            ('reference_outside_declared_range', lambda w: first(w).update(early_range=[0, 0])),
            ('invalid_range', lambda w: first(w).update(early_range=[-1, 1])),
            ('corrupt_source', lambda w: w['packed_envelope']['payload']['early_attempts'][0].update(velocity=[9., 2., 3.])),
            ('wrong_sha', lambda w: w.update(original_envelope_sha256='0' * 64)),
            ('wrong_size', lambda w: w.update(original_envelope_bytes=1)),
            ('wrong_schema', lambda w: w.update(evidence_encoding='wrong')),
            ('wrong_design', lambda w: w.update(design_sha256='0' * 64)),
        ]
        for name, change in changes:
            bad = copy.deepcopy(good); change(bad)
            for decoder in [repair.unpack, independent_unpack]:
                try: decoder(bad)
                except (ValueError, KeyError, IndexError, TypeError): pass
                else: raise AssertionError('accepted corruption: ' + name)
            rejects.append(name)
        source_prefix = target_prefix = None; prior_rows = prior_ref = None
        for name in protocol['real_fixtures']:
            if name != 'split_last': source_prefix = target_prefix = prior_rows = prior_ref = None
            source = previous.RUN / (name + '.json.xz')
            record, source_prefix = old_codec.codec.read_record(source, api.sha(previous.job.DESIGN), source_prefix)
            inputs[str(source)] = api.sha(source); inputs[str(source.with_suffix('.seal.json'))] = api.sha(source.with_suffix('.seal.json'))
            dest = RUN / (name + '.json.xz'); start = time.perf_counter()
            seal, next_prefix = repair.codec.write_record(dest, record, target_prefix)
            elapsed = time.perf_counter() - start
            reconstructed, _ = repair.codec.read_record(dest, record['design_sha256'], target_prefix)
            independent = independent_file(dest, record['design_sha256'], prior_rows, prior_ref)
            api.require(canonical(record) == canonical(reconstructed) == canonical(independent), 'real original bytes and independent history ' + name)
            reports.append({'name': name, 'old_bytes': source.stat().st_size, 'new_bytes': dest.stat().st_size,
                            'write_seconds': elapsed, 'exact_logical_sha256': hashlib.sha256(canonical(record)).hexdigest(),
                            'new_trajectory_steps': 0, 'passed': True})
            target_prefix = next_prefix; prior_rows = record['result']['history']; prior_ref = target_prefix.reference()
            print('REAL_CODEC_IDENTITY', name, flush=True)
        try: repair.codec.write_record(dest, record)
        except FileExistsError: rejects.append('occupied_output')
        else: raise AssertionError('overwrite accepted')
        api.verify_mapping(inputs)
        result = {'passed': True, 'new_trajectory_steps': 0, 'synthetic_fixture_names': tests,
                  'both_decoder_corruption_rejections': rejects, 'original_writer_defect_reproduced': old_failure,
                  'real_records': reports, 'inputs': inputs, 'design_sha256': api.sha(DESIGN),
                  'artifacts': {str(p): api.sha(p) for p in RUN.rglob('*') if p.is_file()},
                  'physical_or_numerical_changes': [], 'underlying_stage193_unsaved_failure_still_unknown': True}
        job.commit(OUT / 'results.json', result); job.commit(OUT / 'completion.json', {'passed': True, 'results_sha256': api.sha(OUT / 'results.json')})
        print('FAILURE_CODEC_PASS', len(tests), len(rejects), len(reports), flush=True)
    except Exception as e:
        job.commit(OUT / 'failure.json', {'error': repr(e), 'traceback': traceback.format_exc(), 'new_trajectory_steps': 0})
        raise


if __name__ == '__main__': run()
