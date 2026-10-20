"""Foreground controller for one new bounded worker; exact-identity cutoff only."""
from pathlib import Path
from datetime import datetime
import os, subprocess, sys, time, traceback
import psutil
import tail_common_v1 as c
import complete_fibre_v1 as worker

PYTHON = Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')

def inspect(pid, birth, command):
    try:
        process=psutil.Process(pid)
        actual_birth=process.create_time()
        if actual_birth != birth:
            return dict(retired=True,birth_mismatch=True,pid=pid,expected_birth=birth,actual_birth=actual_birth)
        actual_command=process.cmdline()
        if not actual_command or actual_command != command:
            raise RuntimeError('Matching birth without exact accessible launch command')
        return dict(retired=False,pid=pid,birth=birth,command=actual_command)
    except psutil.NoSuchProcess:
        return dict(retired=True,pid=pid,no_such_process=True)

def stop_owned(child, birth, command, controller):
    proof=inspect(child.pid,birth,command)
    if not proof['retired']:
        c.commit(controller/f'stop_identity_{time.time_ns()}.json',proof)
        child.terminate()
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proof=inspect(child.pid,birth,command)
            if not proof['retired']:
                c.commit(controller/f'kill_identity_{time.time_ns()}.json',proof)
                child.kill()
            child.wait(timeout=10)
    return inspect(child.pid,birth,command)

def launch():
    plan=worker.verify();c.bound()
    controller=c.RUN.with_name(c.RUN.name+'_controller')
    controller.mkdir(parents=True,exist_ok=False)
    c.commit(controller/'launch.json',dict(pid=os.getpid(),created=psutil.Process().create_time(),
        argv=psutil.Process().cmdline(),utc=c.utc(),design_sha256=c.sha(c.PLAN),authorization_sha256=c.sha(c.AUTH)))
    command=[str(PYTHON),'-B','-u',str(Path(worker.__file__).resolve()),'run']
    cutoff=datetime.fromisoformat(plan['simulation_cutoff_utc']).timestamp()
    env=os.environ.copy()
    for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):env[name]='1'
    child=None;birth=None;forced=False
    try:
        with (controller/'worker_stdout.log').open('xb') as stdout,(controller/'worker_stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=c.ROOT,env=env,stdout=stdout,stderr=stderr,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            birth=psutil.Process(child.pid).create_time()
            actual=psutil.Process(child.pid).cmdline()
            worker.api.require(actual==command, 'Exact new child launch command')
            c.commit(controller/'worker_launch.json',dict(pid=child.pid,created=birth,argv=command,utc=c.utc()))
            while child.poll() is None:
                if time.time() >= cutoff:
                    proof=stop_owned(child,birth,command,controller)
                    forced=True
                    break
                time.sleep(1)
            code=child.wait(timeout=30)
        identity=inspect(child.pid,birth,command)
        worker.api.require(identity['retired'], 'Exact task worker retired')
        exit_record=dict(returncode=code,forced_cutoff_stop=forced,retired_exact_identity=True,
            launch_sha256=c.sha(controller/'worker_launch.json'),identity=identity,utc=c.utc())
        c.commit(controller/'worker_exit.json',exit_record)
        if code==0 and not forced:
            worker.final_authentication(exit_record)
        else:
            worker.failed_authentication(exit_record)
        c.commit(controller/'completion.json',dict(passed=code==0 and not forced,returncode=code,
            closed_logs={str(p):c.sha(p) for p in controller.glob('*.log')},utc=c.utc()))
    except Exception as error:
        retired=None
        if child is not None and birth is not None:
            retired=stop_owned(child,birth,command,controller)
        c.commit(controller/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),utc=c.utc(),
            child_pid=None if child is None else child.pid,exact_child_retirement=retired,raw_work_preserved=True))
        raise

if __name__=='__main__':launch()
