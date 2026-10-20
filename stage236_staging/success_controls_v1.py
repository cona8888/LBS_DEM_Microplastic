"""Labelled nonadvancing primary-success controls for the Stage236 screen.

Historical Stage88 solver inputs are not current transport fixtures. Stage90's
native comparison remains a failed attempt. Synthetic contacts use the original
rigid-body contact geometry; cap1 is a labelled diagnostic, never a production
ceiling change. Import and pure_controls do not call any force solver.
"""
from pathlib import Path
import ast, copy, hashlib, json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
OLD = ROOT/'stage88_evaluations/near_outlet_contact_profile_01'
NEGATIVE = ROOT/'stage90_evaluations/native_local_01'
INPUTS = {
    str(OLD/'cold_system_1.npz'): '1448204ce5503a44d6e09820a20f4fdb7b7c8572ad6b08c22f3da689c575ae65',
    str(OLD/'cold_system_2.npz'): 'e45062c74f008036c2670551b7d0cd10cc7c14c50c99cb066b952ff23ac0a785',
    str(OLD/'results.json'): '7b390ee8f7c6e836a87cead0d5c089f15b2d73ff4efc39a564c04e62e349d37b',
    str(OLD/'completion.json'): '599330373110e41de32019e417c6d7628ad085c074cda1c71090c0ae806da9b1',
    str(NEGATIVE/'results.json'): '77cf84f6e62ce221abde4a3f24450e05da8c2702da51da119a96c23bafac3df4',
    str(NEGATIVE/'completion.json'): 'b12a0a4d4d264814ac9cd50d1d9dda25acb3a0d522ec57516d1a6cde9aca98d5',
    str(NEGATIVE/'frozen_systems.json'): '98a883897ae3dec0eb3dddb9d5eb444a514f4179111f89251cdd5d40fc29aae2',
    str(NEGATIVE/'baseline.json'): 'acd2205b77a48bb583a64816b9e7ee87afd80dab251ab4048e9fb1140e0cca19',
}
SOURCES = {
    str(ROOT/'stage201_staging/qualify_two_contact_held_v1.py'): '7afce2519aa924bbf37796668e2d3dfd04453baebeeaef01d6750fd7fbfd8652',
    str(ROOT/'stage41_staging/inertial_contact_cold_optimized_v1.py'): '5214b949b2d2427591e1876a6af4c1ed76273209498b8e60c25c5947934cb8cd',
}
STATE = dict(started=False, attempted_inner_calls=0, completed_inner_calls=0,
             unknown_inner_calls=0, active_call=None, reports=[], passed=False)


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def definition(path, name, namespace):
    """Compile one unchanged pure original definition; never install it."""
    need(sha(path) == SOURCES[str(path)], 'Frozen pure source changed: '+str(path))
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    need(len(nodes) == 1, 'One exact original pure function: '+name)
    tree = ast.Module(body=nodes, type_ignores=[])
    exec(compile(tree, str(path)+'::unchanged_pure_control', 'exec'), namespace)
    return namespace[name]


def inputs():
    for path, expected in {**INPUTS, **SOURCES}.items():
        need(sha(path) == expected, 'Frozen control input/source changed: '+path)
    historical = json.loads((OLD/'results.json').read_text())
    need(json.loads((OLD/'completion.json').read_text())['results_sha256'] == sha(OLD/'results.json'),
         'Original historical success receipt seal')
    negative = json.loads((NEGATIVE/'results.json').read_text())
    need(json.loads((NEGATIVE/'completion.json').read_text())['results_sha256'] == sha(NEGATIVE/'results.json')
         and negative['passed'] is False, 'Preserve historical native negative')
    rows = []
    for number in (1, 2):
        path = OLD/f'cold_system_{number}.npz'
        saved = historical['top_systems'][number-1]
        need(Path(saved['path']) == path and saved['sha256'] == sha(path)
             and saved['call']['contacts'] == 2
             and saved['call']['solver'] == 'cold_pgs_seeded_scaled_lm',
             'Authentic historical two-contact seeded-LM success')
        with np.load(path, allow_pickle=False) as arrays:
            rows.append(dict(label=f'historical_stage88_{number}',
                vfree=arrays['vfree'].copy(), mobility=arrays['mobility'].copy(),
                jacobian=arrays['jacobian'].copy(), gaps_m=arrays['gaps'].copy(),
                dt_s=float(arrays['dt']), friction=float(arrays['friction']),
                tolerance=float(arrays['tol']), maxiter=int(arrays['maxiter']),
                archived_velocity=arrays['velocity'].copy(),
                archived_reactions=arrays['reactions'].copy(),
                historical_input_sha256=sha(path), current_transport_fixture=False))
    return rows


