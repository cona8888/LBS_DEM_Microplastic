"""Read-only history reader for separately bounded offline accounting.

The current archive uses the original bounded XZ/envelope reader and EXACT
history decoder code. Only prior-prefix validation is replaced: an explicitly
registered prefix is rebound to its freshly hashed compressed file and seal,
instead of decompressing that same prior archive again. Never install this in
transport. A primed seed still needs the consumer's sealed full-ancestry proof;
priming alone does not establish historical physical acceptance or ancestry.
"""
from dataclasses import dataclass, fields
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace
import ast, copy, hashlib, inspect, json, lzma, sys, time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage196_staging'))
import lossless_compact_xz_v1 as qualified

FIELDS = ('path', 'design_sha256', 'compressed_sha256', 'original_sha256',
          'history_sha256', 'history_length')

# Original, already frozen storage sources. Separate qualified imports have
# different class/function identities; they must still have identical source,
# immutable code descriptors and complete links to their own qualified globals.
SOURCE_SHA = {
    'stage176_staging/lossless_record_xz_v1.py': '4917e4c4744c830de8d276d41311147158f7be0d1716e1a2ab3bc2aee3162e0d',
    'stage179_staging/lossless_history_prefix_v1.py': '78a12525874f11939bb3803ffd00841fce0dcea9ddecb21cd40c8996b8125b4a',
    'stage194_staging/lossless_trial_references_v2.py': '3a60db1f151f1ac1ebd123185e4c76e3ef8b51af25b045cd02b953ee655ecdd6',
    'stage198_staging/fast_storage_v1.py': 'db2675d7eab60ebf462fa3492db12faac1571eed13d068adf26e853040f99a5d',
    'stage199_staging/owned_decode_storage_v1.py': 'efd02aa39265980168eba00b74d155a2c5d2017b7395b0135a730146eab09186',
    'stage199_staging/transaction_json_memo_v1.py': '3b69ab1500000672124e09cdd98b9ab8c5eef879741955fd7ce559b7376adbc4',
    'stage199_staging/canonical_json_native_v1.py': 'd93cc1aec40c3a218c87689c40dfddcdf3551de9f5f7a14181177b0ac9da0b72',
}


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def code_descriptor(code):
    """Immutable executable fields, recursively, without marshal identities."""
    constants = tuple(code_descriptor(v) if isinstance(v, CodeType) else v
                      for v in code.co_consts)
    return (code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount,
            code.co_nlocals, code.co_stacksize, code.co_flags, code.co_code,
            constants, code.co_names, code.co_varnames, code.co_freevars,
            code.co_cellvars, code.co_filename, code.co_name, code.co_qualname,
            code.co_firstlineno, code.co_linetable, code.co_exceptiontable)


def same_function(actual, expected):
    return (type(actual) is FunctionType and type(expected) is FunctionType
            and code_descriptor(actual.__code__) == code_descriptor(expected.__code__)
            and actual.__defaults__ == expected.__defaults__
            and actual.__kwdefaults__ == expected.__kwdefaults__
            and actual.__closure__ is expected.__closure__ is None)


def source_definition(relative, name):
    path = ROOT/relative
    data = path.read_bytes()
    need(hashlib.sha256(data).hexdigest() == SOURCE_SHA[relative],
         'Unchanged original storage source: '+relative)
    # Compile the COMPLETE source but execute none of it: CPython's import-name
    # call optimizations depend on the surrounding module symbol table.
    module_code = compile(data, str(path), 'exec')
    code = next(v for v in module_code.co_consts if isinstance(v, CodeType) and v.co_name == name)
    return FunctionType(code, {})


