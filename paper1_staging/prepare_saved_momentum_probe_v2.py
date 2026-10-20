"""Prepare the separately approvable, saved-input momentum probe recovery.

Only immutable closed evidence, source definitions and pure/mock controls are
read.  No model graph, native solve, actor, clock or authority is constructed.
The original fixture file is reused at its exact existing path and bytes.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / 'paper1_staging'
BASE_FAMILY = ROOT / 'paper1_designs/momentum_repair_20261020'
FAMILY = ROOT / 'paper1_designs/momentum_repair_20261020_recovery02'
OUT = ROOT / 'paper1_runs/momentum_repair_20261020_recovery02'
INITIAL_OUT = ROOT / 'paper1_runs/momentum_repair_20261020'
PYTHON = Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
ADMIN = STAGING / 'run_stepdoubling_qualification_v4.py'
ADMIN_SHA = '05447c49e219dfff6849f6b2c543037b894feaafa71be184db5f44133e69cf69'
DRIVER = STAGING / 'run_saved_momentum_probe_v2.py'
HELPER = STAGING / 'cancellation_safe_velocity_v2.py'
CHECKS = ('check_cancellation_safe_velocity_v2.py', 'check_run_saved_momentum_probe_v2.py',
          'check_prepare_saved_momentum_probe_v2.py')
CLOSED = INITIAL_OUT / 'final_execution_receipt_01/results.json'
CLOSED_SHA = '154eb7f34172e4b60738dee746092a2808f227f3c64454eb4aaeec1cc007a469'
FINAL = INITIAL_OUT / 'final_disposition_01/results.json'
FINAL_SHA = '1abbdfe18b761b9afaf92708227ccc860096073e5e59f3e8cf63caf104cfeab4'
BASE_PREP = BASE_FAMILY / 'preparation_01/results.json'
BASE_PREP_SHA = '0b8016d0f555a94e16d10e43e373c61d29f3845665ae0232cefe2288488e2f10'
INITIAL_CLOCK = BASE_FAMILY / 'window_clock_01/results.json'
INITIAL_CLOCK_SHA = 'cf322fb3560aa1bfddcbc9e7db6eaf1c183772fd4413a449f819ac64be1fe938'
DIAGNOSIS = BASE_FAMILY / 'failure_diagnosis_01/results.json'
DIAGNOSIS_SHA = '3d76dbb0abbb36906b86669357a5f6fa220f819160a87e8f3a80473546b2d66d'
FIXTURES = BASE_FAMILY / 'fixtures_01.json'
FIXTURES_SHA = '9d3d975d3ef24b7e08fac190dffb574c18dbff7cafcd24cce08b81afac969151'
ARITHMETIC = BASE_FAMILY / 'saved_arithmetic_01/results.json'
ARITHMETIC_SHA = 'd6736ba38c6ef01c2a7aa77004b52cd83f479da0e0b53b7d9af5075915b25fd8'
PREPARATION_NEGATIVE = FAMILY / 'preparation_failure_01/results.json'
PREPARATION_NEGATIVE_SHA = '2ab072c7f660eb9bca17b489690281f47c76439f389861bc00ca2fc62e75aa50'
PHYSICAL = ROOT / 'paper1_designs/contact_event_diagnostic_20261019/runtime_config_01.json'
PHYSICAL_SHA = '93856391c47850a6fc514232de9772045eff8d239b9282f822d93caf775858d9'
OUTER_CLOCK = ROOT / 'paper1_designs/full_horizon_repair_20261018/qualification_clock_01/results.json'
OUTER_CLOCK_SHA = 'a2f1cffc1ca0ad235125487f316c6b124eac8b1df3f72bb191b8748ae8a22737'
NUMERICAL_END = '2026-10-23T23:43:33.769535+00:00'
END = '2026-10-24T07:43:33.769535+00:00'
PRIOR_PROBE_SPENT = dict(all_work_rows=0, integration_records=2, nonadvancing_units=2,
                         numerical_windows=1)


def need(ok, message):
    if not ok:
        raise ValueError('Saved momentum recovery preparation: ' + message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def merge(*maps):
    result = {}
    for mapping in maps:
        for path, value in mapping.items():
            need(path not in result or result[path] == value, 'conflicting immutable bytes: ' + path)
            result[path] = value
    return result


def forbidden():
    return [OUT, FAMILY / 'design_01.json', FAMILY / 'authorization_01.json',
            FAMILY / 'human_approval_01', FAMILY / 'window_clock_01', FAMILY / 'execution_logs_01']


def check_identity(launch):
    need(isinstance(launch, dict) and type(launch['pid']) is int and launch['pid'] > 0
         and type(launch['created']) in (int, float) and math.isfinite(launch['created'])
         and launch['created'] > 0 and isinstance(launch['command'], list) and launch['command']
         and all(isinstance(x, str) and x for x in launch['command']),
         'every immutable identity has a positive birth and accessible full command')


def prior_identity_inventory(previous_prep, closed):
    """Exactly eight older actors plus the closed first probe's two actors."""
    older = previous_prep['prior_exact_process_identities']
    latest = closed['retirement_after']
    need(len(older) == 8 and len(latest) == 2, 'exact eight-plus-two actor inventories')
    need(all(x['inspection']['retired'] is True for x in latest), 'first probe exact retirement sealed')
    identities = copy.deepcopy(older) + [copy.deepcopy(x['launch']) for x in latest]
    for identity in identities:
        check_identity(identity)
    need(len({(x['pid'], x['created'], tuple(x['command'])) for x in identities}) == 10,
         'ten distinct immutable birth/full-command identities')
    return identities


