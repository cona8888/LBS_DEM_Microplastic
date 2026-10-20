"""Independent bounded Stage229 fixed-pose failure-reuse audit.

No solver, producer module, installed auditor or physical gate is imported or
modified. This audits completed recorded searches and their truthful reuse
references. It is not a proof that every transitive caught exception was
observed, a trajectory qualification, or permission to use the prototype in
production. The unchanged physical/association auditor remains mandatory.
"""
from pathlib import Path
from datetime import datetime
from types import CodeType, FunctionType, SimpleNamespace
import ast
import copy
import dis
import hashlib
import json
import math
import marshal
import struct

ROOT = Path(__file__).resolve().parents[1]
ERROR = 'direct contact residual nonconvergence'
NAME = 'stage229_scope_metadata_guarded_v1'
PHYSICAL_ERRORS = frozenset((ERROR, 'direct contact negative normal force',
    'direct contact cone violation', 'direct contact force closure failed',
    'friction generates energy'))
SEED_SOLVERS = frozenset(('stage172_batched_reduced_near_rest_v1',
                          'stage169_cone_feasible_reduced_modes_v2'))
AUTH = ROOT/'stage229_designs/overnight_20261007/authorization_01.json'
AUTH_SHA256 = '6bee3ee5737d4cd3440d6e4ca13bb03b8fc6ef0f910302aebfc14d9b59b44863'
ROUTE_POLICY = 'stage227_exact_single_failed_early_append_v1'
ROUTE_FIELDS = frozenset(('dt_s', 'gaps_m', 'accepted', 'error', 'wall_s'))


def _authorization(expected_authorization=None):
    raw = AUTH.read_bytes()
    authenticated = hashlib.sha256(raw).hexdigest()
    require(authenticated == AUTH_SHA256, 'frozen Stage229 authorization identity')
    if expected_authorization is not None:
        require(authenticated == expected_authorization, 'caller authorization identity')
    row = json.loads(raw)
    cost = row['cost_screen']
    require(row['stage'] == 'Stage229 bounded overnight numerical verification'
            and row['maximum_nonadvancing_outer_calls'] == cost['maximum_nonadvancing_outer_calls'] == 640
            and cost['maximum_new_trajectory_steps'] == cost['maximum_saved_transport_steps'] == 0
            and row['production_authorized'] is False and row['candidate_production_authorized'] is False
            and cost['production_authorized'] is False and cost['simulation_dispatch'] is False
            and not row['physics_changes'] and not row['physical_gate_changes']
            and not row['route_order_changes'], 'bounded unchanged fixed-pose scientific authorization')
    start = datetime.fromisoformat(row['start_utc']).timestamp()
    stop = datetime.fromisoformat(row['end_utc']).timestamp()
    require(0 < stop-start <= row['maximum_wall_seconds'] == 43200,
            'frozen Stage229 authorization wall cap')
    return start, stop, authenticated


class AuditError(ValueError):
    """The recorded evidence does not establish safe negative-result reuse."""


def require(value, message):
    if not value:
        raise AuditError('Stage229 route-failure-reuse audit: ' + message)


def digest(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise AuditError('Noncanonical witness data') from error
    return hashlib.sha256(raw).hexdigest()


def _code_constant(value):
    """Exact immutable values, independently of object-graph sharing flags."""
    if value is None:
        return {'type': 'none'}
    if type(value) is bool:
        return {'type': 'bool', 'value': value}
    if type(value) is int:
        return {'type': 'int', 'value': str(value)}
    if type(value) is float:
        return {'type': 'float', 'hex_bytes': struct.pack('<d', value).hex()}
    if type(value) is complex:
        return {'type': 'complex', 'hex_bytes': struct.pack('<dd', value.real, value.imag).hex()}
    if type(value) is str:
        return {'type': 'str', 'value': value}
    if type(value) is bytes:
        return {'type': 'bytes', 'hex_bytes': value.hex()}
    if type(value) is tuple:
        return {'type': 'tuple', 'items': [_code_constant(x) for x in value]}
    if type(value) is frozenset:
        items = [_code_constant(x) for x in value]
        items.sort(key=lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False))
        return {'type': 'frozenset', 'items': items}
    if type(value) is CodeType:
        return {'type': 'code', 'value': code_descriptor(value)}
    raise AuditError('Unknown immutable code constant type: ' + type(value).__name__)


def code_descriptor(code):
    """Full recursive immutable Python3.12 code identity; no marshal metadata."""
    require(type(code) is CodeType, 'actual immutable code object descriptor')
    fields = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals',
        'co_stacksize', 'co_flags', 'co_filename', 'co_name', 'co_qualname', 'co_firstlineno')
    result = {name: getattr(code, name) for name in fields}
    for name in ('co_code', 'co_linetable', 'co_exceptiontable'):
        result[name] = getattr(code, name).hex()
    for name in ('co_names', 'co_varnames', 'co_freevars', 'co_cellvars'):
        result[name] = list(getattr(code, name))
    result['co_consts'] = [_code_constant(x) for x in code.co_consts]
    return result


def _sha(value, label):
    require(type(value) is str and len(value) == 64
            and all(c in '0123456789abcdef' for c in value), label + ' SHA256')
    return value


def _integer(value, label, lower=0, upper=None):
    require(type(value) is int and value >= lower
            and (upper is None or value <= upper), label + ' integer bounds')
    return value


def _finite(value, label):
    require(type(value) in (float, int) and math.isfinite(value), label + ' finite scalar')
    return value


def _vector(value, label):
    require(type(value) is list and len(value) == 9, label + ' nine reaction coordinates')
    for x in value:
        _finite(x, label)
    return b''.join(struct.pack('!d', float(x)) for x in value)


def _error(value, label, messages=PHYSICAL_ERRORS):
    require(type(value) is dict and value.get('type') == 'RuntimeError'
            and value.get('message') in messages, label + ' recognized original rejection')
    frames = value.get('frames')
    require(type(frames) is list and bool(frames), label + ' complete traceback origin')
    for frame in frames:
        require(type(frame) is dict and type(frame.get('file')) is str
                and type(frame.get('function')) is str, label + ' frame identity')
        _integer(frame.get('line'), label + ' frame line', 1)
        _integer(frame.get('offset'), label + ' frame offset')
    return frames[-1]


