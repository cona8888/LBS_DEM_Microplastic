"""Pure guard negatives for the fresh administrative adapter; zero solver calls."""
from types import FunctionType, SimpleNamespace
from datetime import datetime, timezone, timedelta
import copy
import psutil
import tail_common_v1 as c
import complete_fibre_v1 as worker
import launch_tail_v1 as launch

def run():
    controls=[]
    def expect(name,fn,raises=False):
        rejected=False
        try:fn()
        except (RuntimeError,psutil.AccessDenied):rejected=True
        if rejected!=raises:raise AssertionError(name)
        controls.append(dict(name=name,passed=True,rejected=rejected))
    class FakeProcess:
        def __init__(self,birth,command,denied_birth=False,denied_command=False):
            self.birth=birth;self.command=command;self.denied_birth=denied_birth;self.denied_command=denied_command
        def create_time(self):
            if self.denied_birth:raise psutil.AccessDenied(99)
            return self.birth
        def cmdline(self):
            if self.denied_command:raise psutil.AccessDenied(99)
            return self.command
    for name,p,raises,retired in [
        ('exact_live',FakeProcess(10,['python','run']),False,False),
        ('different_birth_inaccessible_command',FakeProcess(11,None,denied_command=True),False,True),
        ('matching_birth_empty_command',FakeProcess(10,[]),True,None),
        ('matching_birth_different_command',FakeProcess(10,['unrelated']),True,None),
        ('matching_birth_inaccessible_command',FakeProcess(10,None,denied_command=True),True,None),
        ('inaccessible_birth',FakeProcess(10,['python','run'],denied_birth=True),True,None)]:
        env=dict(launch.inspect.__globals__,psutil=SimpleNamespace(Process=lambda pid:p,NoSuchProcess=psutil.NoSuchProcess))
        fn=FunctionType(launch.inspect.__code__,env)
        def check(fn=fn,retired=retired):
            row=fn(99,10,['python','run'])
            if retired is not None:assert row['retired']==retired
        expect(name,check,raises)
    def absent(pid):raise psutil.NoSuchProcess(pid)
    env=dict(launch.inspect.__globals__,psutil=SimpleNamespace(Process=absent,NoSuchProcess=psutil.NoSuchProcess))
    fn=FunctionType(launch.inspect.__code__,env)
    expect('absent_exact_identity',lambda:worker.api.require(fn(99,10,['python','run'])['retired'],'Absent identity'))
    for name,values,expected_failure,expected_reads in [
        ('first_exact_read',['good'],False,1),
        ('transient_same_path_retry',[OSError('offline'),'good'],False,2),
        ('two_transient_reads',[OSError('a'),OSError('b'),'good'],False,3),
        ('changed_bytes_no_retry',['bad','good'],True,1),
        ('three_read_errors',[OSError('a'),OSError('b'),OSError('c')],True,3)]:
        reads=[];bounds=[];events=[]
        def read_hash(path):
            assert path=='same_path';reads.append(path);value=values[len(reads)-1]
            if isinstance(value,OSError):raise value
            return value
        caught=False
        try:worker.PRIVATE['verify_frozen_file']('same_path','good',read_hash,lambda:bounds.append(True),lambda delay:None,events.append)
        except (OSError,RuntimeError):caught=True
        assert caught==expected_failure and len(reads)==expected_reads and len(bounds)>=expected_reads
        controls.append(dict(name=name,passed=True,reads=len(reads),fresh_bounds=len(bounds)))
    now=datetime.now(timezone.utc)
    plan=dict(simulation_cutoff_utc=(now+timedelta(minutes=5)).isoformat(),maximum_saved_steps_including_diagnostics=50000,
              minimum_free_disk_bytes=20*1024**3)
    env=dict(worker.dispatch_stop.__globals__,c=SimpleNamespace(bound=lambda:True),
             job=SimpleNamespace(utc=lambda:now,policy=SimpleNamespace(utc=datetime.fromisoformat),
                                 codec=SimpleNamespace(base=SimpleNamespace(MAX_COMPRESSED=1))),
             shutil=SimpleNamespace(disk_usage=lambda p:SimpleNamespace(free=100*1024**3)))
    stop=FunctionType(worker.dispatch_stop.__code__,env)
    for name,used,needed,want in [('within_cap',0,512,None),('at_saved_cap',50000,1,'saved_step_ceiling'),
                                  ('diagnostic_reservation_exceeds_cap',49900,512,'saved_step_ceiling')]:
        assert stop(plan,used,needed)==want;controls.append(dict(name=name,passed=True))
    earlier=dict(plan,simulation_cutoff_utc=(now+timedelta(seconds=119)).isoformat())
    assert stop(earlier,0,512)=='simulation_cutoff';controls.append(dict(name='fresh_dispatch_reserve',passed=True))
    env['shutil']=SimpleNamespace(disk_usage=lambda p:SimpleNamespace(free=20*1024**3))
    assert FunctionType(worker.dispatch_stop.__code__,env)(plan,0,512)=='disk_reserve'
    controls.append(dict(name='disk_reserve',passed=True))
    clones=worker.clone_checks()
    folder=c.OUT/'preflight_02'
    c.commit(folder/'results.json',dict(passed=True,controls=controls,clone_checks=clones,
        numerical_calls=0,new_trajectory_steps=0,live_process_inspections=0,process_actions=0,
        preparation_only_seed_manifest_correction=True,
        previous_pure_preflight_preserved=True,
        previous_preflight_sha256=c.sha(c.OUT/'preflight_01/results.json'),
        previous_source_snapshots={str(p):c.sha(p) for p in (c.OUT/'preflight_01/source_snapshot').glob('*.py')},
        sources={str(p):c.sha(p) for p in c.ROOT.joinpath('stage230_staging').glob('*.py')}))
    c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
    print('STAGE230_PURE_CONTROLS',len(controls),flush=True)

if __name__=='__main__':run()
