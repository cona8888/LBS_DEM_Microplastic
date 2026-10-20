"""Fake-mechanics controls of the actual generated loop, never native solves.

This is an engineering fixture. Its artificial field/mass/force operator does
not validate the physical candidate or authorize any numerical experiment.
"""
from contextlib import contextmanager, ExitStack
from pathlib import Path
from types import SimpleNamespace, FunctionType
from datetime import datetime, timezone
import copy
import importlib
import json
import math
import sys
import time
import unittest
from unittest.mock import patch
import numpy as np
import ast,hashlib,inspect
from fractions import Fraction
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'paper1_staging'), str(ROOT / 'stage153_staging')]
import full_state_integration_adapter_v4 as a
import full_state_stepdoubling_v1 as p

class FakeCapture:

    @contextmanager
    def scope(self, role, before):
        self.role = role
        self.trace = dict(schema='fake-only', trial_inner_counts=[], trial_route_counts=[], cycle_guard_trials=[], detailed_trials=[])
        yield dict(contact_trial_trace=self.trace, normal_gap_operand_policy=dict(policy='fake-only', prepare_calls=[]), early_attempts=[], fallback_systems=[], repairs=[], stage119_repair_calls=[], certificates=[], sweep_certificates=[], backend_calls=[dict(enabled=True, backend='fake-only')])

class FakeBackend:

    def __init__(self, capture):
        self.value = False
        self.log = []
        self.capture = capture
        self.fail = None
        self.bearing = []
        self.finite_re = SimpleNamespace(prolate_sphericity=lambda *x: 1.0, reynolds_number=lambda *x: 0.0)

    def set_recovery_mode(self, value):
        self.value = bool(value)

    def recovery_mode(self):
        return self.value

    def stokes_generalized_resistance(self, *x):
        return np.eye(6)

    def generalized_mass_matrix(self, *x):
        return (np.eye(6), None)

    def inertial_contact_step(self, q, bg, body, resistance, lub, mass, active, ell, h, *rest):
        role = self.capture.role
        self.log.append((role, self.value, float(h)))
        self.capture.trace['trial_inner_counts'].append(1)
        self.capture.trace['trial_route_counts'].append([0, 0])
        self.capture.trace['cycle_guard_trials'].append(dict(trial_index=len(self.capture.trace['cycle_guard_trials']), records=[]))
        if self.fail == role:
            raise RuntimeError('fixture physical failure')
        self.value = role == 'C'
        candidate = (q / h + bg + body) / (1 / h + 1)
        return (candidate, dict(momentum_residual=0.0, contact=dict(residual=0.0, force_residual=0.0, iterations=1), reynolds=0.0, total_contact_iterations=1, load_bearing_grain_ids=list(self.bearing), reaction_world_by_grain={gid: [0.0, 0.0, 0.0] for gid in self.bearing}))

class FakeMonitor:

    def __init__(self, *args, **kwargs):
        self.anchor = None
        self.contact_ids = ()
        self.load_bearing_ids = ()
        self.age = 0.0

    def update(self, h, *args):
        self.age += h
        return dict(persistent_contact_observed=False)


