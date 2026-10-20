"""Read-only hypothesis diagnosis from sealed Stage241 evidence; no solvers."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'stage241_evaluations/cycle_relaxation_20261012'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    final=BASE/'final_disposition_01/results.json'
    assert sha(final)=='761b864a75300648ccc719ff5324e6b2ae6dfb7c8aef9cd745e386f760815aab'
    r=read(final);assert read(final.with_name('completion.json'))['results_sha256']==sha(final)
    for p,d in r['artifacts'].items():assert sha(p)==d,p
    assert r['diagnostic_audits_completed'] and not r['method_viability_passed'] and r['known_map_evaluations']==82
    capture=BASE/'call_01_failed/captured_call.json';auditpath=capture.with_name('results.json')
    saved=read(capture);audit=read(auditpath)['original_independent_force_and_recurrence_audit']
    trial=saved['fixture']['contact_trial_trace']['detailed_trials'][0];rows=trial['inner_systems'];args=trial['outer_inputs']
    J=np.asarray(rows[0]['jacobian']);contacts=args[6];ell=args[7]
    levers=[np.asarray(c[3],float) for c in contacts];direction=levers[1]-levers[0]
    assert np.linalg.norm(direction)>0
    direction/=np.linalg.norm(direction)
    twist=np.r_[-np.cross(direction,levers[0]),ell*direction]
    null_residual=float(np.linalg.norm(J@twist)/(np.linalg.norm(J)*np.linalg.norm(twist)))
    assert null_residual<1e-12
    singular=np.linalg.svd(J,compute_uv=False)
    scale=max(np.linalg.norm(args[0]),np.linalg.norm(args[1]),1e-30);tail=[]
    for i in range(70,80):
        item=rows[i];before=rows[i-1];M=np.asarray(item['mobility']);A=J@M@J.T
        tail.append(dict(inner_index=i,solver=item['health']['solver'],
            true_defect=audit['finite_re_recurrence'][i]['fixed_point_ratio'],
            relative_mobility_change=float(np.linalg.norm(M-np.asarray(before['mobility']))/np.linalg.norm(M)),
            free_velocity_change_over_outer_scale=float(np.linalg.norm(np.asarray(item['vfree'])-np.asarray(before['vfree']))/scale),
            mobility_condition=float(np.linalg.cond(M)),delassus_condition=float(np.linalg.cond(A))))
    result=dict(passed=True,utc=datetime.now(timezone.utc).isoformat(),read_only=True,
        sources={str(Path(__file__).resolve()):sha(__file__)},
        inputs={str(p):sha(p) for p in (final,final.with_name('completion.json'),capture,auditpath)},
        runtime=dict(python=sys.version,numpy=np.__version__),known_map_evaluations=82,
        half_relaxation_viability_failed=True,half_step_control_exact=True,
        analytical_two_point_null_twist=twist.tolist(),null_twist_relative_residual=null_residual,
        jacobian_singular_values=singular.tolist(),tail=tail,
        interpretation='Two distinct rigid-body contact points have an expected free twist about their connecting line, so rank5 Jacobian / singular6x6 Delassus is not itself an implementation defect. Tiny saved input changes coexist with much larger undamped output defects and route changes. This motivates testing original primary/fallback consistency at identical systems; it does not prove nonunique physical solutions or identify a uniquely correct route.',
        next_gate='Bounded same-input primary/fallback and rank-aware consistency diagnosis before another stabilization or any transport transfer.',
        numerical_contact_or_outer_calls=0,new_transport_steps=0,production_authorized=False,
        contact_law_changed=False,force_regularization_authorized=False)
    out=BASE/'branch_diagnosis_01';out.mkdir(exist_ok=False)
    p=out/'results.json';p.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    p.with_name('completion.json').write_text(json.dumps(dict(passed=True,results_sha256=sha(p)),sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(results_sha256=sha(p),null_twist_relative_residual=null_residual,
        maximum_tail_free_velocity_change_over_scale=max(x['free_velocity_change_over_outer_scale'] for x in tail),
        smallest_tail_true_defect=min(x['true_defect'] for x in tail),new_solver_calls=0)))
if __name__=='__main__':main()