def qualified_bindings(codec):
    """Qualify independent original aliases, including the actual Stage199 reader."""
    qualified.verify_bindings()
    for name in ('decode', 'validate_prefix', 'read_record', 'make_state', 'packed_history', 'digest'):
        need(same_function(getattr(codec, name), getattr(qualified.codec, name)),
             'Original qualified history code required: '+name)
        need(getattr(codec, name).__globals__ is vars(codec), 'History function local namespace: '+name)
    need(tuple(f.name for f in fields(codec.HistoryState)) == FIELDS+('history_bytes',)
         and codec.HistoryState.__dataclass_params__.frozen
         and same_function(codec.HistoryState.reference, qualified.codec.HistoryState.reference),
         'Original immutable history state type/schema/reference')
    need(codec.base.api is codec.api is qualified.base.api
         and codec.json is json and codec.hashlib is hashlib and codec.Path is Path
         and codec.ENCODING == qualified.codec.ENCODING, 'Complete original history global links')
    frozen_limits = dict(FORMAT='dem-json-xz-v1', MAX_RAW=512*1024**2,
                         MAX_COMPRESSED=128*1024**2, MEMLIMIT=256*1024**2,
                         RESERVE=20*1024**3, CHUNK=1024**2)
    need(all(getattr(qualified.base, name) == value and getattr(codec.base, name) == value
             for name, value in frozen_limits.items()), 'Original immutable XZ/resource declarations')
    for relative in ('stage176_staging/lossless_record_xz_v1.py', 'stage179_staging/lossless_history_prefix_v1.py',
                     'stage194_staging/lossless_trial_references_v2.py'):
        need(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == SOURCE_SHA[relative],
             'Unchanged original source: '+relative)
    for name in ('read_record', 'read_bytes', 'file_sha', 'validate_path'):
        actual = getattr(qualified.base, name)
        need(same_function(actual, source_definition('stage176_staging/lossless_record_xz_v1.py', name))
             and actual.__globals__ is vars(qualified.base), 'Complete original bounded-reader code: '+name)
    need(qualified.base.json is json and qualified.base.hashlib is hashlib
         and qualified.base.lzma is lzma and qualified.base.Path is Path,
         'Complete original bounded-reader standard-library links')
    reader = codec.base.read_record
    if same_function(reader, qualified.codec.base.read_record):
        # Earlier original alias is supported only with its unchanged canonical
        # bytes and exact original unpack/bounded-reader globals.
        need(same_function(codec.base.raw_bytes, qualified.codec.base.raw_bytes),
             'Original canonical byte function')
        g = reader.__globals__
        need(g['codec'] is codec and same_function(g['unpack'], qualified.instance.unpack)
             and g['base'].read_record is qualified.base.read_record
             and g['base'].raw_bytes is codec.base.raw_bytes, 'Complete original envelope global links')
        return 'stage196-original-envelope'
    need(same_function(reader, source_definition('stage199_staging/owned_decode_storage_v1.py', 'read_envelope')),
         'Qualified original owned-envelope reader')
    g = reader.__globals__
    need(g['codec'] is codec and g['instance'].codec is codec
         and g['instance'].read_envelope is reader
         and g['fresh_reader'] is g['instance'].base.read_record is qualified.base.read_record,
         'Actual owned-envelope exact bounded-reader links')
    need(same_function(g['verify_bindings'], source_definition('stage199_staging/owned_decode_storage_v1.py', 'verify_bindings')),
         'Original owned-envelope binding verifier')
    g['verify_bindings']()
    # Reproduce only the frozen unpack code transformation for qualification;
    # no function is installed and no original namespace is mutated.
    tree = ast.parse(inspect.getsource(qualified.instance.unpack))
    tree.body[0].name = '_consume_fresh_wrapper'
    changes = 0
    class Owned(ast.NodeTransformer):
        def visit_Assign(self, node):
            nonlocal changes
            if ast.unparse(node) == "env = copy.deepcopy(wrapper['packed_envelope'])":
                node.value = ast.parse("wrapper['packed_envelope']", mode='eval').body
                changes += 1
            return self.generic_visit(node)
    Owned().visit(tree); ast.fix_missing_locations(tree)
    namespace = {}
    exec(compile(tree, str(ROOT/'stage199_staging/owned_decode_storage_v1.py')+'::owned_fresh_json', 'exec'), namespace)
    unpack = g['_consume_fresh_wrapper']; u = unpack.__globals__
    need(changes == 1 and same_function(unpack, namespace['_consume_fresh_wrapper'])
         and u['base'] is g['instance'].base
         and u['base'].raw_bytes is codec.base.raw_bytes
         and u['copy'] is copy and u['hashlib'] is hashlib
         and same_function(u['checked_range'], qualified.instance.checked_range)
         and u['SCHEMA'] == qualified.instance.SCHEMA
         and u['SYSTEM_KEYS'] == qualified.instance.SYSTEM_KEYS, 'Complete original owned-unpack code/global links')
    raw = codec.base.raw_bytes
    need(same_function(raw, source_definition('stage198_staging/fast_storage_v1.py', 'raw_bytes')),
         'Original exact canonical adapter code')
    memo = g['memo_storage']; mg = vars(memo)
    need(raw.__globals__['canonical'] is memo.canonical
         and raw.__globals__['base'] is qualified.base
         and memo.canonical.dumps is memo.dumps
         and mg['json'] is json and mg['_active'].get() is None,
         'Original canonical adapter global links')
    for name in ('dumps', 'compact', 'ordinary'):
        need(same_function(getattr(memo, name), source_definition('stage199_staging/transaction_json_memo_v1.py', name))
             and getattr(memo, name).__globals__ is mg, 'Original canonical memo code/global links: '+name)
    native = memo.native
    need(memo.np is native.np, 'Original canonical numeric byte-view module')
    for name in ('expand', 'expanded_size'):
        dispatcher = getattr(native, name)
        need(same_function(dispatcher.py_func, source_definition('stage199_staging/canonical_json_native_v1.py', name))
             and dispatcher.py_func.__globals__ is vars(native)
             and dispatcher.targetoptions.get('fastmath') is False
             and dispatcher.targetoptions.get('parallel') is False,
             'Original exact native byte expansion: '+name)
    return 'stage199-original-owned-envelope'


