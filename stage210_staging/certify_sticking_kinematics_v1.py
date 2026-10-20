"""Exact-rational incompatibility bound for the all-sticking contact mode.

This certifies only that mode, not absence of every frictional solution. Uses
the exact saved binary64 Jacobian and original gap/dt targets; changes no gap.
"""
from pathlib import Path
from fractions import Fraction as F
import os, traceback
import numpy as np
from scipy.optimize import linprog
import authenticate_failed_system_v1 as source
job, api, ROOT = source.job, source.api, source.ROOT
OUT = ROOT/'stage210_evaluations/three_contact_failure_20261001/sticking_kinematics_01'


def exact_nullspace(matrix):
    rows = [[F.from_float(float(x)) for x in row] for row in matrix]
    height, width = len(rows), len(rows[0]); pivots = []; r = 0
    for c in range(width):
        p = next((p for p in range(r, height) if rows[p][c]), None)
        if p is None: continue
        rows[r], rows[p] = rows[p], rows[r]; pivot = rows[r][c]
        rows[r] = [x/pivot for x in rows[r]]
        for i in range(height):
            if i != r and rows[i][c]:
                value = rows[i][c]; rows[i] = [a-value*b for a,b in zip(rows[i],rows[r])]
        pivots.append(c); r += 1
        if r == height: break
    free = [c for c in range(width) if c not in pivots]; basis = []
    for c in free:
        vector = [F(0)]*width; vector[c] = F(1)
        for i, p in enumerate(pivots): vector[p] = -rows[i][c]
        basis.append(vector)
    return free, basis


def run():
    d = api.read(job.DESIGN); job.verify(d); fp = source.OUT/'failed_systems.json'; pp = source.OUT/'results.json'
    proof = api.read(pp)
    api.require(api.read(pp.parent/'completion.json')['results_sha256']==api.sha(pp) and api.sha(fp)==proof['failed_systems_sha256'], 'authenticated inputs')
    inputs = {str(p):api.sha(p) for p in (Path(__file__), source.WORK, job.DESIGN, fp, pp)}
    OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0))
    reports=[]
    try:
        for index,item in enumerate(api.read(fp)['failed_inner_systems'][:3]):
            s=item['system'];api.require(api.digest(s)==item['system_sha256'],'held matrices unchanged')
            J=np.asarray(s['jacobian'],float);v=np.asarray(s['vfree'],float);g=np.asarray(s['gaps_m'],float)
            target=np.zeros(9);target[::3]=-g/s['dt_s'];scale=max(np.max(np.abs(target)),1e-30)
            # Component-wise minimax residual; tangential Euclidean residual
            # is at least its largest component, so this is a lower bound.
            fit=linprog(np.r_[np.zeros(6),1.],A_ub=np.vstack([np.column_stack([J,-np.ones(9)]),np.column_stack([-J,-np.ones(9)])]),
                        b_ub=np.r_[target/scale,-target/scale],bounds=[(None,None)]*6+[(0,None)],method='highs')
            api.require(fit.success,'diagnostic minimax LP solved')
            dual=fit.ineqlin.marginals[:9]-fit.ineqlin.marginals[9:]
            free,basis=exact_nullspace(J.T)
            coeff=[F.from_float(float(dual[c])) for c in free]
            witness=[sum((coeff[k]*basis[k][j] for k in range(len(basis))),F(0)) for j in range(9)]
            exact_J=[[F.from_float(float(x)) for x in row] for row in J]
            api.require(all(sum((witness[k]*exact_J[k][j] for k in range(9)),F(0))==0 for j in range(6)),'exact left-nullspace certificate')
            exact_target=[F.from_float(float(x)) for x in target]
            numerator=abs(sum((a*b for a,b in zip(witness,exact_target)),F(0)));denominator=sum((abs(x) for x in witness),F(0))
            api.require(denominator>0,'nonzero witness')
            lower=numerator/denominator;free_scale=max(np.linalg.norm(v),1e-15)
            relative=float(lower)/free_scale
            reports.append(dict(index=index,system_sha256=item['system_sha256'],original_gaps_m=g.tolist(),dt_s=s['dt_s'],
                exact_saved_jacobian_rank=6,exact_left_nullspace_width=len(basis),left_nullspace_witness=[str(x) for x in witness],
                original_gap_velocity_targets=target.tolist(),exact_residual_lower_bound_m_s=str(lower),relative_residual_lower_bound=relative,
                original_tolerance=s['tolerance'],all_sticking_exact_mode_incompatible_with_original_tolerance=relative>s['tolerance'],
                floating_lp_bound=fit.fun*scale/free_scale,claim='All-sticking mode only; no global no-solution claim.'))
            print('STICKING_BOUND',index,relative,'original tolerance',s['tolerance'],flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,exact_rational_nullspace_verified=True,reports=reports,
                    claim='Exact all-sticking kinematic residual lower bound for original saved inputs. Sliding/open modes and arithmetic audit still require diagnosis; this is not a global infeasibility proof or a relaxed gate.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
