"""Prospective exclusive XZ wire adapter with original JSON-byte reconstruction.

Original history/trial-reference encoders, decoders and numerical code remain
unchanged. The lower archive preserves the original JSON SHA and byte count,
adds a separately hashed reversible token stream, and accepts old archives.
This module does not install itself or confer numerical dispatch authority.
"""
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
import hashlib, lzma
import numeric_token_codec_v1 as token

FORMAT = 'dem-json-f64-token-xz-v1'


def clone(fn, namespace):
    return FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)


def build(codec, preset=1):
    oldbase = codec.base
    leaf = oldbase.write_record.__globals__['base']
    oldwriter = leaf.write_record
    originals = oldwriter.__globals__
    wire_base = originals['base']
    if originals['PRESET'] != 1 or preset not in (1,6,9):
        raise RuntimeError('Original preset1 writer and explicit bounded storage setting required')
    original_reader = oldbase.read_bytes
    stats = {}

    class Compressor:
        def __init__(self, **kwargs):
            if kwargs != dict(format=lzma.FORMAT_XZ,check=lzma.CHECK_CRC64,preset=preset):
                raise RuntimeError('Original XZ settings required')
            self.chunks = []
        def compress(self, data):
            self.chunks.append(data)
            return b''
        def flush(self):
            raw = b''.join(self.chunks); self.chunks.clear()
            if len(raw) > oldbase.MAX_RAW: raise ValueError('Original raw ceiling')
            transformed, count = token.encode(raw)
            if token.decode(transformed, len(raw)) != raw: raise RuntimeError('Exact original wire-byte reconstruction')
            stats.clear(); stats.update(transformed_bytes=len(transformed),
                transformed_sha256=hashlib.sha256(transformed).hexdigest(), numeric_tokens=count)
            return lzma.compress(transformed,format=lzma.FORMAT_XZ,check=lzma.CHECK_CRC64,preset=preset)

    def write_seal(path, body):
        if body.get('format') != FORMAT or not stats: raise ValueError('Explicit new archive seal')
        body = dict(body, compression=f'XZ/LZMA2 preset{preset} CRC64 with reversible f64 tokens',
                    numeric_token_transform='finite-repr-f64-little-endian-v1', **stats)
        return wire_base.api.write(path, body)

    proxy = SimpleNamespace(**{**vars(wire_base.api), 'write': write_seal})
    lzma_proxy = SimpleNamespace(**{**vars(lzma), 'LZMACompressor': Compressor})
    settings = SimpleNamespace(**{**vars(wire_base), 'FORMAT': FORMAT, 'api': proxy})
    wire_writer = clone(oldwriter, {**originals, 'base': settings, 'lzma': lzma_proxy, 'PRESET': preset})

    def read_bytes(path, design):
        path, sealpath = oldbase.validate_path(path)
        seal = oldbase.api.read(sealpath)
        if seal.get('format') == wire_base.FORMAT:
            return original_reader(path, design)
        if seal.get('format') != FORMAT or seal.get('design_sha256') != design:
            raise ValueError('New archive format/design binding')
        if seal.get('numeric_token_transform') != 'finite-repr-f64-little-endian-v1':
            raise ValueError('Unknown reversible transform')
        for key, limit in (('uncompressed_bytes',oldbase.MAX_RAW), ('compressed_bytes',oldbase.MAX_COMPRESSED),
                           ('transformed_bytes',oldbase.MAX_RAW)):
            if type(seal.get(key)) is not int or not 0 < seal[key] <= limit: raise ValueError('Original size ceiling')
        if seal['transformed_bytes'] > seal['uncompressed_bytes']: raise ValueError('Transform grew original data')
        if path.stat().st_size != seal['compressed_bytes'] or oldbase.file_sha(path) != seal['compressed_sha256']:
            raise ValueError('Compressed archive seal')
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=oldbase.MEMLIMIT)
        parts = []; size = 0
        with path.open('rb') as stream:
            while True:
                if decoder.eof:
                    if decoder.unused_data or stream.read(1): raise ValueError('Trailing/concatenated stream')
                    break
                incoming = stream.read(oldbase.CHUNK) if decoder.needs_input else b''
                if decoder.needs_input and not incoming: raise ValueError('Truncated XZ stream')
                data = decoder.decompress(incoming,max_length=min(oldbase.CHUNK,seal['transformed_bytes']-size+1))
                size += len(data)
                if size > seal['transformed_bytes']: raise ValueError('Transformed byte ceiling')
                parts.append(data)
        packed = b''.join(parts)
        if decoder.check != lzma.CHECK_CRC64 or size != seal['transformed_bytes'] or hashlib.sha256(packed).hexdigest() != seal['transformed_sha256']:
            raise ValueError('Transformed CRC/size/SHA seal')
        raw = token.decode(packed,seal['uncompressed_bytes'])
        if len(raw) != seal['uncompressed_bytes'] or hashlib.sha256(raw).hexdigest() != seal['uncompressed_sha256']:
            raise ValueError('Original JSON byte-size/SHA seal')
        return raw

    newleaf = SimpleNamespace(**{**vars(leaf), 'write_record': wire_writer, 'read_bytes': read_bytes})
    pack_writer = clone(oldbase.write_record, {**oldbase.write_record.__globals__, 'base': newleaf})
    fresh = oldbase.read_record.__globals__['fresh_reader']
    fresh = clone(fresh, {**fresh.__globals__, 'read_bytes': read_bytes})
    pack_reader = clone(oldbase.read_record, {**oldbase.read_record.__globals__, 'fresh_reader': fresh})
    newbase = SimpleNamespace(**{**vars(oldbase), 'write_record': pack_writer, 'read_record': pack_reader, 'read_bytes': read_bytes})
    result = ModuleType('_paper1_numeric_archive_prefix'); result.__dict__.update(vars(codec)); result.base = newbase
    for name, fn in vars(codec).items():
        if isinstance(fn, FunctionType) and fn.__globals__ is vars(codec):
            setattr(result, name, clone(fn, vars(result)))
    wrapper = codec.write_record
    prefix_writer = clone(wrapper.__globals__['original_write'], vars(result))
    result.write_record = clone(wrapper, {**wrapper.__globals__, 'original_write': prefix_writer})
    # Original unpacking, prefix validation, canonical-byte and complete-history
    # checks are actual consumers, not a separate approximate reconstruction.
    for name in ('encode','decode','validate_prefix','read_record','make_state'):
        if getattr(result,name).__code__ is not getattr(codec,name).__code__: raise RuntimeError('Original history code')
    if wire_writer.__code__ is not oldwriter.__code__ or pack_writer.__code__ is not oldbase.write_record.__code__:
        raise RuntimeError('Original exclusive writer/trial-reference code')
    return result
