"""Reuse the exact 462-held-call/3696-pointwise verification code, zero steps."""
from pathlib import Path
from types import FunctionType
import qualify_constant_pair_v1 as original
import batch_analytic_pair_v1 as candidate
import owned_performance_affinity_v1 as affinity
ROOT=original.ROOT;api=original.api;job=original.job
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/batch_pair_01'
DESIGN=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/batch_pair_01.json'


if __name__=='__main__':
    info=affinity.bind(14)
    job.commit(DESIGN.with_name('batch_pair_01_harness.json'),{'source_sha256':api.sha(__file__),
        'inherited_test_source':str(Path(original.__file__).resolve()),'inherited_test_source_sha256':api.sha(original.__file__),
        'candidate_sha256':api.sha(candidate.__file__),'owned_affinity':info,'new_trajectory_steps':0})
    run=FunctionType(original.run.__code__,{**original.run.__globals__,'candidate':candidate,'OUT':OUT,'DESIGN':DESIGN,'__file__':__file__},'run')
    run()
