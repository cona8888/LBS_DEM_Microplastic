"""Read-only re-evaluation of Stage165 and deadline scenarios; no integration.

Preserves the frozen all-candidate gate and its failed verdict. A passing
previously selected factor is reported separately, never promoted implicitly.
"""
from pathlib import Path
import datetime
import json
import sys

import fresh_start_benchmark_v1 as b

api = b.api
OUT = b.ROOT / 'stage165_evaluations/fresh_start_deadline_benchmark_20260922/failure_assessment_01'


def main():
    api.require(not OUT.exists(), 'immutable assessment already exists')
    d = api.read(b.DESIGN)
    b.verify(d)
    result_path = b.OUT / 'results.json'
    result = api.read(result_path)
    audit_path = b.AUDIT / 'results.json'
    audit = api.read(audit_path)
    for folder, data in [(b.OUT, result), (b.AUDIT, audit)]:
        api.require(api.read(folder / 'completion.json')['results_sha256'] == api.sha(folder / 'results.json'), 'completion seal')
    api.require(audit['evaluation_sha256'] == api.sha(result_path), 'audit evaluation binding')
    api.require(audit['audit_integrity_passed'] and not audit['scientific_gates_passed'] and not result['passed'], 'preserve failed scientific verdict')
    api.require(not (b.RUN / 'failure.json').exists(), 'no unreported runtime failure')
    api.verify_mapping(result['artifacts'])
    b.audit_preflight(d)
    recomputed = b.evaluate(d)
    api.require(all(result[key] == value for key, value in recomputed.items()), 'all raw-record metrics reproduced')

    comparisons = []
    for shape in result['shapes']:
        for factor, metrics in zip(d['factors'][:-1], shape['to_finest']):
            violations = {key: {'observed': metrics['endpoint'][key], 'limit': cap}
                          for key, cap in d['accuracy_limits'].items() if metrics['endpoint'][key] > cap}
            for key in ['position_over_b', 'axis_vector_norm']:
                if metrics['trace'][key] > d['accuracy_limits'][key]:
                    violations['whole_' + key] = {'observed': metrics['trace'][key], 'limit': d['accuracy_limits'][key]}
            if metrics['L1_over_U'] > .005:
                violations['mean_L1_over_U'] = {'observed': metrics['L1_over_U'], 'limit': .005}
            api.require(metrics['passed'] == (not violations), 'explicit gate reproduction')
            comparisons.append({'shape': shape['shape'], 'factor': factor,
                'previously_selected': factor == d['selected_factor'],
                'passed': metrics['passed'], 'violations': violations})
    selected = [x for x in comparisons if x['previously_selected']]
    api.require(len(selected) == 2 and all(x['passed'] for x in selected), 'selected-factor result must be represented accurately')
    failures = [x for x in comparisons if not x['passed']]
    api.require(len(failures) == 1 and failures[0]['shape'] == 'equal_volume_sphere' and failures[0]['factor'] == .125, 'frozen failure classification')

    now = datetime.datetime.now(datetime.timezone.utc)
    deadline = datetime.datetime.fromisoformat(d['deadline']['utc'])
    cutoff = deadline - datetime.timedelta(hours=d['deadline']['audit_reserve_hours'])
    available = (cutoff - now).total_seconds() / 3600
    qd = api.read(b.q.DESIGN)
    qr = api.read(b.q.OUT / 'results.json')
    scenarios = []
    rates = []
    for shape in result['shapes']:
        for cost in shape['cost']:
            rates.append({'shape': shape['shape'], 'window': 'fresh_contact_free_startup',
                          'factor': cost['factor'], 'rate': cost['seconds_per_simulated_second']})
    for window in qr['windows']:
        for cost in window['cost']:
            rates.append({'shape': 'rigid_prolate_ar4', 'window': window['id'],
                          'factor': cost['factor'], 'rate': cost['seconds_per_simulated_second']})
    for horizon_pv in [.1, 2.]:
        duration = horizon_pv / qd['base_spec']['field_metadata']['pv_per_second']
        for rate in rates:
            hours = duration * rate['rate'] / 3600
            scenarios.append({**rate, 'horizon_pv': horizon_pv, 'physical_duration_s': duration,
                'integration_hours': hours, 'with_30_percent_margin_hours': hours * 1.3,
                'fits_before_audit_cutoff': hours * 1.3 <= available})

    out = {'stage': 'Stage165 failure assessment', 'utc': now.isoformat(),
        'original_scientific_verdict': False, 'independent_raw_reload_passed': True,
        'adapter_identity_restart_storage_checks_passed': True, 'comparisons': comparisons,
        'selected_factor_passed_both_shapes': True, 'selected_factor': d['selected_factor'],
        'interpretation': 'The frozen contract required BOTH coarser levels to pass. The previously selected 0.0625 passes, but deliberately larger 0.125 fails for the sphere. This is a failed aggregate qualification, not evidence of a code defect and not automatic authority to change its gate.',
        'observed_contact_coverage': 'All six startup trajectories are contact-free; contact-window qualification remains a separate Stage164 result.',
        'deadline_utc': deadline.isoformat(), 'simulation_cutoff_utc': cutoff.isoformat(),
        'available_before_audit_hours': available, 'cost_scenarios': scenarios,
        'projection_limit': 'Constant observed rate extrapolations, not predictions of future contact occupancy, parallel scaling, early export, checkpoint growth or guaranteed completion. Parallel trajectories do not shorten an individual trajectory critical path.',
        'action': 'Hold long-run promotion. Report the preserved failed qualification and deadline risk; any corrected selection contract must be explicit and new, not a relabeling of Stage165.',
        'simulation_executed_by_this_assessment': False,
        'sources': {str(Path(__file__).resolve()): api.sha(__file__)},
        'inputs': {str(p): api.sha(p) for p in [b.DESIGN, result_path, b.OUT / 'completion.json', audit_path,
                   b.AUDIT / 'completion.json', b.q.DESIGN, b.q.OUT / 'results.json']}}
    OUT.mkdir(parents=True, exist_ok=False)
    api.write(OUT / 'results.json', out, raw=True)
    api.write(OUT / 'completion.json', {'assessment_integrity_passed': True, 'original_qualification_passed': False,
                                     'results_sha256': api.sha(OUT / 'results.json')})
    print(json.dumps({'raw_reload': True, 'original_qualification': False, 'selected_factor_both_shapes': True,
                      'available_hours': available, 'failed_comparisons': failures}, indent=2))


if __name__ == '__main__':
    main()
