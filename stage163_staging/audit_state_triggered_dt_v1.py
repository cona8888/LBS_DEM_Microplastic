"""Independent selector replays and immutable success/failure evidence audit."""
import math
import sys
import numpy as np
import verify_state_triggered_dt_v1 as job


def l1(a, b, start, stop, U):
    i = j = 0; left = start; pieces = []
    while left < stop:
        right = min(a[i]['time_s'], b[j]['time_s'], stop)
        pieces.append((right-left)*float(np.linalg.norm(np.array(a[i]['velocity_generalized'])-b[j]['velocity_generalized']))/U)
        left = right
        if a[i]['time_s'] <= right: i += 1
        if b[j]['time_s'] <= right: j += 1
    return math.fsum(pieces)/(stop-start)


def check_preflight(d, wi):
    api = job.api; folder = job.RUN / d['windows'][wi]['id']
    spec, binding, cp = job.setup(d, wi, .25, 'off', 'identity')
    base, off = [job.read(folder / f'identity_{s}.json') for s in ['baseline', 'off']]
    job.check(base, cp, spec, binding); job.check(off, cp, spec, binding)
    api.require(base['rows'] == off['rows'] and base['result']['checkpoint']['state'] == off['result']['checkpoint']['state'], 'off identity')
    spec, binding, cp = job.setup(d, wi, .25, 'always', 'finest_identity'); fine = job.read(folder / 'always_fine_identity.json')
    job.check(fine, cp, spec, binding)
    api.require(fine['rows'] == job.reference(d['windows'][wi])['rows'][:100], 'finest identity')
    spec, binding, cp = job.setup(d, wi, .25, 'state', 'restart')
    full, first, last = [job.read(folder / f'restart_{s}.json') for s in ['full', 'first', 'last']]
    job.check(full, cp, spec, binding); job.check(first, cp, spec, binding); job.check(last, first['result']['checkpoint'], spec, binding)
    api.require([len(r['rows']) for r in [full, first, last]] == [100, 37, 63], 'restart counts')
    api.require(full['rows'] == first['rows']+last['rows'] and full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'restart state')
    api.require(full['controller_steps'] == first['controller_steps']+last['controller_steps'] and full['discarded_trials'] == first['discarded_trials']+last['discarded_trials'], 'restart selector accounting')
    spec, binding, cp = job.pending_setup(d, wi); pending = job.read(folder / 'pending_fine_resume.json')
    job.check(pending, cp, spec, binding)
    api.require(pending['rows'] == fine['rows'][:1] and not pending['discarded_trials'], 'pending-trial resume')


def replay_controller(d, wi, rec, field, geometry):
    api = job.api; seed = api.read(d['windows'][wi]['seed_source'])['result']['checkpoint']['state']
    cfg = rec['spec']['config']; a, b, _ = cfg['prolate_semiaxes_m']; U = cfg['target_mean_interstitial_velocity_m_s']
    max_q = max_balance = 0.; predicted_discards = []; ncoarse = 0
    with job.old.hot.scope(), job.engine.runtime.repair_scope(), job.fix.scope():
        for i, (row, c) in enumerate(zip(rec['rows'], rec['controller_steps'])):
            p = rec['rows'][i-1] if i else None
            prev = seed if p is None else {'x': p['position_m'], 'p': p['orientation'], 'q': p['velocity_generalized'], 't': p['time_s'], 'recovery': seed['recovery']}
            q, h = job.diag.replay(field, geometry, rec['spec'], prev, row['dt_s'])
            error = float(np.linalg.norm(q-row['velocity_generalized'])/U)
            max_q = max(max_q, error); max_balance = max(max_balance, h['momentum_residual'], h['work_balance_relative'])
            api.require(error <= 1e-8 and max_balance <= 1e-8, 'every accepted q/balance replay')
            if c['decision'] is not None:
                coarse = min(c['nominal_dt_s'], rec['spec']['horizon_s']-prev['t'])
                qc, hc = job.diag.replay(field, geometry, rec['spec'], prev, coarse); ncoarse += 1
                xp, pp = job.model.core.mechanics.advance_pose(np.array(prev['x']), np.array(prev['p']), qc, a, coarse)
                start_ids = [int(x[0]) for x in geometry.contacts(np.array(prev['x']), np.array(prev['p']), a, b, 1e-5*b)]
                end_ids = [int(x[0]) for x in geometry.contacts(xp, pp, a, b, 1e-5*b)]
                # Independent predicate, not controller.observe().
                delta = float(np.linalg.norm(qc-np.array(prev['q']))/U)
                changed = set(start_ids) != set(end_ids); refine = changed or delta > d['velocity_change_trigger_over_U']
                recorded = c['decision']
                api.require(refine == recorded['refine'] and changed == recorded['touching_set_changed'] and abs(delta-recorded['velocity_change_over_U']) <= 1e-12, 'independent state trigger')
                api.require(sorted(start_ids) == recorded['start_touching_ids'] and sorted(end_ids) == recorded['trial_end_touching_ids'], 'independent touching sets')
                expected = c['fine_floor_dt_s'] if refine else coarse
                api.require(row['dt_s'] == expected, 'selected step')
                if refine: predicted_discards.append((c['time_s'], c['step'], coarse, expected))
    actual = [(p['time_s'], p['step'], p['discarded_dt_s'], p['replacement_dt_s']) for p in rec['discarded_trials']]
    api.require(predicted_discards == actual, 'discarded-solve cost independently reproduced')
    return {'accepted_replays': len(rec['rows']), 'coarse_replays': ncoarse, 'discarded_solves': len(actual), 'max_q_error_over_U': max_q, 'max_balance': max_balance}


