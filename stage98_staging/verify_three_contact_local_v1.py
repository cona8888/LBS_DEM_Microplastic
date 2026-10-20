"""Frozen local A/B at three time-step settings; not release observations."""
import copy
import json
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage89_staging'), str(ROOT/'stage92_staging'), str(ROOT/'stage98_staging')]
import verify_short_seed_local_v1 as h
import verify_physical_error_budget_v1 as gates
import trajectory_three_contact_seed_v1 as candidate
OUT = ROOT/'stage98_evaluations/three_contact_local_01'
CASE = ROOT/'stage96_runs/population_prefix_01/s2_i0_prolate_ar4.json'

def main():
    cfg = json.loads(h.DESIGN.read_text())
    previous = json.loads(CASE.read_text())['result']
    sources = [Path(__file__), Path(candidate.__file__), Path(h.__file__), Path(gates.__file__),
               Path(h.candidate.__file__), Path(h.candidate.stage50.__file__), Path(h.candidate.stage53.__file__)]
    OUT.mkdir(parents=True, exist_ok=False)
    protocol = dict(horizon_s=.01, budget_s_per_arm=30, refinements=[1,2,4],
                    surface_budget_m=5e-12, velocity_budget_m_s=1e-8,
                    input_hashes={str(p):h.sha(p) for p in (CASE,h.DESIGN)},
                    source_hashes={str(p):h.sha(p) for p in sources},
                    scope='Local reset-time numerical diagnostic only. No release or global promotion.')
    h.dump(OUT/'protocol.json',protocol)
    rows=[]
    for level in protocol['refinements']:
        config=copy.deepcopy(cfg)
        for key in ('max_dt_s','relaxation_fraction','displacement_fraction','angle_limit_rad'):
            config['numerics'][key] /= level
        pair={}
        for arm,module in [('baseline',h.candidate),('candidate',candidate)]:
            r=h.run_local(module,config,previous,2,.01,30.)
            pair[arm]=r
            h.dump(OUT/f'dt{level}_{arm}.json',r)
        m=gates.metrics(pair['baseline'],pair['candidate'],cfg['prolate_semiaxes_m'][0])
        checks=dict(health=all(gates.health(r) for r in pair.values()),
                    horizon=all(abs(r['time_s']-.01)<1e-12 for r in pair.values()),
                    surface=m['surface_displacement_bound_m']<=5e-12,
                    velocity=m['generalized_velocity_difference_m_s']<=1e-8,
                    same_steps=pair['baseline']['steps']==pair['candidate']['steps'],
                    same_rejections=pair['baseline']['rejected']==pair['candidate']['rejected'],
                    exercised=pair['candidate']['three_contact_seed_stats']['accepted']>0)
        row=dict(level=level,metrics=m,checks=checks,passed=all(checks.values()),
                 runtime_s={k:r['runtime_seconds'] for k,r in pair.items()},
                 counts=pair['candidate']['three_contact_seed_stats'])
        rows.append(row)
        print(json.dumps(row),flush=True)
    record=dict(passed=all(r['passed'] for r in rows),rows=rows,
                input_hashes=protocol['input_hashes'],source_hashes=protocol['source_hashes'],
                artifact_hashes={str(p):h.sha(p) for p in OUT.glob('*.json')})
    h.dump(OUT/'results.json',record)
    h.dump(OUT/'completion.json',dict(status='complete_passed' if record['passed'] else 'complete_failed',results_sha256=h.sha(OUT/'results.json')))
    if not record['passed']: raise SystemExit(1)

if __name__=='__main__': main()
