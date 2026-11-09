"""Matched-state 50/25 um spatial check plus temporal-step sensitivity.
Recreate disk masks from identical physical radii. Hold phase thickness, pore
extent, physical gap and total near-pore water fixed. No refinement of time
or of interface thickness is implied by this comparison.
"""
from pathlib import Path
import argparse,csv
import numpy as np
from scipy.ndimage import distance_transform_edt,map_coordinates
from .field import Mesh,seed,DX
from .run import connected,writecsv

def refined_geometry(labels,coarse):
    yy,xx=np.indices((134,188)); x=(xx+.5)*.5-.5; y=(yy+.5)*.5-.5
    solid=np.zeros(x.shape,int)
    for cx,r,lab in [(28,20,2),(67,7,1)]: solid[(x-cx)**2+(y-33)**2<=r*r]=lab
    nearest=distance_transform_edt(labels!=0,return_distances=False,return_indices=True)
    filled=np.full(labels.shape,np.nan);filled[labels==0]=coarse
    phi=map_coordinates(filled[tuple(nearest)],[y,x],order=1,mode='nearest')
    return solid,phi[solid==0]

def compare(out):
    labels,_=seed(); hist=list(csv.DictReader((out/'history.csv').open())); rows=[]
    for mode in ['root','outer','sealed']:
        for name,stage in [('conditioned','conditioning'),('opened','opening')]:
            r=[r for r in hist if r['mode']==mode and r['stage']==stage][-1]; gap=float(r['grain_gap_m'])/DX; A=float(r['near_water_m2'])/DX**2
            raw=np.genfromtxt(out/f'field_{mode}_{name}.csv',names=True,delimiter=','); x=raw['phi'][raw['solid_id']==0]; f,xf=refined_geometry(labels,x)
            for lab,x0,scale in [(labels,x,1),(f,xf,2)]:
                m=Mesh(lab,gap); s=m.solve(x0,A); active=connected(m,s)
                if not active: raise RuntimeError('Fine/coarse matched state is no longer a connected meniscus')
                fc=np.mean([m.contour(s,k) for k in [2,3,4,5]])
                rows.append(dict(mode=mode,stage=stage,grid_um=50/scale,gap_um=gap*50,near_water_m2=s.water*DX**2,
                                 force_N_m=s.force,contour_N_m=fc,psi_Pa=s.psi,wet_length_m=s.wet_length,mu_residual=s.residual))
    writecsv(out/'mesh_check.csv',rows)
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=Path('results')); compare(ap.parse_args().output)