@dataclass(frozen=True)
class _VerifiedPrefix:
    public: object
    values: tuple
    history_bytes: bytes
    seal_bytes: bytes
    seal_sha256: str


class Reader:
    """Two history-only capabilities: a primed seed and immediate prior output.

    Capabilities are exact registered HistoryState objects, with immutable
    internal snapshots. A copied/fabricated/stale object cannot enter the fast
    path. Mutation of a returned object is checked against its snapshot. No
    force systems, physical acceptance, or model states are cached.
    """
    def __init__(self, codec, fresh_bound=lambda: None, progress=None):
        fresh_bound()
        self.qualified_storage = qualified_bindings(codec)
        fresh_bound()
        self.codec = codec
        self.fresh_bound = fresh_bound
        self.progress = progress
        self.stats = dict(current_archive_reads=0, current_logical_records=0,
                          fresh_prior_raw_hashes=0, prime_original_archive_reads=0,
                          prefix_capabilities_issued=0)
        self._seed = self._active = self._candidate = None
        self._busy = False
        self._current_seal = None
        self._read_seal = lambda path: Path(path).with_suffix('.seal.json').read_bytes()
        self._file_sha = qualified.base.file_sha
        self._file_size = lambda path: Path(path).stat().st_size
        self._decode = FunctionType(codec.decode.__code__,
            {**codec.decode.__globals__, 'validate_prefix': self._validate_prefix},
            codec.decode.__name__, codec.decode.__defaults__, codec.decode.__closure__)
        reader_base = SimpleNamespace(**vars(codec.base))
        reader_base.read_record = self._read_current_envelope
        self._read = FunctionType(codec.read_record.__code__,
            {**codec.read_record.__globals__, 'base': reader_base, 'decode': self._decode},
            codec.read_record.__name__, codec.read_record.__defaults__, codec.read_record.__closure__)

    def _entry(self, prefix):
        for item in (self._active, self._seed):
            if item is not None and item.public is prefix:
                return item
        raise RuntimeError('Explicit registered immediately prior or primed prefix required')

    def _snapshot(self, prefix, seal_bytes):
        need(type(prefix) is self.codec.HistoryState
             and type(prefix.history_bytes) is bytes, 'Original immutable history state required')
        values = tuple(getattr(prefix, field) for field in FIELDS)
        need(type(values[-1]) is int and values[-1] >= 0, 'Exact nonnegative history length')
        seal = json.loads(seal_bytes)
        need(seal.get('design_sha256') == prefix.design_sha256
             and seal.get('compressed_sha256') == prefix.compressed_sha256,
             'Current verified archive/seal prefix identity')
        need(hashlib.sha256(prefix.history_bytes).hexdigest() == prefix.history_sha256,
             'Current verified history bytes')
        need(len(json.loads(prefix.history_bytes)) == prefix.history_length,
             'Current verified history length')
        return _VerifiedPrefix(prefix, values, prefix.history_bytes, seal_bytes,
                               hashlib.sha256(seal_bytes).hexdigest())

    def prime(self, prefix):
        """Validate one externally sealed seed with the ORIGINAL full validator.

        This is an explicit bootstrap, never a shortcut for ancestry auditing.
        The original validator reads/unpacks the prior archive once. All future
        uses rehash its compressed bytes and exact seal, including seed reuse
        for serial/split diagnostics.
        """
        self.fresh_bound()
        need(type(prefix) is self.codec.HistoryState and type(prefix.history_bytes) is bytes,
             'Original immutable seed history state required')
        values_before = tuple(getattr(prefix, field) for field in FIELDS)
        history_before = prefix.history_bytes
        before = self._read_seal(prefix.path)
        self.codec.validate_prefix(prefix, prefix.design_sha256)
        self.stats['prime_original_archive_reads'] += 1
        self.fresh_bound()
        after = self._read_seal(prefix.path)
        need(before == after, 'Seed seal changed during original validation')
        need(tuple(getattr(prefix, field) for field in FIELDS) == values_before
             and prefix.history_bytes == history_before, 'Seed object changed during original validation')
        entry = self._snapshot(prefix, after)
        self._check_prefix(entry, prefix, prefix.design_sha256)
        self._seed = self._active = entry
        self.stats['prefix_capabilities_issued'] += 1
        return prefix

    def _check_prefix(self, entry, prefix, design):
        self.fresh_bound()
        need(type(prefix) is self.codec.HistoryState and type(prefix.history_bytes) is bytes,
             'Original immutable history state required')
        need(prefix is entry.public
             and tuple(getattr(prefix, field) for field in FIELDS) == entry.values
             and prefix.history_bytes == entry.history_bytes,
             'Registered prefix object changed or substituted')
        need(prefix.design_sha256 == design
             and hashlib.sha256(prefix.history_bytes).hexdigest() == prefix.history_sha256,
             'Fresh prefix design/history-byte binding')
        seal_bytes = self._read_seal(prefix.path)
        need(hashlib.sha256(seal_bytes).hexdigest() == entry.seal_sha256
             and seal_bytes == entry.seal_bytes, 'Prior seal changed')
        seal = json.loads(seal_bytes)
        need(seal.get('format') == qualified.base.FORMAT
             and seal.get('design_sha256') == design
             and seal.get('compressed_sha256') == prefix.compressed_sha256,
             'Fresh original prior format/design/seal binding')
        for key, limit in (('compressed_bytes', qualified.base.MAX_COMPRESSED),
                           ('uncompressed_bytes', qualified.base.MAX_RAW)):
            need(type(seal.get(key)) is int and 0 < seal[key] <= limit,
                 'Original bounded prior seal declaration')
        need(self._file_size(prefix.path) == seal['compressed_bytes'], 'Prior compressed size changed')
        self.fresh_bound()
        need(self._file_sha(prefix.path) == prefix.compressed_sha256,
             'Prior compressed archive changed')
        self.stats['fresh_prior_raw_hashes'] += 1
        self.fresh_bound()
        history = json.loads(prefix.history_bytes)
        need(isinstance(history, list) and len(history) == prefix.history_length,
             'Fresh complete prior history length')
        return history

    def _validate_prefix(self, prefix, design):
        need(self._candidate is not None, 'Explicit verified decode capability required')
        return self._check_prefix(self._candidate, prefix, design)

    def _read_current_envelope(self, path, design):
        self.fresh_bound()
        before = self._read_seal(path)
        envelope = self.codec.base.read_record(path, design)
        self.stats['current_archive_reads'] += 1
        self.fresh_bound()
        after = self._read_seal(path)
        need(before == after, 'Current seal changed during original envelope validation')
        self._current_seal = after
        return envelope

    def read_record(self, path, design_sha256, prefix=None):
        self.fresh_bound()
        need(not self._busy, 'Non-reentrant read-only reader')
        candidate = None if prefix is None else self._entry(prefix)
        self._busy = True
        self._candidate, self._current_seal = candidate, None
        try:
            # EXACT original read_record/decode code checks the current envelope,
            # six-field parent reference, appended history, original size and
            # original canonical logical-record hash. Only prior re-opening is
            # replaced by the separately authenticated history-only capability.
            record, state = self._read(path, design_sha256, prefix)
            self.fresh_bound()
            need(self._current_seal is not None, 'Current original sealed read required')
            entry = self._snapshot(state, self._current_seal)
            self._active = entry
            self.stats['current_logical_records'] += 1
            self.stats['prefix_capabilities_issued'] += 1
            if self.progress is not None and self.stats['current_logical_records'] % 10 == 0:
                self.progress(dict(self.stats))
                self.fresh_bound()
            return record, state
        finally:
            self._candidate = self._current_seal = None
            self._busy = False


