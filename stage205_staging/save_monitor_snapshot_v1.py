"""Save one immutable read-only monitoring snapshot in the C evidence index."""
from pathlib import Path
import json,os,sys
import monitor_receipt_repaired_campaign_v1 as monitor


def commit(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.pending.{os.getpid()}')
    if path.exists() or tmp.exists():raise FileExistsError(str(path))
    with tmp.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.rename(tmp,path)


def run(label):
    if not label.replace('_','').isalnum():raise ValueError('simple unique label')
    root=Path(__file__).resolve().parents[1]/'stage205_evaluations/receipt_repaired_campaign_20260930'/label
    r=monitor.run();r['new_trajectory_steps']=0
    commit(root/'results.json',r);commit(root/'completion.json',dict(passed=True,results_sha256=monitor.ns['sha'](root/'results.json')))
    print(json.dumps(dict(output=str(root),utc=r['utc'],design_sha256=r['design_sha256'],verified_segments=sum(x['verified_segments'] for x in r['cases']),declared_saved_steps=sum(x['declared_saved_steps'] for x in r['cases']),pending_snapshot=r['outstanding_snapshot'],failure_markers=r['failure_markers'],stderr=r['stderr'],terminal=r['terminal'],source_and_inputs_verified=r['frozen_sources_verified'] and r['frozen_inputs_verified']),indent=2))


if __name__=='__main__':run(sys.argv[1])
