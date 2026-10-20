"""Bind only the calling process to one verified performance-class core."""
import os
import psutil
from windows_cpu_topology_v1 import cpu_sets


def verify_layout(logicals):
    rows=cpu_sets();maximum=max(x['efficiency_class'] for x in rows)
    selected=[]
    for logical in logicals:
        found=[x for x in rows if x['group']==0 and x['logical']==logical]
        if len(found)!=1 or found[0]['efficiency_class']!=maximum or found[0]['allocated']:
            raise RuntimeError('requested own-worker performance core unavailable')
        selected.append(found[0])
    if len({(x['group'],x['core']) for x in selected})!=len(selected):
        raise RuntimeError('own workers must use distinct physical cores')
    return selected


def bind(logical):
    selected=verify_layout([logical])[0]
    p=psutil.Process();before=p.cpu_affinity();p.cpu_affinity([logical])
    if p.cpu_affinity()!=[logical]:raise RuntimeError('own-process CPU affinity not applied')
    return {'pid':os.getpid(),'original_affinity':before,'current_affinity':[logical],'cpu_set':selected,
            'only_current_process_changed':True,'global_power_settings_changed':False}
