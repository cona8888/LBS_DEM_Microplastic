"""Independent negative-witness audit for bounded Stage226 contact replays.

No solver, producer module, installed auditor or physical gate is imported or
modified. This audits completed recorded searches and their truthful reuse
references. It is not a proof that every transitive caught exception was
observed, a trajectory qualification, or permission to use the prototype in
production. The unchanged physical/association auditor remains mandatory.
"""
from pathlib import Path
from datetime import datetime
import ast
import copy
import hashlib
import json
import math
import struct

ROOT = Path(__file__).resolve().parents[1]
ERROR = 'direct contact residual nonconvergence'
NAME = 'stage226_same_inner_witnessed_exhausted_failure_v2'
PHYSICAL_ERRORS = frozenset((ERROR, 'direct contact negative normal force',
    'direct contact cone violation', 'direct contact force closure failed',
    'friction generates energy'))
SEED_SOLVERS = frozenset(('stage172_batched_reduced_near_rest_v1',
                          'stage169_cone_feasible_reduced_modes_v2'))
HARD_END_EPOCH = datetime.fromisoformat('2026-10-07T16:30:34+00:00').timestamp()


class AuditError(ValueError):
    """The recorded evidence does not establish safe negative-result reuse."""


def require(value, message):
    if not value:
        raise AuditError('Stage226 failure-reuse audit: ' + message)


def digest(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise AuditError('Noncanonical witness data') from error
    return hashlib.sha256(raw).hexdigest()


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
            and last['file'].endswith('exhausted_failure_memo_v2.py::observer_only_semismooth'),
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


def audit(log, expected_binding=None, expected_deadline=None):
    """Audit recorded negative-result reuse; return a compact evidence summary.

    ``expected_binding`` optionally fixes the externally authenticated runtime
    binding digest. Historical timestamps are checked against the frozen work
    deadline; this function never changes the recorded deadline or reads a live
    clock to reinterpret old evidence.
    """
    require(type(log) is dict and log.get('name') == NAME, 'exact prototype log identity')
    require(log.get('production_authorized') is False and log.get('new_trajectory_steps') == 0,
            'bounded nonadvancing development claim')
    require(log.get('enabled') is True and type(log.get('reuse_enabled')) is bool,
            'explicit observed baseline/reuse mode')
    require(log.get('cache_retained') is False, 'cache discarded at scope exit')
    stop = _finite(log.get('stop_epoch'), 'frozen work deadline')
    require(0 < stop <= HARD_END_EPOCH, 'no extended bounded work deadline')
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
    seen_executed = seen_reused = safe_failures = 0
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
        require(0 < entry_checked <= checked, 'fresh entry then post-fingerprint cutoff checks')
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
            require(event.get('certificate_before_sha256') == event.get('certificate_after_sha256')
                    == origin.get('certificate_after_sha256'), 'same unchanged external certificate evidence')
            _sha(event.get('certificate_before_sha256'), 'reused certificate binding')
            require(digest(event.get('certificate_binding_before')) == event['certificate_before_sha256']
                    and digest(event.get('certificate_binding_after')) == event['certificate_after_sha256'],
                    'independent unchanged certificate descriptor digests on hit')
            require(event.get('cache_eligible') is True, 'explicit certified hit eligibility')
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
            newest_eligible[token] = index
            safe_failures += 1
        elif event.get('disposition') == 'executed_failure':
            require(event.get('witness_sha256') == digest(witness), 'uncertain failure retained exactly')
    require(seen_executed == executed and seen_reused == reused, 'all execution counters authenticated')
    return dict(passed=True, logical_requests=logical, executed_requests=executed,
                reused_requests=reused, witnessed_exhaustions=safe_failures,
                inner_calls=inner_calls, new_trajectory_steps=0,
                original_equation_ast_verified=True, physical_audit_replaced=False,
                claim='Recorded bounded negative witnesses, observed Python seed-call exceptions and same-inner references only. Native errors are covered only if propagated to Python; no physical, restart, trajectory or production qualification.')


def mutation_checks(log, expected_binding=None, expected_deadline=None):
    """Falsify meaningful corruption controls against a genuine passing hit."""
    audit(log, expected_binding, expected_deadline)
    hits = [i for i, event in enumerate(log['events']) if event['reused']]
    require(bool(hits), 'mutation fixture contains an actual reuse reference')
    hit_index = hits[0]
    first_index = log['events'][hit_index]['first_failure_event']
    mutations = []
    def change(name, edit):
        candidate = copy.deepcopy(log)
        edit(candidate, candidate['events'][first_index], candidate['events'][hit_index])
        try:
            audit(candidate, expected_binding, expected_deadline)
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
    return dict(passed=True, mutation_controls=mutations, controls_rejected=len(mutations),
                fixture_had_actual_reuse=True, new_trajectory_steps=0)
