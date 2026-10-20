"""Lossless history-prefix encoding layered on the qualified sealed XZ codec.

Diagnostic history is append-only in the unchanged integrator. Store a sealed
prefix reference plus appended rows instead of repeating the complete history.
The reader restores the ORIGINAL canonical JSON bytes and checks their hash.
No history row, float bit, raw trace, proof, or checkpoint field is discarded.
Readers require an explicit verified prefix state; no implicit path traversal.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage176_staging'))
import lossless_record_xz_v1 as base
api=base.api
ENCODING='dem-history-prefix-v1'


def packed_history(rows):
    return json.dumps(rows,separators=(',',':'),allow_nan=True,default=api.frozen.h.json_value).encode('utf-8')


def digest(data):return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class HistoryState:
    path:str
    design_sha256:str
    compressed_sha256:str
    original_sha256:str
    history_sha256:str
    history_length:int
    history_bytes:bytes

    def reference(self):
        return {k:getattr(self,k) for k in ('path','design_sha256','compressed_sha256','original_sha256','history_sha256','history_length')}


def validate_prefix(prefix,design):
    if type(prefix) is not HistoryState or type(prefix.history_bytes) is not bytes:raise ValueError('explicit immutable history state required')
    if prefix.design_sha256!=design or digest(prefix.history_bytes)!=prefix.history_sha256:raise ValueError('prefix bytes/design binding')
    path=Path(prefix.path);s=api.read(path.with_suffix('.seal.json'))
    if s['compressed_sha256']!=prefix.compressed_sha256:raise ValueError('prefix archive changed')
    envelope=base.read_record(path,design)
    if envelope.get('evidence_encoding')!=ENCODING:raise ValueError('prefix encoding')
    if (envelope['original_uncompressed_sha256']!=prefix.original_sha256 or envelope['history']['sha256']!=prefix.history_sha256
        or envelope['history']['length']!=prefix.history_length):raise ValueError('prefix metadata binding')
    history=json.loads(prefix.history_bytes)
    if not isinstance(history,list) or len(history)!=prefix.history_length:raise ValueError('prefix length')
    return history


def encode(record,prefix=None):
    result=record['result'];cp=result['checkpoint'];state=cp['state'];history=result['history']
    if not isinstance(history,list) or not isinstance(state['history'],list):raise ValueError('history arrays required')
    history_bytes=packed_history(history)
    if history_bytes!=packed_history(state['history']):raise ValueError('two history copies disagree')
    design=record['design_sha256'];parent_rows=[]
    if prefix is not None:
        parent_rows=validate_prefix(prefix,design)
        if len(history)<len(parent_rows) or packed_history(history[:len(parent_rows)])!=prefix.history_bytes:raise ValueError('history is not an exact append-only extension')
    # Shallow copies only: never mutate input record or physical state.
    payload=dict(record);out_result=dict(result);out_cp=dict(cp);out_state=dict(state)
    del out_state['history'];del out_result['history'];out_cp['state']=out_state;out_result['checkpoint']=out_cp;payload['result']=out_result
    raw=base.raw_bytes(record)
    if len(raw)>base.MAX_RAW:raise ValueError('original record resource ceiling')
    envelope={'design_sha256':design,'evidence_encoding':ENCODING,'original_uncompressed_sha256':digest(raw),'original_uncompressed_bytes':len(raw),
              'history':{'length':len(history),'sha256':digest(history_bytes),'prefix':prefix.reference() if prefix else None,'appended_rows':history[len(parent_rows):]},
              'payload':payload}
    return envelope,history_bytes


def make_state(path,envelope,history_bytes,seal):
    return HistoryState(str(Path(path).resolve()),envelope['design_sha256'],seal['compressed_sha256'],envelope['original_uncompressed_sha256'],
                        envelope['history']['sha256'],envelope['history']['length'],history_bytes)


def write_record(path,record,prefix=None):
    envelope,hist=encode(record,prefix);seal=base.write_record(path,envelope)
    return seal,make_state(path,envelope,hist,seal)


def decode(envelope,prefix=None):
    if envelope.get('evidence_encoding')!=ENCODING:raise ValueError('explicit history-prefix encoding required')
    if type(envelope.get('original_uncompressed_bytes')) is not int or not 0<envelope['original_uncompressed_bytes']<=base.MAX_RAW:raise ValueError('original size declaration')
    design=envelope['design_sha256'];meta=envelope['history'];rows=[]
    if meta['prefix'] is None:
        if prefix is not None:raise ValueError('unexpected prefix for standalone record')
    else:
        if prefix is None:raise ValueError('verified prefix state required')
        if prefix.reference()!=meta['prefix']:raise ValueError('wrong prefix record')
        rows=validate_prefix(prefix,design)
    appended=meta['appended_rows']
    if not isinstance(appended,list):raise ValueError('append array required')
    rows=rows+appended;hist=packed_history(rows)
    if type(meta['length']) is not int or len(rows)!=meta['length'] or digest(hist)!=meta['sha256']:raise ValueError('reconstructed history seal')
    payload=envelope['payload']
    if payload.get('design_sha256')!=design:raise ValueError('payload design binding')
    result=dict(payload['result']);cp=dict(result['checkpoint']);state=dict(cp['state'])
    if 'history' in result or 'history' in state:raise ValueError('ambiguous stored history')
    state['history']=rows;cp['state']=state;result['checkpoint']=cp;result['history']=rows
    record=dict(payload);record['result']=result;raw=base.raw_bytes(record)
    if len(raw)!=envelope['original_uncompressed_bytes'] or digest(raw)!=envelope['original_uncompressed_sha256']:raise ValueError('original canonical evidence bytes not restored')
    return record,hist


def read_record(path,design_sha256,prefix=None):
    envelope=base.read_record(path,design_sha256);record,hist=decode(envelope,prefix)
    state=make_state(path,envelope,hist,api.read(Path(path).with_suffix('.seal.json')))
    return record,state
