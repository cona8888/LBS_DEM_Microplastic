"""Apparent contact angle from the connected upper midplane water-air interface.
Circle is fitted to the *field* interface, not to the nominal wall potential.
Lengths in reference-grid units; fixed baseline disk positions only.
"""
import numpy as np
from scipy.optimize import least_squares
from applications.rhizofield.field import Mesh,seed
from applications.rhizofield.refine import refined_geometry

def apparent(m,s,trim=1.):
    if not np.isclose(m.cx[54*m.scale], (54*m.scale+.5)*m.hy-.5):
        raise ValueError('Apparent-angle reconstruction only for the initial fixed gap')
    z=m.map(s.phi); y=(np.arange(z.shape[0])+.5)*m.hy-.5
    points=[]
    for j,x in enumerate(m.cx):
        if not 40<x<68: continue
        col=z[:,j]; hit=np.where((y[:-1]>=33)&(col[:-1]>=0)&(col[1:]<0))[0]
        if len(hit)!=1: continue
        i=hit[0]; yp=y[i]+m.hy*col[i]/(col[i]-col[i+1]); p=np.array([x,yp])
        if min(np.linalg.norm(p-[28,33])-20, np.linalg.norm(p-[67,33])-7)>=trim: points.append(p)
    if len(points)<7:raise ValueError("Insufficient upper-interface samples")
    a=np.array(points); mid=a.mean(axis=0)
    def resid(t):return np.linalg.norm(a-t[:2],axis=1)-t[2]
    t=least_squares(resid,[mid[0],mid[1]+12.,12.],bounds=([-300,mid[1],.01],[300,1000,1000])).x
    # Intersection of reconstructed interface circle with physical grain circle.
    # At a circle intersection cos(theta)=n_s . n_lg.  n_lg points to the
    # gas-side centre of this concave meniscus; not valid for a convex drop.
    b=np.array([67.,33.]); d=np.linalg.norm(t[:2]-b); r=7.; R=t[2]
    c=(d*d-r*r-R*R)/(2*r*R)
    if len(a)<7 or not -1<c<1 or np.sqrt(np.mean(resid(t)**2))>.35:raise ValueError(f'Invalid angle readout: {t}, cos={c}, n={len(a)}')
    return float(np.degrees(np.arccos(c))),float(np.sqrt(np.mean(resid(t)**2))),len(a)

def state(theta,scale=1):
    lab,x=seed(); ref=Mesh(lab); A=ref.water(x)
    if scale==2:lab,x=refined_geometry(lab,x)
    m=Mesh(lab,grain_deg=theta);s=m.solve(x,A);return m,s
