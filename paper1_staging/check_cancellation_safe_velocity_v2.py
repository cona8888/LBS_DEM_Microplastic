"""Source-extracted original outer/observer controls with FAKE mechanics only.

No engine import, native contact function, warm, process, transport or authority.
"""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace, FunctionType
import ast
import copy
import importlib.util
import inspect
import json
import math
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'paper1_staging/cancellation_safe_velocity_v2.py'
spec = importlib.util.spec_from_file_location('cancellation_safe_velocity_v2', PATH)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def extracted(relative, names, namespace):
    tree = ast.parse((ROOT / relative).read_text(encoding='utf-8'))
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == set(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(ROOT / relative), 'exec'), namespace)
    return namespace


def full_module_functions(relative, names, namespace):
    # No module exec/imports: bind selected function CodeTypes from the whole
    # pinned module compiler context, including imported-module call opcodes.
    path = ROOT / relative
    source = path.read_text(encoding='utf-8')
    code = compile(source, str(path), 'exec', dont_inherit=True)
    tree = ast.parse(source)
    for name in names:
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        codes = [c for c in code.co_consts if inspect.iscode(c) and c.co_name == name]
        assert len(nodes) == len(codes) == 1
        defaults = tuple(ast.literal_eval(x) for x in nodes[0].args.defaults) or None
        fn = FunctionType(codes[0], namespace, name, defaults)
        for decorator in reversed(nodes[0].decorator_list):
            assert isinstance(decorator, ast.Name) and decorator.id == 'contextmanager'
            fn = namespace['contextmanager'](fn)
        namespace[name] = fn
    return namespace


def fixture(solver_error=False):
    calls = []
    geometry_ns = dict(np=np)
    extracted('stage37_staging/transport_contact.py', ['finite', 'unit', 'contact_frame'], geometry_ns)
    model = SimpleNamespace(contact_frame=geometry_ns['contact_frame'])
    geom_ns = dict(np=np, contact_model=model)
    extracted('stage41_staging/inertial_contact_cold_optimized_v1.py', ['_prepare_geometry'], geom_ns)

    def fake_solver(v, M, J, g, dt, mu, tol, maxiter):
        calls.append(dict(v=np.array(v), M=np.array(M), dt=dt))
        if solver_error:
            raise RuntimeError('FAKE map failure')
        return np.array(v), dict(iterations=0, residual=0., force_residual=0., dissipation=0.,
                                 reactions=np.zeros(len(J)).tolist(), solver='FAKE mechanics only')

    stage41 = SimpleNamespace(_prepare_geometry=geom_ns['_prepare_geometry'], _solve_prepared=fake_solver)
    finite_re = SimpleNamespace(reynolds_number=lambda *args: 0., inertial_multiplier=lambda *args: 1.)
    outer_ns = dict(np=np, stage41=stage41, finite_re=finite_re, CONTACT_ITERATION_CEILING=25000)
    extracted('stage42_staging/inertial_contact_robust_v1.py', ['inertial_contact_step'], outer_ns)
    stage42 = SimpleNamespace(inertial_contact_step=outer_ns['inertial_contact_step'])
    backend = SimpleNamespace(stage42=stage42, inertial_contact_step=lambda *a, **k: stage42.inertial_contact_step(*a, **k))
    old = SimpleNamespace(fast=SimpleNamespace(attempts=[]), capture=SimpleNamespace(records=[]))
    observation_ns = dict(np=np, ast=ast, copy=copy, inspect=inspect, hashlib=m.hashlib, Path=Path,
                          __file__=str(ROOT / 'stage189_staging/contact_trial_trace_v1.py'),
                          contextmanager=contextmanager, backend=backend, old=old, _active=False,
                          SCHEMA='stage189-explicit-inner-trial-v1')
    full_module_functions('stage189_staging/contact_trial_trace_v1.py', ['clone_step', 'plain', 'scope'], observation_ns)

    class FakeCycle:
        def __init__(self, epoch): self.records = []
        def observe(self, observer, solver, index, *args, **kwargs):
            answer = observer(solver, index, *args, **kwargs)
            self.records.append(dict(inner_index=index, map_output=m.plain(answer[0]), health=m.plain(answer[1]),
                                     canonical_selected=False, cycle_detected=False))
            return answer

    core = SimpleNamespace(Cycle=FakeCycle)
    prior = SimpleNamespace(JOB=SimpleNamespace(observer=SimpleNamespace(backend=backend)))
    guard_ns = dict(core=core, prior=prior, require=m.need, contextmanager=contextmanager, FunctionType=FunctionType)
    full_module_functions('stage243_staging/per_pose_guard_v1.py', ['scope'], guard_ns)
    return SimpleNamespace(stage42=stage42, backend=backend, calls=calls, finite_re=finite_re,
                           observer=observation_ns['scope'], guard=guard_ns['scope'])


