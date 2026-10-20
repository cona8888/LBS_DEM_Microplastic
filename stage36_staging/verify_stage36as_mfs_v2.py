"""Frozen small 3-D MFS verification; independent surface residual required."""
import json,time,hashlib,platform
from pathlib import Path
import numpy as np
import scipy
import sharp_stokes_mfs_v2 as solver
import sharp_sphere_reference_v1 as exact
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage36_evaluations/stage36as_sharp_mfs_20260911/verification_02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def prolate_drag(mu,a,b):
    e=np.sqrt(1-(b/a)**2);L=np.log((1+e)/(1-e))
    return np.array([16*np.pi*mu*a*e**3/(-2*e+(1+e*e)*L),
                     32*np.pi*mu*a*e**3/(2*e+(3*e*e-1)*L)])

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg={'boundary_oversampling':3,'svd_cutoff':1e-12,'source_geometry':'confocal interior ellipsoid','counts':[48,96,192],'source_fraction':.6,'mu':.1,'speed':1e-4,
         'sphere_axes':[1.,1.,1.],'spheroid_axes':[2.,1.,1.],
         'force_relative_limit':.001,'independent_noslip_limit':.001,'field_relative_limit':.001,
         'traction_force_closure_limit':1e-4,'rotation_torque_relative_limit':.001,
         'sphere_source_fraction_holdouts':[.5,.7],'source_holdout_force_limit':.005,
         'source_holdout_noslip_limit':.005,
         'scope':'unbounded steady Stokes single-body benchmark; no pore walls, contacts or transport',
         'candidate_failure_policy':'record shape qualification separately; do not fit source location to force'}
    (OUT/'contract.json').write_text(json.dumps(cfg,indent=2))
    files=[Path(__file__),Path(solver.__file__),Path(exact.__file__)]
    hashes={str(p):sha(p) for p in files}
    surface,normals,weights=exact.surface_quadrature(1.)
    rng=np.random.default_rng(3604);probe=rng.normal(size=(128,3));probe/=np.linalg.norm(probe,axis=1)[:,None]
    probe*=rng.uniform(1.2,3.,size=(128,1))
    U=np.array([1e-4,0.,0.]);rows=[];states={};solutions={}
    for shape,axes in [('sphere',[1,1,1]),('spheroid',[2,1,1])]:
        for n in cfg['counts']:
            start=time.perf_counter();state=solver.prepare(axes,n,.6,.1);setup=time.perf_counter()-start
            states[(shape,n)]=state
            for direction in ([0] if shape=='sphere' else [0,1]):
                velocity=np.eye(3)[direction]*1e-4
                start=time.perf_counter();solution=solver.solve(state,velocity);seconds=time.perf_counter()-start
                solutions[(shape,n,direction)]=solution
                boundary=surface*np.asarray(axes)
                independent=float(np.max(np.linalg.norm(solver.velocity(state,solution,boundary),axis=1))/1e-4)
                target=6*np.pi*.1*1e-4 if shape=='sphere' else prolate_drag(.1,2,1)[direction]*1e-4
                row={'shape':shape,'count':n,'direction':direction,'source_fraction':.6,
                     'condition':state['condition'],'setup_seconds':setup,'rhs_solve_seconds':seconds,
                     'force':solution['force'].tolist(),'torque':solution['torque'].tolist(),
                     'force_ratio':float(solution['force'][direction]/target),
                     'relative_force_error':float(np.linalg.norm(solution['force']-np.eye(3)[direction]*target)/target),
                     'independent_noslip_over_U':independent,
                     'collocation_residual_over_U':solution['collocation_residual']/1e-4}
                if shape=='sphere':
                    calculated=solver.velocity(state,solution,probe);truth=exact.fields(probe,1,.1,U)[0]
                    row['exterior_velocity_relative_error']=float(np.max(np.linalg.norm(calculated-truth,axis=1))/1e-4)
                    integrated=weights*1.25**2@solver.traction(state,solution,surface*1.25,normals)
                    row['traction_force_closure']=float(np.linalg.norm(integrated-solution['force'])/target)
                np.savez_compressed(OUT/f'{shape}_n{n}_d{direction}.npz',points=state['points'],sources=state['sources'],forces=solution['lambda'])
                rows.append(row)
                print(json.dumps(row),flush=True)
    fine=next(r for r in rows if r['shape']=='sphere' and r['count']==192)
    coarse=next(r for r in rows if r['shape']=='sphere' and r['count']==48)
    checks={'sphere_drag':fine['relative_force_error']<.001,'sphere_independent_noslip':fine['independent_noslip_over_U']<.001,
            'sphere_exterior_field':fine['exterior_velocity_relative_error']<.001,
            'sphere_traction_closure':fine['traction_force_closure']<1e-4,
            'sphere_refinement_improves':fine['independent_noslip_over_U']<coarse['independent_noslip_over_U']}
    state=states[('sphere',192)];rotation=solver.solve(state,omega=(0,0,1e-4))
    target_torque=np.array([0,0,-8*np.pi*.1*1e-4])
    torque_error=float(np.linalg.norm(rotation['torque']-target_torque)/np.linalg.norm(target_torque))
    rotation_slip=float(np.max(np.linalg.norm(solver.velocity(state,rotation,surface)-np.cross([0,0,1e-4],surface),axis=1))/1e-4)
    checks['sphere_rotational_torque']=torque_error<.001
    checks['sphere_rotation_independent_boundary']=rotation_slip<.001
    holdouts=[]
    for alpha in cfg['sphere_source_fraction_holdouts']:
        s=solver.prepare(count=192,source_fraction=alpha);sol=solver.solve(s,U)
        err=float(np.linalg.norm(sol['force']-[6*np.pi*.1*1e-4,0,0])/(6*np.pi*.1*1e-4))
        slip=float(np.max(np.linalg.norm(solver.velocity(s,sol,surface),axis=1))/1e-4)
        holdouts.append({'alpha':alpha,'force_error':err,'independent_slip':slip,'condition':s['condition']})
    checks['sphere_source_position_holdouts']=all(r['force_error']<.005 and r['independent_slip']<.005 for r in holdouts)
    spheroid={}
    for d in [0,1]:
        r=next(r for r in rows if r['shape']=='spheroid' and r['count']==192 and r['direction']==d)
        spheroid[str(d)]=r['relative_force_error']<.001 and r['independent_noslip_over_U']<.001
    checks['input_hashes_unchanged']=all(sha(p)==hashes[str(p)] for p in files)
    result={'sphere_status':'passed' if all(checks.values()) else 'failed','checks':checks,
            'spheroid_direction_qualification':spheroid,'rows':rows,'rotation_torque_error':torque_error,
            'rotation_boundary_error':rotation_slip,'source_holdouts':holdouts,'input_hashes':hashes,
            'contract_sha256':sha(OUT/'contract.json'),'python':platform.python_version(),'scipy':scipy.__version__,
            'artifacts':{p.name:sha(p) for p in OUT.glob('*.npz')},'production_promoted':False}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['sphere_status','checks','spheroid_direction_qualification','rotation_torque_error','rotation_boundary_error','source_holdouts']},indent=2))
if __name__=='__main__':main()
