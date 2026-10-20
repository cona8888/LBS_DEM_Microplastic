"""Seal exact live creation identities with original parent/launch bindings."""
import os,psutil
from pathlib import Path
import cone_feasibility_campaign_v1 as s
api,job=s.api,s.job

def run():
    d=api.read(job.DESIGN);job.verify(d);launch=api.read(job.RUN/'launch.json');expected=api.sha(job.DESIGN)
    p=psutil.Process(launch['supervisor_pid']);command=[os.sys.executable,'-B','-u',str(job.SELF),'supervise','campaign']
    api.require(p.cmdline()==command and launch['design_sha256']==expected,'original exact supervisor command/design')
    children=[]
    for file in [job.RUN/'auditor_launch.json',*sorted(job.RUN.glob('dispatch_*.json'))]:
        x=api.read(file);child=psutil.Process(x['pid']);api.require(child.ppid()==p.pid and child.cmdline()==x['argv'] and x['design_sha256']==expected,'original direct child launch/source ancestry')
        children.append(dict(pid=child.pid,created=child.create_time(),argv=child.cmdline(),ppid=child.ppid(),launch_path=str(file),launch_sha256=api.sha(file)))
    api.require(len(children)==4,'one auditor plus three initial producers')
    out=job.OUT/'launch_identity_01';api.require(not out.exists(),'exclusive process certificate')
    result=dict(passed=True,new_trajectory_steps=0,utc=job.utc().isoformat(),design_sha256=expected,source_sha256=api.sha(job.SELF),supervisor=dict(pid=p.pid,created=p.create_time(),argv=p.cmdline()),children=children,original_launch_sha256=api.sha(job.RUN/'launch.json'),launch_utc=launch['utc'],reason='Supervisor imports/hash checks take3.45 seconds before original launch.json timestamp. Exact process creation plus direct-child ancestry replaces a false-negative3s timestamp heuristic; no producer/scientific gate changed.',script_sha256=api.sha(__file__))
    job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')))
    err=job.OUT/'read_only_monitor_v1_failure_01';job.commit(err/'results.json',dict(new_trajectory_steps=0,error="KeyError('utc')",reason='Frozen original auditor_launch.json lacks utc; authoritative auditor.affinity.json has PID/design-bound utc. Read-only monitor only; original production frozen sources unchanged.',monitor_sha256=api.sha(Path(__file__).with_name('monitor_cone_campaign_v1.py'))));job.commit(err/'completion.json',dict(passed=False,results_sha256=api.sha(err/'results.json')))
    print('LIVE_LAUNCH_IDENTITY_BOUND',api.sha(out/'results.json'),flush=True)

if __name__=='__main__':run()
