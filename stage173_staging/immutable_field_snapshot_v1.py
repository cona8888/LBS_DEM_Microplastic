"""Opt-in immutable CPD6 snapshot. No interpolation or physics changes.

The original loader and all of its validation run once. Arrays are copied
into immutable Python bytes, not merely flagged read-only. Thus no writable
NumPy view can alias the snapshot. Original pre/post velocity digests are
replaced only for that exact immutable array by its already-computed digest;
object identity, shape, dtype, strides and base ownership are checked at each
use. Full content and file hashes are checked again on scope exit.
"""
from contextlib import contextmanager
import ast, copy, hashlib, inspect, time
import numpy as np

stats={'loads':0,'hits':0,'digest_hits':0,'load_seconds':0.,'snapshot_seconds':0.}


def owner(array):
    base=array
    while isinstance(base,np.ndarray) and base.base is not None:base=base.base
    return base


def freeze(array):
    array=np.asarray(array)
    if array.dtype.hasobject:raise ValueError('object arrays cannot be immutable snapshots')
    raw=array.tobytes(order='C')
    result=np.frombuffer(raw,dtype=array.dtype).reshape(array.shape)
    if result.flags.writeable or not isinstance(owner(result),bytes):raise RuntimeError('immutable byte ownership required')
    if not np.array_equal(array,result,equal_nan=True):raise RuntimeError('snapshot data changed')
    return result,hashlib.sha256(raw).hexdigest()


def execute_adapter(original,digest):
    tree=ast.parse(inspect.getsource(original));count=0
    class Change(ast.NodeTransformer):
        def visit_Call(self,node):
            nonlocal count
            if ast.unparse(node)=='hashlib.sha256(field.u.tobytes()).hexdigest()':
                count+=1
                return ast.copy_location(ast.Call(func=ast.Name(id='snapshot_digest',ctx=ast.Load()),args=[ast.Name(id='field',ctx=ast.Load())],keywords=[]),node)
            return self.generic_visit(node)
    Change().visit(tree)
    if count!=2:raise RuntimeError('expected exactly two original field digest calls')
    ast.fix_missing_locations(tree);namespace=dict(original.__globals__);namespace['snapshot_digest']=digest
    exec(compile(tree,'<Stage173:immutable_field_digest_only>','exec'),namespace)
    return namespace[original.__name__],ast.unparse(tree)


@contextmanager
def scope(api,expected_metadata):
    original_load,original_execute=api.fields.load,api.execute
    cache={};dependencies={}
    for value in expected_metadata.values():
        if isinstance(value,dict) and set(['path','sha256'])<=value.keys():dependencies[value['path']]=value['sha256']
    api.verify_mapping(dependencies)
    def load(seed,flow_factor=1.,cpd=2,**kwargs):
        if (seed,flow_factor,cpd)!=(2,1.,6) or kwargs:raise RuntimeError('outside frozen CPD6 snapshot domain')
        if not cache:
            started=time.perf_counter();field,data,metadata=original_load(seed,flow_factor,cpd)
            stats['loads']+=1;stats['load_seconds']+=time.perf_counter()-started
            api.require(metadata==expected_metadata,'pinned field metadata drift')
            started=time.perf_counter();immutable=copy.copy(field);hashes={}
            for key,value in field.__dict__.items():
                if isinstance(value,np.ndarray):
                    array,digest=freeze(value);setattr(immutable,key,array);hashes['field.'+key]=digest
            fixed={}
            for key,value in data.items():
                if not isinstance(value,np.ndarray):raise RuntimeError('unexpected geometry object')
                fixed[key],hashes['data.'+key]=freeze(value)
            cache.update(field=immutable,data=fixed,metadata=copy.deepcopy(metadata),hashes=hashes,
                         u_shape=immutable.u.shape,u_dtype=immutable.u.dtype.str,u_strides=immutable.u.strides)
            stats['snapshot_seconds']+=time.perf_counter()-started
        else:stats['hits']+=1
        # Copies of the small containers isolate incidental per-call attributes.
        return copy.copy(cache['field']),dict(cache['data']),copy.deepcopy(cache['metadata'])
    def digest(field):
        if not cache:raise RuntimeError('field snapshot not initialized')
        u=field.u;reference=cache['field'].u
        if (u is not reference or u.shape!=cache['u_shape'] or u.dtype.str!=cache['u_dtype']
            or u.strides!=cache['u_strides'] or u.flags.writeable or not isinstance(owner(u),bytes)):
            raise RuntimeError('immutable snapshot identity or storage changed')
        stats['digest_hits']+=1
        return cache['hashes']['field.u']
    replacement,source=execute_adapter(original_execute,digest)
    api.fields.load,api.execute=load,replacement
    try:
        yield {'cache':cache,'load':load,'digest':digest,'generated_source':source}
    finally:
        api.fields.load,api.execute=original_load,original_execute
        if cache:
            for key,expected in cache['hashes'].items():
                group,name=key.split('.',1)
                array=getattr(cache['field'],name) if group=='field' else cache['data'][name]
                api.require(not array.flags.writeable and isinstance(owner(array),bytes),'snapshot ownership at exit')
                api.require(hashlib.sha256(array.tobytes(order='C')).hexdigest()==expected,'full snapshot hash at exit')
        api.verify_mapping(dependencies)
