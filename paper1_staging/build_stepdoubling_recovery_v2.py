"""Freeze the implementation-only repair derivation, never a fresh human grant."""
from pathlib import Path
import copy
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def build():
    path = ROOT / 'paper1_staging/run_stepdoubling_qualification_v2.py'
    spec = importlib.util.spec_from_file_location('_derived_recovery_design', path)
    run = importlib.util.module_from_spec(spec); spec.loader.exec_module(run)
    run.environment()
    old_folder = ROOT / 'paper1_designs/full_horizon_repair_20261018'
    original_path = old_folder / 'qualification_proposal_01.json'
    original = run.read(original_path)
    ready = run.sealed(run.PREPARED, positive=True)
    run.need(not any(p.exists() for p in (run.OUT, run.AUTH, run.PLAN, run.PROPOSAL)), 'one separate prepared repair before dispatch')
    proposal = copy.deepcopy(original)
    proposal.update(schema='paper1.scope-order-recovery.derived-proposal.v2',
        status='EQUATION_PRESERVING_IMPLEMENTATION_REPAIR_DERIVED_FROM_EXISTING_APPROVAL',
        utc=run.utc(), original_proposal_file=str(original_path), original_proposal_sha256=run.sha(original_path),
        original_scope=original['required_human_approval_scope'], scope_remaining=run.approval_scope(),
        required_human_approval_scope=run.approval_scope(), baseline=run.BASELINE,
        original_approval_sha256=run.sha(run.APPROVAL), original_clock_sha256=run.sha(run.CLOCK),
        initial_closure_sha256=ready['initial_closure_sha256'], diagnosis_sha256=ready['diagnosis_sha256'],
        source_files=ready['source_files'], physical_inputs=ready['physical_inputs'],
        evidence_files=ready['evidence_files'], historical_evidence_files=ready['historical_evidence_files'],
        implementation_change='Only restore original observer/kernel-before-inner-wrapper scope entry and reverse exit, with original guards retained. Original physical loop, cap selection, step-doubling decisions, target clocks, raw/history, restart and full-path gates are unchanged.',
        separate_failed_attempt_preserved=True, same_clock_no_reset=True, new_human_approval_claimed=False,
        required_human_approval_scope_is_legacy_schema_name_for_remaining_derived_scope=True,
        original_failed_unknown_reservation_preserved=True,
        prior_conservative_charge=dict(all_work_rows=32,integration_records=2,nonadvancing_warm_invocations=2,numerical_windows=1),
        initial_actual_target_steps=0, initial_actual_target_outer_force_calls=0,
        actual_zero_target_count_basis='Strict sealed actual-trace/source control-flow diagnosis before reference integrator entry; no fabricated post-failure measured counter.',
        cumulative_limits_before=original['cumulative_limits_after'],
        cumulative_limits_after=original['cumulative_limits_after'],
        timing='SAME original 2026-10-18T19:43:33.769535+00:00 start; numerical cutoff2026-10-23T23:43:33.769535+00:00; absolute end2026-10-24T07:43:33.769535+00:00. No new or reset clock. At most10 remaining numerical windows of<=12h after one spent window. All new source preparation consumes this clock.',
        approval_reason='No new resource or time grant requested or inferred. This separately versioned administrative scope-order repair is necessary to execute the already approved original-stack qualification; the frozen failed attempt and all conservative charges remain retained.',
        authorization_created=False,clock_created=False,dispatch_authorized=False,new_native_calls=0,new_transport_steps=0)
    for p in (run.PREPARED, run.PREPARED.with_name('completion.json')):
        proposal['evidence_files'][str(p)] = run.sha(p)
    proposal['mandatory_native_checks']['original_setup'] = 'At most two original synthetic nonadvancing warm invocations per remaining window, at most20 remaining after2 spent; zero transport steps, one separately reserved standalone record per setup.'
    proposal['resource_reasoning'].update(standalone_native_control_work_reserve=run.MAX_STANDALONE,
        standalone_record_reserve=run.MAX_STANDALONE_RECORDS,
        remaining_new_all_work_rows=run.MAX_WORK,remaining_new_integration_records=run.MAX_RECORDS,
        remaining_windows=run.MAX_WINDOWS,remaining_nonadvancing_warm_invocations=run.MAX_NONADVANCING_KERNEL_INVOCATIONS,
        conservative_initial_charge_not_refunded=True,
        own_output_accounting='The unchanged12GiB own-output ceiling counts BOTH initial and recovery run trees; total21GiB/free20GiB remain shared and unchanged.',
        caution='The original approved maximum remains18M/4000/132h/11windows/22warm across both attempts. Remaining17,999,968/3,998/10windows/20warm subtract all initial conservative charges; native gates can still fail, stop incomplete or exhaust the same caps.')
    run.validate_contract(proposal, run.read(run.PHYSICAL), ready)
    run.commit(run.PROPOSAL, proposal)
    print('DERIVED_RECOVERY_PROPOSAL',run.sha(run.PROPOSAL),flush=True)


if __name__ == '__main__':
    build()
