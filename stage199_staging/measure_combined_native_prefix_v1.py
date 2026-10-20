"""One original hard-prefix replay after independently qualified composition.

All old failures remain failed. The prior accounting includes the rejected
native-v3 trajectory. This test has no production or automatic restart path.
"""
from pathlib import Path
from types import FunctionType
import ast, copy, inspect, sys
import combined_native_candidate_v1 as candidate
import owned_decode_storage_v1 as storage
import measure_combined_fine_v1 as template
import measure_current_prefix_v1 as previous
import qualify_combined_native_v1 as qualified
ROOT,api,job,q,WORK=template.ROOT,template.api,template.job,template.q,template.WORK
DESIGN=WORK.with_name('combined_native_prefix_01.json')
RUN=template.RUN.with_name('combined_native_prefix_01');OUT=template.OUT.with_name('combined_native_prefix_01')
ORACLE=template.ORACLE
execute=FunctionType(template.execute.__code__,{**template.execute.__globals__,'codec':storage.codec,'DESIGN':DESIGN},template.execute.__name__,template.execute.__defaults__,template.execute.__closure__)
tree=ast.parse(inspect.getsource(template.run));changes=0
class Ledger(ast.NodeTransformer):
    def visit_Constant(self,node):
        global changes
        if type(node.value) is int and node.value==53086:node.value=71232;changes+=1
        return node
Ledger().visit(tree)
if changes!=4:raise RuntimeError('exactly four prior-ledger substitutions')
ast.fix_missing_locations(tree)
ns={**template.__dict__,'candidate':candidate,'storage':storage,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'execute':execute,'__file__':__file__}
exec(compile(tree,__file__+'::original_fixed_prefix','exec'),ns)

def ledger():
    expected={'combined_fine_01':3580,'long_fine_01':7406,'current_prefix_01':3580,'native_prefix_01':3580}
    accounts=list(RUN.parent.glob('*/*.accounting.json'))
    api.require(len(accounts)==len(expected),'exact four resolved prior trajectory reservations')
    for name,n in expected.items():
        raw=RUN.parent/name/'serial.json.xz';a=api.read(raw.with_suffix('.accounting.json'))
        api.require(a['accepted_steps']==n and a['raw_sha256']==api.sha(raw),'original sealed step accounting')
    closure=OUT.parent/'failure_ledger_audit_01/results.json';r=api.read(closure)
    api.require(r['evidence_and_accounting_passed'] and not r['all_candidates_passed'] and r['cumulative_recovery_steps']==71232,'failure-inclusive prior closure')
    api.require(api.read(closure.parent/'completion.json')['results_sha256']==api.sha(closure),'independent closure seal')
    api.require(53086+sum(expected.values())==71232 and 71232+3580+3676+17000<=100000,'reserve exact restart and full six-worker qualification')

def verify(d):
    previous.verify(api.read(previous.DESIGN));qualified.ns['verify'](api.read(qualified.DESIGN))
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'new exact binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    old=api.read(previous.DESIGN)
    api.require(all(d[k]==old[k] for k in ('cases','budget','numerical_gates','minimum_gap_semantics')),'unchanged original physics and numerical gates')
    api.require(d['diagnostic_prior_recovery_steps']==71232 and d['diagnostic_maximum_new_steps']==3580 and d['calls']=={'serial':3580},'exact current reservation')
    api.require(execute.__code__ is template.execute.__code__ and execute.__globals__['codec'] is storage.codec and execute.__globals__['DESIGN']==DESIGN,'unchanged integration and explicit storage bindings')
    storage.verify_bindings()
ns['verify']=verify

def prepare():
    api.require(job.utc()<job.policy.utc(api.read(WORK)['last_diagnostic_launch_utc']),'launch cutoff');ledger()
    bench=api.read(qualified.DESIGN);qualified.ns['verify'](bench)
    perf=qualified.OUT/'performance.json';p=api.read(perf)
    api.require(p['numerical_exactness_passed'] and p['material_gain_passed'] and api.read(perf.parent/'performance_completion.json')['performance_sha256']==api.sha(perf),'whole-composition exactness and original material gain gate')
    owned=OUT.parent/'owned_decode_01';s=api.read(owned/'benchmark.json')
    api.require(s['passed'] and s['material_reader_gain_passed'] and api.read(owned/'benchmark_completion.json')['benchmark_sha256']==api.sha(owned/'benchmark.json'),'full lossless ownership/lifetime and material reader qualification')
    api.verify_mapping(s['inputs'])
    files=[Path(__file__),Path(template.__file__),Path(previous.__file__),Path(candidate.__file__),Path(storage.__file__)]
    inputs=[qualified.DESIGN,qualified.OUT/'results.json',qualified.OUT/'completion.json',perf,perf.parent/'performance_completion.json',owned/'results.json',owned/'completion.json',owned/'benchmark.json',owned/'benchmark_completion.json',WORK.with_name('owned_decode_harness_01.json'),OUT.parent/'failure_ledger_audit_01/results.json',OUT.parent/'failure_ledger_audit_01/completion.json']
    d=copy.deepcopy(api.read(previous.DESIGN));d.pop('binding')
    d.update(stage='Stage199 exact composed solver and owned-reader hard-prefix qualification',
        sources={**d['sources'],**bench['sources'],**{str(x):api.sha(x) for x in files}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},
        diagnostic_prior_recovery_steps=71232,diagnostic_maximum_new_steps=3580,calls={'serial':3580},
        criterion='Exact every original row and full fixed-cap checkpoint; original independent numerical audit and complete lossless evidence. Separately evaluate hard-regime time with unchanged1.3 margin. No production from this local test.')
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('COMPOSED_PREFIX_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    ledger();candidate.warm();ns['run']()

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