def controls(codec):
    """Pure metadata/capability/history-decoder negatives; no file/process work."""
    reader = Reader(codec)
    design = 'a'*64
    history = [dict(time_s=0., position_m=[1., 2., 3.])]
    packed = codec.packed_history(history)
    reference = dict(path='pure-fixture.json.xz', design_sha256=design,
        compressed_sha256='b'*64, original_sha256='c'*64,
        history_sha256=hashlib.sha256(packed).hexdigest(), history_length=1)
    prefix = codec.HistoryState(**reference, history_bytes=packed)
    seal = dict(format=qualified.base.FORMAT, design_sha256=design,
        compressed_sha256=reference['compressed_sha256'], compressed_bytes=8,
        uncompressed_bytes=16, uncompressed_sha256='d'*64)
    seal_bytes = json.dumps(seal, sort_keys=True).encode()
    reader._read_seal = lambda path: seal_bytes
    reader._file_sha = lambda path: reference['compressed_sha256']
    reader._file_size = lambda path: 8
    reader._active = reader._snapshot(prefix, seal_bytes)
    checks = []
    def reject(name, action):
        try:
            action()
        except (RuntimeError, ValueError, OSError, TypeError):
            checks.append(name)
        else:
            raise AssertionError('Negative admitted: '+name)
    wrong_code = SimpleNamespace(**vars(codec))
    wrong_code.decode = lambda envelope, prefix=None: (envelope, b'[]')
    reject('changed_history_function_code', lambda: Reader(wrong_code))
    wrong_globals = SimpleNamespace(**vars(codec))
    wrong_globals.decode = FunctionType(codec.decode.__code__,
        {**codec.decode.__globals__, 'json': object()}, codec.decode.__name__, codec.decode.__defaults__)
    reject('substituted_history_function_globals', lambda: Reader(wrong_globals))
    need(reader._check_prefix(reader._active, prefix, design) == history,
         'Exact pure capability accepted')
    checks.append('exact_capability')
    reject('fabricated_equal_prefix', lambda: reader._entry(codec.HistoryState(**reference, history_bytes=packed)))
    reject('wrong_reader', lambda: Reader(codec)._entry(prefix))
    saved = reader._active
    reader._active = None
    reject('stale_unregistered_prefix', lambda: reader._entry(prefix))
    reader._active = saved
    for field in FIELDS:
        replacement = 2 if field == 'history_length' else 'changed'
        object.__setattr__(prefix, field, replacement)
        reject('mutated_'+field, lambda: reader._check_prefix(saved, prefix, design))
        object.__setattr__(prefix, field, reference[field])
    object.__setattr__(prefix, 'history_bytes', b'[]')
    reject('mutated_history_bytes', lambda: reader._check_prefix(saved, prefix, design))
    object.__setattr__(prefix, 'history_bytes', packed)
    reject('wrong_design', lambda: reader._check_prefix(saved, prefix, 'e'*64))
    reader._read_seal = lambda path: seal_bytes+b' '
    reject('changed_seal_bytes', lambda: reader._check_prefix(saved, prefix, design))
    reader._read_seal = lambda path: seal_bytes
    reader._file_sha = lambda path: 'f'*64
    reject('changed_prior_raw', lambda: reader._check_prefix(saved, prefix, design))
    reader._file_sha = lambda path: reference['compressed_sha256']
    reader._file_size = lambda path: 9
    reject('changed_prior_size', lambda: reader._check_prefix(saved, prefix, design))
    reader._file_size = lambda path: 8
    def missing(path):
        raise FileNotFoundError('Pure unavailable prior fixture')
    reader._read_seal = missing
    reject('missing_prior_seal', lambda: reader._check_prefix(saved, prefix, design))
    reader._read_seal = lambda path: seal_bytes
    # Exercise the EXACT original decoder with a small valid logical envelope.
    rows = history+[dict(time_s=1., position_m=[2., 3., 4.])]
    record = dict(design_sha256=design, result=dict(history=rows,
        checkpoint=dict(state=dict(history=rows))))
    raw = codec.base.raw_bytes(record)
    payload = dict(design_sha256=design, result=dict(checkpoint=dict(state={})))
    envelope = dict(design_sha256=design, evidence_encoding=codec.ENCODING,
        original_uncompressed_bytes=len(raw), original_uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
        history=dict(length=2, sha256=hashlib.sha256(codec.packed_history(rows)).hexdigest(),
                     prefix=prefix.reference(), appended_rows=rows[1:]), payload=payload)
    reader._candidate = saved
    decoded, full = reader._decode(envelope, prefix)
    need(decoded == record and full == codec.packed_history(rows), 'Exact original pure logical bytes restored')
    checks.append('exact_original_decoder')
    import copy
    for name, mutate in (
        ('wrong_parent_reference', lambda e: e['history']['prefix'].update(original_sha256='0'*64)),
        ('wrong_history_hash', lambda e: e['history'].update(sha256='0'*64)),
        ('wrong_history_length', lambda e: e['history'].update(length=3)),
        ('wrong_original_logical_hash', lambda e: e.update(original_uncompressed_sha256='0'*64)),
        ('wrong_original_logical_size', lambda e: e.update(original_uncompressed_bytes=len(raw)+1)),
        ('mutated_appended_history', lambda e: e['history']['appended_rows'][0].update(time_s=2.)),
        ('ambiguous_state_history', lambda e: e['payload']['result']['checkpoint']['state'].update(history=[])),
        ('wrong_payload_design', lambda e: e['payload'].update(design_sha256='0'*64))):
        changed = copy.deepcopy(envelope); mutate(changed)
        reject(name, lambda changed=changed: reader._decode(changed, prefix))
    reader._candidate = None
    reject('unregistered_decode_capability', lambda: reader._decode(envelope, prefix))
    events = []
    def progress(stats):
        events.append(dict(stats))
        stats['current_logical_records'] = -1  # Observer receives no live stats.
    observed = Reader(codec, progress=progress)
    def pure_read(path, design, parent):
        observed._current_seal = seal_bytes
        return record, prefix
    observed._read = pure_read  # Fixture-only private instance; no original code changes.
    for _ in range(10):
        observed.read_record('pure-observer-fixture', design)
    need(len(events) == 1 and events[0]['current_logical_records'] == 10
         and observed.stats['current_logical_records'] == 10,
         'Progress every ten logical records with a copied stats snapshot')
    checks.append('bounded_progress_snapshot')
    return dict(passed=True, checks=checks, pure_controls=len(checks), numerical_calls=0,
                process_actions=0, new_trajectory_steps=0, evidence_archive_reads=0,
                file_reads='qualified_original_source_files_only', qualified_storage=reader.qualified_storage,
                original_decode_code_object_retained=reader._decode.__code__ is codec.decode.__code__,
                original_read_code_object_retained=reader._read.__code__ is codec.read_record.__code__)


