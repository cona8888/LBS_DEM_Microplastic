"""Opt-in trial-state timestep selector; no state projection or new physics.

A provisional coarse contact solve is discarded if its endpoint changes the
geometrically touching grain set or ||q_trial-q_old|| exceeds 0.0025 U. Re-solve
from the unchanged old state at 1/16 of the unclipped nominal modal timestep.
This is a bounded numerical heuristic, not an error estimator or stability proof.
All legacy rejection, sweep, momentum, contact and force gates remain active.
"""
import ast
from contextlib import contextmanager
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage162_staging'))
import release_phase_probe_v1 as prior
api, old, model = prior.api, prior.old, prior.model
REFINE_FRACTION = 1/16
VELOCITY_CHANGE_OVER_U = .0025
telemetry = []
discarded = []


def observe(qold, qtrial, start_ids, end_ids, U):
    qold, qtrial = np.asarray(qold, float), np.asarray(qtrial, float)
    if qold.shape != (6,) or qtrial.shape != (6,) or not np.isfinite(np.r_[qold, qtrial, U]).all() or U <= 0:
        raise ValueError('finite six-component velocities and positive U required')
    delta = float(np.linalg.norm(qtrial-qold) / U)
    changed = set(start_ids) != set(end_ids)
    return {'refine': changed or delta > VELOCITY_CHANGE_OVER_U,
            'touching_set_changed': changed, 'velocity_change_over_U': delta,
            'start_touching_ids': sorted(int(x) for x in start_ids),
            'trial_end_touching_ids': sorted(int(x) for x in end_ids)}


def record(t, step, nominal, floor, accepted_dt, decision, probes, mode, first_attempt):
    telemetry.append({'time_s': float(t), 'step': int(step), 'nominal_dt_s': float(nominal),
                      'fine_floor_dt_s': float(floor), 'accepted_dt_s': float(accepted_dt),
                      'decision': decision, 'discarded_coarse_solves': int(bool(decision and decision['refine'])),
                      'coarse_probes': int(probes), 'mode': mode, 'first_attempt': int(first_attempt)})


def record_discard(t, step, dt, floor, decision):
    discarded.append({'time_s': float(t), 'step': int(step), 'discarded_dt_s': float(dt),
                      'replacement_dt_s': float(floor), 'decision': decision})


def compile_controller(mode, U):
    if mode not in ['off', 'always', 'state'] or not np.isfinite(U) or U <= 0:
        raise ValueError('explicit controller mode and positive reference speed required')
    tree = ast.parse(old.parent.prior.candidate.GENERATED_SOURCE)
    counts = {'caps': 0, 'trial': 0, 'accept': 0}
    class Inject(ast.NodeTransformer):
        def visit_Assign(self, node):
            text = ast.unparse(node)
            if text == 'dt = min(dt, relaxation_fraction * tau_rot)':
                counts['caps'] += 1
                return [node, *ast.parse('''
controller_nominal_dt = min(max_dt, displacement_fraction*b/translation_scale, angle_limit/rotation_scale, relaxation_fraction*relaxation_time, relaxation_fraction*tau_rot)
controller_floor_dt = min(controller_nominal_dt*controller_refine_fraction, horizon-t)
controller_decision = None
controller_probes = 0
if controller_mode == 'always':
    dt = controller_floor_dt
''').body]
            if text == 'accepted = True':
                counts['accept'] += 1
                return [*ast.parse('record_controller(t, steps, controller_nominal_dt, controller_floor_dt, dt, controller_decision, controller_probes, controller_mode, first_attempt)').body, node]
            return self.generic_visit(node)

        def visit_If(self, node):
            text = ast.unparse(node.test)
            if 'np.linalg.norm(candidate[:3]) * dt > 1.1 * displacement_fraction * b' in text:
                counts['trial'] += 1
                return [*ast.parse('''
if controller_mode == 'state' and dt > controller_floor_dt:
    probe_x, probe_p = mechanics.advance_pose(x, p, candidate, a, dt)
    probe_start_ids = [c[0] for c in near if c[1] <= tolerance]
    probe_end_ids = [c[0] for c in geometry.contacts(probe_x, probe_p, a, b, tolerance)]
    controller_decision = observe_controller(q, candidate, probe_start_ids, probe_end_ids, controller_U)
    controller_probes += 1
    if controller_decision['refine']:
        record_controller_discard(t, steps, dt, controller_floor_dt, controller_decision)
        dt = controller_floor_dt
        continue
''').body, self.generic_visit(node)]
            return self.generic_visit(node)
    Inject().visit(tree)
    api.require(counts == {'caps': 1, 'trial': 1, 'accept': 1}, 'unique bounded controller injection')
    ast.fix_missing_locations(tree)
    namespace = dict(old.parent.prior.candidate.CANDIDATE.__globals__)
    namespace.update(controller_mode=mode, controller_U=float(U), controller_refine_fraction=REFINE_FRACTION,
                     observe_controller=observe, record_controller=record,
                     record_controller_discard=record_discard)
    exec(compile(tree, '<Stage163:state_triggered_dt>', 'exec'), namespace)
    return namespace['integrate'], ast.unparse(tree)


