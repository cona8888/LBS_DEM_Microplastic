"""Strict bounded one-worker supervisor. Candidate is never installed in transport."""
from pathlib import Path
from datetime import datetime
import ctypes, os, subprocess, sys, time
import psutil
import campaign_common_v1 as c

HERE=Path(__file__).resolve().parent
DESIGN=c.DESIGNS/'supervisor_design_01.json'
FOLDER=c.RUN/'supervisor_01'
PYTHON=Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')

def exact(record):
    try:
        p=psutil.Process(record['pid'])
        return p if p.create_time()==record['created'] and p.cmdline()==record['command'] else None
    except (psutil.NoSuchProcess,psutil.AccessDenied):return None

def verify():
    a=c.bound();c.environment();d=c.read(DESIGN)
    c.verify(a['sources']);c.verify(a['inputs']);c.verify(d['sources']);c.verify(d['inputs'])
    if d['authorization_sha256']!=c.sha(c.AUTH) or d['end_utc']!=c.END or d['simulation_cutoff_utc']!=c.CUTOFF or d['workers']!=1:raise RuntimeError('Frozen supervisor authority')
    if Path(sys.executable).resolve()!=PYTHON.resolve():raise RuntimeError('Qualified Python3.12 runtime only')
    return a,d

def prepare():
    a=c.bound();c.environment()
    paths=[HERE/x for x in ('campaign_common_v1.py','launch_overnight_v1.py','finalize_overnight_v1.py','monitor_overnight_v1.py','screen_cost_v1.py','replay_cost_v1.py','failure_reuse_v1.py','audit_failure_reuse_v1.py','continue_baseline_v2.py')]
    inputs=[c.AUTH,c.DESIGNS/'cost_screen_01.json',c.DESIGNS/'transport_design_02.json',c.OUT/'transport_preparation_02/results.json',c.OUT/'transport_preparation_02/completion.json',c.OUT/'tiny_replay_01/results.json',c.OUT/'tiny_replay_01/completion.json']
    for folder in ('tiny_replay_01','transport_preparation_02'):
        if not c.sealed(c.OUT/folder/'results.json')['passed']:raise RuntimeError('Missing launch qualification')
    c.commit(DESIGN,dict(stage='Stage229 strict hidden sequential supervisor',authorization_sha256=c.sha(c.AUTH),start_utc=a['start_utc'],end_utc=a['end_utc'],simulation_cutoff_utc=a['simulation_cutoff_utc'],workers=1,threads=1,candidate_production_authorized=False,sources={str(p):c.sha(p) for p in paths},inputs={str(p):c.sha(p) for p in inputs},phases=['fixed_pose_full_cost','conditional_original_baseline','read_only_final_authentication'],identity_policy='Verify birth AND exact command before every terminate or kill; never touch unrelated processes.'))
    print('STAGE229_SUPERVISOR_PREPARED',c.sha(DESIGN),flush=True)

def retire_owned(record,child):
    """Bounded cleanup; authenticate both birth and command before each action."""
    forced=False
    if child.poll() is None:
        p=exact(record)
        if p is None:raise RuntimeError('Cannot authenticate owned process before terminate')
        p.terminate();forced=True
        try:child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p=exact(record)
            if p is None:raise RuntimeError('Cannot authenticate owned process before fallback kill')
            p.kill();child.wait(timeout=2)
    if child.poll() is None or exact(record) is not None:
        raise RuntimeError('Owned phase must retire before any successor worker')
    return forced