def _original_ast_sha():
    path = ROOT/'stage194_staging/semismooth_rejected_seed_v1.py'
    module = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [node for node in module.body
             if isinstance(node, ast.FunctionDef) and node.name == 'solve']
    require(len(nodes) == 1, 'exact frozen helper function inventory')
    tree = ast.Module(body=nodes, type_ignores=[])
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def _original_scalar_binding():
    """Compile only the existing qualified clone; never import its solver."""
    source_path = ROOT/'stage172_staging/reduced_contact_fast_v1.py'
    text = source_path.read_text(encoding='utf-8')
    parsed = ast.parse(text)
    original = [n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'scalar_solve']
    require(len(original) == 1, 'one original scalar seed algorithm')
    tree = ast.parse(ast.get_source_segment(text, original[0]))
    substituted = brackets = 0
    class ExistingNativeBatch(ast.NodeTransformer):
        def visit_For(self, node):
            nonlocal brackets
            if ast.unparse(node.iter) == 'range(len(samples) - 1)':
                require(ast.unparse(node.body[0].test) ==
                    'not np.isfinite(samples[i:i + 2]).all() or samples[i] * samples[i + 1] >= 0',
                    'unchanged qualified bracket guard')
                node.iter = ast.parse('_bracket_indices(samples)', mode='eval').body
                node.body = node.body[1:]
                brackets += 1
            return self.generic_visit(node)
        def visit_FunctionDef(self, node):
            nonlocal substituted
            if node.name == 'batch':
                positions = [i for i,n in enumerate(node.body)
                             if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'q']
                require(len(positions) == 1, 'one qualified native preparation site')
                node.body[positions[0]:] = ast.parse(
                    'return _batch_body(beta,q0,direction,J,stick,mu,vs,v,B,fs)').body
                substituted += 1
            return self.generic_visit(node)
    ExistingNativeBatch().visit(tree)
    require((substituted, brackets) == (1,1), 'exact existing native scalar substitutions')
    ast.fix_missing_locations(tree)
    filename = str(ROOT/'stage199_staging/native_batch_candidate_v1.py') + '::same_scan_native_batch'
    compiled = compile(tree, filename, 'exec')
    code = next(x for x in compiled.co_consts if isinstance(x, type(compiled)) and x.co_name == 'scalar_solve')
    instructions = list(dis.get_instructions(code))
    terminal = []
    for index, instruction in enumerate(instructions):
        tail = instructions[max(0,index-4):index]
        if instruction.opname == 'RAISE_VARARGS' and instruction.arg == 1 and any(
            x.opname == 'LOAD_GLOBAL' and x.argval == 'RuntimeError' for x in tail) and any(
            x.opname == 'LOAD_CONST' and x.argval == ERROR for x in tail):
            terminal.append(instruction)
    require(len(terminal) == 1 and terminal[0].positions.end_lineno
            == max(x.positions.end_lineno or 0 for x in instructions),
            'independently reconstructed original scalar terminal raise')
    descriptor = code_descriptor(code)
    return dict(function='scalar_solve', file=filename,
                terminal_raise_offset=terminal[0].offset,
                code_sha256=hashlib.sha256(marshal.dumps(code)).hexdigest(),
                code_descriptor=descriptor, code_descriptor_sha256=digest(descriptor))


def _key_evidence(event, stop):
    """Authenticate exact serialized operand and runtime-binding descriptors."""
    descriptor = event.get('key_descriptor')
    require(type(descriptor) is dict and event.get('key_descriptor_sha256') == digest(descriptor),
            'independent complete input-descriptor digest')
    require(type(event.get('binding_descriptor')) is list
            and digest(event['binding_descriptor']) == event['binding_sha256']
            == descriptor.get('binding_sha256'), 'independent actual binding descriptor digest')
    arrays = descriptor.get('arrays')
    shapes = dict(v=[6], M=[6, 6], J=[9, 6], g=[3])
    require(type(arrays) is dict and set(arrays) == set(shapes), 'all four original ordered operands')
    for name, shape in shapes.items():
        row = arrays[name]
        require(type(row) is dict and row.get('shape') == shape and row.get('dtype') == '<f8',
                'native float64 original operand shape: ' + name)
        strides = row.get('strides')
        require(type(strides) is list and len(strides) == len(shape)
                and all(type(x) is int for x in strides), 'exact original operand strides: ' + name)
        require(type(row.get('c_contiguous')) is bool and type(row.get('f_contiguous')) is bool,
                'explicit original operand layout: ' + name)
        text = row.get('hex_bytes')
        size = math.prod(shape)
        require(type(text) is str and len(text) == 16*size
                and all(c in '0123456789abcdef' for c in text), 'complete original operand bytes: ' + name)
        values = struct.unpack('<' + 'd'*size, bytes.fromhex(text))
        require(all(math.isfinite(x) for x in values), 'finite original operand bytes: ' + name)
    scalars = descriptor.get('scalars')
    require(type(scalars) is dict and set(scalars) == {'dt', 'mu', 'tol', 'maxiter', 'stop_epoch'},
            'all five original scalar controls')
    decoded = {}
    for name, row in scalars.items():
        require(type(row) is dict and row.get('type') in
                ('builtins.float', 'builtins.int', 'numpy.float64', 'numpy.int64'),
                'qualified scalar type: ' + name)
        text = row.get('hex_bytes')
        require(type(text) is str and len(text) == 16
                and all(c in '0123456789abcdef' for c in text), 'exact scalar bytes: ' + name)
        dtype = row.get('dtype')
        require(dtype in ('<f8', '<i8'), 'qualified scalar dtype: ' + name)
        decoded[name] = struct.unpack('<d' if dtype == '<f8' else '<q', bytes.fromhex(text))[0]
        require(math.isfinite(decoded[name]), 'finite scalar bytes: ' + name)
    require(decoded['dt'] > 0 and decoded['mu'] > 0 and decoded['tol'] == 1e-10
            and decoded['maxiter'] == 25000 and decoded['stop_epoch'] == stop,
            'unchanged positive physical and original scalar controls')
    return descriptor


