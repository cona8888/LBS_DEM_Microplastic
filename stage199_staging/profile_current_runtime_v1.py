"""Repeat the zero-step attribution with the exact Stage199 candidates."""
from pathlib import Path
from types import FunctionType
import exact_trf_helpers_v1 as candidate
import native_factor_storage_v1 as storage
import profile_runtime_storage_v1 as prior
ROOT=prior.ROOT;api,job=prior.api,prior.job
DESIGN=prior.DESIGN.with_name('current_profile_01.json')
RUN=prior.RUN.with_name('current_profile_01');OUT=prior.OUT.with_name('current_profile_01')
ns={**prior.__dict__,'candidate':candidate,'storage':storage,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'__file__':__file__}
for name in ('verify','run'):
    f=getattr(prior,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(prior.DESIGN);prior.verify(p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    files=[Path(__file__),Path(candidate.__file__),Path(candidate.batch.__file__),Path(candidate.prior.__file__),Path(storage.__file__),Path(storage.canonical.__file__)]
    for x in files:p['sources'][str(x)]=api.sha(x)
    for name in ('solver_brackets_01','trf_helpers_01','native_factor_01'):
        x=OUT.parent/name/'results.json';r=api.read(x)
        api.require(r['passed'] and api.read(x.parent/'completion.json')['results_sha256']==api.sha(x),'sealed zero-step prerequisite')
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 updated zero-step attribution',recovery_steps_before=56666)
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('CURRENT_PROFILE_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    import sys
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        import numpy as np
        candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
        candidate.column_norms(np.eye(9));candidate.max_abs(np.zeros(9));candidate.all_finite(np.zeros(9));storage.raw_bytes({'warm':0.})
        ns['run']()
    else:raise ValueError('prepare | run')
