import hashlib,json,platform
from pathlib import Path
import numpy as np
import periodic_drag_reference_fast_v1 as raw
import periodic_drag_reference_massclosed_v1 as fixed
import periodic_drag_reference_v1 as ref

ROOT=Path(r"C:\MATDEM_MICROPLASTIC");OUT=ROOT/'stage36_evaluations/stage36ak_mass_correction_20260910/verification_01'
CONTRACT=ROOT/'stage36_staging/STAGE36AK_REST_MASS_CORRECTION_CONTRACT.md';SRC=ROOT/'stage36_staging/periodic_drag_reference_massclosed_v1.py'
PARENT=ROOT/'stage36_evaluations/stage36aj_mass_roundoff_diagnosis_20260910/diagnosis_02/diagnosis.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if OUT.exists():raise SystemExit('fail closed: output exists')
    parent=json.loads(PARENT.read_text());assert parent['status']=='mass_gate_failure_diagnosed_as_accumulated_roundoff' and not parent['rerun_authorized']
    pars=ref.nominal_parameters(32);hist={}
    for name,mod in [('raw',raw),('fixed',fixed)]:
        state=mod.initialize(32);rows=[]
        for j in range(256):
            state,row=mod.step(state,pars['source_impulse_per_cell']);row['step']=j+1;rows.append(row)
        hist[name]=rows
    fr=max(abs(a['force_on_sphere'][0]-b['force_on_sphere'][0])/pars['reference_force_lu'] for a,b in zip(hist['raw'],hist['fixed']))
    ur=max(abs(a['superficial_velocity'][0]-b['superficial_velocity'][0])/pars['target_u_lu'] for a,b in zip(hist['raw'],hist['fixed']))
    maxcorr=max(abs(x['mass_restoration_lu']) for x in hist['fixed'])
    checks={'force_equivalence':fr<=1e-8,'velocity_equivalence':ur<=1e-8,'mass':max(x['mass_relative_drift'] for x in hist['fixed'])<=1e-14,
      'momentum':max(max(abs(v) for v in x['momentum_ledger_residual']) for x in hist['fixed'])<=1e-11,
      'density':max(x['density_error'] for x in hist['fixed'])<=.01,'slip':max(x['marker_slip'] for x in hist['fixed'])<=1e-8,
      'positivity':min(x['minimum_population'] for x in hist['fixed'])>0,'correction_bound':maxcorr<=1e-9}
    OUT.mkdir(parents=True);(OUT/'raw_history.json').write_text(json.dumps(hist['raw'],indent=2)+'\n');(OUT/'fixed_history.json').write_text(json.dumps(hist['fixed'],indent=2)+'\n')
    rec={'stage':'Stage36AK','status':'zero_momentum_mass_correction_qualified' if all(checks.values()) else 'failed_closed','steps':256,'checks':checks,
      'max_force_difference_reference_scaled':fr,'max_velocity_difference_target_scaled':ur,'max_absolute_mass_restoration_lu':maxcorr,
      'rerun_authorized':all(checks.values()),'n48_n64_authorized':False,'input_hashes':{'contract':sha(CONTRACT),'candidate':sha(SRC),'parent':sha(PARENT)},'python':platform.python_version(),'numpy':np.__version__}
    rec['artifact_hashes']={str(p):sha(p) for p in OUT.iterdir()};(OUT/'verification.json').write_text(json.dumps(rec,indent=2)+'\n')
    (OUT/'RESULTS.md').write_text(f"# Stage36AK mass-restoration verification\n\n- Status: `{rec['status']}`\n- Force difference/reference: {fr:.3e}\n- Velocity difference/target: {ur:.3e}\n- Maximum per-step correction: {maxcorr:.3e} LU\n- Fresh N32 rerun authorized: {str(rec['rerun_authorized']).lower()}\n- N48/N64 authorized: no\n")
    print(json.dumps(rec,indent=2));
    if not rec['rerun_authorized']:raise SystemExit(2)
if __name__=='__main__':main()
