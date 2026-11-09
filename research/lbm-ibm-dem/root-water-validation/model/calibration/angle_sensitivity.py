"""Conditional mechanical sensitivity. The two inventories are fixed to the
respective 25-um calibrated reference endpoints, not re-simulated drying paths.
Unmeasured root angles are numerical scenarios, not a probability distribution.
"""
from scipy.optimize import brentq
import csv
from .fit import HERE
from .probe_wetting import apparent,state
from applications.rhizofield.field import DX,Mesh,seed
from applications.rhizofield.run import connected,writecsv
from applications.rhizofield.refine import refined_geometry

def main():
    out=HERE/'results';d=list(csv.DictReader((out/'fixed_gap_glass_25um.csv').open()));ls,x=seed();ls,x=refined_geometry(ls,x);rows=[]
    for target in [31.,39.]:
        def f(a):return apparent(*state(a,2))[0]-target
        th=brentq(f,50,60,xtol=.0001)
        for root in [40.,45.,50.,55.,60.,70.,80.,90.,100.6]:
            F={};failures=[];ms=Mesh(ls,677.5e-6/DX,grain_deg=th,root_deg=root)
            for mode in ['root','outer']:
                A=float(next(r['water_mm2'] for r in d if r['mode']==mode))*1e-6
                try:
                    s=ms.solve(x,A/DX**2)
                    if not connected(ms,s):raise RuntimeError('no connected bridge')
                    F[mode]=-s.force
                except RuntimeError as ex:
                    failures.append(f'{mode}: {ex}');F[mode]=None
            rows.append(dict(target_glass_apparent_deg_at_reference_root_input=target,grain_input_deg=th,root_input_deg=root,actual_gap_um=677.5,root_attraction_N_m=F['root'],outer_attraction_N_m=F['outer'],status='; '.join(failures) or 'connected',root_minus_outer_percent=100*(F['root']/F['outer']-1) if None not in F.values() else None))
    writecsv(out/'angle_sensitivity.csv',rows)
if __name__=='__main__':main()
