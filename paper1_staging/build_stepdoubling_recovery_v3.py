"""Freeze remaining-resource derivation of a separate strict audit repair."""
from pathlib import Path
import copy
import importlib.util

ROOT=Path(__file__).resolve().parents[1]


def build():
    path=ROOT/'paper1_staging/run_stepdoubling_qualification_v3.py'
    spec=importlib.util.spec_from_file_location('_third_derived_recovery_design',path)
    run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
    run.environment();origin=ROOT/'paper1_designs/full_horizon_repair_20261018'
    original_path=origin/'qualification_proposal_01.json';original=run.read(original_path)
    ready=run.sealed(run.PREPARED,positive=True)
    run.need(not any(p.exists() for p in(run.OUT,run.AUTH,run.PLAN,run.PROPOSAL)),'separate derived repair before dispatch')
    p=copy.deepcopy(original)
    p.update(schema='paper1.odd-publication-recovery.derived-proposal.v3',passed=True,utc=run.utc(),
        status='STRICT_EVIDENCE_ADAPTER_REPAIR_INSIDE_ORIGINAL_APPROVAL',
        original_proposal_file=str(original_path),original_proposal_sha256=run.sha(original_path),
        original_scope=original['required_human_approval_scope'],scope_remaining=run.approval_scope(),
        required_human_approval_scope=run.approval_scope(),baseline=run.BASELINE,
        original_approval_sha256=run.sha(run.APPROVAL),original_clock_sha256=run.sha(run.CLOCK),
        initial_closure_sha256=ready['initial_closure_sha256'],diagnosis_sha256=ready['diagnosis_sha256'],
        previous_closure_sha256=ready['previous_closure_sha256'],previous_diagnosis_sha256=ready['previous_diagnosis_sha256'],
        source_files=ready['source_files'],physical_inputs=ready['physical_inputs'],
        evidence_files=ready['evidence_files'],historical_evidence_files=ready['historical_evidence_files'],
        implementation_change='Strict common canonical representation of native trial/cursor decisions plus complete authenticated C/F1/F2 carry semantics for odd F1 publication and exactly-once pending F2 publication. Physical equations/gates and all independent branch mechanics/caps/history checks remain mandatory. Adapter only selects the new module-private original mechanical factory; no integration math changes.',
        all_failed_attempts_preserved=True,new_human_approval_claimed=False,new_clock_created=False,
        required_human_approval_scope_is_legacy_schema_name_for_remaining_derived_scope=True,
        original_failed_unknown_reservation_preserved=True,
        cumulative_prior_conservative_charge=dict(all_work_rows=2787,integration_records=16,nonadvancing_warm_invocations=4,numerical_windows=2),
        prior_work_separation=dict(online_audited_discarded_rows=2752,known_unaccepted_rows=3,original_unknown_reserved_rows=32),
        cumulative_limits_before=original['cumulative_limits_after'],cumulative_limits_after=original['cumulative_limits_after'],
        timing='SAME original start2026-10-18T19:43:33.769535+00:00, numerical cutoff2026-10-23T23:43:33.769535+00:00, absolute end2026-10-24T07:43:33.769535+00:00; no reset. At most9 remaining numerical windows<=12h after2 spent. Preparation consumes original clock.',
        approval_reason='Equation-preserving implementation/evidence-adapter repair within the existing fixed human grant, not an accuracy/physics waiver or new resource/time request. Every earlier failed row stays preserved and charged; qualification restarts fresh t0.',
        authorization_created=False,clock_created=False,dispatch_authorized=False,new_native_calls=0,new_transport_steps=0)
    for file in(run.PREPARED,run.PREPARED.with_name('completion.json')):p['evidence_files'][str(file)]=run.sha(file)
    p['mandatory_native_checks']['original_setup']='At most2 original nonadvancing synthetic warm invocations per remaining window; at most18 after4 spent,0transport; standalone record charged separately.'
    p['resource_reasoning'].update(standalone_native_control_work_reserve=run.MAX_STANDALONE,
        standalone_record_reserve=run.MAX_STANDALONE_RECORDS,remaining_new_all_work_rows=run.MAX_WORK,
        remaining_new_integration_records=run.MAX_RECORDS,remaining_windows=run.MAX_WINDOWS,
        remaining_nonadvancing_warm_invocations=run.MAX_NONADVANCING_KERNEL_INVOCATIONS,
        all_initial_and_previous_work_charges_not_refunded=True,
        own_output_accounting='All THREE run trees together count against the SAME12GiB output cap;21GiB total/20GiB free unchanged.',
        caution='Original global18M/4000/132h/11windows/22warm unchanged. Remaining17,997,213/3984/9windows/18warm subtract all prior conservative charges. No extra probe, tolerance change, source overwrite or failed-record promotion.')
    run.validate_contract(p,run.read(run.PHYSICAL),ready)
    run.commit(run.PROPOSAL,p)
    print('DERIVED_RECOVERY3_PROPOSAL',run.sha(run.PROPOSAL),flush=True)


if __name__=='__main__':build()
