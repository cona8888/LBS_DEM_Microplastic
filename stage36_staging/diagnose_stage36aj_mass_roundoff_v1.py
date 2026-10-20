import hashlib,json,platform
from pathlib import Path
import numpy as np

ROOT=Path(r"C:\MATDEM_MICROPLASTIC")
RUN=ROOT/'stage36_runs/stage36ai_periodic_drag_n32_full_20260910/run_01'
AH=ROOT/'stage36_evaluations/stage36ah_fast_projection_20260910/verification_01/fast_history.json'
OUT=ROOT/'stage36_evaluations/stage36aj_mass_roundoff_diagnosis_20260910/diagnosis_02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if OUT.exists():raise SystemExit('fail closed: output exists')
    failure=json.loads((RUN/'failure.json').read_text());hist=json.loads(AH.read_text())
    with np.load(RUN/'checkpoint_window_1.npz') as z:f=z['f']
    n=32**3;m64=float(f.sum());mext=float(np.sum(f,dtype=np.longdouble));target=float(n)
    rel64=m64/target-1;relext=mext/target-1
    eps=np.finfo(float).eps;steps=10240;failure_step=failure['step'];observed=failure['maxima']['mass']
    projected=observed*61440/failure_step
    checks={'process_stopped':True,'failure_is_mass_gate_only':bool(failure['maxima']['density']<.01 and failure['maxima']['slip']<1e-8 and failure['maxima']['ledger']<1e-11),
      'extended_sum_agrees':bool(abs(relext-rel64)<1e-16),'drift_small_vs_linear_eps_bound':bool(abs(rel64)<=steps*eps),'startup_drift_also_linear':bool(hist[-1]['mass_relative_drift']<=128*eps)}
    rec={'stage':'Stage36AJ','status':'mass_gate_failure_diagnosed_as_accumulated_roundoff' if all(checks.values()) else 'failed_closed',
      'failure_step':failure_step,'checkpoint_step':steps,'checkpoint_absolute_mass_change':mext-target,'checkpoint_relative_mass_change':relext,
      'float64_vs_extended_relative_difference':abs(relext-rel64),'machine_epsilon':eps,'steps_times_epsilon':steps*eps,
      'observed_failure_relative_drift':observed,'linear_projected_61440_relative_drift':projected,'checks':checks,
      'recommended_correction':'After each projection, add the global mass residual only to zero-velocity D3Q19 rest populations; this changes no momentum. Qualify against the uncorrected path before rerun.',
      'gate_policy':'retain the original 1e-12 mass gate; do not relax it','rerun_authorized':False,
      'input_hashes':{'failure':sha(RUN/'failure.json'),'checkpoint':sha(RUN/'checkpoint_window_1.npz'),'stage36ah_history':sha(AH)},'python':platform.python_version(),'numpy':np.__version__}
    OUT.mkdir(parents=True);(OUT/'diagnosis.json').write_text(json.dumps(rec,indent=2)+'\n')
    (OUT/'RESULTS.md').write_text(f'''# Stage36AJ mass-gate diagnosis\n\n- Status: `{rec['status']}`\n- Failure step: {failure_step}\n- Checkpoint relative mass change at 10,240 steps: {relext:.3e}\n- Float64 versus extended-sum difference: {abs(relext-rel64):.3e}\n- Linear machine-epsilon bound at 10,240 steps: {steps*eps:.3e}\n- Projected uncorrected drift at 61,440 steps: {projected:.3e}\n\nDensity, marker-slip and momentum-ledger gates were still satisfied. The failed run remains failed. The original `1e-12` mass gate is retained. Next, independently qualify a zero-momentum rest-population mass correction; no rerun is authorized by this diagnosis.\n''')
    if not all(checks.values()):raise SystemExit(2)
if __name__=='__main__':main()
