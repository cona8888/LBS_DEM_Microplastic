"""Source-only preparation for atomic create-only actor JSON publication.

Both retired negatives and their complete charges stay pinned. This creates
no clock, human grant, execution authority, warm call or numerical producer.
"""
from pathlib import Path
import importlib.util
import os
import re
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
STAGING=ROOT/'paper1_staging'


def prepare():
    source=STAGING/'run_stepdoubling_qualification_v4.py'
    spec=importlib.util.spec_from_file_location('_fourth_recovery_source_preparation',source)
    run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
    run.environment()
    origin=ROOT/'paper1_designs/full_horizon_repair_20261018'
    previous_folder=origin/'recovery_03'
    old_ready=run.sealed(previous_folder/'preparation_03/results.json',positive=True)
    previous_proposal=run.read(previous_folder/'qualification_recovery_03.json')
    diagnosis_path=origin/'failure_diagnosis_qualification_03/results.json'
    diagnosis=run.sealed(diagnosis_path,positive=True)
    previous_path=ROOT/'paper1_runs/full_horizon_repair_20261018_recovery03/final_execution_receipt_01/results.json'
    previous=run.sealed(previous_path,positive=True)
    run.need(run.sha(previous_path)=='48722e77c5f07342bbd371c80194556f7516fe3e300b4279221e7f7d1a8375f6', 'exact third retired negative')
    run.need(diagnosis.get('implementation_defect_confirmed') is True, 'strict journal-publication defect diagnosis, never a parser waiver or physical-gate change')
    run.need(previous['closure_complete'] is True and previous['qualified'] is False, 'closed negative, no admitted prefix')
    failed=run.sealed(previous_path.parents[1]/'final_disposition_01/results.json')
    counts=failed['ledger']
    run.need(counts['work_rows']==5446 and counts['records']==6
             and counts['accepted_all_work_rows']==640 and counts['known_unaccepted_work_rows']==0
             and counts['unknown_reserved_work_upper_bound']==4806 and counts['production_records']==0,
             'retain unknown4806 plus640 admitted rows; never infer unobserved actual work')
    run.need(not any(p.exists() for p in(run.OUT,run.PLAN,run.AUTH,run.PREPARED)), 'one separate inactive preparation')
    identities=list(old_ready['prior_exact_process_identities'])
    for row in previous['exact_retirement_after']:
        x=row['launch']
        if not any((v['pid'],v['created'],v['command'])==(x['pid'],x['created'],x['command']) for v in identities):identities.append(x)
    before=run.assert_retired(identities)
    sources=dict(old_ready['source_files'])
    for name in('run_stepdoubling_qualification_v4.py','launch_stepdoubling_qualification_v4.py',
                'check_stepdoubling_recovery_v4.py','monitor_stepdoubling_qualification_v4.py',
                'prepare_failure_diagnosis_qualification_v3.py','build_stepdoubling_recovery_v4.py',Path(__file__).name):
        p=STAGING/name;run.need(p.is_file(),'actual repaired source '+name);sources[str(p)]=run.sha(p)
    inputs=dict(old_ready['physical_inputs'])
    evidence=dict(previous_proposal['evidence_files'])
    for p in(run.APPROVAL,run.CLOCK,previous_folder/'authorization_03.json',previous_folder/'design_03.json',
             previous_folder/'preparation_03/results.json',previous_folder/'preparation_03/completion.json',
             previous_folder/'qualification_recovery_03.json',diagnosis_path,diagnosis_path.with_name('completion.json'),
             previous_path,previous_path.with_name('completion.json')):
        evidence[str(p)]=run.sha(p)
    historical=run.merge_maps(old_ready['historical_evidence_files'],previous['artifacts'])
    for mapping in(sources,inputs,evidence,historical):run.verify_mapping(mapping)
    controls=[]
    for name in('check_stepdoubling_recovery_v4.py',):
        path=STAGING/name;started=time.monotonic()
        result=subprocess.run([str(run.PYTHON),'-B',str(path)],cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True,timeout=180)
        match=re.search(r'Ran (\d+) tests',result.stderr)
        controls.append(dict(source_file=str(path),source_sha256=run.sha(path),returncode=result.returncode,
            test_count=int(match.group(1)) if match else None,seconds=time.monotonic()-started,
            stdout=result.stdout,stderr=result.stderr,no_new_native_force_or_transport=True))
        print('RECOVERY4_SOURCE_CONTROL',name,result.returncode,flush=True)
        if result.returncode:
            target=next(run.DESIGNS/f'preparation_negative_{i:02d}.json' for i in range(1,100) if not(run.DESIGNS/f'preparation_negative_{i:02d}.json').exists())
            run.commit(target,dict(passed=False,controls=controls,source_files=sources,new_native_calls=0,new_transport_steps=0,dispatch_authorized=False))
            raise RuntimeError('Source repair preparation failed; negative preserved '+str(target))
    for mapping in(sources,inputs,evidence,historical):run.verify_mapping(mapping)
    resources=run.resource_guard(force_inventory=True)
    remaining=run.OWN_BYTES-resources['own_bytes']
    run.need(remaining>0 and resources['total_retained_bytes']+remaining<=run.RETENTION_BYTES
             and resources['free_bytes']-remaining>=run.FREE_BYTES,'all four run trees share original output/storage/free limits')
    value=dict(schema='paper1.atomic-journal-recovery.source-preparation.v4',passed=True,utc=run.utc(),
        source_files=sources,physical_inputs=inputs,evidence_files=evidence,historical_evidence_files=historical,
        controls=controls,prior_exact_process_identities=identities,retirement_before=before,
        retirement_after=run.assert_retired(identities),resources=resources,
        all_required_interfaces_present=True,source_interface_checks=run.source_interfaces(),
        original_approval_sha256=run.sha(run.APPROVAL),original_clock_sha256=run.sha(run.CLOCK),
        initial_closure_sha256='ebed1438521447cb4fffda16a0784140118456487bc3b9626479b4907d5bce66',
        diagnosis_sha256='bc5c1a5665b4dd8ad984465f4918d121cb8991f7e1d677e3e2d5ef742801916b',
        previous_closure_sha256=run.sha(previous_path),previous_diagnosis_sha256=run.sha(diagnosis_path),
        scope_remaining=run.approval_scope(),conservative_total_prior_work_rows=8233,
        total_prior_integration_records=22,total_prior_warm_invocations=6,total_prior_windows=3,
        prior_online_audited_discarded_rows=3392,prior_known_unaccepted_rows=3,
        original_unknown_reserved_rows=32,previous_unknown_reserved_rows=4806,total_prior_unknown_reserved_rows=4838,all_failed_attempts_and_negative_records_preserved=True,
        native_restart_qualification_completed=False,native_mechanical_qualification_completed=False,
        native_solver_calls=0,new_transport_steps=0,dispatch_authorized=False,
        fresh_authority_created=False,original_clock_reset=False,any_resource_ceiling_increased=False)
    run.seal(run.PREPARED.parent,value)
    print('RECOVERY4_SOURCE_PREPARATION_COMPLETE',run.sha(run.PREPARED),flush=True)


if __name__=='__main__':prepare()
