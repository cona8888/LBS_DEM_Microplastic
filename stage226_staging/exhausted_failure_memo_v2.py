"""Opt-in, one-inner-call reuse of a witnessed exhausted Stage194 search.

This development scope never integrates or installs a production solver. Enter
it after the existing runtime repair and native numerical scopes. The equation
body is a separately compiled observer clone: removing its hooks reconstructs
the original AST exactly. Every uncertain outcome is a cache miss. Successful
forces are never cached. The cache has one entry and is discarded in finally.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
import ast
import copy
import dis
import hashlib
import inspect
import json
import marshal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage194_staging'))
import numpy as np
import early_semismooth_dispatch_v1 as previous

prior = previous.prior
ERROR = 'direct contact residual nonconvergence'
NAME = 'stage226_same_inner_witnessed_exhausted_failure_v2'
PHYSICAL_ERRORS = frozenset((ERROR, 'direct contact negative normal force',
    'direct contact cone violation', 'direct contact force closure failed',
    'friction generates energy'))
_witness_context = ContextVar('stage226_semismooth_witness', default=None)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _binding_value(value):
    """Exact dependency constants; nonfinite constants are allowed as bits.

    This is distinct from the finite float64 physical-operand contract below.
    Array defaults retain dtype, layout and bytes; object arrays and unknown
    mutable defaults cannot establish identity and conservatively miss.
    """
    if value is None or type(value) in (bool, str, bytes, int):
        return (type(value), value)
    if type(value) in (float, complex) or isinstance(value, np.generic):
        a = np.asarray(value)
        if a.dtype.hasobject:
            raise ValueError('object-valued binding constant is uncertain')
        return ('scalar_bits', type(value), a.dtype.str, repr(a.dtype.descr), a.tobytes())
    if type(value) is np.ndarray:
        if value.dtype.hasobject:
            raise ValueError('object-valued binding array is uncertain')
        return ('array_bits', type(value), value.shape, value.dtype.str,
                repr(value.dtype.descr), value.strides, bool(value.flags.c_contiguous),
                bool(value.flags.f_contiguous), value.tobytes(order='A'))
    if type(value) in (tuple, list):
        return (type(value), tuple(_binding_value(x) for x in value))
    if type(value) is dict and all(type(k) is str for k in value):
        return ('dict', tuple((k,_binding_value(value[k])) for k in sorted(value)))
    if isinstance(value, type):
        return ('type_binding', value)
    if callable(value):
        return ('callable_binding', id(value), id(getattr(value, '__code__', None)))
    if value is Ellipsis or value is NotImplemented or value is vars(np).get('_NoValue'):
        return ('immutable_singleton', type(value), id(value))
    if type(value) is object:
        # Plain built-in object sentinels have no mutable fields; identity is
        # their complete observable value. Unknown user objects still miss.
        return ('immutable_object_sentinel', id(value))
    raise ValueError('unknown binding constant is uncertain')


def _serial(value):
    if isinstance(value, type):
        return dict(type_name=value.__module__ + '.' + value.__qualname__)
    if type(value) is bytes:
        return dict(hex_bytes=value.hex())
    if type(value) in (tuple, list):
        return [_serial(x) for x in value]
    if type(value) is dict:
        return {str(k):_serial(v) for k,v in value.items()}
    if value is None or type(value) in (bool, str, int):
        return value
    if type(value) in (float, complex, np.ndarray) or isinstance(value, np.generic):
        return _serial(_binding_value(value))
    return dict(object_type=type(value).__module__ + '.' + type(value).__qualname__, object_id=id(value))


def _array_descriptor(value):
    key = _array_key(value)
    return dict(shape=list(key[0]), dtype=key[1], strides=list(key[2]),
                c_contiguous=key[3], f_contiguous=key[4], hex_bytes=key[5].hex())


def _scalar_descriptor(value):
    key = _scalar_key(value)
    return dict(type=key[0].__module__ + '.' + key[0].__qualname__,
                dtype=key[1], hex_bytes=key[2].hex())


def _array_key(value):
    # Include layout as well as values: equal element values need not imply
    # equal BLAS operand paths. Lists/subclasses/object arrays are safe misses.
    if type(value) is not np.ndarray or value.dtype != np.float64:
        raise ValueError('exact native float64 ndarray required for reuse')
    if not np.isfinite(value).all():
        raise ValueError('finite memo operand required')
    return (value.shape, value.dtype.str, value.strides,
            bool(value.flags.c_contiguous), bool(value.flags.f_contiguous),
            value.tobytes(order='A'))


def _scalar_key(value):
    if type(value) not in (float, int, np.float64, np.int64):
        raise ValueError('explicit ordinary scalar required for reuse')
    a = np.asarray(value)
    if a.ndim or not np.isfinite(a):
        raise ValueError('finite scalar required for reuse')
    return (type(value), a.dtype.str, a.tobytes())


def _policy_key(value):
    """Freeze a caller's explicit operand-policy binding, without rounding."""
    if value is None or type(value) in (bool, str, bytes, int):
        return (type(value), value)
    if type(value) in (float, np.float64, np.int64):
        return _scalar_key(value)
    if type(value) is np.ndarray:
        return _array_key(value)
    if type(value) in (tuple, list):
        return (type(value), tuple(_policy_key(x) for x in value))
    if type(value) is dict and all(type(k) is str for k in value):
        return ('dict', tuple((k, _policy_key(value[k])) for k in sorted(value)))
    if callable(value):
        return _callable_key(value)
    raise ValueError('policy must expose exact data or callable bindings')


