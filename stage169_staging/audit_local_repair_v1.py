"""Independent raw-record, clock, health and local-refinement audit."""
from pathlib import Path
import sys,json,hashlib,copy
import numpy as np
import local_regression_v1 as job
api,parent=job.api,job.parent
OUT=job.unit.EVAL/'independent_audit_01'


def l1(ra,rb,start,stop,U):
    i=j=0;left=start;total=0.
    while left<stop:
        right=min(ra[i]['time_s'],rb[j]['time_s'],stop)
        api.require(right>left,'monotone independent L1')
        total+=(right-left)*np.linalg.norm(np.asarray(ra[i]['velocity_generalized'])-rb[j]['velocity_generalized'])
        left=right
        if ra[i]['time_s']==right:i+=1
        if rb[j]['time_s']==right:j+=1
    return float(total/(stop-start)/U)


def main():
    d=api.read(job.DESIGN);job.verify(d)
    evaluated=api.read(job.OUT/'results.json');seal=api.read(job.OUT/'completion.json')
    api.require(not (job.OUT/'failure.json').exists() and seal['results_sha256']==api.sha(job.OUT/'results.json'),'terminal seal/no failure')
    units=job.unit.EVAL/'units_01';ur=api.read(units/'results.json')
    api.require(ur['passed'] and api.read(units/'completion.json')['results_sha256']==api.sha(units/'results.json'),'unit seal')
    api.verify_mapping(ur['artifacts'])
    api.require(ur['frozen_probe_passed']==ur['frozen_probe_count']==30 and all(x['passed'] for x in ur['tests']),'unit/probe completeness')
    source=parent.storage.read_record(Path(d['source_checkpoint']),api.sha(parent.DESIGN))
    artifacts={};levels=[];steps=0;total_repairs=0;peak_force=peak_momentum=0.
    def read_raw(path):
        nonlocal steps,total_repairs,peak_force,peak_momentum
        record=parent.storage.read_record(path,api.sha(job.DESIGN));steps+=len(record['rows'])
        r=record['result'];total_repairs+=len(record['repairs'])
        peak_force=max(peak_force,r['max_force_residual']);peak_momentum=max(peak_momentum,r['max_momentum_residual'])
        for p in [path,path.with_suffix('.seal.json')]:artifacts[str(p)]=api.sha(p)
        return record
    def audit_record(record,before,spec,binding):
        r=record['result'];cp=r['checkpoint'];rows=record['rows']
        api.require(record['input_checkpoint_sha256']==api.digest(before),'input state binding')
        api.require(record['spec']==spec and cp['contract']==parent.engine.prior.contracts.expected_contract(spec,parent.model.binding_for(binding,True)),'spec/contract')
        api.require(cp['state_sha256']==api.digest(cp['state']),'checkpoint seal')
        api.require(r['rejected']==before['state']['rejected']==0,'zero new rejected trials')
        t=before['state']['t']
        for row in rows:
            api.require(row['dt_s']>0 and t+row['dt_s']==row['time_s'],'exact raw clock')
            t=row['time_s']
            api.require(np.isfinite(row['position_m']+row['orientation']+row['velocity_generalized']).all(),'finite trace')
            api.require(abs(np.linalg.norm(row['orientation'])-1)<=1e-10,'unit axis')
        api.require(t==r['time_s']==cp['state']['t'] and r['steps']-before['state']['steps']==len(rows),'step/clock endpoint')
        api.require(parent.engine.prior.reference.independent_health(r,spec)['passed'],'independent health')
        api.require(r['status'] in ['paused_checkpoint','incomplete_budget','present_at_horizon'],'no invalid terminal status')
        for call in r['stage119_repair_calls']:
            api.require(call['accepted'] and call['health']['solver']==job.repair.NAME,'qualified fallback only')
            h=call['health'];force=np.asarray(h['reactions']);mu=spec['config']['friction_coefficient']
            api.require(np.isfinite(force).all() and np.all(force[::3]>=0),'finite compressive force')
            api.require(all(np.linalg.norm(force[i+1:i+3])<=mu*force[i]+1e-12*max(np.linalg.norm(force),1e-30) for i in range(0,len(force),3)),'independent Coulomb cone')
            api.require(h['residual']<=1e-10 and h['force_residual']<=1e-8 and h['original_gaps_preserved'],'residual/closure and original gaps')
    for factor in d['factors']:
        spec,binding,cp=job.setup(d,factor);seed=copy.deepcopy(cp);rows=[];paths=sorted((job.RUN/f'factor_{factor}').glob('segment_*.json.gz'))
        for index,path in enumerate(paths,1):
            api.require(path.name==f'segment_{index:03d}.json.gz','contiguous segments')
            rec=read_raw(path);audit_record(rec,cp,spec,binding);rows.extend(rec['rows']);cp=rec['result']['checkpoint']
        api.require(rec['result']['status']=='present_at_horizon' and cp['state']['t']==d['horizon_s'],'complete local horizon')
        levels.append({'factor':factor,'spec':spec,'binding':binding,'seed':seed,'rows':rows,'result':rec['result']})
    expected_paths={str(Path(e['path'])) for level in evaluated['levels'] for e in level['entries']}
    actual_paths={str(p) for p in job.RUN.glob('factor_*/segment_*.json.gz')}
    api.require(expected_paths==actual_paths,'all level records indexed')
    for level in evaluated['levels']:
        for e in level['entries']:api.require(api.sha(e['path'])==e['sha256'],'evaluation raw binding')
    restart={}
    for name in ['entry','full','first','last']:
        path=job.RUN/'restart'/f'{name}.json.gz'
        if path.exists():restart[name]=read_raw(path)
    full=restart['full'];first=restart['first'];last=restart['last']
    if 'entry' in restart:
        entry=restart['entry']['result']['checkpoint']
        candidates=[levels[0]['seed']]
        for path in sorted((job.RUN/'factor_1.0').glob('segment_*.json.gz')):
            candidates.append(parent.storage.read_record(path,api.sha(job.DESIGN))['result']['checkpoint'])
        prior=next(cp for cp in candidates if api.digest(cp)==restart['entry']['input_checkpoint_sha256'])
        audit_record(restart['entry'],prior,levels[0]['spec'],levels[0]['binding'])
    else:raise RuntimeError('expected explicit restart entry record')
    for rec,before in [(full,entry),(first,entry),(last,first['result']['checkpoint'])]:audit_record(rec,before,levels[0]['spec'],levels[0]['binding'])
    api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'independent exact restart')
    api.require(len(full['repairs'])>0,'restart spans repaired event')
    old=parent.storage.read_record(Path(d['failed_segment']),api.sha(parent.DESIGN))
    failure_time=old['result']['rejected_trials'][0]['time_s'];prefix=[r for r in old['rows'] if r['time_s']<=failure_time]
    api.require(levels[0]['rows'][:len(prefix)]==prefix,'independent unchanged prefix')
    # Exercise independent interval integration on an analytical toy first.
    toy_a=[{'time_s':.3,'velocity_generalized':[1.,0.]},{'time_s':1.,'velocity_generalized':[2.,0.]}]
    toy_b=[{'time_s':.7,'velocity_generalized':[0.,0.]},{'time_s':1.,'velocity_generalized':[1.,0.]}]
    api.require(abs(l1(toy_a,toy_b,0.,1.,1.)-1.4)<1e-14,'independent L1 oracle')
    seed=levels[-1]['seed']['state'];start=seed['t'];stop=d['horizon_s'];ref=levels[-1];metrics=[]
    U=ref['spec']['config']['target_mean_interstitial_velocity_m_s'];b=ref['spec']['config']['prolate_semiaxes_m'][1]
    for level in levels[:-1]:
        values={}
        for field,sk,scale,label in [('position_m','x',b,'pose_b'),('orientation','p',1.,'axis')]:
            times=[];data=[]
            for lev in [level,ref]:
                times.append(np.array([start]+[r['time_s'] for r in lev['rows']]))
                data.append(np.array([seed[sk]]+[r[field] for r in lev['rows']]))
            grid=np.unique(np.r_[times[0],times[1]]);a0=[];a1=[]
            for k in range(3):a0.append(np.interp(grid,times[0],data[0][:,k]));a1.append(np.interp(grid,times[1],data[1][:,k]))
            values[label]=float(np.max(np.linalg.norm(np.asarray(a0)-np.asarray(a1),axis=0))/scale)
        values['endpoint_velocity_U']=float(np.linalg.norm(np.array(level['result']['velocity_generalized'])-ref['result']['velocity_generalized'])/U)
        values['mean_L1_velocity_U']=l1(level['rows'],ref['rows'],start,stop,U)
        prior=next(x for x in evaluated['comparisons'] if x['factor']==level['factor'])
        api.require(all(np.isclose(values[k],prior['metrics'][k],rtol=1e-10,atol=1e-14) for k in values),'independent metrics agree')
        metrics.append({'factor':level['factor'],'values':values,'passed':all(values[k]<=d['limits'][k] for k in values)})
    api.require(steps==evaluated['total_new_steps']<=d['budget']['maximum_total_local_steps'],'all steps accounted')
    api.require(all(x['passed'] for x in metrics)==evaluated['passed'],'independent verdict')
    result={'audit_integrity_passed':True,'local_repair_verified':evaluated['passed'],'metrics':metrics,'raw_records':len(artifacts)//2,
        'steps_audited':steps,'repair_calls_including_restart':total_repairs,'max_force_residual':peak_force,'max_momentum_residual':peak_momentum,
        'exact_restart':True,'exact_unchanged_prefix_steps':len(prefix),'original_gaps_and_gates':True,
        'long_campaign_restarted':False,'full_path_qualified':False,'stage167_verdict_changed':False,
        'source_sha256':api.sha(__file__),'local_protocol_sha256':api.sha(job.DESIGN)}
    job.verify(d);OUT.mkdir(exist_ok=False)
    for path in [job.DESIGN,job.unit.DESIGN,job.OUT/'results.json',job.OUT/'completion.json',units/'results.json',units/'completion.json',Path(__file__)]:artifacts[str(path)]=api.sha(path)
    api.write(OUT/'results.json',result);api.write(OUT/'completion.json',{'audit_integrity_passed':True,'local_repair_verified':result['local_repair_verified'],'results_sha256':api.sha(OUT/'results.json'),'artifacts':artifacts})
    print('AUDIT',result,flush=True)


if __name__=='__main__':main()
