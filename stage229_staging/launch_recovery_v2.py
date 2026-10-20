"""Separate same-window original-baseline recovery; never relaunch cost work.

The initial failed attempt and its finalizer remain frozen. Every initial exact
launch identity must retire and its accounting must seal before this controller
can start. No numerical worker stack is imported by the controller.
"""
from pathlib import Path
from datetime import datetime
import ctypes, os, subprocess, sys, time
import psutil
import campaign_common_v1 as c

HERE=Path(__file__).resolve().parent
DESIGN=c.DESIGNS/'supervisor_design_02.json'
FOLDER=c.RUN/'supervisor_02'
LAUNCHER=c.RUN/'launcher_02'
WORK=c.RUN/'run_02'
OLD=c.RUN/'supervisor_01'
PYTHON=Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
DISPATCH=c.OUT/'dispatch_decision_02/results.json'
PRIOR_FINAL=c.OUT/'final_disposition_01/results.json'
RETIREMENT=c.OUT/'initial_retirement_01/results.json'
DIAGNOSIS=c.OUT/'failure_diagnosis_01/results.json'


def require(condition,message):
    if not condition:raise RuntimeError(message)


def exact(record):
    """Access denial is not proof of retirement; both identity fields are exact."""
    command=record.get('command',record.get('argv'))
    require(type(record.get('pid')) is int and type(command) is list
            and type(record.get('created')) in (int,float),'Qualified exact launch receipt')
    if 'command' in record and 'argv' in record:
        require(record['command']==record['argv'],'Conflicting command/argv launch identity')
    try:
        p=psutil.Process(record['pid'])
        return p if p.create_time()==record['created'] and p.cmdline()==command else None
    except psutil.NoSuchProcess:return None


def checked_mapping(values):
    for path,wanted in values.items():
        c.bound();require(c.sha(path)==wanted,'Frozen source/input changed: '+path)


def publish_atomic(path,value):
    """Windows same-directory rename publishes only a complete create-only JSON."""
    path=Path(path);require(not path.exists(),'No overwritten handoff receipt: '+str(path))
    pending=path.with_name(path.name+'.pending_'+str(os.getpid()))
    c.commit(pending,value)
    # os.rename on the required Windows host fails if the destination exists.
    os.rename(pending,path)


def wait_receipt(path,stop):
    while not path.is_file() and time.time()<stop:
        c.bound();time.sleep(.05)
    require(path.is_file(),'Durable handoff receipt required: '+str(path))
    return c.read(path)


def validate_supervisor_ready(ready,record):
    require(ready['passed'] and ready['launch_receipt_sha256']==c.sha(LAUNCHER/'launch.json')
        and ready['supervisor_launch']==record and ready['authorization_sha256']==c.sha(c.AUTH)
        and exact(record) is not None,'Exact supervisor acknowledgement before ownership transfer')


def validate_ownership_commit(handoff,launch_sha):
    require(handoff['passed'] and handoff['launch_receipt_sha256']==launch_sha
        and handoff['supervisor_ready_sha256']==c.sha(FOLDER/'handoff_ready.json')
        and handoff['authorization_sha256']==c.sha(c.AUTH),'Complete exact ownership transfer')


def old_retired():
    """A sealed retirement assertion and a fresh independent process inspection."""
    proof=c.sealed(RETIREMENT)
    require(proof['passed'] and proof['all_exact_launch_identities_retired'],
            'Initial exact identities must have a sealed retirement disposition')
    checked_mapping(proof.get('inputs',{}));checked_mapping(proof.get('artifacts',{}))
    paths=[c.RUN/'launcher_01/launch.json',OLD/'launch.json',
           OLD/'cost_screen_worker_launch.json',OLD/'baseline_worker_launch.json',
           OLD/'final_authentication_worker_launch.json',c.RUN/'run_01/launch.json']
    require(all(path.is_file() for path in paths[:5]),'Complete original controller identity inventory')
    for path in paths:
        if not path.is_file():continue
        row=c.read(path)
        require(row.get('authorization_sha256',c.sha(c.AUTH))==c.sha(c.AUTH),'Initial launch authority')
        require(exact(row) is None,'An initial exact launch identity is still running: '+str(path))
    exitrow=c.read(OLD/'exit.json')
    require(exitrow['authorization_sha256']==c.sha(c.AUTH) and exitrow['dependent_dispatch_stopped'],
            'Initial supervisor is closed, with dispatch stopped')
    return proof


