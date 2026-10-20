"""Read-only qualification/budget gate; executes no transport or contact solve.

Preserves the original observation horizon, reference resolution, runtime
margin and four-hour audit reserve. Prefix-reuse estimates are scenarios,
not authorization to migrate or restart any archived trajectory.
"""
from pathlib import Path
from decimal import Decimal
import datetime as dt
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage169_staging'))
import local_regression_v2 as revised

job = revised.job
api, parent = job.api, job.parent
OUT = ROOT / 'stage170_evaluations/repaired_solver_launch_readiness_20260923/assessment_01'
AUDIT169 = job.unit.EVAL / 'independent_audit_01'
FAIL167 = parent.OUT.parent / 'failure_assessment_01'
ANCHORS = {
    str(parent.DESIGN): '79834baa71a68a7e9a20901763a8779481d1a620dc0f48a13bca3fe884b1de84',
    str(job.DESIGN): '8784cddcc4c1e489c75223cd28f052041538094bdd49dac818d72312f25aa1f9',
    str(AUDIT169 / 'results.json'): 'dd9aa8ca022247ff83958841c5cf0078e6432871a0719c6e227c3985309d9acf',
    str(FAIL167 / 'results.json'): '8d5625f9797cae604d9c96d4f3fcfb33fa8807e10b4e0e87d1c1db75d60d6a39',
}


def remaining_hours(horizon, observed, rate, margin):
    api.require(all(math.isfinite(x) for x in [horizon, observed, rate, margin]), 'finite cost inputs')
    api.require(0 <= observed <= horizon and rate > 0 and margin >= 1, 'valid cost domain')
    value = (horizon-observed)*rate*margin/3600
    oracle = (Decimal(str(horizon))-Decimal(str(observed)))*Decimal(str(rate))*Decimal(str(margin))/Decimal(3600)
    api.require(abs(value-float(oracle)) <= 1e-10, 'independent decimal cost arithmetic')
    return value


