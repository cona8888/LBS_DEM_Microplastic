"""Scoped LM callback acceleration; original search and force gates unchanged.

Only the nested equations functions in original Stage53 and Stage136.PRIMARY
are replaced. NumPy prepares u/scales and z+A@force exactly as before. The
two-coordinate projection/residual bookkeeping is compiled without fastmath.
Stage136's Python math.hypot is deliberately retained: native hypot is not
bit-identical to Python3.12 hypot. No pose, force or failure result is cached.
"""
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FunctionType
import ast, copy, hashlib, inspect, json, math, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage136_staging'), str(ROOT/'stage63_staging'),
               str(ROOT/'stage53_staging'), str(ROOT/'stage158_staging')]
import compiled_scalar_v1 as hot
import inertial_contact_multistart_lm_v1 as s53
import roundoff_closure_v1 as fix
np, njit, DDOT = hot.np, hot.njit, hot.DDOT
ORIGINAL_PRIMARY, ORIGINAL_ZERO = hot.PRIMARY, s53._solve
ORIGINAL_PROJECT = hot.s50._project
ORIGINAL_FINISH = ORIGINAL_PRIMARY.__globals__['_finish']
need_fix_hot_identity = fix.hot is hot
SOURCE_PINS = {
    str(ROOT/'stage53_staging/inertial_contact_multistart_lm_v1.py'): '1fc6d19163bd98d9721b6ca701ef226260aadc972e60b8f6576629375e717796',
    str(ROOT/'stage136_staging/compiled_scalar_v1.py'): '6388db9276033a80629940dc1d6d72de3f70f64e2a6c08883e71cc24d02edde8',
    str(ROOT/'stage50_staging/inertial_contact_seeded_lm_v1.py'): '38c8118c40900aaf74429f347db5f5284ddd32f5c8153c69caa4a1bda963725f',
    str(ROOT/'stage74_staging/scalar_contact_kernels_v1.py'): '351595c3b57094b550f9611ddb23cb8acb76d2233825ce8f5ff9c33ef5e46cd3',
    str(ROOT/'bottleneck_resolution_20260912/src/compiled_blas_loop.py'): 'b6285c9a4eafd9cb1fd57e506f0b2ebdecf28f3793300ccd7c9cec1db7464826',
    str(ROOT/'stage158_staging/roundoff_closure_v1.py'): '76fffcbeF7b7a97a8cc2a67fed620957152ee18fbe3f07c6c22300955029c533'.lower(),
}
COUNTS = dict(scopes=0, primary_callbacks=0, zero_callbacks=0,
              compiled_callbacks=0, two_contact_guard_hits=0, original_domain_callbacks=0,
              primary_two_contact_calls=0, zero_two_contact_calls=0, original_arity_calls=0)
_ACTIVE = False
_TEMPLATES = None
_SOURCE_VALIDATED = False
_ORIGINS = tuple((fn, fn.__code__, fn.__defaults__, fn.__closure__,
                  tuple((key, fn.__globals__[key]) for key in
                        set(fn.__code__.co_names) | {'_project', '_residual'}
                        if key in fn.__globals__ and key != '_finish'))
                 for fn in (ORIGINAL_PRIMARY, ORIGINAL_ZERO))
_CALLABLE_CODES = tuple((fn, fn.__code__) for fn in
                       (hot.phase, hot.scalar.project, ORIGINAL_PROJECT,
                        ORIGINAL_FINISH, fix.finish, ORIGINAL_PRIMARY.__globals__['root'],
                        ORIGINAL_ZERO.__globals__['root']))


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _cell(value):
    return (lambda: value).__closure__[0]


def original_equations(kind, scales, z, A, gaps, dt, friction, steps, scale):
    """Exact original callback code/globals with fresh operand closure cells."""
    source = ORIGINAL_PRIMARY if kind == 'primary' else ORIGINAL_ZERO
    code = next(v for v in source.__code__.co_consts if isinstance(v, CodeType) and v.co_name == 'equations')
    values = dict(scales=scales, z=z, A=A, gaps=gaps, dt=dt, friction=friction, steps=steps, scale=scale)
    need(set(code.co_freevars) == set(values), 'Original callback closure schema')
    return FunctionType(code, source.__globals__, 'equations', None,
                        tuple(_cell(values[k]) for k in code.co_freevars))