def _callable_key(function, seen=None, depth=0):
    """Snapshot live callable dependencies; mutable telemetry contents excluded.

    Identity/code/defaults/closure identities are retained. Referenced module
    attributes are inspected using the function's global names; this includes
    private TRF proxies and the seed producer's dynamic scalar dispatch. The
    explicit policy payload separately covers mutable numerical policy data.
    """
    if seen is None:
        seen = set()
    marker = id(function)
    if marker in seen or depth > 8:
        return ('reference', marker)
    seen.add(marker)
    py = getattr(function, 'py_func', function)
    code = getattr(py, '__code__', None)
    if code is None:
        return ('callable', marker)
    closures = tuple(id(c.cell_contents) for c in (py.__closure__ or ()))
    token = ('function', marker, id(code), _binding_value(py.__defaults__),
             _binding_value(py.__kwdefaults__), closures)
    names = set(code.co_names)
    dependencies = []
    for name in sorted(names.intersection(py.__globals__)):
        value = py.__globals__[name]
        if callable(value):
            dependencies.append((name, _callable_key(value, seen, depth + 1)))
        elif isinstance(value, (ModuleType, SimpleNamespace)):
            attrs = []
            for attr in sorted(names):
                # Passive lookup avoids NumPy's lazy/deprecated __getattr__
                # machinery while snapshotting the actual installed bindings.
                other = vars(value).get(attr)
                if callable(other):
                    attrs.append((attr, _callable_key(other, seen, depth + 1)))
                elif isinstance(other, (ModuleType, SimpleNamespace)):
                    nested = tuple((n, id(vars(other)[n])) for n in sorted(names)
                                   if n in vars(other))
                    attrs.append((attr, id(other), nested))
                elif type(other) in (str, int, float, bool, complex) or isinstance(other, np.generic):
                    attrs.append((attr, _binding_value(other)))
                elif type(other) is np.ndarray:
                    attrs.append((attr, _binding_value(other)))
            dependencies.append((name, id(value), tuple(attrs)))
        elif type(value) is np.ndarray:
            dependencies.append((name, _binding_value(value)))
        elif type(value) in (str, int, float, bool, complex) or isinstance(value, np.generic):
            dependencies.append((name, _binding_value(value)))
    return token, tuple(dependencies)


