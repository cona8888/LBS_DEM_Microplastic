"""Launch hidden supervisor; bounded worker lifetime and task-scoped sleep request."""
from pathlib import Path
import ctypes, json, os, subprocess, sys, time
import psutil
import overnight_campaign_v1 as n


def supervise():
    d=n.api.read(n.PLAN);n.verify(d)
    folder=n.RUN.parent/'supervisor_01';folder.mkdir(parents=True,exist_ok=False)
    me=psutil.Process()
    n.job.commit(folder/'launch.json',dict(pid=me.pid,created=me.create_time(),argv=me.cmdline(),utc=n.job.utc().isoformat(),design_sha256=n.api.sha(n.PLAN)))
    awake=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    n.job.commit(folder/'awake_request.json',dict(succeeded=bool(awake),scope='Task lifetime only; prevent automatic system sleep, allow display sleep; restored when supervisor exits.'))
    command=[sys.executable,'-B','-u',str(Path(n.__file__).resolve()),'run']
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        child=subprocess.Popen(command,cwd=str(n.ROOT),env=dict(os.environ),stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    p=psutil.Process(child.pid);birth=p.create_time()
    n.job.commit(folder/'worker_launch.json',dict(pid=child.pid,created=birth,argv=command,utc=n.job.utc().isoformat(),design_sha256=n.api.sha(n.PLAN)))
    cutoff=n.job.policy.utc(d['authorized_end_utc']).timestamp()
    forced=False
    try:
        while child.poll() is None and time.time()<cutoff:
            time.sleep(min(10,max(.05,cutoff-time.time())))
        if child.poll() is None:
            p=psutil.Process(child.pid)
            n.api.require(abs(p.create_time()-birth)<.001 and p.cmdline()==command,'Exact owned process at deadline')
            n.job.commit(folder/'deadline_stop.json',dict(utc=n.job.utc().isoformat(),pid=child.pid,created=birth,
                reason='User-authorized twelve-hour end; last sealed segments remain recoverable, unfinished raw never promoted.'))
            p.terminate();forced=True
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                n.api.require(abs(psutil.Process(child.pid).create_time()-birth)<.001,'Exact deadline process before forced stop')
                child.kill();child.wait(timeout=10)
        n.job.commit(folder/'exit.json',dict(exit_code=child.returncode,forced_deadline_stop=forced,utc=n.job.utc().isoformat(),design_sha256=n.api.sha(n.PLAN)))
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def launch():
    d=n.api.read(n.PLAN);n.verify(d)
    n.api.require(not n.RUN.exists() and not (n.RUN.parent/'supervisor_01').exists(),'No duplicate overnight launch')
    folder=n.RUN.parent/'launcher_01';folder.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,'-B','-u',str(Path(__file__).resolve()),'supervise']
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        child=subprocess.Popen(command,cwd=str(n.ROOT),env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    n.job.commit(folder/'launch.json',dict(pid=child.pid,created=psutil.Process(child.pid).create_time(),argv=command,
        utc=n.job.utc().isoformat(),design_sha256=n.api.sha(n.PLAN),authorized_end_utc=d['authorized_end_utc']))
    print('OVERNIGHT_SUPERVISOR_LAUNCHED',child.pid,d['authorized_end_utc'],flush=True)


if __name__=='__main__':
    {'launch':launch,'supervise':supervise}[sys.argv[1]]()
