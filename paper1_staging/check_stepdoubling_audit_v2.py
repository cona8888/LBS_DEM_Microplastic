"""Source/mock and authenticated SAVED-packet composition regressions only.

No force, runtime scope, integration, checkpoint resume or campaign admission.
The failed native packet stays known-unaccepted.  Its original physical checks
are NOT re-labelled as a newly executed mechanical/native restart qualification.
"""
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
import copy
import hashlib
import json
import lzma
import unittest
import audit_full_state_stepdoubling_v2 as a
import audit_full_state_stepdoubling_v1 as old
import check_stepdoubling_audit_v1 as legacy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'paper1_runs/full_horizon_repair_20261018_recovery02'
CLOSED = OUT / 'final_execution_receipt_01/results.json'
CLOSED_SHA = 'c117a2349cef6e9123e2a4df76de7694e1aa848eb967aa86693802ddf920370f'
RAW = OUT / 'records/f0p0625_odd_accepted_half_left/packet.json.xz'
RAW_SHA = '81354bc44afdad97647ef1c843a94b2c3bb54246309829ac5335deb36ec2e79f'


def original_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def saved_packet():
    a.require(a.file_sha(CLOSED) == CLOSED_SHA, 'exact closed failed second attempt')
    closed = json.loads(CLOSED.read_text())
    comp = json.loads(CLOSED.with_name('completion.json').read_text())
    a.require(comp['results_sha256'] == CLOSED_SHA and comp['passed'] is True
              and closed['passed'] is True and closed['closure_complete'] is True
              and closed['qualified'] is False, 'closed negative is not qualification')
    folder = RAW.parent
    consumed = {str(p): closed['artifacts'][str(p)] for p in folder.rglob('*') if p.is_file()}
    consumed.update({str(CLOSED): CLOSED_SHA,
                     str(CLOSED.with_name('completion.json')): a.file_sha(CLOSED.with_name('completion.json'))})
    a.verify_mapping(consumed)
    a.require(a.file_sha(RAW) == RAW_SHA, 'exact failed native odd-left bytes')
    env = json.loads(lzma.decompress(RAW.read_bytes())); packet = env['packet']
    mark = packet['checkpoint']['physical_checkpoint']['state']['history']
    a.require(mark['parent'] is None and mark['parent_length'] == 0,
              'this saved fixture is a fresh empty-history prefix, not a late reset')
    packet['checkpoint']['physical_checkpoint']['state']['history'] = mark['delta']
    prefix = json.loads((folder / 'prefix.json').read_text())
    reconstructed = (json.dumps(packet, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()
    a.require(hashlib.sha256(reconstructed).hexdigest() == env['original_uncompressed_sha256'] == prefix['original_sha256']
              and len(reconstructed) == env['original_uncompressed_bytes'], 'literal whole saved packet reconstruction')
    ph = ROOT / 'paper1_designs/full_horizon_repair_20261018/physical_cases_qualification_01.json'
    a.require(a.file_sha(ph) == closed['physical_inputs'][str(ph)], 'original physical case bytes')
    spec = next(x['spec'] for x in json.loads(ph.read_text())['cases'] if x['level_id'] == 'f0p0625')
    consumed[str(ph)] = a.file_sha(ph)
    return packet, spec, consumed


def composition(packet, limits, spec, *, before=None, module=a, prior=None):
    def callback(branch):
        # This callback tests composition ONLY. Actual original stencils remain
        # unchanged and must run in a fresh independently authorized record.
        proof = dict(stencil_verified=True, caps_replayed=True, history_delta_verified=True,
                     raw_observation_verified=True, composition_only_fixture=True)
        if 'previous_packet_receipt_sha256' in branch:
            raw = {k: v for k, v in branch.items() if k != 'previous_packet_receipt_sha256'}
            a.require(prior is not None and raw in prior['checkpoint']['pending_branches'],
                      'fixture exact immutable prior pending branch')
            proof['prior_admission_authenticated'] = True
        return proof
    return module.audit_packet(module.normalized_packet_view(packet), limits,
        input_full_checkpoint=None if before is None else before['physical_checkpoint'],
        output_full_checkpoint=packet['checkpoint']['physical_checkpoint'], original_digest=original_digest,
        audit_branch=callback, expected_input_state_token=packet['input_state_token'],
        expected_policy_sha256=packet['policy_sha256'], initial_spec=spec,
        expected_previous_receipt_sha256='2'*64 if before is not None else None)


class PendingControls(unittest.TestCase):
    def test_saved_native_left_reproduces_v1_and_repairs_only_composition(self):
        packet, spec, consumed = saved_packet()
        with self.assertRaisesRegex(ValueError, 'staged F1/coarse bound but not committed'):
            composition(packet, packet['limits'], spec, module=old)
        result = composition(packet, packet['limits'], spec)
        self.assertEqual(result['all_work_rows'], 3)
        self.assertEqual(result['committed_branch_ids'], [packet['work_branches'][1]['branch_id']])
        self.assertTrue(result['pending_controller_trial'])
        self.assertFalse(result['native_qualification_admitted'])
        self.assertEqual(packet['checkpoint']['physical_checkpoint']['state']['pending_trial'], None)
        a.verify_mapping(consumed)

    def test_saved_native_pending_F2_expected_publication_shape_only(self):
        left, spec, consumed = saved_packet()
        before = copy.deepcopy(left['checkpoint'])
        f2 = left['work_branches'][2]
        # Pure data projection of the required resume result, not an executed
        # native resume. The physical state is the ALREADY SAVED F2 witness.
        state = {k: copy.deepcopy(v) for k, v in f2['after_state'].items()
                 if k not in {'history_node', 'history_length'}}
        state['history'] = copy.deepcopy(before['physical_checkpoint']['state']['history']) + f2['history_delta']
        full = dict(schema=before['physical_checkpoint']['schema'], contract=f2['contract'],
                    state=state, state_sha256=original_digest(state))
        right = copy.deepcopy(left)
        right['input_state_token'] = left['output_state_token']
        right['output_state_token'] = f2['output_state_token']
        right['original_FULL_input_sha256'] = right['input_full_checkpoint_sha256'] = original_digest(before['physical_checkpoint'])
        right['original_FULL_output_sha256'] = right['output_full_checkpoint_sha256'] = original_digest(full)
        right['cursor_before'] = copy.deepcopy(left['cursor_after'])
        right['cursor_after'].update(phase='idle', origin_state_token=f2['output_state_token'], h_s=None,
            original_selected_cap_s=None, depth=0, branch_ids=[], decision=None, clock_preflight=None,
            pending_branch_id=None, published_half_count=2)
        right['ledger_before'] = copy.deepcopy(left['ledger_after'])
        right['ledger_after'] = dict(right['ledger_before'], accepted_half_rows=right['ledger_before']['accepted_half_rows']+1)
        right.update(work_rows=0, work_branches=[], trials=[], committed_branch_ids=[f2['branch_id']],
                     accepted_rows=copy.deepcopy(f2['rows']))
        right['carried_branches'] = [dict(copy.deepcopy(b), previous_packet_receipt_sha256='2'*64)
                                     for b in left['checkpoint']['pending_branches']]
        right['checkpoint'].update(physical_checkpoint=full, published_state_token=right['output_state_token'],
            cursor=copy.deepcopy(right['cursor_after']), numeric_ledger=copy.deepcopy(right['ledger_after']), pending_branches=[])
        proof = composition(right, right['limits'], spec, before=before, prior=left)
        self.assertEqual(proof['all_work_rows'], 0)
        self.assertEqual(proof['committed_branch_ids'], [f2['branch_id']])
        self.assertEqual(proof['accounting']['accepted_half_rows'], 1)
        self.assertFalse(proof['native_qualification_admitted'])
        self.assertEqual(full['state']['q'], f2['rows'][0]['velocity_generalized'])
        a.verify_mapping(consumed)

    def test_saved_native_cursor_corruption_and_missing_fields_fail_closed(self):
        original, spec, consumed = saved_packet()
        changes = (
            ('wrong_F2_token', lambda p: p['cursor_after']['decision'].__setitem__('committed_state_token', '0'*64)),
            ('wrong_defect', lambda p: p['cursor_after']['decision'].__setitem__('scaled_defect', 0.)),
            ('wrong_witness', lambda p: p['cursor_after']['decision'].__setitem__('witness_semantics', 'FULL_sha')),
            ('unreviewed_field', lambda p: p['cursor_after']['decision'].__setitem__('ignored_field', True)),
            ('wrong_pending_id', lambda p: p['cursor_after'].__setitem__('pending_branch_id', p['work_branches'][0]['branch_id'])),
            ('premature_F2', lambda p: p['committed_branch_ids'].append(p['work_branches'][2]['branch_id'])),
            ('missing_coarse', lambda p: p['work_branches'].pop(0)),
        )
        for label, change in changes:
            packet = copy.deepcopy(original); change(packet)
            with self.subTest(label=label), self.assertRaises((ValueError, KeyError)):
                composition(packet, packet['limits'], spec)
        a.verify_mapping(consumed)

    def odd_pair(self):
        import check_full_state_integration_adapter_v3 as fake
        runtime, limits, backend = fake.make_runtime()
        left = fake.packet(runtime, limits, rows=1)
        before = fake.a.controller_checkpoint(left)
        calls = len(backend.log)
        right = fake.packet(runtime, limits, before, rows=1)
        self.assertEqual(len(backend.log), calls, 'pending F2 publication executes no new fake force either')
        return fake, runtime, limits, left, before, right

    def test_fake_pending_F2_authenticates_complete_prior_pair_publishes_once(self):
        fake, runtime, limits, left, before, right = self.odd_pair()
        self.assertTrue(composition(left, asdict(limits), runtime.spec)['pending_controller_trial'])
        self.assertEqual([x['role'] for x in right['carried_branches']], ['C', 'F1', 'F2'])
        result = composition(right, asdict(limits), runtime.spec, before=before, prior=left)
        self.assertEqual(result['all_work_rows'], 0)
        self.assertEqual(result['committed_branch_ids'], [left['work_branches'][2]['branch_id']])
        self.assertEqual(result['accounting']['accepted_half_rows'], 1)
        self.assertFalse(result['pending_controller_trial'])
        self.assertFalse(result['native_qualification_admitted'])
        self.assertEqual(right['ledger_after']['all_work_rows'], left['ledger_after']['all_work_rows'])

    def test_fake_pending_F2_corruption_and_duplicate_publication_rejected(self):
        fake, runtime, limits, left, before, original = self.odd_pair()
        changes = (
            ('drop_C', lambda p: p['carried_branches'].pop(0)),
            ('reject_prior', lambda p: p['cursor_before']['decision'].__setitem__('action', 'discard_all_and_halve')),
            ('wrong_prior_F2', lambda p: p['cursor_before']['decision'].__setitem__('committed_state_token', '0'*64)),
            ('wrong_prior_F1_FULL', lambda p: p['state_headers'][p['input_state_token']]['q'].__setitem__(0, 99.)),
            ('duplicate_F1', lambda p: p['committed_branch_ids'].insert(0, left['work_branches'][1]['branch_id'])),
            ('duplicate_charge', lambda p: p['ledger_after'].__setitem__('all_work_rows', p['ledger_after']['all_work_rows']+3)),
            ('duplicate_accepted', lambda p: p['ledger_after'].__setitem__('accepted_half_rows', p['ledger_after']['accepted_half_rows']+1)),
        )
        for label, change in changes:
            packet = copy.deepcopy(original); change(packet)
            with self.subTest(label=label), self.assertRaises((ValueError, KeyError)):
                composition(packet, asdict(limits), runtime.spec, before=before, prior=left)


if __name__ == '__main__':
    # Reuse all24 preserved controls against V2 by changing only their private
    # in-memory module association. No original source bytes are changed.
    with patch.object(legacy, 'a', a):
        suite = unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(legacy.Controls),
                                    unittest.defaultTestLoader.loadTestsFromTestCase(PendingControls)))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
