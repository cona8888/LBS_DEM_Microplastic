"""Independent saved-trace audit and conservative six-case scheduling check."""
from pathlib import Path
import copy, datetime as dt, sys, shutil
import numpy as np
import repaired_campaign_preflight_v1 as p

api,parent=p.api,p.parent


def exact_l1(a,b,start,stop,scale):
    ia=ib=0;left=start;total=0.
    while left<stop:
        right=min(a[ia]['time_s'],b[ib]['time_s'],stop)
        api.require(right>left,'independent monotone interval integration')
        total+=(right-left)*float(np.linalg.norm(np.asarray(a[ia]['velocity_generalized'])-b[ib]['velocity_generalized']))
        left=right
        if a[ia]['time_s']==right:ia+=1
        if b[ib]['time_s']==right:ib+=1
    return total/(stop-start)/scale


def main():
    d=api.read(p.DESIGN);p.verify(d)
    r=api.read(p.OUT/'results.json');seal=api.read(p.OUT/'completion.json')
    api.require(not (p.OUT/'failure.json').exists() and seal['results_sha256']==api.sha(p.OUT/'results.json'),'terminal preflight seal')
    api.verify_mapping(r['artifacts']);seen=set();steps=repairs=0;levels=[];timings={}
    def read(path):
        nonlocal steps,repairs
        path=Path(path);api.require(str(path) not in seen,'unique raw accounting');seen.add(str(path))
        q=parent.storage.read_record(path,api.sha(p.DESIGN));steps+=len(q['rows']);repairs+=len(q['repairs']);return q
    def audit(q,before,spec,binding):
        result=q['result'];cp=result['checkpoint'];rows=q['rows']
        api.require(q['spec']==spec and q['input_checkpoint_sha256']==api.digest(before),'input and spec')
        api.require(cp['contract']==parent.engine.prior.contracts.expected_contract(spec,parent.model.binding_for(binding,True)),'contract')
        api.require(cp['state_sha256']==api.digest(cp['state']),'checkpoint hash')
        api.require(result['rejected']==before['state']['rejected']==0,'zero rejected trials')
        api.require(parent.engine.prior.reference.independent_health(result,spec)['passed'],'independent numerical health')
        t=before['state']['t']
        for row in rows:
            api.require(row['dt_s']>0 and t+row['dt_s']==row['time_s'],'exact clock')
            api.require(np.isfinite(row['position_m']+row['orientation']+row['velocity_generalized']).all(),'finite trace')
            api.require(abs(np.linalg.norm(row['orientation'])-1)<=1e-10,'unit axis')
            t=row['time_s']
        api.require(t==result['time_s']==cp['state']['t'] and len(rows)==result['steps']-before['state']['steps'],'clock and step accounting')
        api.require(rows[-1]['position_m']==cp['state']['x'] and rows[-1]['velocity_generalized']==cp['state']['q'],'state/trace agreement')
        api.require(q['effective_binding']==parent.model.binding_for(binding,True) and len(q['backend_calls'])==1 and q['backend_calls'][0]['enabled'],'runtime binding')
        calls=result['stage119_repair_calls']
        api.require(len(q['repairs'])==len(calls) and all(x['reduced_accepted'] for x in q['repairs']),'repair call accounting')
        for call in calls:
            h=call['health'];f=np.array(h['reactions']);mu=spec['config']['friction_coefficient']
            api.require(call['accepted'] and h['solver']==p.repair.NAME and h['original_gaps_preserved'],'only qualified original-gap fallback')
            api.require(h['residual']<=1e-10 and h['force_residual']<=1e-8 and np.isfinite(f).all() and np.all(f[::3]>=0),'contact/force gates')
            api.require(all(np.linalg.norm(f[i+1:i+3])<=mu*f[i]+1e-12*max(np.linalg.norm(f),1e-30) for i in range(0,len(f),3)),'independent cones')
    for control in d['controls']:
        before=parent.storage.read_record(Path(control['source']),d['old_source_design_sha256'])
        old=parent.storage.read_record(Path(control['target']),d['old_source_design_sha256'])
        binding=api.digest([d['binding'],control['id']]);spec=before['spec']
        cp=parent.model.checkpoint(spec,binding,before['result']['checkpoint'],True)
        q=read(p.RUN/(control['id']+'.json.gz'));audit(q,cp,spec,binding)
        api.require(q['rows']==old['rows'][:control['steps']] and len(q['rows'])==1000 and not q['repairs'],'bitwise healthy control')
    for factor in d['factors_relative_to_old_fine']:
        spec,binding,cp=p.setup(d,factor);seed=copy.deepcopy(cp);rows=[];rates=[]
        paths=sorted((p.RUN/f'factor_{factor}').glob('segment_*.json.gz'))
        for i,path in enumerate(paths,1):
            api.require(path.name==f'segment_{i:03d}.json.gz','contiguous sequence')
            t=cp['state']['t'];q=read(path);audit(q,cp,spec,binding);cp=q['result']['checkpoint'];rows.extend(q['rows'])
            if t>=d['failure_time_s']+1e-4 and len(q['rows'])>=100:
                rates.append(q['compute_call_wall_s']/(cp['state']['t']-t))
        api.require(q['result']['status']=='present_at_horizon' and cp['state']['t']==d['local_horizon_s'],'exact endpoint')
        api.require(rates,'post-contact rate samples')
        timings[str(factor)]=max(rates)
        levels.append({'factor':factor,'spec':spec,'binding':binding,'seed':seed,'rows':rows,'result':q['result']})
    ref=levels[-1];start=ref['seed']['state']['t'];stop=d['local_horizon_s'];metrics=[]
    U=ref['spec']['config']['target_mean_interstitial_velocity_m_s'];b=ref['spec']['config']['prolate_semiaxes_m'][1]
    toy_a=[{'time_s':.3,'velocity_generalized':[1.,0.]},{'time_s':1.,'velocity_generalized':[2.,0.]}]
    toy_b=[{'time_s':.7,'velocity_generalized':[0.,0.]},{'time_s':1.,'velocity_generalized':[1.,0.]}]
    api.require(abs(exact_l1(toy_a,toy_b,0.,1.,1.)-1.4)<1e-14,'analytical L1 check')
    for level in levels[:-1]:
        values={}
        for field,key,scale,label in [('position_m','x',b,'pose_b'),('orientation','p',1.,'axis')]:
            curves=[];times=[]
            for lev in [level,ref]:
                times.append(np.array([start]+[row['time_s'] for row in lev['rows']]))
                curves.append(np.array([lev['seed']['state'][key]]+[row[field] for row in lev['rows']]))
            grid=np.unique(np.concatenate(times))
            delta=np.array([np.interp(grid,times[0],curves[0][:,k])-np.interp(grid,times[1],curves[1][:,k]) for k in range(3)])
            values[label]=float(np.max(np.linalg.norm(delta,axis=0))/scale)
        values['endpoint_velocity_U']=float(np.linalg.norm(np.array(level['result']['velocity_generalized'])-ref['result']['velocity_generalized'])/U)
        values['mean_L1_velocity_U']=exact_l1(level['rows'],ref['rows'],start,stop,U)
        old=next(x for x in r['comparisons'] if x['factor']==level['factor'])
        api.require(all(np.isclose(v,old['metrics'][k],rtol=1e-10,atol=1e-14) for k,v in values.items()),'independent metrics')
        metrics.append({'factor':level['factor'],'values':values,'passed':all(v<=d['limits'][k] for k,v in values.items())})
    level=levels[1];spec=copy.deepcopy(level['spec']);spec['horizon_s']+=1e-3;spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
    binding=api.digest([d['binding'],'repair_restart']);cp=parent.model.checkpoint(spec,binding,level['result']['checkpoint'],True)
    full=read(p.RUN/'restart/full.json.gz');first=read(p.RUN/'restart/first.json.gz');last=read(p.RUN/'restart/last.json.gz')
    for q,before in [(full,cp),(first,cp),(last,first['result']['checkpoint'])]:audit(q,before,spec,binding)
    api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'] and full['repairs'],'exact active-repair restart')
    api.require(seen=={str(x) for x in p.RUN.rglob('*.json.gz')} and seen=={x for x in r['artifacts'] if x.endswith('.json.gz')},'complete artifact inventory')
    api.require(steps==r['new_steps']<=d['budget']['maximum_new_steps'] and r['wall_s']<=d['budget']['wall_s'],'bounded work')
    verified=all(x['passed'] for x in metrics);api.require(verified==r['passed'],'verdict reproduction')
    old=api.read(parent.DESIGN);margin=d['budget']['runtime_margin'];now=dt.datetime.now(dt.timezone.utc)
    available=(dt.datetime.fromisoformat(d['simulation_cutoff_utc'])-now).total_seconds()/3600
    # Frozen case order and three-worker greedy dispatch, including queued pilots.
    loads=[0.,0.,0.];schedule=[]
    for c in old['cases']:
        rate=old['cost']['fibre_contact_rates_s_per_simulated_s'][str(c['factor'])] if c['shape']=='rigid_prolate_ar4' else timings[str(c['factor']/old['reference_factor'])]
        hours=c['spec']['horizon_s']*rate*margin/3600
        worker=min(range(3),key=lambda i:loads[i]);begin=loads[worker];loads[worker]+=hours
        schedule.append({'case_id':c['id'],'worker':worker,'rate_s_per_simulated_s':rate,'compute_hours_with_margin':hours,'start_hours':begin,'finish_hours':loads[worker]})
    budget_passed=max(loads)<=available and shutil.disk_usage(p.ROOT).free>=d['budget']['minimum_free_disk_bytes']
    result={'audit_integrity_passed':True,'integration_verified':verified,'campaign_budget_passed':budget_passed,
            'ready_for_fresh_campaign_preflight':verified and budget_passed,'new_steps_audited':steps,'raw_records':len(seen),'repair_calls':repairs,
            'exact_restart':True,'healthy_controls_bitwise_identical':True,'metrics':metrics,'post_repair_rates':timings,
            'projected_makespan_hours_with_margin':max(loads),'available_simulation_hours':available,'projected_schedule':schedule,
            'deadline_utc':d['deadline_utc'],'simulation_cutoff_utc':d['simulation_cutoff_utc'],'evaluated_utc':now.isoformat(),
            'full_path_qualified':False,'population_release_established':False,'old_failed_verdicts_changed':False,
            'claim':'Integration verification and conditional cost estimate only; unseen contacts may change cost or fail. Full-path comparisons still required.',
            'source_sha256':api.sha(__file__),'preflight_design_sha256':api.sha(p.DESIGN),'preflight_results_sha256':api.sha(p.OUT/'results.json')}
    p.verify(d);p.AUDIT.mkdir(exist_ok=False);api.write(p.AUDIT/'results.json',result)
    api.write(p.AUDIT/'completion.json',{'audit_integrity_passed':True,'integration_verified':verified,
                                      'campaign_budget_passed':budget_passed,'results_sha256':api.sha(p.AUDIT/'results.json')})
    print('AUDIT',verified,'BUDGET',budget_passed,'MAKESPAN_H',max(loads),'AVAILABLE_H',available,'STEPS',steps,flush=True)


if __name__=='__main__':main()
