"""Verify exact sphere oracle and quantify local diffuse interpolation defect."""
import json,hashlib,platform
from pathlib import Path
import numpy as np
import sharp_sphere_reference_v1 as exact
import periodic_drag_reference_v1 as old

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage36_evaluations/stage36aq_sharp_sphere_20260910/verification_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    if OUT.exists():raise SystemExit('immutable output already exists')
    OUT.mkdir(parents=True)
    contract={'system':'isolated fixed sphere; unbounded creeping flow; no periodic comparator',
              'radius':1.,'viscosity':.1,'U':[1e-4,5e-5,-2.5e-5],
              'derivative_h_over_a':[.02,.01,.005],
              'finest_traction_relative_tolerance':1e-3,'force_relative_tolerance':1e-5,
              'exact_noslip_relative_tolerance':1e-12,'pressure_fraction_tolerance':1e-12,
              'interpolation_grids':[16,24,32],'interpolation_marker_counts':[192,256,384],
              'interpolation_phase':[0.,.25,.5],'interpretation':'local sampling defect, not solved drag or release validation'}
    (OUT/'contract.json').write_text(json.dumps(contract,indent=2))
    files=[Path(__file__),Path(exact.__file__),Path(old.__file__),Path(old.ib.__file__),
           Path(__file__).with_name('body_link_extractor_v1.py'),Path(__file__).with_name('moving_wall_reference_v1.py')]
    hashes={str(p):sha(p) for p in files}
    a=1.;mu=.1;U=np.array(contract['U']);speed=np.linalg.norm(U)
    points,normals,weights=exact.surface_quadrature(a)
    target=6*np.pi*mu*a*U;traction=1.5*mu/a*U
    exact_slip=np.max(np.linalg.norm(exact.fields(points,a,mu,U)[0],axis=1))/speed
    derivatives=[]
    for h in contract['derivative_h_over_a']:
        fp,fv=exact.numerical_traction(points,normals,a,mu,U,h)
        pressure=weights@fp;viscous=weights@fv;total=pressure+viscous
        derivatives.append({'h_over_a':h,'force':total.tolist(),'pressure':pressure.tolist(),'viscous':viscous.tolist(),
                            'force_relative_error':float(np.linalg.norm(total-target)/np.linalg.norm(target)),
                            'pointwise_traction_relative_error':float(np.max(np.linalg.norm(fp+fv-traction,axis=1))/np.linalg.norm(traction)),
                            'pressure_force_fraction':float(pressure@target/(target@target))})
    checks={'geometric_noslip':bool(exact_slip<1e-12),
            'finest_force':derivatives[-1]['force_relative_error']<1e-5,
            'finest_traction':derivatives[-1]['pointwise_traction_relative_error']<1e-3,
            'pressure_one_third':abs(derivatives[-1]['pressure_force_fraction']-1/3)<1e-12,
            'traction_refinement_decreases':all(derivatives[i+1]['pointwise_traction_relative_error']<derivatives[i]['pointwise_traction_relative_error'] for i in range(2))}
    probes=np.array([[1.5,.2,.3],[2.,-.4,.1],[.2,1.7,.6]])
    u,p=exact.fields(probes,a,mu,U);ur,pr=exact.fields(probes,a,mu,-U)
    checks['flow_reversal']=bool(np.array_equal(u,-ur) and np.array_equal(p,-pr))
    uz,pz=exact.fields(probes,a,mu,np.zeros(3))
    checks['zero_flow']=bool(np.max(np.abs(uz))==0 and np.max(np.abs(pz))==0)
    interpolation=[]
    # The cube is a sampling window, NOT an imposed outer boundary.
    # All boundary stencils are local and far from the window seam.
    for n in contract['interpolation_grids']:
        radius=n/8
        centres=np.stack(np.meshgrid(*([np.arange(n)+.5]*3),indexing='ij'),axis=-1).reshape(-1,3)
        for phase in contract['interpolation_phase']:
            centre=np.full(3,n/2+phase)
            grid_u=exact.fields(centres-centre,radius,mu,U,solid_interior=True)[0]
            for count in contract['interpolation_marker_counts']:
                surface=old.surface(radius,count)+centre
                J=old.interpolation_matrix(surface,n)
                sampled=J@grid_u
                local_exact=exact.fields(surface-centre,radius,mu,U)[0]
                interpolation.append({'n':n,'radius_cells':radius,'phase':phase,'markers':count,
                                      'apparent_slip_max_over_U':float(np.max(np.linalg.norm(sampled,axis=1))/speed),
                                      'apparent_slip_rms_over_U':float(np.sqrt(np.mean(np.sum(sampled**2,axis=1)))/speed),
                                      'exact_surface_slip_over_U':float(np.max(np.linalg.norm(local_exact,axis=1))/speed)})
    checks['all_exact_surfaces_noslip']=all(r['exact_surface_slip_over_U']<1e-12 for r in interpolation)
    checks['all_hashes_unchanged']=all(sha(p)==hashes[str(p)] for p in files)
    ranges={str(n):{'minimum_rms':min(r['apparent_slip_rms_over_U'] for r in interpolation if r['n']==n),
                    'maximum_rms':max(r['apparent_slip_rms_over_U'] for r in interpolation if r['n']==n),
                    'maximum_pointwise':max(r['apparent_slip_max_over_U'] for r in interpolation if r['n']==n)} for n in contract['interpolation_grids']}
    result={'status':'oracle_verified' if all(checks.values()) else 'oracle_failed','checks':checks,
            'exact_surface_slip_over_U':float(exact_slip),'traction_derivatives':derivatives,
            'interpolation':interpolation,'interpolation_ranges':ranges,'input_hashes':hashes,
            'contract_sha256':sha(OUT/'contract.json'),'python':platform.python_version(),'numpy':np.__version__,
            'periodic_force_model_qualified':False,'release_model_qualified':False,
            'source':'https://www.damtp.cam.ac.uk/user/hinch/teaching/CISMejh12handout.pdf'}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['status','checks','traction_derivatives','interpolation_ranges']},indent=2))
    if not all(checks.values()):raise SystemExit(1)

if __name__=='__main__':main()
