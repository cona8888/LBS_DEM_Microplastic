"""Zero-native fixtures: extract only pure guards; never import the runner."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
import ast
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).with_name('run_support_common_state_v3.py')


def pure_namespace():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    namespace = dict(datetime=datetime, timezone=timezone, timedelta=timedelta, copy=copy)
    wanted = {'DEADLINE', 'STEP_CAP', 'CALL_CAP', 'PRIOR_STEPS', 'PRIOR_CALLS', 'LOCAL_STEPS',
              'LOCAL_CALLS', 'CASE_STEPS', 'CASE_CALLS', 'TOTAL_DIAGNOSTIC_STEPS', 'TOTAL_DIAGNOSTIC_CALLS'}
    wanted.update(('SHARED_STEPS', 'SHARED_CALLS', 'PRIOR_SHARED_STEPS', 'PRIOR_SHARED_CALLS'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in wanted:
                namespace[target.id] = ast.literal_eval(node.value)
            elif isinstance(target, ast.Tuple) and all(isinstance(x, ast.Name) and x.id in wanted for x in target.elts):
                namespace.update(zip([x.id for x in target.elts], ast.literal_eval(node.value)))
    functions = [copy.deepcopy(x) for x in tree.body if isinstance(x, ast.FunctionDef)
                 and x.name in ('need', 'approval_scope', 'validate_approval', 'bounds', 'controls', 'authorize',
                                'activation_index', 'ledger', 'stop_exact', 'child')]
    functions.extend(copy.deepcopy(x) for x in tree.body if isinstance(x, ast.FunctionDef)
                     and x.name in ('recapture_owned_launch', 'failed_ledger', 'invoke', 'supervise',
                                    'control_hash_snapshot', 'retirement_snapshot', 'store_checkpoint'))
    functions.insert(0, copy.deepcopy(next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'budget_guard')))
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), '<pure-support-runtime-controls>', 'exec'), namespace)
    return namespace


class RuntimeGuards(unittest.TestCase):
    def test_preparation_explicit_seed_parent_precedes_original_store(self):
        path = SOURCE.with_name('prepare_support_common_state_v4.py')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'prepare')
        calls = [(i, node.value) for i, node in enumerate(fn.body)
                 if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]
        stores = [(i, call) for i, call in calls if ast.unparse(call.func) == 'original.DOC.store']
        parents = [(i, call) for i, call in calls if ast.unparse(call.func) == 'seed_folder.mkdir']
        self.assertEqual((len(stores), len(parents)), (1, 1))
        self.assertEqual(parents[0][0] + 1, stores[0][0])
        self.assertEqual({key.arg: ast.literal_eval(key.value) for key in parents[0][1].keywords},
                         {'parents': True, 'exist_ok': False})
        self.assertEqual(ast.unparse(stores[0][1].args[0]), "seed_folder / 'checkpoint.json'")

    def test_checkpoint_parent_exists_before_unchanged_writer_and_partials_are_preserved(self):
        ns = pure_namespace()
        with tempfile.TemporaryDirectory(prefix='support-document-parent-') as temp:
            root, calls = Path(temp), []
            def writer(path, checkpoint, physical_sha):
                self.assertTrue(Path(path).parent.is_dir())
                calls.append((path, checkpoint, physical_sha))
                Path(path).write_text('fixture exclusive reference')
                return {'fixture': 'original writer return'}
            ns.update(Path=Path, DOC=SimpleNamespace(store=writer))
            path = root / 'new/nested/checkpoint.json'
            checkpoint = {'state': {'fixture': 'unchanged FULL object'}}
            self.assertEqual(ns['store_checkpoint'](path, checkpoint, 'physical-source'),
                             {'fixture': 'original writer return'})
            self.assertIs(calls[0][1], checkpoint)
            self.assertEqual(calls[0][2], 'physical-source')
            for partial in ('reference', 'payload', 'seal'):
                target = root / partial / 'checkpoint.json'
                payload = target.with_name('checkpoint.payload.json.xz')
                present = {'reference': target, 'payload': payload,
                           'seal': payload.with_suffix('.seal.json')}[partial]
                present.parent.mkdir(parents=True)
                present.write_bytes(b'original partial evidence')
                before = len(calls)
                with self.assertRaises(RuntimeError):
                    ns['store_checkpoint'](target, checkpoint, 'physical-source')
                self.assertEqual(present.read_bytes(), b'original partial evidence')
                self.assertEqual(len(calls), before)
            tree = ast.parse(SOURCE.read_text())
            direct = [x for x in ast.walk(tree) if isinstance(x, ast.Call)
                      and ast.unparse(x.func) == 'DOC.store']
            routed = [x for x in ast.walk(tree) if isinstance(x, ast.Call)
                      and isinstance(x.func, ast.Name) and x.func.id == 'store_checkpoint']
            self.assertEqual((len(direct), len(routed)), (1, 3))
            helper = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'store_checkpoint')
            self.assertIn(direct[0], list(ast.walk(helper)))

    def test_actual_pure_controls(self):
        ns = pure_namespace()
        result = ns['controls']()
        self.assertTrue(result['passed'])
        self.assertEqual(result['zero_native_solver_calls'], 0)
        self.assertEqual(result['zero_transport_steps'], 0)
        self.assertGreaterEqual(result['mocked_rejections'], 17)

    def test_boolean_scope_cannot_be_integer(self):
        ns = pure_namespace()
        approval = dict(passed=True, proposal_sha256='a' * 64, human_reply='Fixture only',
            question_reference='synthetic', preparation_execution_receipt_sha256='b' * 64,
            scope=ns['approval_scope']())
        approval['scope']['support_common_state_diagnostic_authorized'] = 1
        with self.assertRaises(RuntimeError):
            ns['validate_approval'](approval, 'a' * 64)

    def test_missing_pin_and_unapproved_evidence_never_write_authority(self):
        ns = pure_namespace()
        with tempfile.TemporaryDirectory(prefix='support-runtime-guards-') as temp:
            root = Path(temp)
            approval_path = root / 'human.json'
            proposal = root / 'proposal.json'
            approval_path.write_text(json.dumps(dict(passed=False)))
            proposal.write_text('{}')
            writes = []
            digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            ns.update(PLAN=root / 'design.json', AUTH=root / 'authorization.json', OUT=root / 'output',
                APPROVAL=approval_path, PROPOSAL=proposal, s=SimpleNamespace(environment=lambda: None,
                    fields=SimpleNamespace(sealed=lambda path: json.loads(Path(path).read_text()))),
                sha=digest, commit=lambda *args: writes.append(args))
            with self.assertRaises(RuntimeError):
                ns['authorize'](None)
            with self.assertRaises(RuntimeError):
                ns['authorize']('0' * 64)
            with self.assertRaises(RuntimeError):
                ns['authorize'](digest(approval_path))
            self.assertEqual(writes, [])
            self.assertFalse(ns['AUTH'].exists() or ns['PLAN'].exists() or ns['OUT'].exists())

    def test_pending_activation_is_not_hidden(self):
        fn = pure_namespace()['activation_index']
        self.assertIsNone(fn([dict(trigger_grain_ids=[])]))
        self.assertEqual(fn([dict(trigger_grain_ids=[]), dict(trigger_grain_ids=[182])]), 1)

    def test_launch_record_failure_retires_exact_mock_before_unwinding(self):
        for failed_name in ('worker_launch.json', 'exit.json'):
            with self.subTest(failed_name=failed_name), tempfile.TemporaryDirectory(prefix='support-child-guard-') as temp:
                ns = pure_namespace()
                root = Path(temp)
                plan = root / 'plan.json'
                plan.write_text('{}')
                calls = []
                class FakeProcess:
                    pid = 999
                    code = None
                    def poll(self): return self.code
                    def terminate(self): calls.append('terminate'); self.code = -15
                    def wait(self, timeout):
                        calls.append('wait')
                        if self.code is None: self.code = 0
                        return self.code
                process = FakeProcess()
                def identity(launch):
                    self.assertEqual((launch['pid'], launch['created']), (999, 123.))
                    self.assertEqual(launch['command'][1:3], ['-B', '-u'])
                    calls.append('exact_identity')
                    return dict(retired=process.code is not None)
                def write(path, value):
                    if Path(path).name == failed_name:
                        raise OSError('synthetic write failure')
                    Path(path).write_text(json.dumps(value))
                ns.update(ROOT=root, SELF=SOURCE, PLAN=plan, PYTHON=Path('fixture-python.exe'),
                    subprocess=SimpleNamespace(Popen=lambda *args, **kwargs: process,
                        TimeoutExpired=subprocess.TimeoutExpired), os=SimpleNamespace(environ={}),
                    psutil=SimpleNamespace(Process=lambda pid: SimpleNamespace(create_time=lambda: 123.)),
                    inspect=identity, commit=write, sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    s=SimpleNamespace(utc=lambda: 'synthetic'), time=SimpleNamespace(time=lambda: 0.),
                    traceback=SimpleNamespace(format_exc=lambda: 'synthetic traceback'))
                with self.assertRaises((RuntimeError, OSError)):
                    ns['child']('run', root / 'controller', 100.)
                self.assertIsNotNone(process.code)
                if failed_name == 'worker_launch.json':
                    self.assertIn('terminate', calls)
                    self.assertLess(calls.index('exact_identity'), calls.index('terminate'))
                # Both inherited log handles closed even when launch/exit writes fail.
                for name in ('stdout.log', 'stderr.log'):
                    with (root / 'controller' / name).open('ab') as stream:
                        stream.write(b'fixture closed')

    def test_initial_birth_failure_slow_child_is_recaptured_and_stopped(self):
        for inaccessible in (False, True):
            with self.subTest(inaccessible=inaccessible), tempfile.TemporaryDirectory(prefix='support-birth-guard-') as temp:
                ns, root, calls = pure_namespace(), Path(temp), []
                plan = root / 'plan.json'; plan.write_text('{}')
                state = {'birth_reads': 0, 'command': None}
                class SlowProcess:
                    pid = 888
                    code = None
                    def poll(self): return self.code
                    def terminate(self): calls.append('terminate'); self.code = -15
                    def wait(self, timeout):
                        calls.append('wait')
                        if self.code is None: raise subprocess.TimeoutExpired('synthetic slow child', timeout)
                        return self.code
                process = SlowProcess()
                def birth():
                    state['birth_reads'] += 1
                    if inaccessible or state['birth_reads'] == 1: raise OSError('synthetic inaccessible birth')
                    return 123.
                def popen(command, **kwargs): state['command'] = command; return process
                def identity(launch):
                    self.assertEqual(launch['created'], 123.)
                    self.assertEqual(launch['command'], state['command'])
                    calls.append('both_exact_identity')
                    return dict(retired=process.code is not None)
                def write(path, value): Path(path).write_text(json.dumps(value))
                ns.update(ROOT=root, SELF=SOURCE, PLAN=plan, PYTHON=Path('fixture-python.exe'),
                    subprocess=SimpleNamespace(Popen=popen, TimeoutExpired=subprocess.TimeoutExpired),
                    os=SimpleNamespace(environ={}),
                    psutil=SimpleNamespace(Process=lambda pid: SimpleNamespace(create_time=birth,
                        cmdline=lambda: state['command'])), inspect=identity, commit=write,
                    sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    s=SimpleNamespace(utc=lambda: 'synthetic'),
                    time=SimpleNamespace(time=lambda: 0., sleep=lambda seconds: None),
                    traceback=SimpleNamespace(format_exc=lambda: 'synthetic traceback'))
                folder = root / 'controller'
                with self.assertRaises(RuntimeError): ns['child']('run', folder, 100.)
                receipt = json.loads((folder / 'exit.json').read_text())
                if inaccessible:
                    self.assertNotIn('terminate', calls)
                    self.assertIsNone(receipt['returncode'])
                    self.assertFalse(receipt['identity']['retired'])
                    self.assertTrue(receipt['identity']['unresolved_identity'])
                    self.assertTrue(receipt['live_logs_unsealed'])
                    self.assertEqual(receipt['logs'], {})
                else:
                    self.assertEqual(process.code, -15)
                    self.assertTrue(receipt['identity']['retired'])
                    self.assertTrue(receipt['launch']['freshly_recaptured'])
                    self.assertLess(calls.index('both_exact_identity'), calls.index('terminate'))

    def test_partial_admission_is_charged_and_cannot_dispatch(self):
        ns = pure_namespace()
        with tempfile.TemporaryDirectory(prefix='support-partial-admission-') as temp:
            root = Path(temp)
            def write(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            reserve = root / 'reservations/001.json'
            write(reserve, dict(index=1, branch=0, label='branch0_serial', kind='discarded_diagnostic', maximum_saved_steps=256))
            raw = root / 'records/branch0_serial/call.json.xz'
            raw.parent.mkdir(parents=True); raw.write_bytes(b'fixture native output')
            accounting = raw.with_name('accounting.json')
            write(accounting, dict(saved_steps_known=True, saved_steps=2, raw_sha256=digest(raw)))
            write(root / 'admissions/001/results.json', dict(passed=True))  # deliberately no completion seal
            writes = []
            ns.update(OUT=root, Path=Path, sha=digest, read=lambda p: json.loads(Path(p).read_text()),
                s=SimpleNamespace(fields=SimpleNamespace(sealed=lambda p: self.fail('An incomplete admission was read as sealed'))),
                api=SimpleNamespace(verify_mapping=lambda value: self.fail('No accepted guard exists')),
                authority=lambda numerical: {}, time=SimpleNamespace(time=lambda: 0.),
                commit=lambda *args: writes.append(args))
            counts = ns['ledger']()
            self.assertEqual((counts['accepted_diagnostic_steps'], counts['known_unaccepted_saved_steps'],
                              counts['unknown_reserved_steps_upper_bound']), (0, 2, 0))
            self.assertEqual(counts['conservative_call_charges'], 1)
            self.assertEqual(len(counts['admission_failures']), 1)
            with self.assertRaises(RuntimeError):
                ns['invoke'](None, lambda *args: self.fail('Native transaction must not run'),
                    dict(simulation_cutoff_utc='2030-01-01T00:00:00+00:00'), None, None, 0,
                    'branch0_split_a', 128, None, None, None)
            self.assertEqual(writes, [])
            write(accounting, dict(saved_steps_known=True, saved_steps=2, raw_sha256='incorrect'))
            self.assertEqual(ns['ledger']()['unknown_reserved_steps_upper_bound'], 256)
            reserve.write_text('incomplete reservation')
            fallback = ns['failed_ledger'](RuntimeError('fixture invalid reservation'))
            self.assertFalse(fallback['ledger_authenticated'])
            self.assertIsNone(fallback['unknown_reserved_steps_upper_bound'])
            self.assertEqual(fallback['accepted_diagnostic_steps'], 0)
            self.assertFalse(fallback['authorized_envelope_demonstrable'])
            self.assertEqual(fallback['authorized_additional_saved_step_ceiling'], ns['STEP_CAP'])

    def test_failed_source_resource_and_ledger_still_seal_negative_under_original_design(self):
        ns = pure_namespace()
        with tempfile.TemporaryDirectory(prefix='support-negative-finalizer-') as temp:
            root = Path(temp)
            plan = root / 'plan.json'; plan.write_text('original frozen design')
            digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            expected = digest(plan)
            p = dict(end_utc=ns['DEADLINE'], simulation_cutoff_utc=ns['DEADLINE'],
                     source_files={'expected-source': 'original'}, physical_inputs={'expected-input': 'original'})
            calls, sealed = [], []
            def authority(numerical):
                if calls: raise RuntimeError('synthetic changed source/input gate')
                calls.append('initial-authority'); return p
            def child(*args):
                plan.write_text('changed design must not replace original binding')
                raise RuntimeError('synthetic child administration failure')
            def write(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            def fail(kind): raise RuntimeError('synthetic ' + kind)
            fixed = datetime.fromisoformat('2026-10-17T23:00:00+00:00')
            ns.update(OUT=root / 'output', PLAN=plan, AUTH=root / 'auth.json', PHYSICAL=root / 'physical.json',
                APPROVAL=root / 'approval.json', SELF=SOURCE, Path=Path,
                sha=digest, read=lambda path: json.loads(Path(path).read_text()), authority=authority, child=child,
                psutil=SimpleNamespace(Process=lambda: SimpleNamespace(pid=999, create_time=lambda: 123.,
                    cmdline=lambda: ['synthetic'], cpu_affinity=lambda cpus: None)),
                time=SimpleNamespace(time=lambda: fixed.timestamp()),
                datetime=SimpleNamespace(now=lambda tz: fixed, fromisoformat=datetime.fromisoformat),
                commit=write, resources=lambda p: fail('resource gate'), ledger=lambda: fail('ledger gate'),
                seal=lambda path, body: sealed.append((path, body)),
                traceback=SimpleNamespace(format_exc=lambda: 'synthetic traceback'), s=SimpleNamespace(utc=lambda: fixed.isoformat()))
            with self.assertRaises(SystemExit) as stopped:
                ns['supervise']()
            self.assertEqual(stopped.exception.code, 2)
            self.assertEqual(len(sealed), 1)
            body = sealed[0][1]
            self.assertFalse(body['passed'])
            self.assertFalse(body['ledger']['ledger_authenticated'])
            self.assertFalse(body['all_exact_numerical_producers_retired'])
            self.assertEqual(body['design_sha256'], expected)
            self.assertEqual(body['source_files'], p['source_files'])
            self.assertNotEqual(body['observed_control_files'][str(plan)]['sha256'], expected)
            self.assertEqual({x['kind'] for x in body['finalization_failures']},
                             {'final_source_input_resource_gate', 'resource_limit', 'ledger_authentication'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
