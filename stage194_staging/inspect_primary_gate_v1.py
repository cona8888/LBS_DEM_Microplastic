"""Capture unmodified final-gate candidates on one frozen failed inner system."""
from pathlib import Path
import copy
import os
import time
import numpy as np
import qualify_failure_codec_v1 as q

job, api = q.job, q.api
OUT = q.ROOT / 'stage194_evaluations/evidence_repair_20260924/primary_gate_01'
SOURCE = q.ROOT / 'stage194_evaluations/evidence_repair_20260924/contact_diagnosis_01/results.json'


def run():
    w = api.read(q.WORK)
    api.require(job.utc() < job.policy.utc(w['work_end_utc']), 'work clock')
    api.require(api.read(SOURCE.parent/'completion.json')['results_sha256'] == api.sha(SOURCE), 'input seal')
    job.verify(api.read(job.DESIGN)); source = api.read(SOURCE); s = source['captured_systems'][0]
    OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT/'launch.json', {'pid': os.getpid(), 'utc': job.utc().isoformat(), 'source_sha256': api.sha(SOURCE),
                                  'script_sha256': api.sha(Path(__file__)), 'new_trajectory_steps': 0, 'maximum_inner_calls': 1})
    candidates = []; gate = job.fast.gate; original = gate._finish
    def observe(v, M, J, f, z, A, g, dt, mu, steps, it, solver, extra):
        scale = max(np.linalg.norm(v), 1e-15); fs = max(np.linalg.norm(f), 1e-30)
        entry = {'solver': solver, 'force': np.asarray(f).tolist(), 'extra': copy.deepcopy(extra),
                 'residual': float(gate._residual(f,z,A,g,dt,mu,steps)/scale),
                 'min_normal_relative': float(min(f[::3])/fs),
                 'cone_excess_relative': float(max(np.linalg.norm(f[3*k+1:3*k+3])-mu*f[3*k] for k in range(len(g)))/fs)}
        try: answer = original(v,M,J,f,z,A,g,dt,mu,steps,it,solver,extra)
        except Exception as error: entry.update(accepted=False,error=repr(error)); raise
        else: entry.update(accepted=True,health=answer[1]); return answer
        finally: candidates.append(entry)
    v, M, J, g = [np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    runtime = job.parent.engine.runtime
    job.parent.b.old.parent.configure(); runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
    gate._finish = observe; start=time.perf_counter(); outcome={}
    try:
        with job.prior.p.hot.scope(), job.parent.fix.scope(), job.deadline.scope(runtime,w['work_end_utc'],True), job.capture.scope(runtime,True), runtime.repair_scope():
            try: answer=runtime.probe.RECOVERY.portfolio._solve(v,M,J,g,s['dt_s'],s['friction'],s['tolerance'],s['maxiter'])
            except Exception as error: outcome={'accepted':False,'error':repr(error)}
            else: outcome={'accepted':True,'velocity':answer[0].tolist(),'health':answer[1]}
    finally: gate._finish=original
    job.verify(api.read(job.DESIGN))
    result={'new_trajectory_steps':0,'source_sha256':api.sha(SOURCE),'outcome':outcome,'candidates':candidates,
            'wall_s':time.perf_counter()-start,'input':s,'original_gates_unchanged':True}
    job.commit(OUT/'results.json',result); job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print('PRIMARY_GATE_CAPTURE',outcome,len(candidates),flush=True)


if __name__=='__main__':run()
