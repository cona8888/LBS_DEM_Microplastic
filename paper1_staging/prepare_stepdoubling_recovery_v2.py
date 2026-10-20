"""Prepare a separate scope-order repair under the unchanged approved grant.

Source/mock controls only. No authority, clock, force, warm call or process
launch for numerical work is created here. The initial negative is preserved.
"""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import os
import subprocess
import time
import re

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / 'paper1_staging'


def prepare():
    path = STAGING / 'run_stepdoubling_qualification_v2.py'
    spec = importlib.util.spec_from_file_location('_recovery_source_preparation', path)
    run = importlib.util.module_from_spec(spec); spec.loader.exec_module(run)
    run.environment()
    origin = ROOT / 'paper1_designs/full_horizon_repair_20261018'
    original = run.read(origin / 'qualification_proposal_01.json')
    old_ready = run.sealed(origin / 'preparation_qualification_01/results.json', positive=True)
    diagnosis_path = origin / 'failure_diagnosis_qualification_01/results.json'
    diagnosis = run.sealed(diagnosis_path, positive=True)
    initial_path = ROOT / 'paper1_runs/full_horizon_repair_20261018/final_execution_receipt_01/results.json'
    initial = run.sealed(initial_path, positive=True)
    run.need(run.sha(diagnosis_path) == 'bc5c1a5665b4dd8ad984465f4918d121cb8991f7e1d677e3e2d5ef742801916b', 'strict independent diagnosis')
    run.need(run.sha(initial_path) == 'ebed1438521447cb4fffda16a0784140118456487bc3b9626479b4907d5bce66', 'closed failed original attempt')
    run.need(diagnosis['zero_target_substeps_proved'] is True
             and diagnosis['target_transport_substeps'] == 0
             and diagnosis['target_outer_force_invocations'] == 0
             and diagnosis['conservative_shared_spent_charge']['all_work_rows'] == 32,
             'zero target dispatch proof never erases conservative reservation')
    run.need(initial['qualified'] is False and initial['closure_complete'] is True, 'retired negative, never case credit')
    run.need(not any(p.exists() for p in (run.OUT, run.AUTH, run.PLAN, run.PREPARED)), 'separate create-only preparation')
    identities = list(old_ready['prior_exact_process_identities'])
    for item in diagnosis['exact_retirement_after']:
        launch = item['launch']
        if not any((v['pid'], v['created'], v['command']) == (launch['pid'], launch['created'], launch['command']) for v in identities):
            identities.append(launch)
    retirement_before = run.assert_retired(identities)
    sources = dict(old_ready['source_files'])
    names = ['full_state_integration_adapter_v2.py', 'check_full_state_integration_adapter_v2.py',
             'run_stepdoubling_qualification_v2.py', 'launch_stepdoubling_qualification_v2.py',
             'check_stepdoubling_recovery_v2.py', 'monitor_stepdoubling_qualification_v2.py',
             'prepare_failure_diagnosis_qualification_v1.py', 'build_stepdoubling_recovery_v2.py',
             Path(__file__).name]
    for name in names:
        p = STAGING / name
        run.need(p.is_file(), 'actual prepared repair source ' + name)
        sources[str(p)] = run.sha(p)
    inputs = dict(old_ready['physical_inputs'])
    evidence = dict(original['evidence_files'])
    for p in (run.APPROVAL, run.CLOCK, origin / 'authorization_qualification_01.json',
              origin / 'design_qualification_01.json', diagnosis_path, diagnosis_path.with_name('completion.json'),
              initial_path, initial_path.with_name('completion.json')):
        evidence[str(p)] = run.sha(p)
    historical = run.merge_maps(old_ready['historical_evidence_files'], initial['artifacts'])
    run.verify_mapping(sources); run.verify_mapping(inputs); run.verify_mapping(evidence); run.verify_mapping(historical)
    controls = []
    test_names = ['check_full_state_stepdoubling_v1.py', 'check_full_state_integration_adapter_v1.py',
                  'check_stepdoubling_audit_v1.py', 'check_stepdoubling_qualification_v1.py',
                  'check_stepdoubling_launcher_v1.py', 'check_full_state_integration_adapter_v2.py',
                  'check_stepdoubling_recovery_v2.py']
    for name in test_names:
        p = STAGING / name; started = time.monotonic()
        result = subprocess.run([str(run.PYTHON), '-B', str(p)], cwd=ROOT, env=os.environ.copy(),
                                capture_output=True, text=True, timeout=180)
        match = re.search(r'Ran (\d+) tests', result.stderr)
        controls.append(dict(source_file=str(p), source_sha256=run.sha(p), returncode=result.returncode,
                             test_count=int(match.group(1)) if match else None,
                             seconds=time.monotonic()-started, stdout=result.stdout, stderr=result.stderr,
                             no_target_force_or_transport=True))
        print('RECOVERY_SOURCE_CONTROL', name, result.returncode, flush=True)
        if result.returncode:
            negative = next(run.DESIGNS / f'preparation_negative_{i:02d}.json' for i in range(1, 100)
                            if not (run.DESIGNS / f'preparation_negative_{i:02d}.json').exists())
            run.commit(negative, dict(passed=False, controls=controls, source_files=sources,
                                     new_native_calls=0, new_transport_steps=0, authority_created=False))
            raise RuntimeError('Repair controls failed; negative preserved: ' + str(negative))
    run.verify_mapping(sources); run.verify_mapping(inputs); run.verify_mapping(evidence); run.verify_mapping(historical)
    resources = run.resource_guard(force_inventory=True)
    remaining_own = run.OWN_BYTES - resources['own_bytes']
    run.need(remaining_own > 0 and resources['total_retained_bytes']+remaining_own <= run.RETENTION_BYTES,
             'combined initial and repair output remains inside original shared retention')
    run.need(resources['free_bytes']-remaining_own >= run.FREE_BYTES, 'unchanged free reserve at complete own-output ceiling')
    result = dict(schema='paper1.scope-order-recovery.source-preparation.v2', passed=True,
        utc=datetime.now(timezone.utc).isoformat(), source_files=sources, physical_inputs=inputs,
        evidence_files=evidence, historical_evidence_files=historical, controls=controls,
        prior_exact_process_identities=identities, retirement_before=retirement_before,
        retirement_after=run.assert_retired(identities), resources=resources,
        all_required_interfaces_present=True, source_interface_checks=run.source_interfaces(),
        original_approval_sha256=run.sha(run.APPROVAL), original_clock_sha256=run.sha(run.CLOCK),
        initial_closure_sha256=run.sha(initial_path), diagnosis_sha256=run.sha(diagnosis_path),
        scope_remaining=run.approval_scope(), conservative_initial_work_rows_charged=32,
        conservative_initial_records_charged=2, initial_warm_invocations_charged=2,
        initial_numerical_windows_charged=1, target_substeps_of_failed_smoke_proved_zero=True,
        old_unknown_reservation_and_failed_attempt_unchanged=True,
        native_restart_qualification_completed=False, native_mechanical_qualification_completed=False,
        native_solver_calls=0, new_transport_steps=0, dispatch_authorized=False,
        fresh_authority_created=False, original_clock_reset=False, any_resource_ceiling_increased=False)
    run.seal(run.PREPARED.parent, result)
    print('RECOVERY_SOURCE_PREPARATION_COMPLETE', run.sha(run.PREPARED), flush=True)


if __name__ == '__main__':
    prepare()
