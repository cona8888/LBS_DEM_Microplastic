"""Read documented Windows CPU-set efficiency/core metadata; no system changes.

Sources: Microsoft Learn SYSTEM_CPU_SET_INFORMATION and
GetSystemCpuSetInformation. A larger EfficiencyClass denotes a faster class.
"""
import ctypes as ct
from ctypes import wintypes as wt
import struct


def cpu_sets():
    kernel=ct.WinDLL('kernel32',use_last_error=True)
    get=kernel.GetSystemCpuSetInformation
    get.argtypes=[ct.c_void_p,wt.ULONG,ct.POINTER(wt.ULONG),wt.HANDLE,wt.ULONG]
    get.restype=wt.BOOL
    needed=wt.ULONG()
    get(None,0,ct.byref(needed),None,0)
    if not needed.value or needed.value>1024*1024:raise RuntimeError('invalid CPU-set buffer size')
    buf=ct.create_string_buffer(needed.value)
    if not get(buf,needed.value,ct.byref(needed),None,0):raise ct.WinError(ct.get_last_error())
    raw=buf.raw[:needed.value];rows=[];offset=0
    while offset<len(raw):
        size,kind=struct.unpack_from('<II',raw,offset)
        if size<20 or offset+size>len(raw):raise RuntimeError('invalid variable CPU-set structure')
        if kind==0:
            ident,group,logical,core,cache,numa,efficiency,flags=struct.unpack_from('<IHBBBBBB',raw,offset+8)
            rows.append({'id':ident,'group':group,'logical':logical,'core':core,'cache':cache,'numa':numa,
                'efficiency_class':efficiency,'parked':bool(flags&1),'allocated':bool(flags&2),'allocated_to_process':bool(flags&4)})
        offset+=size
    if offset!=len(raw):raise RuntimeError('CPU-set trailing bytes')
    return rows


if __name__=='__main__':
    import json
    print(json.dumps(cpu_sets(),indent=2))
