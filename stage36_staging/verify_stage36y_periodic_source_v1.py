"""Frozen source-isolation contract: unit periodic cube, rho=1, nu=.1.
u=.001*g(t)*sin(2*pi*y)*ex; advection and pressure gradient vanish.
b=.001*(g'+.1*(2*pi)^2*g)*sin(2*pi*y)*ex.
Same pre-collision equilibrium-difference injection; no interface.
N=12,16,24, dt=N^-2, tau=.8, end=1; rest start, quintic ramp .25.
Gate: maximum full-history RMS error / final exact RMS <=.02.
Health: relative mass <1e-10, momentum ledger <1e-12/cell,
density error <.01, positive finite populations. CPU ceiling 180s.
No modification of prior sources, no release/drag qualification.
"""
import json,time,sys,platform
from pathlib import Path
import numpy as np
from refined_ib_sphere_v1 import C,equilibrium
from verify_stage36r_manufactured_flow_v1 import ramp
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def main():
    parent=ROOT/'stage36_evaluations/stage36x_velocity_diagnosis_20260909/analysis_01/manifest.json'
    p=json.loads(parent.read_text());assert p['completed'];checked={str(parent):sha(parent)}
    for group in ('parent_hashes','artifact_hashes'):
        for f,h in p[group].items():assert sha(f)==h;checked[f]=h
    out=ROOT/'stage36_evaluations/stage36y_periodic_source_20260909/verification_01';out.mkdir(parents=True,exist_ok=False)
    sources={str(Path(mod.__file__).resolve()):sha(mod.__file__) for mod in list(sys.modules.values()) if getattr(mod,'__file__',None) and Path(mod.__file__).parent==ROOT/'stage36_staging' and Path(mod.__file__).suffix=='.py'}
    rows=[];start=time.monotonic()
    try:
        for n in (12,16,24):
            y=(np.indices((n,n,n))[1].ravel()+.5)/n;wave=np.sin(2*np.pi*y);base=np.zeros((3,n**3));base[0]=.001*wave;scale=np.sqrt(np.mean(np.sum(base**2,axis=0)));dt=1/n**2
            f=equilibrium(np.ones(n**3),np.zeros_like(base)).reshape(19,n,n,n);history=[];states={}
            for j in range(1,n*n+1):
                assert time.monotonic()-start<180,'resource cap'
                t=j*dt;g,gp=ramp(t-dt/2);imp=base*(gp+.1*(2*np.pi)**2*g)*dt*dt*n
                a=f.reshape(19,-1);rho=a.sum(axis=0);u=C.T@a/rho;p0=(C.T@a).sum(axis=1)
                forced=a+equilibrium(rho,u+imp/rho)-equilibrium(rho,u)
                actual=C.T@(forced-a);np.testing.assert_allclose(actual,imp,atol=1e-15,rtol=0)
                rf=forced.sum(axis=0);uf=C.T@forced/rf;post=(forced-(forced-equilibrium(rf,uf))/.8).reshape(f.shape)
                f=np.stack([np.roll(post[k],tuple(C[k]),axis=(0,1,2)) for k in range(19)])
                af=f.reshape(19,-1);rn=af.sum(axis=0);up=C.T@af/rn*n;res=(C.T@af).sum(axis=1)-p0-actual.sum(axis=1)
                assert np.isfinite(f).all() and f.min()>0 and abs(f.sum()-n**3)/n**3<1e-10 and np.max(abs(res))/n**3<1e-12 and np.max(abs(rn-1))<.01
                err=float(np.sqrt(np.mean(np.sum((up-ramp(t)[0]*base)**2,axis=0)))/scale)
                history.append({'time':t,'rms_error':err,'mean_velocity':up.mean(axis=1).tolist(),'mass':float(f.sum()),'momentum_residual':res.tolist()})
                if j%(n*n//4)==0:states[f'quarter_{j//(n*n//4)}']=f.copy()
            (out/f'n{n}_history.json').write_text(json.dumps(history,indent=2));np.savez_compressed(out/f'n{n}_states.npz',**states)
            row={'n':n,'max_error':max(h['rms_error'] for h in history),'final_error':history[-1]['rms_error'],'health_passed':True};row['passed']=row['max_error']<=.02;rows.append(row);print(row,flush=True)
    except Exception as e:
        (out/'failure.json').write_text(json.dumps({'error':repr(e)}));raise
    for f,h in sources.items():assert sha(f)==h
    lines=['# Stage36Y — smooth periodic source isolation','', 'Three CPU runs; no interface and no production changes. Full-history 2% gate, normalized by final exact velocity RMS.','', '| N | Maximum error | Final error | Pass |','|---|---:|---:|---|']
    for r in rows:lines.append(f"| {r['n']} | {r['max_error']:.3%} | {r['final_error']:.3%} | {r['passed']} |")
    lines+=['','This benchmark isolates a smooth transverse source mode. It does not test nonzero net forcing, the compact source at the sphere, or traction. Earlier sphere failures remain unchanged. No release fraction is qualified.']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'completed':True,'cases':rows,'source_hashes':sources,'parent_hashes':checked,'artifact_hashes':{str(f):sha(f) for f in out.iterdir()},'elapsed_seconds':time.monotonic()-start,'python':platform.python_version(),'numpy':np.__version__,'new_cpu_flows':3,'release_qualified':False},indent=2))
if __name__=='__main__':main()
