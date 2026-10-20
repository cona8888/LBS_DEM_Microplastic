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
from types import CodeType, FunctionType, ModuleType, SimpleNamespace
import ast
import copy
import dis
import hashlib
import inspect
import json
import marshal
import sys
import time
import struct

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage194_staging'))
import numpy as np
import early_semismooth_dispatch_v1 as previous

prior = previous.prior
ERROR = 'direct contact residual nonconvergence'
NAME = 'stage228_scope_metadata_guarded_v3'
PHYSICAL_ERRORS = frozenset((ERROR, 'direct contact negative normal force',
    'direct contact cone violation', 'direct contact force closure failed',
    'friction generates energy'))
_witness_context = ContextVar('stage226_semismooth_witness', default=None)
ROUTE_POLICY = 'stage227_exact_single_failed_early_append_v1'
ROUTE_FIELDS = frozenset(('dt_s','gaps_m','accepted','error','wall_s'))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _code_constant(value):
    """Typed immutable code constants, independent of marshal references."""
    kind = type(value)
    if value is None:
        return dict(type='none')
    if kind is bool:
        return dict(type='bool', value=value)
    if kind is int:
        return dict(type='int', value=str(value))
    if kind is str:
        return dict(type='str', value=value)
    if kind is bytes:
        return dict(type='bytes', hex_bytes=value.hex())
    if kind is float:
        return dict(type='float', hex_bytes=struct.pack('<d', value).hex())
    if kind is complex:
        return dict(type='complex', hex_bytes=struct.pack('<dd', value.real, value.imag).hex())
    if kind is tuple:
        return dict(type='tuple', items=[_code_constant(x) for x in value])
    if kind is frozenset:
        items = [_code_constant(x) for x in value]
        return dict(type='frozenset', items=sorted(items, key=_canonical))
    if kind is CodeType:
        return dict(type='code', value=_code_descriptor(value))
    if value is Ellipsis:
        return dict(type='ellipsis')
    raise ValueError('unsupported immutable code constant')


def _code_descriptor(code):
    """All immutable executable/debug code fields and typed constants.

    Raw marshal hashes are retained separately as diagnostics: their shared
    reference and string-interning flags are not immutable code semantics.
    """
    if type(code) is not CodeType:
        raise ValueError('actual immutable Python code object required')
    fields = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount',
        'co_nlocals', 'co_stacksize', 'co_flags', 'co_code', 'co_names',
        'co_varnames', 'co_filename', 'co_name', 'co_qualname',
        'co_firstlineno', 'co_linetable', 'co_exceptiontable', 'co_freevars',
        'co_cellvars')
    descriptor = {}
    for field in fields:
        value = getattr(code, field)
        descriptor[field] = value.hex() if type(value) is bytes else list(value) if type(value) is tuple else value
    descriptor['co_consts'] = [_code_constant(value) for value in code.co_consts]
    return descriptor


def _route_snapshot(records, certificates):
    if type(records) is not list or type(certificates) is not dict:
        raise ValueError('complete route records and certificate mapping required')
    marker = certificates.get('fast_attempts')
    if (type(marker) is not dict or type(marker.get('count')) is not int
            or marker['count'] != len(records) or marker.get('sha256') != _digest(records)):
        raise ValueError('full actual fast_attempts channel association required')
    return copy.deepcopy(records)


