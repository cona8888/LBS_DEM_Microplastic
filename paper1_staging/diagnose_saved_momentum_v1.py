"""Read-only arithmetic replay of ONE already sealed momentum-closure negative.

No engine, geometry, contact solver, transport, evaluator or authority is loaded.
The saved 6x6 inverse is independently reconstructed as numerical linear algebra;
counterfactual vectors are never installed, admitted or called physical solutions.
CLI prints JSON only. It creates no files, subprocesses, records or run folders.
"""
from __future__ import annotations

import ast
import copy
from decimal import Decimal, localcontext
import hashlib
import json
import lzma
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'paper1_runs/contact_event_diagnostic_20261019_recovery02'
RAW = OUT / 'records/f0p0625_local_001/packet.json.xz'
RAW_SHA = '00d8eb70116e5a1ed8c58ff63b8241de312d9b211d78868dd019cc7dca11afc3'
FINAL_SHA = '625c9c3ae05675a3745baefb99ccefc51738bbacc41c3c84f0e2de50fbbe6797'
CLOSURE_SHA = 'e6652db2d5a1d44fc17898b93c7010330c8747a2c5b8c085ceac7d1b442a67aa'
SOURCE42 = ROOT / 'stage42_staging/inertial_contact_robust_v1.py'
SOURCES = {
    SOURCE42: '22909a9b5bdd7f86fbf13e9b7c3cb804024fe2fb919d19438ef11c0bf0e0a43b',
    ROOT / 'stage38_staging/finite_re_relaxation_v1.py':
        '10ff8bee4d6bffe0e7a8a9f84c389f20ac868e57300a1e1f56bfbe58c1e9c1e6',
    ROOT / 'stage38_staging/finite_re_relaxation_v2.py':
        '02ad159763f4883fd1296a0fc081eaa55d7a11a1ac3f525a9951dcd5fdad7a0d',
}
ADDITIONAL_SOURCES = (
    ROOT / 'stage115_staging/corrected_transport_v1.py',
    ROOT / 'stage189_staging/contact_trial_trace_v1.py',
    ROOT / 'stage242_staging/contact_consistency_v1.py',
    ROOT / 'stage79_staging/inertial_contact_within_pose_reuse_v1.py',
)