def _witness(event, structure):
    """Recheck eligibility from evidence, without trusting its Boolean alone."""
    witness = event.get('witness')
    require(type(witness) is dict, 'executed failure witness exists')
    require(event.get('witness_sha256') == digest(witness), 'executed witness exact digest')
    require(witness.get('terminal_reached') is True
            and witness.get('all_ordered_attempted') is True, 'finished exhaustive-search proof')
    require(event.get('final_raise_origin') is True, 'helper terminal raise authentication')
    require(witness.get('seed_trace_complete') is True
            and not witness.get('preexisting_seed_trace'), 'complete unobstructed observed Python seed call tree')
    internal = witness.get('seed_internal_exceptions')
    require(type(internal) is list, 'observed seed exception inventory')
    for error in internal:
        require(type(error) is dict and error.get('type') == 'RuntimeError'
                and error.get('message') in PHYSICAL_ERRORS
                and error.get('physical_rejection') is True, 'only observed original physical seed rejections')
        require(type(error.get('file')) is str and type(error.get('function')) is str,
                'observed seed exception source identity')
        _integer(error.get('line'), 'observed seed exception line', 1)
        _integer(error.get('offset'), 'observed seed exception offset')
    last = _error(event.get('error'), 'helper exhaustion', frozenset((ERROR,)))
    require(last['function'] == 'solve'
            and last['file'].endswith('failure_reuse_v1.py::observer_only_semismooth'),
            'actual observer helper terminal frame')
    require(last['offset'] == structure['terminal_raise_offset'], 'exact helper terminal raise offset')

    producer = witness.get('producer')
    require(type(producer) is dict, 'seed-producer completion evidence')
    swallowed = witness.get('swallowed_errors')
    require(type(swallowed) is list, 'complete observed swallowed-error inventory')
    if producer.get('outcome') == 'exhausted':
        require(producer.get('terminal_origin') is True, 'seed producer terminal origin')
        last_seed = _error(producer.get('error'), 'seed-producer exhaustion', frozenset((ERROR,)))
        require(last_seed['function'] == 'scalar_solve', 'bounded scalar search exhaustion origin')
        require(swallowed == [producer], 'only recorded completed producer exhaustion swallowed')
    else:
        require(producer.get('outcome') == 'success' and producer.get('finite') is True,
                'finite completed seed producer')
        require(not swallowed, 'successful seed producer has no swallowed failure')

    rejected_seeds = witness.get('seed_gate_rejections')
    require(type(rejected_seeds) is list, 'seed gate rejection inventory')
    for seed in rejected_seeds:
        require(type(seed) is dict and seed.get('finite') is True, 'finite rejected seed')
        _vector(seed.get('force'), 'rejected seed')
        require(seed.get('solver') in SEED_SOLVERS, 'qualified seed producer method')
        _error(seed.get('error'), 'seed physical gate')
    count = _integer(witness.get('seed_candidate_count'), 'finite seed candidate count', 1, 64)
    require(count == len(rejected_seeds) + (producer.get('outcome') == 'success'),
            'complete producer seed accounting')
    ordered = witness.get('ordered')
    require(type(ordered) is list and len(ordered) == min(8, count),
            'complete bounded ordered seed list')
    source_indices = []
    order_pairs = []
    for seed in ordered:
        require(type(seed) is dict and seed.get('finite') is True, 'finite ordered seed')
        source = _integer(seed.get('source_index'), 'ordered seed source', 0, count-1)
        require(source not in source_indices, 'unique original seed source')
        source_indices.append(source)
        _vector(seed.get('force'), 'ordered seed')
        residual = _finite(seed.get('residual'), 'ordered seed residual')
        require(residual >= 0, 'nonnegative seed residual')
        require(seed.get('solver') in SEED_SOLVERS, 'ordered seed producer method')
        require(seed.get('error') is None or seed['error'] in PHYSICAL_ERRORS,
                'ordered seed original rejection')
        order_pairs.append((residual, source))
        if source < len(rejected_seeds):
            origin = rejected_seeds[source]
            require(_vector(seed['force'], 'ordered seed') == _vector(origin['force'], 'source seed')
                    and seed['solver'] == origin['solver']
                    and seed['error'] == origin['error']['message'], 'exact captured seed association')
        else:
            require(producer.get('outcome') == 'success' and seed['error'] is None,
                    'success seed association')
    require(order_pairs == sorted(order_pairs), 'unchanged residual/index ordering')

    optimizers = witness.get('optimizers')
    finalizers = witness.get('finalizer_rejections')
    require(type(optimizers) is list and type(finalizers) is list
            and len(optimizers) == len(finalizers) == len(ordered), 'all ordered searches completed and rejected')
    for index, (opt, finalizer, seed) in enumerate(zip(optimizers, finalizers, ordered)):
        require(type(opt) is dict and opt.get('index') == index
                and opt.get('source_index') == seed['source_index'], 'optimizer ordered seed provenance')
        require(opt.get('completed') is True and opt.get('finite') is True,
                'optimizer returned finite completed result')
        _integer(opt.get('nfev'), 'executed optimizer nfev', 1, 2000)
        if opt.get('njev') is not None:
            _integer(opt['njev'], 'executed optimizer njev', 1, opt['nfev'])
        status = _integer(opt.get('status'), 'optimizer completed status', 0, 4)
        require(type(opt.get('success')) is bool and opt['success'] == (status > 0),
                'optimizer status and success consistency')
        _sha(opt.get('result_sha256'), 'optimizer returned result')
        require(type(finalizer) is dict and finalizer.get('index') == index,
                'one original finalizer rejection per completed candidate')
        _error(finalizer.get('error'), 'final candidate physical rejection')
    require(event.get('optimizer_calls_executed') == len(optimizers), 'executed optimizer count truth')
    require(event.get('seed_certificate_delta') == 0, 'no seed certificate emitted by cached failure')
    require(event.get('certificate_before_sha256') == event.get('certificate_after_sha256'),
            'unchanged external seed-certificate binding')
    _sha(event.get('certificate_before_sha256'), 'seed certificate before')
    _sha(event.get('certificate_after_sha256'), 'seed certificate after')
    require(digest(event.get('certificate_binding_before')) == event['certificate_before_sha256']
            and digest(event.get('certificate_binding_after')) == event['certificate_after_sha256'],
            'independent external seed-certificate descriptor digests')
    return witness


def _route_snapshot(event, when):
    certificates = event.get('certificate_binding_' + when)
    require(type(certificates) is dict and set(certificates) == {
        'roundoff', 'fast_attempts', 'fast_telemetry', 'reduced', 'fallback',
        'model_calls', 'sweep', 'stage119'}, 'complete external evidence-channel inventory')
    for name, marker in certificates.items():
        require(type(marker) is dict and set(marker) == {'count', 'sha256'},
                'exact count/content evidence marker: ' + name)
        _integer(marker['count'], 'external evidence count: ' + name)
        _sha(marker['sha256'], 'external evidence content: ' + name)
    records = event.get('route_records_' + when)
    require(type(records) is list, 'complete retained original route snapshot: ' + when)
    require(event.get('route_records_' + when + '_sha256') == digest(records)
            == certificates['fast_attempts']['sha256']
            and len(records) == certificates['fast_attempts']['count'],
            'independent full route/channel association: ' + when)
    require(event.get('certificate_' + when + '_sha256') == digest(certificates),
            'independent complete evidence inventory digest: ' + when)
    return records, certificates


