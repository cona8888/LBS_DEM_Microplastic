"""Counterbalanced exact broad replay for strict native batch preparation."""
from pathlib import Path
from types import FunctionType
import copy,sys,traceback
import numpy as np
import native_batch_candidate_v1 as candidate
import qualify_native_batch_helpers_v1 as helper
import qualify_native_trust_v4 as previous
api,job,WORK=previous.api,previous.job,previous.WORK
DESIGN=WORK.with_name('native_batch_01.json');OUT=previous.OUT.with_name('native_batch_01')

def trials():
    archived=previous.tests.api.read(previous.tests.FIXTURES)
    selected=[('archived_'+str(i),archived[i]['fixture']['contact_trial_trace']['detailed_trials'][0]) for i in np.linspace(0,len(archived)-1,16,dtype=int)]
    return selected+previous.trials()

ns={**previous.ns,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'trials':trials,'__file__':__file__}
for name in ('verify','run'):
    f=previous.ns[name];ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=copy.deepcopy(api.read(previous.DESIGN));previous.ns['verify'](p);p.pop('binding')
    hp=api.read(helper.DESIGN);helper.verify(hp)
    h=api.read(helper.OUT/'results.json');api.require(h['passed'] and h['exact_intermediate_tests']==900 and api.read(helper.OUT/'completion.json')['results_sha256']==api.sha(helper.OUT/'results.json'),'all exact matrix helper checks')
    ts=trials();api.require(len(ts)==7422,'sixteen prior hard fixtures plus every long-fine pose')
    p['sources'].update(hp['sources']);p['sources'].update({str(x):api.sha(x) for x in (Path(__file__),Path(candidate.__file__),Path(previous.__file__),Path(helper.__file__))})
    p['inputs'].update({str(x):api.sha(x) for x in (helper.DESIGN,helper.OUT/'results.json',helper.OUT/'completion.json',OUT.parent/'representative_profile_01/results.json',OUT.parent/'representative_profile_01/completion.json')})
    p.update(stage='Stage199 native batch full held-pose exact qualification',labels=[x[0] for x in ts],maximum_outer_calls=len(ts)*3,
        mode_meanings={'baseline':'original constant arithmetic and SciPy wrapper','direct':'trajectory-qualified dense dispatcher','compiled_direct':'dense dispatcher with strict native scalar-batch preparation and original NumPy determinant'},
        adoption_performance_gate={'overall_speedup_vs_dense_minimum':1.05,'hard_prefix_speedup_vs_dense_minimum':1.05},
        note='Native trust variants are NOT used. All full optimizer/outer/physical results must match, including prior hard systems. Zero trajectory steps; original root order and controls unchanged.',
        warmup='Both one-beta Brent and full257-beta array layouts before timing.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('NATIVE_BATCH_PROTOCOL',api.sha(DESIGN),len(ts),flush=True)

def run():
    from datetime import timedelta
    api.require(job.utc()+timedelta(seconds=1000)<job.policy.utc(api.read(WORK)['work_end_utc']),'complete replay fits work window')
    for n in (1,257):candidate.batch_body(np.ones(n),np.ones(6),np.ones(6),np.ones((9,6)),0,.3,.01,np.ones(6),np.eye(6),.03)
    c=candidate.prior;c.batch.equation_arrays(np.zeros((1,9)),0,.3);c.batch.bracket_indices(np.zeros(1));c.prior.column_norms(np.eye(9));c.prior.max_abs(np.zeros(9));c.prior.all_finite(np.zeros(9));c.prior.all_finite(np.eye(9))
    ns['run']();p=api.read(DESIGN);r=api.read(OUT/'results.json');rows=r['held_comparisons'];api.require(len(rows)==7422,'complete exact replay')
    overall=r['timings']['direct']/r['timings']['compiled_direct'];hard=rows[16:16+3580]
    ratio=sum(x['timings']['direct'] for x in hard)/sum(x['timings']['compiled_direct'] for x in hard);gate=p['adoption_performance_gate']
    result={'numerical_exactness_passed':True,'new_trajectory_steps':0,'overall_speedup_vs_dense':overall,'hard_prefix_speedup_vs_dense':ratio,'material_gain_passed':overall>=gate['overall_speedup_vs_dense_minimum'] and ratio>=gate['hard_prefix_speedup_vs_dense_minimum'],'performance_gate':gate,'held_results_sha256':api.sha(OUT/'results.json'),'protocol_sha256':api.sha(DESIGN),'production_authorized':False}
    job.commit(OUT/'performance.json',result);job.commit(OUT/'performance_completion.json',{'performance_sha256':api.sha(OUT/'performance.json')});print('NATIVE_BATCH_PERFORMANCE',overall,ratio,result['material_gain_passed'],flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:run()
        except Exception as e:
            path=OUT.parent/'native_batch_failure_01.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
