"""Zero-step held-contact A/P/E/P comparison; affinity applies only to self."""
from pathlib import Path
import copy, ctypes, os, sys, time, traceback
import numpy as np
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage194_staging'))
import early_semismooth_dispatch_v1 as repair
import constant_analytic_pair_v1 as opt
import windows_cpu_topology_v1 as topology
q=repair.prior.q;job,api=q.job,q.api
WORK=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/contract_01.json'
DESIGN=WORK.with_name('owned_cpu_benchmark_01.json')
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/owned_cpu_benchmark_01'
FIX=ROOT/'stage194_evaluations/evidence_repair_20260924/early_semismooth_qualification_01/fixtures.json'
PROFILE=ROOT/'stage196_runs/deadline_recovery_20260925/segment_profile_01/record.json.xz'
COMPARE=ROOT/'stage196_evaluations/deadline_recovery_20260925/constant_pair_01/results.json'

def run():
    work=api.read(WORK);end=job.policy.utc(work['work_end_utc']).timestamp();api.require(time.time()<end,'work clock')
    for p in psutil.process_iter(['pid','name','cmdline']):
        if p.pid!=os.getpid() and 'python' in (p.info['name'] or '').lower():
            api.require('matdem_microplastic' not in ' '.join(p.info['cmdline'] or []).lower(),'no concurrent benchmark or simulation')
    job.verify(api.read(job.DESIGN));result=api.read(COMPARE);api.require(result['passed'],'pure arithmetic prerequisite')
    trials=[x['fixture']['contact_trial_trace']['detailed_trials'][0] for x in api.read(FIX)]
    rec=q.independent_file(PROFILE,api.read(PROFILE.with_suffix('.seal.json'))['design_sha256']);trials+=rec['contact_trial_trace']['detailed_trials']
    worst=sorted(result['held_comparisons'],key=lambda x:x['candidate_seconds'],reverse=True)[:12]
    selected=sorted(set([x['index'] for x in worst]+list(range(0,462,42))))
    process=psutil.Process();original=process.cpu_affinity();sets=topology.cpu_sets()
    available=[x for x in sets if x['group']==0 and not x['allocated'] and x['logical'] in original]
    classes=sorted(set(x['efficiency_class'] for x in available));api.require(len(classes)==2,'two measured CPU classes')
    pcore=max(x['logical'] for x in available if x['efficiency_class']==classes[-1] and x['logical']%2==0)
    ecore=max(x['logical'] for x in available if x['efficiency_class']==classes[0])
    inputs={str(p):api.sha(p) for p in [WORK,Path(__file__),Path(opt.__file__),Path(topology.__file__),FIX,PROFILE,PROFILE.with_suffix('.seal.json'),COMPARE]}
    job.commit(DESIGN,{'stage':'Stage196 owned-process CPU scheduling benchmark','inputs':inputs,'cpu_sets':sets,'selected_held_trial_indices':selected,
        'affinity_modes':[original,[pcore],[ecore],[pcore]],'maximum_outer_calls':4*len(selected),'new_trajectory_steps':0,'no_global_setting_changes':True})
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'protocol_sha256':api.sha(DESIGN)})
    runtime=job.parent.engine.runtime;job.parent.b.old.parent.configure();outputs={};reports=[]
    current=ctypes.WinDLL('kernel32').GetCurrentProcessorNumber;current.restype=ctypes.c_uint
    try:
        for label,mask in [('default',original),('P1',[pcore]),('E',[ecore]),('P2',[pcore])]:
            process.cpu_affinity(mask);api.require(process.cpu_affinity()==mask,'self affinity binding')
            samples=[];times=[]
            for index in selected:
                api.require(time.time()<end,'work clock');t=trials[index]
                job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True
                runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
                start=time.perf_counter();samples.append(int(current()))
                with opt.scope(True),repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,work['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True):
                    ans=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
                times.append(time.perf_counter()-start)
                val=(ans[0].tobytes(),{k:v for k,v in ans[1].items() if k!='certificate_seconds'})
                if label=='default':outputs[index]=val
                else:api.require(val==outputs[index],'exact scheduling-independent answer')
            row={'label':label,'affinity':mask,'observed_logical_cpus':samples,'seconds':sum(times),'per_trial_seconds':times,'exact':True}
            reports.append(row);job.commit(OUT/(label+'.json'),row)
            print('OWNED_CPU',label,mask,round(sum(times),3),sorted(set(samples)),flush=True)
        api.verify_mapping(inputs)
        report={'passed':True,'inputs':inputs,'new_trajectory_steps':0,'reports':reports,'default_over_P':reports[0]['seconds']/max(reports[1]['seconds'],reports[3]['seconds']),
            'E_over_P':reports[2]['seconds']/max(reports[1]['seconds'],reports[3]['seconds']),'production_authorized':False,'no_global_setting_changes':True}
        job.commit(OUT/'results.json',report);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0,'reports':reports});raise
    finally:
        process.cpu_affinity(original)
        job.commit(OUT/'affinity_restored.json',{'pid':os.getpid(),'affinity':process.cpu_affinity(),'matches_original':process.cpu_affinity()==original})

if __name__=='__main__':run()
