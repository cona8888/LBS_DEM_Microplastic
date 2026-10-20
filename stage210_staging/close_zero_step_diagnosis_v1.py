"""Seal completed zero-step diagnosis without promoting the failed campaign."""
from pathlib import Path
import os,psutil,traceback
import authenticate_failed_system_v1 as source
job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage210_evaluations/three_contact_failure_20261001'
OUT=BASE/'diagnosis_handoff_01'


def run():
    d=api.read(job.DESIGN);job.verify(d);w=api.read(source.WORK);assert w['maximum_new_trajectory_steps']==0
    results=sorted(BASE.glob('*/results.json'));failures=sorted(BASE.glob('*/failure.json'))
    assert len(results)>=15
    inputs={str(p):api.sha(p) for p in [Path(__file__),source.WORK,job.DESIGN,*results,*failures]}
    entries=[]
    for path in results:
        r=api.read(path);assert r['new_trajectory_steps']==0
        completion=path.parent/'completion.json';assert api.read(completion)['results_sha256']==api.sha(path)
        inputs[str(completion)]=api.sha(completion)
        entries.append(dict(kind=path.parent.name,results_sha256=api.sha(path),new_trajectory_steps=0,claim=r.get('claim')))
    for path in failures:assert api.read(path)['new_trajectory_steps']==0
    # No owned diagnostic worker may remain. Do not touch the separate evaluator.
    active=[]
    for p in psutil.process_iter(['pid','name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:cmd=p.cmdline()
        except (psutil.NoSuchProcess,psutil.AccessDenied):continue
        if any('stage210_staging' in x.replace('/','\\').lower() for x in cmd):active.append(dict(pid=p.pid,argv=cmd))
    assert not active,'diagnostic still active; do not duplicate closure'
    witness=ROOT/'stage209_evaluations/cone_feasibility_campaign_20260930/terminal_evaluator_01/evaluator_launch.json'
    e=api.read(witness);p=psutil.Process(e['pid'])
    assert p.cmdline()==e['argv'] and abs(p.create_time()-e['created'])<.001
    inputs[str(witness)]=api.sha(witness)
    OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs))
    try:
        api.verify_mapping(inputs);job.verify(d)
        r=dict(new_trajectory_steps=0,saved_diagnostic_trajectory_steps=0,independently_accepted_diagnostic_trajectory_steps=0,
            original_stage209_remains_failed_incomplete=True,numerical_campaign_goal_achieved=False,
            no_repair_installed=True,no_active_stage210_diagnostic=True,diagnostic_results=entries,
            preserved_failure_artifacts=[dict(path=str(p),sha256=api.sha(p)) for p in failures],
            existing_terminal_evaluator=dict(pid=p.pid,created=p.create_time(),command_bound=True,cpu_seconds=p.cpu_times().user+p.cpu_times().system),
            inputs=inputs,next_gate='Await user decision on any revised roundoff-aware numerical contact-gap contract. Continue only the existing single Stage209 audit and its preserved failed/incomplete accounting; no new trajectory or production.',
            claim='Closed zero-trajectory diagnosis with exact conditional-mode certificates and necessary-polynomial census, but no global frictional infeasibility proof or passing repair. Search failures do not justify silent gate changes. All original evidence preserved.')
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
        print('ZERO_STEP_DIAGNOSIS_CLOSED',len(entries),'results',len(failures),'preserved failures',flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
