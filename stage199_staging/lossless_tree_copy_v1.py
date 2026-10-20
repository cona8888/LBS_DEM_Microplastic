"""Private exact reconstruction copy; no evidence, hash or check is skipped.

Only plain JSON containers/atoms get a narrow memo-preserving copy. All other
types use original deepcopy. No global copy module is changed and no read data
or reconstructed bytes are cached between calls. The original reader remains
the independent reference. Not qualified until the separate tests pass.
"""
from pathlib import Path
from types import SimpleNamespace
import copy,importlib.util,sys
ROOT=Path(__file__).resolve().parents[1]
source=Path(__file__).with_name('transaction_json_memo_v1.py')
spec=importlib.util.spec_from_file_location('_stage199_tree_copy_memo',source)
memo_storage=importlib.util.module_from_spec(spec);sys.modules[spec.name]=memo_storage;spec.loader.exec_module(memo_storage)
base,codec,instance=memo_storage.base,memo_storage.codec,memo_storage.instance
raw_bytes=memo_storage.raw_bytes
ATOMIC=(type(None),bool,int,float,str)

def tree_copy(value):
    memo={}
    def clone(x):
        t=type(x)
        if t in ATOMIC:return x
        key=id(x)
        if key in memo:return memo[key]
        if t is list:
            out=[];memo[key]=out
            out.extend(y if type(y) in ATOMIC else clone(y) for y in x)
            return out
        if t is dict:
            out={};memo[key]=out
            for k,v in x.items():
                # Match original deepcopy assignment order: value before key.
                val=v if type(v) in ATOMIC else clone(v)
                new_key=k if type(k) in ATOMIC else clone(k)
                out[new_key]=val
            return out
        return copy.deepcopy(x,memo)
    return clone(value)

copy_proxy=SimpleNamespace(**vars(copy));copy_proxy.deepcopy=tree_copy
instance.copy=copy_proxy

def verify_bindings():
    memo_storage.verify_bindings()
    assert instance.unpack.__globals__['copy'] is copy_proxy
    assert copy_proxy.deepcopy is tree_copy and copy.deepcopy is not tree_copy
    assert instance.unpack.__code__==memo_storage.original.unpack.__code__

def __getattr__(name):return getattr(memo_storage,name)

verify_bindings()
