"""Zero-step qualification closure; no production or scientific promotion."""
from pathlib import Path
import cone_feasibility_stack_preflight_v1 as s
api,job=s.api,s.job
def run():
    d=api.read(job.DESIGN);job.verify(d)
    pf=s.sealed(job.OUT/'preflight_01/results.json');audit=s.sealed(job.OUT/'independent_readiness_01/results.json');resource=s.sealed(job.OUT/'resource_schedule_01/results.json');checked=s.sealed(job.OUT/'resource_independent_01/results.json')
    api.require(pf['new_steps']==audit['stage208_preflight_steps_verified']==17000 and audit['numerical_qualification_passed'] and audit['process_qualification_passed'],'full independent bounded stack')
    api.require(audit['raw_records_independently_decoded']==35 and len(audit['numerical_reaudits'])==27 and audit['all_owned_processes_retired'],'complete raw/numerical/process inventory')
    api.verify_mapping(pf['artifacts']);api.verify_mapping(pf['sources'])
    api.require(checked['independent_calculation_passed'] and checked['resource_gate_passed']==resource['resource_gate_passed'] and checked['resource_result_sha256']==api.sha(job.OUT/'resource_schedule_01/results.json'),'independent fit binding')
    api.require(not job.RUN.exists(),'production not launched')
    files=[Path(__file__),job.DESIGN,s.WORK,s.CLOSE,job.OUT/'preparation_failure_01.json']
    files +=[job.OUT/p/f for p in ('prelaunch_01','preflight_01','independent_readiness_01','resource_schedule_01','resource_independent_01') for f in ('results.json','completion.json')]
    result=dict(qualification_closed=True,new_trajectory_steps=0,separate_stage208_saved_and_independently_passing_steps=17000,separate_stage207_saved_and_independently_passing_steps=s.sealed(s.CLOSE)['independently_passing_saved_steps'],unresolved_reservations=0,numerical_qualification_passed=True,process_qualification_passed=True,resource_gate_passed=resource['resource_gate_passed'],required_production_hours=checked['required_production_hours'],required_final_audit_hours=checked['required_final_audit_hours'],all_preflight_workers_retired=True,production_authorized=False,production_launched=False,inputs={str(p):api.sha(p) for p in files},claim='Bounded numerical/process qualification and measured resource preparation only. Stage205 remains failed/incomplete with one original terminal evaluator still active. All original selected/fine science gates remain to be established in fresh production.')
    out=job.OUT/'qualification_close_01';job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')));print('CONE_STACK_CLOSED',api.sha(out/'results.json'),flush=True)
if __name__=='__main__':run()
