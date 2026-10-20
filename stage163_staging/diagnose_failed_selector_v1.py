"""Read-only post-failure comparison; no new integration or retuned threshold."""
import math
from pathlib import Path
import numpy as np
import verify_state_triggered_dt_v1 as job


def main():
    api = job.api; d = api.read(job.DESIGN); job.verify(d)
    fa = job.OUT.parent / 'failure_audit_01'
    audited = api.read(fa / 'results.json')
    api.require(api.read(fa / 'completion.json')['results_sha256'] == api.sha(fa / 'results.json'), 'failure audit seal')
    api.require(audited['failure_reproduced'] and not audited['controller_qualified_locally'], 'confirmed failure')
    api.verify_mapping(audited['artifacts'])
    w = d['windows'][0]; a = job.joined(d, 0, 1.); b = job.joined(d, 0, .5)
    _, _, ca = job.setup(d, 0, 1.); _, _, cb = job.setup(d, 0, .5)
    api.require(ca['state'] == cb['state'], 'identical complete initial state')
    first_a, first_b = a['controller_steps'][0], b['controller_steps'][0]
    api.require(first_a['decision']['refine'] and not first_b['decision']['refine'], 'first-state selection inversion')
    first_ratio = first_b['accepted_dt_s']/first_a['accepted_dt_s']
    api.require(abs(first_ratio-8.) < 1e-12, 'eightfold actual timestep inversion')
    i = j = 0; left = w['entry_s']; inverted_durations = []; inversion_count = 0; max_ratio = 0.
    while left < w['horizon_s']:
        right = min(a['rows'][i]['time_s'], b['rows'][j]['time_s'], w['horizon_s'])
        ratio = b['rows'][j]['dt_s']/a['rows'][i]['dt_s']; max_ratio = max(max_ratio, ratio)
        if ratio > 1+1e-10:
            inverted_durations.append(right-left); inversion_count += 1
        left = right
        if a['rows'][i]['time_s'] <= right: i += 1
        if b['rows'][j]['time_s'] <= right: j += 1
    inverted = math.fsum(inverted_durations)/(w['horizon_s']-w['entry_s'])
    uniform = {**job.v.joined(api.read(job.v.DESIGN), 0, .0625), 'factor': .0625, 'phase': 1.}
    ref = job.reference(w); refimp = api.read(job.OUT / 'engagement_reference_impulses.json')
    archived_imp = api.read(job.v.OUT / 'engagement_impulses.json')['levels'][0]
    api.require(archived_imp['factor'] == .0625, 'pre-existing uniform comparator')
    uniform_report = job.phasejob.case_metrics(job.metric_design(d, 0), uniform, ref, archived_imp, refimp)
    seed = api.read(w['seed_source']); args = [seed['rows'][-1]['supported_bearing_ids'], seed['result']['time_s'], w['grain_id'], w['after_present'], d['local_event_persistence_s']]
    ue, re = job.old.event(uniform['rows'], *args), job.old.event(ref['rows'], *args)
    event_error = abs(ue['midpoint_s']-re['midpoint_s']); event_limit = 4*max(r['dt_s'] for r in uniform['rows'])
    api.require(uniform_report['passed'] and event_error <= event_limit, 'existing uniform accuracy under declared absolute metrics')
    costs = []
    for rec in [a, b]:
        solves = len(rec['rows'])+len(rec['discarded_trials'])
        costs.append({'nominal_factor': rec['factor'], 'accepted_steps': len(rec['rows']), 'discarded_solves': len(rec['discarded_trials']),
                      'total_contact_solves': solves, 'ratio_to_existing_accurate_uniform': solves/len(uniform['rows']),
                      'velocity_trigger_count': sum(p['decision']['velocity_change_over_U'] > d['velocity_change_trigger_over_U'] for p in rec['discarded_trials']),
                      'touching_change_count': sum(p['decision']['touching_set_changed'] for p in rec['discarded_trials'])})
    result = {'stage': 'Stage163 post-failure diagnosis', 'diagnosis_integrity_passed': True,
              'controller_qualified_locally': False, 'production_promotion': False, 'new_simulations': 0,
              'first_identical_state': {'coarser_nominal': first_a, 'finer_nominal': first_b, 'actual_timestep_ratio_finer_over_coarser': first_ratio},
              'physical_time_fraction_with_larger_step_at_finer_nominal_setting': inverted,
              'maximum_actual_timestep_ratio': max_ratio, 'overlap_intervals_with_inversion': inversion_count,
              'existing_uniform_comparator': {'factor': .0625, 'steps': len(uniform['rows']), 'metrics': uniform_report, 'event_error_s': event_error, 'event_limit_s': event_limit,
                                              'claim': 'Post-failure cost context using existing immutable data and current absolute metrics only. The original Stage159 failure is not relabeled.'},
              'costs': costs,
              'interpretation': 'A fixed velocity-increment threshold is timestep-dependent, not a truncation-error estimate. Halving nominal dt turns refinement off at the same entry state and creates an eight-times larger actual step. Subsequent meshes are not ordered refinements. Health, discrete balance and restart pass; the smaller-nominal case fails endpoint accuracy. Trial overhead also exceeds a previously accurate uniform setting.',
              'revised_next_step': 'Retain the verified uniform integration as baseline. Do not tune this threshold or promote the trial selector. Design a local coarse-versus-substep solution-error estimator, including a non-smooth impulse/contact-change treatment and restart-safe trial accounting; require benefit against the cheapest accurate uniform comparator. Verify analytically and on these short windows before longer trajectories.',
              'design_sha256': api.sha(job.DESIGN), 'failure_audit_sha256': api.sha(fa / 'results.json'), 'diagnoser_sha256': api.sha(__file__),
              'uniform_impulse_source_sha256': api.sha(job.v.OUT / 'engagement_impulses.json'),
              'failed_case_summary_sha256': api.sha(job.OUT / 'engagement_factor_0.5_summary.json')}
    job.verify(d); out = job.OUT.parent / 'failure_diagnosis_01'; out.mkdir(exist_ok=False)
    api.write(out / 'results.json', result, raw=True); api.write(out / 'completion.json', {'results_sha256': api.sha(out / 'results.json'), 'diagnosis_integrity_passed': True})
    print('DIAGNOSIS', {'initial_actual_step_ratio': first_ratio, 'time_fraction_nonnested': inverted, 'costs': costs}, flush=True)


if __name__ == '__main__': main()