def _route_receipt(origin, hit, original_binding):
    """Prove the changed channel instead of excluding any original record."""
    before, old_certificates = _route_snapshot(origin, 'after')
    after, current_certificates = _route_snapshot(hit, 'before')
    ending, ending_certificates = _route_snapshot(hit, 'after')
    require(digest(ending) == digest(after)
            and digest(ending_certificates) == digest(current_certificates),
            'hit performs no evidence emission or route mutation')
    receipt = hit.get('route_delta_receipt')
    require(type(receipt) is dict
            and hit.get('route_delta_receipt_sha256') == digest(receipt)
            and receipt.get('policy') == ROUTE_POLICY
            and receipt.get('inner_call') == origin['inner_call'] == hit['inner_call']
            and receipt.get('numerical_channels_unchanged') is True
            and receipt.get('all_original_records_retained') is True,
            'explicit independently associated route receipt')
    require(receipt.get('before_records_sha256') == digest(before)
            and receipt.get('after_records_sha256') == digest(after),
            'receipt authenticates actual complete retained snapshots')
    require(all(digest(old_certificates[k]) == digest(current_certificates[k])
                for k in old_certificates if k != 'fast_attempts'),
            'every other numerical evidence channel remains exact')
    if receipt.get('kind') == 'unchanged_full_evidence':
        require(digest(old_certificates) == digest(current_certificates)
                and digest(before) == digest(after), 'original unchanged-full-evidence gate')
        require(set(receipt) == {'policy', 'kind', 'inner_call',
            'numerical_channels_unchanged', 'before_records_sha256',
            'after_records_sha256', 'all_original_records_retained'},
            'no invented delta in unchanged-evidence receipt')
        return False
    require(receipt.get('kind') == 'failed_early_append',
            'only declared narrow append receipt')
    require(len(after) == len(before)+1 and digest(after[:-1]) == digest(before),
            'exactly one appended row and bit-exact existing prefix')
    association = origin.get('early_wrapper_association')
    require(type(association) is dict and association.get('inner_call') == hit['inner_call']
            and association.get('origin_event') == origin['id']
            and association.get('pending_route_index') == len(before),
            'one actual pending original early wrapper in this inner call')
    require(digest(association.get('operands')) == digest(origin['key_descriptor'])
            == digest(hit['key_descriptor']), 'original early error exact operand/key association')
    require(digest(association.get('captured_params')) == digest({
        'arrays':origin['key_descriptor']['arrays'], 'scalars':origin['key_descriptor']['scalars']}),
        'independent original early operand capture')
    require(association.get('original_error_terminal_origin') is True
            and association.get('original_error_returned') is True
            and association.get('helper_request_exhausted') is True,
            'authenticated original early terminal failure actually rethrown')
    original = _error(association.get('original_error'), 'original early wrapper exhaustion',
                      frozenset((ERROR,)))
    require(original['function'] == 'scalar_solve'
            and original['file'].replace('\\', '/').endswith(
                '/stage199_staging/native_batch_candidate_v1.py::same_scan_native_batch'),
            'qualified original native scalar clone terminal source')
    early_binding = association.get('original_error_binding')
    require(type(early_binding) is dict and digest(early_binding) == digest(original_binding),
            'same externally recorded original early producer binding')
    expected_binding = _original_scalar_binding()
    _sha(early_binding.get('code_sha256'), 'recorded original raw marshal diagnostic')
    require(early_binding.get('code_descriptor_sha256') == digest(early_binding.get('code_descriptor')),
            'independent canonical immutable code descriptor digest')
    require(all(early_binding.get(k) == v for k,v in expected_binding.items() if k != 'code_sha256'),
            'independent original scalar clone code/source/terminal fingerprint')
    terminal = _integer(early_binding.get('terminal_raise_offset'), 'original scalar terminal instruction')
    require(original['offset'] == terminal, 'original producer exact terminal instruction')
    function_id = _integer(early_binding.get('function_id'), 'original scalar function binding', 1)
    code_id = _integer(early_binding.get('code_id'), 'original scalar code binding', 1)
    code_pairs = set()
    def bound_pairs(value):
        if type(value) is list:
            if len(value) >= 3 and value[0] == 'function' and type(value[1]) is int and type(value[2]) is int:
                code_pairs.add((value[1], value[2]))
            for child in value:
                bound_pairs(child)
        elif type(value) is dict:
            for child in value.values():
                bound_pairs(child)
    bound_pairs(origin['binding_descriptor'])
    require((function_id, code_id) in code_pairs, 'original error producer appears in actual live first-request bindings')
    row = after[-1]
    require(type(row) is dict and set(row) == ROUTE_FIELDS
            and row.get('accepted') is False and row.get('error') == association['original_error']['message'],
            'exact failed early-route schema with no physical result or certificate')
    dt = _finite(row.get('dt_s'), 'retained failed route dt')
    require(type(dt) is float and struct.pack('<d', dt).hex()
            == hit['key_descriptor']['scalars']['dt']['hex_bytes'], 'bit-exact failed-route dt')
    gaps = row.get('gaps_m')
    require(type(gaps) is list and len(gaps) == 3, 'all three retained signed gaps')
    for value in gaps:
        _finite(value, 'retained signed gap')
    require(b''.join(struct.pack('<d', float(x)) for x in gaps).hex()
            == hit['key_descriptor']['arrays']['g']['hex_bytes'], 'bit-exact failed-route signed gaps')
    wall = _finite(row.get('wall_s'), 'actual retained failed route duration')
    require(type(wall) is float and wall >= 0, 'finite original elapsed route duration')
    require(receipt.get('appended_index') == len(before)
            and digest(receipt.get('appended_row')) == digest(row)
            and receipt.get('appended_row_sha256') == digest(row)
            and receipt.get('association_sha256') == digest(association),
            'exact appended row and original exception association receipt')
    return True


