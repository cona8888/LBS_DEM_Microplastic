"""Original17,000-step lifecycle tests, new immutable bindings and accounting.

No physics, numerical assertion, fixture, test size or parallel-slowdown gate
is edited. The frozen original run body gets only explicit ledger/key changes.
"""
from pathlib import Path
from types import FunctionType
import ast,inspect,sys
import composed_stack_preflight_v1 as wrapper
import qualify_performance_stack_v1 as tests
job,api,q=wrapper.job,wrapper.api,wrapper.q
ROOT=wrapper.ROOT;RUN=job.PREFLIGHT;OUT=job.OUT/'preflight_01';SELF=Path(__file__).resolve()
ns={**tests.__dict__,'wrapper':wrapper,'job':job,'api':api,'q':q,'ROOT':ROOT,'RUN':RUN,'OUT':OUT,'SELF':SELF,'__file__':__file__}
f=tests.base_protocol.protocol_fixtures
ns['protocol_fixtures']=FunctionType(f.__code__,{**f.__globals__,'job':job,'api':api,'RUN':RUN},f.__name__,f.__defaults__,f.__closure__)
for name in ('seed','stress_seed','deadline','call','probe'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)
tree=ast.parse(inspect.getsource(tests.run));counts={'ledger':0,'prior_key':0,'total_key':0,'failure_key':0,'budget_key':0}
class Ledger(ast.NodeTransformer):
    def visit_Constant(self,node):
        if type(node.value) is int and node.value==8326:node.value=78488;counts['ledger']+=1
        elif node.value=='prior_stage196_steps':node.value='prior_recovery_steps';counts['prior_key']+=1
        elif node.value=='window_new_accepted_steps':node.value='cumulative_recovery_steps';counts['total_key']+=1
        elif node.value=='window_known_accepted_steps':node.value='cumulative_known_accepted_steps';counts['failure_key']+=1
        elif node.value=='maximum_new_qualification_accepted_steps':node.value='cumulative_recovery_accepted_step_ceiling';counts['budget_key']+=1
        return node
Ledger().visit(tree)
if counts!={'ledger':5,'prior_key':2,'total_key':1,'failure_key':1,'budget_key':1}:raise RuntimeError('explicit ledger-only AST substitutions '+repr(counts))
ast.fix_missing_locations(tree);exec(compile(tree,__file__+'::original_tests_current_ledger','exec'),ns)

def run():
    wrapper.ledger();wrapper.candidate.warm();ns['run']()

if __name__=='__main__':
    if sys.argv[1:]==['run']:run()
    elif len(sys.argv)==3 and sys.argv[1]=='probe':wrapper.candidate.warm();ns['probe'](int(sys.argv[2]))
    else:raise ValueError('run | probe INDEX')
