"""Separate interface-thickness and mesh checks at fixed state and parameters.
All other physics, geometry, root/grain wall angles and diffuse-phase inventories
stay fixed. This is a sensitivity study, not calibration of a new default.
"""
import numpy as np,json
from scipy.ndimage import distance_transform_edt,map_coordinates
from applications.rhizofield.field import Mesh,seed,DX
from applications.rhizofield.run import connected,writecsv
from .validate import PROFILE,OUT,inspect,dump

def refine_from_fine(labels,phi,scale):
    if scale==2:return labels,phi
    yy,xx=np.indices((67*scale,94*scale));x=(xx+.5)/scale-.5;y=(yy+.5)/scale-.5
    solid=np.zeros(x.shape,int)
    for cx,r,lab in [(28,20,2),(67,7,1)]:solid[(x-cx)**2+(y-33)**2<=r*r]=lab
    nearest=distance_transform_edt(labels!=0,return_distances=False,return_indices=True)
    full=np.full(labels.shape,np.nan);full[labels==0]=phi
    x0=(x+.5)*2-.5;y0=(y+.5)*2-.5
    f=map_coordinates(full[tuple(nearest)],[y0,x0],order=1,mode='nearest')
    return solid,f[solid==0]

def main():
    from .validate import check_frozen
    check_frozen()
    th=json.loads(PROFILE.read_text())['grain_wall_inputs_deg']['25um'];rows=[]
    for scale in (2,4,8):
        for width in (2.5,1.25):
            for mode in ('root','outer'):
                dat=np.load(OUT/f'paired_s2_n18_{mode}.npz');lab,x=refine_from_fine(dat['labels'],dat['phi'],scale)
                m=Mesh(lab,13.55,grain_deg=th,interface_width=width)
                s=m.solve(x,float(dat['near'])/DX**2)
                row=dict(scale=scale,grid_um=50/scale,interface_width_um=width*50,mode=mode,grain_input_deg=th,**inspect(m,s));rows.append(row)
                writecsv(OUT/'width_checks.csv',rows);print(row,flush=True)
    comparisons=[]
    for scale in (2,4,8):
        for width in (125.,62.5):
            a,b=[next(r for r in rows if r['scale']==scale and r['interface_width_um']==width and r['mode']==mode) for mode in ('root','outer')]
            comparisons.append(dict(scale=scale,interface_width_um=width,force_contrast_pct=100*(a['force_N_m']/b['force_N_m']-1),root_laplace_error_pct=a['laplace_error_pct'],outer_laplace_error_pct=b['laplace_error_pct']))
    dump('width_summary.json',comparisons)
if __name__=='__main__':main()
