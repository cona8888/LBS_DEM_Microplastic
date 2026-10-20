"""Three refined local runs with prospective projection and state budgets."""
import copy
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage101_staging'),str(ROOT/'stage92_staging')]
import trajectory_bounded_projection_v2 as candidate
import verify_physical_error_budget_v1 as gates
h=candidate.h;hp=candidate.hp
OUT=ROOT/'stage101_evaluations/projection_local_02'
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(h.DESIGN.read_text());previous=json.loads(hp.CASE.read_text())['result']
    protocol=dict(refinements=[1,2,4],horizon_s=.01,budget_s=30.,cumulative_projection_budget_m=5e-12,
      surface_difference_budget_m=5e-12,velocity_difference_budget_m_s=1e-8,
      input_hashes={str(p):h.sha(p) for p in (hp.CASE,h.DESIGN)},
      source_hashes={str(Path(m.__file__)):h.sha(m.__file__) for m in (candidate,hp,h,gates)},driver_sha256=h.sha(__file__),
      scope='Local solution verification only; no release claim or production promotion.')
    h.dump(OUT/'protocol.json',protocol)
    results=[]
    for level in [1,2,4]:
        cfg2=copy.deepcopy(cfg)
        for k in ('max_dt_s','relaxation_fraction','displacement_fraction','angle_limit_rad'):cfg2['numerics'][k]/=level
        r=h.run_local(candidate,cfg2,previous,2,.01,30.)
        h.dump(OUT/f'dt{level}.json',r);results.append(r)
        print(json.dumps(dict(level=level,status=r['status'],runtime_s=r['runtime_seconds'],steps=r['steps'],rejected=r['rejected'],projection_m=r['projection']['total_translation_m'])),flush=True)
    comparisons=[gates.metrics(results[i],results[i+1],cfg['prolate_semiaxes_m'][0]) for i in range(2)]
    passed=all(gates.health(r) and abs(r['time_s']-.01)<1e-12 for r in results) and all(m['surface_displacement_bound_m']<=5e-12 and m['generalized_velocity_difference_m_s']<=1e-8 for m in comparisons)
    record=dict(passed=passed,comparisons=comparisons,artifact_hashes={str(p):h.sha(p) for p in OUT.glob('*.json')})
    h.dump(OUT/'results.json',record);h.dump(OUT/'completion.json',dict(status='complete_passed' if passed else 'complete_failed',results_sha256=h.sha(OUT/'results.json')))
if __name__=='__main__':main()