def main():
    api.verify_mapping(ANCHORS)
    design = api.read(parent.DESIGN)
    parent.verify(design)
    job.verify(api.read(job.DESIGN))
    audit = api.read(AUDIT169/'results.json')
    seal = api.read(AUDIT169/'completion.json')
    api.require(audit['audit_integrity_passed'] and audit['local_repair_verified'] and not audit['full_path_qualified'], 'local repair claim boundary')
    api.require(seal['results_sha256'] == api.sha(AUDIT169/'results.json'), 'local audit seal')
    api.verify_mapping(seal['artifacts'])
    for name in ['units_01', 'refined_units_01', 'refined_invariance_01']:
        folder = job.unit.EVAL / name
        result, completion = api.read(folder/'results.json'), api.read(folder/'completion.json')
        api.require(result['passed'] and completion['results_sha256'] == api.sha(folder/'results.json'), 'repair unit seals')
    failure = api.read(FAIL167/'results.json')
    failure_seal = api.read(FAIL167/'completion.json')
    api.require(failure_seal['results_sha256'] == api.sha(FAIL167/'results.json') and failure['audit_integrity_passed'], 'failed campaign audit integrity')
    api.require(not failure['scientific_gates_passed'] and not failure['all_observations_complete'], 'preserve failed campaign verdict')
    artifacts = dict(ANCHORS)
    for folder in [AUDIT169, FAIL167]:
        artifacts[str(folder/'completion.json')] = api.sha(folder/'completion.json')
    # Re-derive the frozen conservative rate, not a new post-hoc rate selection.
    cost_path = parent.b.q.OUT / 'results.json'
    api.require(design['inputs'][str(cost_path)] == api.sha(cost_path), 'original cost input')
    costs = api.read(cost_path)
    fine_factor = design['reference_factor']
    rate = max(c['seconds_per_simulated_second'] for w in costs['windows'] for c in w['cost'] if c['factor'] == fine_factor)
    api.require(rate == design['cost']['fibre_contact_rates_s_per_simulated_s'][str(fine_factor)], 'original conservative rate reproduced')
    fine_case = next(c for c in design['cases'] if c['shape']=='rigid_prolate_ar4' and c['sample_id']==0 and c['factor']==fine_factor)
    horizon, margin = fine_case['spec']['horizon_s'], design['budget']['runtime_margin']
    api.require(fine_case['spec']['horizon_pv'] == .1 and margin == 1.3, 'unchanged observation and reserve margin')
    fresh_hours = remaining_hours(horizon, 0., rate, margin)
    api.require(abs(fresh_hours-design['cost']['critical_path_hours_with_margin']) < 1e-12, 'frozen critical path reproduced')
    cutoff = dt.datetime.fromisoformat(design['simulation_cutoff_utc']).astimezone(dt.timezone.utc)
    deadline = dt.datetime.fromisoformat(design['deadline']['utc']).astimezone(dt.timezone.utc)
    reserve = design['deadline']['audit_reserve_hours']
    api.require(reserve == 4 and (deadline-cutoff).total_seconds() == 4*3600, 'four-hour audit reserve retained')
    api.require(cutoff.isoformat() == '2026-09-24T18:59:00+00:00', 'UTC/BST cutoff conversion')
    api.require(abs(remaining_hours(4., 1., 3600., 1.3)-3.9) < 1e-14, 'cost oracle test')
    # Independently seal-check both healthy fibre endpoints. Do not migrate them.
    endpoints = []
    for c in [c for c in design['cases'] if c['sample_id']==0 and c['shape']=='rigid_prolate_ar4']:
        folder = parent.RUN / c['id']
        case_path, completion_path = folder/'case_result.json', folder/'completion.json'
        saved, completion = api.read(case_path), api.read(completion_path)
        for path in [case_path, completion_path]:
            api.require(failure['artifacts'][str(path)] == api.sha(path), 'endpoint bound to archived audit')
            artifacts[str(path)] = api.sha(path)
        api.require(completion['result_sha256'] == api.sha(case_path), 'case seal')
        api.require(saved['reason']=='supervisor_cooperative_stop' and not saved['complete_observation'], 'incomplete is not retention')
        last = saved['entries'][-1]
        raw_path = Path(last['path'])
        api.require(api.sha(raw_path)==last['sha256'] and api.sha(raw_path.with_suffix('.seal.json'))==last['seal_sha256'], 'last raw/seal hashes')
        raw = parent.storage.read_record(raw_path, api.sha(parent.DESIGN))
        final = raw['result']
        api.require(final==saved['final_result'] and final['rejected']==0 and not final.get('stage119_repair_calls'), 'healthy bound endpoint')
        api.require(parent.engine.prior.reference.independent_health(final, raw['spec'])['passed'], 'endpoint health')
        for path in [raw_path, raw_path.with_suffix('.seal.json')]: artifacts[str(path)] = api.sha(path)
        endpoints.append({'case_id': c['id'], 'factor': c['factor'], 'observed_s': final['time_s'],
                          'integration_runtime_s': saved['integration_runtime_s'], 'steps': final['steps'],
                          'complete_observation': False, 'prefix_reuse_authorized': False})
    endpoint = next(e for e in endpoints if e['factor']==fine_factor)
    progress = endpoint['observed_s']
    prefix_hours = remaining_hours(horizon, progress, rate, margin)
    observed_rate = endpoint['integration_runtime_s']/progress
    observed_fresh = remaining_hours(horizon, 0., observed_rate, margin)
    observed_prefix = remaining_hours(horizon, progress, observed_rate, margin)
    now = dt.datetime.now(dt.timezone.utc)
    available = max(0., (cutoff-now).total_seconds()/3600)
    scenarios = []
    for name, hours, basis in [
        ('fresh_finer_fibre_frozen_rate', fresh_hours, 'Binding frozen launch-budget gate; excludes new preflight time.'),
        ('hypothetical_verified_prefix_reuse_frozen_rate', prefix_hours, 'Optimistic scenario only: assumes safe migration not yet qualified or authorized.'),
        ('fresh_finer_fibre_observed_prefix_average', observed_fresh, 'Sensitivity only; cannot replace the frozen worst-window policy.'),
        ('hypothetical_prefix_reuse_observed_average', observed_prefix, 'Sensitivity only; assumes future cost remains at the prefix mean.'),
    ]:
        scenarios.append({'name': name, 'integration_hours_with_margin': hours,
                          'available_integration_hours': available, 'slack_hours': available-hours,
                          'fits_cutoff': hours <= available, 'basis': basis,
                          'conditional_finish_with_audit_utc': (now+dt.timedelta(hours=hours+reserve)).isoformat()})
    result = {'audit_integrity_passed': True, 'launch_budget_passed': fresh_hours <= available,
              'full_path_qualified': False, 'ready_to_launch': False,
              'reason': 'Frozen full-path launch budget does not fit; local solver verification is not full-path qualification.' if fresh_hours > available else 'Budget alone does not authorize restart or replace integration qualification.',
              'checked_utc': now.isoformat(), 'simulation_cutoff_utc': cutoff.isoformat(), 'publication_deadline_utc': deadline.isoformat(),
              'observation_horizon_s': horizon, 'observation_horizon_pv': .1, 'reference_factor': fine_factor,
              'frozen_rate_s_per_simulated_s': rate, 'observed_prefix_rate_s_per_simulated_s': observed_rate,
              'runtime_margin': margin, 'audit_reserve_hours': reserve, 'scenarios': scenarios, 'healthy_endpoints': endpoints,
              'new_trajectory_steps': 0, 'simulation_restarted': False, 'physics_changed': False,
              'gates_relaxed': False, 'old_campaign_verdict_changed': False,
              'decision_needed': 'Keep the 0.1-PV reference comparison and revise deadline, or explicitly approve a narrower observation claim. Neither is silently applied.',
              'limitations': ['Cost extrapolations are not completion guarantees.', 'Unseen contacts and repaired-sphere costs may add time.',
                             'A shorter horizon changes the research question and does not complete the original 0.1-PV observation.',
                             'Dropping the fine reference would leave full-path numerical accuracy unqualified.',
                             'Adding workers does not shorten one serial reference trajectory.'],
              'source_sha256': api.sha(__file__), 'inputs': artifacts}
    api.verify_mapping(ANCHORS)
    job.verify(api.read(job.DESIGN))
    artifacts[str(cost_path)] = api.sha(cost_path)
    OUT.mkdir(parents=True, exist_ok=False)
    api.write(OUT/'results.json', result)
    api.write(OUT/'completion.json', {'audit_integrity_passed': True, 'launch_budget_passed': result['launch_budget_passed'],
                                    'ready_to_launch': False, 'results_sha256': api.sha(OUT/'results.json'),
                                    'source_sha256': api.sha(__file__)})
    print('READINESS', result['ready_to_launch'], 'NEW_STEPS', 0, 'AVAILABLE_HOURS', available, flush=True)
    for s in scenarios: print(s['name'], 'HOURS', s['integration_hours_with_margin'], 'FITS', s['fits_cutoff'], flush=True)


if __name__ == '__main__': main()