def _terminal_offset(function, message=ERROR):
    """Recognize the exact terminal raise, including separately cloned code."""
    function = getattr(function, 'py_func', function)
    code = getattr(function, '__code__', None)
    if code is None:
        return None
    instructions = list(dis.get_instructions(code))
    candidates = []
    for index, instruction in enumerate(instructions):
        tail = instructions[max(0,index-4):index]
        if (instruction.opname == 'RAISE_VARARGS' and instruction.arg == 1
                and any(i.opname == 'LOAD_GLOBAL' and i.argval == 'RuntimeError' for i in tail)
                and any(i.opname == 'LOAD_CONST' and i.argval == message for i in tail)):
            candidates.append(instruction)
    # Python emits exception cleanup blocks after the main body's terminal
    # raise. Its source position, rather than final bytecode position, proves
    # this is the final source statement. Require an unambiguous exact raise.
    last_line = max((i.positions.end_lineno or 0) for i in instructions)
    if len(candidates) != 1 or candidates[0].positions.end_lineno != last_line:
        return None
    return candidates[0].offset


def _origin(error, function, message=ERROR):
    tb = error.__traceback__
    if tb is None:
        return False
    while tb.tb_next is not None:
        tb = tb.tb_next
    function = getattr(function, 'py_func', function)
    return (type(error) is RuntimeError and str(error) == message
            and tb.tb_frame.f_code is getattr(function, '__code__', None)
            and tb.tb_lasti == _terminal_offset(function, message))


def _error_record(error):
    tb = error.__traceback__
    frames = []
    while tb is not None:
        frames.append(dict(file=tb.tb_frame.f_code.co_filename,
                           function=tb.tb_frame.f_code.co_name,
                           line=tb.tb_lineno, offset=tb.tb_lasti))
        tb = tb.tb_next
    return dict(type=type(error).__name__, message=str(error), frames=frames)


class _Witness:
    def __init__(self, seed_producer):
        self.seed_producer = seed_producer
        self.record = dict(seed_gate_rejections=[], ordered=[], optimizers=[],
                           finalizer_rejections=[], swallowed_errors=[],
                           seed_internal_exceptions=[], seed_trace_complete=False,
                           producer=None, terminal_reached=False)
        self.unsafe = False

    def seed_gate(self, error, force, name):
        finite = bool(np.isfinite(np.asarray(force)).all())
        self.record['seed_gate_rejections'].append(dict(error=_error_record(error),
            force=np.asarray(force).tolist() if finite else None, solver=name,
            finite=finite))
        if type(error) is not RuntimeError or str(error) not in PHYSICAL_ERRORS or not finite:
            self.unsafe = True

    def producer_success(self, answer):
        finite = bool(np.isfinite(np.asarray(answer[0])).all()
                      and np.isfinite(np.asarray(answer[1]['reactions'])).all())
        self.record['producer'] = dict(outcome='success', finite=finite)
        self.unsafe |= not finite

    def producer_error(self, error):
        scalar = self.seed_producer.__globals__.get('scalar_solve')
        completed = scalar is not None and _origin(error, scalar)
        row = dict(outcome='exhausted' if completed else 'uncertain',
                   terminal_origin=completed, error=_error_record(error))
        self.record['producer'] = row
        self.record['swallowed_errors'].append(row)
        self.unsafe |= not completed

    def order(self, seeds, ordered):
        rows = []
        for source_index, seed in ordered:
            finite = bool(np.isfinite(seed['force']).all()
                          and np.isfinite(seed['residual']))
            rows.append(dict(source_index=source_index, finite=finite,
                             force=np.asarray(seed['force']).tolist() if finite else None,
                             residual=float(seed['residual']) if finite else None,
                             solver=seed['solver'], error=seed['error']))
            self.unsafe |= not finite
        self.record['ordered'] = rows
        self.record['seed_candidate_count'] = len(seeds)
        # Empty seeds can mean a swallowed failure before any gate was reached.
        self.unsafe |= not bool(rows)

    def optimizer_start(self, index, source_index):
        self.record['optimizers'].append(dict(index=index, source_index=source_index,
                                              completed=False))

    def optimizer_end(self, index, opt):
        finite = all(np.isfinite(np.asarray(getattr(opt, field))).all()
                     for field in ('x', 'fun', 'jac', 'grad', 'cost', 'optimality'))
        counts = (type(opt.nfev) in (int, np.int64) and 0 < opt.nfev <= 2000
                  and type(opt.status) in (int, np.int64) and 0 <= opt.status <= 4)
        row = self.record['optimizers'][-1]
        row.update(completed=True, finite=bool(finite), nfev=int(opt.nfev),
                   njev=None if opt.njev is None else int(opt.njev),
                   status=int(opt.status), success=bool(opt.success),
                   result_sha256=_digest({field:np.asarray(getattr(opt, field)).tolist()
                       for field in ('x', 'fun', 'jac', 'grad', 'cost', 'optimality')})
                   if finite else None)
        self.unsafe |= index != row['index'] or not finite or not counts

    def rejected(self, index, error):
        self.record['finalizer_rejections'].append(dict(index=index, error=_error_record(error)))
        self.unsafe |= type(error) is not RuntimeError or str(error) not in PHYSICAL_ERRORS

    def exhausted(self, seeds, ordered):
        expected = list(range(len(ordered)))
        self.record['terminal_reached'] = True
        self.record['all_ordered_attempted'] = (
            [x['index'] for x in self.record['optimizers']] == expected
            and all(x['completed'] for x in self.record['optimizers'])
            and [x['index'] for x in self.record['finalizer_rejections']] == expected)

    def eligible(self, error, helper):
        producer = self.record['producer'] or {}
        return (not self.unsafe and producer.get('outcome') in ('success', 'exhausted')
                and self.record['seed_trace_complete']
                and self.record['terminal_reached']
                and self.record.get('all_ordered_attempted', False)
                and bool(self.record['ordered']) and _origin(error, helper))


