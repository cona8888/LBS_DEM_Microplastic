"""Fresh-process checkpoint verifier worker; inputs explicitly hash-bound."""
import json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage106_staging'))
import verify_checkpoint_v2 as lib
def main():
    job=json.loads(Path(sys.argv[1]).read_text())
    for p,d in job['bindings'].items():
        if lib.h.sha(p)!=d:raise RuntimeError('worker input/source drift')
    lib.Runner.binding=job['binding'];lib.Runner.checkpoint=job['checkpoint'];lib.Runner.pause=job.get('pause')
    state=json.loads(lib.CASE.read_text())['result'];cfg=json.loads(lib.h.DESIGN.read_text())
    result=lib.h.run_local(lib.Runner,cfg,state,2,.01,60.)
    out=Path(job['output'])
    if out.exists():raise RuntimeError('immutable output exists')
    lib.h.dump(out,dict(pid=os.getpid(),result=result,job_sha256=lib.h.sha(sys.argv[1])))
if __name__=='__main__':main()
