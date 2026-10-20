"""Capture first quarter-step failure without entering the retry cascade."""
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage89_staging'))
import verify_short_seed_local_v1 as h
contact=h.candidate.parent.parent.contact
OUT=ROOT/'stage99_evaluations/first_failure_01'
CASE=ROOT/'stage96_runs/population_prefix_01/s2_i0_prolate_ar4.json'
class Captured(BaseException): pass

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(h.DESIGN.read_text())
    for k in ('max_dt_s','relaxation_fraction','displacement_fraction','angle_limit_rad'):
        cfg['numerics'][k]/=4
    systems=[]
    original_solve=contact.portfolio._solve
    original_step=contact.inertial_contact_step
    def solve(*args,**kwargs):
        row={'args':args,'kwargs':kwargs}
        try:
            result=original_solve(*args,**kwargs)
        except RuntimeError as e:
            row['exception']=str(e)
            systems.append(row)
            raise
        row['health']=result[1]
        systems.append(row)
        return result
    def step(*args,**kwargs):
        try: return original_step(*args,**kwargs)
        except RuntimeError as e:
            h.dump(OUT/'capture.json',dict(exception=str(e),step_args=args,step_kwargs=kwargs,systems=systems))
            raise Captured()
    contact.portfolio._solve=solve
    contact.inertial_contact_step=step
    try:
        h.run_local(h.candidate,cfg,json.loads(CASE.read_text())['result'],2,.01,30.)
    except Captured: pass
    finally:
        contact.portfolio._solve=original_solve
        contact.inertial_contact_step=original_step
    capture=json.loads((OUT/'capture.json').read_text())
    sources={str(Path(m.__file__).resolve()):h.sha(m.__file__) for m in list(sys.modules.values())
             if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}
    result=dict(exception=capture['exception'],system_count=len(systems),
                inner_exceptions=[s.get('exception') for s in capture['systems']],
                source_hashes=sources,input_hashes={str(p):h.sha(p) for p in (CASE,h.DESIGN)},
                capture_sha256=h.sha(OUT/'capture.json'),scope='Numerical diagnostic; no release observation.')
    h.dump(OUT/'results.json',result)
    h.dump(OUT/'completion.json',dict(status='complete_captured',results_sha256=h.sha(OUT/'results.json')))
    print(json.dumps({k:result[k] for k in ('exception','system_count','inner_exceptions')}))
if __name__=='__main__': main()
