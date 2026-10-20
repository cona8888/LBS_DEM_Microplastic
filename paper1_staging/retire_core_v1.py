"""Independent post-exit closure of one bounded Paper1 numerical window."""
from pathlib import Path
from datetime import datetime,timezone
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_core_v2 as shared
s=shared.s


def retire(root,observed_exit,session):
    root=Path(root).resolve();directory=s.ROOT/'paper1_designs'/root.name
    plan_path=directory/'design_01.json';physical=directory/'physical_cases_01.json'
    plan=s.read(plan_path);final=s.fields.sealed(root/'final_disposition_01/results.json')
    s.require(datetime.now(timezone.utc)<datetime.fromisoformat(plan['end_utc']),'Close within absolute window')
    s.require(observed_exit==0 and final['passed'],'Actual successful supervisor exit and final disposition')
    s.require(final['design_sha256']==s.sha(plan_path) and plan['physical_design_sha256']==s.sha(physical),
              'Exact frozen numerical/physical designs')
    s.api.verify_mapping(plan['source_files']);s.api.verify_mapping(plan['physical_inputs'])
    identities=[]
    for path in (root/'controller_01/launch.json',root/'controller_01/worker_launch.json',root/'worker_launch.json'):
        launch=s.read(path);status=s.identity(launch);s.require(status['retired'],'All exact owned identities retired')
        identities.append(dict(path=str(path),sha256=s.sha(path),inspection=status))
    exit=s.read(root/'controller_01/exit.json')
    s.require(exit['returncode']==0 and exit['identity']['retired'],'Actual worker exit')
    s.api.verify_mapping(exit['logs'])
    codec=shared.archives.build(s.q.job.codec,preset=9)
    docs=shared.documents.build(s.q.job.codec,s.api)
    listed=final['production_labels']
    s.require(len(listed)==len(set(listed)) and listed==[f'production_{i:05d}' for i in range(1,len(listed)+1)],
              'Exactly ordered contiguous production inventory')
    actual=sorted(p.name for p in (root/'records').glob('production_*'))
    s.require(actual==listed,'No omitted production failure/reservation')
    prefix=before=None;count=0;artifacts={};terminal=None
    for label in listed:
        folder=root/'records'/label
        guard=s.fields.sealed(folder/'guard_completion/results.json');s.api.verify_mapping(guard['artifacts'])
        receipt=docs.read(folder/'results.json')
        s.require(s.read(folder/'completion.json')['results_sha256']==s.sha(folder/'results.json')
                  and receipt['passed'] and receipt['summary']['passed'] and guard['passed'],'Full independent audit documents sealed')
        rec,prefix=codec.read_record(folder/'call.json.xz',s.sha(physical),prefix)
        s.require(rec['input_checkpoint_sha256']==s.api.digest(before),'Contiguous complete raw ancestry')
        s.require(receipt['input_checkpoint_sha256']==s.api.digest(before)
            and receipt['output_checkpoint_sha256']==s.api.digest(rec['result']['checkpoint'])
            and guard['full_checkpoint_sha256']==receipt['output_checkpoint_sha256'],'Raw/full-checkpoint/audit identity')
        count+=len(rec['rows']);terminal=rec['result'];before=terminal['checkpoint']
        artifacts.update(guard['artifacts'])
        artifacts.update({str(p):s.sha(p) for p in (folder/'guard_completion').glob('*') if p.is_file()})
    s.require(count==final['accepted_physical_steps']==before['state']['steps'] and s.api.digest(before)==final['full_checkpoint_sha256'],
              'All physical steps and last FULL checkpoint authenticated')
    s.require(s.api.digest(docs.read(root/'recoverable/checkpoint.json'))==s.api.digest(before),'Standalone FULL checkpoint recovered losslessly')
    diagnostics=0
    for label in ('serial','split_a','split_b'):
        gate=s.fields.sealed(root/'records'/label/'guard_completion/results.json');s.api.verify_mapping(gate['artifacts'])
        s.require(gate['passed'],'Discarded diagnostic original gates');diagnostics+=gate['saved_steps']
    s.require(diagnostics==final['discarded_diagnostic_steps']==512 and s.fields.sealed(root/'restart_01/results.json')['passed'],
              'Exact restart diagnostic accounting')
    s.require(final['known_unaccepted_saved_steps']==final['unknown_reserved_steps_upper_bound']==0,
              'No unaccepted/unknown work hidden')
    for path in (root/'recoverable').glob('*'):
        if path.is_file():artifacts[str(path)]=s.sha(path)
    s.seal(root/'retirement_01',dict(passed=True,all_exact_owned_identities_retired=True,source_and_inputs_reauthenticated=True,
        observed_supervisor_exit_code=observed_exit,root_exec_session_id=session,design_sha256=s.sha(plan_path),
        final_disposition_sha256=s.sha(root/'final_disposition_01/results.json'),identities=identities,closed_logs=exit['logs'],
        accepted_physical_steps=count,discarded_diagnostic_steps=512,known_unaccepted_saved_steps=0,unknown_reserved_steps_upper_bound=0,
        full_checkpoint_sha256=s.api.digest(before),native_complete=final['native_complete'],
        full_path_accuracy_passed=False,core_result_admitted=False,artifacts=artifacts,utc=s.utc()))
    print('PAPER1_WINDOW_RETIRED',s.sha(root/'retirement_01/results.json'),count,final['native_complete'],flush=True)


if __name__=='__main__':retire(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]))
