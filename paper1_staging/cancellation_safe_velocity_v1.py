"""Inactive, explicitly scoped Stage42 qfree arithmetic experiment.

No engine is imported and no solve, warm, launch or authority is performed on
import.  The owner must enter the original observer and per-pose guard first.
This changes one arithmetic representation, not the contact/momentum gates.
The supplemental journal is complete even when Stage189 retains no details.
"""
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType
import ast
import copy
import hashlib
import inspect
import math
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
POLICY = 'legacy-qfree-first-original-unconstrained-momentum-1e-8-same-compliance-increment-v1'
GATE = 1e-8
SOURCE_PINS = {
    'stage42_staging/inertial_contact_robust_v1.py': '22909a9b5bdd7f86fbf13e9b7c3cb804024fe2fb919d19438ef11c0bf0e0a43b',
    'stage189_staging/contact_trial_trace_v1.py': 'dd870c67e0d6d07c8818a55db4e2cbd7f287942d653289f7407aeb8104469ea4',
    'stage243_staging/per_pose_guard_v1.py': '8a083685b2f1f28ff37fa08f75919603c0d0c22d540d32d0196cc7d2af0d5d6f',
    'stage41_staging/inertial_contact_cold_optimized_v1.py': '5214b949b2d2427591e1876a6af4c1ed76273209498b8e60c25c5947934cb8cd',
    'stage37_staging/transport_contact.py': '6bf53d779b7517b86c825c0a9eecbfccded7f497898d09f070dde3a046424e9a',
}
_active = False


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return copy.deepcopy(value)


def source_pins():
    result = {}
    for relative, expected in SOURCE_PINS.items():
        path = ROOT / relative
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        need(observed == expected, 'Original source changed: ' + relative)
        result[str(path)] = observed
    result[str(SELF)] = hashlib.sha256(SELF.read_bytes()).hexdigest()
    return result


def _function_tree(relative, name):
    source = (ROOT / relative).read_text(encoding='utf-8')
    tree = ast.parse(source)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    need(len(functions) == 1, 'Unique pinned function required: ' + name)
    return ast.Module(body=[copy.deepcopy(functions[0])], type_ignores=[])


def _code_shape(code):
    return (code.co_code, tuple(_code_shape(c) if inspect.iscode(c) else c for c in code.co_consts),
            code.co_names, code.co_varnames, code.co_freevars, code.co_cellvars,
            code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount, code.co_flags)


def _nested_code(relative, outer, inner):
    tree = _function_tree(relative, outer)
    tree.body[0].decorator_list = []
    namespace = {}
    exec(compile(tree, str(ROOT / relative), 'exec'), namespace)
    candidates = [c for c in namespace[outer].__code__.co_consts
                  if inspect.iscode(c) and c.co_name == inner]
    need(len(candidates) == 1, 'Unique original observer code required')
    return candidates[0]


def _observed_tree():
    tree = _function_tree('stage42_staging/inertial_contact_robust_v1.py', 'inertial_contact_step')
    count = 0

    class Observe(ast.NodeTransformer):
        def visit_Call(self, node):
            nonlocal count
            if (isinstance(node.func, ast.Attribute) and node.func.attr == '_solve_prepared'
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'stage41'):
                count += 1
                return ast.copy_location(ast.Call(func=ast.Name(id='_observe_inner', ctx=ast.Load()),
                    args=[node.func, ast.Name(id='iteration', ctx=ast.Load()), *node.args],
                    keywords=node.keywords), node)
            return self.generic_visit(node)

    Observe().visit(tree)
    need(count == 1, 'Exactly one original inner call')
    return ast.fix_missing_locations(tree)


def choose_velocity(legacy, old, background, body, drag, lubrication, mass, dt, compliance):
    """Producer policy; legacy has already been evaluated in original order.

    Return the identical legacy object when inactive.  There is no second
    inverse/solve and no residual tolerance or denominator change.
    """
    values = [legacy, old, background, body, drag, lubrication, mass, compliance]
    need(all(np.isfinite(np.asarray(v, float)).all() for v in values)
         and math.isfinite(float(dt)) and dt > 0, 'Nonfinite qfree policy input')
    acceleration_load = mass @ (legacy - old) / dt
    slip_drag = drag @ (legacy - background)
    lubrication_load = lubrication @ legacy
    reaction_load = np.zeros(6)
    residual = acceleration_load + slip_drag + lubrication_load - body - reaction_load
    denominator = max(np.linalg.norm(acceleration_load), np.linalg.norm(slip_drag),
                      np.linalg.norm(lubrication_load), np.linalg.norm(body),
                      np.linalg.norm(reaction_load), np.linalg.norm(drag @ background), 1e-30)
    ratio = float(np.linalg.norm(residual) / denominator)
    need(math.isfinite(ratio) and math.isfinite(float(denominator)), 'Nonfinite legacy momentum guard')
    if ratio <= GATE:
        selected, mode = legacy, 'legacy_exact'
    else:
        selected = old + compliance @ (drag @ (background - old) + body - lubrication @ old)
        mode = 'same_compliance_increment'
    need(np.isfinite(selected).all(), 'Nonfinite selected qfree')
    return selected, dict(mode=mode, legacy_unconstrained_momentum_residual=ratio,
                         legacy_momentum_reference_load=float(denominator),
                         legacy_unconstrained_residual_norm=float(np.linalg.norm(residual)))