def _single_route_append(origin, current, before_records, after_records, association,
                         current_inner, key_descriptor):
    """A new declared evidence rule; it never changes a physical acceptance."""
    if type(origin) is not dict or type(current) is not dict or set(origin) != set(current):
        return None
    if any(_canonical(origin[k]) != _canonical(current[k]) for k in origin if k != 'fast_attempts'):
        return None
    try:
        before = _route_snapshot(before_records, origin)
        after = _route_snapshot(after_records, current)
    except (TypeError, ValueError):
        return None
    if len(after) != len(before) + 1 or _canonical(after[:-1]) != _canonical(before):
        return None
    if (type(association) is not dict or association.get('inner_call') != current_inner
            or association.get('original_error_terminal_origin') is not True
            or association.get('original_error_returned') is not True
            or association.get('helper_request_exhausted') is not True):
        return None
    if association.get('pending_route_index') != len(before):
        return None
    if association.get('operands') != key_descriptor:
        return None
    if association.get('captured_params') != {
            'arrays':key_descriptor['arrays'], 'scalars':key_descriptor['scalars']}:
        return None
    row = after[-1]
    error = association.get('original_error')
    if (type(row) is not dict or set(row) != ROUTE_FIELDS or row.get('accepted') is not False
            or type(error) is not dict or error.get('type') != 'RuntimeError'
            or type(row.get('error')) is not str or row['error'] != error.get('message')
            or row['error'] not in PHYSICAL_ERRORS):
        return None
    if (type(row['dt_s']) is not float or type(row['gaps_m']) is not list
            or len(row['gaps_m']) != 3 or any(type(x) is not float for x in row['gaps_m'])
            or not np.isfinite([row['dt_s'], *row['gaps_m']]).all()):
        return None
    try:
        dt = _scalar_descriptor(float(row['dt_s']))
        gaps = _array_descriptor(np.asarray(row['gaps_m'], dtype=float))
        # Stage172 stores dt as a Python float and gaps as a plain list. Compare
        # the exact IEEE payload without weakening the original operand key.
        if dt['hex_bytes'] != key_descriptor['scalars']['dt']['hex_bytes']:
            return None
        if gaps['shape'] != [3] or gaps['hex_bytes'] != key_descriptor['arrays']['g']['hex_bytes']:
            return None
        if type(row['wall_s']) is not float or not np.isfinite(row['wall_s']) or row['wall_s'] < 0:
            return None
    except (TypeError, ValueError, KeyError):
        return None
    return dict(policy=ROUTE_POLICY, kind='failed_early_append',
        inner_call=current_inner, appended_index=len(before), appended_row=copy.deepcopy(row),
        appended_row_sha256=_digest(row), before_records_sha256=_digest(before),
        after_records_sha256=_digest(after), association_sha256=_digest(association),
        numerical_channels_unchanged=True, all_original_records_retained=True)


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


def _closure_map_key(value):
    """Exact known immutable mapping keys; callable/user-object keys miss."""
    if value is None or type(value) in (bool, str, bytes, int):
        return _binding_value(value)
    if type(value) is tuple:
        return (tuple, tuple(_closure_map_key(x) for x in value))
    raise ValueError('closure mapping key is not a known immutable value')


def _closure_value(value, seen, depth):
    """Fresh closure leaves; uncertain cycles/deep containers safely miss."""
    if depth > 8:
        raise ValueError('closure dependency depth is uncertain')
    if callable(value) and not isinstance(value, type):
        return _callable_key(value, seen, depth)
    if type(value) in (tuple, list):
        return (type(value), tuple(_closure_value(x, seen, depth + 1) for x in value))
    if type(value) is dict:
        # Preserve actual insertion order as well as every typed key/value.
        # SciPy's installed BLAS/LAPACK dispatch caches use immutable tuple
        # keys and native callable values. Neither content nor order is omitted.
        return ('ordered_dict', tuple((_closure_map_key(k),
            _closure_value(v, seen, depth + 1)) for k, v in value.items()))
    return _binding_value(value)