def synthetic(kernel):
    geometry = definition(ROOT/'stage41_staging/inertial_contact_cold_optimized_v1.py',
        '_prepare_geometry', {'np': np, 'contact_model': kernel.s53.s41.contact_model})
    contacts = [[1, 0.0, [0., 0., 1.], [-.5, 0., 0.]],
                [2, 0.0, [0., 0., 1.], [.5, 0., 0.]]]
    J, g, frames = geometry(contacts, 1.)
    need(J.shape == (6, 6) and g.shape == (2,) and len(frames) == 2,
         'Two physical rigid-body contact frames')
    return dict(label='synthetic_two_parallel_normals',
        vfree=np.array([0., 0., -1e-5, 0., 0., 0.]), mobility=np.eye(6),
        jacobian=J, gaps_m=g, dt_s=.01, friction=.3, tolerance=1e-10,
        maxiter=25000, synthetic=True, current_transport_fixture=False)


def pure_controls(kernel):
    rows = inputs()
    row = synthetic(kernel)
    need(all(r['vfree'].shape == (6,) and r['mobility'].shape == (6, 6)
             and r['jacobian'].shape == (6, 6) and r['gaps_m'].shape == (2,)
             and r['tolerance'] == 1e-10 and r['maxiter'] == 25000 for r in rows+[row]),
         'Unchanged original successful-input shapes and ceilings')
    need(np.all(np.linalg.eigvalsh(row['mobility']) > 0)
         and np.linalg.matrix_rank(row['jacobian']) == 5, 'Physical two-contact rigid-body rank and positive mobility')
    return dict(passed=True, direct_inner_calls=0, force_calls=0,
        historical_success_inputs=2, synthetic_physical_contact_geometry=True,
        historical_native_negative_preserved=True, maximum_planned_direct_inner_calls=14,
        current_transport_fixture=False, new_trajectory_steps=0,
        claim='Pure input construction only; no current primary success has been assumed.')