def require(ok, message):
    if not ok:
        raise ValueError('Saved momentum arithmetic: ' + message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def authenticate_seal(folder, expected):
    value = read(folder / 'results.json')
    completion = read(folder / 'completion.json')
    require(sha(folder / 'results.json') == expected == completion['results_sha256'],
            'exact result and completion association')
    require(value['passed'] == completion['passed'], 'honest positive/negative seal')
    return value


def pure_original_functions():
    """Extract ONLY original finite-Re arithmetic and literal momentum stencil."""
    namespace = {'np': np}
    for relative, names in (
        ('stage38_staging/finite_re_relaxation_v1.py',
         ('reynolds_number', 'haider_levenspiel_cd', 'sphere_cd')),
        ('stage38_staging/finite_re_relaxation_v2.py', ('inertial_multiplier',)),
    ):
        path = ROOT / relative
        require(sha(path) == SOURCES[path], 'finite-Re source pin')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        selected = [copy.deepcopy(x) for x in tree.body
                    if isinstance(x, ast.FunctionDef) and x.name in names]
        require(len(selected) == len(names), 'exact pure function selection')
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    require(sha(SOURCE42) == SOURCES[SOURCE42], 'original momentum source pin')
    text = SOURCE42.read_text(encoding='utf-8')
    tree = ast.parse(text)
    original = next(x for x in tree.body
                    if isinstance(x, ast.FunctionDef) and x.name == 'inertial_contact_step')
    selected = []
    collecting = False
    for statement in original.body:
        if isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name):
            name = statement.targets[0].id
            collecting = collecting or name == 'reaction'
            if collecting:
                selected.append(copy.deepcopy(statement))
            if name == 'momentum_residual':
                break
    require(len(selected) == 8, 'unaltered eight-statement original momentum block')
    names = ('candidate', 'old_velocity', 'background', 'body_load', 'drag',
             'lubrication', 'mass', 'jacobian', 'contact_health', 'dt')
    return_names = ('reaction_load', 'acceleration_load', 'slip_drag',
                    'lubrication_load', 'residual', 'denominator', 'momentum_residual')
    fn = ast.FunctionDef(name='source_gate', args=ast.arguments(
        posonlyargs=[], args=[ast.arg(arg=x) for x in names], kwonlyargs=[],
        kw_defaults=[], defaults=[]), body=selected + [ast.Return(value=ast.Dict(
            keys=[ast.Constant(value=x) for x in return_names],
            values=[ast.Name(id=x, ctx=ast.Load()) for x in return_names]))], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    exec(compile(module, str(SOURCE42) + '::literal_momentum_arithmetic_only', 'exec'), namespace)
    namespace['outer_source_sha256'] = hashlib.sha256(
        (ast.get_source_segment(text, original) + '\n').encode()).hexdigest()
    return namespace


def original_gate(fn, q, old, bg, body, drag, lubrication, mass, J, health, h):
    require(np.isfinite(q).all(), 'nonfinite counterfactual is never accepted')
    return fn(q, old, bg, body, drag, lubrication, mass, J, health, h)


def decimal_matvec(matrix, vector):
    return [sum((a * b for a, b in zip(row, vector)), Decimal(0)) for row in matrix]


def decimal_norm(vector):
    return sum((x * x for x in vector), Decimal(0)).sqrt()


def decimal_elimination(matrix, rhs):
    """Independent saved-matrix arithmetic; no contact or physical solver."""
    a = [list(row) + [v] for row, v in zip(matrix, rhs)]
    for column in range(len(rhs)):
        pivot = max(range(column, len(rhs)), key=lambda i: abs(a[i][column]))
        require(a[pivot][column] != 0, 'nonsingular saved arithmetic system')
        a[column], a[pivot] = a[pivot], a[column]
        divisor = a[column][column]
        a[column] = [x / divisor for x in a[column]]
        for row in range(len(rhs)):
            if row != column:
                factor = a[row][column]
                a[row] = [x - factor * y for x, y in zip(a[row], a[column])]
    return [row[-1] for row in a]


def decimal_check(old, bg, body, drag, lubrication, mass, J, health, h, candidates, precision):
    """Interpret every saved float as its EXACT binary64 value, not str(float)."""
    cv = lambda x: Decimal.from_float(float(x))
    with localcontext() as ctx:
        ctx.prec = precision
        matrices = [[[cv(x) for x in row] for row in a] for a in (mass, drag, lubrication)]
        md, dd, ld = matrices
        qo, qb, bodyd = [[cv(x) for x in v] for v in (old, bg, body)]
        reaction = [cv(x) for x in J.T @ np.asarray(health['reactions'], float)]
        hd = cv(h)
        matrix = [[md[i][j] / hd + dd[i][j] + ld[i][j] for j in range(6)] for i in range(6)]
        d_old = decimal_matvec(dd, [a - b for a, b in zip(qo, qb)])
        l_old = decimal_matvec(ld, qo)
        forcing = [f + r - d - l for f, r, d, l in zip(bodyd, reaction, d_old, l_old)]
        increment = decimal_elimination(matrix, forcing)
        center = [x + d for x, d in zip(qo, increment)]
        output = {'precision_digits': precision,
                  'rounded_continuous_saved_linear_system_q': [float(x) for x in center],
                  'exact_increment_decimal': [str(x) for x in increment], 'candidates': {}}
        for name, q in candidates.items():
            qd = [cv(x) for x in q]
            acceleration = [x / hd for x in decimal_matvec(md, [a - b for a, b in zip(qd, qo)])]
            slip = decimal_matvec(dd, [a - b for a, b in zip(qd, qb)])
            lub = decimal_matvec(ld, qd)
            residual = [a + d + l - f - r for a, d, l, f, r in zip(acceleration, slip, lub, bodyd, reaction)]
            denominator = max(decimal_norm(x) for x in (
                acceleration, slip, lub, bodyd, reaction, decimal_matvec(dd, qb)))
            output['candidates'][name] = dict(normalized_residual=str(decimal_norm(residual) / denominator),
                residual_norm=str(decimal_norm(residual)), reference_load=str(denominator),
                residual_components=[str(x) for x in residual])
        return output


def analyze_saved():
    final = authenticate_seal(OUT / 'final_disposition_01', FINAL_SHA)
    closure = authenticate_seal(OUT / 'final_execution_receipt_01', CLOSURE_SHA)
    require(not final['passed'] and closure['passed'] and closure['administrative_execution_closed'],
            'closed negative is never promoted')
    require(closure['final_disposition_sha256'] == FINAL_SHA, 'closure anchors original failure')
    consumed = {str(OUT / 'final_disposition_01/results.json'): FINAL_SHA,
                str(OUT / 'final_execution_receipt_01/results.json'): CLOSURE_SHA,
                str(RAW): RAW_SHA}
    for folder in ('final_disposition_01', 'final_execution_receipt_01'):
        p = OUT / folder / 'completion.json'
        consumed[str(p)] = sha(p)
    expected_sources = dict(SOURCES)
    for path in ADDITIONAL_SOURCES:
        expected_sources[path] = final['source_files'][str(path)]
    for path, expected in expected_sources.items():
        require(final['source_files'][str(path)] == expected == sha(path), 'sealed actual source bytes')
        consumed[str(path)] = expected
    for label in ('f0p0625_smoke_original32', 'f0p0625_smoke_compiled32'):
        path = OUT / 'records' / label / 'smoke.json.xz'
        expected = final['artifacts'][str(path)]
        require(sha(path) == expected, 'sealed original32 evidence')
        smoke = json.loads(lzma.decompress(path.read_bytes()))
        require(smoke['work_rows'] == 32 and not smoke['record']['contact_trial_trace']['detailed_trials'],
                'no fabricated missing healthy outer matrices for old32')
        consumed[str(path)] = expected
    require(final['artifacts'][str(RAW)] == RAW_SHA == sha(RAW), 'exact negative raw hash')
    wire = json.loads(lzma.decompress(RAW.read_bytes()))
    require(wire['schema'] == 'paper1.lossless-stepdoubling-packet-prefix.v1', 'saved envelope schema')
    packet = wire['packet']
    failed = packet['work_branches'][1642]
    require(failed['branch_id'] == 'm000000547_t000000000_F1' and failed['work_rows'] == 1,
            'exact failed branch, no record substitution')
    trace = failed['contact_trial_trace']
    trial = trace['detailed_trials'][0]
    require(trial['accepted'] is False and trial['error'] == "RuntimeError('inertial momentum closure failed')",
            'the observed failure is the original momentum gate')
    require(len(trial['inner_systems']) == 2 and trace['trial_inner_counts'] == [2], 'complete saved two-inner trace')
    pure = pure_original_functions()
    require(pure['outer_source_sha256'] == trace['structural_identity']['original_source_sha256'],
            'observed original outer source identity')
    o = trial['outer_inputs']
    old, bg, body, stokes, lubrication, mass = [np.asarray(v, float) for v in o[:6]]
    require(all(np.isfinite(v).all() for v in (old, bg, body, stokes, lubrication, mass)),
            'finite literal saved mechanical operands')
    J = np.asarray(trial['inner_systems'][0]['jacobian'], float)
    gaps = trial['inner_systems'][0]['gaps_m']
    require(len(gaps) == 1 and o[6][0][0] == 15, 'one original grain15 system')
    details, final_operands = [], None
    for index in (1641, 1642):
        branch = packet['work_branches'][index]
        require(all(branch['before_state'][k] == failed['before_state'][k] for k in ('x', 'p', 'q', 't')),
                'neighbor C shares identical physical origin')
        h = branch['cap_entries'][0]['actual_trial_dt_s']
        current = old.copy()
        for observed in branch['contact_trial_trace']['cycle_guard_trials'][0]['records']:
            reynolds = pure['reynolds_number'](current[:3] - bg[:3], *o[10:13])
            multiplier = pure['inertial_multiplier'](reynolds, o[13])
            drag = stokes.copy()
            drag[:3, :3] *= multiplier
            matrix = mass / h + drag + lubrication
            mobility = np.linalg.inv(matrix)  # arithmetic on retained six-dimensional operands only
            legacy = mobility @ (mass @ old / h + drag @ bg + body)
            arguments = [legacy.tolist(), mobility.tolist(), J.tolist(), gaps, h, o[9], 1e-10, 25000]
            input_digest = hashlib.sha256(json.dumps(arguments, sort_keys=True, allow_nan=True).encode()).hexdigest()
            require(input_digest == observed['input_sha256'], 'EXACT observed original inner system digest')
            require(np.array_equal(legacy, np.asarray(observed['map_output'], float)), 'literal saved zero-reaction q map')
            health = observed['health']
            require(all(v == 0 for v in health['reactions']), 'no invented nonzero reaction')
            increment = old + mobility @ (drag @ (bg - old) + body - lubrication @ old)
            saved_gate = original_gate(pure['source_gate'], legacy, old, bg, body, drag, lubrication, mass, J, health, h)
            increment_gate = original_gate(pure['source_gate'], increment, old, bg, body, drag, lubrication, mass, J, health, h)
            sold = max(*(np.linalg.norm(v) for v in (drag @ (old - bg), lubrication @ old, body, drag @ bg)), 1e-30)
            details.append(dict(branch_index=index, branch_id=branch['branch_id'], inner_index=observed['inner_index'],
                dt_s=h, reynolds=reynolds, multiplier=multiplier, exact_inner_input_sha256=input_digest,
                legacy_gate=saved_gate['momentum_residual'], increment_same_inverse_gate=increment_gate['momentum_residual'],
                exact_free_closure_guard_would_activate=bool(saved_gate['momentum_residual'] > 1e-8),
                eta_frobenius_telemetry_only=float(np.finfo(float).eps * np.linalg.norm(mass / h, 'fro') * np.linalg.norm(old) / sold),
                increment_q=increment.tolist(), increment_minus_saved_ulp=((increment - legacy) / abs(np.spacing(legacy))).tolist(),
                zero_reaction_normal_slack_m_s=float(J[0] @ increment + gaps[0] / h)))
            if index == 1642:
                item = trial['inner_systems'][observed['inner_index']]
                require(np.array_equal(mobility, np.asarray(item['mobility'])) and np.array_equal(legacy, np.asarray(item['vfree'])),
                        'bit-exact retained inverse and original free velocity')
                final_operands = (h, drag, health, legacy, increment, saved_gate, increment_gate)
            current = np.asarray(observed['map_output'], float)
    h, drag, health, legacy, increment, saved_gate, increment_gate = final_operands
    require(saved_gate['momentum_residual'] > 1e-8 and increment_gate['momentum_residual'] <= 1e-8,
            'actual source gate negative, representable counterfactual positive for THIS saved system')
    decimal_results = [decimal_check(old, bg, body, drag, lubrication, mass, J, health, h,
        {'saved_q': legacy, 'same_inverse_increment_q': increment}, p) for p in (80, 100)]
    require(all(np.array_equal(np.asarray(x['rounded_continuous_saved_linear_system_q']), increment)
                for x in decimal_results), '80/100-digit independent arithmetic rounds to same literal float64 q')
    return dict(schema='paper1.saved-momentum-arithmetic-diagnosis.v1', passed=True,
        scope='posthoc saved arithmetic only; NOT physical/restart/native/local/full-path qualification',
        consumed_files=consumed, helper_sha256=sha(Path(__file__)), original_gate_threshold=1e-8,
        packet_original_json_digest_retained_not_reconstructed=wire['original_uncompressed_sha256'],
        full_history_replayed=False, per_inner=details,
        original_failure=dict(normalized_residual=saved_gate['momentum_residual'],
            residual_norm=float(np.linalg.norm(saved_gate['residual'])), reference_load=float(saved_gate['denominator']),
            residual_components=saved_gate['residual'].tolist(), acceleration_load=saved_gate['acceleration_load'].tolist(),
            drag_load=saved_gate['slip_drag'].tolist(), lubrication_load=saved_gate['lubrication_load'].tolist(),
            body_load=body.tolist(), reaction_load=saved_gate['reaction_load'].tolist()),
        cancellation=dict(mass_old_over_dt_norm=float(np.linalg.norm(mass @ old / h)),
            net_increment_forcing_norm=float(np.linalg.norm(drag @ (bg - old) + body - lubrication @ old)),
            qold_over_increment_norm=float(np.linalg.norm(old) / np.linalg.norm(increment - old))),
        independent_decimal_exact_binary_operands=decimal_results,
        representable_passing_q_exists_for_this_saved_system=True,
        counterfactual_not_a_new_nonlinear_fixed_point_or_contact_iteration=True,
        no_general_float_lattice_or_full_trajectory_guarantee=True,
        early_32_smoke_outer_matrices_not_retained=True,
        zero_new_force_calls=True, zero_new_transport_steps=True, zero_new_native_calls=True,
        zero_new_integration_records=True, no_failed_record_admitted=True, qualified_core_cases_unchanged=1)


def controls():
    pure = pure_original_functions()
    z = np.zeros(6)
    identity = np.eye(6)
    health = dict(reactions=[])
    gate = original_gate(pure['source_gate'], np.ones(6), z, z, np.ones(6),
        np.zeros((6, 6)), np.zeros((6, 6)), identity, np.zeros((0, 6)), health, 1.)
    require(gate['momentum_residual'] == 0., 'exact balanced synthetic source stencil')
    try:
        original_gate(pure['source_gate'], np.full(6, np.nan), z, z, z,
            identity, identity, identity, np.zeros((0, 6)), health, 1.)
    except ValueError:
        pass
    else:
        raise AssertionError('nonfinite fail-closed control')
    with localcontext() as ctx:
        ctx.prec = 60
        answer = decimal_elimination([[Decimal(2), Decimal(1)], [Decimal(1), Decimal(3)]],
                                     [Decimal(5), Decimal(5)])
        require(answer == [Decimal(2), Decimal(1)], 'independent saved-linear-arithmetic control')
    return dict(passed=True, pure_controls=3, original_momentum_block_ast_extracted=True,
                engine_imports=0, force_calls=0, transport_steps=0)


if __name__ == '__main__':
    print(json.dumps(dict(controls=controls(), analysis=analyze_saved()), sort_keys=True, allow_nan=False))