def child_phase(name,script,stop):
    verify()
    if time.time()>=stop-5:raise RuntimeError('No owned phase startup/retirement reserve')
    command=[str(PYTHON),'-B','-u',str(HERE/script)]+([] if name=='final_authentication' else ['run'])
    child=None;record=None
    try:
        with (FOLDER/(name+'_stdout.log')).open('xb') as stdout,(FOLDER/(name+'_stderr.log')).open('xb') as stderr:
            child=subprocess.Popen(command,cwd=str(c.ROOT),env=dict(os.environ),stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        p=psutil.Process(child.pid)
        # Capture the exact owned identity before any receipt can fail to write.
        birth=p.create_time();actual=p.cmdline()
        if actual!=command or p.ppid()!=os.getpid():raise RuntimeError('Owned launch command/parent differs')
        record=dict(pid=child.pid,created=birth,command=actual,utc=c.utc(),authorization_sha256=c.sha(c.AUTH),supervisor_design_sha256=c.sha(DESIGN),stop_utc=datetime.fromtimestamp(stop).astimezone().isoformat())
        c.commit(FOLDER/(name+'_worker_launch.json'),record)
        while child.poll() is None and time.time()<stop:
            time.sleep(min(5,max(.01,stop-time.time())))
        forced=child.poll() is None
        if forced:
            c.commit(FOLDER/(name+'_deadline_stop.json'),dict(utc=c.utc(),pid=child.pid,created=record['created'],command=record['command'],reason='Strict phase cutoff; preserve all sealed and unresolved raw work.'))
        forced=retire_owned(record,child) or forced
        result=dict(exit_code=child.poll(),forced_deadline_stop=forced,utc=c.utc(),launch=record,exact_owned_identity_retired=True)
        c.commit(FOLDER/(name+'_exit.json'),result)
        return result
    except BaseException as error:
        if child is not None and child.poll() is None:
            if record is None:
                # The subprocess handle confirms its original process is still
                # alive; never treat a reused/unrelated PID as owned.
                p=psutil.Process(child.pid)
                birth=p.create_time();actual=p.cmdline()
                if actual!=command or p.ppid()!=os.getpid():
                    raise RuntimeError('Unqualified live phase identity; no unrelated process action') from error
                record=dict(pid=child.pid,created=birth,command=actual)
            retire_owned(record,child)
            c.commit(FOLDER/(name+'_failure_cleanup.json'),dict(utc=c.utc(),launch=record,
                original_error=repr(error),exact_owned_identity_retired=True,dependent_dispatch_stopped=True))
        raise

def cost_dispatch():
    result=c.OUT/'cost_screen_01/results.json'
    if not (result.parent/'completion.json').is_file():return False
    row=c.sealed(result);c.verify(row['artifacts'])
    tiny=c.sealed(c.OUT/'tiny_replay_01/results.json');c.verify(tiny['artifacts'])
    if not (row['passed'] and row['outer_calls_attempted']==588 and row['qualification_fixtures']==98 and row['exact_paired_all_scientific_outputs'] and row['unchanged_independent_physics_association_audits'] and tiny['actual_hit_mutation_controls']['controls_rejected']==32 and tiny['live_metadata_controls']['controls_checked']>=22):raise RuntimeError('Cost scientific/evidence qualification failed')
    paths=[c.AUTH,c.DESIGNS/'cost_screen_01.json',result,result.parent/'completion.json',c.OUT/'tiny_replay_01/results.json',c.OUT/'tiny_replay_01/completion.json']
    c.commit(c.OUT/'dispatch_decision_01/results.json',dict(passed=True,baseline_allowed=True,candidate_production_authorized=False,authorization_sha256=c.sha(c.AUTH),cost_evidence_sha256=c.sha(result),physical_evidence_gates_passed=True,cost_performance_passed=row['both_outer_and_transaction_all_strata_material_gain_passed'],reason='Original baseline independently authorized after scientific/evidence/physical checks. Performance-only optimization negatives retained; prototype never installed.',inputs={str(p):c.sha(p) for p in paths},utc=c.utc()))
    c.commit(c.OUT/'dispatch_decision_01/completion.json',dict(passed=True,results_sha256=c.sha(c.OUT/'dispatch_decision_01/results.json')))
    return True

def supervise():
    a,d=verify();FOLDER.mkdir(parents=True,exist_ok=False)
    me=psutil.Process();me.cpu_affinity([a['logical_cpu']])
    c.commit(FOLDER/'launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=c.utc(),supervisor_design_sha256=c.sha(DESIGN),authorization_sha256=c.sha(c.AUTH),end_utc=c.END))
    awake=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    c.commit(FOLDER/'awake_request.json',dict(succeeded=bool(awake),scope='Task lifetime only; prevent automatic system sleep, allow display sleep, restore on exit.'))
    phases=[];reason='unknown'
    try:
        cutoff=datetime.fromisoformat(c.CUTOFF).timestamp();end=datetime.fromisoformat(c.END).timestamp()
        phases.append(child_phase('cost_screen','screen_cost_v1.py',cutoff))
        if phases[-1]['exit_code']==0 and cost_dispatch() and time.time()<cutoff-180:
            phases.append(child_phase('baseline','continue_baseline_v2.py',cutoff));reason='baseline_retired'
        else:reason='cost_gate_or_window_stopped_dependent_dispatch'
        c.commit(FOLDER/'phase_disposition.json',dict(reason=reason,phases=phases,utc=c.utc(),candidate_production_authorized=False))
        # Ten seconds are reserved for authenticated termination, fallback kill,
        # exit receipts and supervisor retirement before the strict hard end.
        if time.time()<end-70:phases.append(child_phase('final_authentication','finalize_overnight_v1.py',end-10))
        else:reason='deadline_no_final_authentication_reserve'
        c.commit(FOLDER/'exit.json',dict(utc=c.utc(),reason=reason,phases=phases,authorization_sha256=c.sha(c.AUTH),supervisor_design_sha256=c.sha(DESIGN),dependent_dispatch_stopped=True,final_authentication_completed=(c.OUT/'final_disposition_01/completion.json').is_file()))
    except Exception as error:
        import traceback
        c.commit(FOLDER/'failure.json',dict(utc=c.utc(),error=repr(error),traceback=traceback.format_exc(),phases=phases,dependent_dispatch_stopped=True))
        raise
    finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

def launch():
    a,d=verify()
    if FOLDER.exists() or (c.RUN/'launcher_01').exists() or (c.RUN/'run_01').exists():raise RuntimeError('No duplicate Stage229 launch')
    folder=c.RUN/'launcher_01';folder.mkdir(parents=True,exist_ok=False)
    command=[str(PYTHON),'-B','-u',str(Path(__file__).resolve()),'supervise']
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        child=subprocess.Popen(command,cwd=str(c.ROOT),env=dict(os.environ),stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    p=psutil.Process(child.pid)
    if p.cmdline()!=command:raise RuntimeError('Exact launch command')
    c.commit(folder/'launch.json',dict(pid=p.pid,created=p.create_time(),command=p.cmdline(),utc=c.utc(),supervisor_design_sha256=c.sha(DESIGN),authorization_sha256=c.sha(c.AUTH),end_utc=c.END))
    print('STAGE229_OVERNIGHT_LAUNCHED',child.pid,c.END,flush=True)

if __name__=='__main__':{'prepare':prepare,'launch':launch,'supervise':supervise}[sys.argv[1]]()
