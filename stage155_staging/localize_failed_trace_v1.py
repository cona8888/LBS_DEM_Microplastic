"""Read-only localization of Stage155 failures. No revised acceptance rules."""
from pathlib import Path
import numpy as np
import contact_transitions_v1 as job

api = job.api
OUT = job.OUT.parent / 'failure_localization_01'


def history(rec, source):
    s = source['state']
    rows = [{'time_s': s['t'], 'velocity_generalized': s['q']}] + rec['rows']
    return np.array([r['time_s'] for r in rows]), np.array([r['velocity_generalized'] for r in rows])


def interpolate(t, q, common):
    return np.column_stack([np.interp(common, t, q[:, k]) for k in range(6)])


def nearby(rows, time):
    times = np.array([r['time_s'] for r in rows])
    at = int(np.searchsorted(times, time))
    return [{k: r[k] for k in ['time_s', 'dt_s', 'velocity_generalized', 'active_contact_ids', 'supported_bearing_ids']}
            for r in rows[max(0, at-2):min(len(rows), at+3)]]


def main():
    d = api.read(job.DESIGN)
    job.verify(d)
    evaluation = api.read(job.OUT / 'results.json')
    audit = api.read(job.AUDIT / 'results.json')
    api.require(not evaluation['passed'] and audit['audit_integrity_passed'] and not audit['scientific_gates_passed'], 'expected verified scientific failure')
    for folder in [job.OUT, job.AUDIT]:
        api.require(api.sha(folder / 'results.json') == api.read(folder / 'completion.json')['results_sha256'], 'evidence seal')
    api.verify_mapping(evaluation['artifacts'])
    job.parent.configure()
    answers = []
    for wi, w in enumerate(d['windows']):
        records = [job.join_case(d, wi, f) for f in job.FACTORS]
        source = api.read(job.RUN / w['id'] / 'seed.json')['result']['checkpoint']
        ref_t, ref_q = history(records[-1], source)
        U = records[-1]['spec']['config']['target_mean_interstitial_velocity_m_s']
        result = {'id': w['id'], 'comparisons': []}
        for factor, rec in zip(job.FACTORS[:-1], records[:-1]):
            t, q = history(rec, source)
            times = np.unique(np.r_[t, ref_t])
            delta = interpolate(t, q, times) - interpolate(ref_t, ref_q, times)
            norm = np.linalg.norm(delta, axis=1) / U
            maximum = int(np.argmax(norm))
            dt0 = max(r['dt_s'] for r in records[0]['rows'])
            events = evaluation['windows'][wi]['events']
            # Descriptive masks only. No masking is used for pass/fail.
            outside = np.ones(len(times), dtype=bool)
            for ev in events:
                outside &= np.abs(times - ev['midpoint_s']) > 5 * dt0
            threshold = d['accuracy']['limits']['generalized_velocity_relative']
            segments = []
            begin = None
            for i, high in enumerate(norm > threshold):
                if high and begin is None:
                    begin = i
                if begin is not None and (not high or i == len(norm)-1):
                    end = i-1 if not high else i
                    indices = range(begin, end+1)
                    peak = max(indices, key=lambda j: norm[j])
                    segments.append({'start_sample_s': float(times[begin]), 'last_sample_s': float(times[end]),
                                     'sample_span_s': float(times[end]-times[begin]), 'maximum_over_U': float(norm[peak]),
                                     'peak_time_s': float(times[peak])})
                    begin = None
            peak_time = float(times[maximum])
            result['comparisons'].append({
                'factor_vs_finest': factor, 'max_difference_over_U': float(norm[maximum]),
                'peak_time_s': peak_time, 'peak_components_over_U': (delta[maximum]/U).tolist(),
                'max_translation_difference_over_U': float(np.max(np.linalg.norm(delta[:, :3], axis=1))/U),
                'max_scaled_rotation_difference_over_U': float(np.max(np.linalg.norm(delta[:, 3:], axis=1))/U),
                'time_averaged_norm_difference_over_U': float(np.trapezoid(norm, times)/(times[-1]-times[0])),
                'maximum_outside_5_coarse_steps_from_support_events_over_U': float(np.max(norm[outside])),
                'exceedance_sample_spans': segments,
                'coarser_peak_neighborhood': nearby(rec['rows'], peak_time),
                'finest_peak_neighborhood': nearby(records[-1]['rows'], peak_time),
            })
        answers.append(result)
    report = {'stage': 'Stage155 failure localization', 'scientific_failure_preserved': True,
              'no_model_or_acceptance_change': True, 'diagnostics_not_a_new_pass_rule': True,
              'windows': answers, 'source_sha256': api.sha(__file__),
              'inputs': {str(p): api.sha(p) for p in [job.DESIGN, job.OUT/'results.json', job.AUDIT/'results.json']}}
    OUT.mkdir(parents=True, exist_ok=False)
    api.write(OUT/'results.json', report, raw=True)
    api.write(OUT/'completion.json', {'results_sha256': api.sha(OUT/'results.json')})
    for w in answers:
        for c in w['comparisons']:
            print(w['id'], c['factor_vs_finest'], 'MAX', c['max_difference_over_U'], 'AT', c['peak_time_s'],
                  'MEAN', c['time_averaged_norm_difference_over_U'], 'OUTSIDE', c['maximum_outside_5_coarse_steps_from_support_events_over_U'], flush=True)


if __name__ == '__main__':
    main()