@njit(cache=False, fastmath=False, parallel=False, error_model='numpy')
def residual_kernel(u, force, velocity, gaps, dt, friction, steps, scale, norms, scalar_norm):
    result = np.empty_like(u)
    trial = np.empty(2)
    for k in range(len(gaps)):
        i = 3*k
        vn = velocity[i]+gaps[k]/dt
        result[i] = np.hypot(u[i], vn)-u[i]-vn
        trial[0] = force[i+1]-velocity[i+1]/steps[k]
        trial[1] = force[i+2]-velocity[i+2]/steps[k]
        norm = norms[k] if scalar_norm else np.sqrt(DDOT(2, trial.ctypes, 1, trial.ctypes, 1))
        factor = min(1., friction*force[i]/max(norm, 1e-300))
        result[i+1] = u[i+1]-steps[k]*(trial[0]*factor)
        result[i+2] = u[i+2]-steps[k]*(trial[1]*factor)
    return result/scale


def callback(u, scales, z, A, gaps, dt, friction, steps, scale, kind):
    COUNTS[kind+'_callbacks'] += 1
    # Keep original NumPy array division/addition and BLAS expression/order.
    force = u/scales
    velocity = z+A@force
    if (len(gaps) != 2 or u.dtype != np.dtype('float64') or u.ndim != 1 or not u.flags.c_contiguous
            or not np.isfinite(force).all() or not np.isfinite(velocity).all()):
        COUNTS['original_domain_callbacks'] += 1
        return original_equations(kind, scales, z, A, gaps, dt, friction, steps, scale)(u)
    scalar_norm = kind == 'primary'
    norms = np.empty(len(gaps))
    if scalar_norm:
        for k in range(len(gaps)):
            i = 3*k
            x = float(force[i+1]-velocity[i+1]/steps[k])
            y = float(force[i+2]-velocity[i+2]/steps[k])
            norms[k] = math.hypot(x, y)
    COUNTS['compiled_callbacks'] += 1
    COUNTS['two_contact_guard_hits'] += 1
    return residual_kernel(u, force, velocity, gaps, dt, friction, steps, scale, norms, scalar_norm)


def _build(source, text, kind):
    original = ast.parse(text)
    tree = copy.deepcopy(original)
    function = tree.body[0]
    found = [n for n in function.body if isinstance(n, ast.FunctionDef) and n.name == 'equations']
    need(len(found) == 1 and len(found[0].args.args) == 1
         and found[0].args.args[0].arg == 'u', 'One original nested equations callback')
    expected = ('f' if kind == 'primary' else 'force')
    first = ast.parse(f'{expected}=u/scales; velocity=z+A@{expected}; result=np.empty_like(u)').body
    need(ast.dump(ast.Module(body=found[0].body[:3], type_ignores=[]), include_attributes=False)
         == ast.dump(ast.Module(body=first, type_ignores=[]), include_attributes=False),
         'Original NumPy division and BLAS preparation AST')
    old_body = copy.deepcopy(found[0].body)
    found[0].body = ast.parse(
        f"return _stage236_callback(u,scales,z,A,gaps,dt,friction,steps,scale,{kind!r})").body
    reconstructed = copy.deepcopy(tree)
    nested = next(n for n in reconstructed.body[0].body if isinstance(n, ast.FunctionDef) and n.name == 'equations')
    nested.body = old_body
    need(ast.dump(reconstructed, include_attributes=False) == ast.dump(original, include_attributes=False),
         'No outer solver/root seed/options/caps/gate AST changes')
    ast.fix_missing_locations(tree)
    namespace = {**source.__globals__, '_stage236_callback': callback}
    exec(compile(tree, source.__code__.co_filename+'::stage236_lm_callback_only', 'exec'), namespace)
    result = namespace[source.__name__]
    proof = dict(kind=kind, original_ast_sha256=hashlib.sha256(ast.dump(original, include_attributes=False).encode()).hexdigest(),
        transformed_ast_sha256=hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest(),
        only_nested_equations_body_replaced=True, original_outer_ast_reconstructed_exactly=True,
        numpy_force_division_and_blas_preparation_preserved=True, original_root_seeds_options_caps_and_finish_unchanged=True)
    return result, proof


