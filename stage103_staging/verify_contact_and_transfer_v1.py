"""Analytical contact regression then frozen-start numerical transfer."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage102_staging'),str(ROOT/'stage92_staging')]
import trajectory_nullspace_rescue_v1 as candidate
import verify_physical_error_budget_v1 as gates
h=candidate.h
OUT=ROOT/'stage103_evaluations/contact_and_transfer_01'
CASE=ROOT/'stage96_runs/population_prefix_01/s2_i0_prolate_ar4.json'
START=ROOT/'stage95_designs/common_admissible_population_01/starts_s2.json'
PRIOR=ROOT/'stage102_evaluations/nullspace_local_01/results.json'
def main():
    prior=json.loads(PRIOR.read_text())
    if not prior['passed']:raise RuntimeError('local gate not passed')
    for p,d in prior['artifact_hashes'].items():
        if h.sha(p)!=d:raise RuntimeError('local evidence drift')
    OUT.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(h.DESIGN.read_text());reference=json.loads(CASE.read_text())['result']
    sources={str(Path(m.__file__).resolve()):h.sha(m.__file__) for m in list(sys.modules.values())
      if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}
    protocol=dict(target_s=reference['time_s'],budget_s=360.,surface_budget_m=5e-12,velocity_budget_m_s=1e-8,
      input_hashes={str(p):h.sha(p) for p in (CASE,START,PRIOR,h.DESIGN)},source_hashes=sources,
      scope='Analytical regressions and original-start transfer, not an extended release observation.')
    h.dump(OUT/'protocol.json',protocol)
    J=np.vstack([np.eye(6),np.eye(6)[:3]]);M=np.eye(6);tests=[]
    for name in ('sticking','sliding','separating','frictionless','outside_rescue'):
        mu=0. if name=='frictionless' else .3
        q=np.zeros(6);force=np.zeros(9);g=np.zeros(3)
        if name=='separating':q=np.ones(6)
        else:
            force[::3]=1.
            if name in ('sliding','frictionless'):q[[1,4]]=1.
            if name=='outside_rescue':g[:]=1e-6;q[[0,3]]=-1e-6
            w=J@q
            for k in range(3):
                t=w[3*k+1:3*k+3]
                if np.linalg.norm(t)>0:force[3*k+1:3*k+3]=-mu*t/np.linalg.norm(t)
        v=q-M@J.T@force;route='bypass'
        if np.max(np.abs(g))<=1e-15:
            try:answer,health=candidate.mixed(v,M,J,g,1.,mu,1e-10,25000);route='rescue'
            except (RuntimeError,ValueError,FloatingPointError,np.linalg.LinAlgError):
                answer,health=h.candidate._original_solve(v,M,J,g,1.,mu,1e-10,25000);route='fallback'
        else:answer,health=h.candidate._original_solve(v,M,J,g,1.,mu,1e-10,25000)
        err=float(np.linalg.norm(answer-q));passed=err<=1e-8 and health['residual']<=1e-10 and health['force_residual']<=1e-8
        tests.append(dict(name=name,passed=passed,velocity_error=err,route=route,health=health))
    h.dump(OUT/'analytical_tests.json',tests)
    if not all(t['passed'] for t in tests):raise RuntimeError('analytical gate failed')
    print('All five analytical contact checks passed; starting original-start replay.',flush=True)
    start=json.loads(START.read_text())[0]
    previous=dict(position_m=start['position_m'],orientation=start['orientation'],velocity_generalized=start['initial_velocity_generalized'])
    r=h.run_local(candidate,cfg,previous,2,reference['time_s'],360.)
    h.dump(OUT/'candidate.json',r)
    metrics=gates.metrics(reference,r,cfg['prolate_semiaxes_m'][0])
    checks=dict(completed=r['status']=='present_at_horizon' and abs(r['time_s']-reference['time_s'])<1e-12,
      health=gates.health(r),surface=metrics['surface_displacement_bound_m']<=5e-12,
      velocity=metrics['generalized_velocity_difference_m_s']<=1e-8,
      exercised=r['nullspace_rescue']['accepted']>0)
    result=dict(passed=all(checks.values()),checks=checks,metrics=metrics,
      runtime_s=r['runtime_seconds'],counts=r['nullspace_rescue'],
      step_change=r['steps']-reference['steps'],rejection_change=r['rejected']-reference['rejected'],
      artifact_hashes={str(p):h.sha(p) for p in OUT.glob('*.json')})
    h.dump(OUT/'results.json',result);h.dump(OUT/'completion.json',dict(status='complete_passed' if result['passed'] else 'complete_failed',results_sha256=h.sha(OUT/'results.json')))
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
