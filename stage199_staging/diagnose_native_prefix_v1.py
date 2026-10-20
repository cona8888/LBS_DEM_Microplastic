"""Zero-step sealed first-divergence diagnosis; never advance a trajectory."""
from pathlib import Path
import copy,sys,time
from datetime import timedelta
import numpy as np
import measure_native_prefix_v1 as probe
api,job,q=probe.api,probe.job,probe.q
OUT=probe.OUT.parent/'native_prefix_diagnosis_01'

def diff(a,b,path='',limit=12):
    if type(a)!=type(b):return [{'path':path,'expected':a,'actual':b}]
    if isinstance(a,dict):
        out=[]
        for k in sorted(set(a)|set(b)):
            if k not in a or k not in b:out.append({'path':path+'/'+k,'missing':True})
            else:out.extend(diff(a[k],b[k],path+'/'+k,limit))
            if len(out)>=limit:break
        return out[:limit]
    if isinstance(a,list):
        if len(a)!=len(b):return [{'path':path,'lengths':[len(a),len(b)]}]
        out=[]
        for i,(x,y) in enumerate(zip(a,b)):
            out.extend(diff(x,y,path+'/'+str(i),limit))
            if len(out)>=limit:break
        return out[:limit]
    return [] if a==b else [{'path':path,'expected':a,'actual':b}]

def run():
    probe.verify(api.read(probe.DESIGN));api.require(job.utc()<job.policy.utc(api.read(probe.WORK)['work_end_utc']),'work cutoff')
    OUT.mkdir(parents=True,exist_ok=False)
    sources={str(Path(__file__)):api.sha(__file__)}
    raw=probe.RUN/'serial.json.xz';oracle=probe.ORACLE
    failed=api.read(probe.OUT/'failure.json');account=api.read(raw.with_suffix('.accounting.json'))
    api.require(failed['known_new_accepted_steps']==account['accepted_steps']==3580 and not failed['accepted_step_accounting_unresolved'],'closed failed diagnostic accounting')
    a=q.independent_file(oracle,api.sha(probe.template.old.DESIGN));b=q.independent_file(raw,api.sha(probe.DESIGN))
    row_diff=diff(a['rows'],b['rows']);state_diff=diff(a['result']['checkpoint']['state'],b['result']['checkpoint']['state'])
    first=next((i for i,(x,y) in enumerate(zip(a['rows'],b['rows'])) if x!=y),None)
    print('FIRST_DIVERGENCE',first,row_diff[:3],flush=True)
    ta=a['contact_trial_trace']['detailed_trials'];tb=b['contact_trial_trace']['detailed_trials']
    index=next((i for i,(x,y) in enumerate(zip(ta,tb)) if x['outer_inputs']!=y['outer_inputs']),len(ta))
    indices=sorted(set(max(0,i) for i in (index-2,index-1,index) if i<len(ta)))
    mismatches=[];count=0;candidate=probe.candidate;stop=min(job.utc()+timedelta(minutes=5),job.policy.utc(api.read(probe.WORK)['work_end_utc']))
    original=candidate.trf_no_bounds.__globals__['solve_lsq_trust_region']
    def observe(*args,**kwargs):
        nonlocal count
        ref=candidate.original_trust(*args,**kwargs);got=original(*args,**kwargs);count+=1
        if not all(np.asarray(x).tobytes()==np.asarray(y).tobytes() for x,y in zip(ref,got)):
            mismatches.append({'call':count,'args':[np.asarray(x).tolist() for x in args],'kwargs':kwargs,'expected':[np.asarray(x).tolist() for x in ref],'actual':[np.asarray(x).tolist() for x in got]})
        return got
    job.parent.b.old.parent.configure();runtime=job.parent.engine.runtime
    candidate.trf_no_bounds.__globals__['solve_lsq_trust_region']=observe
    try:
        for i in indices:
            api.require(job.utc()<stop,'bounded held replay')
            job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True;runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
            with candidate.scope('compiled_direct'),candidate.repair.scope(runtime,True,stop.timestamp()),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,stop.isoformat(),True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True):
                job.observer.backend.inertial_contact_step(*copy.deepcopy(ta[i]['outer_inputs']))
    finally:candidate.trf_no_bounds.__globals__['solve_lsq_trust_region']=original
    result={'new_trajectory_steps':0,'failed_trajectory_new_steps':3580,'cumulative_recovery_steps':71232,'remaining_recovery_steps':28768,'first_row_difference_index':first,'row_differences':row_diff,'checkpoint_differences':state_diff,'first_input_difference_trial':index,'held_replay_indices':indices,'trust_calls':count,'trust_mismatches':mismatches,'sources':sources,'inputs':{str(x):api.sha(x) for x in (raw,oracle,probe.DESIGN,probe.OUT/'failure.json',raw.with_suffix('.accounting.json'))},'candidate_rejected':True,'production_authorized':False}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')});print('DIAGNOSIS_SAVED',count,len(mismatches),flush=True)

if __name__=='__main__':run()
