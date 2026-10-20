"""Frozen uncorrected-pose local refinement gate."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage102_staging'),str(ROOT/'stage92_staging')]
import trajectory_nullspace_rescue_v1 as candidate
import verify_physical_error_budget_v1 as gates
h=candidate.h
OUT=ROOT/'stage102_evaluations/nullspace_local_01'
CASE=ROOT/'stage96_runs/population_prefix_01/s2_i0_prolate_ar4.json'
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(h.DESIGN.read_text());previous=json.loads(CASE.read_text())['result']
    h.dump(OUT/'protocol.json',dict(refinements=[1,2,4],horizon_s=.01,budget_s=30,
      input_hashes={str(p):h.sha(p) for p in (CASE,h.DESIGN)},
      source_hashes={str(Path(m.__file__)):h.sha(m.__file__) for m in (candidate,h,gates)},driver_sha256=h.sha(__file__),
      scope='Original uncorrected pose; no gap substitution in acceptance. Local test only.'))
    rows=[]
    for level in [1,2,4]:
        c=copy.deepcopy(cfg)
        for k in ('max_dt_s','relaxation_fraction','displacement_fraction','angle_limit_rad'):c['numerics'][k]/=level
        r=h.run_local(candidate,c,previous,2,.01,30);h.dump(OUT/f'dt{level}.json',r);rows.append(r)
        print(json.dumps(dict(level=level,status=r['status'],runtime=r['runtime_seconds'],counts=r['nullspace_rescue'])),flush=True)
    metrics=[gates.metrics(rows[i],rows[i+1],cfg['prolate_semiaxes_m'][0]) for i in [0,1]]
    passed=all(gates.health(r) and abs(r['time_s']-.01)<1e-12 for r in rows) and all(m['surface_displacement_bound_m']<=5e-12 and m['generalized_velocity_difference_m_s']<=1e-8 for m in metrics)
    h.dump(OUT/'results.json',dict(passed=passed,metrics=metrics,artifact_hashes={str(p):h.sha(p) for p in OUT.glob('*.json')}))
    h.dump(OUT/'completion.json',dict(status='complete_passed' if passed else 'complete_failed',results_sha256=h.sha(OUT/'results.json')))
if __name__=='__main__':main()
