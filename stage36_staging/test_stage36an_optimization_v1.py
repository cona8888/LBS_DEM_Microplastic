"""Bounded CPU regression/benchmark. Never starts a simulation campaign."""
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import time
import numpy as np
import periodic_drag_reference_massclosed_v1 as old
import periodic_drag_optimized_v1 as opt

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT/'stage36_runs/stage36al_periodic_drag_n32_massclosed_20260910/run_01/final_state.npz'
OUT = ROOT/'stage36_evaluations/stage36an_optimization_review_20260910/verification_01'
FILES = [Path(__file__), CHECKPOINT] + [ROOT/'stage36_staging'/name for name in (
    'periodic_drag_optimized_v1.py', 'periodic_drag_reference_massclosed_v1.py',
    'periodic_drag_reference_fast_v1.py', 'periodic_drag_reference_v1.py',
    'immersed_interface_v1.py', 'body_link_extractor_v1.py', 'moving_wall_reference_v1.py')]

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def clone(s):
    return dict(s, f=s['f'].copy())

def main():
    OUT.mkdir(parents=True, exist_ok=False)
    hashes = {str(p):digest(p) for p in FILES}
    contract = {'population_abs_tolerance':1e-12, 'velocity_target_scaled_tolerance':1e-8,
                'legacy_force_reference_scaled_tolerance':1e-8, 'integration_abs_tolerance':1e-11,
                'momentum_ledger_abs_tolerance':1e-10, 'marker_slip_tolerance':2e-8,
                'density_error_tolerance':.001, 'full_step_stationary_inertia_abs_tolerance':1e-10,
                'cases':{'startup_steps':64, 'stationary_checkpoint_steps':32},
                'timing_repeats':3, 'timing_steps':16,
                'scope':'regression and timing only, not physical validation or production qualification'}
    (OUT/'contract.json').write_text(json.dumps(contract, indent=2))
    setup_start = time.perf_counter()
    original = old.initialize(32)
    old_setup_s = time.perf_counter()-setup_start
    t = time.perf_counter()
    optimized = opt.prepare(original)
    cache_setup_s = time.perf_counter()-t
    params = opt.reference.base.nominal_parameters(32)
    source = params['source_impulse_per_cell']
    probe = np.random.default_rng(3601).normal(size=(32**3,3))
    body, volume = opt.reference.base.ib.sphere_quadrature(4,8,16,32)
    direct = volume @ opt.reference.base.trilinear(probe, body+original['centre'],32)
    cached = opt.interior_integral(optimized, probe)
    integration_error = float(np.max(np.abs(direct-cached)))
    checks = {'cached_integration':integration_error <= contract['integration_abs_tolerance']}
    cases = {}
    loaded = np.load(CHECKPOINT, allow_pickle=False)['f']
    final_row = None
    for name, steps, initial in [('startup',64,original['f']),('stationary',32,loaded)]:
        a, b = dict(original,f=initial.copy()), dict(optimized,f=initial.copy())
        errors = {'population':0.,'velocity_scaled':0.,'legacy_force_scaled':0.,'ledger':0.,'slip':0.,'density':0.}
        correction_abs_sum = 0.
        for _ in range(steps):
            a, ra = old.step(a,source)
            b, rb = opt.step(b,source)
            errors['population'] = max(errors['population'],float(np.max(np.abs(a['f']-b['f']))))
            errors['velocity_scaled'] = max(errors['velocity_scaled'],float(np.max(np.abs(np.array(ra['superficial_velocity'])-rb['superficial_velocity'])))/params['target_u_lu'])
            errors['legacy_force_scaled'] = max(errors['legacy_force_scaled'],float(np.max(np.abs(np.array(ra['force_on_sphere'])-rb['legacy_substep_force_NOT_PHYSICAL'])))/params['reference_force_lu'])
            errors['ledger'] = max(errors['ledger'],max(abs(x) for x in rb['momentum_ledger_residual']))
            errors['slip'] = max(errors['slip'],rb['marker_slip'])
            errors['density'] = max(errors['density'],rb['density_error'])
            correction_abs_sum += abs(rb['mass_restoration_lu'])
        checks[name+'_trajectory'] = (errors['population'] <= 1e-12 and errors['velocity_scaled'] <= 1e-8 and errors['legacy_force_scaled'] <= 1e-8)
        checks[name+'_health'] = errors['ledger'] <= 1e-10 and errors['slip'] <= 2e-8 and errors['density'] <= .001
        cases[name] = {'steps':steps,'max_errors':errors,'absolute_mass_correction_sum':correction_abs_sum,'last_row':rb}
        if name == 'stationary':
            final_row = rb
    checks['full_step_stationary_inertia'] = max(abs(x) for x in final_row['full_step_interior_momentum_change']) <= 1e-10
    bad = dict(optimized,centre=optimized['centre']+np.array([.01,0,0]))
    try:
        opt.step(bad,source)
        checks['stale_geometry_rejected'] = False
    except ValueError:
        checks['stale_geometry_rejected'] = True
    for value in [float('nan'),-1.,.001]:
        try:
            opt.step(optimized,value)
            checks['bad_source_'+str(value)] = False
        except ValueError:
            checks['bad_source_'+str(value)] = True
    timing = {'reference':[],'optimized':[]}
    for repeat in range(3):
        order = [('reference',old,original),('optimized',opt,optimized)]
        if repeat%2: order.reverse()
        for name,module,state in order:
            state = dict(state,f=loaded.copy())
            state,_ = module.step(state,source)
            t = time.perf_counter()
            for _ in range(16): state,_ = module.step(state,source)
            timing[name].append((time.perf_counter()-t)/16)
    speedup = statistics.median(timing['reference'])/statistics.median(timing['optimized'])
    checks['input_hashes_unchanged'] = all(digest(p)==hashes[str(p)] for p in FILES)
    ux = final_row['superficial_velocity'][0]
    reference_force = 6*np.pi*.1*4*ux*1.530329436009
    results = {'status':'pass' if all(checks.values()) else 'fail', 'checks':checks,
        'input_sha256':hashes, 'contract_sha256':digest(OUT/'contract.json'),
        'python':platform.python_version(),'numpy':np.__version__, 'pid':os.getpid(),
        'reference_setup_s':old_setup_s,'extra_cache_setup_s':cache_setup_s,
        'active_projection_nodes':len(optimized['active_ids']),'total_nodes':32**3,
        'interior_quadrature_nodes':len(optimized['interior_ids']),
        'cached_integration_error':integration_error,'cases':cases,'seconds_per_step':timing,
        'median_speedup':speedup,'reference_force_at_measured_u':float(reference_force),
        'corrected_traction_ratio':final_row['force_on_sphere'][0]/reference_force,
        'total_pressure_gradient_drag_ratio':final_row['total_with_pressure_gradient'][0]/reference_force,
        'qualification':'N32 local regression only; external drag benchmark remains failed; no production promotion'}
    (OUT/'results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps({k:results[k] for k in ['status','checks','median_speedup','seconds_per_step','active_projection_nodes','corrected_traction_ratio','total_pressure_gradient_drag_ratio']},indent=2))
    if not all(checks.values()): raise SystemExit(1)

if __name__ == '__main__': main()
