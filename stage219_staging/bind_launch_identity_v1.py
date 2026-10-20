"""Read-only actual direct-child birth certificate, unique C-side saved result."""
from pathlib import Path
import os,psutil,sys
import normal_gap_campaign_v1 as s
api,job=s.api,s.job
OUT=job.OUT/'launch_identity_01'

def run(expected):
    api.require(api.sha(job.DESIGN)==expected,'exact production design');job.verify(api.read(job.DESIGN))
    api.require(not OUT.exists(),'one immutable launch birth certificate')
    launch=api.read(job.RUN/'launch.json');pid=launch['supervisor_pid'];p=psutil.Process(pid)
    exact=[sys.executable,'-B','-u',str(job.SELF),'supervise','campaign']
    api.require(p.cmdline()==exact and launch['design_sha256']==expected and launch['argv']==exact[3:],'exact original supervisor command and launch')
    api.require(0<=job.policy.utc(launch['utc']).timestamp()-p.create_time()<=60,'supervisor birth precedes sealed launch in startup reserve')
    children=[]
    paths=[job.RUN/'auditor_launch.json',*sorted(job.RUN.glob('dispatch_*.json'))]
    for path in paths:
        a=api.read(path);child=psutil.Process(a['pid']);role=a.get('case','auditor');aff=api.read(job.RUN/(role+'.affinity.json'))
        api.require(a['design_sha256']==aff['design_sha256']==expected and child.cmdline()==a['argv'] and child.ppid()==pid
            and abs(child.create_time()-aff['created'])<.001 and child.cpu_affinity()==aff['current_affinity'],'exact direct-child command/birth/affinity identity')
        children.append(dict(role=role,pid=child.pid,created=child.create_time(),argv=child.cmdline(),parent=pid,launch_sha256=api.sha(path),affinity_sha256=api.sha(job.RUN/(role+'.affinity.json'))))
    api.require(len(children)==4 and {x['role'] for x in children}=={'auditor',*[c['id'] for c in api.read(job.DESIGN)['cases'][:3]]},'original three initial producers and one auditor')
    r=dict(passed=True,new_trajectory_steps=0,design_sha256=expected,supervisor=dict(pid=pid,created=p.create_time(),argv=p.cmdline(),launch_sha256=api.sha(job.RUN/'launch.json')),initial_children=children,
        utc=job.utc().isoformat(),source_sha256=api.sha(__file__),claim='Initial actual direct-child ancestry and exact birth identities, not trajectory completion.')
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
    print('NORMAL_GAP_LAUNCH_IDENTITIES',api.sha(OUT/'results.json'),r['supervisor'],flush=True)
if __name__=='__main__':run(sys.argv[1])
