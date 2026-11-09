"""Closed-loop 2-D capillary field, wet membrane, hydraulic storage and native grain.
Run from repository root: make run. All exchanged quantities are per metre of depth.
"""
from __future__ import annotations
import argparse,csv,json,subprocess
from dataclasses import dataclass,asdict
from pathlib import Path
from itertools import groupby
import numpy as np
from .field import Mesh,State,seed,DX,P0,REFERENCE_GAP

ROOT=Path(__file__).resolve().parents[2]
@dataclass(frozen=True)
class Params:
    stiffness:float=2500.       # N/m², support spring per depth
    membrane:float=3e-10        # m/(Pa s), illustrative
    xylem:float=-110.           # Pa relative to gas
    link:float=1e-13            # m²/(Pa s), outer reservoir -> root zone
    storage:float=2e-9          # m²/Pa, far-pore compliance
    outer_initial:float=2e-6    # m² of water per m depth
    duration:float=3600.        # s, drying only
    opening:float=75.e-6        # m, then sealed incremental opening
    grain_deg:float=60.         # numerical wall-energy angle, through liquid
    root_deg:float=50.          # not calibrated from grain measurements
    def __post_init__(self):
        p=asdict(self)
        if not all(np.isfinite(list(p.values()))) or min(self.stiffness,self.storage,self.outer_initial,self.duration)<=0 or min(self.opening,self.link,self.membrane)<0:
            raise ValueError('Invalid parameter set')
        if not all(0 < z < 180 for z in (self.grain_deg,self.root_deg)):
            raise ValueError('Angles must be inside (0,180) degrees')

def native(gap,anchor,force,k):
    args=[str(ROOT/'bin/rhizoprobe'),*(format(z,'.17g') for z in [gap,anchor,force,k])]
    out=subprocess.run(args,check=True,capture_output=True,text=True).stdout.split()
    return float(out[0]),float(out[1]),int(out[2])

def water_exchange(near,far,link_rate,root_rate,outer_rate,dt):
    """Conservative finite-volume transfers, SI. Positive link flux is into near pore."""
    if not np.isfinite([near,far,link_rate,root_rate,outer_rate,dt]).all() or min(root_rate,outer_rate)<0 or dt<=0:
        raise ValueError('Invalid water exchange')
    near1=near+dt*(link_rate-root_rate); far1=far-dt*(link_rate+outer_rate)
    if min(near1,far1)<=0: raise ValueError('An inventory exhausted; reduce the step or implement dry-out')
    return near1,far1

def uptake_rate(conductivity, measure, outside_Pa, inside_Pa):
    """Positive uptake. Use m² for total m³/s, or m for rate/depth m²/s.

    Conductivity must correspond to the SAME surface measure and pressure taps.
    """
    if not np.isfinite([conductivity,measure,outside_Pa,inside_Pa]).all() or min(conductivity,measure)<0:
        raise ValueError('Invalid hydraulic input')
    return conductivity*measure*max(outside_Pa-inside_Pa,0.)

def membrane_flux(s,p):
    return uptake_rate(p.membrane,s.wet_length,s.psi,p.xylem)

def connected(m,s):
    from scipy.ndimage import label, binary_dilation, generate_binary_structure
    mask=m.map(s.phi)>0; struct=generate_binary_structure(2,1); ids,_=label(mask,struct)
    a=set(ids[binary_dilation(m.labels==2,struct)]); b=set(ids[binary_dilation(m.labels==1,struct)])
    return bool((a&b)-{0})

def equilibrium(labels, state, area, gap, anchor, p):
    x=state.phi
    for it in range(14):
        m=Mesh(labels,gap/DX,grain_deg=p.grain_deg,root_deg=p.root_deg); s=m.solve(x,area/DX**2); x=s.phi
        if not connected(m,s): raise RuntimeError('Lost the connected liquid branch: stop; no physical rupture law is inferred')
        residual=s.force+p.stiffness*(anchor-gap)
        # Force residual is absolute N/m; never accept a small displacement alone.
        gn,_,_=native(gap,anchor,s.force,p.stiffness)
        if abs(residual)<1e-7 and abs(gn-gap)<1e-10: return m,s,gap,it+1
        gap=gn
    raise RuntimeError('Coupled field/grain equilibrium failed')