def controls(kernel, bound):
    """Run only after a new frozen screen admits these <=16 direct calls."""
    need(not STATE['started'] and callable(bound), 'One fresh admitted direct-control execution')
    authority = bound()
    need(authority['maximum_direct_inner_calls'] == 16
         and authority['maximum_trajectory_steps'] == authority['maximum_saved_transport_steps'] == 0
         and authority['production_authorized'] is False, 'Fresh bounded nonadvancing direct-control authority')
    pure = pure_controls(kernel)
    audit = definition(ROOT/'stage201_staging/qualify_two_contact_held_v1.py', 'audit', {'np': np})
    rows = inputs()
    base = synthetic(kernel)
    swapped = copy.deepcopy(base); order = [3, 4, 5, 0, 1, 2]
    swapped.update(label='synthetic_contact_order_swap', jacobian=base['jacobian'][order].copy(),
                   gaps_m=base['gaps_m'][::-1].copy())
    cap1 = copy.deepcopy(base); cap1.update(label='synthetic_cap1_LM_diagnostic', maxiter=1,
        diagnostic_cap_only=True, production_ceiling_changed=False)
    cases = [(row, kind) for row in rows for kind in ('primary', 'zero')]
    cases += [(row, 'primary') for row in (base, swapped, cap1)]
    STATE['started'] = True
    results = {}

    def invoke(row, kind, mode, function):
        bound()
        need(STATE['attempted_inner_calls'] < authority['maximum_direct_inner_calls'], 'Direct inner-call cap')
        args = [row[k].copy() for k in ('vfree', 'mobility', 'jacobian', 'gaps_m')]
        args += [row['dt_s'], row['friction'], row['tolerance'], row['maxiter']]
        before = [x.tobytes() for x in args[:4]]
        record = dict(label=row['label'], solver=kind, mode=mode,
            argument_sha256=digest(args), diagnostic_cap_only=row.get('diagnostic_cap_only', False))
        STATE['attempted_inner_calls'] += 1; STATE['unknown_inner_calls'] = 1
        STATE['active_call'] = record
        try:
            answer = function(*args)
        except Exception as error:
            record.update(passed=False, error=repr(error), solver_returned=False)
            STATE['reports'].append(record); STATE['completed_inner_calls'] += 1
            STATE['unknown_inner_calls'] = 0; STATE['active_call'] = None
            raise
        STATE['completed_inner_calls'] += 1; STATE['unknown_inner_calls'] = 0; STATE['active_call'] = None
        record.update(solver_returned=True, answer=plain(answer))
        STATE['reports'].append(record)
        need(before == [x.tobytes() for x in args[:4]], 'Original/candidate solver inputs unchanged')
        check = audit(row, answer[0], answer[1]); record['original_independent_audit'] = check
        need(check['passed'], 'Original two-contact residual/cone/closure/work gates')
        record['passed'] = True
        bound()
        return answer

    for row, kind in cases:
        with kernel.hot.scope():
            old = kernel.hot.s50._solve if kind == 'primary' else kernel.s53._solve
            original = invoke(row, kind, 'original', old)
            with kernel.scope():
                current = kernel.hot.s50._solve if kind == 'primary' else kernel.s53._solve
                candidate = invoke(row, kind, 'candidate', current)
        need(original[0].tobytes() == candidate[0].tobytes()
             and digest(original[1]) == digest(candidate[1]), 'Exact successful primary output and ALL health fields')
        results[row['label'], kind] = plain(original)
        if row['label'] == base['label']:
            need(original[1]['solver'] == 'standard_cold_pgs', 'Natural original PGS success control')
        if row['label'] == cap1['label']:
            need(original[1]['solver'] == 'cold_pgs_seeded_scaled_lm', 'Cap1 labelled successful seeded-LM diagnostic')
    identity = np.asarray(results[base['label'], 'primary'][0])
    permuted = np.asarray(results[swapped['label'], 'primary'][0])
    covariance = float(np.linalg.norm(identity-permuted)/max(np.linalg.norm(base['vfree']), 1e-15))
    need(covariance <= 1e-8, 'Original declared contact-order velocity covariance ceiling')
    bound()
    need(STATE['attempted_inner_calls'] == STATE['completed_inner_calls'] == 14
         and STATE['unknown_inner_calls'] == 0, 'Complete bounded direct success accounting')
    STATE['passed'] = True
    return dict(passed=True, inner_calls=14, attempted_inner_calls=14, completed_inner_calls=14,
        unknown_inner_calls=0, pure_controls=pure, reports=copy.deepcopy(STATE['reports']),
        original_and_candidate_successful=True, exact_velocity_and_entire_health=True,
        original_finish_acceptance_gates_unchanged=True, original_independent_physical_audits_passed=True,
        contact_order_velocity_covariance_error_over_free_speed=covariance,
        original_covariance_ceiling=1e-8, diagnostic_cap1_is_not_production_change=True,
        historical_native_negative_preserved=True, new_trajectory_steps=0,
        current_transport_fixture=False, production_authorized=False,
        claim='Direct current solver success and labelled synthetic covariance controls only; no transport or campaign qualification.')