def _callable_key(function, seen=None, depth=0):
    """Snapshot live callable dependencies; mutable telemetry contents excluded.

    Identity/code/defaults and fresh typed closure contents are retained. Referenced module
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
    closures = tuple(('cell', id(c), _closure_value(c.cell_contents, seen, depth + 1))
                     for c in (py.__closure__ or ()))
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


class _ScopeCodeMetadata:
    """Cache immutable code proof once; check each actual live binding.

    Strong references keep every witnessed function, py_func and code object
    alive. No default, global, closure, certificate or operand is cached here.
    Changed live function/code identities return no authenticated metadata.
    """
    def __init__(self):
        self._records = {}

    def bind(self, function):
        marker = id(function)
        if marker in self._records:
            return self.current(function)
        py = getattr(function, 'py_func', function)
        code = getattr(py, '__code__', None)
        if type(code) is not CodeType:
            raise ValueError('immutable Python code required for metadata')
        descriptor = _code_descriptor(code)
        record = dict(function_object=function, py_object=py, code_object=code,
            terminal_raise_offset=_terminal_offset(py),
            code_sha256=hashlib.sha256(marshal.dumps(code)).hexdigest(),
            code_descriptor=descriptor, code_descriptor_sha256=_digest(descriptor))
        self._records[marker] = record
        return record

    def current(self, function):
        record = self._records.get(id(function))
        if record is None or record['function_object'] is not function:
            return None
        py = getattr(function, 'py_func', function)
        if py is not record['py_object'] or getattr(py, '__code__', None) is not record['code_object']:
            return None
        return record

    def terminal(self, function, message=ERROR):
        record = self.current(function)
        return None if record is None or message != ERROR else record['terminal_raise_offset']

    def fingerprint(self, function):
        # Controls retain this same metadata object between fixture mutations.
        # Mutable dependency contents are still freshly read on every call.
        if self.bind(function) is None:
            raise ValueError('live code binding changed within metadata scope')
        return _callable_key(function)


def _checked_deadline(stop_epoch, event, disposition):
    """The actual request clock guard, also exposed to pure cutoff controls."""
    checked = time.time()
    event['checked_epoch'] = checked
    if checked >= stop_epoch:
        event.update(disposition=disposition, optimizer_calls_executed=0,
                     cache_eligible=False)
        raise RuntimeError('diagnostic work cutoff reached')
    return checked


def cutoff_control():
    """Exercise the actual request guard without entering any solver body."""
    event = {}
    stop = time.time() - 1.0
    try:
        _checked_deadline(stop, event, 'cutoff_before_lookup')
    except RuntimeError as error:
        return dict(rejected=type(error) is RuntimeError and
                    str(error) == 'diagnostic work cutoff reached',
                    checked_epoch=event['checked_epoch'], stop_epoch=stop,
                    solver_calls=0, optimizer_calls=0,
                    actual_guard='_checked_deadline')
    return dict(rejected=False, solver_calls=0, optimizer_calls=0)


def _origin(error, function, message=ERROR, metadata=None):
    tb = error.__traceback__
    if tb is None:
        return False
    while tb.tb_next is not None:
        tb = tb.tb_next
    function = getattr(function, 'py_func', function)
    return (type(error) is RuntimeError and str(error) == message
            and tb.tb_frame.f_code is getattr(function, '__code__', None)
            and tb.tb_lasti == (_terminal_offset(function, message) if metadata is None
                                 else metadata.terminal(function, message)))


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
    def __init__(self, seed_producer, metadata=None):
        self.seed_producer = seed_producer
        self.metadata = metadata
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
        completed = scalar is not None and _origin(error, scalar, metadata=self.metadata)
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
                and bool(self.record['ordered']) and _origin(error, helper, metadata=self.metadata))


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
          certificate_binding=None, route_records=None, reuse=True):
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
                  route_delta_policy=ROUTE_POLICY,
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
    original_scalar = seed_producer.__globals__.get('scalar_solve')
    metadata = _ScopeCodeMetadata()
    scalar_metadata = None if original_scalar is None else metadata.bind(original_scalar)
    report['original_early_error_binding'] = dict(
        function_id=None if original_scalar is None else id(original_scalar),
        code_id=None if original_scalar is None else id(scalar_metadata['code_object']),
        function=None if original_scalar is None else scalar_metadata['code_object'].co_name,
        file=None if original_scalar is None else scalar_metadata['code_object'].co_filename,
        terminal_raise_offset=None if scalar_metadata is None else scalar_metadata['terminal_raise_offset'],
        code_sha256=None if scalar_metadata is None else scalar_metadata['code_sha256'],
        code_descriptor=None if scalar_metadata is None else copy.deepcopy(scalar_metadata['code_descriptor']),
        code_descriptor_sha256=None if scalar_metadata is None else scalar_metadata['code_descriptor_sha256'])
    helper, report['ast'] = _observer_clone(seed_producer)
    helper_metadata = metadata.bind(helper)
    report['helper_code_sha256'] = helper_metadata['code_sha256']
    report['helper_terminal_offset'] = helper_metadata['terminal_raise_offset']
    report['scope_code_metadata'] = dict(immutable_only=True, live_identity_guarded=True,
        helper_code_id=id(helper_metadata['code_object']),
        original_scalar_code_id=None if scalar_metadata is None else id(scalar_metadata['code_object']))
    report['ast'].update(helper_code_sha256=report['helper_code_sha256'],
                         terminal_raise_offset=report['helper_terminal_offset'])
    portfolio = runtime.probe.RECOVERY.portfolio
    active = None

    def bindings():
        if policy_binding is None or certificate_binding is None or route_records is None:
            return None
        if (metadata.current(helper) is None or original_scalar is None
                or seed_producer.__globals__.get('scalar_solve') is not original_scalar
                or metadata.current(original_scalar) is None):
            return None
        # Re-evaluate all live dependencies for each request, including exact
        # policy data. Solver wrappers may change between scopes; safe misses.
        return (id(prior.solve), _callable_key(seed_producer),
                _callable_key(prior.analytic.system), _callable_key(prior.least_squares),
                _callable_key(prior.gate._finish), _callable_key(prior.gate._residual),
                _callable_key(prior.gate._project), id(policy_binding), id(certificate_binding),
                id(route_records),
                _policy_key(policy_binding()))

    def request(v, M, J, g, dt, mu, tol, maxiter, stop_epoch=None):
        nonlocal active
        entry_epoch = time.time()
        report['logical_requests'] += 1
        event = dict(id=len(report['events']), inner_call=None if active is None else active['id'],
                     logical_request=report['logical_requests'], executed=False, reused=False,
                     stop_epoch=stop_epoch, entry_checked_epoch=entry_epoch,
                     helper_code_id=id(helper.__code__), helper_terminal_offset=metadata.terminal(helper),
                     helper_code_sha256=report['helper_code_sha256'])
        report['events'].append(event)
        event['keyable'] = False
        _checked_deadline(stop_epoch, event, 'cutoff_before_fingerprint')
        certificate_before = None
        routes_before = None
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
                if route_records is not None:
                    routes_before = _route_snapshot(copy.deepcopy(route_records()), certificate_before)
                    event.update(route_records_before=routes_before,
                                 route_records_before_sha256=_digest(routes_before))
            if active is not None and active.get('pending_early') is not None:
                active['pending_early']['origin_event'] = event['id']
                association = copy.deepcopy(active['pending_early'])
                association['operands'] = copy.deepcopy(descriptor)
                association['origin_event'] = event['id']
                event['early_wrapper_association'] = association
        except (ValueError, TypeError, AttributeError, RecursionError):
            key, keyable = None, False
        event['keyable'] = keyable
        # Fingerprinting can itself take time. Recheck immediately before any
        # lookup and record that fresh decision for the independent auditor.
        _checked_deadline(stop_epoch, event, 'cutoff_before_lookup')
        entry = None if active is None else active['entry']
        receipt = None
        if reuse and keyable and entry is not None and entry['key'] == key:
            if event.get('certificate_before_sha256') == entry['certificate_sha256']:
                receipt = dict(policy=ROUTE_POLICY, kind='unchanged_full_evidence',
                    inner_call=active['id'], numerical_channels_unchanged=True,
                    before_records_sha256=_digest(entry['route_after']),
                    after_records_sha256=_digest(routes_before), all_original_records_retained=True)
            else:
                receipt = _single_route_append(entry['certificate_after'], certificate_before,
                    entry['route_after'], routes_before,
                    report['events'][entry['event']].get('early_wrapper_association'), active['id'],
                    event['key_descriptor'])
        # Evidence-delta verification also consumes time. The lookup decision
        # gets its own final fresh clock check after that verification.
        _checked_deadline(stop_epoch, event, 'cutoff_before_lookup')
        if (reuse and keyable and entry is not None and entry['key'] == key
                and receipt is not None):
            # The cache stores only a witness reference, never a copied force,
            # optimizer return, or fabricated second seed certificate.
            report['reused_requests'] += 1
            event.update(reused=True, disposition='reused_exhausted_failure',
                         first_failure_event=entry['event'], witness_sha256=entry['witness_sha256'],
                         optimizer_calls_executed=0, bindings_after_sha256=event['binding_sha256'],
                         certificate_binding_after=copy.deepcopy(certificate_before),
                         certificate_binding_after_sha256=event.get('certificate_binding_before_sha256'),
                         certificate_after_sha256=event.get('certificate_before_sha256'),
                         seed_certificate_delta=0, cache_eligible=True,
                         route_records_after=copy.deepcopy(routes_before),
                         route_records_after_sha256=_digest(routes_before),
                         route_delta_receipt=receipt, route_delta_receipt_sha256=_digest(receipt))
            raise RuntimeError(ERROR)
        report['executed_requests'] += 1
        event['executed'] = True
        witness = _Witness(seed_producer, metadata)
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
                routes_after = None if route_records is None else _route_snapshot(
                    copy.deepcopy(route_records()), certificate_after)
                certificate_stable = (certificate_stable and routes_before is not None
                    and _canonical(routes_before) == _canonical(routes_after))
                event.update(certificate_binding_after=certificate_after,
                    certificate_binding_after_sha256=None if certificate_after is None else _digest(certificate_after),
                    certificate_after_sha256=None if certificate_after is None else _digest(certificate_after),
                    seed_certificate_delta=0 if certificate_stable else None,
                    external_numeric_seed_evidence_unchanged=certificate_stable,
                    route_records_after=routes_after,
                    route_records_after_sha256=None if routes_after is None else _digest(routes_after))
            except (ValueError, TypeError, AttributeError, RecursionError):
                stable, certificate_stable = False, False
            event.update(disposition='executed_failure', error=_error_record(error),
                         witnessed_exhaustion=eligible, bindings_unchanged=stable,
                         witness=copy.deepcopy(witness.record),
                         optimizer_calls_executed=len(witness.record['optimizers']),
                         final_raise_origin=_origin(error, helper, metadata=metadata),
                         cache_eligible=bool(active is not None and eligible and stable and certificate_stable))
            event['witness_sha256'] = _digest(event['witness'])
            if active is not None and eligible and stable and certificate_stable:
                # Max one entry, replaced only by a fully witnessed exhaustion.
                active['entry'] = dict(key=key, event=event['id'],
                                       witness_sha256=event['witness_sha256'],
                                       certificate_sha256=event['certificate_after_sha256'],
                                       certificate_after=copy.deepcopy(certificate_after),
                                       route_after=copy.deepcopy(routes_after),
                                       association=copy.deepcopy(event.get('early_wrapper_association')))
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
            # Capture the original early-wrapper error BEFORE the first helper
            # request. Stage172's unchanged caller will append its route row
            # only after this wrapper rethrows that same original exception.
            pending = None
            if active is not None and route_records is not None:
                try:
                    captured = dict(arrays={k:_array_descriptor(x) for k,x in zip(
                        ('v','M','J','g'), args[:4])}, scalars={k:_scalar_descriptor(x)
                        for k,x in zip(('dt','mu','tol','maxiter','stop_epoch'),
                                       (*args[4:8], stop_epoch))})
                    pending = dict(inner_call=active['id'], pending_route_index=len(route_records()),
                        original_error=_error_record(error), captured_params=captured,
                        original_error_terminal_origin=original_scalar is not None and _origin(error, original_scalar, metadata=metadata),
                        original_error_binding=copy.deepcopy(report['original_early_error_binding']),
                        original_error_code_sha256=report['original_early_error_binding']['code_sha256'],
                        original_error_terminal_offset=report['original_early_error_binding']['terminal_raise_offset'],
                        original_error_function_id=report['original_early_error_binding']['function_id'],
                        original_error_code_id=report['original_early_error_binding']['code_id'],
                        original_error_file=report['original_early_error_binding']['file'],
                        original_error_function=report['original_early_error_binding']['function'],
                        original_error_returned=False, helper_request_exhausted=False)
                    active['pending_early'] = pending
                except (ValueError, TypeError, AttributeError):
                    active['pending_early'] = None
            try:
                return request(*args, stop_epoch=stop_epoch)
            except (RuntimeError, ValueError, np.linalg.LinAlgError, FloatingPointError) as request_error:
                if pending is not None and 'origin_event' in pending:
                    association = report['events'][pending['origin_event']].get('early_wrapper_association')
                    if association is not None:
                        association['helper_request_exhausted'] = _origin(request_error, helper, metadata=metadata)
                        # Set only in the original wrapper's actual caught-error
                        # return branch, immediately before rethrowing error.
                        association['original_error_returned'] = True
                raise error
            finally:
                if active is not None:
                    active['pending_early'] = None

    def inner(original_portfolio, *args):
        nonlocal active
        # Nested portfolio entries get independent caches and restore parent
        # state. They cannot accidentally share reaction or failure history.
        saved = active
        report['inner_calls'] += 1
        active = dict(id=report['inner_calls'], entry=None, pending_early=None)
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
