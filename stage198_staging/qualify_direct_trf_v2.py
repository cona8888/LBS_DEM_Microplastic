"""Same frozen held trials, exact full-result criteria; private norm dispatch."""
from types import FunctionType
from pathlib import Path
import sys
import qualify_direct_trf_v1 as prior
import direct_trf_v2 as candidate
DESIGN=prior.DESIGN.with_name('held_protocol_02.json')
OUT=prior.OUT.with_name('held_02')
ns={**prior.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    ns[name]=FunctionType(getattr(prior,name).__code__,ns,name,getattr(prior,name).__defaults__,getattr(prior,name).__closure__)

def prepare():
    p=prior.api.read(prior.DESIGN);prior.verify(p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for path in (Path(__file__),Path(candidate.__file__),Path(prior.__file__)):
        p['sources'][str(path.resolve())]=prior.api.sha(path)
    p['inputs'][str(prior.DESIGN)]=prior.api.sha(prior.DESIGN)
    p['inputs'][str(prior.OUT/'results.json')]=prior.api.sha(prior.OUT/'results.json')
    p['specialization']='NumPy float64 vector norm exact existing dot/sqrt and inf reduction; all TRF and trust-region code objects remain identical.'
    prior.api.require(candidate.trf_no_bounds.__code__ is candidate.prior.trf.trf_no_bounds.__code__ and candidate.trust.__code__ is candidate.prior.trf.solve_lsq_trust_region.__code__,'original optimizer code objects')
    p['binding']=prior.api.digest(p);prior.job.commit(DESIGN,p);print('HELD_V2_PROTOCOL',prior.api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:ns['run']()
    else:raise ValueError('prepare | run')
