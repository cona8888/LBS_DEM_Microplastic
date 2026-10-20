"""Separate zero-step comparison of the production bridge and calendar gate."""
from pathlib import Path
import os,shutil
import autonomous_completion_campaign_v1 as s
api,job=s.api,s.job
OUT=job.OUT/'independent_bridge_01'


def run():
    d=api.read(job.DESIGN);job.verify(d)
    old=api.read(s.pre.job.DESIGN);w=api.read(job.WORK);r=s.sealed(s.RESOURCE)
    prior=s.sealed(s.OLD_RESOURCE);checked=s.sealed(s.OLD_RESOURCE_AUDIT)
    b=s.sealed(s.BRIDGE/'results.json');dis=s.sealed(s.DISPOSITION)
    api.require(dis['old_campaign_status']=='failed_incomplete' and dis['old_terminal_audit']=='interrupted_unresolved' and not dis['old_failure_promoted'] and dis['fresh_production_checkpoint_source']=='original initial states only','old failure and audit disposition explicit')
    api.verify_mapping(dis['inputs'])
    unchanged=set(old)-s.ALLOWED
    api.require(all(d[k]==old[k] for k in unchanged) and d['budget']==old['budget'] and d['cases']==old['cases'] and d['numerical_gates']==old['numerical_gates'],'all scientific and numerical values identical')
    api.require(r['hours_with_margin']==prior['production_hours_with_margin']==checked['required_production_hours'] and r['bytes_with_margin']==prior['storage_bytes_with_margin'] and r['required_final_audit_hours']==checked['required_final_audit_hours'],'no optimistic resource change')
    for key in ('samples','cases','shape_costs','late_history_cost','queue','schedule_tests','call_limit_passed'):
        api.require(r[key]==prior[key],'same complete cost/queue basis '+key)
    available=(job.policy.utc(w['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    reserve=(job.policy.utc(w['final_audit_deadline_utc'])-job.policy.utc(w['simulation_cutoff_utc'])).total_seconds()/3600
    free=shutil.disk_usage(job.ROOT).free
    api.require(available>=r['hours_with_margin'] and reserve>=r['required_final_audit_hours'] and free>=checked['storage_with_reserve_bytes'],'independent revised resource arithmetic fits')
    api.require(b['new_trajectory_steps']==0 and b['zero_step_dispatch_permutations']==720 and len(b['corrupt_amendments_rejected'])==7,'bounded administrative guard checks')
    api.require(not job.RUN.exists() and not s.active_owned(),'no campaign/evaluator before bridge completion')
    for name in s.IDENTICAL:
        api.require(getattr(job,name).__code__==getattr(s.pre.job,name).__code__,'independent lifecycle bytecode '+name)
    api.require(job.execute_segment.__code__==s.pre.execute_segment.__code__ and s.raw_execute.__code__==s.pre.raw_execute.__code__,'independent integration/contact-route identity')
    api.require(job.codec is s.pre.job.codec and job.kernel is s.pre.job.kernel and job.observer is s.pre.job.observer,'same codec and numerical auditor')
    inputs=[job.DESIGN,job.WORK,s.BRIDGE/'results.json',s.DISPOSITION,s.RESOURCE,s.OLD_RESOURCE,s.OLD_RESOURCE_AUDIT,s.CLOSE,s.AUDIT,Path(__file__)]
    result=dict(passed=True,new_trajectory_steps=0,design_sha256=api.sha(job.DESIGN),required_production_hours=r['hours_with_margin'],available_production_hours=available,required_final_audit_hours=r['required_final_audit_hours'],available_final_audit_hours=reserve,storage_with_reserve_bytes=checked['storage_with_reserve_bytes'],free_D_bytes=free,producer_slots=3,global_outstanding_bound=6,old_audit_disposition='interrupted_unresolved, preserved',utc=job.utc().isoformat(),inputs={str(p):api.sha(p) for p in inputs})
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
    print('INDEPENDENT_BRIDGE_PASS',api.sha(job.DESIGN),flush=True)


if __name__=='__main__':run()
