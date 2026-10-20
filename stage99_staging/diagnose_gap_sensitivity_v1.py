"""Gap-roundoff sensitivity only: perturbed cases cannot replace original data."""
import json
import sys
import time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage89_staging'))
import verify_short_seed_local_v1 as h
CAP=ROOT/'stage99_evaluations/first_failure_01/capture.json'
OUT=ROOT/'stage99_evaluations/gap_sensitivity_01'

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    raw=json.loads(CAP.read_text())['systems'][0]
    args=[np.asarray(x) if i<4 else x for i,x in enumerate(raw['args'])]
    h.dump(OUT/'protocol.json',dict(factors=[1.,.1,0.],source_sha256=h.sha(__file__),capture_sha256=h.sha(CAP),
      scope='Deliberate gap perturbation sensitivity, not a production remedy or accepted trajectory.'))
    rows=[]
    for factor in [1.,.1,0.]:
        a=list(args);a[3]=args[3]*factor;t=time.perf_counter()
        try:
            v,health=h.candidate.stage53._solve(*a,**raw['kwargs'])
            row=dict(factor=factor,passed=True,velocity=v,health=health)
        except RuntimeError as e:row=dict(factor=factor,passed=False,exception=str(e))
        row['runtime_s']=time.perf_counter()-t; rows.append(row)
        print(json.dumps(row,default=h.json_value),flush=True)
    h.dump(OUT/'results.json',dict(rows=rows,protocol_sha256=h.sha(OUT/'protocol.json')))
    h.dump(OUT/'completion.json',dict(status='complete_diagnostic',results_sha256=h.sha(OUT/'results.json')))
if __name__=='__main__':main()