def main(failed=False):
    api = job.api; d = api.read(job.DESIGN); job.verify(d)
    api.require((job.RUN / 'failure.json').exists() == failed, 'expected termination class')
    if not failed:
        result = api.read(job.OUT / 'results.json')
        api.require(api.read(job.OUT / 'completion.json')['results_sha256'] == api.sha(job.OUT / 'results.json'), 'completion seal')
        api.verify_mapping(result['artifacts'])
    api.require(job.control.selftest() == api.read(job.OUT / 'selector_selftest.json'), 'unit and analytical repeat')
    job.old.parent.configure(); spec = d['base_spec']; field, data, meta = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    geometry = job.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    reports = []; replays = []; completed_windows = []
    for wi, w in enumerate(d['windows']):
        if not (job.RUN / w['id']).exists(): continue
        check_preflight(d, wi); completed_windows.append(w['id']); ref = job.reference(w); md = job.metric_design(d, wi)
        refimp = api.read(job.OUT / (w['id']+'_reference_impulses.json'))
        api.require(job.phasejob.impulse(md, ref, field, geometry) == refimp['levels'][0], 'reference impulse replay')
        for factor in job.FACTORS:
            p = job.OUT / f"{w['id']}_factor_{factor}_summary.json"
            if not p.exists(): continue
            rec = job.joined(d, wi, factor); saved = api.read(p); imp = api.read(job.OUT / f"{w['id']}_factor_{factor}_impulses.json")
            api.require(job.phasejob.impulse(md, rec, field, geometry) == imp, 'impulse replay')
            replay = replay_controller(d, wi, rec, field, geometry); replays.append({'window': w['id'], 'factor': factor, **replay})
            report = job.metrics(d, wi, rec, ref, imp, refimp); report['window'] = w['id']; api.require(report == saved, 'primary verdict recomputed')
            U = d['base_spec']['config']['target_mean_interstitial_velocity_m_s']
            api.require(abs(l1(rec['rows'], ref['rows'], w['entry_s'], w['horizon_s'], U)-report['whole_L1_over_U']) <= 1e-12, 'independent L1')
            totals = [math.fsum(s['impulse_generalized'][k]*s['overlap_s']/s['dt_s'] for s in imp['samples']) for k in range(6)]
            api.require(np.allclose(totals, imp['total_impulse'], rtol=1e-12, atol=1e-29), 'independent impulse sum')
            reports.append(report); print('AUDIT', w['id'], factor, report['checks'], flush=True)
    if failed:
        api.require(any(not r['passed'] for r in reports), 'reproduced scientific failure required')
    else:
        api.require(len(reports) == 6 and all(r['passed'] for r in reports) and reports == result['cases'], 'complete six-case result')
    job.verify(d); out = job.OUT.parent / ('failure_audit_01' if failed else 'independent_audit_01'); out.mkdir(exist_ok=False)
    audit = {'audit_integrity_passed': True, 'controller_qualified_locally': not failed, 'failure_reproduced': failed,
             'reports': reports, 'independent_replays': replays, 'auditor_sha256': api.sha(__file__),
             'full_window_accuracy': False, 'production_promotion': False,
             'artifacts': {str(p): api.sha(p) for folder in [job.RUN, job.OUT] for p in folder.rglob('*') if p.is_file()}}
    api.write(out / 'results.json', audit, raw=True); api.write(out / 'completion.json', {'results_sha256': api.sha(out / 'results.json'), 'audit_integrity_passed': True})
    print('AUDIT COMPLETE; local controller qualified=', not failed, flush=True)


if __name__ == '__main__': main(sys.argv[1:] == ['--failed'])
