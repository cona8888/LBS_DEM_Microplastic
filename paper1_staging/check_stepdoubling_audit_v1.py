"""Artificial zero-native adversarial controls, never mechanical qualification."""
import copy
import json
from pathlib import Path
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import audit_full_state_stepdoubling_v1 as a
import prepare_stepdoubling_restart_v1 as r


def fixture():
    limits = dict(speed_m_s=1., position_defect_m=1., director_defect=1.,
                  velocity_defect_over_U=1., minimum_h_s=.001, maximum_halvings=4)
    policy = a.digest("artificial policy")
    s = dict(t=0., steps=0, x=[0., 0., 0.], p=[1., 0., 0.], q=[0.]*6,
             monitor={}, pending_trial=None, minimum_gap=float("inf"), history=[])
    full = dict(state=s, state_sha256=a.digest(s))
    root = a.digest("artificial root")
    header = {k:v for k,v in s.items() if k != "history"}
    header.update(history_node=a.boundary_history_node(full, a.digest), history_length=0)
    def branch(role, parent, before, t, x):
        after = copy.deepcopy(before)
        after.update(t=t, steps=before["steps"]+1, x=[x,0.,0.], q=[x,0.,0.,0.,0.,0.])
        token = a.state_token(parent, after, [])
        row = dict(time_s=t, dt_s=t-before["t"], position_m=after["x"], orientation=after["p"], velocity_generalized=after["q"])
        return dict(branch_id=role, macro_index=0, role=role, input_state_token=parent,
                    output_state_token=token, before_state=before, after_state=after,
                    history_parent=parent, history_delta=[], rows=[row], work_rows=1,
                    requested_dt_s=t-before["t"],target_time_s=t,
                    cap_entries=[dict(trigger_grain_ids=[],original_selected_dt_s=1.)])
    c = branch("C",root,copy.deepcopy(header),1.,.25)
    f1 = branch("F1",root,copy.deepcopy(header),.5,.125)
    f2 = branch("F2",f1["output_state_token"],copy.deepcopy(f1["after_state"]),1.,.375)
    after = {k:v for k,v in f2["after_state"].items() if k not in {"history_node","history_length"}}
    after["history"] = []
    final = dict(state=after,state_sha256=a.digest(after))
    before_ledger = dict(used_work_rows=0, used_integration_records=1, known_audited_rows=0,
                         known_unaccepted_rows=0, unknown_reserved_rows=0, terminal_failure=None,
                         reservation=dict(record_id="artificial",maximum_rows=3),seen_record_ids=["artificial"])
    after_ledger = copy.deepcopy(before_ledger)
    after_ledger.update(used_work_rows=3,known_audited_rows=3,reservation=None)
    decision = dict(action="commit_literal_halves",position_defect_m=.125,director_defect=0.,
                    velocity_defect_over_U=.125,scaled_defect=.125,next_h_s=1.,next_halving_depth=0,
                    committed_tokens=[f1["output_state_token"],f2["output_state_token"]])
    packet = dict(schema="paper1.full-state-stepdoubling.packet.v1",policy_sha256=policy,
                  input_full_checkpoint_sha256=a.digest(full),output_full_checkpoint_sha256=a.digest(final),
                  input_state=header,input_state_token=root,output_state_token=f2["output_state_token"],
                  work_branches=[c,f1,f2],carried_branches=[],committed_branch_ids=["F1","F2"],
                  trials=[dict(macro_index=0,trial_index=0,origin_state_token=root,branch_ids=["C","F1","F2"],
                               depth=0,h_s=1.,original_selected_cap_s=1.,decision=decision)],
                  cursor_before=dict(phase="idle"),cursor_after=dict(phase="idle"),
                  ledger_before=before_ledger,ledger_after=after_ledger,reservation=before_ledger["reservation"])
    return packet, limits, full, final


def synthetic_branch_callback(branch):
    # Deliberately synthetic: this bypasses mechanics for composition tests and
    # cannot be used by the actual source-bound native qualification wrapper.
    return dict(stencil_verified=True,caps_replayed=True,history_delta_verified=True,raw_observation_verified=True,
                prior_admission_authenticated=True)