def audit(log, expected_binding=None, expected_deadline=None, expected_authorization=None):
    """Audit recorded negative-result reuse; return a compact evidence summary.

    ``expected_binding`` optionally fixes the externally authenticated runtime
    binding digest. Historical timestamps are checked against the frozen work
    deadline; this function never changes the recorded deadline or reads a live
    clock to reinterpret old evidence.
    """
    start_epoch, authorized_stop, authorization_sha = _authorization(expected_authorization)
    require(type(log) is dict and log.get('name') == NAME, 'exact prototype log identity')
    require(log.get('route_delta_policy') == ROUTE_POLICY, 'explicit prospective Stage227 evidence policy')
    require(log.get('production_authorized') is False and log.get('new_trajectory_steps') == 0,
            'bounded nonadvancing development claim')
    require(log.get('enabled') is True and type(log.get('reuse_enabled')) is bool,
            'explicit observed baseline/reuse mode')
    require(log.get('cache_retained') is False, 'cache discarded at scope exit')
    stop = _finite(log.get('stop_epoch'), 'frozen work deadline')
    require(stop == authorized_stop, 'only the frozen Stage229 authorization deadline')
    if expected_deadline is not None:
        require(stop == expected_deadline, 'externally authenticated deadline')
    if expected_binding is not None:
        _sha(expected_binding, 'externally authenticated binding')
    structure = log.get('ast')
    require(type(structure) is dict and structure.get('stripped_ast_exact') is True
            and structure.get('equations_changed') is False, 'observer-only equation body')
    require(structure.get('original_ast_sha256') == _original_ast_sha(), 'independent original AST identity')
    _integer(structure.get('observer_hooks'), 'observer hooks', 1)
    _integer(structure.get('terminal_raise_offset'), 'helper terminal offset')
    _sha(structure.get('helper_code_sha256'), 'observed helper code')

    events = log.get('events')
    require(type(events) is list, 'complete logical request inventory')
    logical = _integer(log.get('logical_requests'), 'logical request count')
    executed = _integer(log.get('executed_requests'), 'executed request count')
    reused = _integer(log.get('reused_requests'), 'reused request count')
    inner_calls = _integer(log.get('inner_calls'), 'fresh inner-call count')
    require(log.get('cache_clears') == inner_calls, 'every inner cache discarded in finally')
    require(len(events) == logical == executed+reused, 'logical/executed/reused exact accounting')
    if not log['reuse_enabled']:
        require(reused == 0, 'observed baseline never reuses a failed search')
    seen_executed = seen_reused = safe_failures = associated_appends = 0
    newest_eligible = {}
    checked_previous = None
    for index, event in enumerate(events):
        require(type(event) is dict and event.get('id') == index
                and event.get('logical_request') == index+1, 'sequential logical request identifiers')
        token = _integer(event.get('inner_call'), 'fresh inner-call token', 1, inner_calls)
        checked = _finite(event.get('checked_epoch'), 'fresh request cutoff check')
        entry_checked = _finite(event.get('entry_checked_epoch'), 'fresh entry cutoff check')
        require(event.get('stop_epoch') == stop and 0 < checked < stop,
                'unconditional fresh cutoff check before request')
        require(start_epoch <= entry_checked <= checked, 'authorized fresh entry then post-fingerprint cutoff checks')
        require(event.get('helper_code_sha256') == structure['helper_code_sha256']
                and event.get('helper_terminal_offset') == structure['terminal_raise_offset'],
                'actual helper code and terminal instruction binding')
        require(checked_previous is None or checked >= checked_previous, 'ordered request clock evidence')
        checked_previous = checked
        require(type(event.get('executed')) is bool and type(event.get('reused')) is bool
                and event['executed'] != event['reused'], 'one truthful execution/reuse disposition')
        require(type(event.get('keyable')) is bool, 'explicit exact-key eligibility')
        if event['keyable']:
            key = _sha(event.get('key_sha256'), 'exact complete input key')
            binding = _sha(event.get('binding_sha256'), 'actual runtime binding')
            if expected_binding is not None:
                require(binding == expected_binding, 'expected actual binding at every request')
            if 'key_repr' in event:
                require(type(event['key_repr']) is str
                        and hashlib.sha256(event['key_repr'].encode()).hexdigest() == key,
                        'independently rehashed exact-key representation')
            _key_evidence(event, stop)
        else:
            require(not event.get('cache_eligible') and not event['reused'],
                    'unkeyable requests remain safe misses')
            key = binding = None
        _integer(event.get('optimizer_calls_executed'), 'actual request optimizer count')
        if event['reused']:
            seen_reused += 1
            require(log['reuse_enabled'] and event['keyable']
                    and event.get('disposition') == 'reused_exhausted_failure', 'allowed reuse request')
            first = _integer(event.get('first_failure_event'), 'first executed failure reference', 0, index-1)
            origin = events[first]
            require(origin['executed'] and not origin['reused']
                    and origin.get('witnessed_exhaustion') is True
                    and origin.get('cache_eligible') is True, 'reference to actual executed completed eligible failure')
            require(origin['inner_call'] == token and newest_eligible.get(token) == first,
                    'one-entry cache belongs to this exact inner call')
            require(origin.get('key_sha256') == key and origin.get('binding_sha256') == binding,
                    'same input bytes/layout/controls and actual runtime bindings')
            require(origin['key_descriptor'] == event['key_descriptor']
                    and origin['binding_descriptor'] == event['binding_descriptor'],
                    'independently compared full input and live binding descriptors')
            require(event.get('witness_sha256') == origin.get('witness_sha256'), 'first witness exact reference')
            require(event['optimizer_calls_executed'] == event['seed_certificate_delta'] == 0,
                    'reuse performs no optimizer or seed certificate work')
            require('witness' not in event and not event.get('seed_certificates'),
                    'no invented second search or duplicated seed certificate')
            require(event.get('certificate_before_sha256') == event.get('certificate_after_sha256'),
                    'hit emits no new numerical certificate evidence')
            _sha(event.get('certificate_before_sha256'), 'reused certificate binding')
            require(digest(event.get('certificate_binding_before')) == event['certificate_before_sha256']
                    and digest(event.get('certificate_binding_after')) == event['certificate_after_sha256'],
                    'independent unchanged certificate descriptor digests on hit')
            require(event.get('cache_eligible') is True, 'explicit certified hit eligibility')
            associated_appends += _route_receipt(origin, event, log.get('original_early_error_binding'))
            continue
        seen_executed += 1
        require(event.get('disposition') in ('executed_failure', 'executed_success'), 'executed request outcome')
        require(type(event.get('witnessed_exhaustion')) is bool, 'explicit executed exhaustion outcome')
        witness = event.get('witness')
        require(type(witness) is dict and type(witness.get('optimizers')) is list,
                'actual executed optimizer witness')
        require(event['optimizer_calls_executed'] == len(witness['optimizers']), 'actual executed optimizer inventory')
        require('first_failure_event' not in event, 'executed request is not an invented reference')
        if event.get('cache_eligible') is True:
            require(event['keyable'] and event.get('disposition') == 'executed_failure'
                    and event.get('witnessed_exhaustion') is True
                    and event.get('bindings_unchanged') is True, 'cacheable executed failure identity')
            require(event.get('bindings_after_sha256') == binding, 'runtime bindings remain unchanged')
            _witness(event, structure)
            before_records, before_certificates = _route_snapshot(event, 'before')
            after_records, after_certificates = _route_snapshot(event, 'after')
            require(digest(before_records) == digest(after_records)
                    and digest(before_certificates) == digest(after_certificates),
                    'executed exhaustion emits no record or numerical evidence')
            newest_eligible[token] = index
            safe_failures += 1
        elif event.get('disposition') == 'executed_failure':
            require(event.get('witness_sha256') == digest(witness), 'uncertain failure retained exactly')
    require(seen_executed == executed and seen_reused == reused, 'all execution counters authenticated')
    return dict(passed=True, logical_requests=logical, executed_requests=executed,
                reused_requests=reused, witnessed_exhaustions=safe_failures,
                inner_calls=inner_calls, new_trajectory_steps=0,
                associated_single_failed_route_appends=associated_appends,
                authorization_sha256=authorization_sha,
                original_equation_ast_verified=True, physical_audit_replaced=False,
                claim='Recorded bounded negative witnesses and independently associated retained failed-route appends only. Observed Python seed exceptions; native errors only when propagated to Python. No physical, restart, trajectory or production qualification.')


