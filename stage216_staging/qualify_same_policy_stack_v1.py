"""Same exact protocol; explicitly selected independent sphere contact oracles."""
from types import FunctionType
from pathlib import Path
import ast,inspect,sys
import same_policy_stack_preflight_v1 as wrapper
sys.path.insert(0,str(wrapper.ROOT/'stage196_staging'))
import qualify_performance_stack_v1 as tests
job,api,q=wrapper.job,wrapper.api,wrapper.q
ROOT=wrapper.ROOT;RUN=job.PREFLIGHT;OUT=job.OUT/'preflight_01';SELF=Path(__file__).resolve()
ns=dict(tests.__dict__,wrapper=wrapper,job=job,api=api,q=q,ROOT=ROOT,RUN=RUN,OUT=OUT,SELF=SELF,__file__=__file__,no_competing_trajectory=wrapper.no_competing_trajectory)
f=tests.base_protocol.protocol_fixtures
ns['protocol_fixtures']=FunctionType(f.__code__,dict(f.__globals__,job=job,api=api,RUN=RUN),f.__name__,f.__defaults__,f.__closure__)
for name in ('seed','stress_seed','deadline','call','probe'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)
old_seed=ns['seed']

def seed(d,case):
    cp,oracle=old_seed(d,case)
    if case['shape']=='equal_volume_sphere':
        oracle=wrapper.reference_record(case,'contact')
        saved_before=api.read(wrapper.refs.RUN/(case['id']+'_contact')/'input_checkpoint.json')
        api.require(cp['state']==saved_before['state'],'same accepted original contact seed, new binding only')
    return cp,oracle
ns['seed']=seed
source=inspect.getsource(tests.run)
start=source.index('    for proc in psutil.process_iter(');stop=source.index('    info=wrapper.affinity.bind',start)
api.require('no duplicate simulation or benchmark' in source[start:stop],'original fail-closed process guard')
source=source[:start]+'    no_competing_trajectory()\n'+source[stop:]
tree=ast.parse(source);counts=dict(ledger=0,prior_key=0,total_key=0,failure_key=0)
class Ledger(ast.NodeTransformer):
    def visit_Constant(self,node):
        if type(node.value) is int and node.value==8326:node.value=0;counts['ledger']+=1
        elif node.value=='prior_stage196_steps':node.value='prior_stage216_steps';counts['prior_key']+=1
        elif node.value=='window_new_accepted_steps':node.value='stage216_new_accepted_steps';counts['total_key']+=1
        elif node.value=='window_known_accepted_steps':node.value='stage216_known_accepted_steps';counts['failure_key']+=1
        return node
Ledger().visit(tree);api.require(counts==dict(ledger=5,prior_key=2,total_key=1,failure_key=1),'bookkeeping-only protocol AST changes')
ast.fix_missing_locations(tree);exec(compile(tree,__file__+'::same_exact_assertions_explicit_same_policy_oracles','exec'),ns)

def run():wrapper.ledger();wrapper.candidate.warm();ns['run']()
if __name__=='__main__':
    if sys.argv[1:]==['run']:run()
    elif len(sys.argv)==3 and sys.argv[1]=='probe':wrapper.candidate.warm();ns['probe'](int(sys.argv[2]))
    else:raise ValueError('run | probe INDEX')
