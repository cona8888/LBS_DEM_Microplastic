"""Exact-rational kinematic bounds for each two-stick/one-slip mode only."""
from fractions import Fraction as F
from pathlib import Path
import os, traceback
import numpy as np
from scipy.optimize import linprog
import authenticate_failed_system_v1 as source
import certify_sticking_kinematics_v1 as algebra
job,api,ROOT=source.job,source.api,source.ROOT
OUT=ROOT/'stage210_evaluations/three_contact_failure_20261001/two_sticking_kinematics_01'


def run():
    d=api.read(job.DESIGN);job.verify(d);fp=source.OUT/'failed_systems.json';pp=source.OUT/'results.json';proof=api.read(pp)
    api.require(api.read(pp.parent/'completion.json')['results_sha256']==api.sha(pp) and api.sha(fp)==proof['failed_systems_sha256'],'authenticated inputs')
    inputs={str(p):api.sha(p) for p in (Path(__file__),Path(algebra.__file__),source.WORK,job.DESIGN,fp,pp)}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0))
    reports=[]
    try:
        for index,item in enumerate(api.read(fp)['failed_inner_systems'][:3]):
            s=item['system'];api.require(api.digest(s)==item['system_sha256'],'exact original system')
            J=np.asarray(s['jacobian'],float);g=np.asarray(s['gaps_m'],float);vs=max(np.linalg.norm(s['vfree']),1e-15)
            for sliding in range(3):
                rows=[3*k+j for k in range(3) for j in range(3) if j==0 or k!=sliding]
                C=J[rows];target=np.array([-g[r//3]/s['dt_s'] if r%3==0 else 0. for r in rows]);scale=max(np.max(np.abs(target)),1e-30)
                fit=linprog(np.r_[np.zeros(6),1.],A_ub=np.vstack([np.column_stack([C,-np.ones(7)]),np.column_stack([-C,-np.ones(7)])]),
                            b_ub=np.r_[target/scale,-target/scale],bounds=[(None,None)]*6+[(0,None)],method='highs')
                api.require(fit.success,'bounded-mode minimax calculation')
                dual=fit.ineqlin.marginals[:7]-fit.ineqlin.marginals[7:];free,basis=algebra.exact_nullspace(C.T)
                coefficients=[F.from_float(float(dual[c])) for c in free]
                w=[sum((coefficients[k]*basis[k][j] for k in range(len(basis))),F(0)) for j in range(7)]
                cc=[[F.from_float(float(x)) for x in r] for r in C]
                api.require(all(sum((w[k]*cc[k][j] for k in range(7)),F(0))==0 for j in range(6)),'exact mode nullspace certificate')
                denominator=sum((abs(x) for x in w),F(0));api.require(denominator>0,'nonzero mode witness')
                lower=abs(sum((w[k]*F.from_float(float(target[k])) for k in range(7)),F(0)))/denominator
                reports.append(dict(index=index,system_sha256=item['system_sha256'],sliding_contact=sliding,contact_rows=rows,
                    original_gap_velocity_targets=target.tolist(),left_nullspace_witness=[str(x) for x in w],exact_residual_lower_bound_m_s=str(lower),
                    relative_residual_lower_bound=float(lower)/vs,original_tolerance=s['tolerance'],mode_incompatible_with_original_tolerance=float(lower)/vs>s['tolerance']))
                print('TWO_STICK_BOUND',index,sliding,float(lower)/vs,flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,reports=reports,exact_rational_nullspace_verified=True,
                    claim='Original two-sticking kinematic modes only. No general three-contact infeasibility proof, changed gap or relaxed gate.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
