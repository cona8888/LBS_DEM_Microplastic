"""Compact only the transport wrapper; reconstruct original canonical bytes.

The original logical-record and envelope hashes still use frozen pretty JSON.
Only the already-factored outer wrapper uses the standard library C encoder's
compact JSON. All fields and floating values are retained. Existing readers
validate the new stream's seals and then the original reconstructed hashes.
"""
from pathlib import Path
from types import SimpleNamespace, FunctionType
import importlib.util
import json
import sys
import lossless_fast_xz_v1 as previous
base=previous.base


def compact_bytes(record):
    return (json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=True,default=base.api.frozen.h.json_value)+'\n').encode('utf-8')


write_base=SimpleNamespace(**vars(base));write_base.raw_bytes=compact_bytes
write_record=FunctionType(previous.write_record.__code__,{**previous.write_record.__globals__,'base':write_base},
                          'write_record',previous.write_record.__defaults__,previous.write_record.__closure__)
spec=importlib.util.spec_from_file_location('_stage196_compact_trial_codec',previous.original.__file__)
instance=importlib.util.module_from_spec(spec);sys.modules[spec.name]=instance;spec.loader.exec_module(instance)
instance.base=SimpleNamespace(**vars(base));instance.base.write_record=write_record
codec=instance.codec
original=previous.original


def verify_bindings():
    assert write_record.__code__ is previous.write_record.__code__
    assert write_record.__globals__['base'].raw_bytes is compact_bytes
    assert instance.base.raw_bytes is base.raw_bytes
    assert instance.base.read_record is base.read_record
    assert instance.pack.__code__==original.pack.__code__
    assert instance.unpack.__code__==original.unpack.__code__
    assert codec.base.write_record is instance.write_envelope
    assert codec.base.read_record is instance.read_envelope
    for name in ('encode','decode','validate_prefix','write_record','read_record'):
        assert getattr(codec,name).__code__==getattr(original.codec,name).__code__


verify_bindings()
