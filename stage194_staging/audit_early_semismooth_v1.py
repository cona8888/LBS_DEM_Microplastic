"""Exact provenance for same-system seeds in the original early guard."""
from pathlib import Path
import hashlib,types
import numpy as np
import audit_semismooth_routes_v1 as prior
require=prior.require;q=prior.q

def early_or_fallback(item,routes):
    if item['health']['solver']!=prior.repair.NAME:return
    require(routes in (['early'],['fallback']),'one explicitly bound same-system route')
    prior.solver(item,None)
    if routes==['early']:
        v=np.asarray(item['vfree']);g=np.asarray(item['gaps_m']);scale=max(np.linalg.norm(v),1e-15)
        require(len(g)==3 and item['friction']>0 and item['dt_s']>0 and np.max(np.abs(g))/item['dt_s']<=1e-5*scale,'original early input guard')
        require(np.linalg.norm(item['velocity'])/scale<=1e-4,'original early outgoing speed guard')

source=prior.source
before="if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME, SEMISMOOTH_NAME):"
after="if item['health']['solver'] in (producer.old.fast.old.NAME, NEW_SOLVER_NAME):"
require(source.count(before)==1,'one exact early/fallback routing edit');source=source.replace(before,after)
before='            if len(gaps):'
after='            early_or_fallback(item, accepted_route)\n'+before
require(source.count(before)==1,'one exact original guard audit insertion');source=source.replace(before,after)
ns={**prior.namespace,'early_or_fallback':early_or_fallback};exec(compile(source,str(Path(__file__))+'::early_guard_only','exec'),ns)
evaluate=ns['evaluate'];STRUCTURAL_IDENTITY={**prior.STRUCTURAL_IDENTITY,'early_guard_checked':True,'revised_source_sha256':hashlib.sha256(source.encode()).hexdigest()}
kernel_ns={**q.job.kernel.evaluate.__globals__,'association':types.SimpleNamespace(evaluate=evaluate)}
kernel=types.FunctionType(q.job.kernel.evaluate.__code__,kernel_ns,'evaluate',q.job.kernel.evaluate.__defaults__,q.job.kernel.evaluate.__closure__)
