"""Zero-trajectory qualification across EVERY sealed long-fine held pose.

Prior candidate failure remains failed. Includes its exact captured counterexample.
"""
from pathlib import Path
from types import FunctionType
import ast,copy,inspect,sys,traceback
import numpy as np
import native_trust_candidate_v4 as candidate
import benchmark_native_trust_v3 as previous
api,job,WORK=previous.api,previous.job,previous.WORK
tests=previous.original.tests
DESIGN=WORK.with_name('native_trust_04.json');OUT=previous.OUT.with_name('native_trust_04')
LONG=OUT.parent/'long_fine_01/results.json'
RAW=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/long_fine_01/serial.json.xz')
LONG_DESIGN=WORK.with_name('long_fine_01.json')
DIAG=OUT.parent/'native_prefix_diagnosis_01/results.json'

def trials():
    rec=tests.q.independent_file(RAW,api.sha(LONG_DESIGN))
    return [('long_fine_'+str(i),t) for i,t in enumerate(rec['contact_trial_trace']['detailed_trials'])]

ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'trials':trials,'__file__':__file__}
f=tests.verify;ns['verify']=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)
ns['_modes']=lambda i,m:m[i%3:]+m[:i%3]
tree=ast.parse(inspect.getsource(tests.run));order_changes=0;print_changes=0
class Order(ast.NodeTransformer):
    def visit_For(self,node):
        global order_changes
        if ast.unparse(node.target)=='mode' and ast.unparse(node.iter)=="p['modes']":
            node.iter=ast.parse("_modes(i,p['modes'])",mode='eval').body;order_changes+=1
        return self.generic_visit(node)
    def visit_Compare(self,node):
        global print_changes
        if ast.unparse(node)=='i % 16 == 0':
            print_changes+=1;return ast.copy_location(ast.parse('i % 400 == 0',mode='eval').body,node)
        return self.generic_visit(node)
Order().visit(tree)
if (order_changes,print_changes)!=(1,1):raise RuntimeError('explicit benchmark-order and progress-cadence substitutions only')
ast.fix_missing_locations(tree);exec(compile(tree,__file__+'::all_held_exact','exec'),ns)
helper_ns={**previous.original.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'ns':ns}
tree=ast.parse(inspect.getsource(previous.original.helpers));renames=0
class Names(ast.NodeTransformer):
    def visit_Constant(self,node):
        global renames
        if node.value in ('native_trust_mismatch_01.json','native_trust_edges_01.json'):
            node.value=node.value.replace('_01.json','_04.json');renames+=1
        return node
Names().visit(tree)
if renames!=2:raise RuntimeError('two new immutable helper output names')
ast.fix_missing_locations(tree);exec(compile(tree,__file__+'::same_strict_helpers','exec'),helper_ns)

def prepare():
    p=copy.deepcopy(api.read(previous.DESIGN));previous.ns['verify'](p);p.pop('binding')
    api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    r=api.read(LONG);api.require(r['passed'] and api.read(LONG.parent/'completion.json')['results_sha256']==api.sha(LONG),'complete sealed held-pose source')
    ts=trials();api.require(len(ts)==r['new_accepted_steps']==7406,'all7406 accepted held trials, not selected subset')
    p['sources'].update({str(x.resolve()):api.sha(x) for x in (Path(__file__),Path(candidate.__file__),Path(previous.__file__))})
    p['inputs'].update({str(x):api.sha(x) for x in (LONG,LONG.parent/'completion.json',RAW,RAW.with_suffix('.seal.json'),LONG_DESIGN,DIAG,DIAG.parent/'completion.json',DIAG.parent/'primitive_iterations.json')})
    p.update(stage='Stage199 native trust v4 all sealed fine poses',labels=[x[0] for x in ts],maximum_outer_calls=3*len(ts),recovery_steps_before=71232,benchmark_repetitions=1,
        adoption_performance_gate={'overall_speedup_vs_dense_minimum':1.05,'hard_prefix_speedup_vs_dense_minimum':1.05},
        note='v3 failed at original fine row2995; v4 retains original NumPy scalar half-power as well as vector cube. Every one of7406 held poses checked. Failed trajectory remains failed. No new trajectory steps.',
        warmup='Both C/F native layouts, all three initial-alpha categories and observed failed trust arguments before timing.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('NATIVE_TRUST_V4_PROTOCOL',api.sha(DESIGN),len(ts),flush=True)

def run():
    api.require(job.utc()+__import__('datetime').timedelta(seconds=1000)<job.policy.utc(api.read(WORK)['work_end_utc']),'whole zero-step test fits work window')
    helper_ns['helpers']()
    for V in (np.eye(9),np.asfortranarray(np.eye(9))):
        for alpha in (None,0.,.03):candidate.trust(9,9,np.ones(9),np.arange(1.,10.),V,.1,initial_alpha=alpha)
    for m in api.read(DIAG)['trust_mismatches']:
        args=m['args'];uf,s,V=map(np.asarray,args[2:5])
        for matrix in (V,np.asfortranarray(V)):
            params=(args[0],args[1],uf,s,matrix,args[5]);a=candidate.original_trust(*params,**m['kwargs']);b=candidate.trust(*params,**m['kwargs'])
            api.require(all(np.asarray(x).tobytes()==np.asarray(y).tobytes() for x,y in zip(a,b)),'observed failure reproduced exactly with NumPy half-power')
    ns['run']();p=api.read(DESIGN);r=api.read(OUT/'results.json');rows=r['held_comparisons'];api.require(len(rows)==7406,'every original held pose')
    ratio=r['timings']['direct']/r['timings']['compiled_direct']
    hard=sum(x['timings']['direct'] for x in rows[:3580])/sum(x['timings']['compiled_direct'] for x in rows[:3580]);gate=p['adoption_performance_gate']
    out={'numerical_exactness_passed':True,'new_trajectory_steps':0,'overall_speedup_vs_dense':ratio,'hard_prefix_speedup_vs_dense':hard,'material_gain_passed':ratio>=gate['overall_speedup_vs_dense_minimum'] and hard>=gate['hard_prefix_speedup_vs_dense_minimum'],'performance_gate':gate,'held_results_sha256':api.sha(OUT/'results.json'),'protocol_sha256':api.sha(DESIGN),'production_authorized':False}
    job.commit(OUT/'performance.json',out);job.commit(OUT/'performance_completion.json',{'performance_sha256':api.sha(OUT/'performance.json')});print('V4_FULL_HELD_PERFORMANCE',ratio,hard,out['material_gain_passed'],flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:run()
        except Exception as e:
            path=OUT.parent/'native_trust_failure_04.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
