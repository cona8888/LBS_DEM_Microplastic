"""Prepare a same-FULL-state support diagnostic; numerical dispatch is absent.

Only sealed metadata, the unchanged lossless raw/history codec, checkpoint
contract rebinding and synthetic metric controls are used. There is no worker,
authorization writer, transport, contact solve or physical-auditor replay.
"""
from datetime import datetime, timezone
from pathlib import Path
import copy
import json
import math
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_core_v2 as original

s, api = original.s, original.s.api
ROOT = s.ROOT
SELF = Path(__file__).resolve()
PRIOR_DESIGN = ROOT / 'paper1_designs/full_horizon_timecap_20261016'
PRIOR_RUN = ROOT / 'paper1_runs/full_horizon_timecap_20261016'
DESIGN = ROOT / 'paper1_designs/support_common_state_20261017'
PHYSICAL = DESIGN / 'physical_cases_01.json'
PROPOSAL = DESIGN / 'proposal_01.json'
DEADLINE = '2026-10-18T02:59:34.905691+00:00'
SOURCE_LEVEL = PRIOR_RUN / 'levels/f0p03125'
SOURCE_LAST = 'production_00279'
ANCHOR_S = .4
DURATION_S = .01
BRANCH_STEPS = (17000, 34000)
BRANCH_LOCAL_CALLS = (4, 7)
RESTART_STEPS_EACH = 512
NEW_STEPS = sum(BRANCH_STEPS) + 2 * RESTART_STEPS_EACH
NEW_CALLS = sum(BRANCH_LOCAL_CALLS) + 6
EXPECTED = {
    str(PRIOR_RUN / 'comparison_fine/results.json'): '15d48be2710368ad8499a2998b53f0c31c085b6f1880116fc317d47b1ad048d7',
    str(PRIOR_RUN / 'final_execution_receipt_01/results.json'): 'd23b764b5d5c3769ee2607aca7c0107e424352641306b6575a9b2522f943bf1f',
    str(PRIOR_DESIGN / 'physical_cases_01.json'): '8538038840008bc1b5b06b0c595f4b916cfc9601f3573fff09284dba837d742b',
    str(ROOT / 'paper1_evaluations/timecap_failure_20261017/diagnosis_01/results.json'): 'dfbddc05ef3cbad3f3bb3765a5af9c5269486e3721ab42da80f8e7ac4d29140d',
}


def bound(extra_bytes=0):
    s.environment()
    api.require(datetime.now(timezone.utc) < datetime.fromisoformat(DEADLINE), 'Original absolute bound; no reset')
    retained = sum(p.stat().st_size for name in ('paper1_runs', 'paper1_designs', 'paper1_evaluations')
                   for p in (ROOT / name).rglob('*') if p.is_file())
    free = shutil.disk_usage(ROOT).free
    api.require(retained + extra_bytes < 20 * 1024**3 and free - extra_bytes > 20 * 1024**3,
                'Unchanged 20GiB retention and 20GiB free reserve')
    return dict(retained_bytes=retained, free_bytes=free)


def budget(saved=10184681, calls=2125):
    api.require(saved >= 0 and calls >= 0 and saved + NEW_STEPS <= 11300000
                and calls + NEW_CALLS <= 2400, 'No cumulative case budget increase')
    return dict(prior_conservative_case_saved_steps=saved, prior_conservative_case_calls=calls,
        maximum_additional_saved_steps=NEW_STEPS, maximum_additional_calls=NEW_CALLS,
        maximum_case_saved_steps_after=saved + NEW_STEPS, maximum_case_calls_after=calls + NEW_CALLS,
        existing_case_saved_step_cap=11300000, existing_case_call_cap=2400,
        branch_local_step_caps=list(BRANCH_STEPS), branch_local_call_caps=list(BRANCH_LOCAL_CALLS),
        exact_restart_steps_per_branch=RESTART_STEPS_EACH, exact_restart_calls_per_branch=3,
        restart_serial_steps=256, restart_split_steps=[128, 128],
        all_new_saved_steps_are_discarded_diagnostics=True)