def recovery_allowed():
    prior=c.sealed(PRIOR_FINAL)
    require(prior['passed'] and prior['final_accounting_authenticated']
        and prior['authorization_sha256']==c.sha(c.AUTH)
        and prior['all_accepted_full_checkpoint_history_ancestry_reconstructed']
        and prior['new_audited_physical_steps']==1304148 and prior['diagnostic_audited_steps']==512
        and prior['new_known_saved_steps_including_diagnostics']==1304660
        and prior['known_unaccepted_saved_steps']==0 and not prior['unresolved'],
        'Initial accepted chain and zero pre-dispatch work must be independently sealed')
    row=c.sealed(DISPATCH);checked_mapping(row['inputs'])
    require(row['passed'] is True and row['baseline_allowed'] is True
        and row['candidate_production_authorized'] is False
        and row['authorization_sha256']==c.sha(c.AUTH),'Separately sealed original-only recovery dispatch')
    old_retired()
    return row


def verify():
    a=c.bound();c.environment();d=c.read(DESIGN)
    checked_mapping(a['sources']);checked_mapping(a['inputs'])
    checked_mapping(d['sources']);checked_mapping(d['inputs'])
    require(d['authorization_sha256']==c.sha(c.AUTH) and d['start_utc']==c.START
        and d['end_utc']==c.END and d['simulation_cutoff_utc']==c.CUTOFF
        and d['workers']==a['workers']==1 and d['threads']==a['threads']==1
        and d['logical_cpu']==a['logical_cpu']==14 and not d['candidate_production_authorized']
        and d['cost_rerun_authorized'] is False,'Unchanged frozen recovery clocks and resources')
    b=a['independent_baseline']
    require(d['maximum_shared_saved_steps_including_diagnostics']==a['maximum_saved_steps_including_diagnostics']==10000000
        and d['maximum_nonadvancing_outer_calls']==a['maximum_nonadvancing_outer_calls']==640
        and d['maximum_cumulative_physical_steps_per_case']==b['maximum_cumulative_physical_steps_per_case']==5000000
        and d['maximum_cumulative_calls_per_case']==b['maximum_cumulative_calls_per_case']==1500
        and d['maximum_steps_per_segment']==b['maximum_steps_per_segment']==10000
        and d['prior_shared_saved_steps']==1304660,'Shared and cumulative caps cannot increase')
    require(Path(sys.executable).resolve()==PYTHON.resolve(),'Qualified Python3.12 runtime only')
    recovery_allowed()
    return a,d


def prepare():
    a=c.bound();c.environment();checked_mapping(a['sources']);checked_mapping(a['inputs'])
    recovery_allowed()
    preparation=c.sealed(c.OUT/'transport_preparation_03/results.json')
    require(preparation['passed'] and preparation['numerical_calls']==0
        and preparation['new_trajectory_steps']==0
        and preparation['authorization_sha256']==c.sha(c.AUTH)
        and preparation['transport_design_sha256']==c.sha(c.DESIGNS/'transport_design_03.json'),
        'Separately frozen zero-call original-baseline preparation')
    checked_mapping(preparation['artifacts'])
    paths=[HERE/x for x in ('campaign_common_v1.py','launch_recovery_v2.py',
        'monitor_recovery_v2.py','continue_baseline_v3.py','finalize_recovery_v2.py')]
    inputs=[c.AUTH,c.DESIGNS/'transport_design_03.json',c.DESIGNS/'supervisor_design_01.json',
        OLD/'exit.json',c.RUN/'run_01/failure.json']
    for leaf in ('transport_preparation_03','recovery_seed_01','dispatch_decision_02',
                 'initial_retirement_01','failure_diagnosis_01','final_disposition_01'):
        inputs.extend([c.OUT/leaf/'results.json',c.OUT/leaf/'completion.json'])
    c.commit(DESIGN,dict(stage='Stage229 separately versioned same-window recovery controller',
        authorization_sha256=c.sha(c.AUTH),start_utc=a['start_utc'],end_utc=a['end_utc'],
        simulation_cutoff_utc=a['simulation_cutoff_utc'],workers=1,threads=1,logical_cpu=14,
        candidate_production_authorized=False,cost_rerun_authorized=False,
        prior_shared_saved_steps=1304660,maximum_shared_saved_steps_including_diagnostics=10000000,
        maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,
        maximum_steps_per_segment=10000,maximum_nonadvancing_outer_calls=640,
        sources={str(p):c.sha(p) for p in paths},inputs={str(p):c.sha(p) for p in inputs},
        phases=['conditional_original_baseline_recovery','read_only_final_authentication'],
        predecessor_policy='Sealed original accounting and retirement, repeated exact birth/command inspection; never overlap old and new owned workers.',
        identity_policy='Exact birth and command before every terminate/kill; access denial never counts as retirement.',
        cleanup_policy='Preserve last sealed checkpoint/raw chain and every incomplete or failed attempt; final authentication stops at hard end minus10seconds.'))
    print('STAGE229_RECOVERY_SUPERVISOR_PREPARED',c.sha(DESIGN),flush=True)


