"""Unit tests of failure-only dispatch; stubs test routing, not physics."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage104_staging'))
import trajectory_failure_only_rescue_v1 as c
OUT=ROOT/'stage104_evaluations/dispatch_01'
def main():
    OUT.mkdir(parents=True,exist_ok=False);rows=[]
    cases=[('old_success',None,3,0,False,False),('eligible','direct contact residual nonconvergence',3,0,False,True),
      ('far_gap','direct contact residual nonconvergence',3,1e-12,False,False),('two_contacts','direct contact residual nonconvergence',2,0,False,False),
      ('unrelated','other failure',3,0,False,False),('rescue_fails','direct contact residual nonconvergence',3,0,True,True)]
    original=c.portfolio._solve,c.h.candidate.integrate,c.mixed
    try:
        for name,error,n,g,rescue_fail,expected in cases:
            calls=[]
            def old(*args):
                if error:raise RuntimeError(error)
                return 'old'
            def mixed(*args):
                calls.append(1)
                if rescue_fail:raise ValueError('rescue failed')
                return 'rescue'
            def parent(*args,**kwargs):
                return {'answer':c.portfolio._solve(np.zeros(6),np.eye(6),np.zeros((3*n,6)),np.full(n,g),1.,.3,1e-10,25000)}
            c.portfolio._solve=old;c.h.candidate.integrate=parent;c.mixed=mixed
            caught=None
            try:r=c.integrate()
            except RuntimeError as exc:caught=str(exc)
            expected_error=error if error and (not expected or rescue_fail) else None
            ok=bool(calls)==expected and caught==expected_error and c.portfolio._solve is old
            rows.append(dict(name=name,passed=ok,rescue_calls=len(calls),exception=caught))
    finally:c.portfolio._solve,c.h.candidate.integrate,c.mixed=original
    result=dict(passed=all(r['passed'] for r in rows),rows=rows,source_sha256=c.h.sha(__file__),candidate_sha256=c.h.sha(c.__file__))
    c.h.dump(OUT/'results.json',result);print(json.dumps(result))
if __name__=='__main__':main()
