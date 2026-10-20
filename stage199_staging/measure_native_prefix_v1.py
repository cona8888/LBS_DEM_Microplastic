"""One exact hard-prefix test after a frozen material zero-step speed gain.

No production, changed physics, or automatic successor. Preserve every result.
"""
from pathlib import Path
from types import FunctionType
import ast, copy, inspect, sys
import native_trust_candidate_v3 as candidate
import transaction_json_memo_v1 as storage
import measure_combined_fine_v1 as template
import measure_current_prefix_v1 as previous
import benchmark_native_trust_v3 as qualified
ROOT,api,job,q,WORK=template.ROOT,template.api,template.job,template.q,template.WORK
DESIGN=WORK.with_name('native_prefix_01.json')
RUN=template.RUN.with_name('native_prefix_01');OUT=template.OUT.with_name('native_prefix_01');ORACLE=template.ORACLE
execute=FunctionType(template.execute.__code__,{**template.execute.__globals__,'codec':storage.codec,'DESIGN':DESIGN},template.execute.__name__,template.execute.__defaults__,template.execute.__closure__)
tree=ast.parse(inspect.getsource(template.run));replaced=0
class Ledger(ast.NodeTransformer):
    def visit_Constant(self,node):
        global replaced
        if type(node.value) is int and node.value==53086:node.value=67652;replaced+=1
        return node
Ledger().visit(tree)
if replaced!=4:raise RuntimeError('exactly four explicit prior-ledger substitutions')
ast.fix_missing_locations(tree)
ns={**template.__dict__,'candidate':candidate,'storage':storage,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'execute':execute,'__file__':__file__}
exec(compile(tree,__file__+'::same_fixed_prefix','exec'),ns)

def ledger():
    expected={'combined_fine_01':3580,'long_fine_01':7406,'current_prefix_01':3580}
    accounts=list(RUN.parent.glob('*/*.accounting.json'))
    api.require(len(accounts)==3,'exact three resolved prior trajectory reservations')
    for name,n in expected.items():
        raw=RUN.parent/name/'serial.json.xz';account=api.read(raw.with_suffix('.accounting.json'))
        result=OUT.parent/name/'results.json';r=api.read(result)
        api.require(account['accepted_steps']==n and account['raw_sha256']==api.sha(raw),'exact prior raw accounting')
        api.require(r['passed'] and r['new_accepted_steps']==n and api.read(result.parent/'completion.json')['results_sha256']==api.sha(result),'sealed prior result')
        api.verify_mapping(r['artifacts'])
    api.require(53086+sum(expected.values())==67652 and 67652+3580+3676+17000<=100000,'inclusive reserved future restart and preflight budget')

def verify(d):
    previous.verify(api.read(previous.DESIGN));qualified.ns['verify'](api.read(qualified.DESIGN))
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'new protocol binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    old=api.read(previous.DESIGN)
    api.require(all(d[k]==old[k] for k in ('cases','budget','numerical_gates','minimum_gap_semantics')),'unchanged original physics and gates')
    api.require(d['diagnostic_prior_recovery_steps']==67652 and d['diagnostic_maximum_new_steps']==3580 and d['calls']=={'serial':3580},'new exact step reservation')
    api.require(execute.__code__ is template.execute.__code__ and execute.__globals__['codec'] is storage.codec and execute.__globals__['DESIGN']==DESIGN,'unchanged integration and explicit bindings')
    storage.verify_bindings()
ns['verify']=verify

def prepare():
    d=copy.deepcopy(api.read(previous.DESIGN));previous.verify(d);d.pop('binding');work=api.read(WORK)
    api.require(job.utc()<job.policy.utc(work['last_diagnostic_launch_utc']),'launch cutoff');ledger()
    perf=qualified.OUT/'performance.json';p=api.read(perf)
    api.require(p['numerical_exactness_passed'] and p['material_gain_passed'] and api.read(perf.parent/'performance_completion.json')['performance_sha256']==api.sha(perf),'frozen material speed gate passed')
    bench=api.read(qualified.DESIGN);qualified.ns['verify'](bench)
    files=[Path(__file__),Path(previous.__file__),Path(template.__file__)]
    inputs=[qualified.DESIGN,qualified.OUT/'results.json',qualified.OUT/'completion.json',perf,perf.parent/'performance_completion.json',previous.DESIGN,previous.OUT/'results.json',previous.OUT/'completion.json']
    d.update(stage='Stage199 native trust exact hard-prefix cost test',sources={**d['sources'],**bench['sources'],**{str(x):api.sha(x) for x in files}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},
        diagnostic_prior_recovery_steps=67652,diagnostic_maximum_new_steps=3580,calls={'serial':3580},
        criterion='Every original3580 row and full fixed-cap checkpoint exact; original independent audit and raw seals. Hard-prefix runtime retained separately under1.3 margin; no production from this local test.')
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('NATIVE_PREFIX_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    ledger()
    import numpy as np
    candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
    helper=candidate.prior.prior
    helper.column_norms(np.eye(9));helper.max_abs(np.zeros(9));helper.all_finite(np.zeros(9));helper.all_finite(np.eye(9))
    for V in (np.eye(9),np.asfortranarray(np.eye(9))):
        for alpha in (None,0.,.03):candidate.trust(9,9,np.ones(9),np.arange(1.,10.),V,.1,initial_alpha=alpha)
    ns['run']()

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
