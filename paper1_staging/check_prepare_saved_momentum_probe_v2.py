"""Pure recovery preparation controls; no model, evidence seal or authority."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

SELF = Path(__file__).resolve()
module_before = set(sys.modules)
spec = importlib.util.spec_from_file_location('_prepare_momentum_recovery_controls',
    SELF.with_name('prepare_saved_momentum_probe_v2.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
IMPORTS = set(sys.modules) - module_before


def actors():
    return [dict(pid=100 + i, created=10. + i, command=['python', '-B', str(i)]) for i in range(10)]


def closed_negative():
    ledger = dict(all_work_rows=0, integration_records=2, nonadvancing_units=2,
        known_unaccepted_work_rows=0, unknown_reserved_work_upper_bound=0)
    closed = dict(passed=True, execution_closed=True, final_disposition_passed=False,
        saved_input_screen_passed=False, full_horizon_qualified=False, full_restart_qualified=False,
        ledger=copy.deepcopy(ledger))
    final = dict(passed=False, ledger=copy.deepcopy(ledger))
    diagnosis = dict(passed=True, implementation_defect_confirmed=True, target_outer_calls=0,
        prepared_inner_maps=0, actual_hot_phase_calls=0, new_force_calls=0, new_native_calls=0,
        initial_attempt_closed_sha256=p.CLOSED_SHA, initial_attempt_final_sha256=p.FINAL_SHA,
        prior_probe_spent=copy.deepcopy(p.PRIOR_PROBE_SPENT),
        raw_sha256='922aa79e3f8bcb1a519be3e49d6a4678a6acfcd1b5bc3550a6a6d1a39eda143d')
    return closed, final, diagnosis


class Checks(unittest.TestCase):
    def test_actual_closed_probe_wire_mappings_are_not_assumed_in_disposition(self):
        closed = p.read(p.CLOSED)
        final = p.read(p.FINAL)
        diagnosis = p.read(p.DIAGNOSIS)
        prior = p.read(p.BASE_PREP)
        self.assertNotIn('physical_inputs', final)
        self.assertNotIn('evidence_files', final)
        self.assertNotIn('historical_evidence_files', final)
        sources, physical, evidence, history = p.inherited_mappings(
            closed, final, diagnosis, prior, {}, {})
        self.assertTrue(sources and physical and evidence and history)
        self.assertTrue(set(closed['physical_inputs']) <= set(physical))
        self.assertTrue(set(closed['evidence_files']) <= set(evidence))
        self.assertTrue(set(final['artifacts']) <= set(history))
        bad = copy.deepcopy(closed)
        del bad['physical_inputs']
        with self.assertRaises(KeyError):
            p.inherited_mappings(bad, final, diagnosis, prior, {}, {})

    def test_import_is_source_only(self):
        self.assertFalse(any(x.startswith(('numpy', 'numba', 'stage', 'full_state_integration')) for x in IMPORTS))
        tree = ast.parse(SELF.with_name('prepare_saved_momentum_probe_v2.py').read_text(encoding='utf-8'))
        calls = [n for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
        self.assertEqual(calls, [])

    def test_distinct_recovery_paths_and_no_output_copy(self):
        self.assertNotEqual(p.FAMILY, p.BASE_FAMILY)
        self.assertNotEqual(p.OUT, p.INITIAL_OUT)
        self.assertEqual(p.FIXTURES, p.BASE_FAMILY / 'fixtures_01.json')
        source = SELF.with_name('prepare_saved_momentum_probe_v2.py').read_text(encoding='utf-8')
        self.assertNotIn('copyfile(', source)
        self.assertNotIn('build_fixtures', source)
        self.assertNotIn('analyze_saved(', source)

    def test_only_new_controls_reexecute(self):
        self.assertEqual(p.CHECKS, ('check_cancellation_safe_velocity_v2.py',
            'check_run_saved_momentum_probe_v2.py', 'check_prepare_saved_momentum_probe_v2.py'))
        self.assertNotIn('check_prepare_saved_momentum_probe_v1.py', p.CHECKS)

    def test_original_authority_not_replaced(self):
        self.assertEqual(p.END, '2026-10-24T07:43:33.769535+00:00')
        self.assertEqual(p.NUMERICAL_END, '2026-10-23T23:43:33.769535+00:00')
        self.assertEqual(p.OUTER_CLOCK_SHA, 'a2f1cffc1ca0ad235125487f316c6b124eac8b1df3f72bb191b8748ae8a22737')
        self.assertEqual(set(p.forbidden()), {p.OUT, p.FAMILY/'design_01.json',
            p.FAMILY/'authorization_01.json', p.FAMILY/'human_approval_01',
            p.FAMILY/'window_clock_01', p.FAMILY/'execution_logs_01'})

    def test_conflicting_immutable_mapping_rejected(self):
        self.assertEqual(p.merge({'a': 'x'}, {'a': 'x', 'b': 'y'}), {'a': 'x', 'b': 'y'})
        with self.assertRaises(ValueError):
            p.merge({'a': 'x'}, {'a': 'changed'})

    def test_exact_eight_plus_two_identities(self):
        values = actors()
        old = dict(prior_exact_process_identities=values[:8])
        closed = dict(retirement_after=[dict(launch=x, inspection=dict(retired=True)) for x in values[8:]])
        result = p.prior_identity_inventory(old, closed)
        self.assertEqual(result, values)
        result[0]['command'][0] = 'changed'
        self.assertEqual(values[0]['command'][0], 'python')

    def test_missing_inventory_not_empty_retirement(self):
        with self.assertRaises(KeyError):
            p.prior_identity_inventory({}, {})
        with self.assertRaises(ValueError):
            p.prior_identity_inventory(dict(prior_exact_process_identities=actors()[:7]),
                dict(retirement_after=[]))

    def test_live_latest_actor_rejected(self):
        values = actors()
        latest = [dict(launch=x, inspection=dict(retired=True)) for x in values[8:]]
        latest[1]['inspection']['retired'] = False
        with self.assertRaises(ValueError):
            p.prior_identity_inventory(dict(prior_exact_process_identities=values[:8]),
                dict(retirement_after=latest))

    def test_duplicate_identity_rejected(self):
        values = actors()
        latest = [dict(launch=x, inspection=dict(retired=True)) for x in (values[0], values[9])]
        with self.assertRaises(ValueError):
            p.prior_identity_inventory(dict(prior_exact_process_identities=values[:8]),
                dict(retirement_after=latest))

    def test_unreadable_or_nonfinite_birth_and_command_rejected(self):
        for key, value in (('created', None), ('created', float('nan')), ('created', float('inf')),
                           ('created', 0), ('pid', True), ('command', None), ('command', []),
                           ('command', ['python', ''])):
            actor = actors()[0]; actor[key] = value
            with self.assertRaises((ValueError, TypeError)):
                p.check_identity(actor)

    def test_exact_closed_initial_negative_admitted_as_evidence_only(self):
        values = closed_negative()
        self.assertEqual(p.verify_initial_negative(*values), dict(all_work_rows=0,
            integration_records=2, nonadvancing_units=2, numerical_windows=1))

    def test_unclosed_or_scientific_pass_cannot_replace_initial_negative(self):
        for field in ('execution_closed', 'passed'):
            values = closed_negative(); values[0][field] = False
            with self.assertRaises(ValueError):
                p.verify_initial_negative(*values)
        values = closed_negative(); values[0]['saved_input_screen_passed'] = True
        with self.assertRaises(ValueError):
            p.verify_initial_negative(*values)

    def test_initial_unknown_or_known_work_not_erased(self):
        for field in ('all_work_rows', 'integration_records', 'nonadvancing_units',
                      'known_unaccepted_work_rows', 'unknown_reserved_work_upper_bound'):
            values = closed_negative(); values[1]['ledger'][field] += 1
            with self.assertRaises(ValueError):
                p.verify_initial_negative(*values)

    def test_nonzero_outer_map_or_kernel_rejects_implementation_only_waiver(self):
        for field in ('target_outer_calls', 'prepared_inner_maps', 'actual_hot_phase_calls',
                      'new_force_calls', 'new_native_calls'):
            for nonzero in (1, True, 0.0):
                values = closed_negative(); values[2][field] = nonzero
                with self.assertRaises(ValueError):
                    p.verify_initial_negative(*values)

    def test_unproven_defect_or_changed_negative_bindings_rejected(self):
        for field, value in (('implementation_defect_confirmed', False),
            ('initial_attempt_closed_sha256', 'changed'), ('initial_attempt_final_sha256', 'changed'),
            ('prior_probe_spent', {}), ('raw_sha256', 'changed')):
            values = closed_negative(); values[2][field] = value
            with self.assertRaises(ValueError):
                p.verify_initial_negative(*values)

    def test_local_and_combined_allocations_are_distinct(self):
        b = p.budget_envelope()
        self.assertEqual((b['maximum_new_all_trial_work_rows'], b['maximum_new_integration_records'],
            b['maximum_nonadvancing_invocation_units'], b['maximum_numerical_windows']), (260, 5, 10, 1))
        self.assertEqual(b['combined_probe_maximum'], dict(all_work_rows=260,
            integration_records=7, nonadvancing_units=12, numerical_windows=2))
        self.assertTrue(b['prior_suballocation_amendment_required'])
        self.assertTrue(b['fresh_recovery_window_requires_new_human_approval'])

    def test_no_warm_record_window_refund(self):
        b = p.budget_envelope(); previous = b['prior_probe_spent']
        self.assertEqual(previous, dict(all_work_rows=0, integration_records=2, nonadvancing_units=2, numerical_windows=1))
        self.assertEqual(previous['integration_records'] + b['maximum_new_integration_records'], 7)
        self.assertEqual(previous['nonadvancing_units'] + b['maximum_nonadvancing_invocation_units'], 12)
        self.assertEqual(previous['numerical_windows'] + b['maximum_numerical_windows'], 2)

    def test_case_and_shared_caps_unchanged(self):
        limits = p.budget_envelope()['original_maximum']
        self.assertEqual((limits['cumulative_case_work_rows'], limits['cumulative_case_records']), (28312778, 6174))
        self.assertEqual((limits['cumulative_shared_work_rows'], limits['cumulative_shared_records']), (22664866, 5004))
        self.assertEqual((limits['work_rows'], limits['records'], limits['nonadvancing_charge'], limits['numerical_windows']),
            (18000000, 4000, 22, 11))

    def test_worst_case_counters_include_closed_attempt(self):
        b = p.budget_envelope(); before = b['original_spent']; after = b['worst_case_original_after']
        for key, increment in (('work_rows', 260), ('records', 5), ('nonadvancing_charge', 10),
                               ('numerical_windows', 1), ('standalone_work_rows', 260), ('standalone_records', 5)):
            self.assertEqual(before[key] + increment, after[key])
            self.assertLessEqual(after[key], b['original_maximum'][key])
        self.assertEqual(sum(before[k] for k in ('admitted_physical_rows', 'admitted_discarded_rows',
            'known_unaccepted_rows', 'old_unknown_reserved_rows')), before['work_rows'])

    def test_source_only_writes_after_final_authentication(self):
        tree = ast.parse(SELF.with_name('prepare_saved_momentum_probe_v2.py').read_text(encoding='utf-8'))
        body = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'prepare')
        calls = [x for x in ast.walk(body) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)]
        writes = [x.lineno for x in calls if isinstance(x.func.value, ast.Name)
                  and x.func.value.id == 'admin' and x.func.attr in ('seal', 'commit')]
        hashes = [x.lineno for x in calls if isinstance(x.func.value, ast.Name)
                  and x.func.value.id == 'admin' and x.func.attr == 'verify_mapping']
        after = next(x.lineno for x in ast.walk(body) if isinstance(x, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'after' for t in x.targets))
        self.assertEqual(len(writes), 2)
        self.assertGreater(min(writes), max(hashes))
        self.assertGreater(min(writes), after)

    def test_actual_consumer_initial_prerequisite_failure_prevents_write(self):
        events = []
        def failed_initial(common, proposal):
            events.append('initial_negative_rejected')
            raise RuntimeError('strict actual initial prerequisite failure')
        driver = SimpleNamespace(validate_initial_attempt=failed_initial,
            source_interfaces=lambda: events.append('must_not_continue'))
        with self.assertRaises(RuntimeError):
            p.verify_consumer_package(driver, {}, {}, {})
            events.append('positive_write')
        self.assertEqual(events, ['initial_negative_rejected'])

    def test_actual_consumer_source_interfaces_are_pinned(self):
        driver = SimpleNamespace(validate_initial_attempt=lambda common, proposal: True,
            source_interfaces=lambda: {'old_driver': 'old', 'new_helper': 'new'})
        self.assertTrue(p.verify_consumer_package(driver, {}, {}, {'old_driver': 'old', 'new_helper': 'new'}))
        with self.assertRaises(ValueError):
            p.verify_consumer_package(driver, {}, {}, {'old_driver': 'old', 'new_helper': 'changed'})
        with self.assertRaises(ValueError):
            p.verify_consumer_package(driver, {}, {}, {'new_helper': 'new'})

    def test_consumer_prerequisite_call_precedes_positive_seals(self):
        tree = ast.parse(SELF.with_name('prepare_saved_momentum_probe_v2.py').read_text(encoding='utf-8'))
        body = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'prepare')
        prerequisite = [x.lineno for x in ast.walk(body) if isinstance(x, ast.Call)
            and isinstance(x.func, ast.Name) and x.func.id == 'verify_consumer_package']
        positive = [x.lineno for x in ast.walk(body) if isinstance(x, ast.Call)
            and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Name)
            and x.func.value.id == 'admin' and x.func.attr in ('seal', 'commit')]
        self.assertEqual(len(prerequisite), 1)
        self.assertLess(prerequisite[0], min(positive))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(passed=result.wasSuccessful(), pure_controls=result.testsRun,
        native_force_calls=0, transport_steps=0, authority_created=False), sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
