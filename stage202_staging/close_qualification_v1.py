"""Zero-step closure of bounded Stage202; preserve failed resource gate."""
from pathlib import Path
import os
import psutil
import resource_reassessment_v1 as resources

pre=resources.pre
job,api=pre.job,pre.api
OUT=job.OUT/'qualification_close_01'


def run():
    d=api.read(job.DESIGN);job.verify(d)
    pf=resources.sealed(job.OUT/'preflight_01/results.json')
    ready=resources.sealed(job.OUT/'independent_readiness_02/results.json')
    forecast=resources.sealed(resources.OUT/'results.json')
    checked=resources.sealed(job.OUT/'resource_independent_01/results.json')
    identity=api.read(job.OUT/'independent_readiness_02/retirement_identity.json')
    api.verify_mapping(pf['artifacts']);api.verify_mapping(identity['inputs'])
    api.require(pf['new_steps']==ready['stage202_preflight_steps_verified']==17000,'complete distinct Stage202 step ledger')
    api.require(ready['numerical_qualification_passed'] and ready['process_qualification_passed'] and len(ready['numerical_reaudits'])==27 and ready['raw_records_independently_decoded']==35,'full bounded qualification')
    for row in ready['raw_records']:
        api.require(api.sha(row['path'])==row['raw_sha256'],'raw archives unchanged since independent decode')
    api.require(checked['independent_calculation_passed'] and not checked['resource_gate_passed'] and not forecast['resource_gate_passed'],'retain failed deadline gate')
    api.require(checked['resource_result_sha256']==api.sha(resources.OUT/'results.json'),'independent forecast binding')
    api.require(ready['retirement_identity_sha256']==api.sha(job.OUT/'independent_readiness_02/retirement_identity.json'),'retirement proof binding')
    scripts={os.path.normcase(str(p.resolve())) for p in (job.SELF,job.PREFLIGHT_SCRIPT,pre.ROOT/'stage200_staging/revised_deadline_campaign_v1.py',pre.ROOT/'stage202_staging/audit_contact_repaired_stack_v2.py')}
    live=[]
    for p in psutil.process_iter(['pid','name']):
        if 'python' not in (p.info['name'] or '').lower(): continue
        try:
            cmd=p.cmdline()
            if scripts & {os.path.normcase(os.path.normpath(x)) for x in cmd}:
                live.append(dict(pid=p.pid,argv=cmd))
        except psutil.NoSuchProcess: continue
    api.require(not live,'no owned simulation, preflight or terminal-evaluator command alive')
    api.require(not job.RUN.exists(),'no production launched')
    old_eval=pre.ROOT/'stage200_evaluations/revised_deadline_campaign_20260927/evaluation_01'
    api.require(not old_eval.exists(),'old terminal evaluation still unresolved, not silently accepted')
    files=[job.DESIGN,pre.WORK,job.OUT/'preparation_failure_01.json',job.OUT/'preflight_01/results.json',job.OUT/'preflight_01/completion.json',job.OUT/'independent_readiness_01/launch.json',job.OUT/'independent_readiness_01/failure.json',job.OUT/'independent_readiness_02/results.json',job.OUT/'independent_readiness_02/completion.json',job.OUT/'independent_readiness_02/retirement_identity.json',resources.PROTOCOL,resources.OUT/'results.json',resources.OUT/'completion.json',job.OUT/'resource_independent_01/results.json',job.OUT/'resource_independent_01/completion.json',Path(__file__)]
    result=dict(closure_audit_passed=True,utc=job.utc().isoformat(),new_trajectory_steps=0,
        stage202_saved_and_independently_passing_steps=17000,unresolved_step_reservations=0,
        numerical_qualification_passed=True,process_qualification_passed=True,resource_gate_passed=False,
        production_authorized=False,production_launched=False,all_owned_workers_retired=True,
        original_stage200_terminal_evaluation='Absent output/process; exit status and cause unknown; not restarted. Original campaign remains failed/incomplete.',
        preserved_failures=['Zero-step preparation directory error','Zero-step v1 audit PID-reuse false-positive','Current production-time and final-audit-time resource gates'],
        required_production_hours=checked['required_production_hours'],available_production_hours_at_assessment=checked['available_production_hours'],
        required_final_audit_hours=checked['required_final_audit_hours'],available_final_audit_hours=checked['available_final_audit_hours'],
        storage_with_reserve_bytes=checked['storage_with_reserve_bytes'],free_D_bytes=checked['free_D_bytes'],maximum_backlog=checked['maximum_backlog'],
        next_boundary='No further trajectory under exhausted17,000-step preflight contract. Resolve old terminal-audit disposition and approve revised production/audit windows before a new immutable campaign.',
        scientific_scope='Bounded same-physics numerical/process qualification only. No full-path result, release estimate or empirical validation.',
        inputs={str(f):api.sha(f) for f in files})
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
    print('STAGE202_CLOSED',api.sha(OUT/'results.json'),flush=True)


if __name__=='__main__':run()
