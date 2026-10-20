"""Zero-transport adversarial controls for the inactive pure policy kernel."""
from dataclasses import asdict, replace
import copy
import json
import unittest
import full_state_stepdoubling_v1 as k


def sha(value):
    return k.digest(value)


class Controls(unittest.TestCase):
    def setUp(self):
        self.binding = sha("artificial-control-binding-not-a-production-design")
        self.limits = k.Limits(1., .01, .01, .01, 3, .0001, self.binding)
        def ep(t, name, ancestor, x=0., q=0.):
            return k.Endpoint(t, (x, 0., 0.), (1., 0., 0.), (q, 0., 0., 0., 0., 0.),
                              sha(name), sha(ancestor), sha(name+"audit"),
                              sha(name+"raw"), self.binding, True)
        self.origin = ep(0., "origin", "prior")
        self.coarse = ep(.1, "coarse", "origin", .02, .02)
        self.first = ep(.05, "first", "origin", .01, .01)
        self.second = ep(.1, "second", "first", .025, .025)

    def decision(self, **kw):
        v = dict(limits=self.limits, origin=self.origin, h_s=.1,
                 original_selected_cap_s=.1, halving_depth=0,
                 coarse=self.coarse, first_half=self.first, second_half=self.second)
        v.update(kw)
        return k.decide(**v)

    def test_commit_is_literal_fine_and_does_not_mutate(self):
        before = copy.deepcopy(asdict(self.second))
        d = self.decision()
        self.assertEqual(d.action, "commit_literal_halves")
        self.assertEqual(d.committed_full_checkpoint_sha256, self.second.full_checkpoint_sha256)
        self.assertEqual(asdict(self.second), before)

    def test_error_declines_all_outputs_and_halves(self):
        d = self.decision(second_half=replace(self.second, position_m=(.2, 0., 0.)))
        self.assertEqual((d.action, d.next_h_s, d.next_halving_depth),
                         ("discard_all_and_halve", .05, 1))
        self.assertIsNone(d.committed_full_checkpoint_sha256)
        self.assertEqual(len(d.discarded_full_checkpoint_sha256), 3)

    def test_physical_failure_never_becomes_accuracy_retry(self):
        with self.assertRaises(k.Stop):
            self.decision(coarse=replace(self.coarse, original_audits_passed=False))

    def test_full_ancestry_source_pending_and_time_are_exact(self):
        invalid = [replace(self.second, origin_full_checkpoint_sha256=sha("other")),
                   replace(self.second, numerical_binding=sha("changed")),
                   replace(self.second, pending_original_trial=True),
                   replace(self.second, time_s=.1+1e-15)]
        for v in invalid:
            with self.subTest(v=v), self.assertRaises(k.Stop):
                self.decision(second_half=v)

    def test_director_is_not_sign_aligned(self):
        d = self.decision(second_half=replace(self.second, director=(-1., 0., 0.)))
        self.assertEqual(d.director_defect, 2.)
        self.assertIsNone(d.committed_full_checkpoint_sha256)

    def test_nan_and_minimum_never_force_acceptance(self):
        for v in (replace(self.second, velocity_generalized=(float("nan"),)*6),
                  replace(self.second, position_m=(.2, 0., 0.))):
            with self.assertRaises(k.Stop):
                self.decision(second_half=v, halving_depth=3)
        with self.assertRaises(k.Stop):
            self.decision(original_selected_cap_s=.099)

    def test_finite_relaxation_identity_exposes_pose_only_swap(self):
        # Artificial scalar recurrence; not a DEM trajectory or a native call.
        m, drag, load, h = 2., 3., 7., .01
        q0 = q = x = trap = 0.
        for _ in range(100):
            old = q
            q = (m*q + h*load)/(m+h*drag)
            x += h*q
            trap += h*(old+q)/2
        self.assertAlmostEqual(drag*x, 100*h*load-m*(q-q0), places=12)
        self.assertAlmostEqual(trap-x, -h*(q-q0)/2, places=12)

    def test_one_unverified_and_every_branch_work_is_charged(self):
        ledger = k.WorkLedger(12, 2)
        ledger.reserve("all-three-branches", 9)
        with self.assertRaises(k.Stop):
            ledger.reserve("successor", 3)
        ledger.close(9, audited=True)
        self.assertEqual(ledger.used_work_rows, 9)
        with self.assertRaises(k.Stop):
            ledger.reserve("too-many-work-rows", 4)
        ledger.reserve("last", 3)
        ledger.close(3, audited=True)
        with self.assertRaises(k.Stop):
            ledger.reserve("over-record-cap", 1)

    def test_unknown_and_negative_stop_successors(self):
        a = k.WorkLedger(30, 10)
        a.reserve("unknown", 9)
        a.unresolved_exit()
        self.assertEqual((a.used_work_rows, a.unknown_reserved_rows), (9, 9))
        with self.assertRaises(k.Stop):
            a.reserve("successor", 3)
        b = k.WorkLedger(30, 10)
        b.reserve("negative", 9)
        b.close(7, audited=False)
        with self.assertRaises(k.Stop):
            b.reserve("successor", 3)

    def test_zero_row_evidence_failure_remains_terminal(self):
        ledger = k.WorkLedger(30, 10)
        ledger.reserve("zero-row-negative", 3)
        ledger.close(0, audited=False)
        restored = k.WorkLedger(**ledger.checkpoint())
        for item in (ledger, restored):
            with self.assertRaises(k.Stop):
                item.reserve("forbidden-successor", 3)

    def test_non_boolean_audit_flag_cannot_resolve_reservation(self):
        ledger = k.WorkLedger(30, 10)
        ledger.reserve("literal-audit", 3)
        with self.assertRaises(k.Stop):
            ledger.close(3, audited="False")
        self.assertIsNotNone(ledger.reservation)
        self.assertEqual(ledger.used_work_rows, 0)

    def test_known_overrun_is_not_undercharged_as_unknown(self):
        ledger = k.WorkLedger(3, 1)
        ledger.reserve("overrun", 3)
        with self.assertRaises(k.Stop):
            ledger.close(4, audited=True)
        self.assertEqual((ledger.used_work_rows, ledger.known_unaccepted_rows,
                          ledger.unknown_reserved_rows), (4, 4, 0))
        restored = k.WorkLedger(**ledger.checkpoint())
        with self.assertRaises(k.Stop):
            restored.reserve("forbidden-successor", 1)

    def test_ledger_restore_rejects_forged_or_inconsistent_progress(self):
        for kw in (dict(maximum_work_rows=10, maximum_integration_records=2, used_work_rows=-1),
                   dict(maximum_work_rows=10, maximum_integration_records=2, used_work_rows=1),
                   dict(maximum_work_rows=10, maximum_integration_records=2, used_integration_records=1),
                   dict(maximum_work_rows=True, maximum_integration_records=2)):
            with self.subTest(kw=kw), self.assertRaises(k.Stop):
                k.WorkLedger(**kw)

    def test_checkpoint_preserves_reservation_and_duplicate_identity(self):
        a = k.WorkLedger(30, 10)
        a.reserve("original", 9)
        b = k.WorkLedger(**json.loads(json.dumps(a.checkpoint())))
        self.assertEqual(a.checkpoint(), b.checkpoint())
        for item in (a, b):
            item.close(9, audited=True)
        self.assertEqual(a.checkpoint(), b.checkpoint())
        with self.assertRaises(k.Stop):
            b.reserve("original", 9)

    def test_no_launch_capability(self):
        self.assertFalse(any(k.READINESS.values()))

    def test_controller_restart_at_each_between_branch_interruption(self):
        cursor = k.TrialCheckpoint(self.limits, self.origin, .1, .1, 0)
        serial = self.decision()
        for endpoint in (self.coarse, self.first, self.second):
            restored = k.TrialCheckpoint.restore(json.loads(json.dumps(cursor.checkpoint())))
            self.assertEqual(restored.checkpoint(), cursor.checkpoint())
            with self.assertRaises(k.Stop):
                restored.decision()
            cursor = restored.append(endpoint)
        final = k.TrialCheckpoint.restore(json.loads(json.dumps(cursor.checkpoint())))
        self.assertEqual(asdict(final.decision()), asdict(serial))
        with self.assertRaises(k.Stop):
            final.append(self.second)

    def test_controller_checkpoint_corruption_cannot_be_resigned_into_wrong_ancestry(self):
        cursor = k.TrialCheckpoint(self.limits, self.origin, .1, .1, 0).append(self.coarse)
        envelope = cursor.checkpoint()
        envelope["payload"]["h_s"] = .2
        with self.assertRaises(k.Stop):
            k.TrialCheckpoint.restore(envelope)
        envelope["payload_sha256"] = k.digest(envelope["payload"])
        with self.assertRaises(k.Stop):
            k.TrialCheckpoint.restore(envelope)


if __name__ == "__main__":
    unittest.main(verbosity=2)
