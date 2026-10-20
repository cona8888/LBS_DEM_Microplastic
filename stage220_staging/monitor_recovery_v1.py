"""Bounded read-only status for the separate recovery namespace."""
import json
import psutil
import recover_fibre_v1 as r


def run():
    plan=r.api.read(r.PLAN);folder=r.RUN/'production_01';external=r.api.read(r.RUN/'production_launcher_01/launch.json')
    r.api.require(external['recovery_design_sha256']==r.api.sha(r.PLAN),'Original launch/design binding')
    alive=False;identity=False
    try:
        p=psutil.Process(external['pid']);alive=True
        identity=p.cmdline()==external['argv'] and abs(p.create_time()-external['created'])<.001
        r.api.require(identity,'Exact current recovery process identity')
    except psutil.NoSuchProcess:pass
    receipts=sorted(folder.glob('segment_*/results.json'));tail=None
    if receipts:
        path=receipts[-1];row=r.sealed(path);r.api.verify_mapping(row['artifacts'])
        r.api.require(row['passed'] and row['recovery_design_sha256']==r.api.sha(r.PLAN),'Passing bound latest segment')
        tail=dict(segment=path.parent.name,stop_s=row['summary']['stop_s'],steps=row['new_saved_steps'],latest_artifacts_verified=True)
    terminal=r.api.read(folder/'results.json') if (folder/'completion.json').exists() else None
    final=r.sealed(r.OUT/'combined_evaluation_01/results.json') if (r.OUT/'combined_evaluation_01/completion.json').exists() else None
    return dict(utc=r.job.utc().isoformat(),alive=alive,exact_process_identity=identity,verified_new_segments=len(receipts),latest=tail,
        inherited_start_s=plan['original_time_s'],terminal=terminal,final_evaluation=final,
        failures=[str(p) for p in r.RUN.rglob('failure.json')],new_trajectory_steps=0,
        original_campaign_remains_interrupted=True)


if __name__=='__main__':print(json.dumps(run(),indent=2))
