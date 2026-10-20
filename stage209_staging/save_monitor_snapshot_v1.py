"""Append one immutable C-side read-only snapshot; never mutate production."""
import sys
from pathlib import Path
import cone_feasibility_campaign_v1 as s
import monitor_cone_campaign_v3 as monitor

def run(label):
    s.api.require(label.isidentifier(),'simple unique snapshot label')
    out=s.job.OUT/label;s.api.require(not out.exists(),'exclusive monitor snapshot')
    result=monitor.run(s.api.sha(s.job.DESIGN))
    result['snapshot_script_sha256']=s.api.sha(__file__)
    s.job.commit(out/'results.json',result)
    s.job.commit(out/'completion.json',dict(passed=True,results_sha256=s.api.sha(out/'results.json'),claim='Read-only publication snapshot; not full terminal acceptance.'))
    print('SNAPSHOT',out,s.api.sha(out/'results.json'),flush=True)
    print('COUNTS',sum(x['sealed_segments'] for x in result['cases']),sum(x['verified_segments'] for x in result['cases']),sum(x['declared_saved_steps'] for x in result['cases']),result['failure_markers'],result['stderr'],flush=True)

if __name__=='__main__':run(sys.argv[1])