class _Hooks:
    def __getattr__(self, name):
        def observe(*args):
            witness = _witness_context.get()
            if witness is not None:
                getattr(witness, name)(*args)
        return observe


class _Report(dict):
    """JSON-compatible report with a separate scoped portfolio-entry adapter."""


def _observed_seed(seed_producer):
    """See numeric exceptions even when older seed routines swallow them.

    Trace only during seed generation; line/opcode tracing is disabled. An
    existing debugger/tracer makes eligibility uncertain and is left intact.
    No exception is handled here, and the previous tracing binding is restored.
    """
    def observed(*args):
        witness = _witness_context.get()
        if witness is None:
            return seed_producer(*args)
        saved = sys.gettrace()
        if saved is not None:
            witness.unsafe = True
            witness.record['preexisting_seed_trace'] = True
            return seed_producer(*args)
        def trace(frame, event, arg):
            frame.f_trace_lines = False
            frame.f_trace_opcodes = False
            if event == 'exception':
                kind, error, tb = arg
                if kind not in (StopIteration, GeneratorExit):
                    physical = type(error) is RuntimeError and str(error) in PHYSICAL_ERRORS
                    witness.record['seed_internal_exceptions'].append(dict(
                        type=kind.__name__, message=str(error), physical_rejection=physical,
                        file=frame.f_code.co_filename, function=frame.f_code.co_name,
                        line=frame.f_lineno, offset=frame.f_lasti))
                    witness.unsafe |= not physical
            return trace
        sys.settrace(trace)
        try:
            return seed_producer(*args)
        finally:
            sys.settrace(saved)
            witness.record['seed_trace_complete'] = True
    return observed


