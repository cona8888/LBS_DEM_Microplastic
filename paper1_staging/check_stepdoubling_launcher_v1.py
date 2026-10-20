"""Mock-only controls of actual inactive launcher/closer functions.

The actual wrapper code is privately rebound to temporary byte fixtures and
synthetic Popen/identity objects.  No OS subprocess, model, field, native force,
authority or campaign output is executed.  This is not native qualification.
"""
from pathlib import Path
from types import FunctionType, SimpleNamespace
from unittest.mock import patch
import copy
import importlib.util
import json
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('inactive_launcher_under_test', HERE / 'launch_stepdoubling_qualification_v1.py')
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
driver = wrapper.run


class Child:
    pid = 700002
    def __init__(self, live=False, code=0):
        self.live, self.code, self.waits = live, code, 0
    def poll(self):
        return None if self.live else self.code
    def wait(self, timeout=None):
        self.waits += 1
        if self.live:
            raise TimeoutError('synthetic still-live child')
        return self.code


class Harness:
    def __init__(self, root):
        self.root = root
        self.out = root / 'output'; self.out.mkdir()
        self.plan = root / 'plan.json'; driver.commit(self.plan, {'synthetic': True})
        self.child = Child()
        self.identities = []
        self.stopped = []
        self.captures = 0
        self.capture_failures = 0
        self.inventory_error = False
        self.retirement_inspection_error = False
        self.seals = {}
        self.now = 100.
        self.fixed_end = 10000.
        self.launch_identity = dict(pid=self.child.pid, created=12., command=['synthetic', 'supervise'])
        self.psutil = SimpleNamespace(Process=self.process)
        self.run = SimpleNamespace(ROOT=root, OUT=self.out, PLAN=self.plan, PYTHON=root / 'python.exe', SELF=root / 'driver.py',
            ORIGINAL_GATES={'unchanged': 1}, environment=lambda: None,
            authority=lambda *a, **kw: dict(end_utc=self.fixed_end, source_files={}, physical_inputs={},
                evidence_files={}, historical_evidence_files={}),
            instant=lambda x: x, utc=lambda: 'synthetic-only', need=driver.need,
            sha=driver.sha, is_sha=driver.is_sha, read=driver.read,
            commit=driver.commit, verify_mapping=driver.verify_mapping,
            sealed=driver.sealed, process_identity=self.capture,
            registered_identities=self.inventory, inspect_identity=self.inspect,
            exact_stop=self.stop, seal=self.seal, assert_retired=self.retired,
            ledger=lambda: {'synthetic': 0}, artifact_inventory=self.artifacts)

    def process(self, pid=None):
        return SimpleNamespace(pid=900001 if pid is None else pid, cpu_affinity=lambda x: None,
            create_time=lambda: 11., cmdline=lambda: ['synthetic-wrapper'])

    def capture(self, child, command):
        self.captures += 1
        if self.captures <= self.capture_failures:
            raise PermissionError('synthetic inaccessible birth/full command')
        return copy.deepcopy(self.launch_identity)

    def inspect(self, identity):
        if self.retirement_inspection_error and self.child.waits:
            raise PermissionError('synthetic post-exit identity inaccessible')
        if identity['pid'] == self.child.pid:
            return {'retired': not self.child.live}
        return {'retired': True}

    def retired(self, identities):
        for identity in identities:
            driver.need(self.inspect(identity)['retired'], 'synthetic exact identity remains live')
        return [{'launch': x, 'inspection': self.inspect(x)} for x in identities]

    def stop(self, process, identity):
        # A mock must still receive BOTH the recorded birth and full command.
        driver.need(identity == self.launch_identity and process.pid == identity['pid'],
                    'no PID-only mock stop')
        self.stopped.append(copy.deepcopy(identity)); self.child.live = False

    def inventory(self):
        if self.inventory_error:
            raise ValueError('synthetic corrupt registered launch')
        return copy.deepcopy(self.identities)

    def artifacts(self, **kwargs):
        return {str(p): driver.sha(p) for p in self.out.rglob('*') if p.is_file()}

    def seal(self, path, value):
        self.seals[str(path)] = copy.deepcopy(value)
        return driver.seal(path, value)

    def clone(self, name):
        source = getattr(wrapper, name)
        namespace = dict(source.__globals__, run=self.run,
            subprocess=SimpleNamespace(Popen=lambda *a, **kw: self.child, CREATE_NO_WINDOW=0),
            time=SimpleNamespace(time=lambda: self.now, sleep=lambda seconds: None))
        fn = FunctionType(source.__code__, namespace, source.__name__, source.__defaults__, source.__closure__)
        return fn


