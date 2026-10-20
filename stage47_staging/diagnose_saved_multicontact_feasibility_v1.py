"""Classify the exact Stage43 multi-contact failure at its last accepted state."""
import hashlib, json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage37_staging"),str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging")]
import transport_contact as mechanics
import matrix_case_v1, geometry_exact_v1
import trajectory_optimized_v1 as trajectory
import inertial_contact_cold_optimized_v1 as stage41
import inertial_contact_robust_v1 as stage42

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    out=ROOT/"stage47_evaluations"/"saved_multicontact_feasibility_01"; out.mkdir(parents=True,exist_ok=False)
    source=ROOT/"stage43_runs"/"release_pilot_20260912"/"pilot_01"/"coarse.json"
    saved=json.loads(source.read_text())["result"]
    field,old_geometry,length,spacing,inputs=matrix_case_v1.load(2)
    geometry=geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    x=np.asarray(saved["position_m"],float); p=np.asarray(saved["orientation"],float); q=np.asarray(saved["velocity_generalized"],float)
    a,b=2e-4,5e-5; viscosity=0.001002; rho_p=1380.; rho_f=998.2; dtmax=0.01
    fluid_velocity,gradient=field.sample(x)
    background,_=mechanics.free_motion(p,gradient,fluid_velocity,a,b,viscosity,1.,1.,[0,0,0])
    resistance=stage42.stokes_generalized_resistance(p,a,b,viscosity)
    mass,_=stage42.generalized_mass_matrix(p,a,b,rho_p,rho_f,1.); mass[3:,3:]=0
    volume=4*np.pi*a*b*b/3; body=np.r_[(rho_p-rho_f)*volume*np.array([0,0,-9.80665]),np.zeros(3)]
    near=trajectory.enrich(geometry,geometry.contacts(x,p,a,b,0.2*geometry.r.max()))
    lubrication,_=trajectory.lubrication_matrix(near,p,a,b,a,viscosity,0.2,0.01)
    translation=max(np.linalg.norm(q[:3]),np.linalg.norm(background[:3]),
        np.linalg.norm(body[:3])/max(np.linalg.eigvalsh(resistance[:3,:3]).min(),1e-30),1e-30)
    rotation=max(np.linalg.norm(q[3:]),np.linalg.norm(background[3:]),1e-30)/a
    relax=np.linalg.eigvalsh(mass[:3,:3]).min()/np.linalg.eigvalsh(resistance[:3,:3]).max()
    dt=min(dtmax,0.1*length/1e-4,0.1*b/translation,0.02/rotation,0.5*relax)
    reach=(translation+a*rotation)*dt+1e-5*b
    active=geometry.contacts(x,p,a,b,reach)
    J,gaps,frames=stage41._prepare_geometry(active,a)
    Jn=J[::3]; gaps=np.asarray(gaps)
    constraints={"type":"ineq","fun":lambda v:Jn@v+gaps/dt}
    feasible=minimize(lambda v:0.5*float(v@v),np.zeros(6),jac=lambda v:v,
        constraints=constraints,method="SLSQP",options={"ftol":1e-14,"maxiter":2000})
    reynolds=stage42.finite_re.reynolds_number(q[:3]-background[:3],rho_f,viscosity,2*(a*b*b)**(1/3))
    multiplier=stage42.finite_re.inertial_multiplier(reynolds,stage42.finite_re.prolate_sphericity(a,b))
    drag=resistance.copy(); drag[:3,:3]*=multiplier
    system=mass/dt+drag+lubrication; mobility=np.linalg.inv(system)
    free=mobility@(mass@q/dt+drag@background+body)
    solves={}
    for mu in (0.0,0.3):
        try:
            velocity,health=stage41._solve_prepared(free,mobility,J,gaps,dt,mu,1e-10,25000)
            solves[str(mu)]={"converged":True,"health":health,"velocity":velocity.tolist()}
        except RuntimeError as exc:
            solves[str(mu)]={"converged":False,"reason":str(exc)}
    normal_margin=np.asarray(constraints["fun"](feasible.x))
    A=J@mobility@J.T
    checks={"three_active_contacts":len(active)==3,"normal_constraints_feasible":bool(feasible.success and normal_margin.min()>=-1e-10),
        "frictionless_contact_converges":bool(solves["0.0"]["converged"]),
        "frictional_contact_fails":bool(not solves["0.3"]["converged"])}
    classification=("frictional_contact_algorithm_failure_not_normal_geometric_infeasibility"
        if all(checks.values()) else "unresolved_multicontact_classification")
    record={"passed":bool(all(checks.values())),"checks":checks,"classification":classification,"dt_s":dt,
        "active_contacts":[{"grain_id":int(c[0]),"gap_m":float(c[1]),"normal":c[2].tolist(),"lever_m":c[3].tolist()} for c in active],
        "normal_feasibility":{"success":bool(feasible.success),"message":feasible.message,"velocity":feasible.x.tolist(),
            "minimum_constraint_margin_m_s":float(normal_margin.min()),"objective":float(feasible.fun)},
        "delassus_condition_number":float(np.linalg.cond(A)),"solves":solves,
        "input_hashes":{str(path.resolve()):sha(path) for path in (*inputs,source)},
        "source_hashes":{str(Path(__file__).resolve()):sha(__file__),str(Path(stage41.__file__).resolve()):sha(stage41.__file__)},
        "scope":"frozen-pose failure classification; no trajectory or release claim"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"checks":checks,"classification":classification,"dt_s":dt,
        "gaps_m":gaps.tolist(),"minimum_normal_margin":float(normal_margin.min()),"delassus_condition_number":record["delassus_condition_number"],
        "solves":{k:{kk:vv for kk,vv in v.items() if kk in ("converged","reason")} for k,v in solves.items()}},indent=2))
    if not record["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
