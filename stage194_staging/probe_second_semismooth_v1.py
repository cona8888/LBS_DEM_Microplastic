"""Zero-step analytic complementarity search on the second failure family."""
from pathlib import Path
import os,time
import numpy as np
from scipy.optimize import least_squares
import probe_analytic_contact_v1 as equations
import qualify_sliding_projection_v1 as tests
q=tests.q;job,api=q.job,q.api;BASE=tests.BASE;OUT=BASE/'second_semismooth_probe_01'

def run():
    end=min(job.policy.utc(api.read(q.WORK)['work_end_utc']).timestamp(),time.time()+180)
    api.require(time.time()<end,'work clock');job.verify(api.read(job.DESIGN))
    source=BASE/'dispatch_failure_audit_01/failure_details.json';systems=api.read(source)['captured_systems']
    candidates=api.read(BASE/'mixed_projection_probe_01/results.json')['reports'];reduced=api.read(BASE/'second_failure_candidates_01/results.json')['reports']
    paths=[Path(__file__),source,q.WORK,Path(equations.__file__),BASE/'mixed_projection_probe_01/results.json',BASE/'second_failure_candidates_01/results.json']
    inputs={str(x):api.sha(x) for x in paths};OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'max_wall_seconds':180,'max_nfev_per_call':2000,'max_seeds_per_system':14})
    reports=[]
    with job.prior.p.hot.scope(),job.parent.fix.scope():
        for i,s in enumerate(systems):
            a=tests.args(s);v,M,J,g,dt,mu,_,_=a;both,A,z,steps,scales,vs=equations.system(v,M,J,g,dt,mu)
            force_seeds=[np.zeros(9)]
            for r in reduced:
                if r['index']==i:force_seeds.append(np.asarray(min(r['candidates'],key=lambda c:c['residual'])['force']))
            for mode in candidates[i]['modes']:
                if mode['scale']=='gap' and len(force_seeds)<14:
                    usable=[c for c in mode['candidates'] if c.get('cost') is not None]
                    if usable:force_seeds.append(np.asarray(min(usable,key=lambda c:c['cost'])['force']))
            results=[]
            for k,f in enumerate(force_seeds):
                api.require(time.time()<end,'work clock');start=time.perf_counter()
                opt=least_squares(lambda y:both(y)[0],f*scales/vs,jac=lambda y:both(y)[1],method='trf',xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=2000,x_scale='jac')
                ff=opt.x*vs/scales;entry={'seed':k,'nfev':int(opt.nfev),'cost':float(opt.cost),'force':ff.tolist(),'original_residual':float(job.fast.gate._residual(ff,z,A,g,dt,mu,steps)/vs)}
                try:
                    answer=job.fast.gate._finish(v,M,J,ff,z,A,g,dt,mu,steps,int(opt.nfev),'stage194_second_semismooth_probe',{})
                    audit,row=tests.audit(a,answer)
                except RuntimeError as e:entry.update(passed=False,error=str(e))
                else:entry.update(passed=True,audit=audit,saved_system=row)
                entry['seconds']=time.perf_counter()-start;results.append(entry)
                if entry['passed']:break
            passed=any(c['passed'] for c in results);reports.append({'index':i,'passed':passed,'candidates':results});job.commit(OUT/f'system_{i:02d}.json',reports[-1])
            print('SECOND_SEMISMOOTH',i,passed,len(results),min(c['original_residual'] for c in results),flush=True)
    api.verify_mapping(inputs);job.commit(OUT/'results.json',{'new_trajectory_steps':0,'inputs':inputs,'reports':reports});job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})

if __name__=='__main__':run()