def mutation_checks(log, expected_binding=None, expected_deadline=None, expected_authorization=None):
    """Falsify meaningful corruption controls against a genuine passing hit."""
    audit(log, expected_binding, expected_deadline, expected_authorization)
    hits = [i for i, event in enumerate(log['events']) if event['reused']]
    require(bool(hits), 'mutation fixture contains an actual reuse reference')
    hit_index = hits[0]
    first_index = log['events'][hit_index]['first_failure_event']
    mutations = []
    def change(name, edit):
        candidate = copy.deepcopy(log)
        edit(candidate, candidate['events'][first_index], candidate['events'][hit_index])
        try:
            audit(candidate, expected_binding, expected_deadline, expected_authorization)
        except AuditError:
            mutations.append(dict(test=name, rejected=True))
        else:
            raise AuditError('Corrupted evidence accepted: ' + name)
    def refreshed(first):
        first['witness_sha256'] = digest(first['witness'])
    def unfinished(_log, first, hit):
        first['witness']['terminal_reached'] = False
        refreshed(first)
        hit['witness_sha256'] = first['witness_sha256']
    change('unfinished_search_even_with_rehashed_witness', unfinished)
    change('changed_input_key', lambda _l, _f, h: h.update(key_sha256='0'*64))
    change('changed_runtime_binding', lambda _l, _f, h: h.update(binding_sha256='0'*64))
    change('changed_inner_token', lambda l, _f, h: (l.update(inner_calls=l['inner_calls']+1), h.update(inner_call=l['inner_calls'])))
    change('changed_request_deadline', lambda _l, _f, h: h.update(stop_epoch=h['stop_epoch']+1))
    change('stale_cutoff_check', lambda _l, _f, h: h.update(checked_epoch=h['stop_epoch']))
    change('forged_executed_optimizer_count_on_hit', lambda _l, _f, h: h.update(optimizer_calls_executed=1))
    change('missing_first_witness_reference', lambda _l, _f, h: h.pop('first_failure_event'))
    change('duplicate_seed_certificate_work', lambda _l, _f, h: h.update(seed_certificate_delta=1))
    change('duplicated_seed_certificate_evidence', lambda _l, _f, h: h.update(seed_certificates=[{'fabricated':True}]))
    change('changed_external_certificate_binding', lambda _l, _f, h: h.update(certificate_after_sha256='0'*64))
    change('forged_execution_counters', lambda l, _f, _h: l.update(executed_requests=l['executed_requests']+1))
    def incomplete(_l, first, hit):
        first['witness']['optimizers'][-1]['completed'] = False
        refreshed(first)
        hit['witness_sha256'] = first['witness_sha256']
    change('incomplete_optimizer_even_with_rehashed_witness', incomplete)
    def bad_finalizer(_l, first, hit):
        first['witness']['finalizer_rejections'][-1]['error']['message'] = 'diagnostic work cutoff reached'
        refreshed(first)
        hit['witness_sha256'] = first['witness_sha256']
    change('cutoff_disguised_as_physical_rejection', bad_finalizer)
    change('terminal_origin_not_authenticated', lambda _l, f, _h: f.update(final_raise_origin=False))

    require(log['events'][hit_index].get('route_delta_receipt', {}).get('kind')
            == 'failed_early_append', 'genuine fixture exercises narrow append policy')

    def refresh_route(event, when):
        records = event['route_records_' + when]
        certificates = event['certificate_binding_' + when]
        certificates['fast_attempts'] = dict(count=len(records), sha256=digest(records))
        event['route_records_' + when + '_sha256'] = digest(records)
        event['certificate_' + when + '_sha256'] = digest(certificates)
        event['certificate_binding_' + when + '_sha256'] = digest(certificates)

    def refresh_receipt(first, hit):
        receipt = hit['route_delta_receipt']
        receipt['before_records_sha256'] = digest(first['route_records_after'])
        receipt['after_records_sha256'] = digest(hit['route_records_before'])
        receipt['association_sha256'] = digest(first['early_wrapper_association'])
        receipt['appended_index'] = len(first['route_records_after'])
        receipt['appended_row'] = copy.deepcopy(hit['route_records_before'][-1])
        receipt['appended_row_sha256'] = digest(receipt['appended_row'])
        hit['route_delta_receipt_sha256'] = digest(receipt)

    def altered_row(field, value):
        def edit(_l, first, hit):
            hit['route_records_before'][-1][field] = value
            hit['route_records_after'] = copy.deepcopy(hit['route_records_before'])
            refresh_route(hit, 'before'); refresh_route(hit, 'after')
            refresh_receipt(first, hit)
        return edit

    change('append_accepted_even_with_rehashed_channel', altered_row('accepted', True))
    change('append_health_even_with_rehashed_channel', altered_row('health', {'residual': 0.0}))
    change('append_force_even_with_rehashed_channel', altered_row('force', [0.0]*9))
    old_dt = log['events'][hit_index]['route_records_before'][-1]['dt_s']
    change('append_one_bit_dt_even_with_rehashed_channel', altered_row('dt_s', math.nextafter(old_dt, math.inf)))
    old_gaps = copy.deepcopy(log['events'][hit_index]['route_records_before'][-1]['gaps_m'])
    old_gaps[0] = math.nextafter(old_gaps[0], math.inf)
    change('append_one_bit_signed_gap_even_with_rehashed_channel', altered_row('gaps_m', old_gaps))
    change('append_error_even_with_rehashed_channel', altered_row('error', 'diagnostic work cutoff reached'))

    def extra_append(_l, first, hit):
        hit['route_records_before'].append(copy.deepcopy(hit['route_records_before'][-1]))
        hit['route_records_after'] = copy.deepcopy(hit['route_records_before'])
        refresh_route(hit, 'before'); refresh_route(hit, 'after'); refresh_receipt(first, hit)
    change('extra_append_even_with_rehashed_channel', extra_append)

    def wrong_association(_l, first, hit):
        first['early_wrapper_association']['pending_route_index'] += 1
        refresh_receipt(first, hit)
    change('wrong_pending_append_association_even_with_rehashed_receipt', wrong_association)

    def unreturned_error(_l, first, hit):
        first['early_wrapper_association']['original_error_returned'] = False
        refresh_receipt(first, hit)
    change('original_wrapper_error_not_actually_returned', unreturned_error)

    def original_origin(_l, first, hit):
        first['early_wrapper_association']['original_error_terminal_origin'] = False
        refresh_receipt(first, hit)
    change('original_wrapper_terminal_origin_uncertain', original_origin)

    def helper_not_exhausted(_l, first, hit):
        first['early_wrapper_association']['helper_request_exhausted'] = False
        refresh_receipt(first, hit)
    change('early_wrapper_did_not_receive_completed_helper_exhaustion', helper_not_exhausted)

    def altered_original_code(l, first, hit):
        binding = first['early_wrapper_association']['original_error_binding']
        binding['code_descriptor']['co_flags'] ^= 1
        binding['code_descriptor_sha256'] = digest(binding['code_descriptor'])
        l['original_early_error_binding'] = copy.deepcopy(binding)
        refresh_receipt(first, hit)
    change('changed_original_producer_code_even_with_matching_declared_binding', altered_original_code)

    def altered_error_association(_l, first, hit):
        first['early_wrapper_association']['captured_params']['scalars']['dt']['hex_bytes'] = '0'*16
        refresh_receipt(first, hit)
    change('original_error_has_different_captured_operands', altered_error_association)

    def unfinished_seed_trace(_l, first, hit):
        first['witness']['seed_trace_complete'] = False
        refreshed(first)
        hit['witness_sha256'] = first['witness_sha256']
    change('incomplete_seed_exception_trace_even_with_rehashed_witness', unfinished_seed_trace)

    def swallowed_nonphysical(_l, first, hit):
        error = copy.deepcopy(first['error']['frames'][-1])
        error.update(type='LinAlgError', message='singular numerical seed system', physical_rejection=False)
        first['witness']['seed_internal_exceptions'].append(error)
        refreshed(first)
        hit['witness_sha256'] = first['witness_sha256']
    change('swallowed_nonphysical_seed_exception_even_with_rehashed_witness', swallowed_nonphysical)

    def other_certificate(_l, first, hit):
        for when in ('before', 'after'):
            certificate = hit['certificate_binding_' + when]['roundoff']
            certificate['count'] += 1
            certificate['sha256'] = digest(['invented_numeric_certificate'])
            refresh_route(hit, when)
        refresh_receipt(first, hit)
    change('other_numeric_certificate_changed_even_with_rehashed_inventory', other_certificate)

    # A first-pose fixture naturally has no earlier route rows. Build an
    # explicit synthetic prefix stress fixture from the genuine append log;
    # it establishes no extra physical result. Then corrupt an existing row
    # while rehashing every affected marker, so only prefix preservation
    # rejects it rather than an incidental stale hash.
    prefix_fixture = copy.deepcopy(log)
    prefix_row = copy.deepcopy(prefix_fixture['events'][hit_index]['route_records_before'][-1])
    for event in prefix_fixture['events']:
        if event.get('early_wrapper_association') is not None:
            event['early_wrapper_association']['pending_route_index'] += 1
        for when in ('before', 'after'):
            if event.get('route_records_' + when) is not None:
                event['route_records_' + when].insert(0, copy.deepcopy(prefix_row))
                refresh_route(event, when)
    for event in prefix_fixture['events']:
        if event.get('reused'):
            refresh_receipt(prefix_fixture['events'][event['first_failure_event']], event)
    audit(prefix_fixture, expected_binding, expected_deadline, expected_authorization)
    prefix_hit = prefix_fixture['events'][hit_index]
    prefix_first = prefix_fixture['events'][first_index]
    for when in ('before', 'after'):
        prefix_hit['route_records_' + when][0]['wall_s'] = math.nextafter(prefix_row['wall_s'], math.inf)
        refresh_route(prefix_hit, when)
    refresh_receipt(prefix_first, prefix_hit)
    try:
        audit(prefix_fixture, expected_binding, expected_deadline, expected_authorization)
    except AuditError:
        mutations.append(dict(test='altered_existing_prefix_even_with_rehashed_inventory', rejected=True,
                              fixture='Explicit synthetic prefix on genuine observed append log'))
    else:
        raise AuditError('Corrupted existing prefix accepted')
    return dict(passed=True, mutation_controls=mutations, controls_rejected=len(mutations),
                fixture_had_actual_reuse=True, fixture_had_actual_associated_append=True,
                synthetic_prefix_control_explicit=True, new_trajectory_steps=0)


