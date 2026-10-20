"""Necessary-condition screen, NOT a proof of original-gate infeasibility.

Normal open/closed modes, original equilibrium and an outer polygonal Coulomb
cone are tested. Tangential maximum dissipation is deliberately omitted: a
feasible relaxation need not be an admissible contact step. No trajectories.
"""
from pathlib import Path
import itertools, os, traceback
import numpy as np
from scipy.optimize import linprog
import authenticate_failed_system_v1 as source
job,api,ROOT=source.job,source.api,source.ROOT
OUT=ROOT/'stage210_evaluations/three_contact_failure_20261001/normal_active_set_screen_01'


def screen(s,closed):
    v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    dt,mu=s['dt_s'],s['friction'];B=np.linalg.inv(M)
    fs=max(np.linalg.norm(B@v),1e-30);qs=max(np.max(abs(g/dt)),1e-30)
    # Variables q/qs followed by f/fs. Use force balance instead of forming
    # an ill-conditioned 9x9 contact matrix.
    E=[np.r_[B[i]*qs/fs,-J.T[i]] for i in range(6)];b=list(B@v/fs)
    G=[];h=[]
    for k in range(3):
        i=3*k
        normal=np.zeros(15);normal[6+i]=-1.;G.append(normal);h.append(0.)
        if closed[k]:E.append(np.r_[J[i],np.zeros(9)]);b.append(-g[k]/dt/qs)
        else:
            for c in (i,i+1,i+2):
                row=np.zeros(15);row[6+c]=1.;E.append(row);b.append(0.)
            G.append(np.r_[-J[i],np.zeros(9)]);h.append(g[k]/dt/qs)
        for angle in np.linspace(0,2*np.pi,16,endpoint=False):
            row=np.zeros(15);row[6+i]=-mu;row[6+i+1]=np.cos(angle);row[6+i+2]=np.sin(angle)
            G.append(row);h.append(0.)
    E=np.asarray(E);b=np.asarray(b);G=np.asarray(G);h=np.asarray(h)
    lengths=np.linalg.norm(E,axis=1);E/=lengths[:,None];b/=lengths
    sol=linprog(np.zeros(15),A_eq=E,b_eq=b,A_ub=G,b_ub=h,bounds=[(None,None)]*15,
                method='highs',options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9,'time_limit':10.})
    r=dict(closed_contacts=list(closed),lp_status=int(sol.status),message=sol.message,
           polygon_planes=16,necessary_relaxation_feasible=bool(sol.success),proof_of_original_gate_infeasibility=False)
    if sol.success:
        q=sol.x[:6]*qs;f=sol.x[6:]*fs
        r.update(candidate_velocity=q.tolist(),candidate_force=f.tolist(),maximum_equilibrium_error=float(np.max(abs(E@sol.x-b))),
                 maximum_linear_inequality_violation=float(np.max(G@sol.x-h)),
                 exact_disk_cone_excess=float(max(np.linalg.norm(f[3*k+1:3*k+3])-mu*f[3*k] for k in range(3))),
                 normal_next_velocities=(J[::3]@q+g/dt).tolist())
    return r


def run():
    d=api.read(job.DESIGN);job.verify(d);w=api.read(source.WORK);assert w['maximum_new_trajectory_steps']==0
    fp=source.OUT/'failed_systems.json';proof=api.read(source.OUT/'results.json')
    assert api.sha(fp)==proof['failed_systems_sha256']
    systems=api.read(fp)['failed_inner_systems'][:3]
    inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp)}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0,maximum_lp_calls=24))
    try:
        rows=[]
        for item in systems:
            s=item['system'];assert api.digest(s)==item['system_sha256']
            modes=[screen(s,m) for m in itertools.product((False,True),repeat=3)]
            rows.append(dict(system_sha256=item['system_sha256'],dt_s=s['dt_s'],modes=modes))
            print('NECESSARY_MODES',s['dt_s'],[(z['closed_contacts'],z['lp_status']) for z in modes],flush=True)
        api.verify_mapping(inputs)
        r=dict(new_trajectory_steps=0,inputs=inputs,systems=rows,no_repair_installed=True,
          claim='Numerical LP necessary-condition screen of exact ideal open/closed normal modes and relaxed outer polygon Coulomb cones. Omits tangential maximum dissipation. Feasibility is not an admissible step, numerical infeasibility is not an exact certificate or a proof about all tolerance-admitted original-gate candidates.')
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json')))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