def _clone(current, observer, chooser, enabled):
    tree = _observed_tree()
    namespace = {**current.__globals__, '_observe_inner': observer}
    expected = {}
    exec(compile(tree, str(SELF) + '::expected_original', 'exec'), namespace, expected)
    need(_code_shape(current.__code__) == _code_shape(expected[current.__name__].__code__),
         'Current outer code must be the literal original observed Stage42')
    need(current.__defaults__ == expected[current.__name__].__defaults__ and current.__closure__ is None,
         'Original defaults/closure required')
    original_ast = ast.dump(tree, include_attributes=False)
    count = 0
    if enabled:
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'free_velocity'):
                count += 1
                old_expression = node.value
                node.value = ast.Call(func=ast.Name(id='_cancellation_choose', ctx=ast.Load()),
                    args=[old_expression, *[ast.Name(id=n, ctx=ast.Load()) for n in
                        ('old_velocity', 'background', 'body_load', 'drag', 'lubrication',
                         'mass', 'dt', 'compliance', 'iteration')]], keywords=[])
        need(count == 1, 'Exactly one original qfree assignment')
        undo = copy.deepcopy(tree)
        assignment = next(n for n in ast.walk(undo) if isinstance(n, ast.Assign)
                          and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                          and n.targets[0].id == 'free_velocity')
        assignment.value = assignment.value.args[0]
        need(ast.dump(undo, include_attributes=False) == original_ast, 'Only qfree wrapper may change')
        namespace['_cancellation_choose'] = chooser
        ast.fix_missing_locations(tree)
        result = {}
        exec(compile(tree, str(SELF) + '::same_compliance_qfree', 'exec'), namespace, result)
        function = result[current.__name__]
    else:
        function = FunctionType(current.__code__, namespace, current.__name__,
                                current.__defaults__, current.__closure__)
        need(function.__code__ is current.__code__, 'Inactive numerical bytecode must be identical')
    return function, dict(original_observed_ast_sha256=hashlib.sha256(original_ast.encode()).hexdigest(),
                          candidate_ast_sha256=hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest(),
                          qfree_expression_wrappers=count, other_numerical_ast_edits=0,
                          inactive_code_object_identical=not enabled)


