"""Reversible float-token transform for original JSON bytes, not a physics codec.

Quoted strings and every other byte are preserved. Only finite JSON floats
whose exact spelling equals Python's binary64 repr and exceeds ten bytes are
replaced by NUL, 'd', and eight little-endian bytes. Valid JSON contains no raw
NUL. No rounding, quantization, object deserialization or force-model change.
"""
import math, re, struct

TOKEN = re.compile(rb'"(?:[^"\\]|\\.)*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+(?:[eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)')
MARKER = b'\x00d'


def encode(raw):
    if not isinstance(raw, bytes) or b'\x00' in raw:
        raise ValueError('Original JSON bytes without raw NUL required')
    chunks = []; cursor = count = 0
    for match in TOKEN.finditer(raw):
        token = match.group()
        if token[0] == 34 or len(token) <= 10:
            continue
        value = float(token)
        if not math.isfinite(value) or repr(value).encode('ascii') != token:
            continue
        chunks.extend((raw[cursor:match.start()], MARKER + struct.pack('<d', value)))
        cursor = match.end(); count += 1
    chunks.append(raw[cursor:])
    packed = b''.join(chunks)
    if len(packed) > len(raw): raise RuntimeError('Transform cannot grow input')
    return packed, count


def decode(packed, maximum_raw_bytes):
    if type(maximum_raw_bytes) is not int or maximum_raw_bytes <= 0:
        raise ValueError('Positive original raw-byte bound required')
    chunks = []; cursor = total = 0
    while True:
        offset = packed.find(b'\x00', cursor)
        if offset < 0:
            tail = packed[cursor:]; total += len(tail)
            if total > maximum_raw_bytes: raise ValueError('Original raw-byte ceiling')
            chunks.append(tail); break
        plain = packed[cursor:offset]
        if packed[offset:offset+2] != MARKER or offset+10 > len(packed):
            raise ValueError('Unknown or truncated numeric token')
        value = struct.unpack('<d', packed[offset+2:offset+10])[0]
        if not math.isfinite(value): raise ValueError('Nonfinite binary token forbidden')
        text = repr(value).encode('ascii')
        if len(text) <= 10: raise ValueError('Noncanonical short numeric token')
        total += len(plain) + len(text)
        if total > maximum_raw_bytes: raise ValueError('Original raw-byte ceiling')
        chunks.extend((plain, text)); cursor = offset+10
    return b''.join(chunks)
