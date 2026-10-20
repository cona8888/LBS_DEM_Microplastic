import hashlib,json,time,platform
from pathlib import Path
import numpy as np
import periodic_drag_reference_v1 as exact
import periodic_drag_reference_fast_v1 as fast

ROOT=Path(r"C:\MATDEM_MICROPLASTIC");OUT=ROOT/'stage36_evaluations/stage36ah_fast_projection_20260910/verification_01'
CONTRACT=ROOT/'stage36_staging/STAGE36AH_FAST_PROJECTION_CONTRACT.md';E=ROOT/'stage36_staging/periodic_drag_reference_v1.py';F=ROOT/'stage36_staging/periodic_drag_reference_fast_v1.py'
PARENT=ROOT/'stage36_runs/stage36ag_periodic_drag_n32_diagnostic_20260910/diagnostic_01/manifest.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if OUT.exists():raise SystemExit('fail closed: output exists')
    p=json.loads(PARENT.read_text()); assert p['health_passed'] and not p['convergence_assessed']
    pars=exact.nominal_parameters(32); histories={};times={}
    for name,mod in [('exact',exact),('fast',fast)]:
        state=mod.initialize(32);rows=[];t=time.monotonic()
        for j in range(128):
            state,row=mod.step(state,pars['source_impulse_per_cell']);row['step']=j+1;rows.append(row)
        times[name]=time.monotonic()-t;histories[name]=rows
    fr=max(abs(a['force_on_sphere'][0]-b['force_on_sphere'][0])/pars['reference_force_lu'] for a,b in zip(histories['exact'],histories['fast']))
    ur=max(abs(a['superficial_velocity'][0]-b['superficial_velocity'][0])/pars['target_u_lu'] for a,b in zip(histories['exact'],histories['fast']))
    checks={'force_equivalence':fr<=1e-4,'velocity_equivalence':ur<=1e-5,'slip':max(r['marker_slip'] for r in histories['fast'])<=1e-8,
      'mass':max(r['mass_relative_drift'] for r in histories['fast'])<=1e-12,'density':max(r['density_error'] for r in histories['fast'])<=.01,
      'momentum':max(max(abs(x) for x in r['momentum_ledger_residual']) for r in histories['fast'])<=1e-11,'faster':times['fast']<times['exact']}
    OUT.mkdir(parents=True);(OUT/'exact_history.json').write_text(json.dumps(histories['exact'],indent=2)+'\n');(OUT/'fast_history.json').write_text(json.dumps(histories['fast'],indent=2)+'\n')
    rec={'stage':'Stage36AH','status':'accelerated_projection_equivalence_passed_startup_only' if all(checks.values()) else 'failed_closed',
      'steps':128,'checks':checks,'max_force_difference_reference_scaled':fr,'max_velocity_difference_target_scaled':ur,
      'wall_seconds':times,'speedup':times['exact']/times['fast'],'steady_drag_qualified':False,'passed':all(checks.values()),
      'input_hashes':{'contract':sha(CONTRACT),'exact':sha(E),'fast':sha(F),'parent':sha(PARENT)},'python':platform.python_version(),'numpy':np.__version__,
      'next_action':'run full immutable N32 diagnostic with accelerated projection only if passed'}
    rec['artifact_hashes']={str(x):sha(x) for x in OUT.iterdir()};(OUT/'verification.json').write_text(json.dumps(rec,indent=2)+'\n')
    (OUT/'RESULTS.md').write_text(f"# Stage36AH fast-projection verification\n\n- Status: `{rec['status']}`\n- 128-step force difference/reference: {fr:.3e}\n- Velocity difference/target: {ur:.3e}\n- Exact time: {times['exact']:.3f} s\n- Fast time: {times['fast']:.3f} s\n- Speedup: {rec['speedup']:.3f}x\n- Steady drag qualified: no\n")
    print(json.dumps(rec,indent=2));
    if not rec['passed']:raise SystemExit(2)
if __name__=='__main__':main()