class LauncherControls(unittest.TestCase):
    def test_normal_actual_handle_exit_and_closed_logs(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-mock-') as tmp:
            h = Harness(Path(tmp))
            with patch.dict(sys.modules, psutil=h.psutil):
                self.assertEqual(h.clone('launch')(), 0)
            receipt = driver.sealed(h.out / 'launcher/completion_01/results.json')
            self.assertEqual(receipt['actual_supervisor_returncode'], 0)
            self.assertTrue(receipt['supervisor_returncode_directly_observed'])
            self.assertEqual(h.child.waits, 1)
            driver.verify_mapping(receipt['closed_logs'])

    def test_inaccessible_post_exit_identity_preserves_observed_return_negative(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-inaccessible-retirement-') as tmp:
            h = Harness(Path(tmp)); h.retirement_inspection_error = True
            with patch.dict(sys.modules, psutil=h.psutil):
                self.assertEqual(h.clone('launch')(), 2)
            receipt = driver.sealed(h.out / 'launcher/completion_01/results.json')
            self.assertEqual(receipt['actual_supervisor_returncode'], 0)
            self.assertTrue(receipt['supervisor_returncode_directly_observed'])
            self.assertFalse(receipt['passed'])
            self.assertFalse(receipt['supervisor_retirement']['retired'])
            self.assertTrue(receipt['errors'])
            self.assertEqual(h.stopped, [])
            driver.verify_mapping(receipt['closed_logs'])

    def test_registration_recapture_stops_only_exact_identity(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-recapture-') as tmp:
            h = Harness(Path(tmp)); h.child.live = True; h.capture_failures = 1
            with patch.dict(sys.modules, psutil=h.psutil):
                self.assertEqual(h.clone('launch')(), 2)
            self.assertEqual(h.stopped, [h.launch_identity])
            self.assertEqual(h.child.waits, 1)
            receipt = driver.sealed(h.out / 'launcher/completion_01/results.json')
            self.assertFalse(receipt['passed']); self.assertTrue(receipt['forced'])

    def test_corrupt_registered_inventory_cannot_skip_known_child_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-inventory-') as tmp:
            h = Harness(Path(tmp)); h.child.live = True; h.capture_failures = 1; h.inventory_error = True
            with patch.dict(sys.modules, psutil=h.psutil):
                try:
                    h.clone('launch')()
                except BaseException:
                    pass
            self.assertEqual(h.stopped, [h.launch_identity], 'always retire captured exact supervisor despite corrupt sibling metadata')
            self.assertEqual(h.child.waits, 1, 'always directly observe the original Popen handle')

    def test_inaccessible_identity_never_permits_pid_only_stop(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-unresolved-') as tmp:
            h = Harness(Path(tmp)); h.child.live = True; h.capture_failures = 99
            with patch.dict(sys.modules, psutil=h.psutil), self.assertRaises(TimeoutError):
                h.clone('launch')()
            self.assertEqual(h.stopped, [])
            negative = driver.read(h.out / 'launcher/unresolved_registration_failure.json')
            self.assertTrue(negative['no_exitcode_inferred'])
            self.assertTrue(negative['live_owned_handle_unresolved'])

    def test_fast_exit_without_readable_identity_retains_actual_handle_negative(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-fast-unregistered-') as tmp:
            h = Harness(Path(tmp)); h.child.code = 2; h.capture_failures = 99
            with patch.dict(sys.modules, psutil=h.psutil), self.assertRaises(RuntimeError):
                h.clone('launch')()
            self.assertEqual(h.stopped, [])
            self.assertEqual(h.child.waits, 1)
            negative = driver.read(h.out / 'launcher/unresolved_registration_failure.json')
            self.assertEqual(negative['actual_supervisor_returncode'], 2)
            self.assertTrue(negative['supervisor_returncode_directly_observed'])
            self.assertFalse(negative['retirement_authenticated'])
            driver.verify_mapping(negative['closed_logs'])

    def close_fixture(self, h):
        folder = h.out / 'launcher'
        driver.commit(folder / 'launch.json', dict(pid=900001, created=11., command=['synthetic-wrapper']))
        wrapper_receipt = dict(passed=False, supervisor_returncode_directly_observed=True,
            actual_supervisor_returncode=2, supervisor_launch=h.launch_identity,
            closed_logs={}, forced=False, errors=[])
        driver.seal(folder / 'completion_01', wrapper_receipt)
        owner = dict(pid=700003, created=13., command=['synthetic-owner'])
        driver.commit(h.out / 'owner/launch.json', owner)
        driver.commit(h.out / 'owner/exit.json', dict(launch=owner, returncode=2, logs={}))
        driver.commit(h.out / 'supervisor/launch.json', h.launch_identity)
        return driver.sha(folder / 'completion_01/results.json')

    def test_missing_final_disposition_seals_negative_closure(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-missing-final-') as tmp:
            h = Harness(Path(tmp)); pin = self.close_fixture(h)
            driver.seal(h.out / 'supervisor/completion_01', dict(passed=False,
                held_design_sha256=driver.sha(h.plan),
                directly_observed_owner_exit_sha256=driver.sha(h.out / 'owner/exit.json'),
                directly_observed_owner_returncode=2, final_disposition_sha256='0'*64))
            h.clone('close')(pin)
            result = driver.sealed(h.out / 'final_execution_receipt_01/results.json')
            self.assertFalse(result['passed']); self.assertFalse(result['qualified'])
            self.assertTrue(result['closure_errors'])
            self.assertEqual(result['eligible_case_count'], 1)

    def test_complete_failed_scientific_disposition_can_close_without_qualification(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-complete-negative-') as tmp:
            h = Harness(Path(tmp)); pin = self.close_fixture(h)
            final = dict(passed=False, qualification_passed=False, design_sha256=driver.sha(h.plan),
                artifacts=h.artifacts(), ledger={'synthetic': 0})
            driver.seal(h.out / 'final_disposition_01', final)
            driver.seal(h.out / 'supervisor/completion_01', dict(passed=False,
                held_design_sha256=driver.sha(h.plan),
                directly_observed_owner_exit_sha256=driver.sha(h.out / 'owner/exit.json'),
                directly_observed_owner_returncode=2,
                final_disposition_sha256=driver.sha(h.out / 'final_disposition_01/results.json')))
            h.clone('close')(pin)
            result = driver.sealed(h.out / 'final_execution_receipt_01/results.json')
            self.assertTrue(result['closure_complete']); self.assertTrue(result['passed'])
            self.assertFalse(result['qualified']); self.assertEqual(result['eligible_case_count'], 1)
            self.assertEqual(result['actual_supervisor_returncode'], 2)

    def test_mutated_final_immutable_artifact_cannot_be_resealed_positive(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-mutated-final-') as tmp:
            h = Harness(Path(tmp)); pin = self.close_fixture(h)
            artifact = h.out / 'records/a/immutable.json'; driver.commit(artifact, {'original': True})
            final = dict(passed=False, qualification_passed=False, design_sha256=driver.sha(h.plan),
                artifacts={str(artifact): driver.sha(artifact)}, ledger={'synthetic': 0})
            driver.seal(h.out / 'final_disposition_01', final)
            driver.seal(h.out / 'supervisor/completion_01', dict(passed=False,
                held_design_sha256=driver.sha(h.plan),
                directly_observed_owner_exit_sha256=driver.sha(h.out / 'owner/exit.json'),
                directly_observed_owner_returncode=2,
                final_disposition_sha256=driver.sha(h.out / 'final_disposition_01/results.json')))
            artifact.write_text('{"changed": true}', encoding='utf-8')
            h.clone('close')(pin)
            result = driver.sealed(h.out / 'final_execution_receipt_01/results.json')
            self.assertFalse(result['qualified']); self.assertFalse(result['closure_complete'])
            self.assertTrue(any(e['stage'] == 'immutable_final_or_ledger' for e in result['closure_errors']))

    def test_extra_native_artifact_after_final_inventory_blocks_closure(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-extra-native-') as tmp:
            h = Harness(Path(tmp)); pin = self.close_fixture(h)
            final = dict(passed=False, qualification_passed=False, design_sha256=driver.sha(h.plan),
                artifacts=h.artifacts(), ledger={'synthetic': 0})
            driver.seal(h.out / 'final_disposition_01', final)
            driver.seal(h.out / 'supervisor/completion_01', dict(passed=False,
                held_design_sha256=driver.sha(h.plan),
                directly_observed_owner_exit_sha256=driver.sha(h.out / 'owner/exit.json'),
                directly_observed_owner_returncode=2,
                final_disposition_sha256=driver.sha(h.out / 'final_disposition_01/results.json')))
            driver.commit(h.out / 'reservations/000002.json', {'forbidden_extra_native_reservation': True})
            h.clone('close')(pin)
            result = driver.sealed(h.out / 'final_execution_receipt_01/results.json')
            self.assertFalse(result['qualified']); self.assertFalse(result['closure_complete'])
            self.assertTrue(any(e['stage'] == 'immutable_final_or_ledger' for e in result['closure_errors']))

    def test_changed_ledger_after_original_final_blocks_closure(self):
        with tempfile.TemporaryDirectory(prefix='p1-launcher-extra-ledger-') as tmp:
            h = Harness(Path(tmp)); pin = self.close_fixture(h)
            final = dict(passed=False, qualification_passed=False, design_sha256=driver.sha(h.plan),
                artifacts=h.artifacts(), ledger={'synthetic': 0})
            driver.seal(h.out / 'final_disposition_01', final)
            driver.seal(h.out / 'supervisor/completion_01', dict(passed=False,
                held_design_sha256=driver.sha(h.plan),
                directly_observed_owner_exit_sha256=driver.sha(h.out / 'owner/exit.json'),
                directly_observed_owner_returncode=2,
                final_disposition_sha256=driver.sha(h.out / 'final_disposition_01/results.json')))
            h.run.ledger = lambda: {'synthetic': 1}
            h.clone('close')(pin)
            result = driver.sealed(h.out / 'final_execution_receipt_01/results.json')
            self.assertFalse(result['qualified']); self.assertFalse(result['closure_complete'])
            self.assertTrue(any(e['stage'] == 'immutable_final_or_ledger' for e in result['closure_errors']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
