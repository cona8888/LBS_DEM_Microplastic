"""Unique C-side bounded read-only snapshot; source and previous monitor retained."""
import sys
import monitor_normal_gap_campaign_v2 as m
def run(expected,label):
    m.api.require(label and len(label)<=80 and all(x.isalnum() or x in '_-' for x in label),'simple exclusive snapshot label')
    out=m.job.OUT/label;m.api.require(not out.exists(),'unique immutable snapshot')
    r=m.run(expected);m.job.commit(out/'results.json',r);m.job.commit(out/'completion.json',dict(snapshot_saved=True,results_sha256=m.api.sha(out/'results.json')))
    print('NORMAL_GAP_BOUNDED_SNAPSHOT',label,len(r['processes']),sum(c['verified_segments'] for c in r['cases']),r['outstanding_snapshot'],r['failure_markers'],flush=True)
if __name__=='__main__':run(*sys.argv[1:])
