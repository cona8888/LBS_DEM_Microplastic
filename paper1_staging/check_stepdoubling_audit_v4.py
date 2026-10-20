"""Artificial/source-only event composition controls, ZERO model/native work.

Mechanical callbacks below are explicitly synthetic. These controls do not
admit a retained failed packet, qualify a physical restart or authorize a run.
"""
import ast
import copy
import json
import math
from pathlib import Path
import unittest
from dataclasses import asdict, replace
from unittest.mock import patch

import audit_full_state_stepdoubling_v4 as a
import audit_full_state_stepdoubling_v3 as preserved
import contact_event_cap_v1 as producer

ROOT = Path(__file__).resolve().parents[1]


def reference(state):
    return dict(time_s=state['t'], steps=state['steps'], velocity_generalized=copy.deepcopy(state['q']),
                original_selected_dt_s=.01, base_dt_s=.01, untruncated_dt_s=.02,
                near=[[15, .004, [1., 0., 0.], [0., 0., 0.]]])


def event(state, token, limits, depth=0):
    ref = reference(state)
    h, witness = producer.select(ref['original_selected_dt_s'], ref['near'], state['q'],
                                1., limits['speed_m_s'], limits['velocity_defect_over_U'],
                                limits['minimum_h_s'], state['t'])
    witness = json.loads(json.dumps(witness))
    return dict(original_selected_cap_s=ref['original_selected_dt_s'], macro_initial_cap_s=h,
                h_s=math.ldexp(h, -depth), depth=depth,
                event_cap_witness=dict(schema='paper1.macro-event-cap-binding.v1',
                    event_policy_sha256=producer.POLICY_SHA256, event_source_sha256=a.EVENT_SOURCE_SHA256,
                    origin_state_token=token, time_s=state['t'], original_selected_cap_s=ref['original_selected_dt_s'],
                    macro_initial_cap_s=h, selector_witness=witness))


def full(header, history=None):
    state = {k: copy.deepcopy(v) for k, v in header.items() if k not in {'history_node', 'history_length'}}
    state['history'] = list(history or [])
    return dict(state=state, state_sha256=a.digest(state))


def branch(role, parent, state, t, macro, trial=0, q_after=None):
    after = copy.deepcopy(state)
    dt = t-state['t']
    after.update(t=t, steps=state['steps']+1,
                 x=[x+dt*q for x, q in zip(state['x'], state['q'][:3])])
    if q_after is not None:
        after['q'] = q_after
    delta = []
    after['history_node'] = a.history_node(state['history_node'], delta)
    token = a.state_token(parent, after, delta)
    return dict(branch_id=f'm{macro}_t{trial}_{role}', macro_index=macro, role=role,
        input_state_token=parent, output_state_token=token, before_state=copy.deepcopy(state),
        after_state=after, history_parent=parent, history_delta=delta, work_rows=1,
        rows=[dict(time_s=t, dt_s=dt, position_m=after['x'], orientation=after['p'], velocity_generalized=after['q'])],
        requested_dt_s=dt, target_time_s=t,
        cap_entries=[dict(original_selected_dt_s=.01, trigger_grain_ids=[])])


