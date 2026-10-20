"""Zero-step diagnostic coordinate-scale/seed coverage; original equations."""
from pathlib import Path
import inspect,os,time
import numpy as np
import probe_eliminated_modes_v1 as parent
job,api=parent.job,parent.api;BASE=parent.BASE;OUT=BASE/'multiscale_sliding_01'


def run():
    work=api.read(parent.q.WORK);api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work clock')
    source=inspect.getsource(parent.probe)
    replacements={
        'qs=max(np.max(np.abs(g/dt)),vs*1e-15)':'qs=vs',
        'sorted(product([1,2],repeat=3),key=lambda m:sum(x==2 for x in m))':'[(2,2,2)]',
        'seeds += [rng.normal(size=width) for _ in range(12)]':'seeds += [rng.normal(size=width)*scale for scale in (1e-7,1e-5,1e-3,1e-1,1.,10.) for _ in range(12)]'}
    for old,new in replacements.items():
        api.require(source.count(old)==1,'exact diagnostic coordinate replacement');source=source.replace(old,new)
    namespace=dict(parent.probe.__globals__);exec(compile(source,str(Path(__file__))+'::zero_step_probe','exec'),namespace);probe=namespace['probe']
    systems=api.read(BASE/'contact_diagnosis_01/results.json')['captured_systems'];old=api.read(BASE/'primary_gate_02/results.json')['reports'][1:]
    job.verify(api.read(job.DESIGN));OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(p):api.sha(p) for p in (Path(__file__),Path(parent.__file__),parent.q.WORK,BASE/'contact_diagnosis_01/results.json',BASE/'primary_gate_02/results.json')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,
         'exact_replacements':replacements,'max_systems':3,'max_modes_per_system':1,'max_seeds_per_mode':82,'max_nfev_per_call':1000})
    reports=[]
    with job.parent.fix.scope():
        for i in [0,1,3]:
            api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work cutoff');start=time.perf_counter();s=systems[i]
            modes=probe(s,np.array(old[i]['candidates'][0]['force']));passed=any(c['accepted'] for m in modes for c in m.get('candidates',[]))
            reports.append({'index':i,'input_sha256':api.digest(s),'modes':modes,'passed':passed,'seconds':time.perf_counter()-start})
            print('MULTISCALE_SLIDING',i,passed,flush=True)
    api.verify_mapping(inputs);job.verify(api.read(job.DESIGN))
    job.commit(OUT/'results.json',{'new_trajectory_steps':0,'inputs':inputs,'systems':reports,'original_gates_unchanged':True})
    job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})


if __name__=='__main__':run()