def _base_live_binding_controls(candidate, fingerprint=None, cutoff=None, strict=True):
    """Mutate isolated live fixtures; never call a force solver or optimizer.

    The optional fingerprint adapter must retain the actual candidate metadata
    cache between calls. Its source is frozen by the caller's replay design.
    ``strict=False`` preserves an inherited guard defect as negative evidence;
    it does not qualify the candidate. Mutable closure contents are tested
    independently of cell rebinding. Only fixture functions and arrays change.
    """
    require(type(strict) is bool, 'explicit live-control strictness')
    key = fingerprint if fingerprint is not None else candidate._callable_key
    np = candidate.np
    controls = []

    def fixture(source, **dependencies):
        namespace = dict(dependencies)
        exec(compile(source, '<stage228_live_binding_control>', 'exec'), namespace)
        return namespace, namespace['probe']

    def changed(name, function, edit):
        try:
            before = key(function)
            edit()
            after = key(function)
        except (ValueError, TypeError, RuntimeError) as error:
            controls.append(dict(test=name, passed=True, safe_miss=True,
                                 error_type=type(error).__name__))
        else:
            controls.append(dict(test=name, passed=(before != after), safe_miss=False))

    ns, probe = fixture('def probe(x=1.0):\n    return x\n')
    _, replacement = fixture('def probe(x=1.0):\n    return x\n')
    controls.append(dict(test='changed_function_object', passed=key(probe) != key(replacement)))
    _, replacement_code = fixture('def probe(x=1.0):\n    return x + 1.0\n')
    changed('changed_code_on_same_function', probe,
            lambda: setattr(probe, '__code__', replacement_code.__code__))

    ns, probe = fixture('def probe(x=1.0):\n    return x\n')
    changed('changed_default_value', probe,
            lambda: setattr(probe, '__defaults__', (math.nextafter(1.0, math.inf),)))
    ns, probe = fixture('def probe(*, x=1.0):\n    return x\n')
    changed('changed_kwdefault_value_in_place', probe,
            lambda: probe.__kwdefaults__.update(x=math.nextafter(1.0, math.inf)))

    ns, probe = fixture('def probe():\n    return leaf\n', leaf=1.0)
    changed('changed_global_value', probe,
            lambda: ns.update(leaf=math.nextafter(1.0, math.inf)))
    ns, probe = fixture('def probe():\n    return leaf\n', leaf=0.0)
    changed('changed_global_signed_zero', probe, lambda: ns.update(leaf=-0.0))
    ns, probe = fixture('def probe():\n    return leaf()\n', leaf=lambda: 1.0)
    changed('changed_global_function', probe, lambda: ns.update(leaf=lambda: 1.0))
    module_fixture = SimpleNamespace(value=1.0)
    ns, probe = fixture('def probe():\n    return module_fixture.value\n',
                        module_fixture=module_fixture)
    changed('changed_module_attribute', probe,
            lambda: setattr(module_fixture, 'value', math.nextafter(1.0, math.inf)))

    array_default = np.asarray([1.0], dtype=np.float64)
    ns, probe = fixture('def probe(x=array_default):\n    return x\n', array_default=array_default)
    changed('changed_default_array_in_place', probe,
            lambda: array_default.__setitem__(0, math.nextafter(1.0, math.inf)))
    array_global = np.asarray([1.0], dtype=np.float64)
    ns, probe = fixture('def probe():\n    return array_global\n', array_global=array_global)
    changed('changed_global_array_in_place', probe,
            lambda: array_global.__setitem__(0, math.nextafter(1.0, math.inf)))

    def closure(value):
        def probe():
            return value
        return probe
    probe = closure(1.0)
    changed('changed_closure_cell_binding', probe,
            lambda: setattr(probe.__closure__[0], 'cell_contents', math.nextafter(1.0, math.inf)))
    closure_array = np.asarray([1.0], dtype=np.float64)
    probe = closure(closure_array)
    changed('changed_closure_array_in_place', probe,
            lambda: closure_array.__setitem__(0, math.nextafter(1.0, math.inf)))
    closure_dictionary = {'value': 1.0}
    probe = closure(closure_dictionary)
    changed('changed_closure_dictionary_in_place', probe,
            lambda: closure_dictionary.update(value=math.nextafter(1.0, math.inf)))

    array = np.asarray([1.0], dtype=np.float64)
    before = candidate._array_key(array)
    array[0] = math.nextafter(1.0, math.inf)
    controls.append(dict(test='one_bit_physical_array_operand', passed=before != candidate._array_key(array)))
    array = np.asarray([0.0], dtype=np.float64)
    before = candidate._array_key(array)
    array[0] = -0.0
    controls.append(dict(test='signed_zero_physical_array_operand', passed=before != candidate._array_key(array)))
    controls.append(dict(test='signed_zero_physical_scalar_operand',
        passed=candidate._scalar_key(0.0) != candidate._scalar_key(-0.0)))

    if cutoff is None:
        controls.append(dict(test='stale_actual_cutoff', passed=False,
                             reason='Actual guarded request cutoff adapter not provided'))
    else:
        receipt = cutoff()
        require(type(receipt) is dict, 'actual cutoff control receipt')
        controls.append(dict(test='stale_actual_cutoff',
            passed=receipt.get('rejected') is True and receipt.get('solver_calls') == 0
            and receipt.get('optimizer_calls') == 0,
            actual_receipt=receipt))
    failed = [row['test'] for row in controls if not row['passed']]
    result = dict(passed=not failed, controls=controls, controls_checked=len(controls),
                  failed_controls=failed, fixture_only=True,
                  solver_calls=0, optimizer_calls=0, new_trajectory_steps=0,
                  claim='Actual live fixture mutations against the supplied candidate guard; no solver invocation. Unknown values may safely miss. A failed control is retained negative evidence.')
    if strict:
        require(not failed, 'live metadata mutations bypassed guard: ' + ', '.join(failed))
    return result


