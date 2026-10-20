"""Reuse exact archived-byte, failure-schema, chain and rejection tests.

Only the bounded work clock and output routing are amended in the inherited
zero-step test. Extra randomized canonical/number edge cases run first.
"""
from pathlib import Path
import ast, inspect, json, math, random, sys
import fast_storage_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage196_staging'))
import qualify_compact_storage_v1 as prior
api,job=prior.api,prior.job
WORK=ROOT/'stage197_designs/deadline_extension_20260926/authorization_01.json'
DESIGN=ROOT/'stage198_designs/direct_trf_20260926/storage_protocol_01.json'
RUN=Path('D:/MATDEM_MICROPLASTIC/stage198_runs/direct_trf_20260926/storage_01')
OUT=ROOT/'stage198_evaluations/direct_trf_20260926/storage_01'
tree=ast.parse(inspect.getsource(prior.run));count=0
class Clock(ast.NodeTransformer):
    def visit_Subscript(self,node):
        global count
        if ast.unparse(node)=="work['work_end_utc']":node.slice=ast.Constant(value='final_audit_deadline_utc');count+=1
        return self.generic_visit(node)
Clock().visit(tree)
if count!=2:raise RuntimeError('exactly two bounded work-clock replacements required')
ast.fix_missing_locations(tree)
ns={**prior.__dict__,'candidate':candidate,'WORK':WORK,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'__file__':__file__}
exec(compile(tree,__file__+'::qualified_test_clock_only','exec'),ns)

def main():
    inputs={str(x):api.sha(x) for x in (Path(__file__),Path(candidate.__file__),Path(candidate.canonical.__file__),Path(prior.__file__),WORK)}
    job.commit(DESIGN.with_name('storage_harness_01.json'),{'inputs':inputs,'new_trajectory_steps':0,'changes':'Numeric-leaf standard JSON acceleration and exact numeric factoring comparison only; original decoder and seals retained.'})
    rng=random.Random(198);special=[0.,-0.,float('nan'),float('inf'),-float('inf'),1e-308,5e-324,1e308,1e-7,1.,1,True,None,'a\n\"\\é']
    tests=[special,{'z':special,'a':[special,special]},[],{},[[],{}],tuple(special)]
    for _ in range(300):
        values=[rng.uniform(-1e25,1e25),rng.randint(-2**70,2**70),rng.choice(special)]
        tests.append({'f':values,'matrix':[[rng.random() for _ in range(9)] for _ in range(6)],'a':[values,{},False]})
    for x in tests:
        api.require(candidate.raw_bytes(x)==candidate.base.raw_bytes(x),'exact canonical bytes for numeric and general edges')
    for a in special:
        for b in special:
            api.require(candidate.equivalent(a,b)==(candidate.base.raw_bytes(a)==candidate.base.raw_bytes(b)),'factoring equality exactly matches canonical identity')
    job.commit(DESIGN.with_name('canonical_edges_01.json'),{'passed':True,'objects':len(tests),'scalar_pairs':len(special)**2,'new_trajectory_steps':0,'inputs':inputs})
    ns['run']()

if __name__=='__main__':main()
