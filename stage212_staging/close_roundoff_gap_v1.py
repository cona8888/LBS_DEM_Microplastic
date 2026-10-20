"""Immutable zero-trajectory qualification handoff; no production permission."""
from pathlib import Path
import os,sys,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage210_staging'))
import authenticate_failed_system_v1 as source
job,api=source.job,source.api
BASE=ROOT/'stage212_evaluations/roundoff_gap_20261001'
OUT=BASE/'zero_step_close_01'

def run():
    api.require(not source.frozen.active_owned(False),'all prior numerical workers/auditors retired')
    contract=ROOT/'stage212_designs/roundoff_gap_20261001/contract_02.json'
    w=api.read(contract);api.verify_mapping(w['sources']);api.verify_mapping(w['inputs']);job.verify(api.read(job.DESIGN))
    report=BASE/'qualification_02/results.json';independent=BASE/'independent_01/results.json'
    expected={report:'42e9d724cd656564e9da66b492de80dc87a0a5de348aa1a90cf66d0c2801da11',
              independent:'abb5112648c56fd3403a8d80215191a1592a319f5ff3abb137cdedce6e602ece'}
    for p,h in expected.items():
        api.require(api.sha(p)==h and api.read(p.parent/'completion.json')['results_sha256']==h,'sealed qualification result')
    r=api.read(report);a=api.read(independent)
    api.verify_mapping(r['inputs']);api.verify_mapping(r['artifacts']);api.verify_mapping(a['inputs'])
    api.require(r['held_passes']==r['held_system_count']==a['held_systems_independently_passed']==30
                and a['independent_zero_step_policy_verification_passed'] and len(a['negative_controls_rejected'])==9,'independent bounded scope')
    api.require(r['new_trajectory_steps']==a['new_trajectory_steps']==0 and not r['production_authorized'] and not a['production_authorized'],'zero trajectory/no production')
    free=shutil.disk_usage(ROOT).free;api.require(free>=w['minimum_free_disk_bytes'],'20GiB reserve')
    paths=[Path(__file__),contract,report,report.parent/'completion.json',independent,independent.parent/'completion.json',
           BASE/'qualification_01/failure.json',BASE/'qualification_01/launch.json',ROOT/'stage212_staging/audit_roundoff_gap_v1.py']
    result=dict(utc=job.utc().isoformat(),zero_step_qualification_closed=True,
                independent_held_systems_passed=30,maximum_original_style_relative_residual=max(float(m['rational_decimal_affine_relative_residual']) for m in a['held_metrics']),
                saved_new_trajectory_steps=0,independently_accepted_new_trajectory_steps=0,
                old_stage205_and_stage209_remain_failed=True,policy_revision_explicit=True,
                installed_full_stack_repair=False,trajectory_qualification_passed=False,production_authorized=False,
                all_prior_owned_checks_retired=True,C_free_bytes=free,inputs={str(p):api.sha(p) for p in paths},
                simulation_cutoff_utc=w['simulation_cutoff_utc'],final_audit_cutoff_utc=w['audit_cutoff_utc'],
                remaining_production_hours=(job.policy.utc(w['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600,
                previous_production_planning_hours=117.145155,
                next='Freeze independent full-stack provenance and geometry-policy audit; qualify bounded local serial/split trajectories before fresh six-case process/resource preflight. Reassess schedule before production.',
                claim='Revised sphere arithmetic policy only; finite signed boundary controls and 30 captured held solves independently verified. No original-contract promotion, full trajectory, campaign completion, population release or empirical validation.')
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    print('ROUND_OFF_ZERO_STEP_CLOSED',api.sha(OUT/'results.json'),result['remaining_production_hours'],flush=True)

if __name__=='__main__':run()
