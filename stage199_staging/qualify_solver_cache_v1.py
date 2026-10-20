"""Zero-step full optimizer/physical checks of intra-call memo candidate."""
from pathlib import Path
from types import FunctionType
import sys
import numpy as np
import exact_solver_cache_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import qualify_direct_trf_v1 as tests
import qualify_solver_brackets_v1 as previous
api,job=tests.api,tests.job
WORK=previous.WORK
DESIGN=WORK.with_name('solver_cache_01.json');OUT=previous.OUT.with_name('solver_cache_01')
ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__),Path(candidate.batch.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT/'results.json',previous.OUT.parent/'bracket_helper_edges_01.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 exact intra-call scalar memo',recovery_steps_before=56666,
        mode_meanings={'baseline':'constant arithmetic and original SciPy wrapper','direct':'Stage199 bracket bookkeeping','compiled_direct':'same plus per-stick 256-entry exact-scalar-bit memo'},
        helper_criteria='Full optimizer, scalar evaluation accounting, outer velocity and health identical. No reuse between modes or poses; scalar budget checks before lookup; vector-grid calls not cached.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('CACHE_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
        candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1));ns['run']()
    else:raise ValueError('prepare | run')