def controls():
    b = budget()
    assert b['maximum_additional_saved_steps'] == 52024 and b['maximum_additional_calls'] == 17
    assert sum(math.ceil(n / 5000) for n in BRANCH_STEPS) + 6 == NEW_CALLS
    for saved, calls in ((11300000 - NEW_STEPS + 1, 0), (0, 2400 - NEW_CALLS + 1)):
        try:
            budget(saved, calls)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Case ceiling overflow admitted')
    initial = [.4, 0., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0.]
    rows = np.asarray([[.405, 0., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0.],
                       [.41000000000000003, 0., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0.]])
    end = float(rows[-1, 0])
    metrics = s.q.job.path_metrics.metrics([rows], [rows], initial, initial, end, end, 1., 1.)
    assert metrics['common_start_s'] == .4 and metrics['common_stop_s'] == end
    assert metrics['mean_L1_q_over_U_max'] == metrics['endpoint_q_over_U_max'] == 0.
    try:
        s.q.job.policy.pair_gates(dict(complete_observation=True, stop_s=end),
                                 dict(complete_observation=True, stop_s=end), metrics, s.q.job.policy.GATES)
    except ValueError:
        pass
    else:
        raise AssertionError('Local clock admitted as an original fresh full path')
    return dict(passed=True, zero_transport_steps=0, zero_native_solver_calls=0,
        budget_arithmetic_exact=True, saved_step_overflow_rejected=True, call_overflow_rejected=True,
        identical_local_trace_error_zero=True, absolute_clock_preserved=True,
        forged_full_observation_does_not_bypass_original_fresh_path_gate=True,
        numerical_dispatch_entry_point_absent=True)


def seed_for(index):
    """Return an exact physical seed with only a new diagnostic contract binding."""
    api.require(type(index) is int and 0 <= index < 2, 'Declared diagnostic branch')
    physical = s.read(PHYSICAL)
    provenance = s.fields.sealed(DESIGN / 'seed_source/provenance_01/results.json')
    api.verify_mapping(provenance['seed_artifacts'])
    before = original.DOC.read(DESIGN / 'seed_source/checkpoint.json')
    api.require(api.digest(before) == provenance['full_checkpoint_sha256'], 'Authenticated complete seed')
    case = physical['cases'][index]
    result = s.q.job.parent.model.checkpoint(case['spec'], s.q.job.binding(physical, case), before, True)
    api.require(result['state'] == before['state'] and result['state_sha256'] == before['state_sha256'],
                'No physical state, history, pending trial or counter changed')
    return result, None