def _observer_clone(seed_producer):
    source = inspect.getsource(prior.solve)
    original = ast.parse(source)
    tree = copy.deepcopy(original)
    fn = tree.body[0]
    hooks = []

    def hook(text):
        node = ast.parse('_memo_hooks.' + text).body[0]
        hooks.append(node)
        return node

    # Only observer statements and exception aliases are added. Exact shapes
    # of these source locations are asserted before compiling the new body.
    observe = next(x for x in fn.body if isinstance(x, ast.FunctionDef) and x.name == 'observe')
    observed_handler = observe.body[0].handlers[0]
    assert observed_handler.name == 'error' and isinstance(observed_handler.body[-1], ast.Raise)
    observed_handler.body.insert(-1, hook('seed_gate(error, f, name)'))
    producer = next(x for x in fn.body if isinstance(x, ast.Try)
                    and any('fast.solve' in ast.unparse(y) for y in x.body))
    producer.body.append(hook('producer_success(answer)'))
    assert producer.handlers[0].name is None and ast.unparse(producer.handlers[0].body[0]) == 'pass'
    producer.handlers[0].name = '_memo_producer_error'
    producer.handlers[0].body.insert(0, hook('producer_error(_memo_producer_error)'))
    order_index = next(i for i,x in enumerate(fn.body)
                       if isinstance(x, ast.Assign) and ast.unparse(x.targets[0]) == 'ordered')
    fn.body.insert(order_index + 1, hook('order(seeds, ordered)'))
    loop = next(x for x in fn.body if isinstance(x, ast.For)
                and ast.unparse(x.target) == '(seed_index, (source_index, seed))')
    opt_index = next(i for i,x in enumerate(loop.body)
                     if isinstance(x, ast.Assign) and ast.unparse(x.targets[0]) == 'opt')
    loop.body.insert(opt_index, hook('optimizer_start(seed_index, source_index)'))
    loop.body.insert(opt_index + 2, hook('optimizer_end(seed_index, opt)'))
    finish_try = next(x for x in loop.body if isinstance(x, ast.Try))
    assert finish_try.handlers[0].name is None and ast.unparse(finish_try.handlers[0].body[0]) == 'continue'
    finish_try.handlers[0].name = '_memo_final_error'
    finish_try.handlers[0].body.insert(0, hook('rejected(seed_index, _memo_final_error)'))
    assert isinstance(fn.body[-1], ast.Raise) and ERROR in ast.unparse(fn.body[-1])
    fn.body.insert(-1, hook('exhausted(seeds, ordered)'))

    stripped = copy.deepcopy(tree)
    class RemoveObservers(ast.NodeTransformer):
        def visit_Expr(self, node):
            if (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                    and isinstance(node.value.func.value, ast.Name)
                    and node.value.func.value.id == '_memo_hooks'):
                return None
            return self.generic_visit(node)
        def visit_ExceptHandler(self, node):
            if node.name in ('_memo_producer_error', '_memo_final_error'):
                node.name = None
            return self.generic_visit(node)
    RemoveObservers().visit(stripped)
    assert ast.dump(stripped, include_attributes=False) == ast.dump(original, include_attributes=False), 'observer-only AST reconstruction'
    ast.fix_missing_locations(tree)
    namespace = {**prior.solve.__globals__, 'fast':SimpleNamespace(solve=_observed_seed(seed_producer)),
                 '_memo_hooks':_Hooks()}
    exec(compile(tree, __file__ + '::observer_only_semismooth', 'exec'), namespace)
    function = namespace['solve']
    return function, dict(observer_hooks=len(hooks), original_ast_sha256=
        hashlib.sha256(ast.dump(original, include_attributes=False).encode()).hexdigest(),
        stripped_ast_exact=True, equations_changed=False)