def fixture(*, depth=0, reject=False):
    limits = dict(speed_m_s=1., position_defect_m=1., director_defect=1.,
                  velocity_defect_over_U=.02, minimum_h_s=1e-6, maximum_halvings=8)
    state = dict(t=.15, steps=0, x=[0., 0., 0.], p=[1., 0., 0.], q=[-1., 0., 0., 0., 0., 0.],
                 minimum_gap=float('inf'), monitor={}, pending_trial=None)
    seed = full(state)
    token = a.digest('artificial real FULL root')
    state.update(history_node=a.boundary_history_node(seed, a.digest), history_length=0)
    selection = event(state, token, limits, depth)
    h = selection['h_s']; end, mid = state['t']+h, state['t']+h/2
    c = branch('C', token, state, end, 1, q_after=[-.9, 0., 0., 0., 0., 0.] if reject else None)
    f1 = branch('F1', token, state, mid, 1)
    f2 = branch('F2', f1['output_state_token'], f1['after_state'], end, 1)
    c['requested_dt_s'] = h
    bs = [c, f1, f2]
    decision = a.independent_trial_decision(limits, a._endpoint(state, token, token), bs,
        h_s=h, selected_cap_s=.01, depth=depth)
    trial = dict(macro_index=1, trial_index=depth, origin_state_token=token,
                 branch_ids=[b['branch_id'] for b in bs], decision=decision, **selection)
    idle = dict(phase='idle', macro_index=0, macro_initial_cap_s=None, event_cap_witness=None)
    output = seed if reject else full(f2['after_state'])
    committed = [] if reject else trial['branch_ids'][1:]
    cursor = (dict(trial, phase='after_rejection', trial_index=depth+1, branch_ids=[], decision=None,
                   h_s=h/2, depth=depth+1) if reject else dict(idle, macro_index=1))
    packet = dict(schema='paper1.full-state-stepdoubling.packet.v1', policy_sha256=a.digest('artificial policy'),
        event_policy_sha256=producer.POLICY_SHA256, event_source_sha256=a.EVENT_SOURCE_SHA256,
        input_full_checkpoint_sha256=a.digest(seed), output_full_checkpoint_sha256=a.digest(output),
        input_state=state, input_state_token=token,
        output_state_token=token if reject else f2['output_state_token'],
        work_branches=bs, carried_branches=[], committed_branch_ids=committed, trials=[trial],
        cursor_before=idle, cursor_after=cursor,
        ledger_before=dict(all_work_rows=0, accepted_half_rows=0, rejected_trials=0),
        ledger_after=dict(all_work_rows=3, accepted_half_rows=len(committed), rejected_trials=int(reject)),
        work_rows=3, reservation=dict(maximum_work_rows=3))
    if depth:
        packet['cursor_before'] = dict(trial, phase='after_rejection', branch_ids=[], decision=None)
    return packet, limits, seed, output


def composition(packet, limits, before, after, *, prior=None, reconstruct=reference):
    def callback(b):
        proof = dict(stencil_verified=True, caps_replayed=True, history_delta_verified=True,
                     raw_observation_verified=True, composition_only_fixture=True)
        if 'previous_packet_receipt_sha256' in b:
            raw = {k: v for k, v in b.items() if k != 'previous_packet_receipt_sha256'}
            a.require(prior is not None and raw in prior, 'exact prior synthetic branch association')
            proof['prior_admission_authenticated'] = True
        return proof
    return a.audit_packet(packet, limits, input_full_checkpoint=before, output_full_checkpoint=after,
        original_digest=a.digest, audit_branch=callback, expected_input_state_token=packet['input_state_token'],
        expected_policy_sha256=a.digest('artificial policy'), expected_previous_receipt_sha256='2'*64 if prior else None,
        original_cap_reconstructor=reconstruct, event_length_scale_m=1.)


