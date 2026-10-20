"""Run the unchanged qualified failure/chain/corruption tests on native JSON."""
from pathlib import Path
from types import FunctionType
import sys
import native_storage_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage196_staging'))
import qualify_compact_storage_v1 as tests
WORK=ROOT/'stage199_designs/eight_hour_optimization_20260926/contract_01.json'
DESIGN=WORK.with_name('native_storage_01.json')
RUN=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/native_storage_01')
OUT=ROOT/'stage199_evaluations/eight_hour_optimization_20260926/native_storage_01'
ns={**tests.__dict__,'candidate':candidate,'WORK':WORK,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'__file__':__file__}
run=FunctionType(tests.run.__code__,ns,tests.run.__name__,tests.run.__defaults__,tests.run.__closure__)

if __name__=='__main__':
    prerequisite=OUT.parent/'canonical_native_01/results.json';r=tests.api.read(prerequisite)
    tests.api.require(r['passed'] and r['mean_speedup']>1 and tests.api.read(prerequisite.parent/'completion.json')['results_sha256']==tests.api.sha(prerequisite),'sealed exact canonical speedup prerequisite')
    files=[Path(__file__),Path(candidate.__file__),Path(candidate.canonical.__file__),Path(candidate.prior.__file__),Path(tests.__file__),WORK,prerequisite,prerequisite.parent/'completion.json',DESIGN.with_name('canonical_native_01.json')]
    tests.job.commit(DESIGN.with_name('native_storage_harness_01.json'),{'stage':'Stage199 native canonical transport qualification','inputs':{str(x):tests.api.sha(x) for x in files},'new_trajectory_steps':0,'inherited_test_code':'Original Stage196 full failure/chain/rejection test with only candidate, clock and output globals rebound.'})
    run()
