"""Independent finite-difference PDE residuals of the sphere oracle."""
import json,hashlib
from pathlib import Path
import numpy as np
import sharp_sphere_reference_v1 as exact
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage36_evaluations/stage36aq_sharp_sphere_20260910/pde_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    cfg={'seed':3603,'probe_count':128,'r_over_a':[1.25,3.],
         'h_over_a':[.02,.01,.005],'finest_scaled_residual_limit':.001,
         'minimum_observed_order':1.8,'momentum_equation':'-grad(p)+mu*laplacian(u)=0',
         'continuity_equation':'div(u)=0','domain':'exterior isolated sphere only'}
    (OUT/'contract.json').write_text(json.dumps(cfg,indent=2))
    hashes={str(p):sha(p) for p in [Path(__file__),Path(exact.__file__)]}
    rng=np.random.default_rng(3603);e=rng.normal(size=(128,3));e/=np.linalg.norm(e,axis=1)[:,None]
    x=e*rng.uniform(1.25,3,(128,1));mu=.1;U=np.array([1e-4,5e-5,-2.5e-5]);speed=np.linalg.norm(U)
    uc,_=exact.fields(x,1,mu,U);rows=[]
    for h in cfg['h_over_a']:
        lap=np.zeros_like(uc);gradp=np.zeros_like(uc);div=np.zeros(len(x))
        for j in range(3):
            shift=np.eye(3)[j]*h
            up,pp=exact.fields(x+shift,1,mu,U);um,pm=exact.fields(x-shift,1,mu,U)
            lap+=(up-2*uc+um)/h**2
            gradp[:,j]=(pp-pm)/(2*h)
            div+=(up[:,j]-um[:,j])/(2*h)
        rows.append({'h':h,'scaled_momentum_residual':float(np.max(np.linalg.norm(mu*lap-gradp,axis=1))/(mu*speed)),
                     'scaled_divergence':float(np.max(np.abs(div))/speed)})
    orders={k:[float(np.log2(rows[i][k]/rows[i+1][k])) for i in range(2)] for k in ['scaled_momentum_residual','scaled_divergence']}
    checks={'finest_momentum':rows[-1]['scaled_momentum_residual']<.001,
            'finest_continuity':rows[-1]['scaled_divergence']<.001,
            'second_order_residual_decay':all(v>1.8 for vv in orders.values() for v in vv),
            'input_hashes_unchanged':all(sha(Path(p))==v for p,v in hashes.items())}
    result={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'rows':rows,'orders':orders,
            'input_hashes':hashes,'contract_sha256':sha(OUT/'contract.json')}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if not all(checks.values()):raise SystemExit(1)
if __name__=='__main__':main()
