"""Matched total water after re-opening the hydraulic link: a mechanism control.
Solve psi_near(A) = psi_outer(total-A) from each prior field independently.
The driving flux is exactly the existing G*(psi_outer-psi_near); a zero of this
residual is its steady state for any G>0, not a claim of measured relaxation time.
"""
import json
import numpy as np
from scipy.optimize import brentq
from .validate import OUT,PROFILE,geometry,inspect,dump,arc
from applications.rhizofield.field import Mesh,DX
from applications.rhizofield.run import writecsv,Params

def main():
    from .validate import check_frozen
    check_frozen()
    sc=2;theta=json.loads(PROFILE.read_text())['grain_wall_inputs_deg']['25um'];p=Params(grain_deg=theta)
    rows=[]
    dat=np.load(OUT/'paired_s2_n18_root.npz')
    probe=Mesh(dat['labels'],13.55,grain_deg=theta)
    ps=probe.solve(dat['phi'],float(dat['near'])/DX**2)
    trims=[]
    for trim in (.5,1.,1.5,2.,2.5,3.):
        a=arc(probe,ps,trim)
        trims.append(dict(trim_m=trim*DX,pressure_Pa=-ps.psi,relative_error_pct=100*(a['laplace_suction_Pa']/(-ps.psi)-1),**a))
    writecsv(OUT/'curvature_trim_check.csv',trims)
    for mode in ('root','outer'):
        dat=np.load(OUT/f'paired_s2_n18_{mode}.npz');labels=dat['labels'];guess=dat['phi'];total=float(dat['near']+dat['far'])
        m=Mesh(labels,13.55,grain_deg=theta)
        # Initial far-pressure reference from the actual paired run (fine geometry,
        # same coarse support anchor). Get it from the first history row, not a new fit.
        import csv
        history=list(csv.DictReader((OUT/'paired_s2_n18.csv').open()))
        ref=next(r for r in history if r['mode']==mode);psi0=-float(ref['outer_suction_Pa'])
        calls=[]
        def fun(area_star):
            s=m.solve(guess,area_star)
            pf=psi0+((total-area_star*DX**2)-p.outer_initial)/p.storage
            calls.append((area_star,s,pf));return s.psi-pf
        A0=float(dat['near'])/DX**2
        ends=[float(np.load(OUT/f'paired_s2_n18_{name}.npz')['near'])/DX**2 for name in ('root','outer')]
        a=brentq(fun,min(ends),max(ends),xtol=1e-8);fun(a);_,s,pf=calls[-1]
        rows.append(dict(mode=mode,total_water_m2=total,initial_near_m2=float(dat['near']),equilibrium_near_m2=a*DX**2,equilibrium_outer_m2=total-a*DX**2,pressure_mismatch_Pa=s.psi-pf,solve_calls=len(calls),**inspect(m,s)))
    writecsv(OUT/'hydraulic_reequilibration.csv',rows)
    dump('hydraulic_reequilibration.json',dict(rows=rows,post_relaxation_force_contrast_pct=100*(rows[0]['force_N_m']/rows[1]['force_N_m']-1),same_total_water_error_m2=abs(rows[0]['total_water_m2']-rows[1]['total_water_m2']),scope='Steady common-pressure solve with positive unchanged G; no elapsed physical time inferred'))
    print(rows,flush=True)
if __name__=='__main__':main()
