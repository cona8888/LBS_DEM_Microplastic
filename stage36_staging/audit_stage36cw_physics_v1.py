"""Read-only diagnostics of archived transport; writes a separate review bundle."""
import hashlib, json
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
import matrix_release_transport_v1 as mt
import run_stage36cp_matrix_release_pilot_v1 as old

R=Path(__file__).resolve().parents[1]
O=R/'stage36_evaluations/stage36cw_scientific_review_20260911/review_01'
O.mkdir(parents=True,exist_ok=False)
P=R/'stage36_runs/stage36cr_matrix_release_pilot_corrected_20260911/pilot_01'
paths=[Path(__file__),Path(mt.__file__),Path(old.__file__),P/'results.json',P/'resolved_config.json',P/'trajectories_dx_0p1.json',old.GEOM]
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

class NoGrains:
    def margin(self,*args): return float('inf')
u=np.zeros((3,12,12,12));u[0]=2.;grad=np.zeros((3,3,12,12,12))
# Mean speed is one but local streamline speed is two. Full exit x-r=L has exact t=1.
outlet=old.integrate(u,grad,NoGrains(),[9,5,5],[1,0,0],1,1,1,.1,10,1,10)
invalid=u.copy();invalid[0]=np.nan
nan=old.integrate(invalid,grad,NoGrains(),[5,5,5],[1,0,0],1,1,1,.1,10,1,10)
# Linear cell-centred field: f(i)=i+0.5, true value at physical x=3.2 is 3.2.
f=np.broadcast_to((np.arange(12)+.5)[:,None,None],(12,12,12))
origin_error=float(mt.trilinear(f,[3.2,4.2,5.2])-3.2)

# Exact sphere-ellipsoid separation via closest point on ellipsoid.
a=np.array([4.,1.,1.]);c=np.array([2.,2.,0.]);radius=.1
lam=brentq(lambda t:np.sum((a*c/(t+a*a))**2)-1,0,100)
closest=a*a*c/(lam+a*a)
exact_gap=float(np.linalg.norm(c-closest)-radius)
support_gap=float(np.linalg.norm(c)-radius-mt.ellipsoid_support(c,[1,0,0],4,1))

cfg=json.loads((P/'resolved_config.json').read_text());rows=json.loads((P/'trajectories_dx_0p1.json').read_text())
with np.load(old.GEOM) as z:
    dx=float(z['spacing_m'][0]);L=float(z['cell_length_m'][0]);rs=cfg['particle']['equal_volume_sphere_radius_m']/dx
    grain_mean=float(2*z['sand_radii_m'].mean())
release=[]
for row in rows:
    if row['status']!='released': continue
    aa,bb=(rs,rs) if row['shape']=='sphere' else tuple(cfg['particle']['prolate_axes_cells'][:2])
    gap=row['final_position_cells'][0]-mt.ellipsoid_support([1,0,0],row['final_orientation'],aa,bb)-186
    release.append({'id':row['id'],'shape':row['shape'],'stored_trailing_edge_minus_outlet_cells':gap})

# Physical scale implied by matching the archived lattice viscosity to water.
mu=.001002;rho=998.2;nu=mu/rho;dt=.1*dx*dx/nu
mean_lu=json.loads((P/'results.json').read_text())['numerical']['mean_pore_velocity_lu']
U=mean_lu*dx/dt;d=2*rs*dx
# Illustrative PET density, explicitly not a measured sample input.
rhop=1380.;g=9.80665
settling=(rhop-rho)*g*d*d/(18*mu)
result={'review_status':'material_issues_confirmed_prior_release_claim_requires_revision',
 'diagnostics':{'cell_centre_origin_error_cells':origin_error,
 'outlet_uniform_local_flow':{'exact_full_exit_time':1.,'reported_time':outlet['time_pv']*10,'stored_final_x':outlet['final_position_cells'][0],'required_full_exit_x':11.},
 'nan_velocity_returned_status':nan['status'],
 'conservative_support_false_positive_example':{'support_gap':support_gap,'exact_gap':exact_gap},
 'stored_released_states':release,
 'all_stored_released_states_short_of_full_exit':all(x['stored_trailing_edge_minus_outlet_cells']<0 for x in release)},
 'scales':{'dx_m':dx,'box_m':L,'box_over_mean_grain_diameter':L/grain_mean,'sphere_diameter_m':d,'sphere_diameter_cells':d/dx,'fibre_diameter_cells':.0001/dx,'fibre_length_cells':.0004/dx,'implied_water_time_step_s':dt,'implied_mean_pore_speed_m_s':U,'implied_seven_pv_seconds':7*L/U,'illustrative_PET_density_kg_m3':rhop,'unbounded_stokes_settling_estimate_m_s':settling,'settling_over_implied_pore_speed':settling/U,'settling_reynolds_for_validity_check':settling*d/nu,'note':'Stokes settling is a scale estimate; confinement and finite Re require correction. No sample density or target flow speed is established.'},
 'input_hashes':hashes}
(O/'diagnostics.json').write_text(json.dumps(result,indent=2,allow_nan=False))
assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
print(json.dumps(result,indent=2))
