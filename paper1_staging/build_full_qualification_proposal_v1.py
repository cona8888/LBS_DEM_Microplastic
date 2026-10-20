"""Create one reviewable complete-attempt proposal from closed preparation.

No human reply, clock, authorization, run directory or automation is created.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'paper1_designs/full_horizon_repair_20261018'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def build():
    path=ROOT/'paper1_staging/run_stepdoubling_qualification_v1.py'
    module_spec=importlib.util.spec_from_file_location('_prospective_driver',path)
    driver=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(driver)
    ready=driver.sealed(driver.PREPARED,positive=True)
    assert ready['all_required_interfaces_present'] and ready['dispatch_authorized'] is False
    assert not any(p.exists() for p in (driver.OUT,driver.AUTH,driver.PLAN,driver.APPROVAL,driver.CLOCK))
    physical=read(driver.PHYSICAL)
    base=FOLDER/'method_policy_qualification_01.json'
    clock=FOLDER/'method_policy_clock_amendment_01.json'
    levels=[]
    for case in physical['cases']:
        factor=case['factor'];scale=(factor/.125)**2
        raw_limits=dict(speed_m_s=case['spec']['config']['target_mean_interstitial_velocity_m_s'],
            position_defect_m=1e-12*scale,director_defect=1e-8*scale,
            velocity_defect_over_U=5e-5*scale,maximum_halvings=8,minimum_h_s=1e-14)
        numerical_binding=digest(dict(physical_design_sha256=sha(driver.PHYSICAL),
            base_policy_sha256=sha(base),clock_policy_sha256=sha(clock),factor=factor,limits=raw_limits))
        levels.append(dict(level_id=case['level_id'],factor=factor,
                           limits=dict(raw_limits,numerical_binding=numerical_binding)))
    evidence=dict(ready['evidence_files'])
    for p in (driver.PREPARED,driver.PREPARED.with_name('completion.json'),
              FOLDER/'budget_full_qualification_01.json'):
        evidence[str(p)]=sha(p)
    sources=dict(ready['source_files']);sources[str(Path(__file__).resolve())]=sha(__file__)
    proposal=dict(schema='paper1.full-state-stepdoubling.full-qualification-proposal.v1',
        status='SOURCE_AND_RESTART_PREPARATION_COMPLETE_AWAITING_EXPLICIT_BUDGET_AND_FRESH_TIME_APPROVAL',
        utc=datetime.now(timezone.utc).isoformat(),passed=True,
        logical_core_id='p1_i0_rigid_prolate_ar4_u0p5',
        user_request='Finish integration adapter and restart preparation, then provide a ready-to-approve full-horizon qualification budget; preserve physics and accuracy gates.',
        required_human_approval_scope=driver.approval_scope(),baseline=driver.BASELINE,
        original_accuracy_gates=driver.ORIGINAL_GATES,levels=levels,
        physical_equation_changes=[],gap_policy_changes=[],route_order_changes=[],
        numerical_policy_files={str(base):sha(base),str(clock):sha(clock)},
        source_files=sources,physical_inputs=ready['physical_inputs'],evidence_files=evidence,
        historical_evidence_files=ready['historical_evidence_files'],
        execution_order=['native source-bit/restart/physical/raw/controller qualification',
            'fresh_t0_f0p0625_to_first_accepted_pair_boundary_at_or_after_0p255',
            'fresh_t0_f0p03125_to_first_accepted_pair_boundary_at_or_after_0p255',
            'unchanged_source_frozen_tolerance_cost_and_retention_gate',
            'continue_SAME_accepted_f0p0625_and_f0p03125_paths_to_original_FULL_horizon',
            'numerical_worker_retirement_and_COMPLETE_independent_all_trial_replay',
            'ORIGINAL_complete_fine_pair_gate',
            'ONLY_IF_FINE_PAIR_PASSES_fresh_t0_f0p125_FULL_path_and_COMPLETE_replay',
            'ORIGINAL_complete_coarse_pair_gate','exact_owner_supervisor_retirement_and_separate_closed_log_exit_receipt'],
        what_is_prepared=dict(actual_original_loop_adapter=True,independent_original_mechanical_stencil_composition=True,
            raw_FULL_history_and_separate_controller_cursor=True,source_only_controls_and_saved_history_codec=True,
            native_execution_completed=False,native_restart_qualified=False,full_horizon_accuracy_repaired=False),
        mandatory_native_checks=dict(original_setup='At most two synthetic nonadvancing contact-kernel warm invocations per numerical window, maximum22 separately counted; zero saved/transport rows, one separately reserved standalone integration-record charge per setup. Original warm/configure code is preserved; these are not disguised as zero native calls.',
            old_bit_smoke='32 literal original single substeps versus32 compiled-adapter chained original substeps, never compare accepted new half steps with old nominal steps',
            initial='serial256 versus128+128 ACCEPTED half rows, exact all-trial data and FULL physical/controller/history state',
            staged=['after coarse shadow before F1','after F1 before F2','odd accepted-half publication after a completed decision'],
            first_actual_trigger='FIRST accepted F1/F2 selector trigger; largest legal positive even split before trigger; actual trigger in successor. No later easier event or waiver.',
            late_history='first admitted complete pair boundary at or after0.410s: serial256 versus128+128 accepted-half rows; this is a late FULL-history check, not a claim of another selector activation',
            every_window_handoff='authenticate exact retired prior worker and exact FULL/controller/raw ancestry; discarded serial/split check before continuing',
            finite_stops='physical/source/evidence/restart failure, impossible legal split, caps exhausted or missed common target stop dependent dispatch'),
        source_and_audit_schedule=dict(each_new_packet='freshly authenticate source/input bindings and every prior admission/completion chain; authenticate immediate parent raw/history prefix; independently replay ALL new trial mechanical/cap/raw/FULL composition before successor',
            production_ledger='Positive production packets must finish at an idle/after-rejection complete-decision boundary with no carried/pending branches. Seal bounded all/success/rejected/committed-half/coarse-shadow totals and a complete raw classification digest per record. Rebuild global counts from these immutable compact admissions; full post-exit replay independently rederives every aggregate from retained raw branches before either pair gate.',
            prior_raw_bytes='prior accepted raw bytes retain immutable inventory/digests and are ALL read and independently replayed post-exit, before any original pair or case admission; no O(record_count*all_old_raw_bytes) rehash per packet',
            mandatory_final='full original mechanical/raw/history/policy replay of every shadow, accepted-half, rejected and diagnostic branch; closed source/ledger/log authentication; missing/tampered older raw prevents pair/case admission',
            historical_baseline='all named older physical/input/raw evidence stays pinned in historical_evidence_files and is fully hashed at preparation, authorization and final closure. Fresh closed-baseline receipt/source bindings are checked per packet; these new paths consume no old physical prefix.',
            claim='new prospectively approved packet evidence composition, not global promotion of the old audit-chain prototype or a declaration that old frozen whole-record evidence code accepts new packets'),
        replay_reserve_rule=dict(seconds_per_unreplayed_all_work_row=.01,fixed_closure_seconds=3600,
            mandatory_measured_floor='max(0.01,2*maximum observed SAME-source independent replay seconds/work from standard production packets with work>=their reservation cap/2, and source-identical post-benchmark/full-level rates); can only increase within this fixed authority. Tiny standalone fixed costs are reserved separately, not extrapolated per row across the whole campaign.',
            qualification='0.01 is a conservative scheduling proxy relative to retained old0.00502, not a proved worst-case cost bound. Native prelude/prefix must establish a usable measured rate or stop.',
            numerical_outer_cutoff_hours=124,absolute_end_hours=132,minimum_final_tail_hours=8,
            completed_levels_replayed_before_next_dependent_level=True),
        prefix_forecast_rule=dict(online_observed_rate_multiplier=1.0,
            observed_bytes_per_work_multiplier=1.10,
            analysis_clock='Use ORIGINAL metrics from fresh t0 to the EARLIER actual accepted complete-pair boundary of the two prefixes, each first admitted record boundary at or after0.255s. Pass each actual prefix end to the original cursor; do not claim exact0.255s, clip native rows, interpolate a FULL state or change the full observation horizon.',
            production_rate='maximum actual wall/work rate over standard completed production packets with work>=reservation cap/2; every partial actual cost remains spent/accounted; standalone fixed costs separately bounded and fully charged',
            standalone_future_seconds='max(remaining standalone work*production rate, remaining standalone records*max(45, maximum observed standalone record wall))',
            post_benchmark='After exact numerical worker retirement, mechanically replay the LAST production packet with work>=its reservation cap/2 at or before the prefix. The selection is fixed before outcomes, never by passing or timing. Stop if none exists.',
            prefix_evidence='ALL prefix raw/history/trace hashes and all sealed online independent mechanical/policy decisions authenticated. No assertion that the entire prefix was mechanically replayed again.',
            final_evidence='ALL complete-path trial/diagnostic raw and mechanics receive full post-exit replay before either original pair gate; this requirement is unchanged.'),
        resource_reasoning=dict(practical_not_exact_minimum=True,
            success_all_work_rows=16800000,rejected_trial_work_reserve=1000000,standalone_native_control_work_reserve=200000,
            production_record_pool=3850,standalone_record_reserve=150,
            old_no_rejection_three_level_proxy_rows=15815475,
            old_online_plus_post_proxy_hours_at18M=104.70551948864932,
            chosen_shared_hours=132,new_own_output_GiB=12,total_retention_GiB_before=20,total_retention_GiB_after=21,minimum_free_GiB_unchanged=20,
            conservative_time_rounding='18M*(old online0.015920069085289555 + declared full-post reserve floor0.01) +3600s fixed closure is130.60034542644777h.132h is the smallest12-hour-rounded attempt envelope at these proxies; neither proxy is a proved new-controller worst-case bound.',
            change_from_unapproved_draft='132h replaces the earlier108h draft to include the declared conservative full-post replay reserve.12GiB own output and21GiB total retention replace the draft10/20GiB: old636B/work*18M is10.66GiB, or11.73GiB with the fixed10% byte margin. Combined with8.57GiB already retained,20GiB is insufficient at that proxy.21GiB is the smallest whole-GiB total ceiling accommodating12GiB own output at this snapshot. The20GiB free-disk reserve remains unchanged.',
            caution='Native cost/accuracy/storage rates of this new controller are unproved. The embedded screen must project all remaining current, finer/coarse, diagnostic, replay and closure work against these SAME ceilings; stop incomplete if it cannot fit. No automatic increase, deletion, tolerance change, fourth level or extra screen.'),
        cumulative_limits_before=dict(case_work_rows=11300000,case_records=2400,shared_work_rows=5632768,shared_records=1217,diagnostic_work_rows=147442,diagnostic_records=68),
        cumulative_limits_after=dict(case_work_rows=28312778,case_records=6174,shared_work_rows=22664866,shared_records=5004,diagnostic_work_rows=18146081,diagnostic_records=4066),
        scientific_claim='A bounded fresh complete-horizon numerical qualification of ONE labelled placement/packing. Both original complete pair gates AND final execution closure are needed for this fibre to become eligible for2/12. No asymptotic order, intrinsic true trajectory, population trend or remaining-ten-case dispatch follows.',
        timing='ONE fresh fixed132-hour absolute authority starts only after explicit approval and immutable clock creation; at most11 numerical windows each<=12h; never reset or resume a closed older window. All audits and exact retirement/log closure stay inside the same end.',
        approval_reason='This changes the resource ceilings you explicitly set and all earlier execution windows are closed. Source preparation grants no execution authority.',
        authorization_created=False,clock_created=False,dispatch_authorized=False,new_native_calls=0,new_transport_steps=0)
    driver.validate_contract(proposal,physical,ready)
    target=FOLDER/'qualification_proposal_01.json'
    driver.commit(target,proposal)
    print('FULL_QUALIFICATION_PROPOSAL_READY',sha(target),flush=True)


if __name__=='__main__':build()
