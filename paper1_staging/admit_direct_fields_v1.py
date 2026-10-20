"""Post-retirement admission of a sealed direct-field study; zero transport work."""
from pathlib import Path
from datetime import datetime,timezone
import sys
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
import load_direct_fields_v1 as fields
ROOT=Path(__file__).resolve().parents[1]
DESIGN=ROOT/'paper1_designs/direct_cpd6_flows_20261013_attempt02/design_01.json'
DESIGN_SHA='025521dbe6fd2315aba2efd2178f0a20a54676401c057053e9b7a4cf327d5a0d'
OUT=ROOT/'paper1_runs/direct_cpd6_flows_20261013_attempt02'
sys.path.insert(0,str(ROOT/'paper1_staging'))
import solve_direct_fields_v2 as original


def retired(launch):
    try:
        proc=psutil.Process(launch['pid']);birth=proc.create_time()
        if birth!=launch['created']:return dict(retired=True,different_birth=True,observed_birth=birth)
        fields.require(proc.cmdline()==launch['command'],'Matching birth needs exact accessible command')
        return dict(retired=False,exact_live_command=True)
    except psutil.NoSuchProcess:return dict(retired=True,no_such_process=True)


def admit(observed_supervisor_exit_code,session_id):
    fields.require(observed_supervisor_exit_code==0 and session_id==43677,'Actual root supervisor exit0 observation required')
    fields.require(fields.sha(DESIGN)==DESIGN_SHA,'Exact frozen field study')
    d=fields.read(DESIGN)
    fields.require(datetime.now(timezone.utc)<datetime.fromisoformat(d['end_utc']),'Absolute field-work deadline')
    final=fields.sealed(OUT/'final_disposition_01/results.json')
    fields.require(final['passed'] and final['accepted_fields']==[x['id'] for x in d['cases']]
                   and final['completed_gpu_updates']==final['attempted_gpu_updates']==7984
                   and final['particle_transport_steps']==0,'Complete accepted direct-field ledger')
    original.authenticate(d['source_files']);original.authenticate(d['inputs']);original.authenticate(final['artifacts'])
    receipts=[]
    for case in d['cases']:
        path=OUT/(case['id']+'_solve')/'independent_evaluation_01/results.json'
        row=fields.sealed(path)
        fields.require(row['passed'] and all(row['checks'].values()) and row['case']==case
                       and row['design_sha256']==DESIGN_SHA,'Independent unmodified field science gates')
        original.authenticate(row['artifacts'])
        receipts.append(dict(path=str(path),sha256=fields.sha(path),
                             achieved_mean_interstitial_velocity_m_s=row['mean_interstitial_velocity_m_s']))
    exit=fields.read(OUT/'controller_01/exit.json')
    fields.require(exit['returncode']==0 and exit['retired'],'Worker exit and closed logs')
    original.authenticate(exit['closed_logs'])
    identities=[]
    for path in (OUT/'controller_01/launch.json',OUT/'controller_01/worker_launch.json',OUT/'worker_launch.json'):
        launch=fields.read(path);status=retired(launch)
        fields.require(status['retired'],'All exact owned identities retired')
        identities.append(dict(path=str(path),sha256=fields.sha(path),launch=launch,inspection=status))
    receipt=OUT/'retirement_01'
    original.seal(receipt,dict(passed=True,all_exact_owned_identities_retired=True,source_and_inputs_reauthenticated=True,
        design_sha256=DESIGN_SHA,final_disposition_sha256=fields.sha(OUT/'final_disposition_01/results.json'),
        observed_supervisor_exit_code=observed_supervisor_exit_code,root_exec_session_id=session_id,
        completed_gpu_updates=7984,prior_failed_attempt_gpu_updates=2065,unknown_gpu_updates=0,
        particle_transport_steps=0,identities=identities,closed_logs=exit['closed_logs'],independent_receipts=receipts,
        admission_scope='Direct stationary fields only; new particle dispatch/exposure requires separate frozen design.',
        utc=datetime.now(timezone.utc).isoformat()))
    original.seal(fields.REGISTRY.parent,dict(passed=True,study_path=str(OUT),design_path=str(DESIGN),
        design_sha256=DESIGN_SHA,retirement_sha256=fields.sha(receipt/'results.json'),
        contract_sha256=original.CONTRACT_SHA,flow_levels=[.5,1.,2.],
        no_velocity_normalization=True,no_particle_transport_authority=True,utc=datetime.now(timezone.utc).isoformat()))
    print('DIRECT_FIELDS_RETIRED_AND_ADMITTED',fields.sha(receipt/'results.json'),fields.sha(fields.REGISTRY),flush=True)


if __name__=='__main__':admit(int(sys.argv[1]),int(sys.argv[2]))
