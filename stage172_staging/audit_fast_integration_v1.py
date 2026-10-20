"""Independent reconstruction from saved raw traces and contact algebra."""
from pathlib import Path
import copy, datetime, shutil
import numpy as np
import integration_fast_contact_v1 as run
import audit_repaired_preflight_v1 as prior_audit
api,parent,p,fast=run.api,run.parent,run.p,run.fast
OUT=run.OUT.parent/'independent_audit_01'


def physical(row):
    v,M,J,g=[np.array(row[k]) for k in ['vfree','mobility','jacobian','gaps_m']]
    q=np.array(row['velocity']);f=np.array(row['health']['reactions']);dt=row['dt_s'];mu=row['friction']
    scale=max(np.linalg.norm(v),1e-15);A=J@M@J.T;w=J@q
    load=J.T@f;balance=np.linalg.norm(np.linalg.solve(M,q-v)-load)/max(np.linalg.norm(load),1e-30)
    terms=[];work=0.
    for k in range(3):
        i=3*k;eig=np.linalg.eigvalsh(A[i+1:i+3,i+1:i+3])[-1]
        trial=f[i+1:i+3]-w[i+1:i+3]/eig
        projected=trial*min(1.,mu*f[i]/max(np.linalg.norm(trial),1e-300))
        terms+=[abs(min(A[i,i]*f[i],w[i]+g[k]/dt)),np.linalg.norm(f[i+1:i+3]-projected)*eig]
        api.require(f[i]>=0 and np.linalg.norm(f[i+1:i+3])<=mu*f[i]+1e-12*max(np.linalg.norm(f),1e-30),'independent original cones')
        work+=f[i+1:i+3]@w[i+1:i+3]
    api.require(np.isfinite(q).all() and np.isfinite(f).all() and balance<=1e-8 and max(terms)/scale<=1e-10,'independent closure and complementarity')
    api.require(work<=1e-8*max(np.linalg.norm(f)*scale,1e-30),'independent dissipation')
    api.require(np.max(np.abs(g))/dt<=1e-5*scale and np.linalg.norm(q)/scale<=1e-4,'early dispatch eligibility')
    return float(max(terms)/scale),float(balance)


def curve_metrics(level,reference,start,stop):
    U=level['spec']['config']['target_mean_interstitial_velocity_m_s'];b=level['spec']['config']['prolate_semiaxes_m'][1]
    values={}
    for field,key,scale,label in [('position_m','x',b,'pose_b'),('orientation','p',1.,'axis')]:
        times=[];arrays=[]
        for x in [level,reference]:
            times.append(np.array([start]+[r['time_s'] for r in x['rows']]))
            arrays.append(np.array([x['seed']['state'][key]]+[r[field] for r in x['rows']]))
        grid=np.unique(np.concatenate(times))
        delta=np.column_stack([np.interp(grid,times[0],arrays[0][:,i])-np.interp(grid,times[1],arrays[1][:,i]) for i in range(3)])
        values[label]=float(np.linalg.norm(delta,axis=1).max()/scale)
    values['endpoint_velocity_U']=float(np.linalg.norm(np.array(level['result']['velocity_generalized'])-reference['result']['velocity_generalized'])/U)
    values['mean_L1_velocity_U']=prior_audit.exact_l1(level['rows'],reference['rows'],start,stop,U)
    return values


