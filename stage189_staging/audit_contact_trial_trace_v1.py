"""Independent exact provenance and original-law inner-system audit.

No simulation or contact solve. Each legacy early/fallback record is consumed
once by an explicitly numbered inner solve, and each traced outer result is
bound exactly to its final accepted row. An intermediate result need not equal
that final row. No equality is replaced by a tolerance.
"""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage183_staging'))
import audit_fallback_systems_v1 as physical
import contact_trial_trace_v1 as producer

require = physical.require


def eq(a, b):
    return np.array_equal(np.asarray(a), np.asarray(b))


def evaluate(record, before):
    trace = record['contact_trial_trace']
    rows, proofs = record['rows'], record['sweep_certificates']
    require(trace['schema'] == producer.SCHEMA and trace['structural_identity'] == producer.STRUCTURAL_IDENTITY, 'qualified observer source structure')
    counts = trace['trial_inner_counts']
    require(len(counts) == len(rows) and all(type(n) is int and 1 <= n <= 80 for n in counts), 'one complete contact trial per accepted row; no unobserved/rejected trial')
    routes = trace['trial_route_counts']
    require(len(routes) == len(rows) and all(len(x) == 2 and all(type(n) is int and n >= 0 for n in x) for x in routes), 'complete route count coverage')
    require([i for i, x in enumerate(routes) if sum(x)] == [t['trial_index'] for t in trace['detailed_trials']], 'every routed trial has detailed evidence')
    early, fallback = record['early_attempts'], record['fallback_systems']
    calls, repairs = record['result']['stage119_repair_calls'], record['repairs']
    require(len(calls) == len(repairs) == len(fallback), 'complete original fallback record coverage')
    early_cursor = fallback_cursor = 0
    previous_trial = -1
    audits = []
    fallback_audits = []
    for trial in trace['detailed_trials']:
        index = trial['trial_index']
        require(type(index) is int and previous_trial < index < len(rows), 'unique ordered trial identifiers')
        previous_trial = index
        require(trial['accepted'] is True, 'no failed trial in accepted segment')
        systems = trial['inner_systems']
        require(len(systems) == counts[index] == trial['health']['iterations'], 'complete inner fixed-point iteration coverage')
        require(trial['early_range'][0] == early_cursor and trial['fallback_range'][0] == fallback_cursor, 'ordered exact trial record coverage')
        require([trial['early_range'][1]-early_cursor, trial['fallback_range'][1]-fallback_cursor] == routes[index], 'exact per-trial route counts')
        require(trial['early_range'][1] > early_cursor or trial['fallback_range'][1] > fallback_cursor, 'detailed trial has an observed route')
        inputs = trial['outer_inputs']
        require(len(inputs) == 14, 'complete frozen outer inputs')
        qold, bg, body, R, L, mass = [np.asarray(v, float) for v in inputs[:6]]
        contacts, ell, dt, mu, rhof, viscosity, diameter, sphericity = inputs[6:]
        expected_old = (before['state']['q'] if before else record['spec']['initial_state']['velocity_generalized']) if index == 0 else rows[index-1]['velocity_generalized']
        require(eq(qold, expected_old), 'exact input velocity from preceding accepted state')
        require(dt == proofs[index]['dt_s'] and eq(trial['velocity'], rows[index]['velocity_generalized']), 'exact final trial to accepted row binding')
        require([int(c[0]) for c in contacts] == rows[index]['active_contact_ids'], 'exact active contact ordering')
        backend = producer.backend
        J, gaps, _ = backend.stage41._prepare_geometry(contacts, ell)
        candidate = qold
        velocity_scale = max(np.linalg.norm(qold), np.linalg.norm(bg), 1e-30)
        for k, item in enumerate(systems):
            require(item['inner_index'] == k and item['accepted'] is True, 'sequential successful inner identities')
            require(item['dt_s'] == dt and item['friction'] == mu and item['tolerance'] == 1e-10 and item['maxiter'] == 25000, 'unchanged inner solve controls')
            require(eq(item['jacobian'], J) and eq(item['gaps_m'], gaps), 'unchanged geometry within frozen pose')
            reynolds = backend.finite_re.reynolds_number(candidate[:3]-bg[:3], rhof, viscosity, diameter)
            multiplier = backend.finite_re.inertial_multiplier(reynolds, sphericity)
            drag = R.copy(); drag[:3, :3] *= multiplier
            M = np.linalg.inv(mass/dt + drag + L)
            v = M @ (mass @ qold/dt + drag @ bg + body)
            require(eq(item['mobility'], M) and eq(item['vfree'], v), 'exact consecutive inner-system recurrence')
            require(item['early_range'][0] == early_cursor and item['fallback_range'][0] == fallback_cursor, 'sequential inner route ranges')
            ee, ff = item['early_range'][1], item['fallback_range'][1]
            require(type(ee) is int and early_cursor <= ee <= len(early) and type(ff) is int and fallback_cursor <= ff <= len(fallback), 'bounded route ranges')
            accepted_route = []
            for attempt in early[early_cursor:ee]:
                require(attempt['dt_s'] == dt and eq(attempt['gaps_m'], gaps), 'early attempt trial inputs')
                if attempt['accepted']:
                    for key in ('vfree','mobility','jacobian','gaps_m','velocity','dt_s','friction'):
                        require(eq(attempt[key], item[key]), 'exact early-to-inner binding: '+key)
                    require(attempt['health'] == item['health'], 'exact early health binding')
                    accepted_route.append('early')
            for fi in range(fallback_cursor, ff):
                system, call, repair = fallback[fi], calls[fi], repairs[fi]
                require(system['accepted'] is True and call['accepted'] is True and repair['reduced_accepted'] is True, 'successful recorded fallback')
                for key in ('vfree','mobility','jacobian','gaps_m','velocity','dt_s','friction'):
                    require(eq(system[key], item[key]), 'exact fallback-to-inner binding: '+key)
                require(system['health'] == item['health'] == call['health'], 'exact fallback health binding')
                require(call['dt_s'] == system['dt_s'] == repair['dt_s'] and call['gaps_m'] == system['gaps_m'] == repair['gaps_m'], 'original fallback input binding')
                require(system['health']['solver'] == repair['solver'] == producer.old.fast.old.NAME and system['health']['original_gaps_preserved'], 'original qualified fallback')
                fallback_audits.append(physical.physical(system)); accepted_route.append('fallback')
            require(len(accepted_route) <= 1, 'one returned route per inner solve')
            if item['health']['solver'] == 'within_pose_verified_prior':
                require(k > 0 and not accepted_route and eq(item['health']['reactions'], systems[k-1]['health']['reactions']), 'within-pose reuse binds preceding reaction')
            if item['health']['solver'] == producer.old.fast.NAME:
                require(accepted_route == ['early'], 'no omitted early accepted record')
            if item['health']['solver'] == producer.old.fast.old.NAME:
                require(accepted_route == ['fallback'], 'no omitted fallback accepted record')
            if len(gaps):
                audits.append(physical.physical(item))
            updated = np.asarray(item['velocity'])
            converged = np.linalg.norm(updated-candidate)/velocity_scale <= 1e-10
            require(converged == (k == len(systems)-1), 'original fixed-point termination, no truncated or added iteration')
            candidate = updated
            early_cursor, fallback_cursor = ee, ff
        require(trial['early_range'][1] == early_cursor and trial['fallback_range'][1] == fallback_cursor, 'exact outer route endpoints')
        require(eq(candidate, trial['velocity']) and systems[-1]['health'] == trial['health']['contact'], 'exact final inner-to-outer result')
    require(early_cursor == len(early) and fallback_cursor == len(fallback), 'every early/fallback record accounted for exactly once')
    return {'passed': True, 'detailed_trials': len(trace['detailed_trials']), 'inner_systems': len(audits),
            'early_records': early_cursor, 'fallback_records': fallback_cursor,
            'fallback_audits': fallback_audits,
            'max_contact_residual': max((r['contact_residual'] for r in audits), default=0.),
            'max_force_residual': max((r['force_residual'] for r in audits), default=0.)}