@contextmanager
def scope(runtime, enabled=False, stop_epoch=None, policy_binding=None,
          certificate_binding=None, reuse=True):
    """Replace Stage194 repair.scope in its original outer context position.

    policy_binding must return the exact operand-policy contract and live
    classifier bindings; without it requests execute and cannot be reused.
    Enter report.inner_scope() AFTER runtime.repair_scope(). This preserves the
    existing early/primary/reduced/projection order and spans its entire call.
    certificate_binding exposes all external numeric seed evidence as exact
    JSON data (counts and content hashes). Any emission makes reuse ineligible.
    reuse=False provides an identically observed baseline for paired replay.
    """
    if type(enabled) is not bool or type(reuse) is not bool:
        raise ValueError('explicit Boolean opt-in and reuse mode required')
    report = _Report(name=NAME, enabled=enabled, logical_requests=0, executed_requests=0,
                  reused_requests=0, inner_calls=0, events=[], ast=None,
                  production_authorized=False, new_trajectory_steps=0,
                  stop_epoch=stop_epoch, inner_scope_entries=0,
                  reuse_enabled=reuse, cache_clears=0,
                  seed_exception_coverage='Python seed call-tree exceptions; native internal exceptions only when propagated to a traced Python frame. No claim about hidden native internal errors.')
    if not enabled:
        @contextmanager
        def disabled_inner():
            yield
        report.inner_scope = disabled_inner
        yield report
        return
    if stop_epoch is None or not np.isfinite(stop_epoch):
        raise ValueError('finite explicit qualification deadline required')
    seed_producer = prior.fast.solve
    helper, report['ast'] = _observer_clone(seed_producer)
    report['helper_code_sha256'] = hashlib.sha256(marshal.dumps(helper.__code__)).hexdigest()
    report['helper_terminal_offset'] = _terminal_offset(helper)
    report['ast'].update(helper_code_sha256=report['helper_code_sha256'],
                         terminal_raise_offset=report['helper_terminal_offset'])
    portfolio = runtime.probe.RECOVERY.portfolio
    active = None

    def bindings():
        if policy_binding is None or certificate_binding is None:
            return None
        # Re-evaluate all live dependencies for each request, including exact
        # policy data. Solver wrappers may change between scopes; safe misses.
        return (id(prior.solve), _callable_key(seed_producer),
                _callable_key(prior.analytic.system), _callable_key(prior.least_squares),
                _callable_key(prior.gate._finish), _callable_key(prior.gate._residual),
                _callable_key(prior.gate._project), id(policy_binding),
                _policy_key(policy_binding()))

    def request(v, M, J, g, dt, mu, tol, maxiter, stop_epoch=None):
        nonlocal active
        entry_epoch = time.time()
        report['logical_requests'] += 1
        event = dict(id=len(report['events']), inner_call=None if active is None else active['id'],
                     logical_request=report['logical_requests'], executed=False, reused=False,
                     stop_epoch=stop_epoch, entry_checked_epoch=entry_epoch,
                     helper_code_id=id(helper.__code__), helper_terminal_offset=_terminal_offset(helper),
                     helper_code_sha256=report['helper_code_sha256'])
        report['events'].append(event)
        if entry_epoch >= stop_epoch:
            event.update(checked_epoch=entry_epoch, keyable=False,
                         disposition='cutoff_before_fingerprint', optimizer_calls_executed=0,
                         cache_eligible=False)
            raise RuntimeError('diagnostic work cutoff reached')
        certificate_before = None
        try:
            dependency_key = bindings()
            key = (tuple(_array_key(x) for x in (v,M,J,g)),
                   tuple(_scalar_key(x) for x in (dt,mu,tol,maxiter,stop_epoch)), dependency_key)
            keyable = dependency_key is not None
            descriptor = dict(arrays={k:_array_descriptor(x) for k,x in zip(('v','M','J','g'),(v,M,J,g))},
                scalars={k:_scalar_descriptor(x) for k,x in zip(('dt','mu','tol','maxiter','stop_epoch'),
                    (dt,mu,tol,maxiter,stop_epoch))}, binding_sha256=_digest(_serial(dependency_key)))
            key_repr = repr(key)
            event.update(key_descriptor=descriptor, key_descriptor_sha256=_digest(descriptor),
                         key_repr=key_repr, key_sha256=hashlib.sha256(key_repr.encode()).hexdigest(),
                         binding_sha256=descriptor['binding_sha256'], binding_descriptor=_serial(dependency_key))
            if certificate_binding is not None:
                certificate_before = copy.deepcopy(certificate_binding())
                event['certificate_binding_before'] = certificate_before
                event['certificate_binding_before_sha256'] = _digest(certificate_before)
                event['certificate_before_sha256'] = event['certificate_binding_before_sha256']
        except (ValueError, TypeError, AttributeError, RecursionError):
            key, keyable = None, False
        event['keyable'] = keyable
        # Fingerprinting can itself take time. Recheck immediately before any
        # lookup and record that fresh decision for the independent auditor.
        event['checked_epoch'] = time.time()
        if event['checked_epoch'] >= stop_epoch:
            event.update(disposition='cutoff_before_lookup', optimizer_calls_executed=0)
            raise RuntimeError('diagnostic work cutoff reached')
        entry = None if active is None else active['entry']
        if reuse and keyable and entry is not None and entry['key'] == key:
            # The cache stores only a witness reference, never a copied force,
            # optimizer return, or fabricated second seed certificate.
            report['reused_requests'] += 1
            event.update(reused=True, disposition='reused_exhausted_failure',
                         first_failure_event=entry['event'], witness_sha256=entry['witness_sha256'],
                         optimizer_calls_executed=0, bindings_after_sha256=event['binding_sha256'],
                         certificate_binding_after=copy.deepcopy(certificate_before),
                         certificate_binding_after_sha256=event.get('certificate_binding_before_sha256'),
                         certificate_after_sha256=event.get('certificate_before_sha256'),
                         seed_certificate_delta=0, cache_eligible=True)
            raise RuntimeError(ERROR)
        report['executed_requests'] += 1
        event['executed'] = True
        witness = _Witness(seed_producer)
        token = _witness_context.set(witness)
        try:
            answer = helper(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
        except BaseException as error:
            eligible = witness.eligible(error, helper)
            try:
                dependencies_after = bindings()
                stable = keyable and dependency_key == dependencies_after
                event['bindings_after_sha256'] = _digest(_serial(dependencies_after))
                certificate_after = None if certificate_binding is None else copy.deepcopy(certificate_binding())
                certificate_stable = (certificate_before is not None
                    and certificate_after == certificate_before)
                event.update(certificate_binding_after=certificate_after,
                    certificate_binding_after_sha256=None if certificate_after is None else _digest(certificate_after),
                    certificate_after_sha256=None if certificate_after is None else _digest(certificate_after),
                    seed_certificate_delta=0 if certificate_stable else None,
                    external_numeric_seed_evidence_unchanged=certificate_stable)
            except (ValueError, TypeError, AttributeError, RecursionError):
                stable, certificate_stable = False, False
            event.update(disposition='executed_failure', error=_error_record(error),
                         witnessed_exhaustion=eligible, bindings_unchanged=stable,
                         witness=copy.deepcopy(witness.record),
                         optimizer_calls_executed=len(witness.record['optimizers']),
                         final_raise_origin=_origin(error, helper),
                         cache_eligible=bool(active is not None and eligible and stable and certificate_stable))
            event['witness_sha256'] = _digest(event['witness'])
            if active is not None and eligible and stable and certificate_stable:
                # Max one entry, replaced only by a fully witnessed exhaustion.
                active['entry'] = dict(key=key, event=event['id'],
                                       witness_sha256=event['witness_sha256'])
            raise
        else:
            event.update(disposition='executed_success', witnessed_exhaustion=False,
                         witness=copy.deepcopy(witness.record),
                         optimizer_calls_executed=len(witness.record['optimizers']))
            return answer
        finally:
            _witness_context.reset(token)

    generator = prior.scope.__wrapped__
    bound = FunctionType(generator.__code__, {**generator.__globals__, 'solve':request},
                         generator.__name__, generator.__defaults__, generator.__closure__)

    def early_candidate(*args):
        try:
            return seed_producer(*args)
        except RuntimeError as error:
            if str(error) not in prior.ERRORS:
                raise
            try:
                return request(*args, stop_epoch=stop_epoch)
            except (RuntimeError, ValueError, np.linalg.LinAlgError, FloatingPointError):
                raise error

    def inner(original_portfolio, *args):
        nonlocal active
        # Nested portfolio entries get independent caches and restore parent
        # state. They cannot accidentally share reaction or failure history.
        saved = active
        report['inner_calls'] += 1
        active = dict(id=report['inner_calls'], entry=None)
        try:
            return original_portfolio(*args)
        finally:
            active['entry'] = None
            report['cache_clears'] += 1
            active = saved

    @contextmanager
    def inner_scope():
        original_portfolio = portfolio._solve
        def bound_inner(*args):
            return inner(original_portfolio, *args)
        report['inner_scope_entries'] += 1
        portfolio._solve = bound_inner
        try:
            yield
        finally:
            portfolio._solve = original_portfolio
    report.inner_scope = inner_scope

    with contextmanager(bound)(runtime, True, stop_epoch):
        prior.fast.solve = early_candidate
        try:
            yield report
        finally:
            prior.fast.solve = seed_producer
            active = None
            report['cache_retained'] = False