def paired_test_173(codec):
    """Bounded nonadvancing late-record equality test, NEVER an ancestry proof."""
    limit = time.monotonic()+180
    def bound():
        need(time.monotonic() < limit, 'Bounded nonadvancing paired-reader test expired')
    folder = ROOT/'stage231_runs/sample0_sphere_20261008/run_01/s2_i0_sphere_f0p125'
    design = 'bad6127d636511ab08dbf9a432cc6919885b5e779d2edc577ce0305a8de1a4fc'
    terminal = json.loads((folder/'checkpoint.json').read_text())
    parent_path, path = folder/'segment_00172/call.json.xz', folder/'segment_00173/call.json.xz'
    bound()
    parent_envelope = codec.base.read_record(parent_path, design)
    bound()
    meta = parent_envelope['history']
    parent_history = terminal['state']['history'][:meta['length']]
    seal = json.loads(parent_path.with_suffix('.seal.json').read_text())
    prefix = codec.HistoryState(path=str(parent_path.resolve()), design_sha256=design,
        compressed_sha256=seal['compressed_sha256'], original_sha256=parent_envelope['original_uncompressed_sha256'],
        history_sha256=meta['sha256'], history_length=meta['length'], history_bytes=codec.packed_history(parent_history))
    del parent_envelope
    reader = Reader(codec, bound)
    tick = time.perf_counter(); reader.prime(prefix); prime_seconds = time.perf_counter()-tick
    tick = time.perf_counter(); expected, old_state = codec.read_record(path, design, prefix)
    original_seconds = time.perf_counter()-tick
    bound()
    tick = time.perf_counter(); actual, new_state = reader.read_record(path, design, prefix)
    repaired_seconds = time.perf_counter()-tick
    need(actual == expected and new_state.reference() == old_state.reference()
         and new_state.history_bytes == old_state.history_bytes,
         'Exact real logical record/FULL checkpoint/history and prefix equality')
    need(actual['result']['checkpoint'] == terminal, 'Exact saved terminal FULL checkpoint equality')
    return dict(passed=True, record=str(path), parent=str(parent_path),
        original_reader_seconds=original_seconds, repaired_reader_seconds=repaired_seconds,
        separate_original_seed_prime_seconds=prime_seconds, reader_stats=dict(reader.stats),
        complete_record_equal=True, full_checkpoint_equal=True, history_bytes_equal=True,
        next_prefix_reference_equal=True, test_only_parent_history_from_saved_terminal=True,
        full_ancestry_promoted=False, physical_acceptance_promoted=False,
        numerical_calls=0, new_trajectory_steps=0, process_actions=0)
