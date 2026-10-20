"""Tiny offline corruption controls; no native imports, archives or trajectories.

Runs the candidate's actual adapted nested record verifier and the unchanged
oracle inventory/restart predicates against labelled synthetic JSON fixtures.
It never imports the transport/oracle runtime or executes a retained path.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta
import ast
import copy
import hashlib
import json
import tempfile
import unittest

import authenticate_sealed_chain_candidate_v1 as candidate


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def mapping(values):
    for path, expected in values.items():
        candidate.need(candidate.sha(path) == expected, 'fixture artifact changed')


def sealed(path):
    path = Path(path)
    candidate.need(read(path.with_name('completion.json'))['results_sha256'] == candidate.sha(path), 'fixture unsealed receipt')
    return read(path)


def seal(path, value):
    write(path, value)
    write(Path(path).with_name('completion.json'), {'results_sha256': candidate.sha(path)})


def original_function(name, namespace):
    tree = ast.parse(candidate.ORACLE.read_text())
    fn = copy.deepcopy(next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<unchanged-oracle-fixture>', 'exec'), namespace)
    return namespace[name]


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='paper1_chain_controls_')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.level = self.root / 'levels/f0p0625'
        self.folder = self.level / 'records/production_00001'
        self.folder.mkdir(parents=True)
        self.api = SimpleNamespace(digest=digest, sha=candidate.sha, verify_mapping=mapping)
        self.s = SimpleNamespace(read=read, sha=candidate.sha, ROOT=self.root, PYTHON=Path('fixture-python.exe'),
                                 identity=lambda launch: {'retired': True}, fields=SimpleNamespace(sealed=sealed))
        self.selector = self.root / 'selector.py'
        self.producer = self.root / 'producer.py'
        self.work = self.root / 'policy.json'
        for path in (self.selector, self.producer, self.work):
            path.write_text('frozen fixture source')
        self.case = {'spec': {'fixture': 'no mechanics'}}
        self.config = {'enabled': True, 'policy': {'fixture': True}}
        cp = {'state': {'t': .1, 'steps': 1, 'pending_trial': None, 'history': ['complete fixture history']}}
        row = {'time_s': .1, 'position_m': [0., 0., 0.], 'orientation': [1., 0., 0.],
               'velocity_generalized': [0.] * 6}
        self.record = dict(design_sha256='physical', spec=self.case['spec'], input_checkpoint_sha256=digest(None), step_cap=1,
                           rows=[row], result={'checkpoint': cp, 'rejected': 0},
                           numerical_policy_contract_sha256=candidate.sha(self.work),
                           onset_timecap={**self.config, 'source_sha256': candidate.sha(self.selector),
                               'journal': [{'trigger_grain_ids': [15], 'selected_dt_s': .1, 'base_dt_s': .2}]})
        raw = self.folder / 'call.json.xz'
        write(raw, self.record)  # Deliberately JSON: decoder below is a fixture double.
        trace = self.folder / 'trace.npy'
        write(trace, [[.1, *row['position_m'], *row['orientation'], *row['velocity_generalized']]])
        receipt = dict(passed=True, summary={'passed': True, 'start_s': 0., 'stop_s': .1}, new_saved_steps=1,
                       transport_design_sha256='plan', physical_design_sha256='physical',
                       input_checkpoint_sha256=digest(None), previous_receipt_sha256=None,
                       output_checkpoint_sha256=digest(cp), role='core_pending_accuracy',
                       numerical_policy_contract_sha256=candidate.sha(self.work), original_binding='fixture-binding',
                       artifacts={str(raw): candidate.sha(raw)})
        write(self.folder / 'results.json', receipt)
        write(self.folder / 'completion.json', {'results_sha256': candidate.sha(self.folder / 'results.json')})
        write(self.folder / 'accounting.json', {'saved_steps_known': True, 'saved_steps': 1, 'raw_sha256': candidate.sha(raw)})
        write(self.folder / 'launch.json', {'transport_design_sha256': 'plan', 'physical_design_sha256': 'physical',
              'input_checkpoint_sha256': digest(None), 'argv': [str(self.s.PYTHON), '-B', '-u', str(self.producer), 'window'],
              'pid': 999, 'created': 123.})
        guard = dict(passed=True, saved_steps=1, full_checkpoint_sha256=digest(cp), guard_audit={'passed': True},
                     artifacts={str(p): candidate.sha(p) for p in self.folder.iterdir() if p.is_file()})
        seal(self.folder / 'guard_completion/results.json', guard)
        policy = dict(passed=True, raw_sha256=candidate.sha(raw),
              original_physical_guard_sha256=candidate.sha(self.folder / 'guard_completion/results.json'),
              accepted_rows=1, journal_entries=1, pending_witnesses=0, start_s=0., stop_s=.1,
              trigger_count=1, tightened_steps=1, original_caps_never_increased=True,
              independent_geometry_and_policy_replayed=True, replaces_original_physics_audit=False,
              native_solver_calls=0, new_saved_steps=0)
        seal(self.folder / 'timecap_guard/results.json', policy)
        reservation = dict(global_index=1, level_id='f0p0625', label='production_00001', kind='production',
                           maximum_saved_steps=1, input_checkpoint_sha256=digest(None), previous_result_sha256=None)
        write(self.level / 'reservations/production_00001.json', reservation)
        admission = dict(passed=True, **{k: reservation[k] for k in ('global_index', 'level_id', 'label', 'kind')},
             saved_steps=1, cap=1, full_checkpoint_sha256=digest(cp), raw_sha256=candidate.sha(raw),
             physical_guard_sha256=candidate.sha(self.folder / 'guard_completion/results.json'),
             timecap_guard_sha256=candidate.sha(self.folder / 'timecap_guard/results.json'),
             reservation_sha256=candidate.sha(self.level / 'reservations/production_00001.json'))
        self.admission = self.root / 'admissions/000001/results.json'
        seal(self.admission, admission)
        artifacts = {}
        def bind(path, out): out[str(path)] = candidate.sha(path)
        def document(path, docs, physical_sha, out): bind(path, out); return read(path)
        self.namespace = dict(require=candidate.need, api=self.api, s=self.s, Path=Path,
            _deadline=lambda p: None, _document=document, _bind=bind,
            _receipt_decisions=candidate.receipt_decisions,
            inventory={'production_00001': reservation}, level=self.level, plan={}, plan_sha='plan', physical_sha='physical',
            docs=None, artifacts=artifacts, case=self.case, shared_config=self.config, selector=SimpleNamespace(__file__=str(self.selector)),
            physical={}, ctx=SimpleNamespace(job=SimpleNamespace(WORK=self.work, binding=lambda physical, case: 'fixture-binding')),
            codec=SimpleNamespace(read_record=lambda path, design, prefix: (read(path), 'fixture-prefix')),
            np=SimpleNamespace(asarray=lambda rows, dtype: rows, float64=float, load=lambda path, **kw: read(path), array_equal=lambda a,b: a == b),
            identities={}, receipts={}, admission_paths={1: self.admission},
            plan_source_files={str(self.producer): candidate.sha(self.producer)})
        self.namespace['plan']['source_files'] = self.namespace.pop('plan_source_files')
        tree, _ = candidate.candidate_ast()
        nested = copy.deepcopy(next(x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name == 'verify_record'))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[nested], type_ignores=[])), '<actual-adapted-record-fixture>', 'exec'), self.namespace)

    def verify(self):
        return self.namespace['verify_record']('production_00001', None, None, None, True)

    def test_positive_record_and_no_runtime_import(self):
        self.assertEqual(self.verify()[0], self.record)
        self.assertFalse('evaluate_timecap_full_v1' in __import__('sys').modules)

    def test_record_rejections(self):
        changes = ('missing_receipt', 'unsealed_receipt', 'failed_receipt', 'altered_raw',
                   'altered_trace', 'altered_seed', 'altered_source', 'altered_accounting', 'wrong_admission')
        # Each fixture is independent; corruptions never touch retained evidence.
        for name in changes:
            with self.subTest(name=name):
                other = Fixtures(); other.setUp()
                try:
                    if name == 'altered_seed': other.namespace['inventory']['production_00001']['input_checkpoint_sha256'] = 'wrong'
                    elif name == 'altered_source': other.producer.write_text('changed source')
                    elif name == 'wrong_admission': seal(other.admission, {**read(other.admission), 'saved_steps': 2})
                    elif name == 'failed_receipt': seal(other.folder / 'timecap_guard/results.json', {**read(other.folder / 'timecap_guard/results.json'), 'passed': False})
                    elif name == 'altered_trace': write(other.folder / 'trace.npy', [[999]])
                    elif name == 'altered_accounting': write(other.folder / 'accounting.json', {'saved_steps_known': True, 'saved_steps': 2})
                    elif name == 'altered_raw': (other.folder / 'call.json.xz').write_text('altered')
                    elif name == 'missing_receipt': (other.folder / 'timecap_guard/results.json').unlink()
                    else: (other.folder / 'guard_completion/completion.json').unlink()
                    with self.assertRaises((RuntimeError, OSError, ValueError, KeyError)):
                        other.verify()
                finally: other.doCleanups()

    def test_inventory_and_unknown_work_rejections(self):
        ns = {'Path': Path, 'require': candidate.need, 's': self.s, '_bind': lambda path, out: None}
        inventory = original_function('_reservation_inventory', ns)
        native = {'production_labels': ['production_00001'], 'diagnostic_labels': []}
        self.assertEqual(len(inventory(self.level, native, {})), 1)
        (self.level / 'records/orphan').mkdir()
        with self.assertRaises(RuntimeError): inventory(self.level, native, {})
        tree = candidate.candidate_ast()[0]
        check = next(x for x in ast.walk(tree) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
                     and x.func.id == 'require' and len(x.args) > 1
                     and isinstance(x.args[1], ast.Constant) and x.args[1].value == 'native complete with no hidden failed or unknown work')
        code = compile(ast.fix_missing_locations(ast.Module(body=[ast.Expr(copy.deepcopy(check))], type_ignores=[])), '<actual-native-completion-predicate>', 'exec')
        for key in ('known_unaccepted_saved_steps', 'unknown_reserved_steps_upper_bound'):
            row = {'passed': True, 'native_complete': True, 'known_unaccepted_saved_steps': 0, 'unknown_reserved_steps_upper_bound': 0}
            exec(code, {'require': candidate.need, 'native': row})
            row[key] = 1
            with self.assertRaises(RuntimeError): exec(code, {'require': candidate.need, 'native': row})

    def test_first_trigger_predicate_rejections(self):
        tree = candidate.candidate_ast()[0]
        check = next(x for x in ast.walk(tree) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
                     and x.func.id == 'require' and len(x.args) > 1 and isinstance(x.args[1], ast.Constant)
                     and x.args[1].value == 'first actual triggered production record reproduced exactly across the split')
        code = compile(ast.fix_missing_locations(ast.Module(body=[ast.Expr(copy.deepcopy(check))], type_ignores=[])), '<actual-first-trigger-predicate>', 'exec')
        original = {'input_checkpoint_sha256': 'seed', 'rows': [0, 1], 'result': {'checkpoint': {'state': {'pending_trial': None, 'history': ['FULL']}}}}
        serial = copy.deepcopy(original)
        left = {'rows': [0]}
        right = {'rows': [1], 'onset_timecap': {'journal': [{'trigger_grain_ids': [15]}]}}
        restart = {'original_production_label': 'production_00001', 'first_trigger_index': 1, 'triggered_successor': True}
        ns = dict(require=candidate.need, api=self.api, original=original, serial=serial, left=left, right=right,
                  restart=restart, first_trigger={'label': 'production_00001'}, j=1)
        exec(code, ns)
        for name in ('later_trigger', 'missing_split_b_trigger', 'hidden_full_history', 'wrong_split_length'):
            bad = copy.deepcopy(ns)
            if name == 'later_trigger': bad['restart']['original_production_label'] = 'production_00002'
            elif name == 'missing_split_b_trigger': bad['right']['onset_timecap']['journal'][0]['trigger_grain_ids'] = []
            elif name == 'hidden_full_history': bad['serial']['result']['checkpoint']['state']['history'] = ['changed']
            else: bad['left']['rows'] = []
            with self.subTest(name=name), self.assertRaises(RuntimeError): exec(code, bad)

    def test_destination_and_pinned_transform(self):
        _, counts = candidate.candidate_ast()
        self.assertEqual(counts['mechanical'], 3)
        with self.assertRaises(RuntimeError): candidate.external_destination(self.level, self.root / 'candidate')
        with self.assertRaises(RuntimeError): candidate.external_destination(self.level, candidate.ROOT / 'full_audit_01')

    def test_actual_metadata_is_truthful_and_anchored(self):
        tree = ast.parse(candidate.SELF.read_text())
        fn = copy.deepcopy(next(x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name == 'metadata'))
        raw = str(self.folder / 'call.json.xz')
        resources = candidate.ResourceBoundary(self.resource_plan(), self.root, self.root / 'candidate',
            inventory=lambda *args: (0, 0, 0), free=lambda: 1000 * 1024**2, monotonic=lambda: 0.)
        ns = dict(boundary=lambda plan: None, final_pin_check=lambda: None, final_stage=[False],
                  level=self.level, Path=Path, need=candidate.need, resources=resources,
                  closure={'artifacts': {raw: candidate.sha(raw)}, 'qualification_passed': False},
                  closed_execution_sha256='closed-fixture', expected_candidate_sha256=candidate.sha(candidate.SELF),
                  ORACLE_SHA256=candidate.ORACLE_SHA256, ORACLE=candidate.ORACLE, SELF=candidate.SELF,
                  changes=candidate.candidate_ast()[1], start=datetime.now(timezone.utc), end=datetime.now(timezone.utc),
                  RECEIPT_OUTPUT_CAP=candidate.RECEIPT_OUTPUT_CAP,
                  INVENTORY_INTERVAL_SECONDS=candidate.INVENTORY_INTERVAL_SECONDS)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<actual-candidate-metadata>', 'exec'), ns)
        body = {'artifacts': {raw: candidate.sha(raw)}, 'source_files': {},
                'full_selector_policy_replayed': True, 'original_physics_and_guard_replayed': True,
                'core_result_admitted': True, 'full_path_accuracy_passed': True}
        result = ns['metadata'](body)
        self.assertFalse(result['postexit_mechanical_replay'] or result['core_result_admitted']
                         or result['full_path_accuracy_passed'] or result['full_selector_policy_replayed']
                         or result['original_physics_and_guard_replayed'])
        self.assertTrue(result['original_independent_receipts_authenticated'] and result['candidate_uninstalled'])
        with self.assertRaises(RuntimeError):
            ns['metadata']({'artifacts': {raw: 'changed'}, 'source_files': {}})
        external = tempfile.TemporaryDirectory(prefix='paper1_external_oracle_fixture_')
        self.addCleanup(external.cleanup)
        outside = Path(external.name) / 'old_same_factor_raw.xz'
        outside.write_text('original smoke plus authenticated tail')
        outside_path = str(outside.resolve())
        self.assertNotIn(self.level.parent.parent, outside.resolve().parents)
        ns['closure']['artifacts'][outside_path] = candidate.sha(outside)
        ns['metadata']({'artifacts': {outside_path: candidate.sha(outside)}, 'source_files': {}})
        outside.write_text('same smoke but altered and resealed external tail')
        with self.assertRaises(RuntimeError):
            ns['metadata']({'artifacts': {outside_path: candidate.sha(outside)}, 'source_files': {}})

    @staticmethod
    def resource_plan():
        return dict(maximum_new_output_bytes=64 * 1024**2, unchanged_total_retention_bytes=128 * 1024**2,
                    unchanged_free_reserve_bytes=32 * 1024**2)

    def test_original_absolute_clock_controls(self):
        original_start = '2026-10-16T12:00:00+00:00'
        original_end = '2026-10-18T00:00:00+00:00'
        start, end = '2026-10-17T16:00:00+00:00', '2026-10-17T18:00:00+00:00'
        now = datetime.fromisoformat('2026-10-17T17:00:00+00:00')
        self.assertEqual(candidate.validation_bounds(start, end, original_start, original_end, now)[1],
                         datetime.fromisoformat(end))
        cases = {
            'beyond_original_end': (start, '2026-10-18T00:00:01+00:00', original_start, original_end, now),
            'naive_end': (start, '2026-10-17T18:00:00', original_start, original_end, now),
            'naive_original_end': (start, end, original_start, '2026-10-18T00:00:00', now),
            'invalid_text': (start, 'invalid', original_start, original_end, now),
            'reversed': (end, start, original_start, original_end, now),
            'expired': (start, end, original_start, original_end, datetime.fromisoformat(end)),
            'not_started': (start, end, original_start, original_end, datetime.fromisoformat(start) - timedelta(seconds=1)),
            'before_original_start': ('2026-10-16T11:59:59+00:00', end, original_start, original_end, now),
        }
        for name, args in cases.items():
            with self.subTest(name=name), self.assertRaises((RuntimeError, ValueError)):
                candidate.validation_bounds(*args)

    def test_unchanged_resource_and_output_controls(self):
        plan, reserve = self.resource_plan(), candidate.RECEIPT_OUTPUT_CAP
        normal = (8 * 1024**2, 16 * 1024**2, 0)
        def resource(inventory=normal, free=64 * 1024**2):
            return candidate.ResourceBoundary(plan, self.root, self.root / 'candidate',
                inventory=lambda *args: inventory, free=lambda: free, monotonic=lambda: 0.)
        resource().check(force=True)
        cases = {
            'insufficient_free_reserve': resource(free=plan['unchanged_free_reserve_bytes'] + reserve - 1),
            'retention_with_candidate_reserve': resource(inventory=(normal[0], plan['unchanged_total_retention_bytes'] - reserve + 1, 0)),
            'output_with_candidate_reserve': resource(inventory=(plan['maximum_new_output_bytes'] - reserve + 1, normal[1], 0)),
            'candidate_own_output_cap': resource(inventory=(normal[0], normal[1], 1)),
        }
        for name, boundary in cases.items():
            with self.subTest(name=name), self.assertRaises(RuntimeError): boundary.check(force=True)
        with self.assertRaises(RuntimeError): resource().serialized_size({'oversize': 'x' * reserve})
        with self.assertRaises(RuntimeError): resource().check(reserved_output=reserve + 1)
        with self.assertRaises(RuntimeError):
            candidate.ResourceBoundary({**plan, 'maximum_output_bytes': plan['maximum_new_output_bytes'] + 1},
                                       self.root, self.root / 'candidate')

    def test_resource_inventory_is_periodic_not_per_record(self):
        clock, calls = [0.], {'inventory': 0, 'free': 0}
        def inventory(*args): calls['inventory'] += 1; return (0, 0, 0)
        def free(): calls['free'] += 1; return 1024**3
        boundary = candidate.ResourceBoundary(self.resource_plan(), self.root, self.root / 'candidate',
            inventory=inventory, free=free, monotonic=lambda: clock[0])
        for _ in range(100): boundary.check()
        self.assertEqual(calls, {'inventory': 1, 'free': 100})
        clock[0] = candidate.INVENTORY_INTERVAL_SECONDS
        boundary.check()
        self.assertEqual(calls['inventory'], 2)
        boundary.check(force=True, reserved_output=0)
        self.assertEqual(calls['inventory'], 3)

    def test_final_candidate_closure_and_oracle_mutation_rejections(self):
        paths = [self.root / name for name in ('candidate_source.py', 'closed_receipt.json', 'oracle_source.py')]
        for path in paths: path.write_text('unchanged tiny fixture')
        pinned = [candidate.sha(path) for path in paths]
        args = [value for pair in zip(paths, pinned) for value in pair]
        candidate.verify_final_pins(*args)
        for index, name in enumerate(('candidate', 'closure', 'oracle')):
            with self.subTest(name=name):
                paths[index].write_text('changed after entry authentication')
                with self.assertRaises(RuntimeError): candidate.verify_final_pins(*args)
                paths[index].write_text('unchanged tiny fixture')
        # Actual final-boundary hook must recheck after metadata enters final stage.
        tree = ast.parse(candidate.SELF.read_text())
        fn = copy.deepcopy(next(x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name == 'boundary'))
        checks = []
        now = datetime.now(timezone.utc)
        ns = dict(datetime=datetime, timezone=timezone, start=now - timedelta(minutes=1), end=now + timedelta(minutes=1),
                  need=candidate.need, final_stage=[True], final_pin_check=lambda: checks.append('checked'),
                  resources=SimpleNamespace(check=lambda **kw: None), closure={'identity_inspections_after_hashing': []},
                  RECEIPT_OUTPUT_CAP=candidate.RECEIPT_OUTPUT_CAP)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<actual-final-boundary-hook>', 'exec'), ns)
        ns['boundary'](None)
        self.assertEqual(checks, ['checked'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
