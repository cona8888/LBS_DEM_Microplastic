"""Profile sealed fallback matrices without advancing any trajectory."""
from pathlib import Path
import os,time
import qualify_sliding_projection_v1 as tests
import sliding_projection_repair_v3 as repair
q=tests.q;job,api=q.job,q.api
BASE=tests.BASE;OUT=BASE/'dispatch_profile_01'
RAW=q.ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01/call_02.json.xz'
PROTOCOL=q.ROOT/'stage194_designs/evidence_repair_20260924/trajectory_qualification_01.json'

def run():
    end=job.policy.utc(api.read(q.WORK)['work_end_utc']).timestamp()
    api.require(time.time()<end,'work clock');p=api.read(PROTOCOL);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    result=api.read(BASE/'trajectory_qualification_01/results.json')
    api.require(result['passed'] and result['artifacts'][str(RAW)]==api.sha(RAW),'sealed healthy local raw')
    raw=q.independent_file(RAW,api.sha(PROTOCOL));OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(x):api.sha(x) for x in (Path(__file__),RAW,PROTOCOL,Path(repair.__file__))}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0})
    rows=[];job.parent.b.old.parent.configure()
    with job.prior.p.hot.scope(),job.parent.fix.scope():
        for i,s in enumerate(raw['fallback_systems']):
            api.require(time.time()<end,'work clock');start=time.perf_counter()
            a=tests.args(s);answer=repair.solve(*a,stop_epoch=end);seconds=time.perf_counter()-start
            audit,row=tests.audit(a,answer)
            import numpy as np
            error=float(np.linalg.norm(answer[0]-np.asarray(s['velocity']))/max(np.linalg.norm(a[0]),1e-15))
            rows.append({'index':i,'source_sha256':api.digest(s),'seconds':seconds,'recorded_seconds':s.get('wall_s'),
                         'normalized_velocity_difference':error,'exact_reactions':answer[1]['reactions']==s['health']['reactions'],
                         'audit':audit,'health':answer[1]})
            print('PROFILE',i,round(seconds,6),s.get('wall_s'),error,flush=True)
    api.verify_mapping(inputs);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    r={'passed':all(x['normalized_velocity_difference']<=1e-10 for x in rows),'new_trajectory_steps':0,'rows':rows,
       'direct_seconds':sum(x['seconds'] for x in rows),'recorded_seconds':sum(x['recorded_seconds'] or 0 for x in rows),
       'inputs':inputs,'claim':'Fixed-system diagnostic timing, not production throughput.'}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('PROFILE_RESULT',r['passed'],r['direct_seconds'],r['recorded_seconds'],flush=True)

if __name__=='__main__':run()