def _origins():
    """Cheap live identity checks; immutable source bytes are checked per phase."""
    need(hot.PRIMARY is ORIGINAL_PRIMARY and s53._solve is ORIGINAL_ZERO
         and hot.s50._project is ORIGINAL_PROJECT, 'Frozen original solver/projection origins')
    for fn, code, defaults, closure, namespace in _ORIGINS:
        need(fn.__code__ is code and fn.__defaults__ is defaults and fn.__closure__ is closure
             and all(fn.__globals__.get(key) is value for key, value in namespace),
             'Exact original solver code, defaults, closure and global bindings')
    need(need_fix_hot_identity and fix.hot is hot
         and all(fn.__code__ is code for fn, code in _CALLABLE_CODES),
         'Exact original phase/project/root/finish callable code identities')
    current_finish = ORIGINAL_PRIMARY.__globals__['_finish']
    need((current_finish is ORIGINAL_FINISH or current_finish is fix.finish)
         and hot.s50._finish is current_finish,
         'Only exact original finish or pinned original roundoff adapter permitted')
    need(ORIGINAL_PRIMARY.__globals__['_project'] is hot.scalar.project,
         'Exact original seeded-LM scalar projection')


def validate_sources():
    """Authenticate source bytes before a phase, never inside a timed scope."""
    global _SOURCE_VALIDATED
    need(not _ACTIVE, 'Source authentication outside active candidate scope')
    _origins()
    for path, expected in SOURCE_PINS.items():
        need(expected and sha(path) == expected, 'Unchanged original callback source: '+path)
    _SOURCE_VALIDATED = True
    return dict(passed=True, source_files=dict(SOURCE_PINS))


def build():
    global _TEMPLATES
    _origins()
    if _TEMPLATES is None:
        need(_SOURCE_VALIDATED, 'Explicit phase source authentication before template construction')
        primary, primary_proof = _build(ORIGINAL_PRIMARY, hot.PRIMARY_SOURCE, 'primary')
        zero, zero_proof = _build(ORIGINAL_ZERO, inspect.getsource(ORIGINAL_ZERO), 'zero')
        # Persistent state contains immutable executable/proof metadata only.
        # Every scope gets new functions and current original global bindings.
        _TEMPLATES = (primary.__code__, zero.__code__,
                      json_proof_bytes([primary_proof, zero_proof]))
    primary = FunctionType(_TEMPLATES[0], {**ORIGINAL_PRIMARY.__globals__, '_stage236_callback':callback},
                           ORIGINAL_PRIMARY.__name__, ORIGINAL_PRIMARY.__defaults__, ORIGINAL_PRIMARY.__closure__)
    zero = FunctionType(_TEMPLATES[1], {**ORIGINAL_ZERO.__globals__, '_stage236_callback':callback},
                        ORIGINAL_ZERO.__name__, ORIGINAL_ZERO.__defaults__, ORIGINAL_ZERO.__closure__)
    need(primary.__globals__['_project'] is hot.scalar.project
         and zero.__globals__['s50'] is hot.s50, 'Original distinct projection implementations retained')
    return primary, zero, json.loads(_TEMPLATES[2])


def json_proof_bytes(proof):
    return json.dumps(proof, sort_keys=True, separators=(',', ':')).encode()