def retire_owned(record,child):
    forced=False
    if child.poll() is None:
        p=exact(record);require(p is not None,'Cannot authenticate owned process before terminate')
        p.terminate();forced=True
        try:child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p=exact(record);require(p is not None,'Cannot authenticate owned process before fallback kill')
            p.kill();child.wait(timeout=2)
    require(child.poll() is not None and exact(record) is None,'Owned phase must retire before successor')
    return forced


def owned_record(child,command):
    p=psutil.Process(child.pid);birth=p.create_time();actual=p.cmdline()
    require(actual==command and p.ppid()==os.getpid(),'Owned exact launch command/parent differs')
    return dict(pid=child.pid,created=birth,command=actual,utc=c.utc(),
        authorization_sha256=c.sha(c.AUTH),supervisor_design_sha256=c.sha(DESIGN))


def child_phase(name,script,stop):
    verify();require(time.time()<stop-5,'Owned phase startup/retirement reserve')
    command=[str(PYTHON),'-B','-u',str(HERE/script)]+([] if name=='final_authentication' else ['run'])
    child=None;record=None
    try:
        with (FOLDER/(name+'_stdout.log')).open('xb') as stdout,(FOLDER/(name+'_stderr.log')).open('xb') as stderr:
            child=subprocess.Popen(command,cwd=str(c.ROOT),env=dict(os.environ),stdout=stdout,
                stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        record=owned_record(child,command)
        record['stop_utc']=datetime.fromtimestamp(stop).astimezone().isoformat()
        c.commit(FOLDER/(name+'_worker_launch.json'),record)
        while child.poll() is None and time.time()<stop:
            time.sleep(min(5,max(.01,stop-time.time())))
        forced=child.poll() is None
        if forced:c.commit(FOLDER/(name+'_deadline_stop.json'),dict(utc=c.utc(),launch=record,
            reason='Strict phase cutoff; preserve all sealed and unresolved work.'))
        forced=retire_owned(record,child) or forced
        row=dict(exit_code=child.poll(),forced_deadline_stop=forced,utc=c.utc(),launch=record,
            exact_owned_identity_retired=True)
        c.commit(FOLDER/(name+'_exit.json'),row);return row
    except BaseException as error:
        if child is not None and child.poll() is None:
            if record is None:record=owned_record(child,command)
            retire_owned(record,child)
            c.commit(FOLDER/(name+'_failure_cleanup.json'),dict(utc=c.utc(),launch=record,
                original_error=repr(error),exact_owned_identity_retired=True,dependent_dispatch_stopped=True))
        raise


def supervise():
    a,d=verify();FOLDER.mkdir(parents=True,exist_ok=False)
    me=psutil.Process();me.cpu_affinity([a['logical_cpu']])
    c.commit(FOLDER/'launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),
        utc=c.utc(),supervisor_design_sha256=c.sha(DESIGN),authorization_sha256=c.sha(c.AUTH),end_utc=c.END))
    # The launcher owns this process until a complete final handoff commit. It
    # may safely retire it before then because no descendant can yet be started.
    handoff_stop=min(time.time()+5,datetime.fromisoformat(c.CUTOFF).timestamp()-180)
    launch=wait_receipt(LAUNCHER/'launch.json',handoff_stop)
    owner=exact(launch);require(owner is not None and owner.pid==me.pid,'Exact launcher handoff identity')
    launch_sha=c.sha(LAUNCHER/'launch.json')
    publish_atomic(FOLDER/'handoff_ready.json',dict(passed=True,utc=c.utc(),
        launch_receipt_sha256=launch_sha,supervisor_launch=launch,authorization_sha256=c.sha(c.AUTH)))
    handoff=wait_receipt(LAUNCHER/'handoff_committed.json',handoff_stop)
    validate_ownership_commit(handoff,launch_sha)
    awake=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    c.commit(FOLDER/'awake_request.json',dict(succeeded=bool(awake),
        scope='Task lifetime only; prevent automatic system sleep, allow display sleep, restore on exit.'))
    phases=[];reason='unknown'
    try:
        cutoff=datetime.fromisoformat(c.CUTOFF).timestamp();end=datetime.fromisoformat(c.END).timestamp()
        if time.time()<cutoff-180:
            phases.append(child_phase('baseline','continue_baseline_v3.py',cutoff));reason='recovery_baseline_retired'
        else:reason='simulation_cutoff_no_recovery_dispatch_reserve'
        c.commit(FOLDER/'phase_disposition.json',dict(reason=reason,phases=phases,utc=c.utc(),
            candidate_production_authorized=False,cost_rerun=False))
        if time.time()<end-70:
            phases.append(child_phase('final_authentication','finalize_recovery_v2.py',end-10))
        else:reason='deadline_no_final_authentication_reserve'
        c.commit(FOLDER/'exit.json',dict(utc=c.utc(),reason=reason,phases=phases,
            authorization_sha256=c.sha(c.AUTH),supervisor_design_sha256=c.sha(DESIGN),
            dependent_dispatch_stopped=True,
            final_authentication_completed=(c.OUT/'final_disposition_02/completion.json').is_file()))
    except Exception as error:
        import traceback
        c.commit(FOLDER/'failure.json',dict(utc=c.utc(),error=repr(error),traceback=traceback.format_exc(),
            phases=phases,dependent_dispatch_stopped=True));raise
    finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def launch():
    a,d=verify()
    require(not FOLDER.exists() and not LAUNCHER.exists() and not WORK.exists(),'No duplicate recovery launch')
    require(time.time()<datetime.fromisoformat(c.CUTOFF).timestamp()-180,'Recovery simulation dispatch reserve')
    LAUNCHER.mkdir(parents=True,exist_ok=False)
    command=[str(PYTHON),'-B','-u',str(Path(__file__).resolve()),'supervise']
    child=None;record=None
    try:
        with (LAUNCHER/'stdout.log').open('xb') as stdout,(LAUNCHER/'stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=str(c.ROOT),env=dict(os.environ),stdout=stdout,
                stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        record=owned_record(child,command);record['end_utc']=c.END
        publish_atomic(LAUNCHER/'launch.json',record)
        handoff_stop=min(time.time()+5,datetime.fromisoformat(c.CUTOFF).timestamp()-180)
        ready=wait_receipt(FOLDER/'handoff_ready.json',handoff_stop)
        validate_supervisor_ready(ready,record)
        publish_atomic(LAUNCHER/'handoff_committed.json',dict(passed=True,utc=c.utc(),
            launch_receipt_sha256=c.sha(LAUNCHER/'launch.json'),
            supervisor_ready_sha256=c.sha(FOLDER/'handoff_ready.json'),authorization_sha256=c.sha(c.AUTH)))
    except BaseException as error:
        transferred=(LAUNCHER/'handoff_committed.json').is_file()
        if transferred:
            # The supervisor now owns descendants. Killing it here could leave
            # a worker orphaned; its frozen controller remains responsible.
            c.commit(LAUNCHER/'post_handoff_failure.json',dict(utc=c.utc(),launch=record,
                original_error=repr(error),ownership_transferred=True,supervisor_cleanup_owner=True))
        elif child is not None and child.poll() is None:
            if record is None:record=owned_record(child,command)
            retire_owned(record,child)
            c.commit(LAUNCHER/'failure_cleanup.json',dict(utc=c.utc(),launch=record,
                original_error=repr(error),exact_owned_identity_retired=True))
        raise
    print('STAGE229_RECOVERY_LAUNCHED',child.pid,c.END,flush=True)


if __name__=='__main__':{'prepare':prepare,'launch':launch,'supervise':supervise}[sys.argv[1]]()
