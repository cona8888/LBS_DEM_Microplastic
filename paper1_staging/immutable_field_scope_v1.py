"""One admitted Paper1 flow per immutable scope; original transport unchanged.

Reuse the qualified snapshot storage and two-digest substitution. The only
extension is a prospectively supplied (seed, flow, grid) key and direct-field
reader. This module grants no numerical dispatch or exposure authority.
"""
from pathlib import Path
from contextlib import contextmanager
import copy, hashlib, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage173_staging'))
import immutable_field_snapshot_v1 as original
import load_direct_fields_v1 as reader

SNAPSHOT_SHA = 'cac65dfbecc4ec4bb263d1187182e731601b9f6ea430b5fd247b8eaf725450b2'

def dependencies(metadata):
    return {v['path']: v['sha256'] for v in metadata.values()
            if isinstance(v, dict) and {'path', 'sha256'} <= v.keys()}


@contextmanager
def scope(api, key, expected_metadata):
    key = tuple(key)
    api.require(len(key) == 3 and key[0] == 2 and key[1] in (.5, 1., 2.)
                and key[2] == 6, 'Outside Paper1 direct-field domain')
    api.require(reader.sha(original.__file__) == SNAPSHOT_SHA,
                'Qualified immutable snapshot source changed')
    pinned = dependencies(expected_metadata)
    api.verify_mapping(pinned)
    prior_load, prior_execute = api.fields.load, api.execute
    cache = {}

    def load(seed, flow_factor=1., cpd=2, **kwargs):
        api.require((seed, flow_factor, cpd) == key and not kwargs,
                    'Different field requested inside pinned scope')
        if not cache:
            field, data, metadata = reader.load(*key)
            api.require(metadata == expected_metadata, 'Pinned field metadata drift')
            fixed_field = copy.copy(field)
            hashes = {}
            for name, value in vars(field).items():
                if isinstance(value, np.ndarray):
                    fixed, hashes['field.' + name] = original.freeze(value)
                    setattr(fixed_field, name, fixed)
            fixed_data = {}
            for name, value in data.items():
                api.require(isinstance(value, np.ndarray), 'Unexpected geometry object')
                fixed_data[name], hashes['data.' + name] = original.freeze(value)
            cache.update(field=fixed_field, data=fixed_data, metadata=copy.deepcopy(metadata),
                         hashes=hashes, shape=fixed_field.u.shape,
                         dtype=fixed_field.u.dtype.str, strides=fixed_field.u.strides)
        return copy.copy(cache['field']), dict(cache['data']), copy.deepcopy(cache['metadata'])

    def digest(field):
        api.require(bool(cache), 'Uninitialized field snapshot')
        u = field.u
        api.require(u is cache['field'].u and u.shape == cache['shape']
                    and u.dtype.str == cache['dtype'] and u.strides == cache['strides']
                    and not u.flags.writeable and isinstance(original.owner(u), bytes),
                    'Immutable field identity/storage changed')
        return cache['hashes']['field.u']

    replacement, generated_source = original.execute_adapter(prior_execute, digest)
    api.fields.load, api.execute = load, replacement
    try:
        yield dict(cache=cache, load=load, digest=digest, generated_source=generated_source)
    finally:
        # Restore the exact previous functions even if validation raises.
        api.fields.load, api.execute = prior_load, prior_execute
        if cache:
            for name, expected in cache['hashes'].items():
                group, attr = name.split('.', 1)
                array = getattr(cache['field'], attr) if group == 'field' else cache['data'][attr]
                api.require(not array.flags.writeable and isinstance(original.owner(array), bytes),
                            'Immutable snapshot ownership at exit')
                api.require(hashlib.sha256(array.tobytes(order='C')).hexdigest() == expected,
                            'Complete snapshot content hash at exit')
        api.verify_mapping(pinned)
