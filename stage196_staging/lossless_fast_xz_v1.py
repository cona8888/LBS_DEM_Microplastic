"""Storage-only XZ preset1 writer, with the original bounded reader.

Canonical JSON bytes, failed-trial factoring, history reconstruction, and every
seal/size/reserve check are retained. No numerical module is patched.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import lzma
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage194_staging'))
import lossless_trial_references_v2 as original
base = original.base
PRESET = 1


def write_record(path, record):
    path, sealpath = base.validate_path(path)
    if path.exists() or sealpath.exists():
        raise FileExistsError('immutable record or seal already exists')
    design = record['design_sha256']
    if not isinstance(design, str) or len(design) != 64 or any(c not in '0123456789abcdef' for c in design):
        raise ValueError('SHA256 design required')
    data = base.raw_bytes(record)
    if len(data) > base.MAX_RAW:
        raise ValueError('raw record resource ceiling')
    if shutil.disk_usage(path.parent).free < base.RESERVE + base.MAX_COMPRESSED:
        raise RuntimeError('disk reserve before evidence write')
    compressor = lzma.LZMACompressor(format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=PRESET)
    h = hashlib.sha256(); written = 0
    with path.open('xb') as stream:
        for offset in range(0, len(data), base.CHUNK):
            encoded = compressor.compress(data[offset:offset+base.CHUNK])
            stream.write(encoded); h.update(encoded); written += len(encoded)
            if written > base.MAX_COMPRESSED:
                raise ValueError('compressed record resource ceiling; partial preserved')
        encoded = compressor.flush()
        stream.write(encoded); h.update(encoded); written += len(encoded)
        stream.flush(); os.fsync(stream.fileno())
    if written > base.MAX_COMPRESSED:
        raise ValueError('compressed record resource ceiling; partial preserved')
    seal = {'format': base.FORMAT, 'compression': 'XZ/LZMA2 preset1 CRC64',
            'compressed_sha256': h.hexdigest(), 'uncompressed_sha256': hashlib.sha256(data).hexdigest(),
            'design_sha256': design, 'uncompressed_bytes': len(data), 'compressed_bytes': written}
    base.api.write(sealpath, seal)
    return seal


# Private codec instances only. Original frozen writer and all readers stay intact.
spec = importlib.util.spec_from_file_location('_stage196_fast_trial_codec', original.__file__)
instance = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = instance; spec.loader.exec_module(instance)
instance.base = SimpleNamespace(**vars(base))
instance.base.write_record = write_record
codec = instance.codec


def verify_bindings():
    assert instance.pack.__code__ == original.pack.__code__
    assert instance.unpack.__code__ == original.unpack.__code__
    assert instance.base.read_bytes is base.read_bytes
    assert instance.base.read_record is base.read_record
    assert instance.base.raw_bytes is base.raw_bytes
    assert instance.base.write_record is write_record
    assert codec.base.write_record is instance.write_envelope
    assert codec.base.read_record is instance.read_envelope
    for name in ('encode', 'decode', 'validate_prefix', 'write_record', 'read_record'):
        assert getattr(codec, name).__code__ == getattr(original.codec, name).__code__
    assert original.base.write_record is base.write_record


verify_bindings()