def _dispatch(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    if len(gaps) != 2:
        COUNTS['original_arity_calls'] += 1
        return _original_solver(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
    COUNTS[_kind+'_two_contact_calls'] += 1
    return _two_contact_solver(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)


def dispatch(two_contact, original, kind):
    """Fresh private arity facade; all other arities call the exact original."""
    return FunctionType(_dispatch.__code__, dict(COUNTS=COUNTS, _original_solver=original,
        _two_contact_solver=two_contact, _kind=kind, _stage236_callback=callback), original.__name__)


@contextmanager
def scope():
    """Enter after original hot.scope; patch only its active primary and zero LM."""
    global _ACTIVE
    need(not _ACTIVE and hot.s50._solve is ORIGINAL_PRIMARY, 'Nonreentrant active original Stage136 primary required')
    need(_SOURCE_VALIDATED and _TEMPLATES is not None, 'Warm immutable callback templates before timed scope')
    primary, zero, proof = build()
    current_finish = ORIGINAL_PRIMARY.__globals__['_finish']
    transformed_primary = primary
    primary = dispatch(primary, ORIGINAL_PRIMARY, 'primary')
    zero = dispatch(zero, ORIGINAL_ZERO, 'zero')
    old_primary, old_zero = hot.s50._solve, s53._solve
    hot.s50._solve, s53._solve = primary, zero
    _ACTIVE = True
    COUNTS['scopes'] += 1
    try:
        yield dict(scope_proof=proof, binding_hits=dict(primary=True, zero=True))
    finally:
        exact = (hot.s50._solve is primary and s53._solve is zero
                 and ORIGINAL_PRIMARY.__globals__['_finish'] is current_finish
                 and hot.s50._finish is current_finish
                 and transformed_primary.__globals__['_finish'] is current_finish)
        hot.s50._solve, s53._solve = old_primary, old_zero
        _ACTIVE = False
        need(exact, 'Candidate scoped binding changed before exact restoration')


def telemetry(reset=False):
    result = dict(COUNTS)
    if reset:
        need(not _ACTIVE, 'Never reset active callback evidence')
        for key in COUNTS:
            COUNTS[key] = 0
    return result


def reset():
    return telemetry(reset=True)


def snapshot():
    return telemetry()


def warm():
    """Compile arithmetic on synthetic operands only; no contact/optimizer call."""
    validate_sources()
    build()
    u = np.zeros(6); scales = np.ones(6); z = np.zeros(6); A = np.eye(6)
    gaps = np.array([-0., 0.]); steps = np.ones(2)
    before = telemetry()
    for kind in ('primary', 'zero'):
        result = callback(u, scales, z, A, gaps, .01, .3, steps, 1., kind)
        need(result.tobytes() == original_equations(kind, scales, z, A, gaps, .01, .3, steps, 1.)(u).tobytes(),
             'Exact warm arithmetic')
    return dict(passed=True, arithmetic_callbacks=2, contact_solver_calls=0, outer_calls=0,
                warm_telemetry={k:COUNTS[k]-before[k] for k in COUNTS},
                numba_signatures=[str(x) for x in residual_kernel.signatures])


def controls(fixtures):
    """Byte-exact pure callback tests; no root/contact solve, integration or output."""
    validate_sources()
    primary, zero, proof = build()
    rows = fixtures['fixtures'] if isinstance(fixtures, dict) else fixtures
    systems = [s for row in rows for s in row['resolved_inner_systems']]
    need(systems and len(systems) <= 16, 'Bounded saved callback operand controls')
    rng = np.random.default_rng(236)
    tested = 0
    with np.errstate(all='ignore'):
        for system in systems:
            J, M, vfree = (np.asarray(system[k], dtype=float) for k in ('jacobian', 'mobility', 'vfree'))
            A, z = J@M@J.T, J@vfree
            gaps = np.asarray(system['gaps_m'], dtype=float)
            steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))])
            scales = np.repeat(steps, 3)
            for k in range(len(gaps)):
                scales[3*k] = A[3*k,3*k]
            scale = max(np.linalg.norm(vfree), 1e-15)
            dt, friction = system['dt_s'], system['friction']
            saved = np.asarray(system['health']['reactions'], dtype=float)*scales
            points = [saved, np.zeros(len(z)), np.full(len(z), -0.)]
            for level in (np.nextafter(0., 1.), 1e-308, 1e-150, 1e-8, 1., 1e150, 1e308):
                points += [np.full(len(z), level), np.full(len(z), -level)]
            quiet_nan = np.array([0x7ff8000000000236], dtype=np.uint64).view(np.float64)[0]
            for value in (np.inf, -np.inf, np.nan, quiet_nan):
                points.append(np.full(len(z), value))
                for i in range(len(z)):
                    point = saved.copy(); point[i] = value; points.append(point)
            for i in range(len(z)):
                delta = np.zeros(len(z)); delta[i] = np.sqrt(np.finfo(float).eps)*max(abs(saved[i]), 1.)
                points += [saved+delta, saved-delta]
            points += [rng.normal(size=len(z))*10.**rng.uniform(-150, 150) for _ in range(32)]
            # Both contact orders exercise the same exact callback oracle. No
            # cross-order bit identity or solved physical covariance is claimed.
            permutations = [np.arange(len(z)), np.concatenate([np.arange(3*k,3*k+3) for k in reversed(range(len(gaps)))])]
            for order in permutations:
                contact_order = order[::3]//3
                selected = (scales[order], z[order], A[np.ix_(order,order)], gaps[contact_order],
                            dt, friction, steps[contact_order], scale)
                snapshots = [v.tobytes() for v in selected if isinstance(v, np.ndarray)]
                for kind in ('primary', 'zero'):
                    reference = original_equations(kind, *selected)
                    for point in points:
                        u = np.ascontiguousarray(point[order]); before = u.tobytes()
                        expected, actual = reference(u), callback(u, *selected, kind)
                        need(expected.dtype == actual.dtype and expected.shape == actual.shape
                             and expected.tobytes() == actual.tobytes(),
                             'Exact original '+kind+' callback bytes at point '+str(tested))
                        need(u.tobytes() == before, 'Callback u unchanged')
                        tested += 1
                need(snapshots == [v.tobytes() for v in selected if isinstance(v, np.ndarray)], 'Callback operand arrays unchanged')
    old_primary, old_zero = hot.s50._solve, s53._solve
    # Pure sentinel dispatch exercises arity isolation without a real solver.
    def sentinel_original(*args): return ('original', args)
    def sentinel_two(*args): return ('two', args)
    for kind in ('primary', 'zero'):
        facade = dispatch(sentinel_two, sentinel_original, kind)
        for n in (0, 1, 2, 3, 4):
            args = (None, None, None, [0.]*n, .01, .3, 1e-10, 25000)
            answer = facade(*args)
            need(answer[0] == ('two' if n == 2 else 'original') and answer[1] == args,
                 'Whole-solver strict two-contact dispatch with original other arities')
    with hot.scope():
        with scope():
            need(hot.s50._solve.__globals__['_stage236_callback'] is callback
                 and s53._solve.__globals__['_stage236_callback'] is callback, 'Both actual scoped callback bindings hit')
        need(hot.s50._solve is ORIGINAL_PRIMARY and s53._solve is ORIGINAL_ZERO, 'Inner success restoration')
        try:
            with scope():
                raise RuntimeError('injected pure scope failure')
        except RuntimeError as error:
            need(str(error) == 'injected pure scope failure', 'Original scope failure propagated')
        need(hot.s50._solve is ORIGINAL_PRIMARY and s53._solve is ORIGINAL_ZERO, 'Inner exception restoration')
    need(hot.s50._solve is old_primary and s53._solve is old_zero, 'Outer original hot scope restoration')
    # Match the genuine outer layer order, but do not call any solver/finish.
    old_finish = hot.s50._finish
    with hot.scope():
        with fix.scope():
            with scope():
                fresh_primary = hot.s50._solve.__globals__['_two_contact_solver']
                need(fresh_primary.__globals__['_finish'] is fix.finish
                     and hot.s50._finish is fix.finish, 'Exact existing scoped finish copied freshly')
            need(ORIGINAL_PRIMARY.__globals__['_finish'] is fix.finish,
                 'Candidate leaves original surrounding finish scope intact')
    need(hot.s50._finish is old_finish
         and ORIGINAL_PRIMARY.__globals__['_finish'] is ORIGINAL_FINISH,
         'Surrounding original finish/hot scope restoration')
    return dict(passed=True, exact_arithmetic_points=tested, source_ast_proofs=proof,
        signed_zero_tiny_large_finite_difference_and_saved_force_controls=True,
        nonfinite_nan_payload_callback_bytes_preserved=True,
        other_contact_arities_delegate_exact_original_solver=True,
        exact_original_scoped_roundoff_finish_retained_and_restored=True,
        contact_order_callback_oracle_controls=True, solved_covariance_qualified=False,
        input_arrays_unchanged=True, success_and_exception_bindings_restored=True,
        candidate_callback_binding_hits=True, original_acceptance_gates_unchanged=True,
        root_calls=0, outer_calls=0, new_trajectory_steps=0, artifact_writes=0,
        numba_fastmath=False, numba_parallel=False, numba_cache=False,
        limitation='Pure callback equality only; current paired complete outer scientific outputs/route/physical audits, unprofiled cost and transport restart/full-path gates remain required.')