def args(h=.01, old=None, contacts=None):
    return [np.asarray(old if old is not None else [1., 0, 0, 0, 0, 0]), np.zeros(6), np.zeros(6),
            np.eye(6)*1000, np.zeros((6, 6)), np.eye(6), contacts or [], .0002, h, .3, 1000., .001, .0001, .8]


def physical(item):
    # This is a MOCK physical auditor, deliberately not a native qualification.
    assert item['health']['solver'] == 'FAKE mechanics only'
    assert np.array_equal(item['velocity'], item['vfree'])
    assert not np.asarray(item['health']['reactions']).any()


class Checks(unittest.TestCase):
    def call(self, enabled, arguments=None, before=None, after=None, solver_error=False):
        f = fixture(solver_error)
        original = f.stage42.inertial_contact_step
        journal = trace = None; error = None; answer = None
        with f.observer(None, True) as trace:
            with f.guard(trace, 1e30):
                guarded = f.stage42.inertial_contact_step
                with m.scope(f.stage42, trace, enabled, before_inner=before, after_inner=after) as journal:
                    try: answer = f.backend.inertial_contact_step(*(arguments or args()))
                    except Exception as e: error = e
                self.assertIs(f.stage42.inertial_contact_step, guarded)
        self.assertIs(f.stage42.inertial_contact_step, original)
        self.assertTrue(journal['scope_restored'])
        return f, journal, trace, answer, error

    def audit(self, f, journal, trace):
        return m.audit_journal(journal, reynolds_number=f.finite_re.reynolds_number,
                               inertial_multiplier=f.finite_re.inertial_multiplier,
                               physical_audit=physical, original_trace=trace)

    def test_source_pins_and_no_engine_import(self):
        self.assertEqual(len(m.source_pins()), 6)
        names = {n.names[0].name for n in ast.walk(ast.parse(PATH.read_text())) if isinstance(n, ast.Import)}
        self.assertFalse(any('stage' in n or 'engine' in n for n in names))

    def test_disabled_code_and_bits_match_actual_original(self):
        f = fixture()
        expected = f.stage42.inertial_contact_step(*args())
        f, journal, trace, answer, error = self.call(False)
        self.assertIsNone(error)
        self.assertTrue(np.array_equal(expected[0], answer[0])); self.assertEqual(expected[1], answer[1])
        self.assertTrue(journal['source_proof']['inactive_code_object_identical'])
        self.assertEqual(self.audit(f, journal, trace)['increment_inner_maps'], 0)

    def test_enabled_inactive_keeps_exact_legacy_object(self):
        legacy = np.zeros(6)
        result, log = m.choose_velocity(legacy, legacy, legacy, legacy, np.eye(6), np.zeros((6,6)), np.eye(6), .01, np.eye(6))
        self.assertIs(result, legacy); self.assertEqual(log['mode'], 'legacy_exact')
        f, journal, trace, answer, error = self.call(True, args(old=np.zeros(6)))
        self.assertIsNone(error); self.audit(f, journal, trace)

    def test_enabled_normal_branch_old_bits_and_complete_no_route_journal(self):
        _, a, _, answer_a, _ = self.call(False)
        f, b, trace, answer_b, error = self.call(True)
        self.assertIsNone(error); self.assertTrue(np.array_equal(answer_a[0], answer_b[0]))
        self.assertEqual(trace['detailed_trials'], [])
        self.assertEqual(len(b['outer_calls'][0]['inner_systems']), 2)
        self.assertEqual(self.audit(f, b, trace)['complete_inner_maps'], 2)

    def test_active_representation_uses_same_compliance_no_new_inverse(self):
        h = 2.2e-14; old = np.array([.0036452523104887787, 0, 0, 0, 0, 0])
        D=np.eye(6)*1000; M=np.eye(6); C=np.linalg.inv(M/h+D); z=np.zeros(6)
        legacy = C @ (M@old/h)
        result, log = m.choose_velocity(legacy, old, z, z, D, np.zeros((6,6)), M, h, C)
        self.assertGreater(log['legacy_unconstrained_momentum_residual'], 1e-8)
        self.assertEqual(log['mode'], 'same_compliance_increment')
        self.assertTrue(np.array_equal(result, old+C@(D@(z-old))))
        source = ast.parse(inspect.getsource(m.choose_velocity))
        self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr in ('inv','solve') for n in ast.walk(source)))

    def test_tiny_step_no_lattice_waiver_final_gate_still_negative(self):
        f, journal, trace, _, error = self.call(True, args(h=2.2e-14, old=[.0036452523104887787,0,0,0,0,0]))
        self.assertIn('inertial momentum closure failed', str(error))
        audit = self.audit(f, journal, trace)
        self.assertEqual(audit['original_negative_outer_calls'], 1)
        self.assertGreater(audit['final_momentum_residuals'][0], 1e-8)
        self.assertFalse(audit['full_trajectory_admission'])

    def test_budget_hook_before_original_map_and_complete_negative(self):
        entered = []; exited = []
        def before(item):
            entered.append(item['inner_index'])
            raise RuntimeError('MOCK primitive budget exhausted')
        f,journal,trace,_,error=self.call(True,before=before,after=lambda item:exited.append(item['observer_entered']))
        self.assertIn('budget exhausted',str(error)); self.assertEqual(f.calls,[])
        self.assertEqual(entered,[0]); self.assertEqual(exited,[False])
        self.assertFalse(journal['outer_calls'][0]['inner_systems'][0]['observer_entered'])
        with self.assertRaises(RuntimeError): self.audit(f,journal,trace)

    def test_callbacks_count_every_map_including_fake_reuse(self):
        before=[];after=[]
        f,j,t,a,e=self.call(True,before=lambda x:before.append(x['inner_index']),after=lambda x:after.append(x['returned']))
        self.assertEqual(before,[0,1]);self.assertEqual(after,[True,True]);self.assertEqual(len(f.calls),2)

    def test_solver_failure_restores_and_does_not_claim_complete(self):
        f,j,t,a,e=self.call(True,solver_error=True)
        self.assertIn('FAKE map failure',str(e)); self.assertTrue(j['outer_calls'][0]['inner_systems'][0]['observer_entered'])
        with self.assertRaises(RuntimeError):self.audit(f,j,t)

    def test_nonfinite_rejected_before_solver(self):
        bad=args();bad[0][0]=float('nan')
        f,j,t,a,e=self.call(True,bad)
        self.assertIn('Nonfinite',str(e)); self.assertEqual(f.calls,[])

    def test_observer_order_and_original_code_guard(self):
        f=fixture()
        with self.assertRaises(RuntimeError):
            with m.scope(f.stage42,{},True):pass
        with f.observer(None,True) as trace:
            with f.guard(trace,1e30):
                old=f.stage42.inertial_contact_step
                f.stage42.inertial_contact_step=lambda *a:None
                try:
                    with self.assertRaises(Exception):
                        with m.scope(f.stage42,trace,True):pass
                finally:f.stage42.inertial_contact_step=old

    def test_nested_scope_and_tampered_binding_fail_closed(self):
        f=fixture()
        with f.observer(None,True) as trace:
            with f.guard(trace,1e30):
                with m.scope(f.stage42,trace,False):
                    with self.assertRaises(RuntimeError):
                        with m.scope(f.stage42,trace,False):pass
                original=f.stage42.inertial_contact_step
                with self.assertRaises(RuntimeError):
                    with m.scope(f.stage42,trace,True) as journal:
                        f.stage42.inertial_contact_step=lambda *a:None
                self.assertIs(f.stage42.inertial_contact_step,original)
                self.assertFalse(journal['scope_restored'])

    def test_independent_auditor_rejects_changed_choice_q_and_final_gate(self):
        f,j,t,a,e=self.call(True)
        for mutation in ('choice','velocity','health','guard'):
            altered=copy.deepcopy(j)
            if mutation=='choice':altered['outer_calls'][0]['inner_systems'][0]['selection']['mode']='same_compliance_increment'
            elif mutation=='velocity':altered['outer_calls'][0]['inner_systems'][0]['vfree'][0]+=1e-12
            elif mutation=='health':altered['outer_calls'][0]['health']['momentum_residual']=.1
            else:altered['outer_calls'][0]['inner_systems'][0]['maxiter']=24999
            with self.assertRaises((RuntimeError,AssertionError)):self.audit(f,altered,t)

    def test_json_roundtrip_and_independent_audit_has_no_producer_call(self):
        f,j,t,a,e=self.call(True)
        self.audit(f,json.loads(json.dumps(j)),json.loads(json.dumps(t)))
        text=inspect.getsource(m.audit_journal)
        self.assertNotIn('choose_velocity(',text)

    def test_contact_geometry_actual_observer_and_original_physics_callback(self):
        arguments=args(contacts=[[15, .01, [1., 0., 0.], [.00002, .00003, 0.]]])
        f,j,t,a,e=self.call(True,arguments)
        self.assertIsNone(e)
        visited=[]
        def check_contact(item):
            physical(item); self.assertTrue(item['accepted'])
            self.assertEqual(np.asarray(item['jacobian']).shape,(3,6))
            self.assertEqual(item['original_observer_item']['velocity'],item['velocity'])
            visited.append(item['inner_index'])
        result=m.audit_journal(j,reynolds_number=f.finite_re.reynolds_number,
                               inertial_multiplier=f.finite_re.inertial_multiplier,
                               physical_audit=check_contact,original_trace=t)
        self.assertEqual(visited,[0,1]);self.assertEqual(result['successful_outer_calls'],1)
        altered=copy.deepcopy(j);altered['outer_calls'][0]['inner_systems'][0]['jacobian'][0][0]+=1e-9
        with self.assertRaises(RuntimeError):self.audit(f,altered,t)

    def test_two_outer_calls_fresh_guard_no_selection_or_journal_state_leak(self):
        f=fixture();before=[]
        with f.observer(None,True) as trace:
            with f.guard(trace,1e30):
                with m.scope(f.stage42,trace,True,before_inner=lambda x:before.append((x['outer_index'],x['inner_index']))) as journal:
                    first=f.backend.inertial_contact_step(*args())
                    second=f.backend.inertial_contact_step(*args())
        self.assertEqual(before,[(0,0),(0,1),(1,0),(1,1)])
        self.assertTrue(np.array_equal(first[0],second[0]))
        self.assertEqual([x['trial_index'] for x in trace['cycle_guard_trials']],[0,1])
        self.assertEqual(self.audit(f,journal,trace)['successful_outer_calls'],2)

    def test_all_ast_except_qfree_and_observer_is_original(self):
        f=fixture()
        with f.observer(None,True) as trace:
            with f.guard(trace,1e30):
                old=f.stage42.inertial_contact_step
                patched,proof=m._clone(old,lambda *a:None,lambda *a:None,True)
                self.assertEqual(proof['qfree_expression_wrappers'],1)
                self.assertEqual(proof['other_numerical_ast_edits'],0)
                # Source assertions in _clone reconstruct the entire original AST.
                self.assertEqual(old.__defaults__,patched.__defaults__)


