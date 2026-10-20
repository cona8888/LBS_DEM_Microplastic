"""Start one qualified, hidden continuation and record its exact birth identity."""
from pathlib import Path
import os, subprocess, sys
import psutil
import recover_fibre_v1 as r


def run():
    p=r.verify_plan();q=r.sealed(r.OUT/'restart_qualification_01/results.json')
    r.api.require(q['passed'] and q['recovery_design_sha256']==r.api.sha(r.PLAN),'Exact qualified recovery')
    r.api.require(not r.source.active_owned(),'No competing workspace Python work')
    out=r.RUN/'production_launcher_01';out.mkdir(parents=True,exist_ok=False)
    r.api.require(not (r.RUN/'production_01').exists(),'One fresh recovery output')
    command=[sys.executable,'-B','-u',str(Path(r.__file__).resolve()),'produce']
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
        child=subprocess.Popen(command,cwd=str(r.ROOT),env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    proc=psutil.Process(child.pid)
    r.job.commit(out/'launch.json',dict(pid=child.pid,created=proc.create_time(),argv=command,utc=r.job.utc().isoformat(),
        recovery_design_sha256=r.api.sha(r.PLAN),source_sha256=r.api.sha(r.__file__),threads=1,
        original_campaign_remains_interrupted=True,automatic_final_evaluation_after_complete_recovery=True))
    print('RECOVERY_LAUNCHED',child.pid,proc.create_time(),flush=True)


if __name__=='__main__':run()