def main():
    d=api.read(run.DESIGN);run.verify(d);result=api.read(run.OUT/'results.json')
    seal=api.read(run.OUT/'completion.json')
    api.require(not (run.OUT/'failure.json').exists() and seal['results_sha256']==api.sha(run.OUT/'results.json'),'integration completion seal')
    api.verify_mapping(result['artifacts']);seen=set();totals={'steps':0,'early':0,'fallback':0};maxima=[0.,0.]
    def audit(path,spec,binding,before):
        path=Path(path);api.require(str(path) not in seen,'unique record accounting');seen.add(str(path))
        rec=parent.storage.read_record(path,api.sha(run.DESIGN));r=rec['result'];cp=r['checkpoint'];rows=rec['rows']
        api.require(rec['spec']==spec and rec['input_checkpoint_sha256']==api.digest(before),'input checkpoint binding')
        effective=parent.model.binding_for(binding,True)
        api.require(rec['effective_binding']==effective and cp['contract']==parent.engine.prior.contracts.expected_contract(spec,effective),'runtime contract')
        api.require(cp['state_sha256']==api.digest(cp['state']),'checkpoint state seal')
        api.require(r['rejected']==before['state']['rejected']==0,'no rejected trials')
        api.require(parent.engine.prior.reference.independent_health(r,spec)['passed'],'full numerical health')
        t=before['state']['t']
        for row in rows:
            api.require(row['dt_s']>0 and t+row['dt_s']==row['time_s'],'exact accepted clock')
            api.require(np.isfinite(row['position_m']+row['orientation']+row['velocity_generalized']).all(),'finite state')
            api.require(abs(np.linalg.norm(row['orientation'])-1)<1e-10,'unit orientation')
            t=row['time_s']
        api.require(t==r['time_s']==cp['state']['t']<=spec['horizon_s'],'exact terminal clock')
        api.require(len(rows)==r['steps']-before['state']['steps']<=rec['step_cap'],'exact step accounting')
        api.require(rows[-1]['position_m']==cp['state']['x'] and rows[-1]['velocity_generalized']==cp['state']['q'],'state trace binding')
        api.require(len(rec['backend_calls'])==1 and rec['backend_calls'][0]['enabled'],'qualified rigid backend')
        for row in rec['early_attempts']:
            if row['accepted']:
                metrics=physical(row);totals['early']+=1
                maxima[:]=[max(a,b) for a,b in zip(maxima,metrics)]
        calls=r['stage119_repair_calls'];api.require(len(calls)==len(rec['repairs']),'fallback accounting')
        for row in calls:
            h=row['health'];f=np.array(h['reactions']);mu=spec['config']['friction_coefficient']
            api.require(row['accepted'] and h['solver']==fast.old.NAME and h['original_gaps_preserved'],'qualified old fallback')
            api.require(h['residual']<=1e-10 and h['force_residual']<=1e-8 and np.all(f[::3]>=0),'old contact gates')
            api.require(all(np.linalg.norm(f[i+1:i+3])<=mu*f[i]+1e-12*max(np.linalg.norm(f),1e-30) for i in range(0,len(f),3)),'old cones')
        totals['steps']+=len(rows);totals['fallback']+=len(calls)
        return rec
    for c in d['controls']:
        source=parent.storage.read_record(Path(c['source']),d['old_source_design_sha256'])
        target=parent.storage.read_record(Path(c['target']),d['old_source_design_sha256'])
        binding=api.digest([d['binding'],c['id']]);spec=source['spec'];cp=parent.model.checkpoint(spec,binding,source['result']['checkpoint'],True)
        rec=audit(run.RUN/(c['id']+'.json.gz'),spec,binding,cp)
        api.require(rec['rows']==target['rows'][:c['steps']] and len(rec['rows'])==c['steps'],'healthy controls bitwise identical')
    levels=[];rates={}
    for factor in d['factors_relative_to_old_fine']:
        spec,binding,cp=p.setup(d,factor);seed=copy.deepcopy(cp);rows=[];timings=[]
        for i,path in enumerate(sorted((run.RUN/f'factor_{factor}').glob('segment_*.json.gz')),1):
            api.require(path.name==f'segment_{i:03d}.json.gz','contiguous segments')
            start=cp['state']['t'];rec=audit(path,spec,binding,cp);cp=rec['result']['checkpoint'];rows+=rec['rows']
            if start>=d['failure_time_s']+1e-4 and len(rec['rows'])>=100:timings.append(rec['compute_call_wall_s']/(cp['state']['t']-start))
        api.require(rec['result']['status']=='present_at_horizon' and cp['state']['t']==d['local_horizon_s'] and timings,'complete exact local observation')
        rates[str(factor)]=max(timings)
        levels.append({'factor':factor,'spec':spec,'binding':binding,'seed':seed,'rows':rows,'result':rec['result']})
    start=levels[0]['seed']['state']['t'];stop=d['local_horizon_s'];metrics=[]
    for level,expected in zip(levels[:-1],result['comparisons']):
        values=curve_metrics(level,levels[-1],start,stop)
        api.require(all(np.isclose(v,expected['metrics'][k],rtol=1e-10,atol=1e-14) for k,v in values.items()),'independent refinement metrics')
        metrics.append({'kind':'refinement','factor':level['factor'],'values':values,'passed':all(v<=d['limits'][k] for k,v in values.items())})
    old=api.read(p.OUT/'results.json')
    for level,oldlevel,expected in zip(levels,old['levels'],result['same_level_slow_stack_comparisons']):
        oldrows=[]
        for entry in oldlevel['entries']:oldrows+=parent.storage.read_record(Path(entry['path']),api.sha(p.DESIGN))['rows']
        values=curve_metrics(level,{**level,'rows':oldrows,'result':oldlevel['final']},start,stop)
        api.require(all(np.isclose(v,expected['metrics'][k],rtol=1e-10,atol=1e-14) for k,v in values.items()),'independent same-level metrics')
        metrics.append({'kind':'same_level','factor':level['factor'],'values':values,'passed':all(v<=d['limits'][k] for k,v in values.items())})
    level=levels[1];spec=copy.deepcopy(level['spec']);spec['horizon_s']+=1e-3;spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
    binding=api.digest([d['binding'],'early_restart']);cp=parent.model.checkpoint(spec,binding,level['result']['checkpoint'],True)
    full=audit(run.RUN/'restart/full.json.gz',spec,binding,cp);a=audit(run.RUN/'restart/first.json.gz',spec,binding,cp)
    b=audit(run.RUN/'restart/last.json.gz',spec,binding,a['result']['checkpoint'])
    api.require(full['rows']==a['rows']+b['rows'] and full['result']['checkpoint']['state']==b['result']['checkpoint']['state'],'exact restart')
    api.require(any(x['accepted'] for x in full['early_attempts']),'restart exercised new dispatch')
    api.require(seen=={str(x) for x in run.RUN.rglob('*.json.gz')}=={x for x in result['artifacts'] if x.endswith('.json.gz')},'complete inventory')
    api.require(totals['steps']==result['new_steps']<=d['budget']['maximum_new_steps'] and result['wall_s']<=d['budget']['wall_s'],'bounded work')
    verified=all(x['passed'] for x in metrics);api.require(verified==result['passed'],'reproduced numerical verdict')
    oldd=api.read(parent.DESIGN);loads=[0.,0.,0.];schedule=[]
    for case in oldd['cases']:
        rate=oldd['cost']['fibre_contact_rates_s_per_simulated_s'][str(case['factor'])] if case['shape']=='rigid_prolate_ar4' else rates[str(case['factor']/oldd['reference_factor'])]
        hours=case['spec']['horizon_s']*rate*d['budget']['runtime_margin']/3600
        worker=min(range(3),key=lambda i:loads[i]);loads[worker]+=hours
        schedule.append({'case':case['id'],'worker':worker,'compute_hours':hours,'finish_hours':loads[worker]})
    now=datetime.datetime.now(datetime.timezone.utc);available=(datetime.datetime.fromisoformat(d['simulation_cutoff_utc'])-now).total_seconds()/3600
    oldaudit=api.read(p.AUDIT/'results.json')
    report={'audit_integrity_passed':True,'integration_verified':verified,'new_steps_audited':totals['steps'],'records':len(seen),
            'early_candidate_calls_audited':totals['early'],'old_fallback_calls_audited':totals['fallback'],
            'max_early_contact_residual':maxima[0],'max_early_force_residual':maxima[1],'exact_restart':True,'healthy_controls_exact':True,
            'metrics':metrics,'rates_seconds_per_simsecond':rates,
            'measured_local_sphere_speedup':{k:oldaudit['post_repair_rates'][k]/v for k,v in rates.items()},
            'campaign_budget_passed':max(loads)<=available,'makespan_hours_with_original_margin':max(loads),'available_simulation_hours':available,
            'schedule':schedule,'campaign_launched':False,'full_path_qualified':False,'evaluated_utc':now.isoformat(),
            'source_sha256':api.sha(__file__),'design_sha256':api.sha(run.DESIGN),'raw_results_sha256':api.sha(run.OUT/'results.json')}
    run.verify(d);OUT.mkdir(exist_ok=False);api.write(OUT/'results.json',report)
    api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'integration_verified':verified})
    print('AUDIT',verified,'STEPS',totals,'SPEEDUP',report['measured_local_sphere_speedup'],'BUDGET',report['campaign_budget_passed'],
          'MAKESPAN_H',max(loads),'AVAILABLE_H',available,flush=True)


if __name__=='__main__':main()
