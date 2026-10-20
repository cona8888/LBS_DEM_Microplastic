"""Lossless ancillary JSON documents via the qualified reversible archive.

Future receipts can retain their complete audit details through an explicit
small reference. This does not delete or rewrite any prior evidence. Original
JSON bytes and semantic object digest are independently checked on every read.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import numeric_archive_v1 as archive

FORMAT='dem-json-document-reference-v1'


def build(codec, api):
    wire=archive.build(codec,preset=9)
    leaf=wire.base.write_record.__globals__['base'].write_record
    def write_bytes(path,raw,design):
        settings=SimpleNamespace(**{**vars(leaf.__globals__['base']), 'raw_bytes':lambda record:raw})
        writer=archive.clone(leaf,{**leaf.__globals__,'base':settings})
        return writer(path,dict(design_sha256=design))
    def store(path,value,design):
        path=Path(path);payload=path.with_name(path.stem+'.payload.json.xz')
        if path.exists() or payload.exists():raise FileExistsError('Exclusive document/reference')
        raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=True,default=api.frozen.h.json_value)+'\n').encode()
        seal=write_bytes(payload,raw,design)
        restored=wire.base.read_bytes(payload,design)
        if restored!=raw or api.digest(json.loads(restored))!=api.digest(value):raise RuntimeError('Original complete document not restored')
        ref=dict(format=FORMAT,payload=str(payload.resolve()),design_sha256=design,
                 original_json_sha256=seal['uncompressed_sha256'],document_sha256=api.digest(value))
        if isinstance(value,dict) and 'passed' in value:ref['passed']=value['passed']
        api.write(path,ref)
        return ref
    def read(path):
        path=Path(path);value=api.read(path)
        if not isinstance(value,dict) or value.get('format')!=FORMAT:return value
        expected=path.with_name(path.stem+'.payload.json.xz').resolve()
        if Path(value['payload']).resolve()!=expected:raise ValueError('Explicit same-directory payload only')
        seal=api.read(expected.with_suffix('.seal.json'))
        if seal['uncompressed_sha256']!=value['original_json_sha256']:raise ValueError('Original document-byte identity')
        result=json.loads(wire.base.read_bytes(expected,value['design_sha256']))
        if api.digest(result)!=value['document_sha256']:raise ValueError('Original document semantic identity')
        if 'passed' in value and value['passed']!=result['passed']:raise ValueError('Reference cannot promote original result')
        return result
    return SimpleNamespace(store=store,read=read,wire=wire)