def source_only_modal():
    """Literal source transforms in FAKE namespaces; no model import/solver."""
    paths=[ROOT/'stage119_staging/checkpoint_core_v3.py',ROOT/'stage151_staging/rigid_rotation_v1.py',ROOT/'stage153_staging/modal_rotation_dt_v1.py']
    for path in paths:
        expected=a.SOURCE_PINS[path.relative_to(ROOT).as_posix()]
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    core_source=paths[0].read_text();core_tree=ast.parse(core_source)
    fn=next(n for n in core_tree.body if isinstance(n,ast.FunctionDef) and n.name=='integrate')
    namespace=dict(np=np,copy=copy,json=json,hashlib=hashlib,time=time,math=math)
    exec(compile(ast.Module(body=[copy.deepcopy(fn)],type_ignores=[]),str(paths[0]),'exec'),namespace)
    core=SimpleNamespace(**namespace)
    binding_for=lambda binding,enabled:a.original_digest([binding,'source-fake-rigid']) if enabled else binding
    gyro_load=lambda *args:np.zeros(3)
    ns151=dict(ast=ast,inspect=inspect,core=core,binding_for=binding_for,gyro_load=gyro_load)
    make=next(n for n in ast.parse(paths[1].read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='make_integrate')
    exec(compile(ast.Module(body=[copy.deepcopy(make)],type_ignores=[]),str(paths[1]),'exec'),ns151)
    integrate,generated=ns151['make_integrate']()
    model=SimpleNamespace(original=SimpleNamespace(GENERATED_SOURCE=generated,INTEGRATE=integrate))
    ns153=dict(ast=ast,model=model,shortest_mode=lambda *args:1.)
    fn153=next(n for n in ast.parse(paths[2].read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='compile_candidate')
    exec(compile(ast.Module(body=[copy.deepcopy(fn153)],type_ignores=[]),str(paths[2]),'exec'),ns153)
    candidate,source=ns153['compile_candidate']()
    assert hashlib.sha256(source.encode()).hexdigest()=='e3aadaea70256c5c0cf54694c20abf691e18c376933b0a10a1d2a15107c7b16e'
    return SimpleNamespace(CANDIDATE=candidate,GENERATED_SOURCE=source)

def fake_original_selector(runtime):
    # Pinned original selector/compiler AST only; skip its MODEL imports.
    path=ROOT/'paper1_staging/contact_onset_timecap_v1.py';source=path.read_text();tree=ast.parse(source)
    names={'POLICY','SIGNATURE'};nodes=[]
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets):nodes.append(copy.deepcopy(node))
        elif isinstance(node,ast.FunctionDef) and node.name in {'select','compile_candidate'}:nodes.append(copy.deepcopy(node))
    fake_candidate=FunctionType(runtime.factory.__code__,runtime.provider['namespace']) if False else None
    # compile_candidate reads only original generated source+original function defaults/globals.
    ns=dict(ast=ast,copy=copy,hashlib=hashlib,np=np,Path=Path,__file__=str(path),
        modal=SimpleNamespace(GENERATED_SOURCE=runtime.provider['source'],CANDIDATE=source_only_modal().CANDIDATE))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return SimpleNamespace(**ns)

def make_runtime(horizon=0.08, cap=0.01, exit_at=None):
    modal = source_only_modal()
    capture = FakeCapture()
    backend = FakeBackend(capture)
    mechanics = SimpleNamespace(finite=lambda x: np.asarray(x, float), unit=lambda x: np.asarray(x, float) / np.linalg.norm(x), free_motion=lambda p, g, u, *rest: (np.r_[u, np.zeros(3)], None), advance_pose=lambda x, p, q, ell, h: (x + h * q[:3], p.copy()), linear_pose_exit_time=lambda x, p, q, ell, b, outlet, h: exit_at if exit_at is not None and exit_at < h else None)
    ns = dict(modal.CANDIDATE.__globals__)
    ns.update(np=np, copy=copy, json=json, time=time, math=math, inertial=backend, mechanics=mechanics, trap_event_v2=SimpleNamespace(TrapMonitor=FakeMonitor), geometry_tools=SimpleNamespace(swept_gap=lambda *args: 1.0), enrich=lambda geometry, contacts: [(*c,1.) if len(c)==4 else c for c in contacts], lubrication_matrix=lambda *args: (np.zeros((6, 6)), []), gyro_load=lambda *args: np.zeros(3), shortest_mode=lambda *args: 1.0)
    selector = SimpleNamespace(select=lambda base, near, q, ell, speed, untruncated_dt: (base, []))

    def assemble(*args):
        v = [None] * 14
        v[8] = cap
        return v
    provider = lambda gate: dict(source=modal.GENERATED_SOURCE, namespace=ns, selector=selector, capture=capture, assemble=assemble)
    spec = dict(config=dict(prolate_semiaxes_m=[1.0, 1.0, 1.0], dynamic_viscosity_Pa_s=1.0, particle_density_kg_m3=1.0, fluid_density_kg_m3=1.0, gravity_m_s2=[0.0, 0.0, 0.0], friction_coefficient=0.0, added_mass_fraction=0.0, target_mean_interstitial_velocity_m_s=1.0, trap=dict(dwell_time_s=1.0, speed_ratio=0.01, drift_over_minor_radius=0.01, absorbing=False), numerics=dict(displacement_fraction=1.0, angle_limit_rad=1.0, relaxation_fraction=1.0, max_dt_s=cap, reynolds_limit=3.0)), initial_state=dict(position_m=[0.0, 0.0, 0.0], orientation=[1.0, 0.0, 0.0], velocity_generalized=[0.0] * 6), field_metadata=dict(cell_length_m=100.0), horizon_s=horizon)
    field = SimpleNamespace(sample=lambda x: (np.array([1.0, 0.0, 0.0]), np.zeros((3, 3))))
    geometry = SimpleNamespace(r=np.array([1.0]), contacts=lambda *args: [])
    runtime = a.build_runtime(spec, 'fake-only-binding', field, geometry, dispatch_gate=lambda: dict(native_dispatch_authorized=True, simulation_cutoff_utc=datetime.fromtimestamp(time.time() + 100, timezone.utc).isoformat()), source_provider=provider)
    limits = p.Limits(1.0, 1.0, 1.0, 1.0, 8, 1e-12, '1' * 64)
    return (runtime, limits, backend)


def numeric_branches(packet):
    result=copy.deepcopy(packet['work_branches'])
    for branch in result:
        branch['compact_result'].pop('runtime_seconds',None)
    return result

def packet(runtime, limits, cp=None, rows=4, phase=None, work=30):
    return runtime.advance_packet(cp, limits, max_work_rows=work, pause_after_accepted_rows=rows, time_bound=time.time() + 10, record_id='fixture', pause_at_phase=phase, previous_packet_receipt_sha256='2' * 64 if cp is not None else None)


class NoModelImports:
    def find_spec(self,fullname,path=None,target=None):
        if fullname in {'modal_rotation_dt_v1','reconstruct_fixed_pose_v3','contact_onset_timecap_v1','rigid_rotation_v1','checkpoint_core_v3'}:
            raise AssertionError('Physical model import forbidden in source-only controls: '+fullname)
        return None
sys.meta_path.insert(0,NoModelImports())

class Controls(unittest.TestCase):

    def test_actual_loop_ast_and_three_branch_work(self):
        r, l, b = make_runtime()
        x = packet(r, l, rows=2)
        self.assertEqual(x['status'], 'paused_controller', x['error'])
        self.assertTrue(x['source_proof']['original_loop_ast_after_removing_two_hooks_identical'])
        self.assertEqual([z['role'] for z in x['work_branches']], ['C', 'F1', 'F2'])
        self.assertEqual(x['work_rows'], 3)
        self.assertEqual(len(x['accepted_rows']), 2)
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state_sha256'], a.original_digest(x['checkpoint']['physical_checkpoint']['state']))

    def test_serial_vs_even_split_complete_state(self):
        r, l, _ = make_runtime()
        serial = packet(r, l, rows=4)
        left = packet(r, l, rows=2)
        right = packet(r, l, a.controller_checkpoint(left), rows=2)
        self.assertEqual(a.trace_rows(serial), a.trace_rows(left) + a.trace_rows(right))
        self.assertEqual(a.numeric_restart_signature(serial), a.numeric_restart_signature(right))

    def test_all_between_branch_phases(self):
        for phase in ('C_done', 'F1_done', 'F2_done', 'decision_done'):
            r, l, _ = make_runtime()
            serial = packet(r, l, rows=2)
            left = packet(r, l, phase=phase, rows=2)
            self.assertEqual(len(left['accepted_rows']), 0, phase)
            right = packet(r, l, a.controller_checkpoint(left), rows=2)
            self.assertEqual(a.numeric_restart_signature(serial), a.numeric_restart_signature(right), phase)
            self.assertEqual(serial['work_rows'], left['work_rows'] + right['work_rows'])

    def test_odd_publication_only_after_decision(self):
        r, l, _ = make_runtime()
        serial = packet(r, l, rows=4)
        left = packet(r, l, rows=1)
        self.assertEqual(left['cursor_after']['phase'], 'publish_second_half')
        self.assertEqual(left['work_rows'], 3)
        right = packet(r, l, a.controller_checkpoint(left), rows=3)
        self.assertEqual(a.trace_rows(serial), a.trace_rows(left) + a.trace_rows(right))
        self.assertEqual(a.numeric_restart_signature(serial), a.numeric_restart_signature(right))

    def test_source_policy_and_old_bare_checkpoint_reject_before_force(self):
        r, l, b = make_runtime()
        old = dict(schema=1, state={}, contract='old', state_sha256='old')
        with self.assertRaises(a.Stop):
            packet(r, l, old)
        self.assertEqual(b.log, [])
        good = packet(r, l, rows=2)['checkpoint']
        good['policy_sha256'] = '3' * 64
        count = len(b.log)
        with self.assertRaises(a.Stop):
            packet(r, l, good)
        self.assertEqual(len(b.log), count)

    def test_coarse_recovery_never_leaks_into_first_half(self):
        r, l, b = make_runtime()
        x = packet(r, l, rows=2)
        self.assertEqual([(role, mode) for role, mode, _ in b.log], [('C', False), ('F1', False), ('F2', False)])

    def test_physical_failure_preserved_no_successor(self):
        r, l, b = make_runtime()
        b.fail = 'C'
        x = packet(r, l, rows=2)
        self.assertEqual(x['status'], 'negative')
        self.assertEqual(x['work_rows'], 1)
        self.assertEqual([z[0] for z in b.log], ['C'])
        self.assertEqual(x['accepted_rows'], [])
        self.assertEqual(a.packet_summary(x)['known_unaccepted_rows'], 1)

    def test_export_is_bounded_negative_without_extension(self):
        r, l, b = make_runtime(exit_at=0.001)
        x = packet(r, l, rows=2)
        self.assertEqual(x['status'], 'negative')
        self.assertEqual(x['accepted_rows'], [])
        self.assertEqual(x['work_branches'][0]['result_status'], 'full_window_exit')
        self.assertEqual(len(b.log), 1)

    def test_finite_work_limit_no_partial_production_pair(self):
        r, l, b = make_runtime()
        x = packet(r, l, rows=20, work=5)
        self.assertEqual(x['work_rows'], 3)
        self.assertEqual(len(b.log), 3)
        self.assertEqual(x['cursor_after']['phase'], 'idle')

    def test_history_roundtrip_and_original_sentinels(self):
        literal = [[0.0, 1.0, float('inf')], [1.0, 2.0, -float('inf')]]
        store = a.HistoryStore(literal)
        h = store.start('4' * 64)
        fork = h.fork()
        fork.append([2.0, 3.0])
        self.assertEqual(store.materialize(h.node), literal)
        self.assertEqual(store.materialize(fork.node), literal + [[2.0, 3.0]])
        self.assertEqual(a.token(float('inf')), a.token(float('inf')))
        with self.assertRaises(a.Stop):
            a.token(float('nan'))

    def test_nonzero_literal_midpoint_and_exact_full_horizon(self):
        for t in (0.15, 0.15358074327919755, 0.4, 0.9364396280429766):
            z = a.choose_clock_interval(t, 3.108865289e-07, 1e-15, 8)
            self.assertEqual(z['h_s'], 3.108865289e-07)
            self.assertEqual(t + z['first_interval_s'], z['midpoint_time_s'])
            self.assertEqual(z['midpoint_time_s'] + z['second_interval_s'], z['end_time_s'])
        r, l, _ = make_runtime(horizon=0.025)
        x = packet(r, l, rows=100, work=30)
        self.assertEqual(x['status'], 'present_at_horizon', x['error'])
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state']['t'], 0.025)

    def test_administrative_time_pause_does_not_clip_full_horizon(self):
        r, l, _ = make_runtime(horizon=0.08)
        x = r.advance_packet(None, l, max_work_rows=30, pause_after_time_s=0.015, time_bound=time.time() + 10, record_id='clock-pause')
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state']['t'], 0.02)
        self.assertEqual(x['cursor_after']['phase'], 'idle')
        self.assertEqual(x['work_rows'], 6)
        self.assertEqual(r.spec['horizon_s'], 0.08)

    def test_pure_policy_arithmetic_matches_compiled_bridge(self):
        limits = p.Limits(2.0, 0.01, 0.01, 0.01, 8, 1e-12, '1' * 64)

        def frame(i, parent, t, x, q):
            return dict(token=str(i) * 64, parent=parent, state=dict(t=t, x=[x, 0.0, 0.0], p=[1.0, 0.0, 0.0], q=[q, 0.0, 0.0, 0.0, 0.0, 0.0]))
        origin = frame(1, None, 0.4, 0.0, 0.0)
        coarse = frame(2, origin['token'], 0.4 + 0.01, 0.02, 0.03)
        first = frame(3, origin['token'], 0.4 + 0.01 / 2, 0.01, 0.015)
        second = frame(4, first['token'], 0.4 + 0.01, 0.021, 0.031)

        def endpoint(f):
            s = f['state']
            return p.Endpoint(s['t'], tuple(s['x']), tuple(s['p']), tuple(s['q']), f['token'], f['parent'] or '0' * 64, '5' * 64, '6' * 64, limits.numerical_binding, True)
        actual = a.decision_values(limits, origin, coarse, first, second, 0.01, 0.01, 0)
        expected = p.decide(limits, endpoint(origin), 0.01, 0.01, 0, endpoint(coarse), endpoint(first), endpoint(second))
        for key in ('action', 'position_defect_m', 'director_defect', 'velocity_defect_over_U', 'scaled_defect', 'next_h_s', 'next_halving_depth'):
            self.assertEqual(actual[key], getattr(expected, key))

    def test_accuracy_reject_work_retained_and_bounded(self):
        r, l, b = make_runtime()
        l = p.Limits(1.0, 1e-15, 1.0, 1e-15, 8, 1e-12, '1' * 64)
        x = packet(r, l, rows=2, work=12)
        self.assertEqual(x['work_rows'], 12)
        self.assertEqual(len(b.log), 12)
        self.assertEqual(x['accepted_rows'], [])
        self.assertTrue(all((t['decision']['action'] == 'discard_all_and_halve' for t in x['trials'])))
        self.assertEqual(a.packet_summary(x)['rejected_rows'], 12)
        self.assertEqual(x['cursor_after']['phase'], 'after_rejection')

    def test_real_original32_vs_compiled_C32_with_fake_mechanics(self):
        r, l, b = make_runtime(horizon=1.0)
        with patch.object(a, 'importlib', SimpleNamespace(import_module=lambda name: fake_original_selector(r) if name=='contact_onset_timecap_v1' else (_ for _ in ()).throw(AssertionError('No model import authorized')))):
            old = a._native_smoke(r, l, 'original', '7' * 64, 'fixture gaps', '8' * 64)
        compiled = a._native_smoke(r, l, 'compiled', '7' * 64, 'fixture gaps', '8' * 64)
        self.assertEqual(old['work_rows'], compiled['work_rows'])
        self.assertEqual(old['record']['rows'], compiled['record']['rows'])
        self.assertEqual(old['physical_checkpoint'], compiled['physical_checkpoint'])
        self.assertEqual(len(b.log), 64)
        self.assertTrue(all((v[0] == 'original_nominal' for v in b.log[:32])))
        self.assertTrue(all((v[0] == 'C' for v in b.log[32:])))
        self.assertNotIn('checkpoint', compiled)

    def test_explicit_prelude_counts_synthetic_kernels_and_restores(self):
        hot = SimpleNamespace(phase=lambda label: label)

        def warmup():
            return [hot.phase('false'), hot.phase('true')]
        hot.warmup = warmup

        def configured():
            hot.warmup()
        configured = FunctionType(configured.__code__, {**globals(), 'hot': hot}, configured.__name__, configured.__defaults__, configured.__closure__)
        backend = SimpleNamespace(inertial_contact_step=lambda: None)
        kernel = SimpleNamespace(warm=lambda: dict(contact_solver_calls=0, outer_calls=0), reset=lambda: None)
        candidate = SimpleNamespace(warm=lambda: None, __file__='fake-arithmetic')

        def outer():
            pass
        outer = FunctionType(outer.__code__, {'candidate': candidate})

        def execute():
            pass
        execute = FunctionType(execute.__code__, {'frozen': SimpleNamespace(execute=outer)})
        configure_path = SimpleNamespace(configure=configured)
        q = SimpleNamespace(reference=SimpleNamespace(JOB=SimpleNamespace(parent=SimpleNamespace(b=SimpleNamespace(old=SimpleNamespace(parent=configure_path))))), baseline=SimpleNamespace(execute=execute), job=SimpleNamespace(observer=SimpleNamespace(backend=backend)), kernel=kernel)
        real_import = a.importlib
        original_phase = hot.phase
        original_outer = backend.inertial_contact_step
        a.importlib = SimpleNamespace(import_module=lambda name: SimpleNamespace(s=SimpleNamespace(q=q)))
        try:
            report = a.native_stack_prelude(lambda: dict(native_dispatch_authorized=True, native_prelude_authorized=True, simulation_cutoff_utc=datetime.fromtimestamp(time.time() + 100, timezone.utc).isoformat()))
        finally:
            a.importlib = real_import
        self.assertEqual(report['nonadvancing_contact_kernel_invocations'], 2)
        self.assertEqual(report['saved_work_rows'], 0)
        self.assertEqual(report['target_outer_transport_calls'], 0)
        self.assertIs(hot.phase, original_phase)
        self.assertIs(backend.inertial_contact_step, original_outer)

    def test_half_state_cap_mismatch_is_retained_accuracy_rejection(self):
        r, l, b = make_runtime()
        r.selector.select = lambda base, near, q, ell, speed, untruncated_dt: (min(base, 0.001) if q[0] > 0 else base, [])
        x = packet(r, l, rows=2, work=30)
        self.assertEqual(x['status'], 'paused_controller', x['error'])
        rejects = [t for t in x['trials'] if t['decision']['action'] == 'discard_all_and_halve']
        self.assertGreater(len(rejects), 0)
        self.assertTrue(all((t['decision']['reason'] == 'cap_mismatch' and t['decision']['scaled_defect'] is None for t in rejects)))
        self.assertEqual(x['work_rows'], 3 * len(x['trials']))
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state']['rejected'], 0)

    def test_new_origin_can_recover_fresh_original_cap(self):
        r, l, _ = make_runtime()
        r.selector.select = lambda base, near, q, ell, speed, untruncated_dt: (min(base, 0.001) if q[0] == 0 else base, [])
        x = packet(r, l, rows=4, work=30)
        self.assertEqual([t['h_s'] for t in x['trials']], [0.001, 0.01])
        self.assertEqual([t['depth'] for t in x['trials']], [0, 0])

    def test_literal_supported_bearing_survives_dwell_reset(self):
        r, l, b = make_runtime()
        b.bearing = [15]
        r.geometry.contacts = lambda *args: [(15, 0.0, np.array([1.0, 0.0, 0.0]), np.zeros(3), 1.0)]
        x = packet(r, l, rows=2)
        self.assertEqual(x['status'], 'paused_controller', x['error'])
        self.assertTrue(all((row['supported_bearing_ids'] == [15] for row in x['accepted_rows'])))
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state']['monitor']['load_bearing_ids'], [])

    def test_v2_changes_only_scope_and_administrative_evidence(self):
        import ast
        old = ast.parse((ROOT / 'paper1_staging/full_state_integration_adapter_v1.py').read_text(encoding='utf-8'))
        new = ast.parse((ROOT / 'paper1_staging/full_state_integration_adapter_v2.py').read_text(encoding='utf-8'))

        def functions(tree):
            result = {}
            for item in tree.body:
                if isinstance(item, ast.FunctionDef):
                    result[item.name] = ast.dump(item, include_attributes=False)
                if isinstance(item, ast.ClassDef):
                    for value in item.body:
                        if isinstance(value, ast.FunctionDef):
                            result[item.name + '.' + value.name] = ast.dump(value, include_attributes=False)
            return result
        before, after = (functions(old), functions(new))
        changed = {name for name in before if before[name] != after[name]}
        self.assertEqual(changed, {'QualifiedCapture.packet_scope', 'Runtime.advance_packet', 'native_execution_scope', '_native_smoke'})
        for name in ('compile_machine', 'Runtime._advance_packet', 'Runtime.select_dt', 'Runtime._branch', 'Runtime.complete', 'decision_values', 'choose_clock_interval', 'original_inner_execution_scopes'):
            self.assertEqual(before[name], after[name], name)

    def test_v3_changes_only_factory_import_and_preserved_v2_pin(self):
        import ast
        before = ast.parse((ROOT / 'paper1_staging/full_state_integration_adapter_v2.py').read_text(encoding='utf-8'))
        after = ast.parse((ROOT / 'paper1_staging/full_state_integration_adapter_v3.py').read_text(encoding='utf-8'))
        left = {n.name: n for n in before.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        right = {n.name: n for n in after.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        changed = {name for name in left if ast.dump(left[name], include_attributes=False) != ast.dump(right[name], include_attributes=False)}
        self.assertEqual(changed, {'native_execution_scope'})

        def revert(node):
            if isinstance(node, ast.Constant) and node.value == 'audit_full_state_stepdoubling_v2':
                node.value = 'audit_full_state_stepdoubling_v1'
            for child in ast.iter_child_nodes(node):
                revert(child)
        revert(right['native_execution_scope'])
        self.assertEqual(ast.dump(left['native_execution_scope'], include_attributes=False), ast.dump(right['native_execution_scope'], include_attributes=False))
        self.assertEqual(a.SOURCE_PINS['paper1_staging/full_state_integration_adapter_v2.py'], 'eb8a6d0c87026303e9c0e8807c61ffd816a11aa1e0216c7cf527ebd9b49db252')
        self.assertEqual(set(left), set(right))

    def test_v4_physical_branch_accuracy_and_smoke_stencils_ast_identical(self):
        old=ast.parse((ROOT/'paper1_staging/full_state_integration_adapter_v3.py').read_text())
        new=ast.parse((ROOT/'paper1_staging/full_state_integration_adapter_v4.py').read_text())
        def functions(t):
            out={}
            for node in t.body:
                if isinstance(node,ast.FunctionDef):out[node.name]=ast.dump(node,include_attributes=False)
                if isinstance(node,ast.ClassDef):
                    for n in node.body:
                        if isinstance(n,ast.FunctionDef):out[node.name+'.'+n.name]=ast.dump(n,include_attributes=False)
            return out
        x,y=functions(old),functions(new)
        for name in ['compile_machine','Runtime.select_dt','Runtime._branch','Runtime.complete','Runtime.contact_call','Runtime.restore','Runtime.restore_machine' if 'Runtime.restore_machine' in x else 'Runtime.materialize','decision_values','choose_clock_interval','_native_smoke','original_inner_execution_scopes']:
            self.assertEqual(x[name],y[name],name)
        self.assertEqual(a.SOURCE_PINS['paper1_staging/full_state_integration_adapter_v3.py'],'56b71127ee9aeecf2926c58200d2edda1eb18e9969691df5b1de2bf1ba2f2217')

    def test_event_macro_only_preserves_raw_gap_and_original_branch_caps(self):
        r,l,backend=make_runtime();r.spec['initial_state']['velocity_generalized']=[-1.,0.,0.,0.,0.,0.]
        l=p.Limits(1.,1.,1.,.01,8,1e-12,'1'*64)
        near=[[15,.001,[1.,0.,0.],[0.,0.,0.]]];old=copy.deepcopy(near)
        r.geometry.contacts=lambda *args:copy.deepcopy(near)
        x=packet(r,l,rows=2)
        self.assertIsNone(x['error']);trial=x['trials'][0]
        self.assertEqual(trial['original_selected_cap_s'],.01)
        self.assertEqual(trial['macro_initial_cap_s'],.0005)
        self.assertEqual(trial['h_s'],.0005)
        self.assertEqual(near,old)
        self.assertTrue(all(b['cap_entries'][0]['original_selected_dt_s']==.01 for b in x['work_branches']))
        self.assertEqual(trial['event_cap_witness']['origin_state_token'],x['input_state_token'])
        self.assertEqual(trial['event_cap_witness']['selector_witness']['passes'][0]['contact_witnesses'][0]['raw_gap_m'],.001)
        self.assertEqual(x['event_policy_sha256'],a.EVENT_POLICY_SHA256)

    def test_event_witness_survives_serial_split_all_staged_and_odd(self):
        for phase in [None,'C_done','F1_done','F2_done','decision_done','odd']:
            r,l,_=make_runtime();r.spec['initial_state']['velocity_generalized']=[-1.,0.,0.,0.,0.,0.]
            l=p.Limits(1.,1.,1.,.01,8,1e-12,'1'*64);r.geometry.contacts=lambda *args:[[15,.001,[1.,0.,0.],[0.,0.,0.]]]
            serial=packet(r,l,rows=4)
            self.assertIsNone(serial['error'],phase)
            left=packet(r,l,rows=1 if phase=='odd' else 2,phase=None if phase in [None,'odd'] else phase)
            if phase is not None:
                self.assertEqual(left['cursor_after']['macro_initial_cap_s'],left['cursor_after']['event_cap_witness']['macro_initial_cap_s'])
            self.assertIsNone(left['error'],phase)
            remaining=4-len(left['accepted_rows'])
            right=packet(r,l,left['checkpoint'],rows=remaining)
            self.assertIsNone(right['error'],phase)
            self.assertEqual(a.trace_rows(serial),a.trace_rows(left)+a.trace_rows(right),phase)
            self.assertEqual(a.numeric_restart_signature(serial),a.numeric_restart_signature(right),phase)
            self.assertEqual(serial['work_rows'],left['work_rows']+right['work_rows'],phase)
            self.assertEqual(serial['trials'],left['trials']+right['trials'],phase)
            self.assertEqual(numeric_branches(serial),numeric_branches(left)+numeric_branches(right),phase)
            if phase not in [None,'odd']:
                self.assertEqual(right['cursor_before']['event_cap_witness'],left['cursor_after']['event_cap_witness'])

    def test_event_retries_never_reselect_or_release_same_origin(self):
        r,l,backend=make_runtime();r.spec['initial_state']['velocity_generalized']=[-1.,0.,0.,0.,0.,0.]
        r.geometry.contacts=lambda *args:[[15,.001,[1.,0.,0.],[0.,0.,0.]]]
        l=p.Limits(1.,1e-25,1.,1e-25,8,1e-12,'1'*64)
        calls=[];original=a.event_cap.select
        def observed(*args,**kwargs):calls.append(args);return original(*args,**kwargs)
        with patch.object(a.event_cap,'select',observed):x=packet(r,l,rows=2,work=12)
        self.assertEqual(len(calls),1)
        self.assertEqual(len(x['trials']),4)
        self.assertEqual([t['depth'] for t in x['trials']],[0,1,2,3])
        self.assertEqual([t['h_s'] for t in x['trials']],[.0005/2**d for d in range(4)])
        self.assertTrue(all(t['event_cap_witness']==x['trials'][0]['event_cap_witness'] for t in x['trials']))

    def test_event_small_proxy_release_and_old_envelopes_not_credit(self):
        r,l,_=make_runtime();r.spec['initial_state']['velocity_generalized']=[-1.,0.,0.,0.,0.,0.]
        l=p.Limits(1.,1.,1.,.01,8,1e-12,'1'*64);r.geometry.contacts=lambda *args:[[15,1e-8,[1.,0.,0.],[0.,0.,0.]]]
        x=packet(r,l,rows=2);self.assertEqual(x['trials'][0]['h_s'],.01)
        cp=copy.deepcopy(x['checkpoint']);cp['adapter_source_sha256']='56b71127ee9aeecf2926c58200d2edda1eb18e9969691df5b1de2bf1ba2f2217'
        with self.assertRaises(a.Stop):packet(r,l,cp)
        cp=copy.deepcopy(x['checkpoint']);cp['event_policy_sha256']='0'*64
        with self.assertRaises(a.Stop):packet(r,l,cp)

    def test_original_momentum_stencil_tiny_h_cancellation_counterexample(self):
        source=(ROOT/'stage42_staging/inertial_contact_robust_v1.py').read_text()
        self.assertIn('acceleration_load = mass @ (candidate - old_velocity) / dt',source)
        self.assertIn('momentum_residual > 1e-8',source)
        qold=.0036452523104887787;m=1.;drag=1000.
        for h in [2.2e-14,1.1e-14]:
            # Positive scalar frozen-drag free-flight limit, no native call.
            q=(1/(m/h+drag))*(m*qold/h)
            accel=m*(q-qold)/h;load=drag*q
            residual=abs(accel+load)/max(abs(accel),abs(load))
            self.assertGreater(residual,1e-8)
            qstar=Fraction(qold)/(1+Fraction(h)*Fraction(drag))
            near=float(qstar);neighbors=[math.nextafter(near,-math.inf),near,math.nextafter(near,math.inf)]
            exact=[]
            for candidate in neighbors:
                accel_exact=Fraction(m)*(Fraction(candidate)-Fraction(qold))/Fraction(h)
                load_exact=Fraction(drag)*Fraction(candidate)
                exact.append(abs(accel_exact+load_exact)/max(abs(accel_exact),abs(load_exact)))
            self.assertGreater(float(min(exact)),1e-8)
        # This counterexample is not an actual6D target failure or a residual waiver.



    def test_event_below_minimum_fails_before_fake_force_with_witness(self):
        r,l,backend=make_runtime();r.spec['initial_state']['velocity_generalized']=[-1.,0.,0.,0.,0.,0.]
        l=p.Limits(1.,1.,1.,1e-20,8,1e-12,'1'*64)
        r.geometry.contacts=lambda *args:[[15,1e-15,[1.,0.,0.],[0.,0.,0.]]]
        x=packet(r,l,rows=2)
        self.assertEqual(x['status'],'negative');self.assertEqual(x['work_rows'],0)
        self.assertEqual(backend.log,[]);self.assertEqual(x['accepted_rows'],[])
        self.assertIn('below unchanged minimum',x['error'])
        witness=x['event_cap_failure_witness'];self.assertEqual(witness['origin_state_token'],x['input_state_token'])
        self.assertEqual(witness['near'][0][1],1e-15);self.assertTrue(witness['no_accuracy_override'])
        self.assertIsNotNone(witness['selector_witness'])

    def test_event_unrepresentable_clock_preserves_pure_failure_witness(self):
        r,l,backend=make_runtime();r.limits=l;r.spec['horizon_s']=1e30
        r.geometry.contacts=lambda *args:[]
        origin=dict(token='1'*64,state=dict(x=[0.,0.,0.],p=[1.,0.,0.],q=[0.]*6,t=1e20))
        with self.assertRaises(a.event_cap.EventCapError):r._macro_initial_cap(origin)
        self.assertIn('unrepresentable',r.event_cap_failure_witness['error'])
        self.assertEqual(backend.log,[])



    def test_event_literal_history_and_all_trial_rows_serial_split(self):
        r,l,_=make_runtime(horizon=1.);r.spec['initial_state']['velocity_generalized']=[-1.,0.,0.,0.,0.,0.]
        l=p.Limits(1.,1.,1.,.01,8,1e-12,'1'*64)
        r.geometry.contacts=lambda *args:[[15,.001,[1.,0.,0.],[0.,0.,0.]]]
        serial=packet(r,l,rows=256,work=1000)
        left=packet(r,l,rows=128,work=500);right=packet(r,l,left['checkpoint'],rows=128,work=500)
        self.assertIsNone(serial['error']);self.assertIsNone(left['error']);self.assertIsNone(right['error'])
        self.assertGreater(len(serial['checkpoint']['physical_checkpoint']['state']['history']),0)
        self.assertEqual(a.numeric_restart_signature(serial),a.numeric_restart_signature(right))
        self.assertEqual(a.trace_rows(serial),a.trace_rows(left)+a.trace_rows(right))
        self.assertEqual(serial['trials'],left['trials']+right['trials'])
        self.assertEqual(numeric_branches(serial),numeric_branches(left)+numeric_branches(right))

    def test_event_rejected_origin_restart_keeps_h0_witness_without_reselect(self):
        r,l,_=make_runtime();r.spec['initial_state']['velocity_generalized']=[-1.,0.,0.,0.,0.,0.]
        r.geometry.contacts=lambda *args:[[15,.001,[1.,0.,0.],[0.,0.,0.]]]
        l=p.Limits(1.,1e-10,1.,1e-10,8,1e-12,'1'*64)
        serial=packet(r,l,rows=2,work=90);left=packet(r,l,rows=2,work=9)
        self.assertIsNone(serial['error']);self.assertEqual(left['cursor_after']['phase'],'after_rejection')
        with patch.object(a.event_cap,'select',side_effect=AssertionError('Same-origin restart cannot reselect event cap')):
            right=packet(r,l,left['checkpoint'],rows=2,work=81)
        self.assertIsNone(right['error']);self.assertEqual(a.numeric_restart_signature(serial),a.numeric_restart_signature(right))
        self.assertEqual(serial['trials'],left['trials']+right['trials'])
        self.assertEqual(numeric_branches(serial),numeric_branches(left)+numeric_branches(right))


if __name__ == '__main__':
    unittest.main(verbosity=2)
