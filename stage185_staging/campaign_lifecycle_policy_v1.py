"""CPU-only policy preparation for a NEW campaign, not a simulation launcher.

No DEM imports, process launch, trajectory advancement, or mutation of evidence.
The scheduler is a pure state machine. Terminal summaries require previously
independently verified observations; this module does NOT replace raw auditing.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math


GATES = {
    'whole_position_over_b_max': .02,
    'whole_axis_vector_norm_max': .01,
    'endpoint_q_over_U_max': .005,
    'mean_L1_q_over_U_max': .005,
    'exit_time_difference_s_max': .0025,
    'first_dwell_time_difference_s_max': .0025,
    'same_terminal_label': True,
    'same_dwell_flag': True,
}
COMPLETE = frozenset({'present_at_horizon', 'full_window_exit'})


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.tzinfo is not None, 'explicit timezone required')
    return dt.astimezone(timezone.utc)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream)


@dataclass(frozen=True)
class Lifecycle:
    """A failed/completed worker may never re-enter the queue in this run."""
    order: tuple
    queued: tuple
    active: tuple = ()
    retired: tuple = ()
    stop_reasons: tuple = ()


def initial(order):
    order = tuple(order)
    require(order and len(order) == len(set(order)), 'unique nonempty case order')
    return Lifecycle(order, order)


def validate(state):
    entries = state.queued + state.active + state.retired
    require(len(entries) == len(set(entries)) and set(entries) == set(state.order),
            'every frozen case belongs to exactly one lifecycle partition')
    require(state.queued == tuple(c for c in state.order if c in state.queued),
            'queued order may not change')


def stop(state, reason):
    validate(state)
    require(isinstance(reason, str) and bool(reason.strip()), 'explicit stop reason')
    reasons = state.stop_reasons if reason in state.stop_reasons else state.stop_reasons + (reason,)
    return replace(state, stop_reasons=reasons)


def dispatch(state, capacity, auditor_alive):
    validate(state)
    require(type(capacity) is int and capacity > 0, 'positive worker capacity')
    require(type(auditor_alive) is bool, 'auditor state must be known')
    if state.stop_reasons or not auditor_alive or len(state.active) >= capacity or not state.queued:
        return state, None
    case = state.queued[0]
    return replace(state, queued=state.queued[1:], active=state.active + (case,)), case


def retire(state, case, exit_code, result_sealed):
    validate(state)
    require(case in state.active, 'only a currently owned worker may retire')
    require(type(exit_code) is int and type(result_sealed) is bool, 'known process exit and seal')
    result = replace(state, active=tuple(c for c in state.active if c != case),
                     retired=state.retired + (case,))
    if exit_code != 0 or not result_sealed:
        result = stop(result, 'worker_failure:' + case)
    return result


def resource_stop(state, now_utc, simulation_cutoff_utc, free_bytes, reserve_bytes):
    require(type(free_bytes) is int and type(reserve_bytes) is int and reserve_bytes > 0,
            'known integer disk budget')
    if utc(now_utc) >= utc(simulation_cutoff_utc):
        state = stop(state, 'simulation_cutoff')
    if free_bytes <= reserve_bytes:
        state = stop(state, 'disk_reserve')
    return state


def next_audit(order, expected, available, cursor=0):
    """Fair ready-only selection; one slow case cannot block other case audits.

    Called in both RUN and DRAIN states, including after producer failure.
    A later segment cannot bypass an absent predecessor. Partial/unsealed files
    are not in available. Missing predecessor at final inventory is a failure.
    """
    order = tuple(order)
    require(order and set(expected) == set(available) == set(order), 'complete audit inventory')
    require(type(cursor) is int and 0 <= cursor < len(order), 'valid round-robin cursor')
    for offset in range(len(order)):
        index = (cursor + offset) % len(order)
        case = order[index]
        require(type(expected[case]) is int and expected[case] >= 1, 'positive expected segment')
        if expected[case] in available[case]:
            return (case, expected[case]), (index + 1) % len(order)
    return None, cursor


def may_produce(state, case, outstanding, per_case_limit=2, total_limit=6):
    validate(state)
    require(case in state.active and set(outstanding) == set(state.order), 'owned case and full lag inventory')
    require(all(type(n) is int and n >= 0 for n in outstanding.values()), 'nonnegative audit lag')
    require(type(per_case_limit) is int and per_case_limit > 0 and
            type(total_limit) is int and total_limit > 0, 'positive lag limits')
    return not state.stop_reasons and outstanding[case] < per_case_limit and sum(outstanding.values()) < total_limit


def verify_receipt(paths, case, segment, design_sha, kernel_sha, before_sha, previous_sha):
    """Verify acknowledgement against explicit expected paths and ancestry.

    The auditor independently checks raw physics before committing its receipt.
    This acknowledgement authenticates that receipt and its artifacts; it does
    not treat producer status, file existence or a Boolean alone as an audit.
    """
    p = {k: Path(v) for k, v in paths.items()}
    require(set(p) == {'raw', 'ready', 'receipt', 'trace'}, 'explicit artifact set')
    marker, receipt = read(p['ready']), read(p['receipt'])
    require(marker['case'] == receipt['case'] == case and
            marker['segment'] == receipt['segment'] == segment, 'case/segment identity')
    require(marker['design_sha256'] == receipt['design_sha256'] == design_sha and
            receipt['audit_source_sha256'] == kernel_sha, 'design/kernel binding')
    require(marker['raw_path'] == str(p['raw']) and receipt['trace_path'] == str(p['trace']),
            'expected raw/trace path')
    require(receipt['ready_sha256'] == sha(p['ready']) and
            receipt['raw_sha256'] == marker['raw_sha256'] == sha(p['raw']) and
            marker['seal_sha256'] == sha(p['raw'].with_suffix('.seal.json')) and
            receipt['trace_sha256'] == sha(p['trace']), 'all artifact hashes')
    require(receipt['previous_receipt_sha256'] == previous_sha and
            receipt['input_checkpoint_sha256'] == marker['input_checkpoint_sha256'] == before_sha,
            'receipt/checkpoint ancestry')
    summary = receipt['summary']
    require(receipt['status'] == 'independently_verified' and summary['passed'] is True,
            'passed independent physics audit')
    require(type(summary['steps']) is int and 0 < summary['steps'] == marker['steps'] and
            finite(summary['start_s']) and finite(summary['stop_s']) and
            summary['start_s'] < summary['stop_s'], 'nonempty audit clock/step coverage')
    require(summary['status'] in COMPLETE | {'paused_checkpoint', 'incomplete_budget'} and
            summary['complete_observation'] == (summary['status'] in COMPLETE),
            'audit terminal classification')
    return {'receipt_sha256': sha(p['receipt']), 'steps': summary['steps'],
            'complete_observation': summary['complete_observation']}


def observation(evidence, horizon):
    """Classify audited evidence without converting censoring into retention.

    Input is an explicit summary from a raw-evidence assembler. Full observations
    additionally require a fresh start, no numerical failures, full clock/step
    and hash coverage, and independently replayed whole-body export geometry.
    Zero accepted steps and missing audit evidence are always incomplete.
    """
    require(finite(horizon) and horizon > 0, 'positive exact observation horizon')
    errors = []
    for key in ('pending_trial', 'first_dwell_s'):
        if key not in evidence:
            errors.append('missing_' + key)
    for key in ('raw_hashes_verified', 'clock_steps_verified', 'physics_verified', 'fresh_start'):
        if evidence.get(key) is not True:
            errors.append(key)
    steps, start, end = evidence.get('steps'), evidence.get('start_s'), evidence.get('stop_s')
    if type(steps) is not int or steps <= 0:
        errors.append('no_accepted_steps')
    if not finite(start) or start != 0:
        errors.append('not_fresh_t0')
    if not finite(end) or not 0 < end <= horizon:
        errors.append('invalid_observation_clock')
    if evidence.get('rejected') != 0 or type(evidence.get('rejected')) is not int:
        errors.append('rejected_or_unknown_trials')
    if evidence.get('failure_markers') != []:
        errors.append('failure_or_unknown_inventory')
    label = evidence.get('status', 'missing')
    if label == 'present_at_horizon':
        if end != horizon or evidence.get('export_verified') is not False:
            errors.append('invalid_horizon_terminal')
    elif label == 'full_window_exit':
        if evidence.get('export_verified') is not True:
            errors.append('unverified_whole_body_export')
    else:
        errors.append('incomplete_terminal')
    if label in COMPLETE and evidence.get('pending_trial') is not None:
        errors.append('pending_trial_at_terminal')
    dwell = evidence.get('first_dwell_s')
    if dwell is not None and (not finite(dwell) or not finite(end) or not 0 < dwell <= end):
        errors.append('invalid_first_dwell_clock')
    complete = not errors
    return {'complete_observation': complete, 'status': label, 'reasons': errors,
            'observation': ('whole_body_export' if label == 'full_window_exit' else
                            'not_exported_by_horizon') if complete else 'incomplete_or_failed',
            'start_s': start, 'stop_s': end, 'steps': steps, 'first_dwell_s': dwell,
            'irreversible_retention_inferred': False}


def pair_gates(first, second, metrics, gates):
    require(gates == GATES, 'unchanged original Stage167 full-path gates')
    if not (first['complete_observation'] and second['complete_observation']):
        return {'passed': False, 'reason': 'incomplete observation; no extrapolation', 'checks': {}}
    require(metrics is not None and metrics['common_start_s'] == 0 and
            metrics['common_stop_s'] == min(first['stop_s'], second['stop_s']) and
            metrics['common_duration_s'] == metrics['common_stop_s'], 'entire fresh common clock')
    names = ('whole_position_over_b_max', 'whole_axis_vector_norm_max',
             'endpoint_q_over_U_max', 'mean_L1_q_over_U_max')
    require(all(finite(metrics[k]) and metrics[k] >= 0 for k in names), 'finite nonnegative path errors')
    checks = {key: metrics[key] <= gates[key] for key in names}
    checks['same_terminal_label'] = first['status'] == second['status']
    checks['exit_time_difference'] = abs(first['stop_s'] - second['stop_s']) <= gates['exit_time_difference_s_max']
    da, db = first['first_dwell_s'], second['first_dwell_s']
    checks['same_dwell_flag'] = (da is None) == (db is None)
    checks['first_dwell_time_difference'] = (da is None and db is None) or (
        da is not None and db is not None and abs(da - db) <= gates['first_dwell_time_difference_s_max'])
    return {'passed': all(checks.values()), 'checks': checks, 'metrics': metrics}


def campaign_summary(cases, observations, comparisons, failures, unsealed, active_workers):
    """No population release calculation; keep both labelled placements separate."""
    order = [c['id'] for c in cases]
    require(len(order) == 6 and len(set(order)) == 6 and set(observations) == set(order),
            'all six frozen cases, including missing or failed observations')
    require(type(active_workers) is int and active_workers >= 0, 'known owned process inventory')
    require(type(failures) is list and type(unsealed) is list, 'explicit failure and artifact inventories')
    require(set(comparisons) == {'rigid_prolate_ar4', 'equal_volume_sphere'}, 'both selected/fine comparisons required')
    complete = all(observations[c]['complete_observation'] for c in order)
    pair_pass = all(comparisons[s].get('passed') is True for s in comparisons)
    ready = complete and pair_pass and not failures and not unsealed and active_workers == 0
    return {'passed': ready, 'all_observations_complete': complete,
            'full_path_numerical_qualification': ready, 'failures': failures,
            'unsealed_artifacts': unsealed, 'active_workers': active_workers,
            'placements': [{'sample_id': sample, 'cases': [
                {'case_id': c['id'], 'shape': c['shape'], 'factor': c['factor'], **observations[c['id']]}
                for c in cases if c['sample_id'] == sample]} for sample in (0, 124)],
            'comparisons': comparisons, 'population_release_estimate': None,
            'empirical_validation': False, 'irreversible_retention_inferred': False}