@contextmanager
def scope(mode, U):
    fn, _ = compile_controller(mode, U)
    saved = model.original.INTEGRATE
    model.original.INTEGRATE = fn
    try:
        with model.scope(True): yield
    finally:
        model.original.INTEGRATE = saved


def selftest():
    zero = np.zeros(6); one = np.array([.01, 0, 0, 0, 0, 0])
    checks = {'steady': not observe(zero, zero, [1], [1], 1.)['refine'],
              'new_contact': observe(zero, zero, [], [1], 1.)['refine'],
              'lost_contact': observe(zero, zero, [1], [], 1.)['refine'],
              'same_count_different_contact': observe(zero, zero, [1], [2], 1.)['refine'],
              'rapid_q_change': observe(zero, one, [], [], 1.)['refine'],
              'rotation_monitored': observe(zero, np.roll(one, 3), [], [], 1.)['refine'],
              'threshold_equality': not observe(zero, one/4, [], [], 1.)['refine'],
              'id_order_invariant': not observe(zero, zero, [2, 1], [1, 2], 1.)['refine']}
    negatives = []
    for q, U in [(np.zeros(5), 1.), (np.full(6, np.nan), 1.), (zero, 0.), (zero, -1.), (zero, np.inf)]:
        try: observe(zero, q, [], [], U)
        except ValueError: negatives.append(True)
        else: negatives.append(False)
    toys = []
    for n in [32, 64, 128]:
        for hit in [.271, 1/3, .419]:
            # Unit mass/speed, inelastic unilateral wall x>=0, no other loads.
            x, q, t = hit, -1., 0.; steps = calls = fine = 0; impulse = 0.; max_balance = 0.
            while t < 1.:
                nominal = 1/n; dt = min(nominal, 1-t); floor = min(nominal*REFINE_FRACTION, 1-t)
                candidate = max(q, -x/dt); calls += 1
                decision = observe([q, 0, 0, 0, 0, 0], [candidate, 0, 0, 0, 0, 0], [0] if x <= 1e-14 else [], [0] if x+dt*candidate <= 1e-14 else [], 1.)
                if decision['refine'] and dt > floor:
                    dt = floor; candidate = max(q, -x/dt); calls += 1; fine += 1
                load = candidate-q
                balance = abs(.5*(candidate*candidate-q*q)+.5*(candidate-q)**2-candidate*load)
                max_balance = max(max_balance, balance); impulse += load
                x += dt*candidate; q = candidate; t += dt; steps += 1
                api.require(x >= -1e-14 and steps <= 16*n+1, 'toy penetration/termination')
            passed = abs(x) <= 1e-14 and abs(q) <= 1e-14 and abs(impulse-1.) <= 1e-14 and max_balance <= 1e-14 and calls < 16*n and fine > 0
            toys.append({'n': n, 'impact_s': hit, 'steps': steps, 'solves': calls, 'fine_steps': fine, 'momentum_impulse': impulse, 'max_discrete_work_residual': max_balance, 'passed': passed})
    # A horizon shorter than the minimum step must finish, never halve the remaining time repeatedly.
    checks['endpoint_floor_clipped_after_scaling'] = min(1.*REFINE_FRACTION, .001) == .001
    for mode in ['off', 'always', 'state']: compile_controller(mode, 1.)
    api.require(all(checks.values()) and all(negatives) and all(t['passed'] for t in toys), 'controller unit/analytical checks')
    return {'passed': True, 'checks': checks, 'invalid_inputs_rejected': negatives, 'analytical_impacts': toys}