def verify_initial_negative(closed, final, diagnosis):
    need(closed['passed'] is True and closed['execution_closed'] is True
         and closed['final_disposition_passed'] is False and closed['saved_input_screen_passed'] is False
         and closed['full_horizon_qualified'] is False and closed['full_restart_qualified'] is False,
         'initial scientific negative remains separately closed, never qualified')
    ledger = final['ledger']
    need(final['passed'] is False and ledger['all_work_rows'] == 0
         and ledger['integration_records'] == 2 and ledger['nonadvancing_units'] == 2
         and ledger['known_unaccepted_work_rows'] == 0
         and ledger['unknown_reserved_work_upper_bound'] == 0
         and closed['ledger'] == ledger, 'exact initial two-record/two-warm charges retained')
    need(diagnosis['passed'] is True and diagnosis['implementation_defect_confirmed'] is True
         and all(type(diagnosis[k]) is int and diagnosis[k] == 0 for k in
                 ('target_outer_calls', 'prepared_inner_maps', 'actual_hot_phase_calls',
                  'new_force_calls', 'new_native_calls'))
         and diagnosis['initial_attempt_closed_sha256'] == CLOSED_SHA
         and diagnosis['initial_attempt_final_sha256'] == FINAL_SHA
         and diagnosis['prior_probe_spent'] == PRIOR_PROBE_SPENT
         and diagnosis['raw_sha256'] == '922aa79e3f8bcb1a519be3e49d6a4678a6acfcd1b5bc3550a6a6d1a39eda143d',
         'strict pre-outer implementation diagnosis, not a physical candidate outcome')
    return copy.deepcopy(PRIOR_PROBE_SPENT)


def budget_envelope():
    return dict(maximum_new_all_trial_work_rows=260, setup_unknown_work_reservation=256,
        maximum_target_outer_invocations=4, conservative_rows_per_outer_invocation=1,
        maximum_new_integration_records=5, maximum_numerical_windows=1,
        maximum_nonadvancing_invocation_units=10, maximum_synthetic_warm_invocations=2,
        expected_units_if_each_outer_has_two_inner_maps=10,
        actual_units_not_inferred_from_outer_count=True,
        unit_definition='two actual synthetic hot.phase warms; every observed prepared-inner dispatch INCLUDING within-pose returns; each nested hot.phase invocation beyond the first inside one observed map adds another unit; any unassociated kernel invocation is charged separately',
        all_actual_inner_and_kernel_counts_logged_separately=True,
        budget_exhaustion_stops_incomplete_never_truncates_to_claim_convergence=True,
        prior_probe_spent=copy.deepcopy(PRIOR_PROBE_SPENT),
        combined_probe_maximum=dict(all_work_rows=260, integration_records=7,
            nonadvancing_units=12, numerical_windows=2),
        prior_suballocation_amendment_required=True, fresh_recovery_window_requires_new_human_approval=True,
        original_spent=dict(work_rows=757577, records=204, admitted_physical_rows=493074,
            admitted_discarded_rows=256294, known_unaccepted_rows=3371, old_unknown_reserved_rows=4838,
            nonadvancing_charge=12, numerical_windows=6, standalone_work_rows=16148, standalone_records=55),
        original_maximum=dict(work_rows=18000000, records=4000, nonadvancing_charge=22, numerical_windows=11,
            standalone_work_rows=200000, standalone_records=150,
            cumulative_case_work_rows=28312778, cumulative_case_records=6174,
            cumulative_shared_work_rows=22664866, cumulative_shared_records=5004),
        worst_case_original_after=dict(work_rows=757837, records=209, nonadvancing_charge=22,
            numerical_windows=7, standalone_work_rows=16408, standalone_records=60),
        no_global_resource_ceiling_increase=True, no_unknown_or_negative_refund=True)