def typed_mapping_controls(candidate, fingerprint=None, strict=True):
    """Fresh tuple-key/value controls shaped like BLAS/LAPACK dispatch memos.

    Native dispatchers are referenced passively, never called. Actual SciPy
    memo contents are copied to isolated dictionaries; installed memos remain
    untouched. A separately checked nested immutable key and an array value
    exercise typed keys and in-place value changes independently.
    """
    key = fingerprint if fingerprint is not None else candidate._callable_key
    np = candidate.np
    controls = []
    def closure(value):
        def probe():
            return value
        return probe
    def changed(name, mapping, edit):
        probe = closure(mapping)
        try:
            before = key(probe)
        except (ValueError, TypeError, RuntimeError) as error:
            controls.append(dict(test=name, passed=False, baseline_keyable=False,
                                 error_type=type(error).__name__))
            return
        try:
            edit(mapping)
            after = key(probe)
        except (ValueError, TypeError, RuntimeError) as error:
            controls.append(dict(test=name, passed=True, baseline_keyable=True, safe_miss=True,
                                 error_type=type(error).__name__))
        else:
            controls.append(dict(test=name, passed=before != after, baseline_keyable=True,
                                 safe_miss=False))

    # The imported candidate already exposes the qualified NumPy/SciPy stack.
    # Read only the known callable closure cell; no native dispatch is invoked.
    import sys
    actual_domains = []
    for module_name, function_name in (
            ('scipy.linalg.blas', 'get_blas_funcs'),
            ('scipy.linalg.lapack', 'get_lapack_funcs')):
        function = getattr(sys.modules[module_name], function_name)
        cells = dict(zip(function.__code__.co_freevars, function.__closure__ or ()))
        memo = cells['memo'].cell_contents
        require(type(memo) is dict and bool(memo), 'actual imported SciPy dispatch memo fixture')
        copied = dict(memo)
        old_key = next(iter(copied))
        require(type(old_key) is tuple, 'actual tuple-keyed SciPy dispatch memo')
        actual_domains.append(dict(module=module_name, entries=len(copied),
            tuple_key=True, value_type=type(copied[old_key]).__name__))
        def change_key(mapping, old=old_key):
            value = mapping.pop(old)
            mapping[old + ('stage228_key_control',)] = value
        changed(function_name + '_actual_typed_key_mutation', copied, change_key)
        copied = dict(memo)
        def change_value(mapping, old=old_key):
            value = mapping[old]
            mapping[old] = (value, 'stage228_value_control')
        changed(function_name + '_actual_typed_value_mutation', copied, change_value)

    nested_key = (('gesdd', 'gesdd_lwork'), None, 'preferred', 'd', False)
    array = np.asarray([1.0], dtype=np.float64)
    changed('typed_mapping_array_value_in_place', {nested_key: array},
            lambda mapping: array.__setitem__(0, math.nextafter(1.0, math.inf)))
    failed = [row['test'] for row in controls if not row['passed']]
    result = dict(passed=not failed, controls=controls, controls_checked=len(controls),
                  failed_controls=failed, actual_scipy_memo_domains=actual_domains,
                  installed_memos_mutated=False, solver_calls=0, optimizer_calls=0,
                  new_trajectory_steps=0,
                  claim='Passive actual SciPy tuple-keyed memo copies and isolated mutable array values; no native callable execution.')
    if strict:
        require(not failed, 'typed live mapping mutations bypassed guard: ' + ', '.join(failed))
    return result


def live_binding_controls(candidate, fingerprint=None, cutoff=None, strict=True):
    """Preserve all seventeen live guards and add five typed-mapping probes."""
    base = _base_live_binding_controls(candidate, fingerprint, cutoff, strict=False)
    typed = typed_mapping_controls(candidate, fingerprint, strict=False)
    base['controls'].extend(typed['controls'])
    base['controls_checked'] = len(base['controls'])
    base['failed_controls'] = [row['test'] for row in base['controls'] if not row['passed']]
    base['passed'] = not base['failed_controls']
    base['actual_scipy_memo_domains'] = typed['actual_scipy_memo_domains']
    base['installed_memos_mutated'] = False
    if strict:
        require(base['passed'], 'live metadata mutations bypassed guard: '
                + ', '.join(base['failed_controls']))
    return base
