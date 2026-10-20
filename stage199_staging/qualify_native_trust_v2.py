"""Original strict tests, new immutable outputs and exact NumPy-power candidate."""
from pathlib import Path
from types import FunctionType
import ast,inspect,sys,traceback
import native_trust_candidate_v2 as candidate
import qualify_native_trust_v1 as previous
api,job,WORK=previous.api,previous.job,previous.WORK
DESIGN=previous.DESIGN.with_name('native_trust_02.json');OUT=previous.OUT.with_name('native_trust_02')
ns={**previous.ns,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(previous.tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)
helper_ns={**previous.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'ns':ns}
tree=ast.parse(inspect.getsource(previous.helpers));renames=0
class Output(ast.NodeTransformer):
    def visit_Constant(self,node):
        global renames
        if node.value in ('native_trust_mismatch_01.json','native_trust_edges_01.json'):
            node.value=node.value.replace('_01.json','_02.json');renames+=1
        return node
Output().visit(tree)
if renames!=2:raise RuntimeError('exactly two immutable helper output path substitutions')
ast.fix_missing_locations(tree);exec(compile(tree,__file__+'::same_tests_new_outputs','exec'),helper_ns)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__),Path(previous.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT.parent/'native_trust_failure_01.json',previous.OUT.parent/'native_trust_mismatch_01.json',previous.OUT.parent/'native_trust_diagnosis_01.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 native trust screening with original NumPy power',correction='Keep the original NumPy vector power operation. Original v1 arithmetic mismatch remains rejected and preserved. No gate or tolerance changes.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('NATIVE_TRUST_V2_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helper_ns['helpers']();ns['run']()
        except Exception as e:
            path=OUT.parent/'native_trust_failure_02.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
