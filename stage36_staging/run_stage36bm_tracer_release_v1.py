"""Open-plane release in the point-tracer limit around one fixed sphere.

Not finite microplastic, fibre, contact, DEM, or soil-matrix validation.
"""
import json,hashlib,platform,time
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
import sharp_sphere_reference_v1 as flow
out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bm_tracer_release_20260911/run_01'
out.mkdir(parents=True,exist_ok=False)
cfg={'particle_role':'noninteracting zero-size tracers, equal tagged weights, not finite MPs','grain_radius':1.,'injection_x':-3.,'outlet_x':4.,'initial_y':[-2,2],'count':81,'duration':20.,'timesteps':[.02,.01,.005],'release_definition':'first outward crossing of x=4; fraction of initial tagged count','initial_weights':'uniform per tracer, not flux weighted','exit_time_error_limit':1e-4,'streamfunction_error_limit':1e-7,'radius_tolerance':1e-10,'reference_rtol':1e-11,'reference_atol':1e-12,'scope':'unbounded analytic Stokes flow around one fixed sphere; open measurement plane; no walls or particle contacts'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
hashes={str(p):sha(p) for p in [Path(__file__),Path(flow.__file__)]}
initial=np.column_stack([np.full(81,-3.),np.linspace(-2,2,81),np.zeros(81)])
def velocity(p):
    if np.min(np.linalg.norm(p,axis=1))<1-1e-10:raise ValueError('tracer inside grain')
    return flow.fields(p,1.,1.,[1.,0,0])[0]
def psi(p):
    r=np.linalg.norm(p,axis=-1)
    return (.5*r*r-.75*r+.25/r)*(p[...,1]**2+p[...,2]**2)/r**2
def run(dt):
    n=round(20/dt);p=initial.copy();path=[p.copy()];exit_time=np.full(81,np.nan);curve=[0];maxpsi=0.;minradius=3.
    for i in range(n):
        k1=velocity(p);k2=velocity(p+dt*k1/2);k3=velocity(p+dt*k2/2);k4=velocity(p+dt*k3)
        new=p+dt*(k1+2*k2+2*k3+k4)/6
        d=new-p;den=np.sum(d*d,axis=1);fraction=np.clip(-np.sum(p*d,axis=1)/np.maximum(den,1e-300),0,1)
        minimum=float(np.linalg.norm(p+fraction[:,None]*d,axis=1).min());minradius=min(minradius,minimum)
        if minimum<1-1e-10 or np.any(d[:,0]<-1e-12):raise ValueError('crossing/monotonicity violation')
        crossing=np.isnan(exit_time)&(new[:,0]>=4)
        exit_time[crossing]=i*dt+dt*(4-p[crossing,0])/d[crossing,0]
        p=new;path.append(p.copy());curve.append(int(np.isfinite(exit_time).sum()))
        maxpsi=max(maxpsi,float(np.max(np.abs(psi(p)-psi(initial)))))
    return np.array(path),exit_time,np.array(curve),maxpsi,minradius
start=time.perf_counter()
ref=solve_ivp(lambda t,z:velocity(z.reshape(-1,3)).ravel(),[0,20],initial.ravel(),rtol=1e-11,atol=1e-12,dense_output=True,max_step=.05)
if not ref.success:raise ValueError('independent integrator failed')
ref_exit=np.full(81,np.nan)
for j in range(81):
    if ref.y[:, -1].reshape(-1,3)[j,0]>=4:ref_exit[j]=brentq(lambda t:ref.sol(t).reshape(-1,3)[j,0]-4,0,20,xtol=1e-11)
rows=[]
for dt in cfg['timesteps']:
    path,ex,curve,err,minr=run(dt)
    if not np.array_equal(np.isfinite(ex),np.isfinite(ref_exit)):raise ValueError('release IDs differ from reference')
    difference=float(np.max(np.abs(ex[np.isfinite(ex)]-ref_exit[np.isfinite(ex)])))
    count=int(curve[-1]);rows.append({'dt':dt,'released':count,'remaining':81-count,'released_fraction':count/81,'exit_time_max_error':difference,'streamfunction_error':err,'minimum_radius':minr,'count_balance_error':0})
    np.savez_compressed(out/f'dt{dt}.npz',path=path,exit_times=ex,release_count=curve,time=np.arange(len(curve))*dt)
    print(json.dumps(rows[-1]),flush=True)
# Uniform-flow event check independent of grain flow: x=-3+t crosses at t=7.
t=np.arange(0,20+.005,.005);uniform_first=t[np.flatnonzero(-3+t>=4)[0]]
checks={'exit_time':rows[-1]['exit_time_max_error']<1e-4,'streamfunction':all(r['streamfunction_error']<1e-7 for r in rows),'release_count_refinement':len(set(r['released'] for r in rows))==1,'balance':all(r['released']+r['remaining']==81 for r in rows),'uniform_control':abs(uniform_first-7)<1e-12,'input_hashes':all(sha(p)==h for p,h in hashes.items())}
result={'checks':checks,'passed':all(checks.values()),'rows':rows,'runtime_seconds':time.perf_counter()-start,'hashes':hashes,'artifacts':{p.name:sha(p) for p in out.glob('*.npz')},'python':platform.python_version(),'finite_microplastic_release_measured':False,'tracer_release_measured':True,'remaining_is_not_proven_trapped':True}
(out/'results.json').write_text(json.dumps(result,indent=2));print(checks)
