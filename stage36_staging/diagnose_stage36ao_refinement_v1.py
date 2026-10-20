"""Coarser independent Stokes ladder; reuses hash-bound N32 evidence."""
import json,time,hashlib
from pathlib import Path
import numpy as np
from scipy.linalg import cho_factor,cho_solve
from scipy.sparse.linalg import LinearOperator,cg
from diagnose_stage36ao_stokes_v1 import Mobility,ref,ROOT,sha

OUT=ROOT/'stage36_evaluations/stage36ao_independent_stokes_20260910/refinement_01'
PRIOR=OUT.parent/'diagnosis_01/results.json'

def main():
    OUT.mkdir(exist_ok=False)
    contract={'new_grids':[16,24],'reused_grid':32,'a_over_L':.125,'mu':.1,'U':1e-4,
              'marker_count_rule':'16*(N/8)^2','cg_rtol':1e-9,'maxiter':1200,
              'relative_slip_limit':1e-7,'hypothesis':'excess drag decreases as radius in cells increases',
              'claim':'exploratory lower-resolution trend only; no continuum extrapolation, fitting or production promotion'}
    (OUT/'contract.json').write_text(json.dumps(contract,indent=2))
    prior=json.loads(PRIOR.read_text());assert prior['status']=='diagnostics_pass'
    files=[Path(__file__),PRIOR,Path(__file__).with_name('diagnose_stage36ao_stokes_v1.py')]
    hashes={str(p):sha(p) for p in files}
    for path,digest in prior['input_hashes'].items(): assert sha(Path(path))==digest
    rows=[]
    for n in [16,24]:
        radius=n/8;count=int(16*radius**2)
        J=ref.base.interpolation_matrix(ref.base.surface(radius,count)+n/2,n)
        JT=J.T.tocsr();factor=cho_factor((J@JT).toarray(),lower=True)
        rhs=np.zeros((count,3));rhs[:,0]=-1e-4;dim=count*3
        for kind in ['spectral','centered_fd']:
            mob=Mobility(n,.1,kind)
            def action(v):return (J@mob.apply(JT@v.reshape(-1,3))).ravel()
            A=LinearOperator((dim,dim),matvec=action,dtype=float)
            M=LinearOperator((dim,dim),matvec=lambda v:cho_solve(factor,v.reshape(-1,3)).ravel(),dtype=float)
            iterations=[];t=time.perf_counter()
            lam,info=cg(A,rhs.ravel(),M=M,rtol=1e-9,atol=0,maxiter=1200,callback=lambda _:iterations.append(1))
            elapsed=time.perf_counter()-t
            u=mob.apply(JT@lam.reshape(-1,3));u[:,0]+=1e-4
            slip=float(np.max(np.abs(J@u))/1e-4)
            force=-lam.reshape(-1,3).sum(axis=0)
            rows.append({'n':n,'radius_cells':radius,'marker_count':count,'operator':kind,
                         'info':info,'relative_slip':slip,'iterations':len(iterations),'seconds':elapsed,
                         'drag_ratio':float(force[0]/(6*np.pi*.1*radius*1e-4*1.530329436009))})
    for row in prior['operators']:
        rows.append({'n':32,'radius_cells':4,'marker_count':256,'operator':row['operator'],
                     'info':row['solver_info'],'relative_slip':row['relative_marker_slip'],
                     'iterations':row['iterations'],'seconds':row['seconds'],'drag_ratio':row['drag_ratio'],'reused':True})
    checks={'all_solves':all(r['info']==0 and r['relative_slip']<1e-7 for r in rows),
            'hashes_unchanged':all(sha(p)==hashes[str(p)] for p in files)}
    trends={}
    for kind in ['spectral','centered_fd']:
        selected=sorted([r for r in rows if r['operator']==kind],key=lambda r:r['n'])
        values=[r['drag_ratio'] for r in selected]
        trends[kind]={'decreasing_excess':all(values[i]>values[i+1]>1 for i in range(2)),
                      'values':values}
    result={'status':'diagnostic_pass' if all(checks.values()) else 'diagnostic_failed',
            'checks':checks,'rows':rows,'hypothesis_results':trends,'input_hashes':hashes,
            'contract_sha256':sha(OUT/'contract.json'),'sharp_sphere_qualified':False}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if not all(checks.values()):raise SystemExit(1)

if __name__=='__main__':main()