class FullModuleContextRegression(unittest.TestCase):
    def old_helper(self):
        path = ROOT / 'paper1_staging/cancellation_safe_velocity_v1.py'
        self.assertEqual(m.hashlib.sha256(path.read_bytes()).hexdigest(),
                         '79a42add87ee7fb8d8a483879f5cc5905fa6d4a390ee8786e06442acf3d190c3')
        spec = importlib.util.spec_from_file_location('_frozen_v1_context_negative', path)
        old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
        return old

    def test_old_isolated_context_negative_and_full_context_exact(self):
        old = self.old_helper()
        relative = 'stage243_staging/per_pose_guard_v1.py'
        path = ROOT / relative
        module = compile(path.read_text(encoding='utf-8'), str(path), 'exec', dont_inherit=True)
        scope = next(c for c in module.co_consts if inspect.iscode(c) and c.co_name == 'scope')
        actual = next(c for c in scope.co_consts if inspect.iscode(c) and c.co_name == 'wrapped')
        prior = old._nested_code(relative, 'scope', 'wrapped')
        expected = m._nested_code(relative, 'scope', 'wrapped')
        self.assertEqual(actual.co_flags, prior.co_flags)
        self.assertEqual(actual.co_consts, prior.co_consts)
        self.assertNotEqual(actual.co_code, prior.co_code)
        self.assertNotEqual(old._code_shape(actual), old._code_shape(prior))
        self.assertEqual(m._code_shape(actual), m._code_shape(expected))
        # co_flags remain part of the unmodified strict assertion, never masked.
        self.assertEqual(ast.dump(ast.parse(inspect.getsource(old._code_shape)), include_attributes=False),
                         ast.dump(ast.parse(inspect.getsource(m._code_shape)), include_attributes=False))

    def test_real_full_context_fake_scope_reproduces_old_negative_then_new_pass(self):
        old = self.old_helper(); f = fixture()
        with f.observer(None, True) as trace:
            with f.guard(trace, 1e30):
                before = f.stage42.inertial_contact_step
                with self.assertRaisesRegex(RuntimeError, 'Pinned per-pose guard callback required'):
                    with old.scope(f.stage42, trace, True): pass
                self.assertEqual(f.calls, [])
                self.assertIs(f.stage42.inertial_contact_step, before)
                with m.scope(f.stage42, trace, True) as journal:
                    answer = f.backend.inertial_contact_step(*args())
        self.assertTrue(journal['scope_restored'])
        self.assertEqual(len(f.calls), 2)
        self.assertTrue(np.isfinite(answer[0]).all())
        self.assertEqual(m.audit_journal(journal, reynolds_number=f.finite_re.reynolds_number,
            inertial_multiplier=f.finite_re.inertial_multiplier, physical_audit=physical,
            original_trace=trace)['successful_outer_calls'], 1)

    def test_module_compilation_never_executes_imports_or_toplevel(self):
        before = set(sys.modules)
        for relative, name in [('stage243_staging/per_pose_guard_v1.py', 'wrapped'),
                               ('stage189_staging/contact_trial_trace_v1.py', 'observe_inner')]:
            result = m._nested_code(relative, 'scope', name)
            self.assertTrue(inspect.iscode(result))
        self.assertEqual(set(sys.modules), before)
        tree = ast.parse(inspect.getsource(m._nested_code))
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            and n.func.id in ('exec', 'eval', '__import__') for n in ast.walk(tree)))
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                           and n.func.id == 'compile' and any(k.arg == 'dont_inherit'
                           and isinstance(k.value, ast.Constant) and k.value.value is True
                           for k in n.keywords) for n in ast.walk(tree)))

    def test_all_other_policy_capture_and_audit_functions_identical(self):
        old = self.old_helper()
        a = ast.parse(Path(old.__file__).read_text(encoding='utf-8'))
        b = ast.parse(PATH.read_text(encoding='utf-8'))
        af = {n.name: ast.dump(n, include_attributes=False) for n in a.body if isinstance(n, ast.FunctionDef)}
        bf = {n.name: ast.dump(n, include_attributes=False) for n in b.body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(set(af), set(bf))
        self.assertEqual({k for k in af if af[k] != bf[k]}, {'_nested_code'})
        self.assertEqual(old.SOURCE_PINS, m.SOURCE_PINS)
        self.assertEqual(old.GATE, m.GATE)
        self.assertEqual(old.POLICY, m.POLICY)


if __name__ == '__main__':
    unittest.main(verbosity=2)
