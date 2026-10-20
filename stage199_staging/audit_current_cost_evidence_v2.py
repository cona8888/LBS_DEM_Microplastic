"""Correct source provenance for the frozen namespace-backed audit kernel."""
from pathlib import Path
from types import FunctionType
import sys
import audit_current_cost_evidence_v1 as prior
measured,ROOT,api,job,q=prior.measured,prior.ROOT,prior.api,prior.job,prior.q
DESIGN=prior.DESIGN.with_name('independent_cost_audit_02.json');OUT=prior.OUT.with_name('independent_cost_audit_02')
namespace={**prior.__dict__,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
f=prior.run;run=FunctionType(f.__code__,namespace,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    paths=[measured.OUT/'results.json',measured.prior.OUT/'results.json']
    inputs=[measured.WORK,measured.DESIGN,measured.prior.DESIGN,measured.ORACLE,measured.ORACLE.with_suffix('.seal.json'),OUT.parent/'cost_audit_preparation_failure_01.json']
    for path in paths:
        r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'saved sealed measurement')
        api.verify_mapping(r['artifacts']);inputs.extend([path,path.parent/'completion.json',*[Path(x) for x in r['artifacts']]])
    for name in ('solver_brackets_01','trf_helpers_01','dense_dispatch_01','transaction_json_01'):
        path=OUT.parent/name/'results.json';r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed local qualification');inputs.extend([path,path.parent/'completion.json'])
    for name in ('benchmark.json','benchmark_completion.json'):inputs.append(OUT.parent/'transaction_json_01'/name)
    kernel_source=Path(job.kernel.evaluate.__code__.co_filename.split('::')[0]);api.require(kernel_source.is_file(),'actual frozen audit kernel source')
    sources=[Path(__file__),Path(prior.__file__),Path(measured.__file__),Path(q.__file__),kernel_source]
    p={'stage':'Stage199 independent cost-evidence closure v2','new_trajectory_steps':0,'sources':{str(x):api.sha(x) for x in sources},'inputs':{str(x):api.sha(x) for x in inputs},'production_authorized':False,'prior_recovery_steps':53086,'correction':'Only provenance lookup for namespace-backed kernel; independent audit run bytecode unchanged from preserved v1.'}
    p['binding']=api.digest(p);job.commit(DESIGN,p);print('COST_AUDIT_V2_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
