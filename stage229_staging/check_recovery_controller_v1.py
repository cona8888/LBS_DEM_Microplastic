"""Pure administrative identity/publication controls; no real process calls."""
from pathlib import Path
import copy, importlib.util, sys, time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('recovery_controller_controls',HERE/'launch_recovery_v2.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c=m.c
OUT=c.OUT/'supervisor_identity_controls_03'


def run():
    c.bound();controls=[];actions=[];artifacts={}
    original_process=m.psutil.Process;original_commit=c.commit
    original_folder=m.FOLDER;original_launcher=m.LAUNCHER
    record=dict(pid=24680,created=123456.125,command=['python.exe','-B','owned.py','run'])
    class Fake:
        def __init__(self,birth,command):self.birth=birth;self.command=command
        def create_time(self):return self.birth
        def cmdline(self):return self.command
        def terminate(self):actions.append('terminate');raise AssertionError('No process action')
        def kill(self):actions.append('kill');raise AssertionError('No process action')
    def note(name):controls.append(dict(name=name,passed=True,process_actions=0))
    def rejects(name,fn,error=RuntimeError):
        try:fn()
        except error:note(name)
        else:raise AssertionError('Negative control accepted: '+name)
        assert not actions
    def identity(name,receipt,birth=None,command=None,error=None,expected=None,throws=None):
        before=copy.deepcopy(receipt)
        def process(pid):
            if error is not None:raise error(pid)
            return Fake(receipt['created'] if birth is None else birth,
                receipt.get('command',receipt.get('argv')) if command is None else command)
        m.psutil.Process=process
        if throws is not None:rejects(name,lambda:m.exact(receipt),throws)
        else:
            assert (m.exact(receipt) is not None)==expected;note(name)
        assert receipt==before and not actions
    try:
        oldpath=c.RUN/'run_01/launch.json';actual=c.read(oldpath)
        identity('command_exact_match',record,expected=True)
        identity('actual_initial_worker_argv_exact_match',actual,expected=True)
        identity('consistent_dual_fields',{**record,'argv':record['command']},expected=True)
        identity('sub_millisecond_birth_difference',record,birth=record['created']+0.0000001,expected=False)
        identity('exact_full_command_difference',record,command=record['command']+['other'],expected=False)
        identity('both_identity_fields_differ',record,birth=record['created']+1,command=['unrelated'],expected=False)
        identity('conflicting_command_argv',{**record,'argv':['unrelated']},throws=RuntimeError)
        identity('missing_command',{k:v for k,v in record.items() if k!='command'},throws=RuntimeError)
        identity('missing_birth',{k:v for k,v in record.items() if k!='created'},throws=RuntimeError)
        identity('recorded_pid_absent',record,error=m.psutil.NoSuchProcess,expected=False)
        identity('access_denial_never_proves_retirement',record,error=m.psutil.AccessDenied,throws=m.psutil.AccessDenied)

        # Observe publication while its pending file is being written. Only the
        # completed same-directory rename makes the final name readable.
        atomic=OUT/'fixtures/atomic_complete.json';observed=[]
        def observe_pending(path,value):
            assert not atomic.exists();observed.append('final_absent_before_pending_write')
            original_commit(path,value)
            assert not atomic.exists();observed.append('final_absent_after_pending_write')
        c.commit=observe_pending;m.publish_atomic(atomic,dict(passed=True,fixture=True));c.commit=original_commit
        assert c.read(atomic)==dict(passed=True,fixture=True) and len(observed)==2
        note('complete_json_visible_only_after_atomic_publication');artifacts[str(atomic)]=c.sha(atomic)
        before=atomic.read_bytes()
        rejects('existing_handoff_receipt_never_overwritten',lambda:m.publish_atomic(atomic,dict(overwrite=True)))
        assert atomic.read_bytes()==before
        incomplete=OUT/'fixtures/atomic_failed.json'
        def partial_failure(path,value):
            path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('x',encoding='utf-8') as stream:stream.write('{')
            raise OSError('Pure fixture simulated pending-write failure')
        c.commit=partial_failure
        rejects('failed_pending_write_never_publishes_partial_handoff',lambda:m.publish_atomic(incomplete,dict(passed=True)),OSError)
        c.commit=original_commit
        assert not incomplete.exists()
        pending=incomplete.with_name(incomplete.name+'.pending_'+str(m.os.getpid()))
        assert pending.read_text(encoding='utf-8')=='{';artifacts[str(pending)]=c.sha(pending)
        rejects('missing_handoff_deadline_refuses_without_wait',
            lambda:m.wait_receipt(OUT/'fixtures/missing.json',time.time()-1))

        m.FOLDER=OUT/'fixtures/supervisor';m.LAUNCHER=OUT/'fixtures/launcher'
        c.commit(m.LAUNCHER/'launch.json',record)
        ready=dict(passed=True,launch_receipt_sha256=c.sha(m.LAUNCHER/'launch.json'),
            supervisor_launch=record,authorization_sha256=c.sha(c.AUTH))
        c.commit(m.FOLDER/'handoff_ready.json',ready)
        m.psutil.Process=lambda pid:Fake(record['created'],record['command'])
        m.validate_supervisor_ready(ready,record);note('exact_supervisor_ready_acknowledgement')
        for key,value in (('passed',False),('launch_receipt_sha256','0'*64),
                          ('supervisor_launch',{**record,'created':record['created']+1}),
                          ('authorization_sha256','0'*64)):
            rejected=copy.deepcopy(ready);rejected[key]=value
            rejects('supervisor_ready_rejects_'+key,lambda rejected=rejected:m.validate_supervisor_ready(rejected,record))
        m.psutil.Process=lambda pid:Fake(record['created']+1,record['command'])
        rejects('ready_ack_refuses_retired_or_reused_supervisor_identity',lambda:m.validate_supervisor_ready(ready,record))
        handoff=dict(passed=True,launch_receipt_sha256=ready['launch_receipt_sha256'],
            supervisor_ready_sha256=c.sha(m.FOLDER/'handoff_ready.json'),authorization_sha256=c.sha(c.AUTH))
        m.validate_ownership_commit(handoff,ready['launch_receipt_sha256']);note('complete_exact_ownership_commit')
        for key,value in (('passed',False),('launch_receipt_sha256','0'*64),
                          ('supervisor_ready_sha256','0'*64),('authorization_sha256','0'*64)):
            rejected=copy.deepcopy(handoff);rejected[key]=value
            rejects('ownership_commit_rejects_'+key,
                lambda rejected=rejected:m.validate_ownership_commit(rejected,ready['launch_receipt_sha256']))
        for path in (m.LAUNCHER/'launch.json',m.FOLDER/'handoff_ready.json'):artifacts[str(path)]=c.sha(path)
    finally:
        m.psutil.Process=original_process;c.commit=original_commit
        m.FOLDER=original_folder;m.LAUNCHER=original_launcher
    assert not actions and m.psutil.Process is original_process and c.commit is original_commit
    result=dict(passed=True,utc=c.utc(),authorization_sha256=c.sha(c.AUTH),controls=controls,
        controls_checked=len(controls),numerical_calls=0,new_trajectory_steps=0,process_actions=0,
        live_processes_inspected=0,patched_helpers_restored=True,artifacts=artifacts,
        inputs={str(HERE/'launch_recovery_v2.py'):c.sha(HERE/'launch_recovery_v2.py'),
                str(Path(__file__).resolve()):c.sha(__file__),str(oldpath):c.sha(oldpath),
                str(Path(c.__file__).resolve()):c.sha(c.__file__)},
        mechanism='Pure exact-identity and actual handoff-gate helper controls; mocked Process only. Atomic file controls use a separate fixture directory. No worker, supervisor, child process, transport or force call is launched.')
    c.bound();c.commit(OUT/'results.json',result)
    c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    print('RECOVERY_CONTROLLER_PURE_CONTROLS_PASSED',len(controls),c.sha(OUT/'results.json'),flush=True)


if __name__=='__main__':run()
