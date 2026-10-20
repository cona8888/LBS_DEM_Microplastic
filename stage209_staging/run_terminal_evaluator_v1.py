"""Exclusive original terminal evaluation witness; never duplicate an audit."""
from pathlib import Path
import os,sys,time,subprocess,traceback,psutil
import cone_feasibility_campaign_v1 as s
api,job=s.api,s.job

def run(expected):
    api.require(api.sha(job.DESIGN)==expected,'exact frozen design')
    d=api.read(job.DESIGN);job.verify(d);s.require_old_terminal_closure();terminal=api.read(job.RUN/'completion.json')
    api.require(terminal['design_sha256']==expected and terminal['all_owned_processes_retired'],'terminal lifecycle bound')
    work=job.OUT/'terminal_evaluator_01';out=job.OUT/'evaluation_01'
    api.require(not work.exists() and not out.exists() and not s.active_owned(),'no existing evaluation/process/output')
    api.require(job.utc()<job.policy.utc(d['final_audit_deadline_utc']),'new audit before cutoff only')
    work.mkdir(parents=True,exist_ok=False)
    current=psutil.Process();job.commit(work/'witness_launch.json',dict(pid=os.getpid(),created=current.create_time(),argv=current.cmdline(),utc=job.utc().isoformat(),design_sha256=expected,source_sha256=api.sha(__file__),new_trajectory_steps=0))
    command=[sys.executable,'-B','-u',str(job.SELF),'evaluate','campaign']
    try:
        with (work/'stdout.log').open('xb') as stdout,(work/'stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=str(s.ROOT),env=dict(os.environ,OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1'),stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        job.commit(work/'evaluator_launch.json',dict(pid=child.pid,created=psutil.Process(child.pid).create_time(),argv=command,utc=job.utc().isoformat(),design_sha256=expected,source_sha256=api.sha(job.SELF),threads=1,new_trajectory_steps=0))
        while child.poll() is None:
            if job.utc()>=job.policy.utc(d['final_audit_deadline_utc']):
                job.commit(work/'unfinished_at_cutoff.json',dict(pid=child.pid,utc=job.utc().isoformat(),child_left_running=True));return
            time.sleep(5)
        result=dict(exit_code=child.returncode,utc=job.utc().isoformat(),design_sha256=expected,new_trajectory_steps=0,evaluation_output_exists=out.exists())
        if (out/'results.json').exists() and (out/'completion.json').exists():
            r=s.sealed(out/'results.json');result.update(results_sha256=api.sha(out/'results.json'),audit_passed=bool(r['passed']))
        job.commit(work/'exit.json',result);job.commit(work/'completion.json',dict(passed=child.returncode==0 and 'results_sha256' in result,exit_sha256=api.sha(work/'exit.json'),audit_passed=result.get('audit_passed',False)))
        print('TERMINAL_EVALUATOR_EXIT',result,flush=True)
    except Exception as error:
        job.commit(work/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),utc=job.utc().isoformat()));raise
if __name__=='__main__':run(sys.argv[1])
