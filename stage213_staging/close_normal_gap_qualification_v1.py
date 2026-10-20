"""Close all launched local diagnostics; unrun optional extensions remain unrun."""
from pathlib import Path
import os,sys,shutil
import bounded_normal_gap_trajectory_v1 as base
job,api=base.job,base.api
OUT=base.EVALBASE/'local_qualification_close_01'
INDEPENDENT=base.EVALBASE/'serial_split_independent_01/results.json'

def run():
    w,d=base.prerequisites();base.no_worker();r=base.sealed(INDEPENDENT)
    api.require(api.sha(INDEPENDENT)=='0a403408fe3dc7f02216da42b1ade40b56615ec71a4123b039ba50f059852087'
        and r['passed'] and r['exact_restart_full_rows'] and r['exact_restart_full_checkpoint'],'exact independent full restart gate')
    api.verify_mapping(r['inputs']);used,pending=base.ledger()
    api.require(not pending and used==r['inclusive_saved_steps']==r['independently_passing_saved_steps']==4000,'closed inclusive launched inventory')
    launched=sorted(p.parent.name for p in base.RUNBASE.glob('*/launch.json'))
    api.require(launched==['serial_01','split_a_01','split_b_01'],'all and only original three qualifying trajectories')
    inputs={str(p):api.sha(p) for p in (Path(__file__),base.WORK,INDEPENDENT,INDEPENDENT.parent/'completion.json',base.LOCAL/'results.json',base.LOCAL/'completion.json')}
    rates=[]
    for name in launched:
        folder=base.RUNBASE/name;row=base.sealed(folder/'results.json');plan=api.read(base.DESIGNBASE/(name+'.json'))
        api.verify_mapping(row['artifacts']);api.verify_mapping(plan['inputs']);api.verify_mapping(plan['sources'])
        rates.append(dict(name=name,saved_steps=row['steps'],compute_seconds=row['compute_seconds'],transaction_seconds=row['transaction_seconds']))
        for path in list(folder.glob('*'))+[base.DESIGNBASE/(name+'.json')]:
            if path.is_file():inputs[str(path)]=api.sha(path)
    free=shutil.disk_usage(base.ROOT).free;api.require(free>=w['minimum_free_disk_bytes'],'20GiB reserve')
    result=dict(utc=job.utc().isoformat(),local_numerical_qualification_passed=True,
        launched_qualification_accounting_closed=True,saved_new_trajectory_steps=used,
        independently_accepted_new_trajectory_steps=4000,failed_or_rejected_new_saved_steps=0,
        unresolved_reservations=[],exact_serial_split_full_rows=True,exact_serial_split_full_checkpoint=True,
        producer_classifier_not_used_in_independent_audit=r['producer_gap_classifier_never_called'],
        revised_normal_gap_policy_explicit=True,raw_geometry_membership_lubrication_swept_clearance_dwell_unchanged=True,
        old_stage205_and_stage209_remain_failed=True,all_owned_diagnostics_retired=True,
        launched_calls=launched,unrun_optional_calls=sorted(set(w['planned_calls'])-set(launched)),all_planned_calls_run=False,
        optional_extensions_claimed_passed=False,C_free_bytes=free,measured_local_rates=rates,
        full_six_case_stack_preflight_passed=False,resource_fit_verified=False,production_authorized=False,
        current_simulation_cutoff_utc=d['simulation_cutoff_utc'],current_final_audit_cutoff_utc=d['final_audit_deadline_utc'],
        inputs=inputs,next='Fresh six-case full-stack preflight and process/resource qualification, retaining the original cases/timesteps/horizon/other gates and explicit numerical-policy version. No more local extensions needed for this gate.',
        claim='All launched local diagnostic evidence closed and independently qualifying under explicit revised normal-gap operands. Optional unrun tests remain unrun. Not an original-gap pass, six-case completion, population release or empirical validation.')
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    print('NORMAL_GAP_LOCAL_QUALIFICATION_CLOSED',used,api.sha(OUT/'results.json'),flush=True)

if __name__=='__main__':run()
