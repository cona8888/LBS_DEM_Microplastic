"""Whole-composition exactness/speed gate against current trajectory solver."""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy,sys,traceback
import combined_native_candidate_v1 as candidate
import qualify_native_batch_v1 as previous
api,job,WORK=previous.api,previous.job,previous.WORK
DESIGN=WORK.with_name('combined_native_01.json');OUT=previous.OUT.with_name('combined_native_01')
ns={**previous.ns,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('verify','run'):
    f=previous.ns[name];ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=copy.deepcopy(api.read(previous.DESIGN));previous.ns['verify'](p);p.pop('binding')
    api.require(job.utc()+timedelta(seconds=1000)<job.policy.utc(api.read(WORK)['work_end_utc']),'full replay fits clock')
    for directory in (previous.OUT,previous.previous.OUT):
        r=api.read(directory/'results.json');api.require(r['passed'] and api.read(directory/'completion.json')['results_sha256']==api.sha(directory/'results.json'),'independent component exactness prerequisites')
        perf=api.read(directory/'performance.json');api.require(perf['numerical_exactness_passed'] and api.read(directory/'performance_completion.json')['performance_sha256']==api.sha(directory/'performance.json'),'component performance evidence preserved')
        for x in (directory/'results.json',directory/'completion.json',directory/'performance.json',directory/'performance_completion.json'):p['inputs'][str(x)]=api.sha(x)
    p['sources'].update({str(x):api.sha(x) for x in (Path(__file__),Path(candidate.__file__),Path(candidate.arrays.__file__),Path(candidate.trust.__file__),Path(previous.__file__))})
    p.update(stage='Stage199 combined native whole-stack held qualification',
        mode_meanings={'baseline':'original constant arithmetic and SciPy wrapper','direct':'current trajectory-qualified dense dispatcher','compiled_direct':'exact native batch and NumPy-power-preserving native trust composition'},
        note='Trust-v4 alone failed its aggregate speed gate and was not trajectory-used. This new combination must independently pass unchanged whole-stack material criteria against the current trajectory solver. No failed numerical candidate promoted.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('COMBINED_NATIVE_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    api.require(job.utc()+timedelta(seconds=1000)<job.policy.utc(api.read(WORK)['work_end_utc']),'complete replay fits work clock');candidate.warm();ns['run']()
    p=api.read(DESIGN);r=api.read(OUT/'results.json');rows=r['held_comparisons'];api.require(len(rows)==7422,'complete composition test inventory')
    overall=r['timings']['direct']/r['timings']['compiled_direct'];part=rows[16:3596];hard=sum(x['timings']['direct'] for x in part)/sum(x['timings']['compiled_direct'] for x in part);gate=p['adoption_performance_gate']
    result={'numerical_exactness_passed':True,'new_trajectory_steps':0,'overall_speedup_vs_dense':overall,'hard_prefix_speedup_vs_dense':hard,'material_gain_passed':overall>=gate['overall_speedup_vs_dense_minimum'] and hard>=gate['hard_prefix_speedup_vs_dense_minimum'],'performance_gate':gate,'held_results_sha256':api.sha(OUT/'results.json'),'protocol_sha256':api.sha(DESIGN),'production_authorized':False}
    job.commit(OUT/'performance.json',result);job.commit(OUT/'performance_completion.json',{'performance_sha256':api.sha(OUT/'performance.json')});print('COMBINED_NATIVE_PERFORMANCE',overall,hard,result['material_gain_passed'],flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:run()
        except Exception as e:
            path=OUT.parent/'combined_native_failure_01.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