def paired(steps=18,nopen=9,p=None,grid_scale=1):
    if not isinstance(steps,int) or steps<1 or not isinstance(nopen,int) or nopen<1: raise ValueError('Positive step counts required')
    p=p or Params(); labels,guess=seed(); m=Mesh(labels,grain_deg=p.grain_deg,root_deg=p.root_deg); start=m.solve(guess,m.water(guess)); gap0=REFERENCE_GAP*DX
    near0=start.water*DX**2; anchor0=gap0-start.force/p.stiffness; dt=p.duration/steps
    if grid_scale not in (1,2): raise ValueError('Allowed grid scales: 1 or 2')
    if grid_scale==2:
        from .refine import refined_geometry
        labels,x=refined_geometry(labels,start.phi); m=Mesh(labels,grain_deg=p.grain_deg,root_deg=p.root_deg)
        start=m.solve(x,near0/DX**2); m,start,gap0,_=equilibrium(labels,start,near0,gap0,anchor0,p)
    # Identical overall initial inventory and physical spring anchor on both grids.
    # Each reservoir starts at the equilibrium pressure of its own mesh.
    rows=[]; maps=[]; extraction=[]
    for mode in ['root','outer','sealed']:
        s=start; mesh=m; gap=gap0; near=near0; far=p.outer_initial; rsum=osum=0.; anchor=anchor0
        def record(stage,t,u,nit,q12=0.,qr=0.,qo=0.):
            contour=np.array([mesh.contour(s,pad,1) for pad in [2,3,4,5]])
            root_contour=np.mean([mesh.contour(s,pad,2) for pad in [2,3,4,5]])
            budget=(s.water*DX**2-near0)+(far-p.outer_initial)+rsum+osum
            rows.append(dict(mode=mode,stage=stage,time_s=t,opening_m=u,grain_gap_m=gap,support_gap_m=anchor,
                     suction_Pa=-s.psi,outer_suction_Pa=-(start.psi+(far-p.outer_initial)/p.storage),
                     near_water_m2=s.water*DX**2,outer_water_m2=far,uptake_m2=rsum,outer_drain_m2=osum,
                     net_water_residual_m2=budget,wet_perimeter_m=s.wet_length,grain_capillary_N_m=s.force,
                     grain_contour_N_m=float(contour.mean()),root_contour_N_m=float(root_contour),contour_range_N_m=float(np.ptp(contour)),
                     force_residual_N_m=s.force+p.stiffness*(anchor-gap),mu_residual=s.residual,iterations=nit,
                     preceding_Q_link_m2_s=q12,preceding_Q_root_m2_s=qr,preceding_Q_outer_m2_s=qo))
            if abs(budget)>1.e-16 or abs(rows[-1]['force_residual_N_m'])>1.1e-7: raise RuntimeError('Water/force gate failed')
        def snapshot(stage):
            phase=mesh.map(s.phi); y,x=np.indices(labels.shape)
            maps.append((mode,stage,np.column_stack((mesh.cx[x.ravel()]*DX,((y.ravel()+.5)*mesh.hy-.5)*DX,labels.ravel(),phase.ravel()))))
        record('conditioning',0.,0.,1)
        for j in range(steps):
            pf=start.psi+(far-p.outer_initial)/p.storage
            q12=p.link*(pf-s.psi); qr=membrane_flux(s,p) if mode=='root' else 0.
            if mode=='root': extraction.append(qr)
            qo=extraction[j] if mode=='outer' else 0.
            near,far=water_exchange(near,far,q12,qr,qo,dt); rsum+=qr*dt; osum+=qo*dt
            mesh,s,gap,nit=equilibrium(labels,s,near,gap,anchor,p)
            record('conditioning',(j+1)*dt,0.,nit,q12,qr,qo)
        snapshot('conditioned')
        # Opening is a fast, drained-within-patch but sealed-between-compartments limit.
        # No duration is attached to the increasing mechanical displacement.
        for j in range(1,nopen+1):
            u=p.opening*j/nopen; anchor=anchor0+u
            mesh,s,gap,nit=equilibrium(labels,s,near,gap,anchor,p)
            record('opening',p.duration,u,nit)
        snapshot('opened')
    return rows,maps

def writecsv(path,rows):
    with open(path,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n'); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--output',type=Path,default=ROOT/'results'); ap.add_argument('--steps',type=int,default=18); ap.add_argument('--nopen',type=int,default=9); ap.add_argument('--grid-scale',type=int,choices=[1,2],default=1); args=ap.parse_args()
    out=args.output; out.mkdir(exist_ok=True,parents=True); rows,maps=paired(args.steps,args.nopen,grid_scale=args.grid_scale)
    writecsv(out/'history.csv',rows)
    for mode,stage,field in maps:
        np.savetxt(out/f'field_{mode}_{stage}.csv',field,delimiter=',',header='x_m,y_m,solid_id,phi',comments='',fmt=['%.12g','%.12g','%d','%.9g'])
    summary={'inputs':asdict(Params()),'conditioning_steps':args.steps,'opening_steps':args.nopen,'limits':{'base_spacing_um':DX*1e6/args.grid_scale,'out_of_plane_depth_m':1,'is_measured':False},'max_water_residual_m2':max(abs(r['net_water_residual_m2']) for r in rows),'max_force_residual_N_m':max(abs(r['force_residual_N_m']) for r in rows),'endpoints':{}}
    for (mode,stage),group in groupby(rows,lambda r:(r['mode'],r['stage'])):
        summary['endpoints'][mode+'_'+stage]=list(group)[-1]
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print('Wrote',len(rows),'samples;',summary['max_water_residual_m2'],'m² max water residual.')
if __name__=='__main__':main()
