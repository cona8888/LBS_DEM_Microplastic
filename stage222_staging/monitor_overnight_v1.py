"""Compact read-only exact-process and sealed-evidence status."""
from pathlib import Path
import json, psutil
import overnight_campaign_v1 as n


def identity(path):
    if not path.exists():return None
    row=n.api.read(path)
    try:
        p=psutil.Process(row['pid'])
        n.api.require(abs(p.create_time()-row['created'])<.001 and p.cmdline()==row['argv'],'Exact owned monitor identity')
        return dict(pid=p.pid,alive=True,identity_verified=True)
    except psutil.NoSuchProcess:
        return dict(pid=row['pid'],alive=False,identity_verified=False)


def run():
    d=n.api.read(n.PLAN)
    sealed=list(n.RUN.glob('*/segment_*/completion.json'))
    latest=None
    if sealed:
        path=max(sealed,key=lambda p:p.stat().st_mtime_ns).with_name('results.json')
        row=n.sealed(path)
        n.api.verify_mapping(row['artifacts'])
        latest=dict(case=path.parent.parent.name,segment=path.parent.name,stop_s=row['summary']['stop_s'],steps=row['new_saved_steps'],passed=row['passed'],artifacts_verified=True)
    comparisons=[]
    for p in n.OUT.glob('*/comparison_01/completion.json'):
        row=n.sealed(p.with_name('results.json'))
        comparisons.append(dict(case=row['case'],reference_case=row['reference_case'],passed=row['passed']))
    return dict(utc=n.job.utc().isoformat(),authorized_end_utc=d['authorized_end_utc'],
        supervisor=identity(n.RUN.parent/'launcher_01/launch.json'),worker=identity(n.RUN.parent/'supervisor_01/worker_launch.json'),
        prerequisite_complete=(n.PREREQUISITE.parent/'completion.json').exists(),
        prerequisite_admitted=(n.RUN/'prerequisite_admission.json').exists(),new_sealed_production_segments=len(sealed),latest=latest,
        comparisons=comparisons,finished=(n.RUN/'completion.json').exists(),
        terminal=n.api.read(n.RUN/'results.json') if (n.RUN/'completion.json').exists() else None,
        failures=[str(p) for p in n.RUN.rglob('failure.json')],deadline_forced_stop=(n.RUN.parent/'supervisor_01/deadline_stop.json').exists(),
        new_trajectory_steps=0)


if __name__=='__main__':print(json.dumps(run(),indent=2))
