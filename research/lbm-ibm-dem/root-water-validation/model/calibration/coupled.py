"""Native paired benchmarks with measured-target glass wetting; no fit to force.
Cup transfer is a separate sensitivity assumption, not a validation.
"""
import json,argparse
import numpy as np
from .fit import HERE
from applications.rhizofield.run import Params,paired,connected,writecsv
from applications.rhizofield.field import Mesh,seed,DX
from applications.rhizofield.refine import refined_geometry

def run(which,scale):
    out=HERE/'results';pr=json.loads((out/'profiles.json').read_text());grid=50//scale;theta=pr['grain_wall_inputs_deg'][f'{grid}um']
    if which=='glass':p=Params(grain_deg=theta);steps,nopen=18,9
    elif which=='cup_transfer':p=Params(grain_deg=theta,membrane=pr['ceramic']['lateral']['Lp_apparent_m_Pa_s'],duration=600.);steps,nopen=12,6
    elif which in ('grapevine_not_soaked','grapevine_soaked_24h'):
        from .tissue import profiles
        lp=profiles()[which.removeprefix('grapevine_')]['Lp_m_Pa_s']
        # Fixed -20 kPa xylem relative to gas; initial soil-side pressure is
        # solved. Only the tissue coefficient changes between these two runs.
        p=Params(grain_deg=theta,membrane=lp,xylem=-20000.,duration=3600.);steps,nopen=18,9
    else:raise ValueError(which)
    rows,maps=paired(steps,nopen,p,scale);name=f'{which}_{grid}um';writecsv(out/f'history_{name}.csv',rows)
    labels,x=seed()
    if scale==2:labels,_=refined_geometry(labels,x)
    fs={};data=[]
    for mode,stage,a in maps:
        if stage!='opened':continue
        last=[r for r in rows if r['mode']==mode][-1];xm=a[a[:,2]==0,3];m=Mesh(labels,677.5e-6/DX,grain_deg=theta,root_deg=p.root_deg);s=m.solve(xm,last['near_water_m2']/DX**2)
        if not connected(m,s):raise RuntimeError('Disconnected fixed-gap state')
        fs[mode]=-s.force
        data.append(dict(mode=mode,fixed_gap_um=677.5,attraction_N_m=-s.force,independent_contour_N_m=-np.mean([m.contour(s,k) for k in [2,3,4,5]]),root_wet_length_mm=s.wet_length*1000,suction_Pa=-s.psi,water_mm2=s.water*DX**2*1e6))
    rr=[r for r in rows if r['mode']=='root'];oo=[r for r in rows if r['mode']=='outer'];ep=rr[-1];mm=max(abs(r['uptake_m2']-o['outer_drain_m2']) for r,o in zip(rr,oo));assert mm<1e-16
    s=dict(grid_um=grid,case=which,grain_input_deg=theta,membrane_m_Pa_s=p.membrane,duration_s=p.duration,extracted_area_mm2=ep['uptake_m2']*1e6,worst_matched_removal_m2=mm,max_water_residual_m2=max(abs(r['net_water_residual_m2']) for r in rows),max_native_force_residual_N_m=max(abs(r['force_residual_N_m']) for r in rows),fixed_gap_root_N_m=fs['root'],fixed_gap_outer_N_m=fs['outer'],fixed_gap_relative_change_pct=100*(fs['root']/fs['outer']-1),fixed_gap_sealed_N_m=fs['sealed']);writecsv(out/f'fixed_gap_{name}.csv',data);(out/f'paired_{name}.json').write_text(json.dumps(s,indent=2)+'\n');print(s,flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--case',choices=['glass','cup_transfer','grapevine_not_soaked','grapevine_soaked_24h'],default='glass');ap.add_argument('--scale',type=int,choices=[1,2],default=1);args=ap.parse_args();run(args.case,args.scale)
