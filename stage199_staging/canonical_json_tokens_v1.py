"""Standard-library compact C encoding plus lossless indentation of tokens.

Strings, numeric spellings, sorted key order and default handling come from
the same JSON implementation as the original canonical form. This private
formatter touches only structural characters outside quoted JSON strings.
"""
import json, re

TOKENS=re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|[{}\[\],:]')

def dumps(value,default):
    compact=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=True,ensure_ascii=True,default=default)
    pieces=[];append=pieces.append;depth=0;cursor=0;indents=[''];last=''
    for match in TOKENS.finditer(compact):
        start,end=match.span();token=match.group()
        if start>cursor:append(compact[cursor:start])
        if token[0]=='"':append(token)
        elif token in ('{','['):
            append(token);depth+=1
            if len(indents)<=depth:indents.append('  '*depth)
            if compact[end:end+1] not in ('}',']'):append('\n'+indents[depth])
        elif token in ('}',']'):
            depth-=1
            if compact[start-1:start] not in ('{','['):append('\n'+indents[depth])
            append(token)
        elif token==',':append(',\n'+indents[depth])
        elif token==':':append(': ')
        cursor=end;last=token
    append(compact[cursor:]);append('\n')
    if depth:raise ValueError('unbalanced canonical token stream')
    return ''.join(pieces).encode('utf-8')
