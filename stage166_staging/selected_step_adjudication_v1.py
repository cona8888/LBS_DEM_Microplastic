"""Explicit, user-authorized selection-policy correction; no new integration.

Stage165 remains failed. Selection was already fixed by Stage164 before the
startup evidence existed. Requiring a deliberately larger, rejected timestep
to pass is not a condition for using that preselected smaller timestep.
This is disclosed post-failure adjudication, not independent validation.
"""
from pathlib import Path
import copy
import datetime
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage165_staging'))
import fresh_start_benchmark_v1 as b
api = b.api
DESIGN = ROOT / 'stage166_designs/selected_step_adjudication_20260922/design_01.json'
OUT = ROOT / 'stage166_evaluations/selected_step_adjudication_20260922/evaluation_01'


def policy(selected, factors, shapes, integrity):
    if not integrity or len(factors) != 3 or not factors[0] > factors[1] > factors[2] > 0:
        return False
    if selected != factors[1] or {s['shape'] for s in shapes} != {'equal_volume_sphere', 'rigid_prolate_ar4'} or len(shapes) != 2:
        return False
    return all(len(s['to_finest']) == 2 and s['to_finest'][1]['passed'] for s in shapes)


def source_evidence():
    d = api.read(b.DESIGN); b.verify(d)
    r = api.read(b.OUT / 'results.json'); a = api.read(b.AUDIT / 'results.json')
    for folder in [b.OUT, b.AUDIT]:
        api.require(api.read(folder / 'completion.json')['results_sha256'] == api.sha(folder / 'results.json'), 'predecessor seal')
    api.require(a['audit_integrity_passed'] and a['evaluation_sha256'] == api.sha(b.OUT / 'results.json'), 'startup audit binding')
    api.require(not r['passed'] and not a['scientific_gates_passed'], 'original Stage165 failure must remain')
    api.verify_mapping(r['artifacts']); b.audit_preflight(d)
    recomputed = b.evaluate(d)
    api.require(all(r[k] == v for k, v in recomputed.items()), 'raw startup evidence reproduced')
    qr = api.read(b.q.OUT / 'results.json')
    api.require(qr['passed'] and qr['selected_factor'] == d['selected_factor'] == .0625, 'selection fixed before startup test')
    api.verify_mapping(qr['artifacts'])
    return d, r


def prepare():
    d, r = source_evidence()
    inputs = [b.DESIGN, b.OUT / 'results.json', b.OUT / 'completion.json', b.AUDIT / 'results.json',
              b.AUDIT / 'completion.json', b.q.DESIGN, b.q.OUT / 'results.json', b.q.AUDIT / 'results.json',
              b.OUT.parent / 'failure_assessment_01/results.json']
    new = {'stage': 'Stage166', 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'authorization': 'User next on 22 September after explicit request to correct the selection rule without changing error limits and target 24 September 23:59 UK time.',
        'selected_factor': d['selected_factor'], 'factors': d['factors'], 'accuracy_limits': d['accuracy_limits'],
        'policy': 'Require the factor already selected by Stage164 to pass startup for both shapes against the finest reference, plus every original artifact, health, balance, clock and restart check. The larger rejected factor remains a disclosed negative comparator, never a production setting.',
        'changed': ['Aggregation/selection policy only; no per-case limits or outcomes changed.'],
        'unchanged': ['Equations', 'Contact law', 'Forces', 'Time controls', 'Error thresholds', 'Initial states', 'Raw evidence', 'Stage165 failed verdict'],
        'claim': 'Permission for bounded full-path comparison using factor 0.0625; no full-path accuracy, population release or empirical validation is yet established.',
        'evidence_role': 'Disclosed post-failure adjudication of development data, not a new independent test.',
        'deadline': {'local': '2026-09-24T23:59:00+01:00', 'utc': '2026-09-24T22:59:00+00:00', 'audit_reserve_hours': 4},
        'inputs': {str(p): api.sha(p) for p in inputs},
        'sources': {str(Path(__file__).resolve()): api.sha(__file__)}}
    new['binding'] = api.digest(new)
    DESIGN.parent.mkdir(parents=True, exist_ok=True); api.write(DESIGN, new)


def evaluate():
    d = api.read(DESIGN); api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'design binding')
    api.verify_mapping(d['inputs']); api.verify_mapping(d['sources'])
    old_d, r = source_evidence()
    checks = [policy(d['selected_factor'], d['factors'], r['shapes'], True)]
    bad = copy.deepcopy(r['shapes']); bad[0]['to_finest'][1]['passed'] = False
    checks.append(not policy(.0625, d['factors'], bad, True))
    bad = copy.deepcopy(r['shapes']); bad[1]['to_finest'][1]['passed'] = False
    checks.append(not policy(.0625, d['factors'], bad, True))
    checks += [not policy(.125, d['factors'], r['shapes'], True),
               not policy(.03125, d['factors'], r['shapes'], True),
               not policy(.0625, d['factors'], r['shapes'], False),
               not policy(.0625, list(reversed(d['factors'])), r['shapes'], True),
               not policy(.0625, d['factors'], r['shapes'][:1], True)]
    api.require(all(checks), 'selection policy regression')
    result = {'passed': checks[0], 'selected_factor': d['selected_factor'], 'original_stage165_passed': r['passed'],
        'selection_tests_passed': len(checks), 'thresholds_identical': d['accuracy_limits'] == old_d['accuracy_limits'],
        'raw_evidence_reloaded': True, 'new_simulation_executed': False, 'claim': d['claim'],
        'evidence_role': d['evidence_role'], 'design_sha256': api.sha(DESIGN),
        'selected_metrics': {s['shape']: s['to_finest'][1] for s in r['shapes']}}
    api.require(result['thresholds_identical'], 'unchanged thresholds')
    OUT.mkdir(parents=True, exist_ok=False); api.write(OUT / 'results.json', result, raw=True)
    api.write(OUT / 'completion.json', {'passed': result['passed'], 'results_sha256': api.sha(OUT / 'results.json')})
    print('STAGE166 PASS; original Stage165 remains failed; factor', d['selected_factor'], flush=True)


def verify():
    d = api.read(DESIGN); r = api.read(OUT / 'results.json')
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'adjudication design')
    api.verify_mapping(d['inputs']); api.verify_mapping(d['sources'])
    api.require(api.read(OUT / 'completion.json')['results_sha256'] == api.sha(OUT / 'results.json') and r['passed'], 'adjudication completion')
    api.require(r['design_sha256'] == api.sha(DESIGN) and not r['original_stage165_passed'], 'preserved predecessor verdict')
    return d, r


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']: prepare()
    elif sys.argv[1:] == ['evaluate']: evaluate()
    else: raise ValueError('Use prepare or evaluate')
