import json,time,sys,platform
from pathlib import Path
import numpy as np
import refined_ib_sphere_v1 as m
import verify_stage36q_nonzero_reference_v1 as ref
from verify_stage36r_manufactured_flow_v1 import ramp,gint
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def dump(p,d):p.write_text(json.dumps(d,indent=2,default=lambda x:x.item()),encoding='utf-8')
def smooth(q):q=np.clip(q,0,1);return 10*q**3-15*q**4+6*q**5

def main():
    base=ROOT/'stage36_evaluations/stage36w_spatial_flow_20260908/verification_01';bv=json.loads((base/'manifest.json').read_text());assert bv['completed'] and not (base/'failure.json').exists();checked={str(base/'manifest.json'):sha(base/'manifest.json')}
    for group in ('source_hashes','parent_hashes','artifact_hashes'):
        for p,h in bv[group].items():assert sha(p)==h;checked[p]=h
    out=ROOT/'stage36_evaluations/stage36ab_source_gap_20260909/verification_01';out.mkdir(parents=True,exist_ok=False)
    contract=ROOT/'stage36_staging/STAGE36AB_SOURCE_GAP_SENSITIVITY_CONTRACT.md';sources={str(contract):sha(contract)}
    for mod in list(sys.modules.values()):
        p=getattr(mod,'__file__',None)
        if p and Path(p).parent==ROOT/'stage36_staging' and Path(p).suffix=='.py':sources[str(Path(p).resolve())]=sha(p)
    n=24;dt=1/n**2;x=(np.indices((n,n,n)).reshape(3,-1).T+.5)/n-.5;r=np.linalg.norm(x,axis=1);mask=(r>ref.R)&(r<ref.L);ext=r>ref.R;u0=ref.field(x);adv=np.zeros_like(x);lap=np.zeros_like(x);G,lap[mask]=ref.derivatives(x[mask]);adv[mask]=np.einsum('nij,nj->ni',G,u0[mask]);centre=np.ones(3)*n/2;body,w=m.ib.sphere_quadrature(n/5);F0=4*np.pi/3*.1*.2**3*2*.01/.2**2
    rows=[];start=time.monotonic()
    try:
        for gap_cells in (1,2):
            taper=smooth((r-(ref.R+gap_cells/n))*n);assert np.all(taper[r<=ref.R+gap_cells/n]==0);np.savez_compressed(out/f'gap{gap_cells}_source_taper.npz',points=x,taper=taper)
            f=m.equilibrium(np.ones(n**3),np.zeros((3,n**3))).reshape(19,n,n,n);states={'initial':f.copy()};hist=[];errors=[]
            for j in range(1,n*n+1):
                if time.monotonic()-start>180:raise TimeoutError('CPU cap')
                t=j*dt;g,gp=ramp(t-dt/2);source=(gp*u0+g*g*adv-.1*g*lap)*taper[:,None];imp=source*dt*dt*n
                old=f.copy();a=f.reshape(19,-1);rho=a.sum(axis=0);u=m.C.T@a/rho;_,pinside=m.interior(f,centre,n/5);pold=(m.C.T@a).sum(axis=1)
                forced=(a+m.equilibrium(rho,u+(imp/rho[:,None]).T)-m.equilibrium(rho,u)).reshape(f.shape);actual=(m.C.T@(forced-f).reshape(19,-1)).T;inside=w@m.trilinear(actual,body+centre,n)
                f,row,packet=m.step(forced,centre,n/5,np.zeros(3),128,tau=.8,capture=j==1);raw=-np.array(row['force_on_fluid'])+np.array(row['interior_momentum_after'])-pinside;computed=raw-inside;analytical=np.array([F0*(gint(t)-gint(t-dt))/dt,0,0]);residual=np.array(row['momentum_after'])-pold-actual.sum(axis=0)-row['force_on_fluid']
                health=abs(row['mass_after']-n**3)/n**3<1e-10 and np.max(abs(residual))/n**3<1e-12 and row['density_error']<.01 and row['marker_slip']<1e-10 and np.isfinite(f).all() and f.min()>0;assert health
                hist.append({'time':t,'force':computed.tolist(),'exact_force':analytical.tolist(),'interior_source_force':inside.tolist(),'source_integral':(source.sum(axis=0)/n**3).tolist(),'force_discrepancy':float(np.linalg.norm(computed-analytical)/F0),'momentum_residual':residual.tolist(),'density_error':row['density_error'],'marker_slip':row['marker_slip'],'mass':row['mass_after']})
                if j==1:np.savez_compressed(out/f'gap{gap_cells}_first.npz',before_source=old,source_impulse=actual,**packet)
                if j%(n*n//4)==0:
                    states[f'quarter_{j//(n*n//4)}']=f.copy();a=f.reshape(19,-1);up=(m.C.T@a).T/a.sum(axis=0)[:,None]*n;target=ramp(t)[0]*u0;err=up[ext]-target[ext]
                    errors.append({'rms':float(np.sqrt(np.mean(np.sum(err**2,axis=1)))/np.sqrt(np.mean(np.sum(u0[ext]**2,axis=1)))),'mean_velocity':up[ext].mean(axis=0).tolist()})
            row={'gap_cells':gap_cells,'health_passed':True,'max_force_discrepancy':max(h['force_discrepancy'] for h in hist),'quarter_velocity_discrepancies':errors,'max_interior_source_force_relative':max(np.linalg.norm(h['interior_source_force'])/F0 for h in hist),'validation_gate_applicable':False};rows.append(row)
            dump(out/f'gap{gap_cells}_history.json',hist);np.savez_compressed(out/f'gap{gap_cells}_states.npz',**states);print(row,flush=True)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
    for p,h in sources.items():assert sha(p)==h
    dump(out/'manifest.json',{'completed':True,'cases':rows,'new_cpu_flows':2,'diagnostic_only':True,'source_hashes':sources,'parent_hashes':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'python':platform.python_version(),'numpy':np.__version__,'elapsed_seconds':time.monotonic()-start,'release_qualified':False})
if __name__=='__main__':main()
