"""Diagnose and solve the exact Stage50 medium terminal contact state."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import root
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage37_staging"),str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging")]
import transport_contact as mechanics
import matrix_case_v1,geometry_exact_v1,trajectory_optimized_v1 as trajectory
import inertial_contact_cold_optimized_v1 as s41,inertial_contact_robust_v1 as s42
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=ROOT/"stage52_evaluations"/"terminal_contact_diagnostic_01"; out.mkdir(parents=True,exist_ok=False)
    source=ROOT/"stage50_runs"/"release_pilot_20260912"/"medium_01"/"results.json"; rec=json.loads(source.read_text()); saved=rec["result"]
    field,old,L,dx,inputs=matrix_case_v1.load(2); geom=geometry_exact_v1.GrainGeometry.from_geometry(old)
    x=np.array(saved["position_m"]); p=np.array(saved["orientation"]); q=np.array(saved["velocity_generalized"])
    a,b,visc,rp,rf=2e-4,5e-5,.001002,1380.,998.2; uf,grad=field.sample(x)
    bg,_=mechanics.free_motion(p,grad,uf,a,b,visc,1,1,[0,0,0]); R=s42.stokes_generalized_resistance(p,a,b,visc)
    M,_=s42.generalized_mass_matrix(p,a,b,rp,rf,1); M[3:,3:]=0; volume=4*np.pi*a*b*b/3; body=np.r_[(rp-rf)*volume*np.array([0,0,-9.80665]),np.zeros(3)]
    near=trajectory.enrich(geom,geom.contacts(x,p,a,b,.2*geom.r.max())); LUB,_=trajectory.lubrication_matrix(near,p,a,b,a,visc,.2,.01)
    ts=max(np.linalg.norm(q[:3]),np.linalg.norm(bg[:3]),np.linalg.norm(body[:3])/np.linalg.eigvalsh(R[:3,:3]).min(),1e-30); rs=max(np.linalg.norm(q[3:]),np.linalg.norm(bg[3:]),1e-30)/a
    relax=np.linalg.eigvalsh(M[:3,:3]).min()/np.linalg.eigvalsh(R[:3,:3]).max(); remaining=rec["horizon_s"]-saved["time_s"]
    dt=min(.01,remaining,.05*b/ts,.02/rs,.25*relax); active=geom.contacts(x,p,a,b,(ts+a*rs)*dt+1e-5*b)
    J,gaps,frames=s41._prepare_geometry(active,a); gaps=np.array(gaps); re=s42.finite_re.reynolds_number(q[:3]-bg[:3],rf,visc,2*(a*b*b)**(1/3))
    mult=s42.finite_re.inertial_multiplier(re,s42.finite_re.prolate_sphericity(a,b)); D=R.copy(); D[:3,:3]*=mult
    system=M/dt+D+LUB; mobility=np.linalg.inv(system); vfree=mobility@(M@q/dt+D@bg+body); A=J@mobility@J.T; z=J@vfree
    n=len(gaps); scale=max(np.linalg.norm(vfree),1e-15); steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(n)])
    scales=np.repeat(steps,3)
    for k in range(n): scales[3*k]=A[3*k,3*k]
    def project(ft,vt,step,limit):
        trial=ft-vt/step; return trial*min(1.,limit/max(np.linalg.norm(trial),1e-300))
    def exact(force,mu):
        velocity=z+A@force; value=0.
        for k in range(n):
            i=3*k; value=max(value,abs(min(A[i,i]*force[i],velocity[i]+gaps[k]/dt)))
            value=max(value,np.linalg.norm(force[i+1:i+3]-project(force[i+1:i+3],velocity[i+1:i+3],steps[k],mu*force[i]))*steps[k])
        return value/scale
    def equations(u,mu):
        force=u/scales; velocity=z+A@force; result=np.empty_like(u)
        for k in range(n):
            i=3*k; vn=velocity[i]+gaps[k]/dt; result[i]=np.hypot(u[i],vn)-u[i]-vn
            result[i+1:i+3]=u[i+1:i+3]-steps[k]*project(force[i+1:i+3],velocity[i+1:i+3],steps[k],mu*force[i])
        return result/scale
    force=np.zeros(3*n)
    for iteration in range(25000):
        for k in range(n):
            i=3*k; vn=z[i]+A[i]@force+gaps[k]/dt; force[i]=max(0.,force[i]-vn/A[i,i]); vt=z[i+1:i+3]+A[i+1:i+3]@force
            force[i+1:i+3]=project(force[i+1:i+3],vt,steps[k],.3*force[i])
    trials=[]
    for name,seed in (("pgs",force*scales),("zero",np.zeros(3*n))):
        solved=root(lambda u:equations(u,.3),seed,method="lm",options={"ftol":1e-14,"xtol":1e-14,"gtol":1e-14,"maxiter":200000})
        f=solved.x/scales; trials.append({"name":name,"success":bool(solved.success),"nfev":int(solved.nfev),"equation_inf":float(np.linalg.norm(equations(solved.x,.3),np.inf)),
            "exact_residual":float(exact(f,.3)),"min_normal":float(f[::3].min()),"force":f.tolist(),"message":str(solved.message)})
    u=force*scales; continuation=[]
    for mu in np.linspace(0,.3,13):
        solved=root(lambda y:equations(y,float(mu)),u,method="lm",options={"ftol":1e-14,"xtol":1e-14,"gtol":1e-14,"maxiter":100000})
        u=solved.x; f=u/scales; continuation.append({"mu":float(mu),"success":bool(solved.success),"nfev":int(solved.nfev),
            "equation_inf":float(np.linalg.norm(equations(u,float(mu)),np.inf)),"exact_residual":float(exact(f,float(mu))),"min_normal":float(f[::3].min())})
    final_force=u/scales; final=continuation[-1]; passed=final["exact_residual"]<=1e-10 and final["min_normal"]>=0
    record={"passed":bool(passed),"active_contact_count":n,"gaps_m":gaps.tolist(),"dt_s":dt,"remaining_s":remaining,
        "delassus_condition_number":float(np.linalg.cond(A)),"pgs_terminal_residual":float(exact(force,.3)),"trials":trials,
        "continuation":continuation,"continuation_final_force":final_force.tolist(),"input_hashes":{str(p.resolve()):sha(p) for p in (*inputs,source)},
        "source_hashes":{str(Path(__file__).resolve()):sha(__file__)},"scope":"terminal contact solver diagnostic; no trajectory claim"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if passed else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":passed,"contacts":n,"gaps_m":gaps.tolist(),"dt_s":dt,"condition":record["delassus_condition_number"],
        "pgs_residual":record["pgs_terminal_residual"],"trials":[{k:v for k,v in t.items() if k!="force"} for t in trials],"continuation":continuation},indent=2))
    if not passed: raise SystemExit(1)
if __name__=="__main__": main()
