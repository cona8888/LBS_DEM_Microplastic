"""Lossless intra-write JSON reuse for unchanged top-level evidence objects.

The frozen encoder/packer only shallow-copy the selected fields; they never
mutate them. Cache lifetime is ONE synchronous write, never a second record,
particle step, reader or process. Original independent readers still rehash
all reconstructed bytes. Cache is capped at128MiB, with normal encoding beyond.
"""
from pathlib import Path
from types import SimpleNamespace,FunctionType
from contextvars import ContextVar
import importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage198_staging'),str(ROOT/'stage194_staging')]
import canonical_json_native_v1 as native
import numpy as np
source=ROOT/'stage198_staging/fast_storage_v1.py'
spec=importlib.util.spec_from_file_location('_stage199_transaction_json_memo_v1',source)
prior=importlib.util.module_from_spec(spec);sys.modules[spec.name]=prior;spec.loader.exec_module(prior)
base,original,previous,instance,codec=prior.base,prior.original,prior.previous,prior.instance,prior.codec
LIMIT=128*1024**2
FIELDS=('spec','rows','early_attempts','repairs','backend_calls','certificates','sweep_certificates','fallback_systems','contact_trial_trace')
_active=ContextVar('stage199_one_write_json',default=None)
last_stats=None

def ordinary(value,default):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=True,ensure_ascii=True,default=default).encode('utf-8')

def compact(value,default):
    state=_active.get()
    if state is None:return ordinary(value,default)
    key=id(value)
    if key in state['eligible'] and state['eligible'][key] is value:
        if key in state['cached']:
            data=state['cached'][key];state['hits']+=1;state['reused_bytes']+=len(data);return data
        data=ordinary(value,default)
        if len(data)<=LIMIT-state['bytes']:
            state['cached'][key]=data;state['bytes']+=len(data)
        return data
    if type(value) is dict and all(type(k) is str for k in value):
        # Descend only through envelope structure. Everything else remains one
        # standard-library C-encoder call, including cycles/default conversions.
        pieces=[]
        for k in sorted(value):
            child=value[k]
            encoded=compact(child,default) if k in FIELDS or k in ('payload','packed_envelope') else ordinary(child,default)
            pieces.append(ordinary(k,default)+b':'+encoded)
        return b'{'+b','.join(pieces)+b'}'
    return ordinary(value,default)

def dumps(value,default):
    data=compact(value,default)
    return native.expand(np.frombuffer(data,dtype=np.uint8)).tobytes()

canonical=SimpleNamespace(dumps=dumps)
prior.canonical=canonical
raw_bytes=prior.raw_bytes
write_base=SimpleNamespace(**vars(previous.write_record.__globals__['base']))
def compact_wire(record):return compact(record,base.api.frozen.h.json_value)+b'\n'
write_base.raw_bytes=compact_wire
wire_writer=FunctionType(previous.write_record.__code__,{**previous.write_record.__globals__,'base':write_base},previous.write_record.__name__,previous.write_record.__defaults__,previous.write_record.__closure__)
instance.base.write_record=wire_writer
original_write=codec.write_record

def write_record(path,record,prefix=None):
    global last_stats
    if _active.get() is not None:raise RuntimeError('one synchronous evidence write required')
    eligible={id(record[k]):record[k] for k in FIELDS if k in record and type(record[k]) in (dict,list,tuple)}
    state={'eligible':eligible,'cached':{},'bytes':0,'hits':0,'reused_bytes':0}
    token=_active.set(state)
    try:return original_write(path,record,prefix)
    finally:
        last_stats={k:state[k] for k in ('bytes','hits','reused_bytes')};_active.reset(token)

codec.write_record=write_record
def verify_bindings():
    assert _active.get() is None
    assert codec.write_record is write_record and original_write.__code__==original.codec.write_record.__code__
    assert wire_writer.__code__==previous.write_record.__code__ and write_base.raw_bytes is compact_wire
    assert instance.base.write_record is wire_writer and codec.base.write_record is instance.write_envelope and codec.base.read_record is instance.read_envelope
    assert instance.unpack.__code__==original.unpack.__code__
    assert prior.canonical is canonical and codec.base.raw_bytes is raw_bytes and instance.base.raw_bytes is raw_bytes
    for name in ('encode','decode','validate_prefix','read_record'):
        assert getattr(codec,name).__code__==getattr(original.codec,name).__code__
verify_bindings()
