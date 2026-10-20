"""V1 cumulative-vs-call ledger reader failure preserved; same resource arithmetic."""
from pathlib import Path
import sys
import resource_normal_gap_v1 as s
api,job=s.api,s.job
FIRST=Path(__file__).with_name('audit_resource_normal_gap_v1.py')
FAIL=s.OUT.parent/'audit_v1_failure_01'
source=FIRST.read_text()
before="a['steps']==a['total_saved_steps']==a['independently_accepted_steps']"
after="a['steps']==a['independently_accepted_steps'] and a['total_saved_steps']=={'serial_01':2000,'split_a_01':3000,'split_b_01':4000}[e.parent.name]"
api.require(source.count(before)==1,'one exact per-call versus cumulative ledger reader correction')
source=source.replace(before,after)
before="OUT=s.OUT.parent/'independent_01'"
api.require(source.count(before)==1,'new exclusive independent output')
source=source.replace(before,"OUT=s.OUT.parent/'independent_02'")
before="        resource_result_sha256=api.sha(s.OUT/'results.json'),protocol_sha256=api.sha(s.PROTOCOL),production_authorized=False,clock_revision_not_yet_bound_to_production=True,utc=job.utc().isoformat())"
api.require(source.count(before)==1,'preserved failure result binding')
source=source.replace(before,"        v1_reader_failure_sha256=api.sha(FAIL/'results.json'),v1_source_sha256=api.sha(FIRST),per_call_and_cumulative_steps_distinct=True,\n"+before)
ns=dict(__name__='_stage218_independent_v2',__file__=__file__,FIRST=FIRST,FAIL=FAIL)
exec(compile(source,__file__+'::same_resource_arithmetic_correct_ledger_semantics','exec'),ns)
if __name__=='__main__':
    api.require(not FAIL.exists(),'preserve observed V1 reader failure once')
    job.commit(FAIL/'results.json',{'failed':True,'new_trajectory_steps':0,'error':"RuntimeError('closed local steps')",'scope':'Independent V1 resource audit stopped before output after incorrectly comparing cumulative total_saved_steps with per-call steps. serial2000/cumulative2000; split_a1000/cumulative3000; split_b1000/cumulative4000. Producer forecast unchanged.',
        'v1_source_sha256':api.sha(FIRST),'resource_protocol_sha256':api.sha(s.PROTOCOL),'producer_resource_sha256':api.sha(s.OUT/'results.json'),'v2_source_sha256':api.sha(__file__)})
    job.commit(FAIL/'completion.json',{'failure_preserved':True,'results_sha256':api.sha(FAIL/'results.json')})
    ns['run']()
