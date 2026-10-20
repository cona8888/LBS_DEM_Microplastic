"""Zero-step exact verification using the solver's existing compiler version."""
from pathlib import Path
from types import FunctionType
import qualify_constant_pair_v1 as original
import compiled_analytic_pair_v2 as candidate
import owned_performance_affinity_v1 as affinity
ROOT=original.ROOT;api=original.api;job=original.job
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/compiled_pair_02'
DESIGN=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/compiled_pair_02.json'


if __name__=='__main__':
    info=affinity.bind(14)
    package_files={str(p):api.sha(p) for base in ('numba','llvmlite') for p in (candidate.DEPENDENCIES/base).rglob('*') if p.is_file() and p.suffix in ('.py','.pyd','.dll')}
    job.commit(DESIGN.with_name('compiled_pair_02_harness.json'),{'source_sha256':api.sha(__file__),
        'inherited_test_source':str(Path(original.__file__).resolve()),'inherited_test_source_sha256':api.sha(original.__file__),
        'candidate_sha256':api.sha(candidate.__file__),'owned_affinity':info,'new_trajectory_steps':0,
        'existing_dependency_files':package_files,'previous_preparation_failure_sha256':api.sha(OUT.parent/'compiled_import_failure_01.json'),
        'compiler':{'numba':'0.62.1','llvmlite':'0.45.1','fastmath':False,'parallel':False,'numba_threads':1}})
    run=FunctionType(original.run.__code__,{**original.run.__globals__,'candidate':candidate,'OUT':OUT,'DESIGN':DESIGN,'__file__':__file__},'run')
    run()
