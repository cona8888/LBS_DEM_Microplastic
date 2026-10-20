"""Explicit translation-only local repair experiment; never edit saved state."""
import copy
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage100_staging'),str(ROOT/'stage89_staging'),str(ROOT/'stage92_staging')]
import audit_high_precision_gaps_v1 as hp
import verify_short_seed_local_v1 as h
import verify_physical_error_budget_v1 as gates
OUT=ROOT/'stage100_evaluations/bounded_correction_01'
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(h.DESIGN.read_text());state=json.loads(hp.CASE.read_text())['result']
    cap=json.loads(hp.CAP.read_text());audit=json.loads((hp.OUT/'results.json').read_text())
    protocol=dict(target_gap_m=1e-16,max_translation_m=5e-12,refinements=[1,2,4],horizon_s=.01,budget_s=30.,
      scope='Local corrected-pose diagnostic; no physical continuation, no release observation, no automatic production correction.',
      input_hashes={str(p):h.sha(p) for p in (hp.CASE,hp.CAP,h.DESIGN,hp.OUT/'results.json')},
      source_hashes={str(Path(m.__file__)):h.sha(m.__file__) for m in (hp,h,gates,h.candidate)},driver_sha256=h.sha(__file__))
    h.dump(OUT/'protocol.json',protocol)
    normals=np.array([c[2] for c in cap['step_args'][6]])
    gaps=np.array([float(r['high_precision_gap_m'][-1]) for r in audit['rows']])
    dx=np.linalg.solve(normals,np.full(3,protocol['target_gap_m'])-gaps)
    previous=copy.deepcopy(state);previous['position_m']=(np.array(state['position_m'])+dx).tolist()
    actual=float(np.linalg.norm(np.array(previous['position_m'])-state['position_m']))
    if actual>protocol['max_translation_m']:raise RuntimeError('correction exceeds budget')
    _,geom,_,_,_=h.matrix_case_v1.load(2);a,b,_=cfg['prolate_semiaxes_m']
    checked=[]
    for k in range(len(geom.r)):
        g=hp.gap(previous['position_m'],previous['orientation'],a,b,geom.c[k],geom.r[k],geom.L,60)
        checked.append(dict(id=k,gap_m=str(g)))
    if any(hp.Decimal(c['gap_m'])<0 for c in checked):raise RuntimeError('corrected pose overlaps')
    h.dump(OUT/'corrected_pose.json',dict(state=previous,translation_m=actual,requested_dx=dx,all_grain_gaps=checked))
    rows=[]
    for level in [1,2,4]:
        config=copy.deepcopy(cfg)
        for k in ('max_dt_s','relaxation_fraction','displacement_fraction','angle_limit_rad'):config['numerics'][k]/=level
        r=h.run_local(h.candidate,config,previous,2,.01,30.)
        h.dump(OUT/f'dt{level}.json',r)
        row=dict(level=level,status=r['status'],time_s=r['time_s'],runtime_s=r['runtime_seconds'],steps=r['steps'],rejected=r['rejected'],health=gates.health(r))
        rows.append(row);print(json.dumps(row),flush=True)
    result=dict(rows=rows,all_local_runs_passed=all(r['health'] and abs(r['time_s']-.01)<1e-12 for r in rows),
      translation_m=actual,grains_checked=len(checked),artifact_hashes={str(p):h.sha(p) for p in OUT.glob('*.json')})
    h.dump(OUT/'results.json',result)
    h.dump(OUT/'completion.json',dict(status='complete_diagnostic',results_sha256=h.sha(OUT/'results.json')))
if __name__=='__main__':main()
