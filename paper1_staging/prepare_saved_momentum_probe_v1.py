"""Prepare the smallest saved-input momentum-representation falsifier.

Only sealed evidence, source AST, saved-matrix arithmetic and mock controls
are consumed. No model graph, contact solver, actor, clock or authority is
created. The separately reviewed native driver remains inactive.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / 'paper1_staging'
FAMILY = ROOT / 'paper1_designs/momentum_repair_20261020'
OUT = ROOT / 'paper1_runs/momentum_repair_20261020'
PYTHON = Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
CLOSED = ROOT / 'paper1_runs/contact_event_diagnostic_20261019_recovery02/final_execution_receipt_01/results.json'
CLOSED_SHA = 'e6652db2d5a1d44fc17898b93c7010330c8747a2c5b8c085ceac7d1b442a67aa'
DIAGNOSIS = ROOT / 'paper1_designs/contact_event_diagnostic_20261019_recovery02/failure_diagnosis_01/results.json'
DIAGNOSIS_SHA = '3538a4c760bbf5574792bdaded1a420a87c6e6f7e24f40f76e278ba5ae24e5de'
OUTER_CLOCK = ROOT / 'paper1_designs/full_horizon_repair_20261018/qualification_clock_01/results.json'
OUTER_CLOCK_SHA = 'a2f1cffc1ca0ad235125487f316c6b124eac8b1df3f72bb191b8748ae8a22737'
END = '2026-10-24T07:43:33.769535+00:00'
ADMIN = STAGING / 'run_stepdoubling_qualification_v4.py'
ADMIN_SHA = '05447c49e219dfff6849f6b2c543037b894feaafa71be184db5f44133e69cf69'
PHYSICAL = ROOT / 'paper1_designs/contact_event_diagnostic_20261019/runtime_config_01.json'
PHYSICAL_SHA = '93856391c47850a6fc514232de9772045eff8d239b9282f822d93caf775858d9'
RAW = CLOSED.parent.parent / 'records/f0p0625_local_001/packet.json.xz'
RAW_SHA = '00d8eb70116e5a1ed8c58ff63b8241de312d9b211d78868dd019cc7dca11afc3'
SAVED = STAGING / 'diagnose_saved_momentum_v1.py'
SAVED_SHA = 'd58efdccd29a21601199a5e3c9a3119d002cf15cd9a96bb7597c77a55938dea0'
DRIVER = STAGING / 'run_saved_momentum_probe_v1.py'
CHECKS = ('check_cancellation_safe_velocity_v1.py', 'check_run_saved_momentum_probe_v1.py',
          'check_prepare_saved_momentum_probe_v1.py')


def need(ok, message):
    if not ok:
        raise ValueError('Saved momentum probe preparation: ' + message)


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


def prior_identity_inventory(closed, previous):
    """Two explicit closure schemas, never an empty-default retirement claim."""
    latest = closed['identities']
    older = previous['exact_retirement_after']
    need(len(latest) == len(older) == 4, 'both exact four-actor inventories remain complete')
    rows = latest + older
    need(all(isinstance(x['launch'], dict) and x['inspection']['retired'] is True
             and type(x['launch']['pid']) is int and x['launch']['pid'] > 0
             and type(x['launch']['created']) in (int, float)
             and isinstance(x['launch']['command'], list) and x['launch']['command']
             and all(isinstance(a, str) for a in x['launch']['command']) for x in rows),
         'all immutable identities contain birth and full command')
    identities = [copy.deepcopy(x['launch']) for x in rows]
    need(len({(x['pid'], x['created'], tuple(x['command'])) for x in identities}) == 8,
         'eight distinct immutable birth/full-command identities')
    return identities


def build_fixtures(wire, arithmetic):
    """Exact directly retained F1 and independently digest-verified same-origin C."""
    packet = wire['packet']
    coarse, failed = [packet['work_branches'][i] for i in (1641, 1642)]
    need(coarse['branch_id'] == 'm000000547_t000000000_C'
         and failed['branch_id'] == 'm000000547_t000000000_F1', 'fixed negative, not a later easier input')
    original = failed['contact_trial_trace']['detailed_trials'][0]
    need(not original['accepted'] and original['error'] == "RuntimeError('inertial momentum closure failed')",
         'directly retained original momentum negative')
    fields = ('x', 'p', 'q', 't', 'history_node', 'history_length')
    need(all(coarse['before_state'][k] == failed['before_state'][k] for k in fields),
         'literal FULL physical/history origin association')
    values = {}
    for label, branch, index in (('F1', failed, 1642), ('C', coarse, 1641)):
        operands = copy.deepcopy(original['outer_inputs'])
        operands[8] = branch['cap_entries'][0]['actual_trial_dt_s']
        maps = branch['contact_trial_trace']['cycle_guard_trials'][0]['records']
        checks = [x for x in arithmetic['per_inner'] if x['branch_index'] == index]
        need(len(checks) == len(maps) == 2
             and [x['exact_inner_input_sha256'] for x in checks] == [x['input_sha256'] for x in maps],
             'every independently reconstructed original inner digest equals actual saved observation')
        need(all(x['exact_free_closure_guard_would_activate'] is (label == 'F1') for x in checks),
             'saved negative activates while passing neighbor retains legacy arithmetic')
        values[label] = dict(outer_inputs=operands, branch_id=branch['branch_id'], branch_index=index,
            before_runtime_recovery_mode=branch['before_state'].get('recovery', False),
            reference_prepare_call=copy.deepcopy(branch['normal_gap_operand_policy']['prepare_calls'][0]),
            normal_gap_prepare_metadata=copy.deepcopy(branch['normal_gap_operand_policy']['prepare_calls'][0]['metadata']),
            reference_inner_maps=copy.deepcopy(maps),
            exact_inner_input_digests=[x['input_sha256'] for x in maps],
            reference_legacy_velocity=copy.deepcopy(maps[-1]['map_output']),
            expected_legacy_error='inertial momentum closure failed' if label == 'F1' else None,
            original_legacy_error_repr=original['error'] if label == 'F1' else None,
            directly_stored_outer_inputs=label == 'F1',
            derivation_same_origin_fields_verified=True, derivation_same_origin_fields=list(fields),
            reconstruction='literal failed14 operands; C substitutes only its SAVED actual dt; all consecutive inner input digests rederive exactly',
            reference_failed_momentum=arithmetic['original_failure']['normalized_residual'] if label == 'F1' else None)
    need(all(values['F1']['outer_inputs'][i] == values['C']['outer_inputs'][i] for i in range(14) if i != 8),
         'same pose/system input except the two archived timesteps')
    return dict(schema='paper1.saved-momentum-probe-fixtures.v1', raw_source_path=str(RAW), raw_source_sha256=RAW_SHA,
        F1=values['F1'], C=values['C'], new_force_calls=0, new_transport_steps=0,
        saved_evidence_not_new_physical_admission=True)


def budget_envelope():
    """Conservatively charge outer probes as work/records despite zero transport."""
    return dict(maximum_new_all_trial_work_rows=260, setup_unknown_work_reservation=256,
        maximum_target_outer_invocations=4, conservative_rows_per_outer_invocation=1,
        maximum_new_integration_records=5, maximum_numerical_windows=1,
        maximum_nonadvancing_invocation_units=12, maximum_synthetic_warm_invocations=2,
        expected_units_if_each_outer_has_two_inner_maps=10,
        actual_units_not_inferred_from_outer_count=True,
        unit_definition='two actual synthetic hot.phase warms; every observed prepared-inner dispatch INCLUDING within-pose returns; each nested hot.phase invocation beyond the first inside one observed map adds another unit; any unassociated kernel invocation is charged separately',
        all_actual_inner_and_kernel_counts_logged_separately=True,
        budget_exhaustion_stops_incomplete_never_truncates_to_claim_convergence=True,
        original_spent=dict(work_rows=757577, records=202, admitted_physical_rows=493074,
            admitted_discarded_rows=256294, known_unaccepted_rows=3371, old_unknown_reserved_rows=4838,
            nonadvancing_charge=10, numerical_windows=5, standalone_work_rows=16148, standalone_records=53),
        original_maximum=dict(work_rows=18000000, records=4000, nonadvancing_charge=22, numerical_windows=11,
            standalone_work_rows=200000, standalone_records=150,
            cumulative_case_work_rows=28312778, cumulative_case_records=6174,
            cumulative_shared_work_rows=22664866, cumulative_shared_records=5004),
        worst_case_original_after=dict(work_rows=757837, records=207, nonadvancing_charge=22,
            numerical_windows=6, standalone_work_rows=16408, standalone_records=58),
        no_resource_ceiling_increase=True, no_unknown_or_negative_refund=True)


def prepare(pins_path, expected_sha):
    need(Path(sys.executable).resolve() == PYTHON.resolve() and sys.version_info[:2] == (3, 12), 'qualified Python312')
    need(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'thread controls')
    need(all(not x.exists() for x in forbidden()), 'preparation creates no clock/approval/authority/run')
    need(not (FAMILY / 'proposal_01.json').exists() and not (FAMILY / 'preparation_01').exists(), 'create-only reviewed package')
    need(sha(pins_path) == expected_sha, 'caller-pinned exact source map')
    pins = read(pins_path)
    need(sha(ADMIN) == ADMIN_SHA and sha(SAVED) == SAVED_SHA and sha(RAW) == RAW_SHA, 'pinned reused definitions and negative')
    admin = load(ADMIN, '_saved_momentum_prep_frozen_admin')
    admin.verify_mapping(pins)
    for path in (Path(__file__).resolve(), DRIVER, SAVED, *(STAGING / name for name in CHECKS)):
        need(pins.get(str(path)) == sha(path), 'preparation and all actual consumers/controls are pinned')
    closed = admin.sealed(CLOSED, positive=True)
    need(sha(CLOSED) == CLOSED_SHA and closed['administrative_execution_closed']
         and not closed['local_diagnostic_passed'], 'scientific negative and separate closed execution preserved')
    need(sha(DIAGNOSIS) == DIAGNOSIS_SHA and sha(PHYSICAL) == PHYSICAL_SHA, 'unchanged original negative/input')
    clock = admin.sealed(OUTER_CLOCK, positive=True)
    need(sha(OUTER_CLOCK) == OUTER_CLOCK_SHA and clock['end_utc'] == END
         and datetime.now(timezone.utc) < datetime.fromisoformat(END), 'same unexpired original132h clock')
    final = admin.sealed(CLOSED.parent.parent / 'final_disposition_01/results.json')
    need(final['ledger']['work_rows'] == 4779 and final['ledger']['records'] == 16, 'all prior conservative charges retained')
    previous_closed = ROOT / 'paper1_runs/full_horizon_repair_20261018_recovery04/final_execution_receipt_01/results.json'
    need(sha(previous_closed) == '6251eed02f4b3e5c3c4290f28f81cfd97edb364e2fc646866bc2234964045d25',
         'caller-pinned previous full-qualification closure')
    previous = admin.sealed(previous_closed, positive=True)
    identities = prior_identity_inventory(closed, previous)
    def retired():
        observations = [dict(launch=x, inspection=admin.inspect_identity(x)) for x in identities]
        need(all(x['inspection']['retired'] is True for x in observations), 'fresh exact birth/full-command retirement')
        return observations
    before = retired()
    saved = load(SAVED, '_saved_momentum_arithmetic_preparation')
    arithmetic = saved.analyze_saved()
    need(arithmetic['passed'] and arithmetic['representable_passing_q_exists_for_this_saved_system'], 'actual failure reproduced, passing saved-matrix candidate exists')
    wire = json.loads(lzma.decompress(RAW.read_bytes()))
    fixture = build_fixtures(wire, arithmetic)
    controls = [dict(path=str(SAVED), source_sha256=SAVED_SHA, **saved.controls())]
    for name in CHECKS:
        p = STAGING / name
        completed = subprocess.run([str(PYTHON), '-B', str(p)], cwd=ROOT,
            capture_output=True, text=True, timeout=120, env=os.environ.copy())
        need(completed.returncode == 0, 'source/mock control failure: ' + name + '\n' + completed.stdout + completed.stderr)
        controls.append(dict(path=str(p), source_sha256=sha(p), returncode=0,
                             stdout=completed.stdout, stderr=completed.stderr, source_mock_only=True))
    driver = load(DRIVER, '_saved_momentum_probe_preparation_driver')
    driver.verify_fixtures(fixture)
    driver.budget_guard(0, 0, 0)
    scope = driver.approval_scope()
    need(scope['outer_calls'] == 4 and scope['maximum_new_all_work_rows'] == 260
         and scope['maximum_new_integration_records'] == 5
         and scope['maximum_nonadvancing_units'] == 12
         and scope['maximum_numerical_windows'] == 1
         and scope['maximum_window_seconds'] == 4500
         and scope['maximum_numerical_seconds'] == 900
         and scope['minimum_final_seconds'] == 3600
         and scope['original_shared_end_utc'] == END,
         'actual driver scope equals the bounded reviewable test')
    baseline = driver.BASELINE
    need(baseline['case_work_rows'] == 11070355 and baseline['case_records'] == 2376
         and baseline['shared_work_rows'] == 5422443 and baseline['shared_records'] == 1206,
         'actual cumulative ceilings accounting matches new consumer')
    sources = merge(final['source_files'], pins)
    physical = merge(final['physical_inputs'], {str(PHYSICAL): PHYSICAL_SHA})
    evidence = merge(final['evidence_files'], {str(CLOSED): CLOSED_SHA,
        str(CLOSED.with_name('completion.json')): sha(CLOSED.with_name('completion.json')),
        str(OUTER_CLOCK): OUTER_CLOCK_SHA, str(DIAGNOSIS): DIAGNOSIS_SHA, str(RAW): RAW_SHA})
    historical = merge(final['historical_evidence_files'], final['artifacts'], arithmetic['consumed_files'])
    for mapping in (sources, physical, evidence, historical):
        admin.verify_mapping(mapping)
    after = retired()
    # No prospective consumer is allowed to turn source checks into execution authority.
    need(all(not x.exists() for x in forbidden()), 'no preapproval native effects')
    admin.seal(FAMILY / 'saved_arithmetic_01', arithmetic)
    fixture_path = FAMILY / 'fixtures_01.json'; admin.commit(fixture_path, fixture)
    evidence = merge(evidence, {str(fixture_path): sha(fixture_path),
        str(FAMILY / 'saved_arithmetic_01/results.json'): sha(FAMILY / 'saved_arithmetic_01/results.json'),
        str(FAMILY / 'saved_arithmetic_01/completion.json'): sha(FAMILY / 'saved_arithmetic_01/completion.json')})
    resources = dict(maximum_new_output_bytes=16 * 1024**2, maximum_joint_diagnostic_output_bytes=512 * 1024**2,
        maximum_all_qualification_output_bytes=12 * 1024**3, maximum_paper1_retained_bytes=21 * 1024**3,
        minimum_free_bytes=20 * 1024**3, workers=1, logical_cpu=14, thread_variables=1,
        maximum_native_seconds_per_request=45, maximum_unverified_records=1)
    proposal = dict(schema='paper1.saved-momentum-repair-probe-proposal.v1',
        status='REQUIRES_SEPARATE_HUMAN_APPROVAL', dispatch_authorized=False,
        scientific_question='Does residual-guarded increment arithmetic repair the exact saved momentum failure in the unchanged native contact stack, preserving the inactive neighbor and fresh-solve determinism?',
        required_human_approval_scope=scope, baseline=baseline,
        budget=budget_envelope(), resources=resources,
        fixtures_file=str(fixture_path), fixtures_sha256=sha(fixture_path),
        physical_file=str(PHYSICAL), physical_sha256=PHYSICAL_SHA,
        call_order=[dict(fixture='F1', mode='original', expected='original_momentum_negative'),
                    dict(fixture='F1', mode='guarded', expected='all_original_gates_pass'),
                    dict(fixture='F1', mode='guarded', expected='fresh_repeat_bit_exact'),
                    dict(fixture='C', mode='guarded', expected='inactive_bit_exact_to_saved_native')],
        arithmetic_change='Only free_velocity representation: compute exact legacy expression first; if its finite unconstrained ORIGINAL momentum residual>1e-8, use qold+same_compliance@(drag@(background-qold)+body-lubrication@qold) before the unchanged one contact call.',
        original_final_momentum_expression_normalizer_threshold_unchanged=True,
        legacy_exact_arithmetic_when_inactive=True,
        recurrence_check_change='An explicit new representation-specific EXACT recurrence check independently rederives mode and vector; legacy exact check remains on inactive iterations. No equality tolerance is substituted.',
        independent_contact_mechanics_fixedpoint_and_final_momentum_required=True,
        expected_old_failure_is_preserved_and_charged=True,
        every_inner_mode_and_input_retained_including_successful_zero_route_trials=True,
        original_physics_changes=[], original_gap_policy_changes=[], original_contact_route_changes=[],
        original_accuracy_threshold_changes=[], new_transport_steps=0, original_FULL_history_or_restart_qualification=False,
        full_observation_horizon_qualified=False, core_case_admission=False, successor_dispatch=False,
        future_scope='Passing supports these retained input systems only; active FULL restart, local two-factor path, selector finite progress and BOTH original full-horizon pairs remain separate gates.',
        prospective_window=dict(maximum_minutes=75, maximum_numerical_including_setup_online_audit_minutes=15,
            minimum_postworker_replay_exit_log_reserve_minutes=60, clock_created=False,
            original_outer_clock_never_reset=True, original_absolute_end_utc=END),
        separate_external_execution_receipt_required=True,
        controller_own_logs=[str(FAMILY / 'execution_logs_01/controller_stdout.log'),
                             str(FAMILY / 'execution_logs_01/controller_stderr.log')],
        controller_own_exit_provenance='ROOT direct foreground qualified native command and immediately observed LASTEXITCODE/terminal receipt; never inferred from its child',
        original_outer_clock_sha256=OUTER_CLOCK_SHA,
        source_files=sources, physical_inputs=physical, evidence_files=evidence, historical_evidence_files=historical,
        previous_closed_negative_sha256=CLOSED_SHA, qualified_core_cases=1, required_core_cases=12,
        no_automatic_budget_or_scientific_gate_increase=True)
    admin.commit(FAMILY / 'proposal_01.json', proposal)
    prep = dict(schema='paper1.saved-momentum-probe-source-preparation.v1', passed=True,
        dispatch_authorized=False, all_required_interfaces_present=True, native_qualification_passed=False,
        new_force_calls=0, new_transport_steps=0, new_integration_records=0, new_clock_created=False,
        original_failure_reproduced=arithmetic['original_failure']['normalized_residual'],
        candidate_saved_arithmetic_only=arithmetic['per_inner'][-1]['increment_same_inverse_gate'],
        all_accuracy_thresholds_and_original_final_gate_unchanged=True,
        original_state_history_or_source_never_modified=True, baseline=baseline,
        controls=controls, source_files=sources, physical_inputs=physical, evidence_files=evidence,
        historical_evidence_files=historical, prior_exact_process_identities=identities,
        fresh_retirement_before_hash=before, fresh_retirement_after_hash=after,
        full_hash_authenticated_files=len(merge(sources, physical, evidence, historical)),
        hash_authentication_not_mechanical_replay=True, proposal_sha256=sha(FAMILY / 'proposal_01.json'),
        artifacts={str(fixture_path): sha(fixture_path), str(FAMILY / 'proposal_01.json'): sha(FAMILY / 'proposal_01.json')},
        original_outer_clock_sha256=OUTER_CLOCK_SHA, original_absolute_end_utc=END,
        utc=datetime.now(timezone.utc).isoformat())
    admin.seal(FAMILY / 'preparation_01', prep)
    need(all(not x.exists() for x in forbidden()), 'no clock/actor/authority was created by preparation')
    need(shutil.disk_usage(ROOT).free >= 20 * 1024**3, 'free reserve remains after compact preparation')
    return dict(passed=True, proposal_sha256=sha(FAMILY / 'proposal_01.json'),
                preparation_sha256=sha(FAMILY / 'preparation_01/results.json'),
                numerical_work_launched=False, new_force_calls=0, new_transport_steps=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pins', type=Path, required=True)
    parser.add_argument('--pins-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.pins, args.pins_sha256), sort_keys=True))
