"""Three-resolution solved sharp-surface sphere benchmark; no calibration."""
import hashlib,json,platform
from pathlib import Path
import numpy as np
import scipy
import sharp_radial_stokes_v1 as solver

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage36_evaluations/stage36ar_sharp_radial_20260911/verification_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg={'system':'isolated stationary sphere; axisymmetric Stokes mode; body-fitted radial FD',
         'radial_intervals':[96,192,384],'outer_radius_over_a':8.,'radius':1.,'mu':.1,'speed':1e-4,
         'outer_boundary':'exact isolated-sphere velocity only; no exact interior values or drag supplied to solve',
         'finest_drag_relative_error_limit':.01,'finest_velocity_relative_error_limit':.001,
         'finest_independent_wall_slip_limit':1e-4,'algebraic_residual_limit':1e-10,
         'minimum_drag_observed_order':1.5,'scope':'numerical reference only; no periodic or mobile-fibre qualification'}
    (OUT/'contract.json').write_text(json.dumps(cfg,indent=2))
    files=[Path(__file__),Path(solver.__file__)]
    hashes={str(p):sha(p) for p in files}
    rows=[]
    for n in cfg['radial_intervals']:
        result=solver.solve(n,8.,1.,.1,1e-4)
        s=result['s'];H=result['H'];target_H=.5*(s*s-1.5*s+.5/s)
        # Velocity extrema over angle are bounded by the radial/tangential coefficients.
        ss=s[2:-2];target_dH=ss-.75-.25/ss**2
        velocity_error=max(float(np.max(np.abs(2*(H-target_H)/s**2))),
                           float(np.max(np.abs((result['interior_dH']-target_dH)/ss))))
        fd=6*np.pi*.1*1e-4
        row={k:v for k,v in result.items() if not isinstance(v,np.ndarray)}
        row.update({'drag_ratio':result['force']/fd,'drag_relative_error':abs(result['force']/fd-1),
                    'velocity_relative_error':velocity_error,'pressure_fraction':result['pressure_force']/result['force']})
        np.savez_compressed(OUT/f'radial_{n}.npz',s=s,H=H,dH=result['interior_dH'])
        rows.append(row)
    orders=[float(np.log2(rows[i]['drag_relative_error']/rows[i+1]['drag_relative_error'])) for i in range(2)]
    checks={'all_algebraic_residuals':all(r['algebraic_residual']<1e-10 for r in rows),
            'finest_drag':rows[-1]['drag_relative_error']<.01,
            'finest_velocity':rows[-1]['velocity_relative_error']<.001,
            'finest_independent_wall_slip':rows[-1]['independent_wall_slip_over_abs_U']<1e-4,
            'drag_refinement_order':all(x>1.5 for x in orders),
            'velocity_error_decreases':all(rows[i+1]['velocity_relative_error']<rows[i]['velocity_relative_error'] for i in range(2))}
    zero=solver.solve(96,speed=0);reverse=solver.solve(96,speed=-1e-4)
    checks['zero_flow_force']=zero['force']==0
    checks['force_reversal']=abs(reverse['force']+rows[0]['force'])<1e-15
    checks['hashes_unchanged']=all(sha(p)==hashes[str(p)] for p in files)
    results={'status':'verified_radial_reference' if all(checks.values()) else 'verification_failed',
             'checks':checks,'rows':rows,'drag_orders':orders,'input_hashes':hashes,
             'contract_sha256':sha(OUT/'contract.json'),'python':platform.python_version(),
             'numpy':np.__version__,'scipy':scipy.__version__,
             'artifacts':{p.name:sha(p) for p in OUT.glob('*.npz')},'production_promoted':False}
    (OUT/'results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))
    if not all(checks.values()):raise SystemExit(1)
if __name__=='__main__':main()
