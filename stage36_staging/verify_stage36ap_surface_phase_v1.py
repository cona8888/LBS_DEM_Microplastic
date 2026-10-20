"""Bounded fixed-radius surface-density/grid-phase diagnostic; no fitting."""
import json, time, platform
from pathlib import Path
import numpy as np
import scipy
from scipy.linalg import cho_factor,cho_solve
from scipy.sparse.linalg import cg,LinearOperator
from diagnose_stage36ao_stokes_v1 import Mobility,ref,ROOT,sha

OUT=ROOT/'stage36_evaluations/stage36ap_surface_phase_20260910/audit_01'
PRIOR=ROOT/'stage36_evaluations/stage36ao_independent_stokes_20260910/diagnosis_01/results.json'

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg={'n':32,'radius_cells':4.,'mu':.1,'mean_ux':1e-4,'operator':'spectral',
         'marker_counts':[192,256,384],'diagonal_offsets_cells':[0.,.25,.5],
         'comparison':'fixed radius/kernel; Fibonacci surface generator shared across phases',
         'cg_rtol':1e-9,'max_iterations':1200,'wall_budget_s':240,
         'relative_slip_limit':1e-7,'gram_condition_limit':1e12,
         'marker_change_tolerance':.01,'phase_range_over_mean_tolerance':.01,
         'tolerance_role':'1% numerical sensitivity screening, not drag validation acceptance',
         'claim':'mechanism isolation only; no radius fitting, transient or moving-fibre qualification'}
    (OUT/'contract.json').write_text(json.dumps(cfg,indent=2))
    prior=json.loads(PRIOR.read_text())
    assert prior['status']=='diagnostics_pass'
    for p,h in prior['input_hashes'].items(): assert sha(Path(p))==h
    files=[Path(__file__),PRIOR,Path(__file__).with_name('diagnose_stage36ao_stokes_v1.py')]
    hashes={str(p):sha(p) for p in files}
    rows=[];begin=time.perf_counter();mob=Mobility(32,.1,'spectral')
    for count in cfg['marker_counts']:
        for offset in cfg['diagonal_offsets_cells']:
            if count==256 and offset==0:
                old=next(x for x in prior['operators'] if x['operator']=='spectral')
                rows.append({'marker_count':count,'offset':offset,'reused':True,'info':old['solver_info'],
                             'relative_slip':old['relative_marker_slip'],'drag_ratio':old['drag_ratio'],
                             'force':old['force'],'iterations':old['iterations'],'seconds':old['seconds']})
                continue
            points=ref.base.surface(4,count)+16+offset
            J=ref.base.interpolation_matrix(points,32);JT=J.T.tocsr()
            gram=(J@JT).toarray();condition=float(np.linalg.cond(gram))
            if not np.isfinite(condition) or condition>1e12: raise ValueError('Gram condition gate failed')
            factor=cho_factor(gram,lower=True);dim=count*3
            def action(v):return (J@mob.apply(JT@v.reshape(-1,3))).ravel()
            A=LinearOperator((dim,dim),matvec=action,dtype=float)
            M=LinearOperator((dim,dim),matvec=lambda v:cho_solve(factor,v.reshape(-1,3)).ravel(),dtype=float)
            rhs=np.zeros((count,3));rhs[:,0]=-1e-4
            iterations=[]
            def callback(v):
                iterations.append(1)
                if time.perf_counter()-begin>cfg['wall_budget_s']:raise TimeoutError('bounded diagnostic wall budget')
            t=time.perf_counter()
            lam,info=cg(A,rhs.ravel(),M=M,rtol=1e-9,atol=0,maxiter=1200,callback=callback)
            elapsed=time.perf_counter()-t
            u=mob.apply(JT@lam.reshape(-1,3));u[:,0]+=1e-4
            force=-lam.reshape(-1,3).sum(axis=0)
            row={'marker_count':count,'offset':offset,'info':int(info),'gram_condition':condition,
                 'relative_slip':float(np.max(np.abs(J@u))/1e-4),'force':force.tolist(),
                 'drag_ratio':float(force[0]/(6*np.pi*.1*4*1e-4*1.530329436009)),
                 'iterations':len(iterations),'seconds':elapsed,'reused':False,
                 'points_sha256':__import__('hashlib').sha256(points.tobytes()).hexdigest()}
            rows.append(row)
            (OUT/f'case_m{count}_p{int(offset*100):02d}.json').write_text(json.dumps(row,indent=2))
            print(json.dumps(row),flush=True)
    phase={}
    for count in cfg['marker_counts']:
        vals=[r['drag_ratio'] for r in rows if r['marker_count']==count]
        phase[str(count)]={'minimum':min(vals),'maximum':max(vals),'relative_range':float(np.ptp(vals)/np.mean(vals))}
    density={}
    for offset in cfg['diagonal_offsets_cells']:
        vals={r['marker_count']:r['drag_ratio'] for r in rows if r['offset']==offset}
        density[str(offset)]={'192_to_256_relative':abs(vals[256]/vals[192]-1),
                              '256_to_384_relative':abs(vals[384]/vals[256]-1)}
    checks={'all_solves_converged':all(r['info']==0 for r in rows),
            'all_slips_pass':all(r['relative_slip']<1e-7 for r in rows),
            'input_hashes_unchanged':all(sha(p)==hashes[str(p)] for p in files)}
    screens={'phase_below_1pct':all(r['relative_range']<=.01 for r in phase.values()),
             'finest_marker_change_below_1pct':all(r['256_to_384_relative']<=.01 for r in density.values())}
    result={'status':'diagnostic_completed' if all(checks.values()) else 'diagnostic_numerical_failure',
            'checks':checks,'sensitivity_screens':screens,'phase':phase,'surface_density':density,'rows':rows,
            'input_hashes':hashes,'contract_sha256':sha(OUT/'contract.json'),
            'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,
            'total_elapsed_s':time.perf_counter()-begin,'production_promoted':False,'sharp_sphere_validated':False}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['status','checks','sensitivity_screens','phase','surface_density','total_elapsed_s']},indent=2))
    if not all(checks.values()): raise SystemExit(1)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        if OUT.exists() and not (OUT/'failure.json').exists():
            (OUT/'failure.json').write_text(json.dumps({'error':str(exc),'type':type(exc).__name__},indent=2))
        raise
