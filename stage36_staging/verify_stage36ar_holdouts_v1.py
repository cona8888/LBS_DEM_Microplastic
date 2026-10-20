"""Frozen-code outer-shell and unit-scaling checks of radial sphere reference."""
import json,hashlib
from pathlib import Path
import numpy as np
import sharp_radial_stokes_v1 as solver
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'stage36_evaluations/stage36ar_sharp_radial_20260911'
OUT=BASE/'holdouts_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    config={'outer_ratios':[4.,12.],'radial_intervals':384,'drag_relative_limit':.01,
            'velocity_relative_limit':.001,'scaled_case':{'radius':2.3,'viscosity':.37,'speed':.00025},
            'scaling_relative_limit':1e-12,'boundary_data':'same analytical velocity closure, never target force',
            'scope':'isolated sphere verification holdouts, not experimental validation'}
    (OUT/'contract.json').write_text(json.dumps(config,indent=2))
    prior_path=BASE/'verification_01/results.json';prior=json.loads(prior_path.read_text())
    assert prior['status']=='verified_radial_reference'
    for path,digest in prior['input_hashes'].items():assert sha(Path(path))==digest
    files=[Path(__file__),Path(solver.__file__),prior_path]
    hashes={str(p):sha(p) for p in files}
    rows=[];checks={}
    for R in config['outer_ratios']:
        r=solver.solve(384,R);s=r['s'];target=.5*(s*s-1.5*s+.5/s);ss=s[2:-2]
        velocity=max(np.max(np.abs(2*(r['H']-target)/s**2)),np.max(np.abs((r['interior_dH']-(ss-.75-.25/ss**2))/ss)))
        error=abs(r['force']/(6*np.pi*.1*1e-4)-1)
        row={'outer_ratio':R,'drag_relative_error':float(error),'velocity_relative_error':float(velocity),
             'wall_slip':r['independent_wall_slip_over_abs_U'],'seconds':r['seconds']}
        rows.append(row)
        checks[f'outer_{R}_drag']=bool(error<.01)
        checks[f'outer_{R}_velocity']=bool(velocity<.001)
    q=config['scaled_case'];scaled=solver.solve(384,8,**q)
    baseline=prior['rows'][-1]['force']
    expected=baseline*(q['radius']*q['viscosity']*q['speed'])/(1.*.1*1e-4)
    scaling_error=abs(scaled['force']/expected-1)
    checks['physical_scaling']=scaling_error<1e-12
    # Polynomial exactness of finite-difference weights, including wall stencil.
    moments=[]
    for offsets in [np.arange(-2,3),np.arange(5),np.arange(7)]:
        for derivative in range(1,min(4,len(offsets)-1)+1):
            w=solver.weights(offsets,derivative)
            for power in range(len(offsets)):
                expected_moment=float(__import__('math').factorial(power)) if power==derivative else 0.
                moments.append(abs(w@(offsets.astype(float)**power)-expected_moment))
    checks['derivative_weight_polynomials']=max(moments)<1e-8
    rejections=[]
    for kwargs in [{'intervals':12},{'radius':-1},{'viscosity':0},{'speed':float('nan')},{'outer_ratio':1.}]:
        try:solver.solve(**kwargs);rejections.append(False)
        except ValueError:rejections.append(True)
    checks['invalid_parameters_rejected']=all(rejections)
    checks['hashes_unchanged']=all(sha(p)==hashes[str(p)] for p in files)
    result={'status':'holdouts_passed' if all(checks.values()) else 'holdouts_failed','checks':checks,'rows':rows,
            'scaling_relative_error':scaling_error,'maximum_polynomial_moment_error':max(moments),
            'input_hashes':hashes,'contract_sha256':sha(OUT/'contract.json'),'production_promoted':False}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if not all(checks.values()):raise SystemExit(1)
if __name__=='__main__':main()
