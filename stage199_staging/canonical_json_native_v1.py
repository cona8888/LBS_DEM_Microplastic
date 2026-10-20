"""Exact JSON canonical whitespace expansion using compiled byte copying.

The original standard-library C encoder supplies every token, float spelling,
sorted key and escape. Native loops only copy bytes and insert indentation.
No floating-point arithmetic or scientific data transformation occurs here.
"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage196_staging'))
import compiled_analytic_pair_v3 as environment
import numpy as np
njit=environment.numba.njit

@njit(cache=True,fastmath=False,parallel=False)
def expanded_size(data):
    size=len(data)+1;depth=0;quoted=False;escaped=False
    for i in range(len(data)):
        c=data[i]
        if quoted:
            if escaped:escaped=False
            elif c==92:escaped=True
            elif c==34:quoted=False
        elif c==34:quoted=True
        elif c==123 or c==91:
            depth+=1
            if i+1<len(data) and data[i+1]!=125 and data[i+1]!=93:size+=1+2*depth
        elif c==125 or c==93:
            depth-=1
            if i==0 or (data[i-1]!=123 and data[i-1]!=91):size+=1+2*depth
        elif c==44:size+=1+2*depth
        elif c==58:size+=1
    if depth!=0 or quoted or escaped:raise ValueError('unbalanced compact JSON')
    return size

@njit(cache=True,fastmath=False,parallel=False)
def expand(data):
    out=np.empty(expanded_size(data),dtype=np.uint8);n=0;depth=0;quoted=False;escaped=False
    for i in range(len(data)):
        c=data[i]
        if quoted:
            out[n]=c;n+=1
            if escaped:escaped=False
            elif c==92:escaped=True
            elif c==34:quoted=False
        elif c==34:
            out[n]=c;n+=1;quoted=True
        elif c==123 or c==91:
            out[n]=c;n+=1;depth+=1
            if i+1<len(data) and data[i+1]!=125 and data[i+1]!=93:
                out[n]=10;n+=1
                for _ in range(2*depth):out[n]=32;n+=1
        elif c==125 or c==93:
            depth-=1
            if i==0 or (data[i-1]!=123 and data[i-1]!=91):
                out[n]=10;n+=1
                for _ in range(2*depth):out[n]=32;n+=1
            out[n]=c;n+=1
        elif c==44:
            out[n]=44;out[n+1]=10;n+=2
            for _ in range(2*depth):out[n]=32;n+=1
        elif c==58:out[n]=58;out[n+1]=32;n+=2
        else:out[n]=c;n+=1
    out[n]=10;n+=1
    if n!=len(out):raise ValueError('canonical byte count mismatch')
    return out

def dumps(value,default):
    text=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=True,ensure_ascii=True,default=default)
    return expand(np.frombuffer(text.encode('utf-8'),dtype=np.uint8)).tobytes()
