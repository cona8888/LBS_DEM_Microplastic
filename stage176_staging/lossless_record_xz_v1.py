"""Exclusive, sealed XZ records. Same JSON bytes as Stage165; no rounding.

One XZ stream only; CRC64 plus independent compressed/uncompressed SHA256.
Unsealed partial writes are retained and never silently accepted or replaced.
"""
from pathlib import Path
import hashlib,json,lzma,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage165_staging'))
import transport_budget_io_v1 as legacy
api=legacy.api
FORMAT='dem-json-xz-v1'
MAX_RAW=512*1024**2
MAX_COMPRESSED=128*1024**2
MEMLIMIT=256*1024**2
RESERVE=20*1024**3
CHUNK=1024**2


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(CHUNK),b''):h.update(chunk)
    return h.hexdigest()


def raw_bytes(record):
    return (json.dumps(record,sort_keys=True,indent=2,allow_nan=True,default=api.frozen.h.json_value)+'\n').encode('utf-8')


def validate_path(path):
    path=Path(path)
    if not path.name.endswith('.json.xz'):raise ValueError('explicit .json.xz suffix required')
    return path,path.with_suffix('.seal.json')


def write_record(path,record):
    path,sealpath=validate_path(path)
    if path.exists() or sealpath.exists():raise FileExistsError('immutable record or seal already exists')
    design=record['design_sha256']
    if not isinstance(design,str) or len(design)!=64 or any(c not in '0123456789abcdef' for c in design):raise ValueError('SHA256 design required')
    data=raw_bytes(record)
    if len(data)>MAX_RAW:raise ValueError('raw record resource ceiling')
    if shutil.disk_usage(path.parent).free<RESERVE+MAX_COMPRESSED:raise RuntimeError('disk reserve before evidence write')
    compressor=lzma.LZMACompressor(format=lzma.FORMAT_XZ,check=lzma.CHECK_CRC64,preset=9)
    h=hashlib.sha256();written=0
    with path.open('xb') as stream:
        for offset in range(0,len(data),CHUNK):
            encoded=compressor.compress(data[offset:offset+CHUNK]);stream.write(encoded);h.update(encoded);written+=len(encoded)
            if written>MAX_COMPRESSED:raise ValueError('compressed record resource ceiling; partial preserved')
        encoded=compressor.flush();stream.write(encoded);h.update(encoded);written+=len(encoded)
    if written>MAX_COMPRESSED:raise ValueError('compressed record resource ceiling; partial preserved')
    seal={'format':FORMAT,'compression':'XZ/LZMA2 preset9 CRC64','compressed_sha256':h.hexdigest(),
          'uncompressed_sha256':hashlib.sha256(data).hexdigest(),'design_sha256':design,
          'uncompressed_bytes':len(data),'compressed_bytes':written}
    api.write(sealpath,seal)
    return seal


def read_bytes(path,design_sha256):
    path,sealpath=validate_path(path);seal=api.read(sealpath)
    if seal.get('format')!=FORMAT or seal.get('design_sha256')!=design_sha256:raise ValueError('format/design binding')
    for key,limit in [('uncompressed_bytes',MAX_RAW),('compressed_bytes',MAX_COMPRESSED)]:
        if type(seal.get(key)) is not int or not 0<seal[key]<=limit:raise ValueError('record size declaration')
    if path.stat().st_size!=seal['compressed_bytes'] or file_sha(path)!=seal['compressed_sha256']:raise ValueError('compressed seal mismatch')
    decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=MEMLIMIT)
    pieces=[];size=0;h=hashlib.sha256()
    with path.open('rb') as f:
        while True:
            if decoder.eof:
                if decoder.unused_data or f.read(1):raise ValueError('trailing or concatenated stream')
                break
            incoming=f.read(CHUNK) if decoder.needs_input else b''
            if decoder.needs_input and not incoming:raise ValueError('truncated XZ stream')
            data=decoder.decompress(incoming,max_length=min(CHUNK,seal['uncompressed_bytes']-size+1))
            size+=len(data)
            if size>seal['uncompressed_bytes']:raise ValueError('decompressed resource ceiling')
            pieces.append(data);h.update(data)
    if decoder.check!=lzma.CHECK_CRC64:raise ValueError('required CRC64 missing')
    if size!=seal['uncompressed_bytes'] or h.hexdigest()!=seal['uncompressed_sha256']:raise ValueError('uncompressed seal mismatch')
    return b''.join(pieces)


def read_record(path,design_sha256):
    record=json.loads(read_bytes(path,design_sha256))
    if not isinstance(record,dict) or record.get('design_sha256')!=design_sha256:raise ValueError('record design binding')
    return record