def prepare():
    bound()
    api.require(not DESIGN.exists(), 'New create-only package; no frozen source or evidence overwritten')
    pure = controls()
    api.verify_mapping(EXPECTED)
    failed = s.fields.sealed(PRIOR_RUN / 'comparison_fine/results.json')
    closed = s.fields.sealed(PRIOR_RUN / 'final_execution_receipt_01/results.json')
    api.require(not failed['passed'] and failed['original_gate_values'] == s.q.job.policy.GATES
                and closed['passed'] and closed['all_exact_owned_identities_retired']
                and closed['dependent_dispatch_stopped'] and not closed['qualification_passed'],
                'Closed scientific failure remains stopped; preparation confers no dispatch authority')
    prior = s.read(PRIOR_DESIGN / 'design_01.json')
    old_auth = s.read(PRIOR_DESIGN / 'authorization_01.json')
    api.require(prior['end_utc'] == old_auth['end_utc'] == DEADLINE
                and prior['binding'] == api.digest({k: v for k, v in prior.items() if k != 'binding'}),
                'Original shared design and absolute deadline')
    for key in ('source_files', 'physical_inputs'):
        api.verify_mapping(prior[key])
    for key in ('source_files', 'evidence_files'):
        api.verify_mapping(failed[key])
    physical_source = s.read(PRIOR_DESIGN / 'physical_cases_01.json')
    source_case = next(x for x in physical_source['cases'] if x['factor'] == .03125)
    audit_path = SOURCE_LEVEL / 'full_audit_01/results.json'
    audit = s.fields.sealed(audit_path)
    api.require(s.sha(audit_path) == failed['evidence_files'][str(audit_path)]
                and audit['passed'] and audit['fresh_t0'] and audit['original_physics_and_guard_replayed']
                and audit['full_selector_policy_replayed'], 'Existing complete finer path audit')
    guards = []
    for label in audit['production_labels']:
        path = SOURCE_LEVEL / 'records' / label / 'timecap_guard/results.json'
        api.require(s.sha(path) == audit['artifacts'][str(path)], 'Existing selector-clock seal')
        guards.append(s.fields.sealed(path))
    eligible = [i for i, value in enumerate(guards) if value['stop_s'] <= ANCHOR_S]
    endpoint_index = max(eligible)
    api.require(audit['production_labels'][endpoint_index] == SOURCE_LAST
                and guards[endpoint_index + 1]['stop_s'] > ANCHOR_S,
                'Prospectively specified last whole checkpoint not after 0.400s')

    inputs = {**prior['physical_inputs'], **EXPECTED, str(audit_path): s.sha(audit_path),
              str(audit_path.with_name('completion.json')): s.sha(audit_path.with_name('completion.json'))}
    codec = original.archives.build(s.q.job.codec, preset=9)
    prefix = before = last = None
    for index, label in enumerate(audit['production_labels'][:endpoint_index + 1], 1):
        folder = SOURCE_LEVEL / 'records' / label
        guard_path = folder / 'guard_completion/results.json'
        guard = s.fields.sealed(guard_path)
        api.require(guard['passed'] and s.sha(guard_path) == audit['artifacts'][str(guard_path)],
                    'Accepted source record guard bound into full audit')
        for path, expected in guard['artifacts'].items():
            api.require(path in audit['artifacts'] and s.sha(path) == expected == audit['artifacts'][path],
                        'Original raw/receipt/trace artifact seal')
            inputs[path] = expected
        rec, prefix = codec.read_record(folder / 'call.json.xz', s.sha(PRIOR_DESIGN / 'physical_cases_01.json'), prefix)
        api.require(rec['spec'] == source_case['spec'] and rec['input_checkpoint_sha256'] == api.digest(before),
                    'Exact contiguous full-checkpoint/history ancestry from fresh t0')
        cp = rec['result']['checkpoint']
        previous_steps = 0 if before is None else before['state']['steps']
        api.require(cp['state']['steps'] == previous_steps + len(rec['rows'])
                    and api.digest(cp) == guard['full_checkpoint_sha256'], 'All saved steps and full output identity')
        expected_trace = np.asarray([[row['time_s'], *row['position_m'], *row['orientation'],
                                      *row['velocity_generalized']] for row in rec['rows']], dtype=np.float64)
        api.require(np.array_equal(expected_trace, np.load(folder / 'trace.npy', mmap_mode='r', allow_pickle=False)),
                    'Every source trace row reconstructs from unchanged raw codec')
        before, last = cp, rec
        for path in (guard_path, guard_path.with_name('completion.json')):
            inputs[str(path)] = s.sha(path)
        if index % 50 == 0:
            print('SUPPORT_SEED_RAW_RECONSTRUCTED', index, flush=True)
    api.require(before['state']['steps'] == 1395000 and before['state']['t'] == .3996279422468776
                and before['state']['pending_trial'] is None, 'Exact accepted support seed, no pending trial')
    start, stop = before['state']['t'], before['state']['t'] + DURATION_S
    cases = []
    for factor in (.0625, .03125):
        case = copy.deepcopy(next(x for x in physical_source['cases'] if x['factor'] == factor))
        case['id'] += '__same_full_state_support_diagnostic'
        case['role'] = 'discarded_same_full_state_sustained_support_diagnostic'
        case['spec']['case_id'] = case['id']
        case['spec']['horizon_s'] = stop
        cases.append(case)
    def normalized(case):
        result = copy.deepcopy(case['spec'])
        result.pop('case_id'); result.pop('refinement')
        for key in s.factory.SCALED_CONTROLS:
            result['config']['numerics'].pop(key)
        return result
    api.require(normalized(cases[0]) == normalized(cases[1])
                and all(cases[1]['spec']['config']['numerics'][key] == cases[0]['spec']['config']['numerics'][key] / 2
                        for key in s.factory.SCALED_CONTROLS), 'Only the original four numerical controls halve')
    physical = dict(schema='paper1.same-full-state-support.physical.v1', cases=cases, diagnostic_only=True,
        seed_time_s=start, local_stop_s=stop, original_paper1_horizon_s=source_case['spec']['horizon_s'],
        minimum_gap_semantics=physical_source['minimum_gap_semantics'],
        numerical_controller=copy.deepcopy(physical_source['numerical_controller']),
        numerical_controller_source_sha256=physical_source['numerical_controller_source_sha256'],
        physical_equation_changes=[], accuracy_gate_changes=[])
    physical['binding'] = api.digest(physical)
    bound(256 * 1024**2)
    DESIGN.mkdir(parents=True, exist_ok=False)
    s.commit(PHYSICAL, physical)
    seed_folder = DESIGN / 'seed_source'
    original.DOC.store(seed_folder / 'checkpoint.json', before, s.sha(PRIOR_DESIGN / 'physical_cases_01.json'))
    s.commit(seed_folder / 'prefix.json', prefix.reference())
    seed_artifacts = {str(path): s.sha(path) for path in seed_folder.iterdir() if path.is_file()}
    s.seal(seed_folder / 'provenance_01', dict(passed=True, preparation_only=True,
        source_level='f0p03125', source_last_label=SOURCE_LAST, source_physical_sha256=s.sha(PRIOR_DESIGN / 'physical_cases_01.json'),
        source_full_audit_sha256=s.sha(audit_path), raw_records_reconstructed=endpoint_index + 1,
        raw_rows_reconstructed=before['state']['steps'], full_checkpoint_sha256=api.digest(before),
        physical_state_sha256=before['state_sha256'], seed_time_s=start,
        terminal_row=last['rows'][-1], source_history_prefix=prefix.reference(),
        complete_history_preserved=True, new_transport_steps=0, new_native_solver_calls=0,
        physical_auditor_replays=0, seed_artifacts=seed_artifacts, source_evidence_files=inputs, utc=s.utc()))
    seed_checks = []
    for index in range(2):
        rebound, fresh_prefix = seed_for(index)
        record = dict(design_sha256=s.sha(PHYSICAL), rows=[],
                      result=dict(checkpoint=rebound, history=rebound['state']['history']))
        packed, state = codec.encode(record, fresh_prefix)
        restored, restored_state = codec.decode(packed, fresh_prefix)
        api.require(api.digest(record) == api.digest(restored) and state == restored_state,
                    'Original literal full-history codec roundtrip for each rebound diagnostic contract')
        seed_checks.append(dict(branch=index, factor=cases[index]['factor'], full_checkpoint_sha256=api.digest(rebound),
                                same_full_physical_state_history=True, literal_initial_history_roundtrip=True))
    for path in DESIGN.rglob('*'):
        if path.is_file():
            inputs[str(path)] = s.sha(path)
    sources = {**prior['source_files'], str(SELF): s.sha(SELF)}
    for module in list(sys.modules.values()):
        file = getattr(module, '__file__', None)
        if file and Path(file).suffix == '.py' and ROOT in Path(file).resolve().parents and Path(file).is_file():
            sources[str(Path(file).resolve())] = s.sha(file)
    api.verify_mapping(sources); api.verify_mapping(inputs)
    old_ledger = closed['ledger']
    saved = prior['baseline']['conservative_prospective_baseline_saved_steps'] + old_ledger['saved_steps']
    calls = prior['baseline']['conservative_prospective_baseline_integration_calls'] + old_ledger['calls']
    api.require((saved, calls) == (10184681, 2125), 'Current conservative cumulative baseline includes all old restart/screen charges')
    allocation = dict(old_frozen_diagnostic_step_cap=old_auth['maximum_discarded_diagnostic_steps'],
        old_frozen_diagnostic_call_cap=old_auth['maximum_diagnostic_integration_calls'],
        already_used_diagnostic_steps=old_ledger['diagnostic_steps'], already_used_diagnostic_calls=old_ledger['diagnostic_calls'],
        requested_revised_total_diagnostic_step_allocation=old_ledger['diagnostic_steps'] + NEW_STEPS,
        requested_revised_total_diagnostic_call_allocation=old_ledger['diagnostic_calls'] + NEW_CALLS,
        required_step_allocation_increase=max(0, old_ledger['diagnostic_steps'] + NEW_STEPS - old_auth['maximum_discarded_diagnostic_steps']),
        required_call_allocation_increase=max(0, old_ledger['diagnostic_calls'] + NEW_CALLS - old_auth['maximum_diagnostic_integration_calls']),
        old_frozen_documents_unchanged=True, supplemental_allocation_and_dispatch_require_independent_human_approval=True)
    proposal = dict(schema='paper1.same-full-state-support.proposal.v1', passed=True,
        status='REQUIRES_SEPARATE_HUMAN_APPROVAL_AFTER_SCIENTIFIC_STOP', dispatch_authorized=False,
        question='How much discrepancy develops over one fixed10ms sustained-support interval when the two original refinements start from exactly the same FULL physical state/history?',
        selection_rule='The last complete accepted finer raw record ending at or before the prospective0.400s anchor; fixed10ms duration. No parameter is chosen from local error outcomes.',
        logical_core_id=failed['logical_core_id'], source_level='f0p03125', source_last_record=SOURCE_LAST,
        seed_time_s=start, local_stop_s=stop, local_duration_s=DURATION_S, factors=[.0625, .03125],
        seed_checks=seed_checks, original_numerical_controller=physical['numerical_controller'],
        original_accuracy_gates=failed['original_gate_values'], budget=budget(saved, calls), diagnostic_suballocation=allocation,
        maximum_window_minutes=60, requested_numerical_interval_minutes=30, requested_postnumerical_retirement_audit_minutes=30,
        authorization_start_utc=None, authorization_end_utc=None, original_shared_end_utc=DEADLINE,
        deadline_rule='If separately approved, stop numerical work no later than min(approval+30min, original_shared_end-30min), retire/authenticate by min(approval+60min, original_shared_end). No clock reset or automatic extension.',
        workers=1, threads=1, logical_cpu=14, maximum_unverified_records=1, steps_per_record=5000,
        native_seconds_per_record=45, maximum_new_output_bytes=256 * 1024**2,
        unchanged_total_retention_bytes=20 * 1024**3, unchanged_free_reserve_bytes=20 * 1024**3,
        qualification='Before either local branch: serial256 vs split128+128 exact rows and FULL checkpoint/history; discard all512 diagnostic steps, then restart local branch from the original common seed.',
        acceptance='Each future record must pass the unchanged independent physical auditor, fixed-selector audit and lossless raw reconstruction before any successor record. Failed/censored/unknown work is retained and counted.',
        analysis='Use original held-velocity/unshifted absolute clock and unchanged full-six-component meanL1/endpoint and pose/event thresholds over the declared local interval; retain component norms as nonadditive diagnostics. Label all results local-only.',
        inference_limits=['Two factors cannot establish first-order convergence or any convergence order.',
            'A local common-state discrepancy separates newly generated local error from independent-prefix divergence only at this seed; it cannot establish the cause of the full-horizon failure.',
            'A pass cannot admit the original full horizon, select or tune a timestep cap, qualify a publication case or authorize a successor case.'],
        physics_changes=[], accuracy_gate_changes=[], contact_route_changes=[], selector_policy_changes=[],
        full_path_accuracy_promotion_authorized=False, original_full_path_admission=False, successor_dispatch_authorized=False,
        new_transport_steps=0, new_native_solver_calls=0, physical_auditor_replays=0,
        controls=pure, source_files=sources, physical_inputs=inputs, utc=s.utc())
    bound(8 * 1024**2)
    s.commit(PROPOSAL, proposal)
    s.seal(DESIGN / 'preparation_01', dict(passed=True, dispatch_authorized=False, proposal_sha256=s.sha(PROPOSAL),
        physical_design_sha256=s.sha(PHYSICAL), source_files=sources, physical_inputs=inputs,
        pure_controls=pure, seed_checks=seed_checks, new_transport_steps=0, new_native_solver_calls=0,
        original_shared_end_utc=DEADLINE, authority_timestamps_written=False, numerical_worker_launched=False, utc=s.utc()))
    print(json.dumps(dict(passed=True, dispatch_authorized=False, source_sha256=s.sha(SELF), proposal_sha256=s.sha(PROPOSAL),
        preparation_sha256=s.sha(DESIGN / 'preparation_01/results.json'), seed_time_s=start, local_stop_s=stop,
        maximum_new_saved_steps=NEW_STEPS, maximum_new_calls=NEW_CALLS, new_transport_steps=0), sort_keys=True), flush=True)


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) == 2 else None
    if command == 'controls':
        print(json.dumps(controls(), sort_keys=True), flush=True)
    elif command == 'prepare':
        prepare()
    else:
        raise SystemExit('Only controls or prepare; numerical dispatch is deliberately absent.')
