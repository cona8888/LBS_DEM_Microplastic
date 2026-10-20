"""Nonadvancing gate-candidate diagnosis of the next three failed systems."""
from pathlib import Path
import copy,os,time
import numpy as np
import qualify_sliding_projection_v1 as tests
import sliding_projection_repair_v3 as projection
q=tests.q;job,api=q.job,q.api;BASE=tests.BASE;OUT=BASE/'second_failure_candidates_01'

def run():
    end=job.policy.utc(api.read(q.WORK)['work_end_utc']).timestamp();api.require(time.time()<end,'work clock');job.verify(api.read(job.DESIGN))
    source=BASE/'dispatch_failure_audit_01/failure_details.json';s=api.read(source)['captured_systems'];OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(x):api.sha(x) for x in [source,Path(__file__),Path(projection.__file__),q.WORK]}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'maximum_systems':3,'solvers_per_system':2})
    reports=[];job.parent.b.old.parent.configure()
    with job.prior.p.hot.scope(),job.parent.fix.scope():
        gate=job.fast.gate;original=gate._finish
        for i,system in enumerate(s):
            for name,solver in [('old_reduced',job.fast.solve),('projection',lambda *a:projection.solve(*a,stop_epoch=end))]:
                candidates=[]
                def observed(v,M,J,f,z,A,g,dt,mu,steps,iterations,solvername,extra):
                    vs=max(np.linalg.norm(v),1e-15);fs=max(np.linalg.norm(f),1e-30)
                    c={'solver':solvername,'extra':copy.deepcopy(extra),'force':f.tolist(),'residual':float(gate._residual(f,z,A,g,dt,mu,steps)/vs),
                       'cone_excess_relative':float(max(np.linalg.norm(f[3*k+1:3*k+3])-mu*f[3*k] for k in range(3))/fs),'minimum_normal_relative':float(min(f[::3])/fs)}
                    try:answer=original(v,M,J,f,z,A,g,dt,mu,steps,iterations,solvername,extra)
                    except Exception as error:c.update(accepted=False,error=repr(error));raise
                    else:c.update(accepted=True);return answer
                    finally:candidates.append(c)
                gate._finish=observed;entry={'index':i,'solver':name,'input_sha256':api.digest(system)};start=time.perf_counter()
                try:
                    answer=solver(*tests.args(system));audit,_=tests.audit(tests.args(system),answer);entry.update(passed=True,audit=audit)
                except Exception as e:entry.update(passed=False,error=repr(e))
                finally:gate._finish=original
                entry.update(candidates=candidates,seconds=time.perf_counter()-start);reports.append(entry)
                print('SECOND_FAILURE',i,name,entry['passed'],len(candidates),min((c['cone_excess_relative'] for c in candidates),default=None),flush=True)
    api.verify_mapping(inputs)
    job.commit(OUT/'results.json',{'new_trajectory_steps':0,'reports':reports,'inputs':inputs,'original_gates_unchanged':True})
    job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})

if __name__=='__main__':run()
