"""Test direct residual solvers from the terminal feasible PGS iterate."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares,root
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage37_staging"),str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging")]
import transport_contact as mechanics
import matrix_case_v1,geometry_exact_v1,trajectory_optimized_v1 as trajectory
import inertial_contact_cold_optimized_v1 as s41, inertial_contact_robust_v1 as s42
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
    source=ROOT/"stage43_runs"/"release_pilot_20260912"/"pilot_01"/"coarse.json"; saved=json.loads(source.read_text())["result"]
    field,old,L,dx,inputs=matrix_case_v1.load(2); geom=geometry_exact_v1.GrainGeometry.from_geometry(old)
    x=np.array(saved["position_m"]); p=np.array(saved["orientation"]); q=np.array(saved["velocity_generalized"])
    a,b,mu,rp,rf=2e-4,5e-5,0.3,1380.,998.2; visc=.001002
    uf,grad=field.sample(x); bg,_=mechanics.free_motion(p,grad,uf,a,b,visc,1,1,[0,0,0]); R=s42.stokes_generalized_resistance(p,a,b,visc)
    M,_=s42.generalized_mass_matrix(p,a,b,rp,rf,1); M[3:,3:]=0; vol=4*np.pi*a*b*b/3; body=np.r_[(rp-rf)*vol*np.array([0,0,-9.80665]),np.zeros(3)]
    near=trajectory.enrich(geom,geom.contacts(x,p,a,b,.2*geom.r.max())); LUB,_=trajectory.lubrication_matrix(near,p,a,b,a,visc,.2,.01)
    ts=max(np.linalg.norm(q[:3]),np.linalg.norm(bg[:3]),np.linalg.norm(body[:3])/np.linalg.eigvalsh(R[:3,:3]).min(),1e-30); rs=max(np.linalg.norm(q[3:]),np.linalg.norm(bg[3:]),1e-30)/a
    relax=np.linalg.eigvalsh(M[:3,:3]).min()/np.linalg.eigvalsh(R[:3,:3]).max(); dt=min(.01,.1*b/ts,.02/rs,.5*relax)
    active=geom.contacts(x,p,a,b,(ts+a*rs)*dt+1e-5*b); J,gaps,frames=s41._prepare_geometry(active,a)
    re=s42.finite_re.reynolds_number(q[:3]-bg[:3],rf,visc,2*(a*b*b)**(1/3)); mult=s42.finite_re.inertial_multiplier(re,s42.finite_re.prolate_sphericity(a,b)); D=R.copy(); D[:3,:3]*=mult
    system=M/dt+D+LUB; mobility=np.linalg.inv(system); free=mobility@(M@q/dt+D@bg+body)
    return source,inputs,free,mobility,J,np.array(gaps),dt,mu
def main():
    out=ROOT/"stage49_evaluations"/"direct_contact_seed_diagnostic_01"; out.mkdir(parents=True,exist_ok=False)
    source,inputs,vfree,mobility,J,gaps,dt,mu=build(); A=J@mobility@J.T; z=J@vfree; n=len(gaps); scale=max(np.linalg.norm(vfree),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(n)]); scales=np.repeat(steps,3)
    for k in range(n): scales[3*k]=A[3*k,3*k]
    def projection(ft,vt,step,limit):
        x=ft-vt/step; return x*min(1.,limit/max(np.linalg.norm(x),1e-300))
    def exact_residual(force):
        vel=z+A@force; value=0.
        for k in range(n):
            i=3*k; value=max(value,abs(min(A[i,i]*force[i],vel[i]+gaps[k]/dt)))
            value=max(value,np.linalg.norm(force[i+1:i+3]-projection(force[i+1:i+3],vel[i+1:i+3],steps[k],mu*force[i]))*steps[k])
        return value/scale
    force=np.zeros(3*n); trace=[]
    for it in range(25000):
        for k in range(n):
            i=3*k; vn=z[i]+A[i]@force+gaps[k]/dt; force[i]=max(0.,force[i]-vn/A[i,i]); vt=z[i+1:i+3]+A[i+1:i+3]@force
            force[i+1:i+3]=projection(force[i+1:i+3],vt,steps[k],mu*force[i])
        if it in (0,9,99,999,9999,24999): trace.append({"iteration":it+1,"residual":exact_residual(force)})
    def equations(u):
        f=u/scales; vel=z+A@f; r=np.empty_like(u)
        for k in range(n):
            i=3*k; vn=vel[i]+gaps[k]/dt; r[i]=np.hypot(u[i],vn)-u[i]-vn
            r[i+1:i+3]=u[i+1:i+3]-steps[k]*projection(f[i+1:i+3],vel[i+1:i+3],steps[k],mu*f[i])
        return r/scale
    u0=force*scales; lower=np.full(3*n,-np.inf); upper=np.full(3*n,np.inf); lower[::3]=0
    trials=[]
    for method in ("trf","dogbox"):
        sol=least_squares(equations,u0,bounds=(lower,upper),method=method,xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=50000,x_scale="jac")
        trials.append({"method":method,"success":bool(sol.success),"nfev":int(sol.nfev),"message":sol.message,
            "equation_inf":float(np.linalg.norm(equations(sol.x),np.inf)),"exact_residual":float(exact_residual(sol.x/scales)),"force":(sol.x/scales).tolist()})
    sol=root(equations,u0,method="lm",options={"ftol":1e-14,"xtol":1e-14,"gtol":1e-14,"maxiter":50000})
    trials.append({"method":"root_lm","success":bool(sol.success),"nfev":int(sol.nfev),"message":str(sol.message),
        "equation_inf":float(np.linalg.norm(equations(sol.x),np.inf)),"exact_residual":float(exact_residual(sol.x/scales)),"force":(sol.x/scales).tolist(),
        "minimum_normal_force":float(np.min((sol.x/scales)[::3]))})
    passed=any(t["exact_residual"]<=1e-10 and min(t["force"][::3])>=0 for t in trials)
    record={"passed":passed,"pgs_trace":trace,"trials":trials,"dt_s":dt,"gaps_m":gaps.tolist(),
        "input_hashes":{str(p.resolve()):sha(p) for p in (*inputs,source)},"source_hashes":{str(Path(__file__).resolve()):sha(__file__)},
        "scope":"direct-solver seed/method diagnostic; no trajectory claim"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps({"status":"complete_passed" if passed else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":passed,"pgs_trace":trace,"trials":[{k:v for k,v in t.items() if k not in ("force",)} for t in trials]},indent=2))
    if not passed: raise SystemExit(1)
if __name__=="__main__": main()
