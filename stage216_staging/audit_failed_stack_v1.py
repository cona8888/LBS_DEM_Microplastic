"""Failure-inclusive independent replay. Never promotes the stopped preflight."""
from pathlib import Path
import copy, os
import audit_same_policy_stack_v1 as prior
wrapper=prior.wrapper
api,job=wrapper.api,wrapper.job
FAIL=job.OUT/'preflight_01/failure.json'
OUT=job.OUT/'failed_stack_independent_01'

def failure_ledger(d):
    f=api.read(FAIL)
    api.require(f['error']=="RuntimeError('isolated unchanged lifecycle root_for')"
        and f['known_probe_steps']==11000 and f['live_saved_steps']==6000
        and f['stage216_known_accepted_steps']==17000 and not f['unresolved_probes']
        and f['all_probe_children_retired'],'exact preserved administrative fixture failure')
    api.require(not (job.OUT/'preflight_01/results.json').exists(),'no preflight completion fabricated')
    first,_=job.codec.read_record(job.PREFLIGHT/'probes/split_first.json.xz',api.sha(job.DESIGN))
    ratios=[]
    for index in range(6):
        rec,_=job.codec.read_record(job.PREFLIGHT/'probes'/f'parallel_{index}.json.xz',api.sha(job.DESIGN))
        ratios.append(rec['compute_call_wall_s']/first['compute_call_wall_s'])
    return {'new_steps':17000,'prior_stage216_steps':0,'parallel_slowdown_ratios':ratios}

source=prior.source
changes={
    "OUT = job.OUT/'independent_readiness_01'":"OUT = job.OUT/'failed_stack_independent_01'",
    'r = job.verify_preflight(d)':'r = failure_ledger(d)',
    "len(all_paths) == 35, '15 probes, 12 live records, eight zero-step fixtures'":"len(all_paths) == 31, '15 probes, 12 live records, four saved unfinished zero-step fixture copies'",
    "job.verify(d); job.verify_preflight(d)":"job.verify(d); failure_ledger(d)",
    "'numerical_qualification_passed':True, 'process_qualification_passed':True":"'numerical_qualification_passed':True, 'process_qualification_passed':False, 'preflight_passed':False, 'failure_accounting_closed':True, 'saved_steps':actual, 'independently_physical_passing_steps':actual, 'producer_classifier_never_called':True",
    "api.sha(pre.OUT/'results.json')":"api.sha(FAIL)",
    "{'passed':True,'results_sha256':api.sha(OUT/'results.json')}":"{'accounting_closed':True,'preflight_passed':False,'results_sha256':api.sha(OUT/'results.json')}",
    'STAGE216_INDEPENDENT_PASS':'STAGE216_FAILED_INDEPENDENT_ACCOUNTED'
}
for before,after in changes.items():
    api.require(source.count(before)==1,'exact failed-inclusive audit substitution '+before)
    source=source.replace(before,after)
start=source.index('        fixtures = []\n')
end=source.index("        api.require(actual == r['new_steps']",start)
source=source[:start]+"""        fixture_root=job.PREFLIGHT/'protocol_fixtures'
        api.require(not (fixture_root/'cutoff_drain/auditor_complete.json').exists()
            and not (fixture_root/'failure_drain').exists(),'unfinished drain tests stay unpassed')
        fixtures=[{'name':'cutoff_drain','saved_copies':4,'passed_audits':0,'completed':False,'new_trajectory_steps':0},
                  {'name':'failure_drain','saved_copies':0,'completed':False,'new_trajectory_steps':0}]
        inputs={str(p):api.sha(p) for p in job.PREFLIGHT.rglob('*') if p.is_file()}
        inputs.update(d['sources']);inputs.update(d['inputs'])
        inputs.update({str(p):api.sha(p) for p in [job.DESIGN,FAIL,Path(__file__)]})
        api.verify_mapping(inputs)
"""+source[end:]
before="'design_sha256':dsha, 'preflight_result_sha256':"
api.require(source.count(before)==1,'failure closure input seal site')
source=source.replace(before,"'inputs':inputs, 'stage216_original_fixture_failure_preserved':True, 'unresolved_reservations':[], 'design_sha256':dsha, 'preflight_result_sha256':")
ns=dict(prior.ns,__name__='_stage216_failed_accounting',__file__=__file__,failure_ledger=failure_ledger,FAIL=FAIL)
exec(compile(source,__file__+'::independent_full_physics_failure_accounting','exec'),ns)
if __name__=='__main__':
    with wrapper.refs.reference.forbid_producer():ns['run']()
