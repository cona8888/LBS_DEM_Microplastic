"""New immutable test paths for the live-observer norm candidate."""
from pathlib import Path
from types import FunctionType
import ast,inspect,sys,traceback
import exact_norm_dispatch_v2 as candidate
import qualify_norm_dispatch_v1 as tests
import qualify_norm_dispatch_v2 as failed
api,job,WORK=tests.api,tests.job,tests.WORK
DESIGN=tests.DESIGN.with_name('norm_dispatch_03.json');OUT=tests.OUT.with_name('norm_dispatch_03')
ns={**tests.ns,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(tests.tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)
helper_ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'ns':ns}
tree=ast.parse(inspect.getsource(tests.helpers));renames=0
class Output(ast.NodeTransformer):
    def visit_Constant(self,node):
        global renames
        if node.value=='norm_helper_edges_01.json':node.value='norm_helper_edges_03.json';renames+=1
        return node
Output().visit(tree)
if renames!=1:raise RuntimeError('one exact immutable helper output path correction')
ast.fix_missing_locations(tree);exec(compile(tree,__file__+'::helper_path_only','exec'),helper_ns)

def prepare():
    p=api.read(failed.DESIGN);failed.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(failed.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (failed.DESIGN,OUT.parent/'norm_dispatch_failure_02.json'):
        p['inputs'][str(x)]=api.sha(x)
    p['stage']='Stage199 private norm dispatch live observer, immutable output v3'
    p['harness_correction']='v2 helper test correctly refused collision with the old immutable edge output. Only new helper/design/result paths change; no physics, numerical candidate or test assertions changed.'
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('NORM_DISPATCH_V3_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helper_ns['helpers']();ns['run']()
        except Exception as e:
            path=OUT.parent/'norm_dispatch_failure_03.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
