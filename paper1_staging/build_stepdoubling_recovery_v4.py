"""Freeze remaining-resource derivation of atomic actor JSON publication."""
from pathlib import Path
import copy
import importlib.util

ROOT=Path(__file__).resolve().parents[1]


def build():
    path=ROOT/'paper1_staging/run_stepdoubling_qualification_v4.py'
    spec=importlib.util.spec_from_file_location('_fourth_derived_recovery_design',path)
    run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
    run.environment();origin=ROOT/'paper1_designs/full_horizon_repair_20261018'
    original_path=origin/'qualification_proposal_01.json';original=run.read(original_path)
    ready=run.sealed(run.PREPARED,positive=True)
    run.need(not any(p.exists() for p in(run.OUT,run.AUTH,run.PLAN,run.PROPOSAL)),'separate derived repair before dispatch')
    p=copy.deepcopy(original)
    p.update(schema='paper1.atomic-journal-recovery.derived-proposal.v4',passed=True,utc=run.utc(),
        status='ATOMIC_CREATE_ONLY_JSON_PUBLICATION_REPAIR_INSIDE_ORIGINAL_APPROVAL',
        original_proposal_file=str(original_path),original_proposal_sha256=run.sha(original_path),
        original_scope=original['required_human_approval_scope'],scope_remaining=run.approval_scope(),
        required_human_approval_scope=run.approval_scope(),baseline=run.BASELINE,
        original_approval_sha256=run.sha(run.APPROVAL),original_clock_sha256=run.sha(run.CLOCK),
        initial_closure_sha256=ready['initial_closure_sha256'],diagnosis_sha256=ready['diagnosis_sha256'],
        previous_closure_sha256=ready['previous_closure_sha256'],previous_diagnosis_sha256=ready['previous_diagnosis_sha256'],
        source_files=ready['source_files'],physical_inputs=ready['physical_inputs'],
        evidence_files=ready['evidence_files'],historical_evidence_files=ready['historical_evidence_files'],
        implementation_change='Publish every immutable interprocess JSON only after exclusive sibling temp write, flush, fsync and close, using same-directory atomic create-if-absent hard-link; never overwrite a final path, parser-waive malformed complete JSON or change45s. Published temp cleanup only after same-file/byte proof; failed temp evidence retained. Integration adapter3/auditor2 and all model, cap, restart, original physics/accuracy policy are unchanged.',
        all_failed_attempts_preserved=True,new_human_approval_claimed=False,new_clock_created=False,
        required_human_approval_scope_is_legacy_schema_name_for_remaining_derived_scope=True,
        original_failed_unknown_reservation_preserved=True,
        cumulative_prior_conservative_charge=dict(all_work_rows=8233,integration_records=22,nonadvancing_warm_invocations=6,numerical_windows=3),
        prior_work_separation=dict(online_audited_discarded_rows=3392,known_unaccepted_rows=3,original_unknown_reserved_rows=32,previous_unknown_reserved_rows=4806,total_unknown_reserved_rows=4838),
        cumulative_limits_before=original['cumulative_limits_after'],cumulative_limits_after=original['cumulative_limits_after'],
        timing='SAME original start2026-10-18T19:43:33.769535+00:00, numerical cutoff2026-10-23T23:43:33.769535+00:00, absolute end2026-10-24T07:43:33.769535+00:00; no reset. At most8 remaining numerical windows<=12h after3 spent. Preparation consumes original clock.',
        approval_reason='Equation-preserving implementation/journal-publication repair within the existing fixed human grant, not an accuracy/physics waiver or new resource/time request. Every earlier failed row stays preserved and charged; qualification restarts fresh t0.',
        authorization_created=False,clock_created=False,dispatch_authorized=False,new_native_calls=0,new_transport_steps=0)
    for file in(run.PREPARED,run.PREPARED.with_name('completion.json')):p['evidence_files'][str(file)]=run.sha(file)
    p['mandatory_native_checks']['original_setup']='At most2 original nonadvancing synthetic warm invocations per remaining window; at most16 after6 spent,0transport; standalone record charged separately.'
    p['resource_reasoning'].update(standalone_native_control_work_reserve=run.MAX_STANDALONE,
        standalone_record_reserve=run.MAX_STANDALONE_RECORDS,remaining_new_all_work_rows=run.MAX_WORK,
        remaining_new_integration_records=run.MAX_RECORDS,remaining_windows=run.MAX_WINDOWS,
        remaining_nonadvancing_warm_invocations=run.MAX_NONADVANCING_KERNEL_INVOCATIONS,
        all_initial_and_previous_work_charges_not_refunded=True,
        own_output_accounting='All FOUR run trees together count against the SAME12GiB output cap;21GiB total/20GiB free unchanged.',
        caution='Original global18M/4000/132h/11windows/22warm unchanged. Remaining17,991,767/3978/8windows/16warm subtract all prior conservative charges. No extra probe, tolerance change, source overwrite or failed-record promotion.')
    run.validate_contract(p,run.read(run.PHYSICAL),ready)
    run.commit(run.PROPOSAL,p)
    print('DERIVED_RECOVERY4_PROPOSAL',run.sha(run.PROPOSAL),flush=True)


if __name__=='__main__':build()
