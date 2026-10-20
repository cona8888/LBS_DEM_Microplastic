"""Exclusive C-side snapshot using the qualified read-only generation guard."""
import sys
from pathlib import Path
import cone_feasibility_campaign_v1 as s
import monitor_cone_campaign_v6 as monitor


def run(label):
    s.api.require(label.isidentifier(), 'simple unique snapshot label')
    out = s.job.OUT / label; s.api.require(not out.exists(), 'exclusive monitor snapshot')
    qual = s.sealed(s.job.OUT / 'monitor_generation_qualification_01/results.json')
    s.api.require(qual['passed'] and qual['new_trajectory_steps'] == 0, 'qualified read-only monitor')
    s.api.verify_mapping(qual['inputs'])
    result = monitor.run(s.api.sha(s.job.DESIGN))
    result.update(snapshot_script_sha256=s.api.sha(__file__), monitor_qualification_sha256=s.api.sha(s.job.OUT / 'monitor_generation_qualification_01/results.json'))
    s.job.commit(out / 'results.json', result)
    s.job.commit(out / 'completion.json', dict(passed=True, results_sha256=s.api.sha(out / 'results.json'), claim='Read-only publication snapshot; not full terminal acceptance.'))
    print('SNAPSHOT', out, s.api.sha(out / 'results.json'), flush=True)


if __name__ == '__main__': run(sys.argv[1])
