"""Constant-reference-density factorized variant of periodic_drag_reference_v1."""
import numpy as np
from scipy.linalg import cho_factor, cho_solve
import periodic_drag_reference_v1 as base
from body_link_extractor_v1 import C
from moving_wall_reference_v1 import equilibrium

def initialize(n):
    s=base.initialize(n)
    gram=(s['matrix']@s['matrix'].T).toarray()
    s['factor']=cho_factor(gram,lower=True,check_finite=True)
    s['factor_condition']=float(np.linalg.cond(gram))
    return s

def project(f,matrix,factor):
    flat=f.reshape(19,-1);rho=flat.sum(axis=0);u=(C.T@flat).T/rho[:,None]
    rhs=-(matrix@u);marker=cho_solve(factor,rhs,check_finite=False);grid=matrix.T@marker
    up=u+grid/rho[:,None]
    new=flat+equilibrium(rho,up.T)-equilibrium(rho,u.T)
    return new.reshape(f.shape),marker,float(np.max(np.abs(matrix@up)))

def step(state,source_impulse_per_cell):
    f=state['f'];n=state['n'];centre=state['centre'];radius=state['radius'];matrix=state['matrix']
    if not np.isfinite(source_impulse_per_cell) or source_impulse_per_cell<0 or source_impulse_per_cell>1e-4:raise ValueError('invalid source impulse')
    flat=f.reshape(19,-1);rho=flat.sum(axis=0);u=(C.T@flat).T/rho[:,None]
    post=flat-(flat-equilibrium(rho,u.T))/.8;uf=u.copy();uf[:,0]+=source_impulse_per_cell/rho
    forced=post+equilibrium(rho,uf.T)-equilibrium(rho,u.T);source_actual=(C.T@(forced-post)).T
    streamed=np.stack([np.roll(forced[q].reshape(n,n,n),tuple(C[q]),axis=(0,1,2)) for q in range(19)])
    p0=(C.T@flat).sum(axis=1);pi0=base.interior_momentum(streamed,centre,radius)
    projected,markers,slip=project(streamed,matrix,state['factor'])
    p1=(C.T@projected.reshape(19,-1)).sum(axis=1);pi1=base.interior_momentum(projected,centre,radius)
    mt=markers.sum(axis=0);st=source_actual.sum(axis=0)
    body,volume=base.ib.sphere_quadrature(radius,8,16,32);si=volume@base.trilinear(source_actual,body+centre,n)
    force=-mt+pi1-pi0-si;ledger=p1-p0-st-mt
    new=dict(state);new['f']=projected
    row={'superficial_velocity':(p1/n**3).tolist(),'force_on_sphere':force.tolist(),'source_impulse':st.tolist(),
         'interior_source_impulse':si.tolist(),'marker_impulse_on_fluid':mt.tolist(),'momentum_ledger_residual':ledger.tolist(),
         'marker_slip':slip,'condition_number':state['factor_condition'],'mass_relative_drift':abs(float(projected.sum())/n**3-1),
         'density_error':float(np.max(np.abs(projected.sum(axis=0)-1))),'minimum_population':float(projected.min())}
    return new,row
