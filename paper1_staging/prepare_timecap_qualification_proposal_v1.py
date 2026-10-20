"""Create-only budget proposal; no solver, integration, launcher or authority.

The consumer is a future approved, configuration-driven full-path scheduler
around the frozen original transport transaction and verified timecap scope.
"""
from pathlib import Path
from datetime import datetime
import copy,math,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_core_v2 as shared
import contact_onset_timecap_v1 as selector
import audit_onset_timecap_v1 as independent
import compare_core_v2 as comparator
s=shared.s;ROOT=s.ROOT;SELF=Path(__file__).resolve()
DEST=ROOT/'paper1_designs/full_horizon_timecap_20261016'
PROPOSAL=DEST/'proposal_01.json'
OLD_NAMES=('p1_i0_fibre_u0p5_20261014','p1_i0_fibre_u0p5_fine_20261014','p1_i0_fibre_u0p5_accuracy_recovery_20261014')


def main():
    s.environment();s.require(not DEST.exists(),'Create-only proposal, never overwrite frozen evidence')
    local_root=ROOT/'paper1_runs/onset_timecap_20261016'
    receipt=s.fields.sealed(local_root/'retirement_01/results.json')
    s.require(receipt['passed'] and receipt['local_screen_passed'] and receipt['all_exact_owned_identities_retired'],'Authenticated closed local screen')
    s.api.verify_mapping(receipt['source_files']);s.api.verify_mapping(receipt['physical_inputs']);s.api.verify_mapping(receipt['artifacts'])
    s.require(receipt['cumulative_saved_steps']==5644840 and receipt['cumulative_conservative_calls']==1156,'Exact original published ledger preserved')
    inputs=dict(receipt['physical_inputs']);sources=dict(receipt['source_files'])
    def bind(path):inputs[str(path)]=s.sha(path)
    for sub in ('evaluation_01','retirement_01','final_disposition_01'):
        bind(local_root/sub/'results.json');bind(local_root/sub/'completion.json')
    baselines=[]
    for factor,name in zip((.125,.0625,.03125),OLD_NAMES):
        root=ROOT/'paper1_runs'/name;design=ROOT/'paper1_designs'/name
        final=s.fields.sealed(root/'final_disposition_01/results.json')
        retired=s.fields.sealed(root/'retirement_01/results.json')
        s.require(final['passed'] and final['native_complete'] and retired['passed'],'Closed original complete physical paths')
        for sub in ('final_disposition_01','retirement_01'):
            bind(root/sub/'results.json');bind(root/sub/'completion.json')
        bind(design/'physical_cases_01.json');bind(design/'design_01.json')
        old=s.read(design/'design_01.json');s.api.verify_mapping(old['source_files']);s.api.verify_mapping(old['physical_inputs'])
        identities=[]
        for file in ('controller_01/launch.json','controller_01/worker_launch.json','worker_launch.json'):
            launch=s.read(root/file);s.require(s.identity(launch)['retired'],'Every original exact process remains retired');bind(root/file)
            identities.append(str(root/file))
        restart_steps=0
        for label in ('serial','split_a','split_b'):
            path=root/'records'/label/'guard_completion/results.json';v=s.fields.sealed(path)
            s.require(v['passed'],'Historical original restart physics');restart_steps+=v['saved_steps'];bind(path)
        s.require(restart_steps==final['discarded_diagnostic_steps']==512,'Historical restart calls and saved steps')
        start=datetime.fromisoformat(s.read(root/'controller_01/launch.json')['utc'])
        end=datetime.fromisoformat(s.read(root/'controller_01/exit.json')['utc'])
        baselines.append(dict(factor=factor,physical_steps=final['accepted_physical_steps'],restart_steps=restart_steps,
            production_calls=len(final['production_labels']),restart_calls=3,complete_worker_wall_hours=(end-start).total_seconds()/3600,
            retained_bytes=sum(x.stat().st_size for x in root.rglob('*') if x.is_file()),root=str(root)))
    prior_local=ROOT/'paper1_runs/local_common_state_20261015/evaluation_01/results.json'
    prior_onset=ROOT/'paper1_runs/onset_common_state_20261015/evaluation_01/results.json'
    later=[s.fields.sealed(x) for x in (prior_local,prior_onset)]
    s.require(all(v['passed'] for v in later),'Closed development diagnostics')
    for path in (prior_local,prior_onset):bind(path)
    total_core_steps=sum(x['physical_steps']+x['restart_steps'] for x in baselines)+sum(v['discarded_diagnostic_steps'] for v in later)+receipt['discarded_diagnostic_steps']
    reported_calls=sum(x['production_calls'] for x in baselines)+sum(v['conservative_call_charges'] for v in later)+receipt['conservative_call_charges']
    s.require(total_core_steps==5644840 and reported_calls==1156,'Reconstructed frozen core ledger')
    # This screen had a separate authorization and no logical_core_id. It is
    # disclosed separately and voluntarily included in the prospective ceiling.
    screen_root=ROOT/'paper1_runs/initial_cost_screen_20261013'
    screen_steps=screen_calls=0
    for label in ('serial','split_a','split_b','cost','fine'):
        path=screen_root/'records/case_01'/label/'guard_completion/results.json'
        v=s.fields.sealed(path);s.require(v['passed'],'Separately authorized screen record');bind(path)
        screen_steps+=v['saved_steps'];screen_calls+=1
    s.require(screen_steps==3072 and screen_calls==5,'Explicit separate same-condition screen scope')
    baseline_steps=total_core_steps+screen_steps;baseline_calls=reported_calls+9+screen_calls
    s.require((baseline_steps,baseline_calls)==(5647912,1170),'Prospective conservative combined ledger')
    case_rows=[]
    for factor,step_cap,call_cap in ((.125,800000,170),(.0625,1600000,340),(.03125,3200000,680)):
        case,_,_=s.factory.load_case('p1_i0_rigid_prolate_ar4_u0p5',.01,factor,'core')
        case['id']+='__timecap_full_qualification';case['role']='full_path_timecap_qualification_pending_original_gates'
        case['spec']['case_id']=case['id']
        case_rows.append(dict(factor=factor,case=case,maximum_new_production_steps=step_cap,maximum_production_calls=call_cap))
    signatures=[comparator.physical_signature(x['case']['spec']) for x in case_rows]
    s.require(signatures[0]==signatures[1]==signatures[2],'Same original full physics, initial state and exposure')
    for left,right in zip(case_rows,case_rows[1:]):
        s.require(all(right['case']['spec']['config']['numerics'][k]==left['case']['spec']['config']['numerics'][k]/2 for k in s.factory.SCALED_CONTROLS),'Four original controls exactly halve')
    horizon=case_rows[0]['case']['spec']['horizon_s'];s.require(horizon==.9364396280429768,'Full frozen0.01PV exposure')
    production_cap=sum(x['maximum_new_production_steps'] for x in case_rows)
    diagnostic_cap=32768
    # Actual first triggered production record: N<=5000. Replaying serial N
    # versus j+(N-j) charges2N<=10000 per level, not a new production prefix.
    planned_diagnostics=3*512+3*10000+2*512+3*32
    diagnostic_calls=9+9+6+3
    new_cap=production_cap+diagnostic_cap
    max_calls=sum(x['maximum_production_calls'] for x in case_rows)+diagnostic_calls
    s.require(planned_diagnostics==32656<=diagnostic_cap and diagnostic_calls==27,'All fresh/trigger/handoff/smoke diagnostics bounded')
    s.require(baseline_steps+new_cap==11280680<=11300000,'Shared saved-step ceiling includes every prior scope and diagnostic')
    s.require(baseline_calls+max_calls==2387<=2400,'Shared integration-call ceiling includes every restart')
    total_retained=sum(x.stat().st_size for name in ('paper1_runs','paper1_designs','paper1_evaluations') for x in (ROOT/name).rglob('*') if x.is_file())
    free=shutil.disk_usage(ROOT).free;own=6*1024**3
    s.require(total_retained+own<20*1024**3 and free-own>20*1024**3,'No retention/free-reserve increase required for qualification')
    local_rates=[]
    for i in (0,1):
        branch=s.fields.sealed(local_root/'final_disposition_01/results.json')['branches'][i]
        first=local_root/'records'/branch['labels'][0];last=local_root/'records'/branch['labels'][-1]
        seconds=(datetime.fromisoformat(s.read(last/'timecap_guard/results.json')['utc'])-datetime.fromisoformat(s.read(first/'launch.json')['utc'])).total_seconds()
        local_rates.append(dict(factor=branch['factor'],complete_transaction_seconds_per_step=seconds/branch['new_steps'],scope='Local10ms loading interval, including inline independent selector audit and intercall gaps; not representative whole-path cost'))
    baseline_new_steps=sum(x['physical_steps'] for x in baselines)
    rate=max(x['complete_transaction_seconds_per_step'] for x in local_rates)
    # Keep the full independent post-exit replay, and explicitly reserve it.
    forecast_hours=baseline_new_steps*(rate+.0054+.0007)/3600
    for module in (selector,independent,comparator):sources[str(Path(module.__file__).resolve())]=s.sha(module.__file__)
    sources[str(SELF)]=s.sha(SELF);sources.update(comparator.SOURCE_FILES)
    s.api.verify_mapping(sources);s.api.verify_mapping(inputs)
    proposal=dict(schema='paper1.timecap-full-qualification-budget-proposal.v1',status='PENDING_HUMAN_BUDGET_APPROVAL',
        passed=True,dispatch_authorized=False,authorization_clock_created=False,new_transport_steps=0,new_native_solver_calls=0,
        logical_core_id='p1_i0_rigid_prolate_ar4_u0p5',goal='Qualify the fixed approaching-contact timecap over the full frozen exposure, then continue the existing12-case conditional mechanism study only from admitted evidence.',
        minimum_interpretation='A practical rounded three-level qualification ceiling, not a provable exact minimum or a guarantee of passing. The old527517-step bound funds only one coarse tail, not a fresh full-path reference comparison.',
        scope='Only this problematic fibre logical case receives higher cumulative limits. Other Paper1 case limits, total storage and physical assumptions are unchanged.',
        ledger=dict(frozen_core_saved_steps=total_core_steps,frozen_reported_production_local_call_counter=reported_calls,
            additional_historical_core_restart_calls=9,actual_core_integration_records=reported_calls+9,
            separately_authorized_same_condition_screen_saved_steps=screen_steps,separate_screen_integration_records=screen_calls,
            conservative_prospective_baseline_saved_steps=baseline_steps,conservative_prospective_baseline_integration_calls=baseline_calls,
            old_immutable_ledgers_edited=False,nonadvancing_contact_route_invocations_remain_separate=True),
        request=dict(saved_step_ceiling_before=6000000,saved_step_ceiling_after=11300000,saved_step_increase=5300000,
            integration_call_ceiling_before=1500,integration_call_ceiling_after=2400,integration_call_increase=900,
            maximum_new_saved_steps=new_cap,maximum_new_production_steps=production_cap,maximum_discarded_diagnostic_steps=diagnostic_cap,
            maximum_new_integration_calls=max_calls,maximum_diagnostic_integration_calls=diagnostic_calls,
            maximum_prospective_combined_saved_steps=baseline_steps+new_cap,maximum_prospective_combined_integration_calls=baseline_calls+max_calls,
            maximum_shared_wall_hours=36,maximum_numerical_windows=3,maximum_hours_per_numerical_window=12,
            one_shared_absolute_deadline_frozen_after_approval=True,no_automatic_deadline_or_budget_extension=True,
            maximum_new_output_bytes=own,unchanged_total_retention_bytes=20*1024**3,unchanged_free_reserve_bytes=20*1024**3,
            workers=1,threads=1,logical_cpu=14,maximum_unverified_records=1,steps_per_record=5000,native_seconds_per_record=45),
        controller=dict(enabled=True,policy=copy.deepcopy(selector.POLICY),source=str(Path(selector.__file__).resolve()),sha256=s.sha(selector.__file__),
            frozen_without_parameter_tuning=True,physical_equation_changes=[],accuracy_gate_changes=[],gap_changes=[],solver_route_changes=[]),
        full_exposure=dict(pore_volumes=.01,horizon_s=horizon,fresh_t0=True,original_initial_state=case_rows[0]['case']['spec']['initial_state'],
            old_prefix_or_local_tail_credit=False,local_common_fine_seed_cannot_become_independent_finer_fresh_path=True),
        levels=case_rows,execution_order=[.0625,.03125,'UNCHANGED_FULL_PATH_FINE_PAIR_GATES',.125,'UNCHANGED_FULL_PATH_COARSE_PAIR_GATES'],
        diagnostic_plan=dict(planned_upper_saved_steps=planned_diagnostics,initial_exact_restart='256 versus128+128 per fresh level; discard and reset original initial state',
            active_restart='At the first admitted production record with a selector trigger, pause dependent production. From its exact FULL input, compare serialN with j+(N-j), N<=5000, j=first trigger index>0. Require exact original production rows AND FULL checkpoint/history, and trigger in the split successor. Discard probes and restore the original production checkpoint. If qualification cannot meet these conditions, STOP; do not waive or add unbudgeted calls.',
            active_restart_max_discarded_steps_per_level=10000,active_restart_calls_per_level=3,
            handoff='At most two exact512-step restart checks at authenticated FULL checkpoint after a bounded numerical-window retirement; discard diagnostics. Matching birth AND exact command required for any stop.',
            smoke='At most32 discarded pretrigger rows per level, compared bitwise with old same-factor original rows; any mismatch or early trigger stops this smoke comparison without asserting equivalence.'),
        gates=copy.deepcopy(s.q.job.policy.GATES),
        evidence_plan='Reuse frozen original physics/raw transaction and the verified selector scope. Every production/diagnostic record needs unchanged independent physical, lossless raw/history and independent selector-policy audit before dependent dispatch. Authenticate fresh t0 ancestry with no inherited raw prefix. Retire exact process identities/logs and standalone FULL checkpoints. Complete post-exit policy/raw replay and original full-path observations/metrics/events stay inside the shared36h deadline; a closed12h numerical window is never implicitly extended.',
        outcome_policy=dict(fine_pair_failure='Stop dependent numerical/core dispatch; preserve all failures. No automatic finer factor or budget expansion.',
            fine_pair_pass='Permit the separately declared.125 full confirmation within the same shared envelope. Do not install the controller in successor core cases yet.',
            coarse_pair_pass='Both original adjacent full-pair gates pass: the.125 level may be eligible for this labelled case, pending final closure. Resume existing Paper1 case order only in a fresh bounded window under existing other-case limits.',
            coarse_pair_failure='Preserve the negative. Only.0625 with.03125 reference can remain per-case eligible; never promote.125. Stop successor core dispatch for explicit review rather than weakening any gate.',
            physical_evidence_source_restart_ledger_failure='Stop all dependent dispatch immediately; retain sealed/partial/known-unaccepted/unknown work separately.',
            no_automatic_publication_admission=True,no_asymptotic_order_or_population_claim=True),
        continue_paper1='Successful qualification can raise temporal case count1to2of12. Remaining10 core trajectories keep original shapes/flows/placements/exposure, per-case checks and resource caps. This proposal is not a promise that the entire remaining numerical dataset fits the current time/storage allowance; update the existing study forecast from accepted new cost evidence before the next bounded batch.',
        reuse_decision='No budget credit for old prefix/local path reuse: the all-prefix selector-inactivity proof and mixed-design full-ancestry assembler do not currently exist. Rebinding the common fine-state diagnostic checkpoint would bypass fresh-path evidence. Immutable field/geometry and code are reused.',
        cost_evidence=dict(original_full_paths=baselines,labelled_local_complete_transaction_rates=local_rates,
            baseline_fresh_physical_steps=baseline_new_steps,baseline_full_steps_plus_max_planned_diagnostics=baseline_new_steps+planned_diagnostics,
            no_adaptive_overhead_floor_combined_saved_steps=baseline_steps+baseline_new_steps+planned_diagnostics,
            post_exit_selector_replay_seconds_per_step_proxy=.0054,final_retirement_seconds_per_step_proxy=.0007,
            whole_batch_wall_hours_proxy=forecast_hours,forecast_is_not_guarantee=True,later_trigger_duty_and_contact_cost_unknown=True,
            why_not12h='Even two factor-specific tails alone forecast about13h production before prefix proof, restart and full replay. Three fresh full levels need a larger shared wall envelope while individual numerical windows remain at most12h.'),
        storage=dict(current_paper1_retained_bytes=total_retained,current_free_bytes=free,
            proxy_bytes_per_new_saved_step=54299637/71925,maximum_envelope_proxy_output_bytes=new_cap*54299637/71925,
            projected_total_using_hard_own_ceiling_bytes=total_retained+own,projected_free_using_hard_own_ceiling_bytes=free-own,
            hard_stop_if_any_limit_would_be_crossed=True,no_evidence_deletion_authorized=True),
        cheaper_first_attempt_not_recommended=dict(saved_step_ceiling=8100000,integration_call_ceiling=1700,
            explanation='Could bound only a first fresh.125/.0625 pair, whose repaired local pairing has not been tested and may fail. It does not reserve a third repaired full level or reliably remove the qualification barrier; therefore it is not the recommended whole qualification package.'),
        implementation_readiness='Budget/design proposal only. A configuration-driven full-path scheduling adapter reusing the frozen transaction/comparator must pass zero-step/source/ledger/negative controls before any approved numerical launch; no new force model. No PLAN, AUTH, launcher, output run or automation is created by this preparation.',
        source_files=sources,physical_inputs=inputs,utc=s.utc())
    shared.commit(PROPOSAL,proposal)
    shared.seal(DEST/'readiness_01',dict(passed=True,proposal_sha256=s.sha(PROPOSAL),new_transport_steps=0,new_native_solver_calls=0,
        arithmetic_verified=True,all_prior_costs_disclosed=True,resolved_three_level_physics_equal=True,original_gates_unchanged=True,
        no_budget_clock_or_launch_authority_created=True,source_files=sources,physical_inputs=inputs,utc=s.utc()))
    print('FULL_HORIZON_BUDGET_PROPOSED',s.sha(PROPOSAL),'NEW_STEPS',new_cap,'TOTAL_STEPS',baseline_steps+new_cap,'TOTAL_CALLS',baseline_calls+max_calls,
        'WALL_PROXY_HOURS',forecast_hours,flush=True)


if __name__=='__main__':main()
