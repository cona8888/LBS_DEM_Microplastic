"""Lossless native canonical codec with exact built-in-tree equality factoring."""
from pathlib import Path
import importlib.util,math,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage198_staging'),str(ROOT/'stage194_staging')]
import canonical_json_native_v1 as canonical
source=ROOT/'stage198_staging/fast_storage_v1.py'
spec=importlib.util.spec_from_file_location('_stage199_native_factor_storage_v1',source)
prior=importlib.util.module_from_spec(spec);sys.modules[spec.name]=prior;spec.loader.exec_module(prior)
prior.canonical=canonical
base,original,previous,instance,codec=prior.base,prior.original,prior.previous,prior.instance,prior.codec
raw_bytes=prior.raw_bytes

def native_tree(x,active):
    t=type(x)
    if t in (float,int,bool,str,type(None)):return True
    if t not in (dict,list,tuple) or id(x) in active:return False
    if t is dict and any(type(k) is not str for k in x):return False
    active.add(id(x))
    try:return all(native_tree(v,active) for v in (x.values() if t is dict else x))
    finally:active.remove(id(x))

def tree_equal(a,b):
    ta,tb=type(a),type(b)
    if ta in (list,tuple) and tb in (list,tuple):
        return len(a)==len(b) and all(tree_equal(x,y) for x,y in zip(a,b))
    if ta is not tb:return False
    if ta is dict:return a.keys()==b.keys() and all(tree_equal(v,b[k]) for k,v in a.items())
    if ta is float:return (math.isnan(a) and math.isnan(b)) or (a==b and (a!=0. or math.copysign(1.,a)==math.copysign(1.,b)))
    return a==b

def equivalent(a,b):
    if native_tree(a,set()) and native_tree(b,set()):return tree_equal(a,b)
    # Preserve original default conversion, circular errors and key semantics.
    return raw_bytes(a)==raw_bytes(b)

instance.__dict__['_equivalent']=equivalent
def verify_bindings():
    prior.verify_bindings()
    assert prior.canonical is canonical and raw_bytes.__globals__['canonical'] is canonical
    assert instance.__dict__['_equivalent'] is equivalent
verify_bindings()