class Controls(unittest.TestCase):
    def audit_fake_native(self, packet, limits, runtime, before=None):
        import check_full_state_integration_adapter_v1 as fake
        view=a.normalized_packet_view(packet)
        return a.audit_packet(view,asdict(limits),input_full_checkpoint=None if before is None else before["physical_checkpoint"],
                              output_full_checkpoint=packet["checkpoint"]["physical_checkpoint"],original_digest=fake.a.original_digest,
                              audit_branch=synthetic_branch_callback,expected_input_state_token=packet["input_state_token"],
                              expected_policy_sha256=limits.numerical_binding,initial_spec=runtime.spec,
                              expected_previous_receipt_sha256="2"*64 if before is not None else None)

    def run_packet(self, packet=None):
        p,l,b,e=fixture()
        return a.audit_packet(packet or p,l,input_full_checkpoint=b,output_full_checkpoint=e,
                              original_digest=a.digest,audit_branch=synthetic_branch_callback,
                              expected_input_state_token=p["input_state_token"],expected_policy_sha256=p["policy_sha256"])

    def test_complete_literal_half_chain_and_all_work(self):
        result=self.run_packet()
        self.assertEqual(result["all_work_rows"],3)
        self.assertEqual(result["committed_branch_ids"],["F1","F2"])
        self.assertFalse(result["native_qualification_admitted"])

    def test_shadow_promotion_rejected(self):
        p,*_=fixture();p["committed_branch_ids"]=["C"]
        with self.assertRaises(ValueError):self.run_packet(p)

    def test_missing_shadow_rows_rejected(self):
        p,*_=fixture();p["work_branches"].pop(0)
        with self.assertRaises(ValueError):self.run_packet(p)

    def test_rehashed_history_token_does_not_change_full_history(self):
        p,*_=fixture();p["work_branches"][2]["history_delta"]=[[99.]]
        with self.assertRaises(ValueError):self.run_packet(p)

    def test_source_policy_binding_cannot_be_replaced(self):
        p,*_=fixture();p["policy_sha256"]=a.digest("different")
        with self.assertRaises(ValueError):self.run_packet(p)

    def test_original_stencil_failure_is_not_accuracy_retry(self):
        p,l,b,e=fixture()
        with self.assertRaises(ValueError):
            a.audit_packet(p,l,input_full_checkpoint=b,output_full_checkpoint=e,
                           original_digest=a.digest,audit_branch=lambda _:dict(stencil_verified=False),
                           expected_input_state_token=p["input_state_token"],expected_policy_sha256=p["policy_sha256"])

    def test_all_six_q_components_and_signed_director(self):
        p,l,*_=fixture();c,f1,f2=p["work_branches"]
        origin=a._endpoint(c["before_state"],c["input_state_token"],c["input_state_token"])
        ends=[a._endpoint(v["after_state"],v["output_state_token"],v["input_state_token"]) for v in (c,f1,f2)]
        ends[2]["p"]=[-1.,0.,0.];ends[2]["q"][5]=2.
        result=a.independent_decision(l,origin,*ends,h_s=1.,selected_cap_s=1.,depth=0)
        self.assertEqual(result["director_defect"],2.)
        self.assertGreater(result["velocity_defect_over_U"],2.)
        self.assertEqual(result["action"],"discard_all_and_halve")

    def test_half_state_cap_replayed_not_origin_cap(self):
        branch=dict(before_state=dict(t=.5,steps=1,x=[0.]*3,p=[1.,0.,0.],q=[0.]*6,pending_trial=None),
                    after_state=dict(t=.625,steps=2,x=[0.]*3,p=[1.,0.,0.],q=[0.]*6),
                    rows=[dict(time_s=.625,dt_s=.125,position_m=[0.]*3,orientation=[1.,0.,0.],velocity_generalized=[0.]*6)],
                    cap_entries=[dict(time_s=.5,steps=1,velocity_generalized=[0.]*6,near=[],base_dt_s=.125,
                                      untruncated_dt_s=.125,original_selected_dt_s=.125,trigger_grain_ids=[],requested_dt_s=.5,target_time_s=1.,actual_trial_dt_s=.125)],
                    sweep_certificates=[dict(dt_s=.125)],target_time_s=1.,requested_dt_s=.5,result_status="paused_checkpoint")
        called=[]
        def replay(state,*args):
            called.append(state["t"])
            return {k:v for k,v in branch["cap_entries"][0].items() if k not in {"requested_dt_s","target_time_s","actual_trial_dt_s"}}
        with patch.object(a,"reconstruct_original_cap",replay):
            self.assertTrue(a.audit_compact_branch_caps(branch,dict(horizon_s=2.),None,None)["passed"])
            branch["cap_entries"][0]["actual_trial_dt_s"]=.5
            with self.assertRaises(ValueError):a.audit_compact_branch_caps(branch,dict(horizon_s=2.),None,None)
        self.assertEqual(called,[.5,.5])

    def test_zero_negative_and_known_overrun_accounting(self):
        p,*_=fixture();before=p["ledger_before"]
        for count in (0,4):
            after=copy.deepcopy(before);after.update(used_work_rows=count,known_unaccepted_rows=count,
                                                   reservation=None,terminal_failure="preserved negative")
            self.assertEqual(a.audit_accounting(before,after,p["reservation"],count,disposition="known_unaccepted")["charged_rows"],count)

    def test_known_work_cannot_be_relabelled_unknown(self):
        p,*_=fixture();after=copy.deepcopy(p["ledger_after"])
        after.update(known_audited_rows=0,unknown_reserved_rows=3,terminal_failure="unknown")
        with self.assertRaises(ValueError):a.audit_accounting(p["ledger_before"],after,p["reservation"],4,disposition="unknown")

    def test_original_infinity_sentinel_not_nan(self):
        self.assertEqual(a.digest(dict(minimum_gap=float("inf"))),r.digest(dict(minimum_gap=float("inf"))))
        with self.assertRaises(ValueError):a.digest(dict(q=[float("nan")]))

    def test_first_active_uses_accepted_halves_and_even_split(self):
        p,*_=fixture();p["work_branches"][0]["cap_entries"][0]["trigger_grain_ids"]=[15]
        self.assertIsNone(a.first_accepted_selector(p))
        journal=[dict(role="F1" if i%2==0 else "F2",trigger_grain_ids=[15] if i==5 else []) for i in range(8)]
        self.assertEqual(r.first_active_split(journal,8),dict(N=8,j=4,successor_accepted_rows=4,first_accepted_trigger_index=5))
        journal[0]["trigger_grain_ids"]=[15]
        with self.assertRaises(ValueError):r.first_active_split(journal,8)
        journal[0]["role"]="C"
        with self.assertRaises(ValueError):r.first_active_split(journal,8)

    def test_restart_comparison_excludes_only_declared_admin_identity(self):
        p,_,full,_=fixture()
        kwargs=dict(anchor="after_coarse",policy_sha256=p["policy_sha256"],physical_design_sha256=a.digest("physical"),
                    full_checkpoint=full,controller_cursor=dict(phase="after_coarse"),
                    all_trial_rows=[dict(q=[0.]*6)],committed_rows=[],cap_journal=[],work_rows=1,
                    original_digest=a.digest,actual_native_execution=False)
        first=r.observation(**kwargs,pending_reservation=dict(record_id="serial",maximum_rows=3))
        second=r.observation(**kwargs,pending_reservation=dict(record_id="split",maximum_rows=3))
        self.assertTrue(r.compare(first,second)["passed"])
        with self.assertRaises(ValueError):r.compare(first,second,native=True)
        second["controller_cursor_sha256"]=a.digest("changed")
        with self.assertRaises(ValueError):r.compare(first,second)

    def test_native_matrix_not_satisfied_by_preparation_or_mocks(self):
        contract=r.prepare_restart_contract(dict(policy_sha256=a.digest("policy"),adapter_source_sha256=a.digest("adapter")),a.digest("physical"))
        self.assertFalse(contract["numerical_launch_ready"])
        self.assertTrue(contract["native_execution_required"])
        with self.assertRaises(ValueError):r.require_complete_matrix([],a.digest("p"),a.digest("x"))

    def test_partial_coarse_cursor_is_retained_without_publication(self):
        p,l,b,_=fixture()
        p["work_branches"]=p["work_branches"][:1]
        p["trials"][0].update(branch_ids=["C"],decision=None)
        p["committed_branch_ids"]=[];p["output_state_token"]=p["input_state_token"]
        p["output_full_checkpoint_sha256"]=a.digest(b)
        p["cursor_after"]=dict(phase="after_coarse",origin_state_token=p["input_state_token"],branch_ids=["C"])
        p["ledger_after"].update(used_work_rows=1,known_audited_rows=1)
        result=a.audit_packet(p,l,input_full_checkpoint=b,output_full_checkpoint=b,
                              original_digest=a.digest,audit_branch=synthetic_branch_callback,
                              expected_input_state_token=p["input_state_token"],expected_policy_sha256=p["policy_sha256"])
        self.assertTrue(result["pending_controller_trial"])
        self.assertEqual(result["committed_branch_ids"],[])

    def test_carried_coarse_is_not_solved_or_charged_twice(self):
        p,l,b,e=fixture();c=p["work_branches"].pop(0)
        previous=a.digest("previous authenticated packet receipt")
        c["previous_packet_receipt_sha256"]=previous
        p["carried_branches"]=[c]
        p["cursor_before"]=dict(phase="after_coarse",branch_ids=["C"])
        p["ledger_before"].update(used_work_rows=1,known_audited_rows=1)
        p["ledger_before"]["reservation"]["maximum_rows"]=2
        result=a.audit_packet(p,l,input_full_checkpoint=b,output_full_checkpoint=e,
                              original_digest=a.digest,audit_branch=synthetic_branch_callback,
                              expected_input_state_token=p["input_state_token"],expected_policy_sha256=p["policy_sha256"],
                              expected_previous_receipt_sha256=previous)
        self.assertEqual(result["all_work_rows"],2)
        self.assertEqual(result["committed_branch_ids"],["F1","F2"])

    def test_native_semantic_ledger_does_not_hide_shadow_work(self):
        p,l,b,e=fixture()
        p["ledger_before"]=dict(all_work_rows=0,accepted_half_rows=0,rejected_trials=0)
        p["ledger_after"]=dict(all_work_rows=3,accepted_half_rows=2,rejected_trials=0)
        p["reservation"]=dict(record_id="native",maximum_work_rows=3);p["work_rows"]=3
        def check():
            return a.audit_packet(p,l,input_full_checkpoint=b,output_full_checkpoint=e,
                                  original_digest=a.digest,audit_branch=synthetic_branch_callback,
                                  expected_input_state_token=p["input_state_token"],expected_policy_sha256=p["policy_sha256"])
        self.assertTrue(check()["accounting"]["external_actual_call_and_case_shared_ledger_required"])
        p["ledger_after"]["all_work_rows"]=2
        with self.assertRaises(ValueError):check()

    def test_new_macro_recovers_fresh_original_cap_not_permanent_ratchet(self):
        p,l,b,_=fixture()
        c,f1,f2=p["work_branches"]
        for branch,t,request in ((c,.5,.5),(f1,.25,.25),(f2,.5,.25)):
            branch["after_state"]["t"]=t;branch["rows"][0]["time_s"]=t
            branch["requested_dt_s"]=request;branch["target_time_s"]=t
        f2["before_state"]=copy.deepcopy(f1["after_state"])
        c["output_state_token"]=a.state_token(c["input_state_token"],c["after_state"],[])
        f1["output_state_token"]=a.state_token(f1["input_state_token"],f1["after_state"],[])
        f2["input_state_token"]=f1["output_state_token"];f2["history_parent"]=f1["output_state_token"]
        f2["output_state_token"]=a.state_token(f2["input_state_token"],f2["after_state"],[])
        c["cap_entries"][0]["original_selected_dt_s"]=.5
        first=p["trials"][0];first.update(h_s=.5,original_selected_cap_s=.5)
        first["decision"].update(next_h_s=.5,committed_tokens=[f1["output_state_token"],f2["output_state_token"]])
        origin=f2["output_state_token"];old=f2["after_state"]
        def extra(role,parent,before,t,x,request):
            after=copy.deepcopy(before);after.update(t=t,steps=before["steps"]+1,x=[x,0.,0.],q=[x,0.,0.,0.,0.,0.])
            return dict(branch_id="second_"+role,macro_index=1,role=role,input_state_token=parent,
                        output_state_token=a.state_token(parent,after,[]),before_state=copy.deepcopy(before),after_state=after,
                        history_parent=parent,history_delta=[],rows=[dict(time_s=t)],work_rows=1,
                        requested_dt_s=request,target_time_s=t,cap_entries=[dict(original_selected_dt_s=1.,trigger_grain_ids=[])])
        c2=extra("C",origin,old,1.5,.5,1.)
        a2=extra("F1",origin,old,1.,.5,.5)
        b2=extra("F2",a2["output_state_token"],a2["after_state"],1.5,.625,.5)
        choice=dict(action="commit_literal_halves",position_defect_m=.125,director_defect=0.,velocity_defect_over_U=.125,
                    scaled_defect=.125,next_h_s=1.,next_halving_depth=0,committed_tokens=[a2["output_state_token"],b2["output_state_token"]])
        p["trials"].append(dict(macro_index=1,trial_index=0,depth=0,h_s=1.,original_selected_cap_s=1.,
                                origin_state_token=origin,branch_ids=[c2["branch_id"],a2["branch_id"],b2["branch_id"]],decision=choice))
        p["work_branches"].extend([c2,a2,b2]);p["committed_branch_ids"].extend([a2["branch_id"],b2["branch_id"]])
        final_state={k:v for k,v in b2["after_state"].items() if k not in {"history_node","history_length"}}
        final_state["history"]=[];e=dict(state=final_state,state_sha256=a.digest(final_state))
        p["output_state_token"]=b2["output_state_token"];p["output_full_checkpoint_sha256"]=a.digest(e)
        p["reservation"]["maximum_rows"]=6;p["ledger_after"].update(used_work_rows=6,known_audited_rows=6)
        result=a.audit_packet(p,l,input_full_checkpoint=b,output_full_checkpoint=e,original_digest=a.digest,
                              audit_branch=synthetic_branch_callback,expected_input_state_token=p["input_state_token"],
                              expected_policy_sha256=p["policy_sha256"])
        self.assertEqual(result["all_work_rows"],6)

    def test_nonzero_clock_uses_literal_endpoint_durations_without_alignment(self):
        for time,cap in ((.15,1e-6),(.15280694670867345,6.245e-7),(.4,1e-6)):
            result=a.choose_clock_interval(time,cap,1e-15)
            self.assertEqual(result["h_s"],cap)
            self.assertEqual(time+result["h_s"],result["end_s"])
            self.assertEqual(time+result["first_requested_dt_s"],result["middle_s"])
            self.assertEqual(result["middle_s"]+result["second_requested_dt_s"],result["end_s"])
            self.assertLessEqual(abs(result["first_requested_dt_s"]-result["second_requested_dt_s"]),result["endpoint_roundoff_bound_s"])
        with self.assertRaises(ValueError):a.choose_clock_interval(1e30,1e-20,1e-21)

    def test_consumer_actual_compiled_fake_packet_interface(self):
        import check_full_state_integration_adapter_v1 as fake
        runtime,limits,_=fake.make_runtime()
        packet=fake.packet(runtime,limits,rows=2)
        result=self.audit_fake_native(packet,limits,runtime)
        self.assertEqual(result["all_work_rows"],3)
        self.assertEqual(len(result["committed_branch_ids"]),2)
        self.assertFalse(result["native_qualification_admitted"])

    def test_consumer_compiled_fake_pending_pair_restart(self):
        import check_full_state_integration_adapter_v1 as fake
        for phase in ("C_done","F1_done"):
            runtime,limits,_=fake.make_runtime()
            left=fake.packet(runtime,limits,phase=phase,rows=2)
            self.assertTrue(self.audit_fake_native(left,limits,runtime)["pending_controller_trial"])
            before=fake.a.controller_checkpoint(left)
            right=fake.packet(runtime,limits,before,rows=2)
            result=self.audit_fake_native(right,limits,runtime,before)
            self.assertFalse(result["pending_controller_trial"])
            self.assertEqual(left["work_rows"]+right["work_rows"],3)

    def test_retained_original_terminal_full_history_codec_only(self):
        import check_full_state_integration_adapter_v1 as fake
        import run_core_v2 as original
        root=Path(__file__).resolve().parents[1]
        receipt=root/'paper1_runs/full_horizon_timecap_20261016/final_execution_receipt_01/results.json'
        expected='d23b764b5d5c3769ee2607aca7c0107e424352641306b6575a9b2522f943bf1f'
        self.assertEqual(a.file_sha(receipt),expected)
        completion=json.loads(receipt.with_name('completion.json').read_text())
        self.assertEqual(completion['results_sha256'],expected)
        self.assertIs(completion['passed'],True)
        closed=json.loads(receipt.read_text())
        self.assertIs(closed['passed'],True)
        self.assertIs(closed['all_exact_owned_identities_retired'],True)
        ref=root/'paper1_runs/full_horizon_timecap_20261016/levels/f0p03125/recoverable/checkpoint.json'
        paths=[ref,ref.with_name('checkpoint.payload.json.xz'),ref.with_name('checkpoint.payload.json.seal.json')]
        consumed={str(path):closed['artifacts'][str(path)] for path in paths}
        a.verify_mapping(consumed)
        full=original.DOC.read(ref)
        self.assertEqual(original.s.api.digest(full),json.loads(ref.read_text())['document_sha256'])
        result=r.retained_history_control(full,original_digest=original.s.api.digest,
                    history_store_type=fake.a.HistoryStore,state_token_function=fake.a.state_token,
                    reject_unqualified_checkpoint=fake.a.validate_outer_checkpoint_admission,
                    new_policy_binding=a.digest('fixture-new-policy-NOT-an-authority'),
                    adapter_source_sha256=a.file_sha(fake.a.__file__))
        self.assertGreater(result['history_length'],10000)
        self.assertFalse(result['checkpoint_resumed'])
        self.assertEqual(result['native_calls'],0)
        a.verify_mapping(consumed)
        print('RETAINED_HISTORY_CODEC_ONLY_CONTROL='+json.dumps(dict(result,consumed_files=consumed,closure_sha256=expected),sort_keys=True))

    def test_actual_mechanical_factory_source_association_without_call(self):
        # Construct the actual original-function bridge, never invoke a stencil
        # on a target trajectory and never construct an integration runtime.
        root=Path(__file__).resolve().parents[1]
        design=root/'paper1_designs/full_horizon_timecap_20261016/physical_cases_01.json'
        physical=json.loads(design.read_text())
        adapter=a.create_original_mechanical_adapter(physical['cases'][0]['spec'],
                    'source-association-fixture-NOT-authority',None,a.file_sha(design),physical['minimum_gap_semantics'])
        self.assertIs(adapter.original_stencil_adapter_marker,a._ORIGINAL_STENCIL_ADAPTER_MARKER)
        self.assertFalse(adapter.native_qualification_claimed)
        a.verify_mapping(adapter.source_files)
        self.assertEqual(len(adapter.original_stencil_sources),4)

    def test_consumer_cap_mismatch_has_no_fabricated_defect(self):
        import check_full_state_integration_adapter_v1 as fake
        runtime,limits,backend=fake.make_runtime()
        runtime.selector=SimpleNamespace(select=lambda base,near,q,ell,speed,untruncated_dt:
                (min(base,.0001) if getattr(backend.capture,'role',None)=='F2' else base,[]))
        packet=fake.packet(runtime,limits,rows=2)
        result=self.audit_fake_native(packet,limits,runtime)
        rejected=[t for t in packet['trials'] if t['decision']['action']=='discard_all_and_halve']
        self.assertTrue(rejected)
        for trial in rejected:
            self.assertEqual(trial['decision']['reason'],'cap_mismatch')
            self.assertIsNone(trial['decision']['position_defect_m'])
            self.assertIsNone(trial['decision']['scaled_defect'])
        self.assertEqual(result['all_work_rows'],packet['work_rows'])


if __name__ == "__main__":
    unittest.main(verbosity=2)