@contextmanager
def scope(backend, trace, enabled=False, *, before_inner=None, after_inner=None):
    """Wrap current guarded Stage42; callbacks run before/after EVERY inner map.

    before_inner(item) runs before the original guarded observer is called and
    may reject the dispatch. after_inner(item) runs in finally. Nested hot-kernel
    invocations need a separate owner budget hook: one observed map is not a
    promise of only one native primitive. The journal records attempted versus
    actually entered observer calls, including budget and solver failures.
    """
    global _active
    need(type(enabled) is bool and not _active, 'Explicit nonnested arithmetic scope required')
    pins = source_pins()
    current = backend.inertial_contact_step
    observed = current.__globals__.get('_observe_inner')
    need(callable(observed) and isinstance(trace, dict) and 'cycle_guard_trials' in trace
         and 'trial_inner_counts' in trace, 'Original observer + fresh per-pose guard required first')
    need(_code_shape(observed.__code__) == _code_shape(_nested_code(
        'stage243_staging/per_pose_guard_v1.py', 'scope', 'wrapped')), 'Pinned per-pose guard callback required')
    closure = dict(zip(observed.__code__.co_freevars, [cell.cell_contents for cell in observed.__closure__]))
    underlying = closure.get('observer')
    need(callable(underlying) and _code_shape(underlying.__code__) == _code_shape(_nested_code(
        'stage189_staging/contact_trial_trace_v1.py', 'scope', 'observe_inner')),
        'Pinned original inner observer required under per-pose guard')
    journal = dict(schema='paper1-same-compliance-qfree-probe-v1', policy=POLICY, enabled=enabled,
                   source_files=pins, outer_calls=[], scope_restored=False,
                   target_transport_steps=0, native_qualification_claim=False)
    trial = None
    selections = {}

    def chooser(legacy, old, bg, body, drag, lubrication, mass, dt, compliance, index):
        need(trial is not None and index not in selections, 'One qfree choice per original map')
        answer, metadata = choose_velocity(legacy, old, bg, body, drag, lubrication, mass, dt, compliance)
        selections[index] = dict(**metadata, legacy_qfree=plain(legacy), selected_qfree=plain(answer))
        return answer

    def capture(solver, index, v, M, J, g, dt, mu, tol, maxiter):
        need(trial is not None and index == len(trial['inner_systems']), 'Sequential complete inner journal')
        frame = sys._getframe(1)
        need(frame.f_code is patched.__code__, 'Capture must originate in the verified original outer code')
        local = frame.f_locals
        item = dict(outer_index=trial['outer_index'], inner_index=int(index), vfree=plain(v),
                    mobility=plain(M), jacobian=plain(J), gaps_m=plain(g), dt_s=float(dt),
                    friction=float(mu), tolerance=float(tol), maxiter=int(maxiter),
                    outer_locals={key: plain(local[key]) for key in (
                        'old_velocity', 'background', 'body_load', 'stokes', 'lubrication',
                        'mass', 'candidate', 'drag', 'system', 'compliance', 'reynolds', 'multiplier')},
                    selection=plain(selections.get(index)), observer_entered=False, returned=False)
        trial['inner_systems'].append(item)
        try:
            if before_inner is not None:
                before_inner(item)
            item['observer_entered'] = True
            answer = observed(solver, index, v, M, J, g, dt, mu, tol, maxiter)
            item.update(returned=True, accepted=True, velocity=plain(answer[0]), health=plain(answer[1]))
            return answer
        except BaseException as error:
            item['error'] = repr(error)
            raise
        finally:
            observer_cells = dict(zip(underlying.__code__.co_freevars,
                                      [cell.cell_contents for cell in underlying.__closure__]))
            original_trial = observer_cells.get('current')
            if item['observer_entered'] and original_trial is not None:
                originals = original_trial['inner_systems']
                need(len(originals) == index + 1, 'One original observed inner record per entered map')
                original_item = originals[index]
                need(np.array_equal(original_item['vfree'], item['vfree'])
                     and original_item['inner_index'] == index, 'Original observer actual-map association')
                item['original_observer_item'] = plain(original_item)
                item['early_range'] = plain(original_item['early_range'])
                item['fallback_range'] = plain(original_item['fallback_range'])
            if after_inner is not None:
                after_inner(item)

    patched, proof = _clone(current, capture, chooser, enabled)
    journal['source_proof'] = proof

    def outer(*args, **kwargs):
        nonlocal trial, selections
        need(trial is None and len(args) == 14 and not kwargs, 'Qualified original 14-positional outer interface required')
        selections = {}
        trial = dict(outer_index=len(journal['outer_calls']), original_trial_index=len(trace['trial_inner_counts']),
                     outer_inputs=plain(args), inner_systems=[], returned=False)
        journal['outer_calls'].append(trial)
        try:
            answer = patched(*args)
            trial.update(returned=True, velocity=plain(answer[0]), health=plain(answer[1]))
            return answer
        except BaseException as error:
            trial['error'] = repr(error)
            raise
        finally:
            trial['selection_count'] = len(selections)
            trial = None
            selections = {}

    _active = True
    backend.inertial_contact_step = outer
    try:
        yield journal
    finally:
        exact = backend.inertial_contact_step is outer
        backend.inertial_contact_step = current
        journal['scope_restored'] = exact
        _active = False
        need(exact, 'Arithmetic scope binding changed; original binding restored but evidence negative')


def _audit_momentum(q, old, mass, drag, lubrication, background, body, J, reaction, dt):
    # Independent literal Stage42 final expression, intentionally not producer helper.
    acceleration_load = mass @ (q - old) / dt
    slip_drag = drag @ (q - background)
    lubrication_load = lubrication @ q
    reaction_load = J.T @ reaction if len(reaction) else np.zeros(6)
    residual = acceleration_load + slip_drag + lubrication_load - body - reaction_load
    denominator = max(np.linalg.norm(acceleration_load), np.linalg.norm(slip_drag),
                      np.linalg.norm(lubrication_load), np.linalg.norm(body),
                      np.linalg.norm(reaction_load), np.linalg.norm(drag @ background), 1e-30)
    ratio = float(np.linalg.norm(residual) / denominator)
    need(math.isfinite(ratio) and math.isfinite(float(denominator)), 'Finite independent momentum operands')
    return ratio, float(denominator)


