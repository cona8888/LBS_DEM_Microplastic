"""Stdlib-only synthetic controls for the inactive qualification driver.

No physical-runtime module, field, solver, transport, authority or campaign output is
executed. Temporary byte fixtures test the ACTUAL codec/ledger/restart helper
code with privately bound paths. Passing these is not native qualification.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import FunctionType
import ast
import copy
import hashlib
import importlib.util
import json
import lzma
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('qualification_source_only', HERE / 'run_stepdoubling_qualification_v1.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def private(folder):
    namespace = dict(vars(driver))
    namespace.update(ROOT=folder, OUT=folder / 'output', PLAN=folder / 'plan.json', PHYSICAL=folder / 'physical.json',
        resource_guard=lambda **kwargs: dict(own_bytes=0, total_retained_bytes=0, free_bytes=10**20))
    for name, value in vars(driver).items():
        if isinstance(value, type(private)) and value.__module__ == driver.__name__:
            clone = FunctionType(value.__code__, namespace, value.__name__, value.__defaults__, value.__closure__)
            clone.__kwdefaults__ = copy.copy(value.__kwdefaults__)
            namespace[name] = clone
    namespace['resource_guard'] = lambda **kwargs: dict(own_bytes=0, total_retained_bytes=0, free_bytes=10**20)
    namespace['_RESOURCE_LAST'] = [0., None]
    namespace['commit'](namespace['PLAN'], {'synthetic_plan': True, 'source_files': {}, 'physical_inputs': {}})
    namespace['commit'](namespace['PHYSICAL'], {'synthetic_physical': True})
    return namespace


def packet(history):
    state = dict(t=.1, steps=2, x=[0., 0., 0.], p=[1., 0., 0.], q=[0.] * 6,
                 history=copy.deepcopy(history), pending_trial=None, minimum_gap=float('inf'))
    full = dict(schema=1, contract={'synthetic': True}, state=state, state_sha256=driver.original_digest(state))
    return dict(schema='synthetic-codec-fixture-not-native', record_id='fixture',
        checkpoint={'physical_checkpoint': full}, original_FULL_output_sha256=driver.original_digest(full))


def restart_packet(branches, accepted, checkpoint):
    return dict(work_branches=copy.deepcopy(branches), carried_branches=[],
        accepted_rows=copy.deepcopy(accepted), committed_branch_ids=[b['branch_id'] for b in branches if b['role'] != 'C'],
        work_rows=len(branches), checkpoint=copy.deepcopy(checkpoint))


def branch(identity, role, number):
    return dict(branch_id=identity, role=role, work_rows=1,
        compact_result={'runtime_seconds': 1., 'total_contact_iterations': 7},
        rows=[{'time_s': number, 'velocity_generalized': [number] * 6}],
        cap_entries=[{'trigger_grain_ids': [], 'actual_trial_dt_s': .1}],
        after_state={'q': [number] * 6}, reactions=[1., 0., 0.], error=None)


class QualificationControls(unittest.TestCase):
    def test_actual_budget_and_clock_negatives(self):
        result = driver.controls()
        self.assertTrue(result['passed'])
        self.assertGreaterEqual(len(result['pure_negative_controls']), 17)
        self.assertFalse(result['native_restart_qualified'])
        self.assertNotIn('reconstruct_fixed_pose_v3', sys.modules)

    def test_actual_window_bound_reserve_and_number(self):
        start = datetime(2030, 1, 1, tzinfo=timezone.utc)
        plan = dict(start_utc=start.isoformat(), simulation_cutoff_utc=(start + timedelta(hours=124)).isoformat(),
                    end_utc=(start + timedelta(hours=132)).isoformat())
        now = (start + timedelta(hours=120)).timestamp()
        weak = driver.window_bounds(plan, now, 11, 9 * 3600)
        strong = driver.window_bounds(plan, now, 11, 10 * 3600)
        self.assertLess(strong, weak)
        self.assertLessEqual(weak - now, 12 * 3600)
        with self.assertRaises(RuntimeError):
            driver.window_bounds(plan, now, 12, 9 * 3600)
        with self.assertRaises(RuntimeError):
            driver.window_bounds(plan, now, 11, 13 * 3600)

    def test_literal_six_field_prefix_and_infinity_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix='p1-packet-fixture-') as tmp:
            ns = private(Path(tmp))
            first = packet([[.01, 1., float('inf')]])
            a = ns['store_packet'](ns['OUT'] / 'a', first, None, [])
            self.assertEqual(ns['load_packet'](a['path'], a, None, []), first)
            second = packet(first['checkpoint']['physical_checkpoint']['state']['history'] + [[.02, 2., 3.]])
            b = ns['store_packet'](ns['OUT'] / 'b', second, a, first['checkpoint']['physical_checkpoint']['state']['history'])
            restored = ns['load_packet'](b['path'], b, a, first['checkpoint']['physical_checkpoint']['state']['history'])
            self.assertEqual(restored, second)
            for key, bad in (('original_sha256', '0' * 64), ('history_sha256', '1' * 64),
                             ('history_length', 999), ('design_sha256', '2' * 64)):
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    ns['load_packet'](b['path'], {**b, key: bad}, a, first['checkpoint']['physical_checkpoint']['state']['history'])
            changed_parent = {**a, 'original_sha256': '0' * 64}
            with self.assertRaises(RuntimeError):
                ns['load_packet'](b['path'], b, changed_parent, first['checkpoint']['physical_checkpoint']['state']['history'])

    def test_immediate_raw_and_older_post_inventory_mutations(self):
        with tempfile.TemporaryDirectory(prefix='p1-packet-mutation-') as tmp:
            ns = private(Path(tmp)); value = packet([])
            a = ns['store_packet'](ns['OUT'] / 'a', value, None, [])
            cache = {}; ns['load_reference'](a, cache)
            data = Path(a['path']).read_bytes()
            Path(a['path']).write_bytes(data + b'changed')
            with self.assertRaises(RuntimeError):
                ns['load_reference'](a, cache)
            # The prospective full-post schedule freshly hashes EVERY earlier
            # raw against its admission inventory, even if a parent was cached.
            with self.assertRaises(RuntimeError):
                ns['verify_mapping']({a['path']: a['compressed_sha256']})

    def test_raw_trace_exact_thirteen_columns(self):
        with tempfile.TemporaryDirectory(prefix='p1-trace-fixture-') as tmp:
            path = Path(tmp) / 'trace.npy'
            rows = [[float(i) for i in range(13)], [float(i + 1) for i in range(13)]]
            driver.write_trace(path, rows)
            self.assertEqual(driver.read_trace(path), rows)
            with path.open('ab') as stream:
                stream.write(b'x')
            with self.assertRaises(RuntimeError):
                driver.read_trace(path)

    def test_actual_restart_physics_projection_not_raw_walltime(self):
        c, f1, f2 = branch('c', 'C', 1), branch('f1', 'F1', 2), branch('f2', 'F2', 3)
        cp = dict(physical_checkpoint={'state': {'history': [], 'q': [3.] * 6}},
            published_state_token='x', cursor={'phase': 'idle'}, numeric_ledger={'all_work_rows': 3},
            history_root={}, frames={}, staged_history_nodes={}, pending_branches=[])
        serial = restart_packet([c, f1, f2], f1['rows'] + f2['rows'], cp)
        left = restart_packet([c], [], {**cp, 'cursor': {'phase': 'after_coarse'}})
        right = restart_packet([f1, f2], f1['rows'] + f2['rows'], cp)
        right['work_branches'][0]['compact_result']['runtime_seconds'] = 99.
        self.assertTrue(driver.restart_equal(serial, [left, right]))
        for field in ('q', 'reactions', 'iterations'):
            bad = copy.deepcopy(right)
            if field == 'q':
                bad['work_branches'][0]['after_state']['q'][0] += .01
            elif field == 'reactions':
                bad['work_branches'][0]['reactions'][0] += .01
            else:
                bad['work_branches'][0]['compact_result']['total_contact_iterations'] += 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                driver.restart_equal(serial, [left, bad])
        bad = copy.deepcopy(right); bad['checkpoint']['physical_checkpoint']['state']['history'] = [[1.]]
        with self.assertRaises(RuntimeError):
            driver.restart_equal(serial, [left, bad])

    def test_actual_first_active_accepted_even_split(self):
        spec = importlib.util.spec_from_file_location('pure_restart_contract', driver.RESTART)
        restart = importlib.util.module_from_spec(spec); spec.loader.exec_module(restart)
        rows = [dict(role='F1' if i % 2 == 0 else 'F2', trigger_grain_ids=[15] if i == 5 else []) for i in range(8)]
        self.assertEqual(restart.first_active_split(rows, 8)['j'], 4)
        for index in (0, 1):
            early = [dict(v, trigger_grain_ids=[15] if i == index else []) for i, v in enumerate(rows)]
            with self.assertRaises(ValueError):
                restart.first_active_split(early, 8)
        wrong = copy.deepcopy(rows); wrong[5]['role'] = 'C'
        with self.assertRaises(ValueError):
            restart.first_active_split(wrong, 8)

    def make_admission(self, ns, index=1, *, invalid=False):
        label = f'fixture{index}'; key = 'f0p0625'
        r = dict(index=index, level_id=key, kind='production', label=label, maximum_work_rows=3,
                 maximum_nonadvancing_kernel_invocations=0, design_sha256=ns['sha'](ns['PLAN']))
        reserve = ns['OUT'] / 'reservations' / f'{index:06d}.json'; ns['commit'](reserve, r)
        folder = ns['OUT'] / 'records' / label; folder.mkdir(parents=True)
        raw = folder / 'packet.json.xz'; raw.write_bytes(lzma.compress(json.dumps({'packet': {'work_rows': 3}}).encode()))
        aggregate = dict(all_work_rows=3, success_work_rows=3, rejected_work_rows=0,
            committed_half_rows=2, coarse_shadow_work_rows=1, discarded_diagnostic_work_rows=1,
            raw_branch_classification_sha256='a'*64, complete_production_boundary=True)
        ns['seal'](folder / 'policy_mechanical_audit_01', dict(passed=True, work_rows=3,
            independent_mechanical_replay_performed=True, production_aggregate_sha256=ns['digest'](aggregate),
            **ns['guard_bindings']()))
        artifacts = {str(p): ns['sha'](p) for p in folder.rglob('*') if p.is_file()}
        metadata = {p: h for p, h in artifacts.items() if not p.endswith('.xz')}
        ns['seal'](ns['OUT'] / 'admissions' / f'{index:06d}', dict(passed=True, index=index, level_id=key,
            kind='production', label=label, work_rows=3, reservation_sha256=ns['sha'](reserve),
            audit_sha256=ns['sha'](folder / 'policy_mechanical_audit_01/results.json'), artifacts=artifacts,
            chain_metadata=metadata, production_aggregate=aggregate))
        return folder

    def test_actual_ledger_chain_and_metadata_mutation(self):
        with tempfile.TemporaryDirectory(prefix='p1-ledger-fixture-') as tmp:
            ns = private(Path(tmp)); self.make_admission(ns, 1); self.make_admission(ns, 2)
            counts = ns['ledger']()
            self.assertEqual((counts['work_rows'], counts['records'], counts['accepted_committed_half_rows']), (6, 2, 4))
            path = ns['OUT'] / 'admissions/000001/results.json'
            path.write_text(path.read_text() + ' ', encoding='utf-8')
            with self.assertRaises(RuntimeError):
                ns['ledger']()

    def test_actual_partial_known_overrun_is_not_clamped(self):
        with tempfile.TemporaryDirectory(prefix='p1-ledger-partial-') as tmp:
            ns = private(Path(tmp)); folder = self.make_admission(ns)
            # Preserve a partial admission negative rather than overwriting its
            # frozen seal. A raw known6 versus reserved3 is charged as6.
            path = ns['OUT'] / 'admissions/000001/results.json'
            path.write_text(path.read_text() + ' ', encoding='utf-8')
            raw = folder / 'packet.json.xz'; raw.write_bytes(lzma.compress(json.dumps({'packet': {'work_rows': 6}}).encode()))
            ns['commit'](folder / 'accounting.json', dict(actual_work_known=True, work_rows=6, packet_sha256=ns['sha'](raw)))
            counts = ns['ledger']()
            self.assertEqual(counts['known_unaccepted_work_rows'], 6)
            self.assertEqual(counts['work_rows'], 6)
            self.assertEqual(len(counts['known_cap_overruns']), 1)
            with self.assertRaises(RuntimeError):
                ns['budget_guard'](counts, 'f0p0625', 'production', 1)

    def test_source_interfaces_actual_keyword_contract(self):
        def function(path, name):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        scope = function(driver.RUNTIME, 'native_execution_scope')
        scope_args = {a.arg for a in scope.args.args + scope.args.kwonlyargs}
        self.assertTrue({'spec', 'binding', 'dispatch_gate', 'plan_path', 'auth_path', 'physical_path',
                         'numerical', 'prior_receipt_authenticator'} <= scope_args)
        smoke = function(driver.RUNTIME, 'native_single_branch_smoke')
        self.assertTrue({'mode', 'rows', 'limits'} <= {a.arg for a in smoke.args.kwonlyargs})
        audit = function(driver.AUDITOR, 'audit_runtime_packet')
        self.assertTrue({'checkpoint_before', 'checkpoint_after', 'source_bindings', 'mechanical_stencil_adapter',
                         'expected_previous_receipt_sha256'} <= {a.arg for a in audit.args.kwonlyargs})
        tree = ast.parse(driver.RUNTIME.read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Runtime')
        advance = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'advance_packet')
        self.assertIn('pause_after_time_s', {a.arg for a in advance.args.kwonlyargs})
        self.assertTrue(driver.source_interfaces()['all_required_interfaces_present'])

    def test_actual_exhausted_budget_rejects_before_any_popen(self):
        observed = []
        now = driver.time.time()
        plan = dict(start_utc=datetime.fromtimestamp(now - 1, timezone.utc).isoformat(),
                    simulation_cutoff_utc=datetime.fromtimestamp(now + 124 * 3600, timezone.utc).isoformat(),
                    end_utc=datetime.fromtimestamp(now + 132 * 3600 - 1, timezone.utc).isoformat())
        for update in ({'work_rows': driver.MAX_WORK}, {'records': driver.MAX_RECORDS},
                       {'standalone_records': driver.MAX_STANDALONE_RECORDS},
                       {'nonadvancing_kernel_invocations': driver.MAX_NONADVANCING_KERNEL_INVOCATIONS}):
            counts = driver.empty_counts(); counts.update(update)
            namespace = dict(vars(driver), ledger=lambda: counts, replay_reserve=lambda *args: 3600.,
                             start_child=lambda *args: observed.append(args))
            function = driver.Execution.ensure_window
            actual = FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
            self.assertIs(actual.__code__, driver.Execution.ensure_window.__code__)
            owner = SimpleNamespace(plan=plan, audited_levels=set(), handle=None, window_index=0,
                                    window_request=0, window_stop=None, setup_complete=False)
            with self.subTest(update=update), self.assertRaises(RuntimeError):
                actual(owner, 'f0p0625', 'production', driver.PACKET_CAP)
        self.assertEqual(observed, [])

    def test_actual_staged_branch_authenticator_rejects_mutation(self):
        with tempfile.TemporaryDirectory(prefix='p1-staged-fixture-') as tmp:
            ns = private(Path(tmp))
            # This fixture tests only byte/role association, never mechanics.
            ns['PLAN'].write_text(json.dumps({'source_files': {}, 'physical_inputs': {}}), encoding='utf-8')
            staged = branch('m1_C', 'C', 1)
            raw = packet([]); raw['checkpoint']['pending_branches'] = [staged]
            prefix = ns['store_packet'](ns['OUT'] / 'records' / 'staged', raw, None, [])
            folder = ns['OUT'] / 'records/staged'
            reserve = ns['OUT'] / 'reservations/000001.json'
            ns['commit'](reserve, dict(index=1, label='staged', kind='standalone', level_id='f0p0625',
                                    design_sha256=ns['sha'](ns['PLAN'])))
            ns['seal'](folder / 'policy_mechanical_audit_01', dict(passed=True,
                independent_mechanical_replay_performed=True, **ns['guard_bindings']()))
            metadata = {str(path): ns['sha'](path) for path in folder.rglob('*') if path.is_file() and not path.name.endswith('.xz')}
            receipt = ns['OUT'] / 'admissions/000001'
            ns['seal'](receipt, dict(passed=True, index=1, label='staged', kind='standalone', level_id='f0p0625',
                reservation_sha256=ns['sha'](reserve), audit_sha256=ns['sha'](folder / 'policy_mechanical_audit_01/results.json'),
                chain_metadata=metadata))
            actual = dict(staged, previous_packet_receipt_sha256=ns['sha'](receipt / 'results.json'))
            self.assertTrue(ns['authenticate_prior_branch'](actual))
            changed = copy.deepcopy(actual); changed['reactions'][0] += .1
            with self.assertRaises(RuntimeError):
                ns['authenticate_prior_branch'](changed)

    def test_failed_prelude_reports_unknown_warm_not_zero_actual(self):
        with tempfile.TemporaryDirectory(prefix='p1-warm-unknown-') as tmp:
            ns = private(Path(tmp))
            ns['commit'](ns['OUT'] / 'reservations/000001.json', dict(index=1,
                level_id='f0p0625', kind='standalone', label='warm', maximum_work_rows=1,
                maximum_nonadvancing_kernel_invocations=2, design_sha256=ns['sha'](ns['PLAN'])))
            counts = ns['ledger']()
            self.assertEqual(counts['known_nonadvancing_kernel_invocations'], 0)
            self.assertEqual(counts['unknown_nonadvancing_kernel_invocations_upper_bound'], 2)
            self.assertIsNone(counts['actual_nonadvancing_kernel_invocations'])
            self.assertEqual(counts['unknown_reserved_work_upper_bound'], 1)
            with self.assertRaises(RuntimeError):
                ns['budget_guard'](counts, 'f0p0625', 'production', 1)

    def test_actual_monotone_rate_excludes_tiny_diagnostic_overhead(self):
        with tempfile.TemporaryDirectory(prefix='p1-rate-fixture-') as tmp:
            ns = private(Path(tmp))
            ns['PLAN'].write_text(json.dumps({'frozen_replay_reserve_rule': {
                'seconds_per_unreplayed_all_work_row': .01, 'fixed_closure_seconds': 3600}}), encoding='utf-8')
            samples = [('standalone', 1, 100.), ('production', 3, 100.), ('production', 3000, 30.)]
            for index, (kind, rows, seconds) in enumerate(samples, 1):
                ns['commit'](ns['OUT'] / 'reservations' / f'{index:06d}.json', {'maximum_work_rows': 4998})
                ns['seal'](ns['OUT'] / 'admissions' / f'{index:06d}', dict(passed=True, index=index,
                    kind=kind, work_rows=rows, independent_replay_seconds=seconds))
            self.assertEqual(ns['effective_replay_rate'](), .02)
            ns['seal'](ns['OUT'] / 'cost_observations/001', dict(passed=True,
                design_sha256=ns['sha'](ns['PLAN']), conservative_replay_seconds_per_work_row=.03))
            self.assertEqual(ns['effective_replay_rate'](), .03)

    def test_actual_output_retention_and_free_reserve_edges(self):
        current = [1024, 8 * 1024**3, 40 * 1024**3]
        namespace = dict(vars(driver), inventory_bytes=lambda: tuple(current),
                         shutil=SimpleNamespace(disk_usage=lambda root: SimpleNamespace(free=current[2])),
                         _RESOURCE_LAST=[0., None])
        fn = driver.resource_guard
        actual = FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)
        actual.__kwdefaults__ = copy.copy(fn.__kwdefaults__)
        self.assertTrue(actual(force_inventory=True)['free_bytes'] > driver.FREE_BYTES)
        for index, value in ((0, driver.OWN_BYTES), (1, driver.RETENTION_BYTES), (2, driver.FREE_BYTES)):
            current[:] = [1024, 8 * 1024**3, 40 * 1024**3]; current[index] = value
            with self.subTest(index=index), self.assertRaises(RuntimeError):
                actual(force_inventory=True)

    def test_actual_prefix_gate_uses_earlier_real_overshoot_clock(self):
        # This is the ORIGINAL pure metrics source with artificial arrays.
        # It performs no field/geometry/native/transport work.
        metric_dir = HERE.parent / 'stage180_staging'
        sys.path.insert(0, str(metric_dir))
        try:
            source = importlib.util.spec_from_file_location('original_prefix_metrics_fixture', metric_dir / 'streaming_path_metrics_v2.py')
            metrics = importlib.util.module_from_spec(source); source.loader.exec_module(metrics)
        finally:
            sys.path.remove(str(metric_dir))
        import numpy as np
        initial = [0., 0., 0., 0., 1., 0., 0., *([0.] * 6)]
        ends = (.255001, .255002)
        arrays = [np.asarray([[.2, .2, 0., 0., 1., 0., 0., *([1.] * 6)],
                              [end, end, 0., 0., 1., 0., 0., *([1.] * 6)]]) for end in ends]
        with self.assertRaises(ValueError):
            metrics.metrics([arrays[0]], [arrays[1]], initial, initial, .255, .255, 1., 1.)
        with tempfile.TemporaryDirectory(prefix='p1-prefix-overshoot-') as tmp:
            ns = private(Path(tmp)); replay, states = {}, {}
            for index, key in enumerate(driver.LEVELS[:2], 1):
                path = Path(tmp) / f'{key}.npy'; driver.write_trace(path, arrays[index-1].tolist())
                replay[key] = (dict(trace_paths=[str(path)], stop_s=ends[index-1]), {})
                states[key] = dict(time_s=ends[index-1])
                ns['commit'](ns['OUT'] / 'reservations' / f'{index:06d}.json', {'maximum_work_rows': 4998})
                ns['seal'](ns['OUT'] / 'admissions' / f'{index:06d}', dict(passed=True, index=index,
                    kind='production', work_rows=3000, owner_packet_seconds=3.))
            cfg = dict(prolate_semiaxes_m=[2., 1., 1.], target_mean_interstitial_velocity_m_s=1.)
            case = dict(spec=dict(initial_state=dict(position_m=initial[1:4], orientation=initial[4:7],
                                                     velocity_generalized=initial[7:13]), config=cfg))
            counts = driver.empty_counts(); counts['work_rows'] = 6000
            proposal = dict(prefix_forecast_rule=dict(online_observed_rate_multiplier=1., observed_bytes_per_work_multiplier=1.10))
            actual_read = ns['read']
            ns.update(metric_interface=lambda: (SimpleNamespace(s=SimpleNamespace(q=SimpleNamespace(job=SimpleNamespace(
                path_metrics=SimpleNamespace(metrics=metrics.metrics))))), None), definitions=lambda: {key: {'case': case} for key in driver.LEVELS},
                ledger=lambda: counts, read=lambda path: proposal if path == driver.PROPOSAL else actual_read(path),
                replay_reserve=lambda *args: 3600., effective_replay_rate=lambda: .01,
                resource_guard=lambda **kwargs: dict(own_bytes=1000000, total_retained_bytes=1024**3, free_bytes=100*1024**3))
            owner = SimpleNamespace(plan=dict(end_utc=datetime.fromtimestamp(driver.time.time()+132*3600, timezone.utc).isoformat(),
                                             source_files={}), audited_levels=set())
            result = ns['prefix_cost_gate'](owner, states, replay)
            self.assertTrue(result['passed'])
            self.assertEqual(result['common_physical_analysis_stop_s'], min(ends))
            self.assertFalse(result['full_path_accuracy_passed'])

    def classification_fixture(self):
        values = [branch(f'm1{role}', role, index) for index, role in enumerate(('C', 'F1', 'F2'), 1)]
        result = restart_packet(values, values[1]['rows']+values[2]['rows'],
            dict(physical_checkpoint={'state': {'pending_trial': None}}, pending_branches=[]))
        result.update(status='paused_controller', cursor_before={'phase': 'idle'}, cursor_after={'phase': 'idle'},
            trials=[{'branch_ids': [value['branch_id'] for value in values], 'decision': {'action': 'commit_literal_halves'}}])
        return result

    def test_compact_classification_matches_raw_and_rejects_pending_production(self):
        packet = self.classification_fixture()
        aggregate = driver.production_classification(packet)
        self.assertEqual((aggregate['all_work_rows'], aggregate['success_work_rows'],
                          aggregate['committed_half_rows'], aggregate['discarded_diagnostic_work_rows']), (3, 3, 2, 1))
        self.assertTrue(driver.verify_production_aggregate(packet, {'production_aggregate': aggregate}))
        for field, value in (('cursor_after', {'phase': 'publish_second_half'}),
                             ('carried_branches', [packet['work_branches'][0]])):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                driver.production_classification({**packet, field: value})
        pending = copy.deepcopy(packet); pending['checkpoint']['pending_branches'] = [packet['work_branches'][0]]
        with self.assertRaises(RuntimeError):
            driver.production_classification(pending)

    def test_compact_aggregate_tamper_and_raw_replay_mismatch_rejected(self):
        packet = self.classification_fixture(); aggregate = driver.production_classification(packet)
        bad = {**aggregate, 'committed_half_rows': 1}
        with self.assertRaises(RuntimeError):
            driver.validate_production_aggregate(bad, 3)
        # This partition is internally bounded but is false for these exact
        # raw trial decisions. The mandatory whole post replay catches it.
        resealed = {**aggregate, 'success_work_rows': 0, 'rejected_work_rows': 3,
                    'committed_half_rows': 0, 'discarded_diagnostic_work_rows': 3}
        driver.validate_production_aggregate(resealed, 3)
        with self.assertRaises(RuntimeError):
            driver.verify_production_aggregate(packet, {'production_aggregate': resealed})
        with self.assertRaises(RuntimeError):
            driver.verify_production_aggregate(packet, {'production_aggregate': {
                **aggregate, 'raw_branch_classification_sha256': 'f'*64}})

    def test_compact_rejected_trial_partition_and_guard_map_digest(self):
        packet = self.classification_fixture()
        packet['trials'][0]['decision']['action'] = 'discard_all_and_halve'
        packet['committed_branch_ids'] = []; packet['accepted_rows'] = []
        packet['cursor_after']['phase'] = 'after_rejection'
        aggregate = driver.production_classification(packet)
        self.assertEqual((aggregate['rejected_work_rows'], aggregate['committed_half_rows'],
                          aggregate['discarded_diagnostic_work_rows']), (3, 0, 3))
        with tempfile.TemporaryDirectory(prefix='p1-guard-digest-') as tmp:
            ns = private(Path(tmp)); guard = ns['guard_bindings']()
            ns['verify_guard_bindings'](guard)
            self.assertNotIn('source_files', guard)
            with self.assertRaises(RuntimeError):
                ns['verify_guard_bindings']({**guard, 'source_mapping_sha256': 'f'*64})


if __name__ == '__main__':
    unittest.main(verbosity=2)
