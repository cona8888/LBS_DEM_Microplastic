"""Evaluate gates without changing tolerances in response to outcomes."""
import json,csv,hashlib
from pathlib import Path
from .validate import OUT,ROOT,dump,loadcsv,writecsv,check_frozen

def main():
    check_frozen();a=json.loads((OUT/'paired_s2_n18.json').read_text());b=json.loads((OUT/'paired_s2_n36.json').read_text())
    f=json.loads((OUT/'field_summary.json').read_text());width=json.loads((OUT/'width_summary.json').read_text());rel=json.loads((OUT/'hydraulic_reequilibration.json').read_text());h=json.loads((OUT/'holdout_summary.json').read_text())
    R=lambda case,mode:next(r for r in case['fixed_gap'] if r['mode']==mode)
    force_dt=max(abs(R(b,m)['force_N_m']/R(a,m)['force_N_m']-1)*100 for m in ('root','outer','sealed'))
    uptake_dt=abs(R(b,'root')['uptake_m2']/R(a,'root')['uptake_m2']-1)*100
    radial=loadcsv(OUT/'radial_steady.csv');trans=loadcsv(OUT/'radial_transient.csv')
    gates=[]
    def g(name,metric,threshold,unit,evidence,status=None):
        gates.append(dict(test=name,value=metric,threshold=threshold,unit=unit,status=status or ('PASS' if metric<=threshold else 'FAIL'),evidence_level=evidence))
    g('Water ledger, full coupled runs',max(a['max_water_residual_m2'],b['max_water_residual_m2']),1e-16,'m2','numerical verification')
    g('Coupled force residual',max(a['max_force_residual_N_m'],b['max_force_residual_N_m']),1.1e-7,'N/m','numerical verification')
    g('Matched cumulative extraction',a['extracted_difference_m2'],1e-16,'m2','numerical control')
    g('Energy/virtual-work force',f['max_virtual_work_error_pct'],.1,'percent','numerical verification')
    g('Stress contour vs energy force',f['max_contour_discrepancy_pct'],2.5,'percent','independent discretisation')
    g('Force change on timestep halving',force_dt,1.,'percent','numerical refinement')
    g('Extraction change on timestep halving',uptake_dt,1.,'percent','numerical refinement')
    g('Laplace check, original W at 6.25um grid',next(r for r in width if r['scale']==8 and r['interface_width_um']==125)['root_laplace_error_pct'],5.,'percent','sharp-interface consistency diagnostic')
    g('Laplace check, half W at 6.25um grid',max(next(r for r in width if r['scale']==8 and r['interface_width_um']==62.5)[key] for key in ('root_laplace_error_pct','outer_laplace_error_pct')),5.,'percent','sharp-interface consistency diagnostic')
    g('Radial Richards steady Q at 128 cells',float(radial[-1]['flow_error_pct']),.1,'percent','analytical verification; separate reference')
    g('Radial Richards transient budget',max(abs(float(r['max_mass_residual_m2'])) for r in trans),1e-16,'m2','numerical verification; separate reference')
    g('Saturated cup geometry holdout',abs(h['saturated_large']['error_pct']),10.,'percent','component physical validation')
    for r in h['tree_holdouts']:g('Tree holdout: '+r['species'],abs(r['error_pct']),20.,'percent','chronological component validation')
    g('Whole-model independent force/volume/pore field',None,None,'not applicable','physical validation','NOT RUN')
    g('Drainage-path effect size qualified',None,None,'not applicable','model numerical uncertainty','INCONCLUSIVE')
    writecsv(OUT/'gates.csv',gates)
    summary=dict(gates=gates,fixed_gap_contrast_200s_pct=a['fixed_gap_contrast_pct'],fixed_gap_contrast_100s_pct=b['fixed_gap_contrast_pct'],force_time_change_pct=force_dt,uptake_time_change_pct=uptake_dt,after_hydraulic_redistribution_contrast_pct=rel['post_relaxation_force_contrast_pct'],width_study=width,verdict='Component verification and narrow saturated analogue agreement; full root-soil-water model NOT VALIDATED. Original 1.03 percent contrast is not an accepted physical effect size.',no_recalibration=True)
    dump('summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
