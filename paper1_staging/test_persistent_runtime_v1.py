"""AST-only administration fixtures; no campaign/runtime import or dispatch."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
import ast
import copy
import hashlib
import json
import tempfile
import unittest

SOURCE = Path(__file__).with_name('run_persistent_common_state_v1.py')
OLD = Path(__file__).with_name('run_support_common_state_v3.py')


def fixture():
    tree = ast.parse(SOURCE.read_text(encoding='utf8'))
    root = SOURCE.resolve().parents[1]
    ns = dict(copy=copy, ModuleType=ModuleType, FunctionType=FunctionType, Path=Path,
              datetime=datetime, timezone=timezone, timedelta=timedelta, ROOT=root, SELF=SOURCE.resolve())
    constants = ('DEADLINE', 'STEP_CAP', 'CALL_CAP', 'LOCAL_STEPS', 'LOCAL_CALLS', 'PRIOR_STEPS', 'PRIOR_CALLS',
        'CASE_STEPS', 'CASE_CALLS', 'SHARED_STEPS', 'SHARED_CALLS', 'PRIOR_SHARED_STEPS', 'PRIOR_SHARED_CALLS',
        'PRIOR_DIAGNOSTIC_STEPS', 'PRIOR_DIAGNOSTIC_CALLS', 'TOTAL_DIAGNOSTIC_STEPS', 'TOTAL_DIAGNOSTIC_CALLS',
        'PRIOR_NUMERICAL_WINDOWS', 'MAXIMUM_TOTAL_NUMERICAL_WINDOWS', 'PREPARATION_NAME', 'FROZEN_SHA', 'REUSED')
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in constants:
                ns[target.id] = ast.literal_eval(node.value)
            elif isinstance(target, ast.Tuple) and all(isinstance(x, ast.Name) and x.id in constants for x in target.elts):
                ns.update(zip((x.id for x in target.elts), ast.literal_eval(node.value)))
    designs = root / 'paper1_designs/first_persistent_common_state_20261017'
    ns.update(DESIGNS=designs, OUT=root / 'paper1_runs/first_persistent_common_state_20261017',
        PLAN=designs/'design_01.json', AUTH=designs/'authorization_01.json', PHYSICAL=designs/'physical_cases_01.json',
        PROPOSAL=designs/'proposal_01.json', APPROVAL=designs/'permission_01/results.json',
        PREPARED=designs/'preparation_01/results.json', PREPARATION_EXIT=designs/'preparation_execution_receipt_01/results.json')
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('need', 'approval_scope', 'validate_approval', 'build_private_namespace', 'authorize', 'controls')]
    selected += [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'LazyPreparation']
    ns['importlib'] = SimpleNamespace(import_module=lambda name: (_ for _ in ()).throw(AssertionError('Lazy prep must not import during fixtures')))
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), '<pure-persistent-administration>', 'exec'), ns)
    old_tree = ast.parse(OLD.read_text(encoding='utf8'))
    old = ModuleType('fixture_original_frozen_runner')
    old.__dict__.update({key: ns[key] for key in constants if key in ns and key != 'REUSED'})
    old.__dict__.update(dict(datetime=datetime, timezone=timezone, timedelta=timedelta,
        PRIOR_STEPS=10184681, PRIOR_CALLS=2125, PRIOR_SHARED_STEPS=4536769, PRIOR_SHARED_CALLS=955,
        TOTAL_DIAGNOSTIC_STEPS=70008, TOTAL_DIAGNOSTIC_CALLS=34,
        OUT=root/'fixture_old_out', SELF=OLD.resolve(), PLAN=root/'fixture_old_plan', CONFIG={'enabled': True, 'policy': {'fixture': 16}},
        preparation=object(), sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()))
    functions = [node for node in old_tree.body if isinstance(node, ast.FunctionDef)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), '<original-frozen-functions-only>', 'exec'), vars(old))
    old.__file__ = str(OLD.resolve())
    ns['frozen'] = old
    ns['private'] = ns['build_private_namespace'](old)
    return ns


def permission(ns):
    return dict(passed=True, proposal_sha256='a'*64, actual_human_reply='allowed and next',
        direct_user_instruction_reference='Synthetic direct-user provenance', human_reviewed_exact_proposal=False,
        exact_bounded_allocations_selected_by_agent=True, preparation_execution_receipt_sha256='b'*64,
        scope=ns['approval_scope']())


class PersistentAdministration(unittest.TestCase):
    def test_actual_controls_private_code_graph_and_rejections(self):
        ns = fixture()
        result = ns['controls']()
        self.assertTrue(result['passed'])
        self.assertEqual(result['mocked_rejections'], 12)
        self.assertEqual(result['zero_native_solver_calls'], 0)
        self.assertEqual(result['zero_transport_steps'], 0)

    def test_private_clones_do_not_mutate_original_globals_or_defaults(self):
        ns = fixture(); old, new = ns['frozen'], ns['private']
        for name in ns['REUSED']:
            self.assertIs(getattr(new, name).__code__, getattr(old, name).__code__)
            self.assertIs(getattr(new, name).__globals__, vars(new))
        original_plan = old.PLAN
        new.PLAN = Path('fixture-only-new-context')
        new.CONFIG['policy']['fixture'] = 32
        new.budget_guard.__kwdefaults__['prior_case_saved'] += 1
        self.assertEqual(old.PLAN, original_plan)
        self.assertEqual(old.CONFIG['policy']['fixture'], 16)
        self.assertEqual(old.budget_guard.__kwdefaults__['prior_case_saved'], 10184681)
        self.assertIs(new.run.__globals__['invoke'], new.invoke)
        self.assertIs(new.child.__globals__['SELF'], ns['SELF'])

    def test_updated_keyword_baselines_are_used_by_actual_budget_guard(self):
        for ceiling, baseline, amount in (
            ('CASE_STEPS', 'PRIOR_STEPS', 'STEP_CAP'), ('CASE_CALLS', 'PRIOR_CALLS', 'CALL_CAP'),
            ('SHARED_STEPS', 'PRIOR_SHARED_STEPS', 'STEP_CAP'), ('SHARED_CALLS', 'PRIOR_SHARED_CALLS', 'CALL_CAP')):
            with self.subTest(ceiling=ceiling):
                ns = fixture(); new = ns['private']
                new.budget_guard(ns['STEP_CAP'], ns['CALL_CAP'])
                setattr(new, ceiling, ns[baseline] + ns[amount] - 1)
                with self.assertRaises(RuntimeError):
                    new.budget_guard(ns['STEP_CAP'], ns['CALL_CAP'])

    def test_permission_does_not_fabricate_human_review_or_accept_old_scope(self):
        ns = fixture(); good = permission(ns)
        self.assertTrue(ns['validate_approval'](good, 'a'*64))
        for key, value in (('human_reviewed_exact_proposal', True),
                           ('exact_bounded_allocations_selected_by_agent', False),
                           ('actual_human_reply', 'Approve bounded diagnostic (Recommended)'),
                           ('direct_user_instruction_reference', '')):
            with self.subTest(key=key):
                bad = copy.deepcopy(good); bad[key] = value
                with self.assertRaises(RuntimeError): ns['validate_approval'](bad, 'a'*64)
        for key, value in (('maximum_diagnostic_integration_calls', 34),
                           ('maximum_discarded_diagnostic_steps', 70008),
                           ('maximum_total_numerical_windows', 3),
                           ('additional_independent_numerical_windows', True)):
            with self.subTest(scope_key=key):
                bad = copy.deepcopy(good); bad['scope'][key] = value
                with self.assertRaises(RuntimeError): ns['validate_approval'](bad, 'a'*64)

    def test_unpinned_or_false_permission_cannot_write_authority(self):
        ns = fixture()
        with tempfile.TemporaryDirectory(prefix='persistent-permission-') as temp:
            root = Path(temp); writes=[]
            approval = root/'permission.json'; approval.write_text(json.dumps({'passed': False}))
            proposal=root/'proposal.json'; proposal.write_text('{}')
            ns.update(PLAN=root/'design.json', AUTH=root/'authorization.json', OUT=root/'run', APPROVAL=approval, PROPOSAL=proposal)
            new=ns['private']
            new.s=SimpleNamespace(environment=lambda: None,
                fields=SimpleNamespace(sealed=lambda p: json.loads(Path(p).read_text())))
            new.commit=lambda *args: writes.append(args)
            for pin in (None, '0'*64, hashlib.sha256(approval.read_bytes()).hexdigest()):
                with self.subTest(pin=pin), self.assertRaises(RuntimeError): ns['authorize'](pin)
            self.assertEqual(writes, [])
            self.assertFalse(ns['PLAN'].exists() or ns['AUTH'].exists() or ns['OUT'].exists())

    def test_clock_is_new_bounded_window_inside_original_end(self):
        ns=fixture(); end=datetime.fromisoformat(ns['DEADLINE'])
        start=end-timedelta(minutes=45)
        cutoff, stopped=ns['private'].bounds(start)
        self.assertEqual(stopped,end)
        self.assertEqual(cutoff,end-timedelta(minutes=30))
        for bad in (end, end-timedelta(minutes=30), end+timedelta(seconds=1)):
            with self.subTest(start=bad), self.assertRaises(RuntimeError): ns['private'].bounds(bad)

    def test_pending_trigger_retains_original_stop_and_cli_has_no_default_dispatch(self):
        ns=fixture()
        self.assertEqual(ns['private'].activation_index([{'trigger_grain_ids': []}, {'trigger_grain_ids': [182]}]),1)
        tree=ast.parse(SOURCE.read_text())
        main=next(node for node in tree.body if isinstance(node,ast.If) and '__name__' in ast.unparse(node.test))
        text=ast.unparse(main)
        self.assertIn("raise SystemExit('Explicit controls",text)
        self.assertIn("len(sys.argv) == 3",text)
        self.assertNotIn('warm(',text)
        self.assertNotIn('configure(',text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