class Controls(unittest.TestCase):
    def test_preserved_v3_negative_and_corrected_decision_to_odd_to_F2_chain(self):
        self.assertEqual(a.file_sha(Path(preserved.__file__)), a.PRESERVED_AUDIT_V3_SHA256)
        fake, runtime, limits, backend = self.generated_runtime()
        serial = fake.packet(runtime, limits, rows=2)
        left = fake.packet(runtime, limits, phase='decision_done', rows=2)
        self.assertTrue(self.generated_audit(left, runtime, limits)['passed'])
        calls = len(backend.log)
        before = fake.a.controller_checkpoint(left)
        middle = fake.packet(runtime, limits, before, rows=1)
        self.assertIsNone(middle['error'])
        with patch.dict(self.generated_audit.__func__.__globals__, a=preserved):
            with self.assertRaisesRegex(ValueError, 'no coarse shadow or staged F1 promotion'):
                self.generated_audit(middle, runtime, limits, before, left)
        proof = self.generated_audit(middle, runtime, limits, before, left)
        self.assertEqual(proof['all_work_rows'], 0)
        self.assertEqual(proof['committed_branch_ids'], [left['work_branches'][1]['branch_id']])
        self.assertTrue(proof['pending_controller_trial'])
        middle_cp = fake.a.controller_checkpoint(middle)
        right = fake.packet(runtime, limits, middle_cp, rows=1)
        result = self.generated_audit(right, runtime, limits, middle_cp, middle)
        self.assertEqual(result['all_work_rows'], 0)
        self.assertEqual(result['committed_branch_ids'], [left['work_branches'][2]['branch_id']])
        self.assertEqual(len(backend.log), calls, 'neither pending publication re-executes even fake force')
        self.assertEqual(fake.a.numeric_restart_signature(serial), fake.a.numeric_restart_signature(right))
        self.assertEqual(serial['checkpoint']['physical_checkpoint'], right['checkpoint']['physical_checkpoint'])

    def test_unapplied_decision_requires_zero_publication_and_no_pending_half(self):
        fake, runtime, limits, backend = self.generated_runtime()
        left = fake.packet(runtime, limits, phase='decision_done', rows=2)
        before = fake.a.controller_checkpoint(left)
        right = fake.packet(runtime, limits, before, rows=1)
        for field, value in (('published_half_count', 1), ('pending_branch_id', left['work_branches'][2]['branch_id'])):
            altered = copy.deepcopy(left); altered['cursor_after'][field] = value
            with self.subTest(phase='after', field=field), self.assertRaises(ValueError):
                self.generated_audit(altered, runtime, limits)
            altered = copy.deepcopy(right); altered['cursor_before'][field] = value
            with self.subTest(phase='before', field=field), self.assertRaises(ValueError):
                self.generated_audit(altered, runtime, limits, before, left)

    def test_only_narrow_v3_composition_delta_and_preserved_sources(self):
        self.assertEqual(a.file_sha(Path(preserved.__file__)), a.PRESERVED_AUDIT_V3_SHA256)
        defs = lambda path: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
        old, new = defs(Path(preserved.__file__)), defs(Path(a.__file__))
        self.assertEqual(old.keys(), new.keys())
        for name in old.keys()-{'audit_packet', 'normalized_packet_view'}:
            self.assertEqual(old[name], new[name], name)

    def generated_runtime(self):
        # This fixture compiles pinned original AST in private FAKE namespaces;
        # its meta_path tripwire rejects every physical model dependency import.
        import check_full_state_integration_adapter_v5 as fake
        runtime, limits, backend = fake.make_runtime()
        runtime.spec['initial_state']['velocity_generalized'] = [-1., 0., 0., 0., 0., 0.]
        runtime.geometry.contacts = lambda *args: [(15, .004, [1., 0., 0.], [0., 0., 0.])]
        return fake, runtime, replace(limits, velocity_defect_over_U=.02), backend

    def generated_audit(self, packet, runtime, limits, before=None, prior=None):
        def reconstruct(state):
            H = min(.01, runtime.spec['horizon_s']-state['t'])
            return dict(time_s=state['t'], steps=state['steps'], velocity_generalized=copy.deepcopy(state['q']),
                original_selected_dt_s=H, base_dt_s=H, untruncated_dt_s=.01,
                near=[[15, .004, [1., 0., 0.], [0., 0., 0.]]])
        def callback(branch):
            result = dict(stencil_verified=True, caps_replayed=True, history_delta_verified=True,
                          raw_observation_verified=True, artificial_compiled_loop_only=True)
            if 'previous_packet_receipt_sha256' in branch:
                raw = {k:v for k,v in branch.items() if k != 'previous_packet_receipt_sha256'}
                a.require(prior is not None and raw in prior['checkpoint']['pending_branches'],
                          'exact prior producer packet before synthetic carry authentication')
                result['prior_admission_authenticated'] = True
            return result
        return a.audit_packet(a.normalized_packet_view(packet), asdict(limits),
            input_full_checkpoint=None if before is None else before['physical_checkpoint'],
            output_full_checkpoint=packet['checkpoint']['physical_checkpoint'],
            original_digest=__import__('full_state_integration_adapter_v5').original_digest,
            audit_branch=callback, expected_input_state_token=packet['input_state_token'],
            expected_policy_sha256=limits.numerical_binding, initial_spec=runtime.spec,
            expected_previous_receipt_sha256='2'*64 if prior is not None else None,
            original_cap_reconstructor=reconstruct, event_length_scale_m=1.)

    def test_actual_fake_compiled_producer_and_raw_roundtrip_event_witness(self):
        fake, runtime, limits, backend = self.generated_runtime()
        packet = fake.packet(runtime, limits, rows=4)
        self.assertIsNone(packet['error'])
        self.assertLess(packet['trials'][0]['macro_initial_cap_s'], packet['trials'][0]['original_selected_cap_s'])
        self.assertTrue(self.generated_audit(packet, runtime, limits)['passed'])
        encoded = json.loads(json.dumps(packet, allow_nan=True))
        self.assertTrue(self.generated_audit(encoded, runtime, limits)['passed'])
        self.assertEqual(packet['trials'][0]['event_cap_witness'], encoded['trials'][0]['event_cap_witness'])
        self.assertGreater(packet['trials'][1]['macro_initial_cap_s'], packet['trials'][0]['macro_initial_cap_s'])
        self.assertEqual(packet['trials'][1]['depth'], 0, 'fresh cap recovery is never a permanent ratchet')
        self.assertEqual([v[0] for v in backend.log], ['C', 'F1', 'F2', 'C', 'F1', 'F2'])

    def test_actual_fake_compiled_every_partial_cursor_and_complete_odd_carry(self):
        for phase in ('C_done', 'F1_done', 'F2_done', 'decision_done', 'odd'):
            fake, runtime, limits, backend = self.generated_runtime()
            left = fake.packet(runtime, limits, rows=1 if phase == 'odd' else 2,
                               phase=None if phase == 'odd' else phase)
            self.assertIsNone(left['error'], phase)
            self.assertTrue(self.generated_audit(left, runtime, limits)['passed'], phase)
            before = fake.a.controller_checkpoint(left)
            calls = len(backend.log)
            right = fake.packet(runtime, limits, before, rows=3 if phase == 'odd' else 2)
            self.assertIsNone(right['error'], phase)
            self.assertTrue(self.generated_audit(right, runtime, limits, before, left)['passed'], phase)
            self.assertEqual(right['ledger_after']['all_work_rows']-left['ledger_after']['all_work_rows'],
                             len(backend.log)-calls, phase)
            if phase == 'odd':
                self.assertEqual([v['role'] for v in right['carried_branches']], ['C', 'F1', 'F2'])
                self.assertEqual(right['committed_branch_ids'][0], left['work_branches'][2]['branch_id'])
                self.assertNotIn(left['work_branches'][1]['branch_id'], right['committed_branch_ids'])

    def test_actual_fake_staged_reject_decision_is_applied_and_charged_once_on_resume(self):
        fake, runtime, limits, backend = self.generated_runtime()
        limits = replace(limits, velocity_defect_over_U=1e-8)
        left = fake.packet(runtime, limits, phase='decision_done', rows=2)
        self.assertEqual(left['trials'][0]['decision']['action'], 'discard_all_and_halve')
        self.assertEqual(left['ledger_after']['rejected_trials'], 0)
        self.assertEqual(left['committed_branch_ids'], [])
        self.assertEqual(self.generated_audit(left, runtime, limits)['accounting']['rejected_trials'], 0)
        before = fake.a.controller_checkpoint(left)
        right = fake.packet(runtime, limits, before, rows=2, work=120)
        self.assertIsNone(right['error'])
        proof = self.generated_audit(right, runtime, limits, before, left)
        self.assertEqual(proof['accounting']['rejected_trials'], right['ledger_after']['rejected_trials'])
        self.assertEqual(right['ledger_after']['all_work_rows'], len(backend.log))
        self.assertEqual(proof['accounting']['accepted_half_rows'], 2)

    def test_actual_fake_staged_decision_tampering_and_duplicate_application_rejected(self):
        fake, runtime, limits, backend = self.generated_runtime()
        left = fake.packet(runtime, limits, phase='decision_done', rows=2)
        before = fake.a.controller_checkpoint(left)
        original = fake.packet(runtime, limits, before, rows=2)
        changes = (
            lambda p: p['cursor_before']['decision'].__setitem__('committed_state_token', '0'*64),
            lambda p: p['cursor_before']['decision'].__setitem__('scaled_defect', 0.),
            lambda p: p['cursor_before']['decision'].__setitem__('ignored_field', True),
            lambda p: p['cursor_before']['event_cap_witness'].__setitem__('original_selected_cap_s', .02),
            lambda p: p['carried_branches'].pop(0),
            lambda p: p['trials'].insert(0, copy.deepcopy(left['trials'][0])),
            lambda p: p['ledger_after'].__setitem__('accepted_half_rows', 4),
        )
        for change in changes:
            packet = copy.deepcopy(original); change(packet)
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                self.generated_audit(packet, runtime, limits, before, left)
        bad = copy.deepcopy(left)
        bad['ledger_after']['rejected_trials'] = 1
        with self.assertRaises(ValueError): self.generated_audit(bad, runtime, limits)

    def test_independent_selector_matches_frozen_pure_producer(self):
        self.assertEqual(a.file_sha(a.EVENT_SOURCE), a.EVENT_SOURCE_SHA256)
        self.assertEqual(a.EVENT_POLICY_SHA256, producer.POLICY_SHA256)
        for t in (0., .15, .4):
            for gap in (-.001, 0., 1e-7, .0001, .004, .03):
                for q in ([-1., 0., 0., 0., 0., 0.], [1., 0., 0., 0., 0., 0.],
                          [0., 0., 0., 0., 0., 1.]):
                    near = [[15, gap, [1., 0., 0.], [0., .01, 0.]],
                            [182, .008, [1., 0., 0.], [0., 0., 0.]]]
                    actual = a.independent_event_cap(.01, near, q, 1., 1., .02, 1e-9, t)
                    expected = producer.select(.01, near, q, 1., 1., .02, 1e-9, t)
                    self.assertEqual(actual, (expected[0], json.loads(json.dumps(expected[1]))))

    def test_event_cap_first_trial_and_all_work_are_independent(self):
        p, l, b, e = fixture()
        self.assertEqual(p['trials'][0]['macro_initial_cap_s'], .002)
        self.assertEqual(composition(p, l, b, e)['all_work_rows'], 3)
        self.assertFalse(composition(p, l, b, e)['native_qualification_admitted'])

    def test_every_witness_field_and_original_operands_are_required(self):
        p, l, b, e = fixture()
        changes = (
            lambda q: q['trials'][0].pop('event_cap_witness'),
            lambda q: q.pop('event_source_sha256'),
            lambda q: q['trials'][0]['event_cap_witness'].__setitem__('event_source_sha256', '0'*64),
            lambda q: q['trials'][0]['event_cap_witness'].__setitem__('event_policy_sha256', '0'*64),
            lambda q: q['trials'][0]['event_cap_witness']['selector_witness']['passes'][0]['contact_witnesses'][0].__setitem__('raw_gap_m', .003),
            lambda q: q['trials'][0]['event_cap_witness']['selector_witness']['velocity_generalized'].__setitem__(0, -.9),
            lambda q: q['trials'][0]['event_cap_witness']['selector_witness']['literal_clock'].__setitem__('end_time_s', .2),
            lambda q: q['trials'][0]['event_cap_witness'].__setitem__('ignored_key', True),
            lambda q: q['trials'][0].__setitem__('original_selected_cap_s', .02),
        )
        for change in changes:
            q = copy.deepcopy(p); change(q)
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                composition(q, l, b, e)

    def test_h_less_than_H_is_insufficient_and_first_depth_cannot_skip(self):
        p, l, b, e = fixture()
        p['trials'][0]['h_s'] = .001
        with self.assertRaisesRegex(ValueError, 'h0/2'):
            composition(p, l, b, e)
        p, l, b, e = fixture(depth=1)
        self.assertTrue(composition(p, l, b, e)['passed'])
        p['cursor_before'] = dict(phase='idle', macro_index=0, macro_initial_cap_s=None, event_cap_witness=None)
        with self.assertRaisesRegex(ValueError, 'depth zero'):
            composition(p, l, b, e)

    def test_independent_original_H_near_q_cannot_be_replaced_by_record(self):
        p, l, b, e = fixture()
        for key in ('near', 'velocity_generalized', 'original_selected_dt_s', 'time_s'):
            def changed(state, key=key):
                value = reference(state)
                if key == 'near': value[key][0][1] = .003
                elif key == 'velocity_generalized': value[key][0] = -.9
                elif key == 'time_s': value[key] += .001
                else: value[key] = .02
                return value
            with self.subTest(key=key), self.assertRaises(ValueError):
                composition(p, l, b, e, reconstruct=changed)

    def test_partial_C_and_F1_cursor_retains_exact_event_without_promotion(self):
        for count, phase in ((1, 'after_coarse'), (2, 'after_first_half')):
            p, l, b, _ = fixture()
            p['work_branches'] = p['work_branches'][:count]
            p['trials'][0].update(branch_ids=[v['branch_id'] for v in p['work_branches']], decision=None)
            p.update(committed_branch_ids=[], output_state_token=p['input_state_token'],
                     output_full_checkpoint_sha256=a.digest(b), work_rows=count)
            p['cursor_after'] = dict(p['trials'][0], phase=phase)
            p['ledger_after'].update(all_work_rows=count, accepted_half_rows=0)
            self.assertTrue(composition(p, l, b, b)['pending_controller_trial'])
            p['cursor_after']['event_cap_witness']['macro_initial_cap_s'] = .003
            with self.assertRaises(ValueError): composition(p, l, b, b)

    def test_partial_carried_C_keeps_first_origin_witness_and_charges_once(self):
        p, l, b, e = fixture()
        c = p['work_branches'].pop(0)
        p['carried_branches'] = [dict(copy.deepcopy(c), previous_packet_receipt_sha256='2'*64)]
        p['cursor_before'] = dict(p['trials'][0], phase='after_coarse', branch_ids=[c['branch_id']], decision=None)
        p['ledger_before']['all_work_rows'] = 1
        p['work_rows'] = 2
        self.assertEqual(composition(p, l, b, e, prior=[c])['all_work_rows'], 2)
        p['cursor_before']['event_cap_witness']['time_s'] += .001
        with self.assertRaises(ValueError): composition(p, l, b, e, prior=[c])

    def odd_pair(self):
        left, l, b, e = fixture()
        f1, f2 = left['work_branches'][1:]
        first = full(f1['after_state'])
        left.update(output_state_token=f1['output_state_token'], output_full_checkpoint_sha256=a.digest(first),
                    committed_branch_ids=[f1['branch_id']])
        left['trials'][0]['published_half_count'] = 1
        left['ledger_after']['accepted_half_rows'] = 1
        left['cursor_after'] = dict(left['trials'][0], phase='publish_second_half',
                                   pending_branch_id=f2['branch_id'], published_half_count=1)
        right = copy.deepcopy(left)
        right.update(input_state=copy.deepcopy(f1['after_state']), input_state_token=f1['output_state_token'],
            input_full_checkpoint_sha256=a.digest(first), output_state_token=f2['output_state_token'],
            output_full_checkpoint_sha256=a.digest(e), work_branches=[], trials=[], work_rows=0,
            carried_branches=[dict(copy.deepcopy(v), previous_packet_receipt_sha256='2'*64) for v in left['work_branches']],
            committed_branch_ids=[f2['branch_id']], cursor_before=copy.deepcopy(left['cursor_after']),
            cursor_after=dict(phase='idle', macro_index=1, macro_initial_cap_s=None, event_cap_witness=None),
            ledger_before=copy.deepcopy(left['ledger_after']),
            ledger_after=dict(all_work_rows=3, accepted_half_rows=2, rejected_trials=0))
        return left, right, l, b, first, e

    def test_odd_full_F1_then_authenticated_whole_triple_F2_exact_once(self):
        left, right, l, b, first, e = self.odd_pair()
        self.assertTrue(composition(left, l, b, first)['pending_controller_trial'])
        result = composition(right, l, first, e, prior=left['work_branches'])
        self.assertEqual(result['all_work_rows'], 0)
        self.assertEqual(result['committed_branch_ids'], [left['work_branches'][2]['branch_id']])
        self.assertEqual(result['accounting']['accepted_half_rows'], 1)

    def test_carried_odd_witness_and_FULL_corruptions_never_waived(self):
        left, p, l, b, first, e = self.odd_pair()
        changes = (lambda q: q['carried_branches'].pop(0),
            lambda q: q['cursor_before']['event_cap_witness'].__setitem__('macro_initial_cap_s', .01),
            lambda q: q['cursor_before'].__setitem__('h_s', .001),
            lambda q: q['committed_branch_ids'].insert(0, left['work_branches'][1]['branch_id']),
            lambda q: q['ledger_after'].__setitem__('all_work_rows', 6),
            lambda q: q['carried_branches'][0]['before_state']['q'].__setitem__(0, -.8))
        for change in changes:
            q = copy.deepcopy(p); change(q)
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                composition(q, l, first, e, prior=left['work_branches'])
        broken = copy.deepcopy(first); broken['state']['history'] = [[99.]]; broken['state_sha256'] = a.digest(broken['state'])
        with self.assertRaises(ValueError): composition(p, l, broken, e, prior=left['work_branches'])

    def test_rejection_keeps_origin_witness_and_exact_half_not_permanent_ratchet(self):
        p, l, b, e = fixture(reject=True)
        self.assertTrue(composition(p, l, b, e)['pending_controller_trial'])
        p['cursor_after']['macro_initial_cap_s'] = .001
        with self.assertRaises(ValueError): composition(p, l, b, e)

    def test_no_minimum_clip_no_geometry_projection_and_no_float_clock_rewrite(self):
        args = (.01, [[15, 1e-15, [1.,0.,0.], [0.,0.,0.]]], [-1.,0.,0.,0.,0.,0.], 1., 1., 1e-20, 1e-10, .15)
        with self.assertRaises(ValueError): a.independent_event_cap(*args)
        args = (.01, [], [-1.,0.,0.,0.,0.,0.], 1., 1., .02, 1e-20, 1e20)
        with self.assertRaises(ValueError): a.independent_event_cap(*args)
        for bad in (True, float('nan'), float('inf')):
            with self.assertRaises(ValueError): a.independent_event_cap(bad, [], [0.]*6, 1., 1., .02, 1e-9, .15)

    def test_original_mechanics_caps_decisions_history_and_accounting_AST_unchanged(self):
        old = ROOT/'paper1_staging/audit_full_state_stepdoubling_v2.py'
        self.assertEqual(a.file_sha(old), a.PRESERVED_AUDIT_V2_SHA256)
        defs = lambda p: {v.name: ast.dump(v, include_attributes=False) for v in ast.parse(p.read_text()).body if isinstance(v, ast.FunctionDef)}
        before, after = defs(old), defs(Path(a.__file__))
        changes = {'audit_packet', 'normalized_packet_view', 'audit_runtime_packet'}
        for name in before.keys()-changes:
            self.assertEqual(before[name], after[name], name)
        for node in ast.parse(Path(a.__file__).read_text()).body:
            if isinstance(node, ast.Import):
                self.assertNotIn('contact_event_cap_v1', [v.name for v in node.names])
            if isinstance(node, ast.ImportFrom): self.assertNotEqual(node.module, 'contact_event_cap_v1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
