"""Measure the original difficult3580-step interval with the final candidate.

Do not infer its cost from the longer observation's faster later interval.
Original fixed-prefix test reused; only explicit candidate/output/accounting
bindings change, with four exact ledger constants mechanically replaced.
"""
from pathlib import Path
from types import FunctionType
import ast,copy,inspect,sys
import exact_dense_dispatch_v1 as candidate
import transaction_json_memo_v1 as storage
import measure_combined_fine_v1 as template
import measure_qualified_long_fine_v1 as previous
ROOT,api,job,q,WORK=template.ROOT,template.api,template.job,template.q,template.WORK
DESIGN=WORK.with_name('current_prefix_01.json');RUN=template.RUN.with_name('current_prefix_01');OUT=template.OUT.with_name('current_prefix_01')
ORACLE=template.ORACLE
execute=FunctionType(template.execute.__code__,{**template.execute.__globals__,'codec':storage.codec,'DESIGN':DESIGN},template.execute.__name__,template.execute.__defaults__,template.execute.__closure__)
tree=ast.parse(inspect.getsource(template.run));replaced=0
class Ledger(ast.NodeTransformer):
    def visit_Constant(self,node):
        global replaced
        if type(node.value) is int and node.value==53086:node.value=64072;replaced+=1
        return node
Ledger().visit(tree)
if replaced!=4:raise RuntimeError('exactly four prior-ledger constants must change; no broad text substitution')
ast.fix_missing_locations(tree)
namespace={**template.__dict__,'candidate':candidate,'storage':storage,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'execute':execute,'__file__':__file__}
exec(compile(tree,__file__+'::same_fixed_prefix_new_accounting','exec'),namespace)

def verify(d):
    previous.verify(api.read(previous.DESIGN));api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'fixed-prefix binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    old=api.read(previous.DESIGN);api.require(all(d[k]==old[k] for k in ('cases','budget','numerical_gates','minimum_gap_semantics')),'unchanged physics and gates')
    api.require(d['diagnostic_prior_recovery_steps']==64072 and d['diagnostic_maximum_new_steps']==3580 and d['calls']=={'serial':3580},'exact current ledger/cap')
    api.require(execute.__code__ is template.execute.__code__ and execute.__globals__['codec'] is storage.codec and execute.__globals__['DESIGN']==DESIGN,'original integration and explicit bindings');storage.verify_bindings()
namespace['verify']=verify

def prepare():
    d=copy.deepcopy(api.read(previous.DESIGN));previous.verify(d);d.pop('binding');work=api.read(WORK)
    api.require(job.utc()<job.policy.utc(work['last_diagnostic_launch_utc']),'launch cutoff')
    audit=OUT.parent/'independent_cost_audit_02/results.json';r=api.read(audit)
    api.require(r['passed'] and r['cumulative_recovery_steps']==64072 and r['no_unresolved_reservation'] and api.read(audit.parent/'completion.json')['results_sha256']==api.sha(audit),'independent ledger and evidence closure')
    files=[Path(__file__),Path(template.__file__)]
    inputs=[previous.DESIGN,previous.OUT/'results.json',previous.OUT/'completion.json',audit,audit.parent/'completion.json']
    d.update(stage='Stage199 exact difficult-prefix cost confirmation',sources={**d['sources'],**{str(x):api.sha(x) for x in files}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},
        diagnostic_prior_recovery_steps=64072,diagnostic_maximum_new_steps=3580,calls={'serial':3580},expected_statuses=['paused_checkpoint'],
        criterion='Every original3580 row and complete original fixed-cap checkpoint state exact, with original numerical gates. Measure this difficult interval separately; do not replace its cost by a faster subsequent interval. Local/runtime/full-stack gates remain distinct.')
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('CURRENT_PREFIX_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        import numpy as np
        candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
        candidate.prior.column_norms(np.eye(9));candidate.prior.max_abs(np.zeros(9));candidate.prior.all_finite(np.zeros(9));candidate.prior.all_finite(np.eye(9))
        namespace['run']()
    else:raise ValueError('prepare | run')
