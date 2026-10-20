"""Zero-step evenly spaced current-regime attribution, not a speed claim."""
from pathlib import Path
from types import FunctionType,SimpleNamespace
import copy,sys
import numpy as np
import exact_dense_dispatch_v1 as candidate
import transaction_json_memo_v1 as storage
import profile_runtime_storage_v1 as prior
import measure_current_prefix_v1 as measured
api,job,WORK=prior.api,prior.job,prior.WORK
DESIGN=WORK.with_name('representative_profile_01.json')
RUN=prior.RUN.with_name('representative_profile_01');OUT=prior.OUT.with_name('representative_profile_01')
RAW=measured.RUN/'serial.json.xz';RAWDESIGN=measured.DESIGN
LONG=RAW.parent.parent/'long_fine_01/serial.json.xz';LONG_DESIGN=WORK.with_name('long_fine_01.json')

def trials():
    r=prior.q.independent_file(LONG,api.sha(LONG_DESIGN));ts=r['contact_trial_trace']['detailed_trials']
    return [('long_'+str(i),ts[i]) for i in np.linspace(0,len(ts)-1,400,dtype=int)]

held=SimpleNamespace(**vars(prior.held));held.trials=trials
ns={**prior.__dict__,'candidate':candidate,'storage':storage,'held':held,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'RAW':RAW,'RAWDESIGN':RAWDESIGN,'__file__':__file__}
for name in ('verify','run'):
    f=getattr(prior,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=copy.deepcopy(api.read(prior.DESIGN));prior.verify(p);p.pop('binding')
    measured.verify(api.read(measured.DESIGN))
    p['sources'].update(api.read(measured.DESIGN)['sources'])
    p['sources'].update({str(x):api.sha(x) for x in (Path(__file__),Path(prior.__file__),Path(candidate.__file__),Path(storage.__file__))})
    p['inputs'].update({str(x):api.sha(x) for x in (RAWDESIGN,RAW,RAW.with_suffix('.seal.json'),LONG,LONG.with_suffix('.seal.json'),LONG_DESIGN,measured.OUT/'results.json')})
    p.update(stage='Stage199400 uniformly spaced held-pose current-regime profile',held_outer_call_limit=400,selection='np.linspace(0,7405,400,dtype=int); includes both interval endpoints; no outcome selection',recovery_steps_before=71232)
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('REPRESENTATIVE_PROFILE_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
        candidate.prior.column_norms(np.eye(9));candidate.prior.max_abs(np.zeros(9));candidate.prior.all_finite(np.zeros(9));candidate.prior.all_finite(np.eye(9));storage.raw_bytes({'warm':0.})
        ns['run']()
    else:raise ValueError('prepare | run')
