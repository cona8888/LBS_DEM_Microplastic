"""Budget-only modal-runner adapter and lossless immutable evidence storage.

Neither helper changes equations, tolerances, timesteps, forces or accepted
states. The legacy global 500,000-step ceiling is a resource limit, not a
per-checkpoint allowance. A future long run must bind an explicit total budget.
"""
from contextlib import contextmanager
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage164_staging'))
import fixed_step_deadline_qualification_v1 as qualification
api = qualification.api
modal = qualification.old.parent.prior.candidate


def with_step_budget(function, maximum_steps):
    if type(maximum_steps) is not int or not 1 <= maximum_steps <= 50_000_000:
        raise ValueError('explicit positive total step budget <=50 million required')
    names = function.__code__.co_varnames[:function.__code__.co_argcount]
    defaults = list(function.__defaults__)
    index = names.index('max_steps') - (len(names) - len(defaults))
    if index < 0:
        raise RuntimeError('max_steps must have a default')
    defaults[index] = maximum_steps
    changed = types.FunctionType(function.__code__, function.__globals__,
                                 function.__name__, tuple(defaults), function.__closure__)
    changed.__kwdefaults__ = dict(function.__kwdefaults__ or {})
    a, b = inspect.signature(function), inspect.signature(changed)
    differences = [name for name in a.parameters if a.parameters[name] != b.parameters[name]]
    api.require(differences == ([] if maximum_steps == a.parameters['max_steps'].default else ['max_steps']),
                'only the resource ceiling may change')
    api.require(changed.__code__ is function.__code__ and changed.__globals__ is function.__globals__,
                'identical numerical bytecode and globals')
    return changed


@contextmanager
def step_budget_scope(maximum_steps):
    saved = modal.CANDIDATE
    modal.CANDIDATE = with_step_budget(saved, maximum_steps)
    try:
        with modal.scope(True):
            yield
    finally:
        modal.CANDIDATE = saved


def write_record(path, record):
    """Exclusive gzip, deterministic header, unrounded JSON and two hashes."""
    path = Path(path)
    data = (json.dumps(record, sort_keys=True, indent=2, allow_nan=True,
                       default=api.frozen.h.json_value) + '\n').encode('utf-8')
    with path.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=3) as stream:
            stream.write(data)
    seal = {'gzip_sha256': api.sha(path), 'uncompressed_sha256': hashlib.sha256(data).hexdigest(),
            'design_sha256': record['design_sha256'], 'uncompressed_bytes': len(data),
            'compressed_bytes': path.stat().st_size}
    api.write(path.with_suffix('.seal.json'), seal)
    return seal


def read_record(path, design_sha256):
    path = Path(path)
    seal = api.read(path.with_suffix('.seal.json'))
    api.require(seal['gzip_sha256'] == api.sha(path) and seal['design_sha256'] == design_sha256,
                'compressed record binding')
    with gzip.open(path, 'rb') as stream:
        data = stream.read()
    api.require(hashlib.sha256(data).hexdigest() == seal['uncompressed_sha256'] and len(data) == seal['uncompressed_bytes'],
                'exact uncompressed evidence')
    r = json.loads(data)
    api.require(r['design_sha256'] == design_sha256, 'record design binding')
    return r