def audit_journal(journal, *, reynolds_number, inertial_multiplier, physical_audit, original_trace=None):
    """Independent saved arithmetic/physical audit; no solver or force call.

    Callbacks must be owner-authenticated original finite-Re functions and the
    unchanged independent contact-physics auditor, not a producer pass flag.
    A failed original call stays failed; passed=True authenticates its negative
    evidence, it does not admit the failed solution. Budget-interrupted or
    incomplete fixed-point calls are not accepted by this full-call auditor.
    """
    need(journal['schema'] == 'paper1-same-compliance-qfree-probe-v1' and journal['policy'] == POLICY
         and type(journal['enabled']) is bool and journal['scope_restored'], 'Complete restored journal required')
    need(journal['source_files'] == source_pins(), 'Exact current source associations')
    need(all(callable(f) for f in (reynolds_number, inertial_multiplier, physical_audit)),
         'Independent original arithmetic/physics callbacks required')
    activated = inner_count = successes = negatives = 0
    residuals = []; outer_results = []
    for outer_index, trial in enumerate(journal['outer_calls']):
        need(trial['outer_index'] == outer_index and len(trial['outer_inputs']) == 14, 'Exact original outer inputs/order')
        args = trial['outer_inputs']
        old, bg, body, stokes, lub, mass = [np.asarray(a, float) for a in args[:6]]
        contacts, ell, dt, mu, rho, viscosity, diameter, sphericity = args[6:14]
        need(all(np.isfinite(v).all() for v in (old, bg, body, stokes, lub, mass))
             and math.isfinite(dt) and dt > 0 and ell > 0, 'Finite physical saved input')
        # Independent exact original geometry construction; no force solve.
        rows, gaps, frames = [], [], []
        for _, gap, normal, lever in contacts:
            n = np.asarray(normal, float); n = n / np.linalg.norm(n)
            axis = np.eye(3)[np.argmin(abs(n))]
            tangent = np.cross(n, axis); tangent = tangent / np.linalg.norm(tangent)
            frame = np.vstack([n, tangent, np.cross(n, tangent)])
            rows.extend(np.c_[frame, np.cross(lever, frame) / ell]); gaps.append(gap); frames.append(frame)
        J = np.asarray(rows, float).reshape((-1, 6)); g = np.asarray(gaps, float)
        candidate = old.copy()
        scale = max(np.linalg.norm(old), np.linalg.norm(bg), 1e-30)
        systems = trial['inner_systems']
        need(0 < len(systems) <= 80, 'Original complete bounded fixed-point history')
        converged = False
        for index, item in enumerate(systems):
            need(item['inner_index'] == index and item['outer_index'] == outer_index
                 and item['observer_entered'] and item['returned'], 'Every native map has complete observed return')
            Re = reynolds_number(candidate[:3] - bg[:3], rho, viscosity, diameter)
            multiplier = inertial_multiplier(Re, sphericity)
            drag = stokes.copy(); drag[:3, :3] *= multiplier
            system = mass / dt + drag + lub
            compliance = np.linalg.inv(system)
            legacy = compliance @ (mass @ old / dt + drag @ bg + body)
            # Reconstruct original unconstrained guard independently of choose_velocity.
            legacy_ratio, legacy_den = _audit_momentum(legacy, old, mass, drag, lub, bg, body, J, np.zeros(0), dt)
            active = journal['enabled'] and legacy_ratio > 1e-8
            expected = old + compliance @ (drag @ (bg - old) + body - lub @ old) if active else legacy
            mode = 'same_compliance_increment' if active else 'legacy_exact'
            saved = item['outer_locals']
            pairs = [(saved['old_velocity'], old), (saved['background'], bg), (saved['body_load'], body),
                     (saved['stokes'], stokes), (saved['lubrication'], lub), (saved['mass'], mass),
                     (saved['candidate'], candidate), (saved['drag'], drag), (saved['system'], system),
                     (saved['compliance'], compliance), (item['mobility'], compliance),
                     (item['vfree'], expected), (np.asarray(item['jacobian'], float).reshape((-1, 6)), J),
                     (item['gaps_m'], g)]
            need(all(np.array_equal(np.asarray(a), b) for a, b in pairs), 'Independent exact recurrence/geometry/actual input association')
            need(saved['reynolds'] == Re and saved['multiplier'] == multiplier
                 and item['dt_s'] == dt and item['friction'] == mu
                 and item['tolerance'] == 1e-10 and item['maxiter'] == 25000, 'Original fixed-point/inner numerical controls')
            selection = item['selection']
            if journal['enabled']:
                need(selection['mode'] == mode and np.array_equal(selection['legacy_qfree'], legacy)
                     and np.array_equal(selection['selected_qfree'], expected)
                     and selection['legacy_unconstrained_momentum_residual'] == legacy_ratio
                     and selection['legacy_momentum_reference_load'] == legacy_den, 'Exact independently reconstructed branch choice')
            else:
                need(selection is None, 'Disabled branch has no numerical policy call')
            # This callback performs unchanged original force/Coulomb/dissipation gates.
            if len(g):
                physical_audit(item)
            else:
                need(np.array_equal(item['velocity'], item['vfree']) and not item['health']['reactions'],
                     'Original zero-contact map is exactly qfree with no reactions')
            original_item = item.get('original_observer_item')
            need(original_item is not None and original_item['accepted'] is True
                 and all(original_item[key] == item[key] for key in (
                     'inner_index', 'vfree', 'mobility', 'jacobian', 'gaps_m', 'dt_s', 'friction',
                     'tolerance', 'maxiter', 'velocity', 'health', 'early_range', 'fallback_range')),
                 'Supplemental complete system is literal original observer output')
            updated = np.asarray(item['velocity'], float)
            need(np.isfinite(updated).all(), 'Finite original map output')
            converged = np.linalg.norm(updated - candidate) / scale <= 1e-10
            need(not converged or index == len(systems) - 1, 'No extra map after original fixed-point convergence')
            candidate = updated
            activated += int(active); inner_count += 1
        need(converged, 'Original fixed-point convergence required; no forced acceptance')
        last = systems[-1]
        reaction = np.asarray(last['health']['reactions'], float)
        ratio, denominator = _audit_momentum(candidate, old, mass, drag, lub, bg, body, J, reaction, dt)
        residuals.append(ratio)
        if trial['returned']:
            need(ratio <= 1e-8 and np.array_equal(trial['velocity'], candidate), 'Original actual-contact momentum gate')
            health = trial['health']
            need(health['iterations'] == len(systems) and health['momentum_residual'] == ratio
                 and health['momentum_reference_load'] == denominator and health['contact'] == last['health'],
                 'Original returned health/last actual map association')
            world = {str(int(c[0])): (frames[k].T @ reaction[3*k:3*k+3]).tolist()
                     for k, c in enumerate(contacts)}
            bearing = [int(contacts[k][0]) for k in range(len(contacts)) if reaction[3*k] > 0]
            need(health['reynolds'] == Re and health['finite_re_multiplier'] == multiplier
                 and health['total_contact_iterations'] == sum(s['health']['iterations'] for s in systems)
                 and health['reaction_world_by_grain'] == world and health['load_bearing_grain_ids'] == bearing
                 and health['cache_policy'] == 'discard_between_all_solves'
                 and health['minimum_system_eigenvalue'] == float(np.linalg.eigvalsh((system + system.T) / 2).min())
                 and health['contact_iteration_ceiling'] == 25000, 'Every original final health operand remains literal')
            successes += 1
        else:
            need(ratio > 1e-8 and 'inertial momentum closure failed' in trial['error'],
                 'Only authentic original final-momentum negative is a complete negative result')
            negatives += 1
        outer_results.append(dict(outer_index=outer_index, original_returned=trial['returned'],
                                  final_momentum_residual=ratio, momentum_reference_load=denominator,
                                  original_final_gate_passed=ratio <= 1e-8))
        if original_trace is not None:
            k = trial['original_trial_index']
            need(original_trace['trial_inner_counts'][k] == len(systems), 'Original observer complete count matches supplemental journal')
            guard = original_trace['cycle_guard_trials'][k]
            need(guard['trial_index'] == k and len(guard['records']) == len(systems), 'Original fresh per-pose guard coverage')
            for index, record in enumerate(guard['records']):
                need(record['inner_index'] == index and np.array_equal(record['map_output'], systems[index]['velocity'])
                     and record['health'] == systems[index]['health'], 'Exact actual guarded map output/health')
    return dict(passed=True, arithmetic_evidence_authenticated=True, successful_outer_calls=successes,
                original_negative_outer_calls=negatives, complete_inner_maps=inner_count,
                increment_inner_maps=activated, final_momentum_residuals=residuals,
                outer_results=outer_results,
                original_force_and_final_momentum_gates_unchanged=True,
                original_qfree_recurrence_identity_replaced_only_when_guarded=True,
                native_qualification_claim=False, full_trajectory_admission=False)