def verify_consumer_package(driver, common, proposal, sources):
    """Run the actual consumer's prerequisites before any positive write."""
    need(driver.validate_initial_attempt(common, proposal) is True,
         'actual driver authenticates its initial-attempt prerequisites')
    expected = driver.source_interfaces()
    need(expected and all(sources.get(path) == value for path, value in expected.items()),
         'actual source interfaces, including old and new consumers, are frozen')
    return True


def inherited_mappings(closed, final, diagnosis, previous_prep, source_pins, linked):
    """Use the real probe wire: complete maps belong to its closed receipt.

    The disposition contributes its actual source inventory and artifact map.
    Missing receipt maps remain errors; no empty-default waiver is introduced.
    """
    sources = merge(closed['source_files'], final['source_files'],
                    diagnosis['source_files'], source_pins)
    physical = merge(closed['physical_inputs'], {str(PHYSICAL): PHYSICAL_SHA})
    evidence = merge(closed['evidence_files'], diagnosis['evidence_files'], linked)
    historical = merge(closed['historical_evidence_files'], closed['artifacts'],
                       final['artifacts'], previous_prep['artifacts'])
    return sources, physical, evidence, historical


def prepare(pins_path, expected_sha):
    need(Path(sys.executable).resolve() == PYTHON.resolve() and sys.version_info[:2] == (3, 12), 'qualified Python312')
    need(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'thread controls')
    need(all(not x.exists() for x in forbidden()), 'no recovery clock/approval/authority/run/logs')
    need(not (FAMILY / 'proposal_01.json').exists() and not (FAMILY / 'preparation_01').exists(), 'create-only review package')
    need(sha(pins_path) == expected_sha, 'caller-pinned exact source/evidence map')
    pins = read(pins_path)
    need(sha(ADMIN) == ADMIN_SHA, 'unchanged frozen administrative definitions')
    admin = load(ADMIN, '_saved_momentum_recovery_preparation_admin')
    admin.verify_mapping(pins)
    for path in (Path(__file__).resolve(), DRIVER, HELPER, *(STAGING / name for name in CHECKS)):
        need(pins.get(str(path)) == sha(path), 'all actual new consumers and controls pinned')
    diagnosis_sha = pins[str(DIAGNOSIS)]
    need(diagnosis_sha == DIAGNOSIS_SHA == sha(DIAGNOSIS),
         'caller-pinned initial failure diagnosis')
    for path, expected in ((CLOSED, CLOSED_SHA), (FINAL, FINAL_SHA), (BASE_PREP, BASE_PREP_SHA),
                           (INITIAL_CLOCK, INITIAL_CLOCK_SHA), (FIXTURES, FIXTURES_SHA),
                           (ARITHMETIC, ARITHMETIC_SHA), (PHYSICAL, PHYSICAL_SHA), (OUTER_CLOCK, OUTER_CLOCK_SHA)):
        need(sha(path) == expected, 'literal previous evidence: ' + str(path))
    closed = admin.sealed(CLOSED, positive=True)
    final = admin.sealed(FINAL)
    previous_prep = admin.sealed(BASE_PREP, positive=True)
    need(previous_prep['dispatch_authorized'] is False and previous_prep['new_force_calls'] == 0
         and previous_prep['new_transport_steps'] == 0, 'original source-only preparation remains historical')
    diagnosis = admin.sealed(DIAGNOSIS, positive=True)
    need(sha(PREPARATION_NEGATIVE) == PREPARATION_NEGATIVE_SHA,
         'source-only schema negative and its exact source snapshots preserved')
    preparation_negative = admin.sealed(PREPARATION_NEGATIVE)
    need(preparation_negative['passed'] is False
         and preparation_negative['new_force_calls'] == 0
         and preparation_negative['no_positive_proposal_or_preparation_written'] is True,
         'source preparation failure grants no native work or acceptance')
    failed_pin_path = Path(preparation_negative['caller_pins_path'])
    need(sha(failed_pin_path) == preparation_negative['caller_pins_sha256'],
         'negative caller-pin receipt is preserved, not treated as current bindings')
    need(all(hashlib.sha256(row['utf8_text'].encode('utf-8')).hexdigest() == row['sha256']
             for row in preparation_negative['source_snapshots']),
         'exact failed source bytes remain available inside the negative receipt')
    spent = verify_initial_negative(closed, final, diagnosis)
    clock = admin.sealed(OUTER_CLOCK, positive=True)
    need(clock['end_utc'] == END and clock['simulation_cutoff_utc'] == NUMERICAL_END
         and datetime.now(timezone.utc) < datetime.fromisoformat(NUMERICAL_END),
         'same unexpired original132h numerical and absolute cutoffs')
    identities = prior_identity_inventory(previous_prep, closed)

    def retired():
        observations = [dict(launch=x, inspection=admin.inspect_identity(x)) for x in identities]
        need(all(x['inspection']['retired'] is True for x in observations), 'fresh exact birth/full-command retirement')
        return observations

    before = retired()
    controls = []
    for name in CHECKS:
        path = STAGING / name
        completed = subprocess.run([str(PYTHON), '-B', str(path)], cwd=ROOT,
            capture_output=True, text=True, timeout=120, env=os.environ.copy())
        need(completed.returncode == 0, 'new source/mock control failure: ' + name + '\n' + completed.stdout + completed.stderr)
        controls.append(dict(path=str(path), source_sha256=sha(path), returncode=0,
            stdout=completed.stdout, stderr=completed.stderr, source_mock_only=True))
    # Old preparation controls are historical evidence, not re-executed once their output exists.
    driver = load(DRIVER, '_saved_momentum_recovery_preparation_driver')
    driver.verify_fixtures(read(FIXTURES))
    driver.budget_guard(0, 0, 0)
    scope = driver.approval_scope()
    need(scope['outer_calls'] == 4 and scope['maximum_new_all_work_rows'] == 260
         and scope['maximum_new_integration_records'] == 5 and scope['maximum_nonadvancing_units'] == 10
         and scope['maximum_numerical_windows'] == 1 and scope['maximum_window_seconds'] == 4500
         and scope['maximum_numerical_seconds'] == 900 and scope['minimum_final_seconds'] == 3600
         and scope['original_shared_end_utc'] == END and scope['prior_probe_spent'] == spent
         and scope['maximum_aggregate_probe_work_rows'] == 260
         and scope['maximum_aggregate_probe_integration_records'] == 7
         and scope['maximum_aggregate_probe_nonadvancing_units'] == 12
         and scope['maximum_aggregate_probe_numerical_windows'] == 2
         and scope['fresh_recovery_window_requires_new_explicit_human_approval'] is True
         and scope['initial_probe_authority_closed_unchanged'] is True,
         'actual new driver scope equals bounded recovery and explicit suballocation amendment')
    baseline = driver.BASELINE
    need(baseline == dict(case_work_rows=11070355, case_records=2378, shared_work_rows=5422443,
         shared_records=1208, diagnostic_work_rows=162229, diagnostic_records=121), 'unchanged work plus initial two-record charges')
    source_pins = {k: v for k, v in pins.items() if k != str(DIAGNOSIS)}
    linked = {str(path): sha(path) for path in (CLOSED, CLOSED.with_name('completion.json'), FINAL,
        FINAL.with_name('completion.json'), BASE_PREP, BASE_PREP.with_name('completion.json'),
        INITIAL_CLOCK, INITIAL_CLOCK.with_name('completion.json'), OUTER_CLOCK,
        OUTER_CLOCK.with_name('completion.json'), DIAGNOSIS, DIAGNOSIS.with_name('completion.json'),
        FIXTURES, ARITHMETIC, ARITHMETIC.with_name('completion.json'),
        PREPARATION_NEGATIVE, PREPARATION_NEGATIVE.with_name('completion.json'))}
    linked[str(failed_pin_path)] = preparation_negative['caller_pins_sha256']
    sources, physical, evidence, historical = inherited_mappings(
        closed, final, diagnosis, previous_prep, source_pins, linked)
    for mapping in (sources, physical, evidence, historical):
        admin.verify_mapping(mapping)
    after = retired()
    need(datetime.now(timezone.utc) < datetime.fromisoformat(NUMERICAL_END), 'full hashing cannot extend original numerical authority')
    need(all(not x.exists() for x in forbidden()), 'preparation creates no execution authority')
    need(sha(FIXTURES) == FIXTURES_SHA, 'original fixture path and bytes remain unchanged')
    need(shutil.disk_usage(ROOT).free >= 20 * 1024**3, 'free reserve before compact source-only seals')
    resources = dict(maximum_combined_probe_output_bytes=16 * 1024**2,
        combined_probe_output_paths=[str(INITIAL_OUT), str(BASE_FAMILY / 'execution_logs_01'),
                                    str(OUT), str(FAMILY / 'execution_logs_01')],
        maximum_joint_diagnostic_output_bytes=512 * 1024**2,
        maximum_all_qualification_output_bytes=12 * 1024**3, maximum_paper1_retained_bytes=21 * 1024**3,
        minimum_free_bytes=20 * 1024**3, workers=1, logical_cpu=14, thread_variables=1,
        maximum_native_seconds_per_request=45, maximum_unverified_records=1)
    common = dict(initial_attempt_closed_sha256=CLOSED_SHA, initial_attempt_final_sha256=FINAL_SHA,
        initial_failure_diagnosis_sha256=diagnosis_sha, initial_probe_clock_sha256=INITIAL_CLOCK_SHA,
        prior_probe_spent=spent, original_outer_clock_sha256=OUTER_CLOCK_SHA)
    proposal = dict(schema='paper1.saved-momentum-repair-probe-proposal.v2',
        status='REQUIRES_SEPARATE_HUMAN_APPROVAL', dispatch_authorized=False,
        scientific_question='Does the unchanged saved-input momentum-representation candidate pass the original native gates once the source binding retains its exact module compilation context?',
        required_human_approval_scope=scope, baseline=baseline, budget=budget_envelope(), resources=resources,
        fixtures_file=str(FIXTURES), fixtures_sha256=FIXTURES_SHA,
        physical_file=str(PHYSICAL), physical_sha256=PHYSICAL_SHA,
        call_order=[dict(fixture='F1', mode='original', expected='original_momentum_negative'),
                    dict(fixture='F1', mode='guarded', expected='all_original_gates_pass'),
                    dict(fixture='F1', mode='guarded', expected='fresh_repeat_bit_exact'),
                    dict(fixture='C', mode='guarded', expected='inactive_bit_exact_to_saved_native')],
        repair='Only preserve original module compiler context while reconstructing the strictly guarded function. No physical candidate outcome occurred in the initial probe.',
        arithmetic_change='Unchanged candidate: exact legacy free velocity first; only if its finite unconstrained original momentum residual exceeds1e-8 use the same-inverse increment representation before the original one contact call.',
        original_final_momentum_expression_normalizer_threshold_unchanged=True,
        legacy_exact_arithmetic_when_inactive=True, independent_contact_mechanics_fixedpoint_and_final_momentum_required=True,
        expected_old_failure_is_preserved_and_charged=True, every_inner_mode_and_input_retained_including_successful_zero_route_trials=True,
        original_physics_changes=[], original_gap_policy_changes=[], original_contact_route_changes=[],
        original_accuracy_threshold_changes=[], new_transport_steps=0, original_FULL_history_or_restart_qualification=False,
        full_observation_horizon_qualified=False, core_case_admission=False, successor_dispatch=False,
        prior_suballocation_amendment_required=True, fresh_recovery_window_requires_new_explicit_human_approval=True,
        initial_probe_authority_closed_unchanged=True,
        prospective_window=dict(maximum_minutes=75, maximum_numerical_including_setup_online_audit_minutes=15,
            minimum_postworker_replay_exit_log_reserve_minutes=60, clock_created=False,
            original_outer_clock_never_reset=True, original_absolute_end_utc=END,
            original_numerical_outer_cutoff_utc=NUMERICAL_END),
        future_scope='A passing screen supports these retained input systems only; active FULL restart, local two-factor path, selector finite progress and both original full-horizon pair gates remain unqualified.',
        separate_external_execution_receipt_required=True,
        controller_own_logs=[str(FAMILY / 'execution_logs_01/controller_stdout.log'), str(FAMILY / 'execution_logs_01/controller_stderr.log')],
        controller_own_exit_provenance='ROOT direct foreground qualified native command and immediately observed LASTEXITCODE/terminal receipt; never inferred from its child',
        source_files=sources, physical_inputs=physical, evidence_files=evidence, historical_evidence_files=historical,
        previous_closed_negative_sha256=CLOSED_SHA, qualified_core_cases=1, required_core_cases=12,
        no_automatic_budget_or_scientific_gate_increase=True, **common)
    verify_consumer_package(driver, common, proposal, sources)
    need(all(not x.exists() for x in forbidden())
         and datetime.now(timezone.utc) < datetime.fromisoformat(NUMERICAL_END),
         'consumer prerequisite checks create no authority or extend original numerical cutoff')
    admin.commit(FAMILY / 'proposal_01.json', proposal)
    prep = dict(schema='paper1.saved-momentum-probe-source-preparation.v2', passed=True,
        dispatch_authorized=False, all_required_interfaces_present=True, native_qualification_passed=False,
        new_force_calls=0, new_transport_steps=0, new_integration_records=0, new_clock_created=False,
        original_failure_reproduced=previous_prep['original_failure_reproduced'],
        candidate_saved_arithmetic_only=previous_prep['candidate_saved_arithmetic_only'],
        arithmetic_evidence_reused_without_new_matrix_or_native_calls=True,
        initial_implementation_failure_preserved=True, all_accuracy_thresholds_and_original_final_gate_unchanged=True,
        source_preparation_negative_sha256=PREPARATION_NEGATIVE_SHA,
        original_state_history_or_source_never_modified=True, baseline=baseline, controls=controls,
        previous_source_mock_controls_immutable_not_reexecuted=previous_prep['controls'],
        source_files=sources, physical_inputs=physical, evidence_files=evidence, historical_evidence_files=historical,
        prior_exact_process_identities=identities, fresh_retirement_before_hash=before, fresh_retirement_after_hash=after,
        full_hash_authenticated_files=len(merge(sources, physical, evidence, historical)),
        hash_authentication_not_mechanical_replay=True, proposal_sha256=sha(FAMILY / 'proposal_01.json'),
        artifacts={str(FAMILY / 'proposal_01.json'): sha(FAMILY / 'proposal_01.json')},
        original_absolute_end_utc=END, original_numerical_outer_cutoff_utc=NUMERICAL_END,
        utc=datetime.now(timezone.utc).isoformat(), **common)
    admin.seal(FAMILY / 'preparation_01', prep)
    need(all(not x.exists() for x in forbidden()), 'no clock/actor/authority was created')
    need(sha(FIXTURES) == FIXTURES_SHA, 'no copy or mutation of original fixtures')
    need(shutil.disk_usage(ROOT).free >= 20 * 1024**3, 'free reserve after compact preparation')
    return dict(passed=True, proposal_sha256=sha(FAMILY / 'proposal_01.json'),
        preparation_sha256=sha(FAMILY / 'preparation_01/results.json'), numerical_work_launched=False,
        new_force_calls=0, new_transport_steps=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pins', type=Path, required=True)
    parser.add_argument('--pins-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.pins, args.pins_sha256), sort_keys=True))
