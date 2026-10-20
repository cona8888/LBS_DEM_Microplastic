"""Repeated counterbalanced held benchmark, after all native layouts are warm."""
from pathlib import Path
from types import FunctionType
import ast,inspect,sys,traceback
import numpy as np
import native_trust_candidate_v3 as candidate
import qualify_native_trust_v2 as previous
original=previous.previous
api,job,WORK=previous.api,previous.job,previous.WORK
DESIGN=previous.DESIGN.with_name('native_trust_03.json');OUT=previous.OUT.with_name('native_trust_03')
ns={**previous.ns,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('verify',):
    f=getattr(original.tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)
ns['trials']=lambda:original.tests.trials()*3
ns['_modes']=lambda i,m:m[i%3:]+m[:i%3]
tree=ast.parse(inspect.getsource(original.tests.run));changes=0
class Order(ast.NodeTransformer):
    def visit_For(self,node):
        global changes
        if ast.unparse(node.target)=='mode' and ast.unparse(node.iter)=="p['modes']":
            node.iter=ast.parse("_modes(i,p['modes'])",mode='eval').body;changes+=1
        return self.generic_visit(node)
Order().visit(tree)
if changes!=1:raise RuntimeError('one counterbalanced benchmark-order substitution')
ast.fix_missing_locations(tree);exec(compile(tree,__file__+'::same_exact_tests_counterbalanced','exec'),ns)
helper_ns={**original.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'ns':ns}
tree=ast.parse(inspect.getsource(original.helpers));renames=0
class Names(ast.NodeTransformer):
    def visit_Constant(self,node):
        global renames
        if node.value in ('native_trust_mismatch_01.json','native_trust_edges_01.json'):
            node.value=node.value.replace('_01.json','_03.json');renames+=1
        return node
Names().visit(tree)
if renames!=2:raise RuntimeError('two immutable helper-path substitutions')
ast.fix_missing_locations(tree);exec(compile(tree,__file__+'::same_strict_helpers','exec'),helper_ns)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__),Path(previous.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT/'results.json',previous.OUT/'completion.json',previous.OUT.parent/'native_trust_edges_02.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 warm counterbalanced native-trust qualification',labels=p['labels']*3,maximum_outer_calls=720,benchmark_repetitions=3,
        warmup='C/F matrix layouts and None/zero/positive initial alpha before any timed call; retained NumPy power.',
        adoption_performance_gate={'overall_speedup_vs_dense_minimum':1.05,'each_repetition_speedup_vs_dense_minimum':1.02},
        note='v2 full exactness passed, but its first timed native call includes compilation. v2 timing is not used as a steady-state speedup claim.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('NATIVE_TRUST_V3_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    helper_ns['helpers']()
    for V in (np.eye(9),np.asfortranarray(np.eye(9))):
        for alpha in (None,0.,.03):candidate.trust(9,9,np.ones(9),np.arange(1.,10.),V,.1,initial_alpha=alpha)
    ns['run']();p=api.read(DESIGN);r=api.read(OUT/'results.json');rows=r['held_comparisons'];api.require(len(rows)==240,'all repeated exact comparisons')
    ratios=[]
    for k in range(3):
        group=rows[k*80:(k+1)*80];ratios.append(sum(x['timings']['direct'] for x in group)/sum(x['timings']['compiled_direct'] for x in group))
    ratio=r['timings']['direct']/r['timings']['compiled_direct'];gate=p['adoption_performance_gate']
    result={'numerical_exactness_passed':True,'new_trajectory_steps':0,'overall_speedup_vs_dense':ratio,'per_repetition_speedups':ratios,'material_gain_passed':ratio>=gate['overall_speedup_vs_dense_minimum'] and min(ratios)>=gate['each_repetition_speedup_vs_dense_minimum'],'performance_gate':gate,'held_results_sha256':api.sha(OUT/'results.json'),'protocol_sha256':api.sha(DESIGN),'production_authorized':False}
    job.commit(OUT/'performance.json',result);job.commit(OUT/'performance_completion.json',{'performance_sha256':api.sha(OUT/'performance.json')});print('WARM_NATIVE_PERFORMANCE',ratio,ratios,result['material_gain_passed'],flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:run()
        except Exception as e:
            path=OUT.parent/'native_trust_failure_03.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
