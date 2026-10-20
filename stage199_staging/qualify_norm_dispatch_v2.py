"""Repeat exact tests without freezing the live optimizer observer binding."""
from pathlib import Path
from types import FunctionType
import sys,traceback
import exact_norm_dispatch_v2 as candidate
import qualify_norm_dispatch_v1 as previous
api,job,WORK=previous.api,previous.job,previous.WORK
DESIGN=previous.DESIGN.with_name('norm_dispatch_02.json');OUT=previous.OUT.with_name('norm_dispatch_02')
ns={**previous.ns,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(previous.tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)
helper_ns={**previous.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'ns':ns}
f=previous.helpers;helpers=FunctionType(f.__code__,helper_ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__),Path(previous.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT/'failure.json',previous.OUT.parent/'norm_helper_edges_01.json'):
        p['inputs'][str(x)]=api.sha(x)
    # Static, zero-step confirmation: v1 snapshots the optimizer dispatch,
    # whereas the test installs its observer later into the live module.
    with candidate.previous.scope('compiled_direct'):
        v1_snapshots_optimizer=candidate.repair.prior.solve.__globals__ is not vars(candidate.repair.prior) and candidate.repair.prior.solve.__globals__['least_squares'] is candidate.repair.prior.least_squares
    with candidate.scope('compiled_direct'):
        v2_live_optimizer=candidate.repair.prior.solve.__globals__ is vars(candidate.repair.prior)
    api.require(v1_snapshots_optimizer and v2_live_optimizer,'observer binding diagnosis')
    p.update(stage='Stage199 private norm dispatch with live observer retained',correction='Do not clone the outer semismooth solve. Its optimizer observer binding remains live; v1 failure stays failed. Norm implementation and all scientific controls unchanged.',
        binding_diagnosis={'v1_snapshots_optimizer':v1_snapshots_optimizer,'v2_live_optimizer':v2_live_optimizer})
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('NORM_DISPATCH_V2_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helpers();ns['run']()
        except Exception as e:
            path=OUT.parent/'norm_dispatch_failure_02.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
