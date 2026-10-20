"""Frozen zero-trajectory tests of future-campaign lifecycle/audit policy."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import itertools
import json
import math
import random
import sys
import time
from types import SimpleNamespace
import campaign_lifecycle_policy_v1 as policy

ROOT = Path(__file__).resolve().parents[1]
BASE = 'campaign_lifecycle_20260924'
DESIGN = ROOT / 'stage185_designs' / BASE / 'design_01.json'
RUN = ROOT / 'stage185_runs' / BASE / 'fixtures_01'
OUT = ROOT / 'stage185_evaluations' / BASE / 'qualification_01'
ORIGINAL = ROOT / 'stage167_designs/paired_full_path_deadline_20260922/design_01.json'
ORACLE = ROOT / 'stage167_staging/audit_paired_deadline_campaign_v3.py'
LIVE = ROOT / 'stage182_runs/bounded_live_audit_20260924/run_01'
WORK = ROOT / 'stage172_designs/four_hour_work_20260923/contract_01.json'


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def within_window():
    policy.require(datetime.now(timezone.utc) < policy.utc(policy.read(WORK)['end_utc']),
                   'no development after work cutoff')


def prepare():
    within_window()
    inputs = [ORIGINAL, ORACLE, WORK,
        ROOT / 'stage182_evaluations/bounded_live_audit_20260924/evaluation_01/results.json',
        ROOT / 'stage182_evaluations/bounded_live_audit_20260924/evaluation_01/completion.json']
    prior = policy.read(inputs[-2])
    policy.require(prior['passed'] and policy.read(inputs[-1])['results_sha256'] == policy.sha(inputs[-2]),
                   'qualified archived live protocol')
    d = {'stage': 'Stage185 zero-step lifecycle policy preparation', 'new_trajectory_steps': 0,
         'physical_changes': [], 'campaign_launch_authorized': False,
         'sources': {str(p): policy.sha(p) for p in (Path(__file__).resolve(), Path(policy.__file__))},
         'inputs': {str(p): policy.sha(p) for p in inputs}, 'cutoff_utc': policy.read(WORK)['end_utc'],
         'claim': 'Pure orchestration/terminal-policy checks only; future launcher integration remains unqualified.'}
    write(DESIGN, d)
    print('FROZEN', policy.sha(DESIGN), flush=True)


def verify(d):
    for mapping in (d['sources'], d['inputs']):
        for path, digest in mapping.items():
            policy.require(policy.sha(path) == digest, 'frozen dependency ' + path)


def run():
    within_window()
    started = time.perf_counter()
    d = policy.read(DESIGN)
    verify(d)
    RUN.mkdir(parents=True, exist_ok=False)
    OUT.mkdir(parents=True, exist_ok=False)
    checks = []
    rejects = []

    def check(name, value):
        policy.require(value, name)
        checks.append(name)

    def reject(name, action):
        try:
            action()
        except (ValueError, KeyError, FileNotFoundError, TypeError):
            rejects.append(name)
        else:
            raise AssertionError('did not reject: ' + name)

    original = policy.read(ORIGINAL)
    cases = original['cases']
    order = tuple(c['id'] for c in cases)
    check('gates_exact_original', policy.GATES == original['numerical_gates'])
    for pattern in itertools.product((0, 1), repeat=6):
        state = policy.initial(order)
        launched = []
        while state.queued or state.active:
            while True:
                state, case = policy.dispatch(state, 3, True)
                if case is None:
                    break
                launched.append(case)
            if not state.active:
                break
            case = state.active[0]
            state = policy.retire(state, case, pattern[order.index(case)], True)
            policy.validate(state)
            if state.stop_reasons:
                check('sticky_failure_' + str(pattern) + '_' + case,
                      policy.dispatch(state, 3, True) == (state, None))
        check('no_restart_' + str(pattern), len(launched) == len(set(launched)) and
              tuple(launched) == order[:len(launched)] and not state.active)
    state = policy.initial(order)
    check('auditor_required', policy.dispatch(state, 3, False) == (state, None))
    state, first = policy.dispatch(state, 3, True)
    check('missing_seal_latches_stop', bool(policy.retire(state, first, 0, False).stop_reasons))
    reject('duplicate_order', lambda: policy.initial(('a', 'a')))
    reject('retire_unowned', lambda: policy.retire(state, order[-1], 0, True))
    reject('corrupt_partition', lambda: policy.validate(policy.Lifecycle(order, order, (order[0],))))
    reject('unknown_worker_exit', lambda: policy.retire(state, first, None, True))
    for now, disk, reason in [('2026-09-25T18:59:00Z', 101, 'simulation_cutoff'),
                              ('2026-09-25T18:58:59Z', 100, 'disk_reserve')]:
        stopped = policy.resource_stop(state, now, '2026-09-25T18:59:00Z', disk, 100)
        check(reason, reason in stopped.stop_reasons)
        renewed = policy.resource_stop(stopped, '2026-09-25T18:58:00Z', '2026-09-25T18:59:00Z', 999, 100)
        check(reason + '_not_cleared', policy.dispatch(renewed, 3, True)[1] is None)
    lag = {c: 0 for c in order}
    check('lag_empty_allowed', policy.may_produce(state, first, lag))
    lag[first] = 2
    check('local_backpressure', not policy.may_produce(state, first, lag))
    lag = {c: 1 for c in order}
    check('global_backpressure', not policy.may_produce(state, first, lag))
    check('stop_prevents_segment', not policy.may_produce(policy.stop(state, 'test'), first, {c: 0 for c in order}))
    expected = {c: 1 for c in order}
    available = {c: {1, 2} for c in order}
    available[order[0]] = {2}
    cursor = 0
    got = []
    for _ in range(5):
        item, cursor = policy.next_audit(order, expected, available, cursor)
        got.append(item[0]); expected[item[0]] += 1
    check('fair_no_head_of_line_blocking', got == list(order[1:]))
    check('missing_parent_not_skipped', order[0] not in got)
    available[order[0]] = {1, 2}
    check('drain_ready_after_producer_stop', policy.next_audit(order, expected, available, 0)[0] == (order[0], 1))
    check('unsealed_not_a_ready_record', policy.next_audit(order, expected, {c: set() for c in order}, 0)[0] is None)

    # Replay protocol acknowledgements against original immutable files.
    receipts = sorted(LIVE.glob('*/segment_*.audit.json'))
    previous = {}
    exemplar = None
    for path in receipts:
        r = policy.read(path)
        raw = path.with_name(path.name.replace('.audit.json', '.json.xz'))
        ready = path.with_name(path.name.replace('.audit.json', '.ready.json'))
        paths = {'raw': raw, 'ready': ready, 'receipt': path, 'trace': Path(r['trace_path'])}
        args = (r['case'], r['segment'], r['design_sha256'], r['audit_source_sha256'],
                r['input_checkpoint_sha256'], previous.get(r['case']))
        got = policy.verify_receipt(paths, *args)
        check('archived_receipt_' + r['case'] + '_' + str(r['segment']), got['steps'] == 3000)
        previous[r['case']] = got['receipt_sha256']
        if exemplar is None:
            exemplar = paths, args
    check('all_twelve_receipts', len(receipts) == 12)
    paths, args = exemplar
    changes = [
        ('case_swap', 'case', 'other'), ('segment_swap', 'segment', 2),
        ('design_swap', 'design_sha256', '0' * 64), ('kernel_swap', 'audit_source_sha256', '0' * 64),
        ('wrong_parent', 'previous_receipt_sha256', '0' * 64),
        ('wrong_input', 'input_checkpoint_sha256', '0' * 64),
        ('wrong_raw', 'raw_sha256', '0' * 64), ('wrong_trace', 'trace_sha256', '0' * 64),
        ('wrong_trace_path', 'trace_path', 'wrong.npy'), ('unverified', 'status', 'producer_pass'),
        ('false_audit', 'summary.passed', False), ('zero_steps', 'summary.steps', 0),
        ('clock_nan', 'summary.stop_s', None), ('false_terminal', 'summary.complete_observation', True),
    ]
    for name, key, value in changes:
        fixture = RUN / name
        fixture.mkdir()
        marker, receipt = policy.read(paths['ready']), policy.read(paths['receipt'])
        write(fixture / 'ready.json', marker)
        receipt['ready_sha256'] = policy.sha(fixture / 'ready.json')
        if key.startswith('summary.'):
            receipt['summary'][key.split('.')[1]] = value
        else:
            receipt[key] = value
        write(fixture / 'receipt.json', receipt)
        changed = {**paths, 'ready': fixture / 'ready.json', 'receipt': fixture / 'receipt.json'}
        reject('receipt_' + name, lambda p=changed: policy.verify_receipt(p, *args))

    horizon = cases[0]['spec']['horizon_s']
    good = {'status': 'present_at_horizon', 'steps': 100, 'start_s': 0., 'stop_s': horizon,
            'rejected': 0, 'failure_markers': [], 'pending_trial': None, 'first_dwell_s': None,
            'raw_hashes_verified': True, 'clock_steps_verified': True, 'physics_verified': True,
            'fresh_start': True, 'export_verified': False}
    base = policy.observation(good, horizon)
    check('exact_horizon_not_retention', base['complete_observation'] and
          base['observation'] == 'not_exported_by_horizon' and not base['irreversible_retention_inferred'])
    exported = policy.observation({**good, 'status': 'full_window_exit', 'stop_s': 1., 'export_verified': True}, horizon)
    check('audited_export', exported['complete_observation'])
    for key, value in [('steps', 0), ('steps', True), ('start_s', .1), ('stop_s', horizon - 1e-12),
                       ('stop_s', float('nan')), ('stop_s', horizon + 1e-12), ('rejected', 1),
                       ('rejected', False), ('failure_markers', ['failed']), ('physics_verified', False),
                       ('pending_trial', {}), ('first_dwell_s', -1), ('export_verified', True),
                       ('status', 'incomplete_budget'), ('status', 'unknown'), ('fresh_start', False)]:
        check('incomplete_' + key + '_' + str(value), not policy.observation({**good, key: value}, horizon)['complete_observation'])
    for key in good:
        missing = copy.deepcopy(good); del missing[key]
        check('missing_field_' + key, not policy.observation(missing, horizon)['complete_observation'])

    # Original frozen pair-decision function is compiled without engine imports.
    tree = ast.parse(ORACLE.read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'pair_gates')
    namespace = {'np': SimpleNamespace(load=lambda *a, **k: None), 'metrics': lambda *a: metric}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(ORACLE), 'exec'), namespace)
    oracle = namespace['pair_gates']
    rng = random.Random(185)
    pairs = 0
    for index in range(500):
        first, second = copy.deepcopy(base), copy.deepcopy(base)
        if index % 3:
            first = copy.deepcopy(exported); second = copy.deepcopy(exported)
            second['stop_s'] += rng.choice([0, .002, .003])
        if index % 7 == 0:
            first['first_dwell_s'] = .25
            second['first_dwell_s'] = rng.choice([None, .25, .251, .254])
        if index % 11 == 0:
            second['status'] = 'full_window_exit'
        names = ('whole_position_over_b_max', 'whole_axis_vector_norm_max', 'endpoint_q_over_U_max', 'mean_L1_q_over_U_max')
        metric = {key: policy.GATES[key] * rng.choice([0., .5, 1., 1.0001]) for key in names}
        metric.update(common_start_s=0., common_stop_s=min(first['stop_s'], second['stop_s']),
                      common_duration_s=min(first['stop_s'], second['stop_s']))
        modern = policy.pair_gates(first, second, metric, policy.GATES)
        def old_case(ob):
            return {**ob, 'case_id': 'fixture', 'observed_s': ob['stop_s'], 'trace_path': 'stub',
                    'dwell': {'first_dwell_s': ob['first_dwell_s']}}
        old = oracle(original, old_case(first), old_case(second), cases[0]['spec'])
        policy.require(modern['checks'] == old['checks'] and modern['passed'] == old['passed'], 'original pair gates reproduced')
        pairs += 1
    check('original_pair_oracle_500', pairs == 500)
    metric = {key: 0. for key in names}
    metric.update(common_start_s=0., common_stop_s=horizon, common_duration_s=horizon)
    pair = policy.pair_gates(base, base, metric, policy.GATES)
    check('complete_identity_pair', pair['passed'])
    check('partial_path_never_promoted', not policy.pair_gates({**base, 'complete_observation': False}, base, None, policy.GATES)['passed'])
    reject('changed_gate', lambda: policy.pair_gates(base, base, metric, {**policy.GATES, 'mean_L1_q_over_U_max': .01}))
    reject('conditional_start', lambda: policy.pair_gates(base, base, {**metric, 'common_start_s': .1}, policy.GATES))
    reject('truncated_common_path', lambda: policy.pair_gates(base, base, {**metric, 'common_stop_s': 1.}, policy.GATES))
    reject('nan_metric', lambda: policy.pair_gates(base, base, {**metric, 'endpoint_q_over_U_max': math.nan}, policy.GATES))
    obs = {c: copy.deepcopy(base) for c in order}
    comparisons = {shape: copy.deepcopy(pair) for shape in ('rigid_prolate_ar4', 'equal_volume_sphere')}
    summary = policy.campaign_summary(cases, obs, comparisons, [], [], 0)
    check('two_labelled_placements_only', summary['passed'] and summary['population_release_estimate'] is None and
          [p['sample_id'] for p in summary['placements']] == [0, 124] and
          [len(p['cases']) for p in summary['placements']] == [4, 2] and not summary['empirical_validation'])
    for failures, unsealed, workers in [(['failure'], [], 0), ([], ['raw.pending'], 0), ([], [], 1)]:
        check('blocked_campaign_' + str((failures, unsealed, workers)), not policy.campaign_summary(cases, obs, comparisons, failures, unsealed, workers)['passed'])
    for case in order:
        incomplete = copy.deepcopy(obs); incomplete[case]['complete_observation'] = False
        check('no_dropped_case_' + case, not policy.campaign_summary(cases, incomplete, comparisons, [], [], 0)['passed'])
    reject('missing_case', lambda: policy.campaign_summary(cases, {k: v for k, v in obs.items() if k != order[0]}, comparisons, [], [], 0))
    verify(d)
    result = {'passed': True, 'new_trajectory_steps': 0, 'physical_changes': [],
              'checks': checks, 'negative_guards': rejects, 'original_pair_oracle_cases': pairs,
              'real_archived_receipts': len(receipts), 'sources': d['sources'],
              'inputs': d['inputs'], 'design_sha256': policy.sha(DESIGN),
              'artifacts': {str(p): policy.sha(p) for p in RUN.rglob('*') if p.is_file()},
              'wall_seconds': time.perf_counter() - started, 'claim': d['claim'],
              'production_launched': False, 'future_launcher_integration_qualified': False}
    write(OUT / 'results.json', result)
    write(OUT / 'completion.json', {'passed': True, 'results_sha256': policy.sha(OUT / 'results.json')})
    print('POLICY_PASS', len(checks), len(rejects), pairs, flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']:
        prepare()
    elif sys.argv[1:] == ['run']:
        run()
    else:
        raise ValueError('prepare | run; neither command can execute a trajectory')
