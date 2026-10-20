"""Bounded zero-trajectory probes of the authenticated failed two-contact solve."""
from pathlib import Path
import copy,json,os,time,traceback
import numpy as np
import authenticate_failed_system_v1 as source
frozen,job,api,ROOT=source.frozen,source.job,source.api,source.ROOT
candidate=frozen.pre.repair
scalar=candidate.algebra
eliminated=candidate.eliminated
OUT=ROOT/'stage206_evaluations/contact_failure_20260930/held_diagnosis_01'

def run():
    w=api.read(source.WORK);d=api.read(job.DESIGN);job.verify(d)
    fp=source.OUT/'failed_systems.json';proof=api.read(source.OUT/'results.json')
    api.require(api.read(source.OUT/'completion.json')['results_sha256']==api.sha(source.OUT/'results.json'),'authentication seal')
    api.require(proof['evidence_authentication_passed'] and not proof['numerical_gate_passed'] and api.sha(fp)==proof['failed_systems_sha256'],'failed system binding')
    systems=api.read(fp)['failed_inner_systems'];api.require(len(systems)<=w['maximum_held_systems'],'bounded held systems')
    stop=time.time()+1800
    inputs={str(p):api.sha(p) for p in (source.WORK,job.DESIGN,Path(__file__),Path(candidate.__file__),Path(scalar.__file__),Path(eliminated.__file__),fp,source.OUT/'results.json')}
    OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs,maximum_wall_seconds=1800))
    reports=[]
    try:
        with job.parent.fix.scope():
            gate=candidate.algebra.job.fast.gate;original_finish=gate._finish
            for item in systems:
                s=item['system'];api.require(api.digest(s)==item['system_sha256'],'exact held input')
                args=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]+[s['dt_s'],s['friction'],s['tolerance'],s['maxiter'],stop]
                observed=[]
                def finish(*values):
                    v,M,J,f,z,A,g,dt,mu,steps,it,name,extra=values
                    row=dict(solver=name,force=np.asarray(f).tolist(),residual=float(gate._residual(f,z,A,g,dt,mu,steps)/max(np.linalg.norm(v),1e-15)))
                    try:
                        answer=original_finish(*values)
                    except RuntimeError as error:
                        row.update(accepted=False,error=str(error));raise
                    else:
                        row.update(accepted=True,velocity=answer[0].tolist(),health=answer[1]);return answer
                    finally:observed.append(row)
                gate._finish=finish
                try:
                    try:
                        q,h=candidate.solve(*args);baseline=dict(accepted=True,velocity=q.tolist(),health=h)
                    except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as error:
                        baseline=dict(accepted=False,error=repr(error))
                    modes=scalar.solve_modes(s,stop)
                    allc=[c for m in modes for c in m['candidates']]
                    near=[np.asarray(c['force']) for c in sorted(allc,key=lambda c:c['residual'])[:3]]
                    alternatives=eliminated.candidates(s,near,stop)
                finally:gate._finish=original_finish
                row=dict(system_sha256=item['system_sha256'],baseline=baseline,scalar_modes=modes,eliminated_modes=alternatives,
                         finalizer_candidates=observed,rank=int(np.linalg.matrix_rank(args[2])),singular_values=np.linalg.svd(args[2],compute_uv=False).tolist(),
                         mobility_condition=float(np.linalg.cond(args[1])),vfree_norm=float(np.linalg.norm(args[0])))
                reports.append(row)
                job.commit(OUT/('system_%02d.json'%(len(reports)-1)),row)
                print('HELD_DIAGNOSIS',baseline,'best_residual',min(c['residual'] for c in observed),flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,systems=reports,original_gates_unchanged=True,
                    claim='Held equations only. Original Stage205 failure retained; no trajectory repair or production qualification.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise

if __name__=='__main__':run()
