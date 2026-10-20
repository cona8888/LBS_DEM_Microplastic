import json,time,sys,platform
from pathlib import Path
import numpy as np
import refined_ib_sphere_v1 as m
import verify_stage36q_nonzero_reference_v1 as ref
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
def dump(p,d):p.write_text(json.dumps(d,indent=2,default=lambda x:x.item()),encoding='utf-8')
def ramp(t):
    q=np.clip(t/.25,0,1);return 10*q**3-15*q**4+6*q**5, (30*q*q-60*q**3+30*q**4)/.25 if 0<t<.25 else 0.
def gint(t):
    q=np.clip(t/.25,0,1);return .25*(2.5*q**4-3*q**5+q**6)+max(t-.25,0)
def main():
    parent=ROOT/'stage36_evaluations/stage36q_nonzero_reference_20260908/reference_01/manifest.json';v=json.loads(parent.read_text());assert v['reference_passed'];checked={str(parent):sha(parent)}
    for group in ('source_hashes','input_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h;checked[p]=h
    out=ROOT/'stage36_evaluations/stage36r_manufactured_flow_20260908/verification_01';out.mkdir(parents=True,exist_ok=False)
    sources={str(ROOT/'stage36_staging/STAGE36R_MANUFACTURED_FLOW_CONTRACT.md'):sha(ROOT/'stage36_staging/STAGE36R_MANUFACTURED_FLOW_CONTRACT.md')}
    for mod in list(sys.modules.values()):
        p=getattr(mod,'__file__',None)
        if p and Path(p).parent==ROOT/'stage36_staging' and Path(p).suffix=='.py':sources[str(Path(p).resolve())]=sha(p)
    x=(np.indices((16,16,16)).reshape(3,-1).T+.5)/16-.5;r=np.linalg.norm(x,axis=1);mask=(r>ref.R)&(r<ref.L);ext=r>ref.R
    u0=ref.field(x);adv=np.zeros_like(x);lap=np.zeros_like(x);G,lap[mask]=ref.derivatives(x[mask]);adv[mask]=np.einsum('nij,nj->ni',G,u0[mask])
    centre=np.ones(3)*8;body,w=m.ib.sphere_quadrature(3.2);F0=4*np.pi/3*.1*.2**3*2*.01/.2**2;rows=[];start=time.monotonic()
    assert ramp(0)==(0.,0.) and ramp(.25)==(1.,0.);assert abs(gint(1)-.875)<1e-15
    try:
        for s in (1,2,4):
            dt=1/(256*s);f=m.equilibrium(np.ones(4096),np.zeros((3,4096))).reshape(19,16,16,16);states={'initial':f.copy()};hist=[];errors=[]
            for j in range(1,256*s+1):
                if time.monotonic()-start>180:raise TimeoutError('CPU cap')
                t=j*dt;g,gp=ramp(t-dt/2);force=gp*u0+g*g*adv-.1*g*lap;imp=force*dt*dt*16
                old=f.copy();a=f.reshape(19,-1);rho=a.sum(axis=0);u=m.C.T@a/rho;_,pinside=m.interior(f,centre,3.2);pold=(m.C.T@a).sum(axis=1)
                forced=(a+m.equilibrium(rho,u+(imp/rho[:,None]).T)-m.equilibrium(rho,u)).reshape(f.shape)
                actual=(m.C.T@(forced-f).reshape(19,-1)).T;inside=w@m.trilinear(actual,body+centre,16)
                f,row,packet=m.step(forced,centre,3.2,np.zeros(3),56,tau={1:.8,2:.65,4:.575}[s],capture=j==1)
                raw=-np.array(row['force_on_fluid'])+np.array(row['interior_momentum_after'])-pinside;corrected=raw-inside;analytical=np.array([F0*(gint(t)-gint(t-dt))/dt,0,0]);computed=corrected*s*s
                residual=np.array(row['momentum_after'])-pold-actual.sum(axis=0)-row['force_on_fluid'];health=abs(row['mass_after']-4096)/4096<1e-10 and np.max(abs(residual))/4096<1e-12 and row['density_error']<.01 and row['marker_slip']<1e-10
                assert health
                hist.append({'time':t,'force':computed.tolist(),'exact_force':analytical.tolist(),'unsubtracted_force':(raw*s*s).tolist(),'interior_source_force':(inside*s*s).tolist(),'force_error':float(np.linalg.norm(computed-analytical)/F0),'momentum_residual':residual.tolist(),'density_error':row['density_error'],'marker_slip':row['marker_slip'],'mass':row['mass_after']})
                if j==1:np.savez_compressed(out/f's{s}_first.npz',before_source=old,source_impulse=actual,**packet)
                if j%(64*s)==0:
                    states[f'quarter_{j//(64*s)}']=f.copy();a=f.reshape(19,-1);up=(m.C.T@a).T/a.sum(axis=0)[:,None]*16*s;target=ramp(t)[0]*u0
                    errors.append(float(np.sqrt(np.mean(np.sum((up[ext]-target[ext])**2,axis=1)))/np.sqrt(np.mean(np.sum(u0[ext]**2,axis=1)))))
            row={'s':s,'steps':256*s,'health_passed':True,'max_force_error':max(h['force_error'] for h in hist),'quarter_velocity_errors':errors,'max_interior_source_force_relative':max(np.linalg.norm(h['interior_source_force'])/F0 for h in hist)};row['analytical_passed']=row['max_force_error']<=.02 and max(errors)<=.02;rows.append(row)
            dump(out/f's{s}_history.json',hist);np.savez_compressed(out/f's{s}_states.npz',**states);print(row,flush=True)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
    for p,h in sources.items():assert sha(p)==h
    dump(out/'manifest.json',{'completed':True,'cases':rows,'new_cpu_flows':3,'analytical_passed':all(r['analytical_passed'] for r in rows),'source_hashes':sources,'parent_hashes':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'python':platform.python_version(),'numpy':np.__version__,'elapsed_seconds':time.monotonic()-start,'release_qualified':False})
if __name__=='__main__':main()
