"""Compare independently rerun histories and open a bridge at identical actual gap.

Use after `make sensitivity`. The fixed-gap check changes the support reaction,
not water inventory or contact law. Forces are reported as positive attraction.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from .field import DX, Mesh, seed
from .refine import refined_geometry
from .run import connected, writecsv


def compare_histories(directory):
    rows=[]
    for name,folder in [('reference',''),('half_time_and_opening_step','time_refinement'),('half_mesh_spacing','space_refinement')]:
        summary=json.loads((directory/folder/'summary.json').read_text());end=summary['endpoints']
        root=end['root_opening']; outer=end['outer_opening']; sealed=end['sealed_opening']
        if abs(root['uptake_m2']-outer['outer_drain_m2'])>1e-18: raise RuntimeError('Unmatched extraction')
        fr,fo,fs=[-r['grain_capillary_N_m'] for r in (root,outer,sealed)]
        rows.append(dict(refinement=name,spacing_um=25 if folder=='space_refinement' else 50,
                         dt_s=summary['inputs']['duration']/summary['conditioning_steps'],
                         opening_increment_um=summary['inputs']['opening']*1e6/summary['opening_steps'],
                         extracted_area_mm2=root['uptake_m2']*1e6,
                         root_force_N_m=fr,outer_force_N_m=fo,sealed_force_N_m=fs,
                         reduction_percent=100*(1-fr/fo),max_mass_budget_error_m2=summary['max_water_residual_m2'],
                         max_force_error_N_m=summary['max_force_residual_N_m']))
    writecsv(directory/'refinement_summary.csv',rows)


def fixed_gap(directory, gap_um=677.5):
    labels,_=seed();g=gap_um*1e-6/DX
    rows=[]
    for scale,sub in [(1,''),(2,'space_refinement')]:
        run_dir=directory/sub
        target=json.loads((run_dir/'summary.json').read_text())['endpoints']
        for mode in ('root','outer','sealed'):
            # Allow minimal release to exclude large fine-grid maps: warm start
            # from the corresponding base-grid endpoint, then relax on chosen grid.
            raw=np.genfromtxt(directory/f'field_{mode}_opened.csv',names=True,delimiter=',')
            x=raw['phi'][raw['solid_id']==0];ls=labels
            if scale==2: ls,x=refined_geometry(labels,x)
            mesh=Mesh(ls,g);s=mesh.solve(x,target[mode+'_opening']['near_water_m2']/DX**2)
            if not connected(mesh,s): raise RuntimeError('Disconnected fixed-gap field')
            rows.append(dict(mode=mode,grid_um=50/scale,gap_um=gap_um,near_water_mm2=s.water*DX**2*1e6,
                        wet_perimeter_mm=s.wet_length*1000,attraction_N_m=-s.force,
                        independent_contour_N_m=-np.mean([mesh.contour(s,pad,1) for pad in (2,3,4,5)]),suction_Pa=-s.psi))
    writecsv(directory/'identical_grain_gap.csv',rows)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=Path('results'))
    p=ap.parse_args().output;compare_histories(p);fixed_gap(p)
