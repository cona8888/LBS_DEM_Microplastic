"""Independent certificate algebra, raw trace, clock and paired-state audit."""
from pathlib import Path
import copy,math
import numpy as np
import integrate_certified_sweep_v1 as job
api,parent,p,unit=job.api,job.parent,job.p,job.unit
from audit_repaired_preflight_v1 import exact_l1
OUT=job.OUT.parent/'independent_audit_01'


def audit_proof(proof,geometry,x,orientation,q,dt,a,b):
    api.require(proof['x']==x and proof['p']==orientation and proof['v']==q and proof['dt_s']==dt,'certificate applied to accepted motion')
    x=np.array(x);q=np.array(q);orientation=np.array(orientation)
    translation=np.linalg.norm(q[:3]);omega=np.linalg.norm(q[3:]/a);speed=float(translation+a*omega)
    api.require(speed==proof['motion_speed_bound'] and proof['a_m']==a and proof['b_m']==b,'Lipschitz scales')
    radius=geometry.r.max();travel=translation*dt
    margin=1e-10*(2*np.linalg.norm(x)+geometry.L+a+radius+travel)
    api.require(2*(radius+a+travel+margin)<geometry.L,'independent periodic image guard')
    expected_ids=geometry.tree.query_ball_point(np.mod(x,geometry.L),radius+a+travel+margin)
    api.require(sorted(expected_ids)==sorted(r['grain'] for r in proof['pairs']),'complete broadphase certificate')
    global_lower=0.
    motion=job.candidate.original._FixedMotion(x,orientation,q,a)
    for pair in proof['pairs']:
        k=pair['grain'];delta=geometry.c[k]-x;delta-=geometry.L*np.round(delta/geometry.L);c=x+delta
        padding=1e-10*(np.linalg.norm(x)+np.linalg.norm(c)+a+geometry.r[k]+travel)
        api.require(padding==pair['pad'],'original safety pad')
        times=np.array(pair.get('partition_times_s',[0.,dt]));gaps=[]
        for t in times:gaps.append(job.candidate.original._gap_at_pose(*motion.at(t),a,b,c,geometry.r[k]))
        saved=pair.get('partition_gaps_m',[pair['f0'],pair['f1']])
        api.require(np.max(np.abs(np.array(gaps)-saved))<=1e-17,'independently recomputed endpoint distances')
        bounds=[]
        for left,right,f0,f1 in zip(times[:-1],times[1:],gaps[:-1],gaps[1:]):
            travel_i=speed*(right-left);bounds.append(max(f0-travel_i,f1-travel_i,(f0+f1-travel_i)/2)-padding)
        lower=min(bounds);api.require(abs(lower-pair['lower'])<=1e-17,'independent subinterval bound')
        global_lower=min(global_lower,lower)
    api.require(abs(global_lower-proof['lower_bound_m'])<=1e-17 and proof['threshold_m']==-1e-5*b and global_lower>=-1e-5*b,'same penetration gate certified')


def metrics(a,b,start,stop):
    U=a['spec']['config']['target_mean_interstitial_velocity_m_s'];minor=a['spec']['config']['prolate_semiaxes_m'][1];values={}
    for field,key,scale,label in [('position_m','x',minor,'pose_b'),('orientation','p',1.,'axis')]:
        times=[np.r_[start,[r['time_s'] for r in x['rows']]] for x in [a,b]]
        states=[np.array([x['seed']['state'][key]]+[r[field] for r in x['rows']]) for x in [a,b]]
        grid=np.unique(np.r_[times[0],times[1]])
        diff=np.array([np.interp(grid,times[0],states[0][:,k])-np.interp(grid,times[1],states[1][:,k]) for k in range(3)])
        values[label]=float(np.linalg.norm(diff,axis=0).max()/scale)
    values['endpoint_velocity_U']=float(np.linalg.norm(np.array(a['result']['velocity_generalized'])-b['result']['velocity_generalized'])/U)
    values['mean_L1_velocity_U']=exact_l1(a['rows'],b['rows'],start,stop,U)
    return values


def main():
    d=api.read(job.DESIGN);job.verify(d);r=api.read(job.OUT/'results.json');seal=api.read(job.OUT/'completion.json')
    api.require(not (job.OUT/'failure.json').exists() and seal['results_sha256']==api.sha(job.OUT/'results.json'),'terminal result seal')
    api.verify_mapping(r['artifacts']);seen=set();counts={'steps':0,'certified':0,'legacy':0};levels=[]
    # Geometry is independently loaded and verified; no numerical trajectory is advanced.
    parent.b.old.parent.configure();source=parent.storage.read_record(Path(d['source']['source']),d['source']['source_design_sha256'])
    field,data,meta=api.fields.load(2,1.,6)
    geometry=job.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    def record(path,spec,binding,before,enabled):
        path=Path(path);api.require(str(path) not in seen,'unique record');seen.add(str(path));rec=parent.storage.read_record(path,api.sha(job.DESIGN))
        result=rec['result'];state=result['checkpoint']['state'];rows=rec['rows']
        api.require(rec['spec']==spec and rec['input_checkpoint_sha256']==api.digest(before),'input binding')
        api.require(result['checkpoint']['state_sha256']==api.digest(state),'checkpoint seal')
        api.require(result['checkpoint']['contract']==parent.engine.prior.contracts.expected_contract(spec,parent.model.binding_for(binding,True)),'contract')
        api.require(result['rejected']==before['state']['rejected']==0 and parent.engine.prior.reference.independent_health(result,spec)['passed'],'no rejected trials and health')
        api.require(rec['certified_sweep_enabled']==enabled and rec['minimum_gap_semantics']==('conservative_lower_bound' if enabled else 'legacy_bounded_minimum_estimate'),'diagnostic semantics explicitly bound')
        t=before['state']['t'];x=before['state']['x'];orientation=before['state']['p'];a,b,_=spec['config']['prolate_semiaxes_m']
        if enabled:api.require(len(rows)==len(rec['sweep_certificates']),'one proof per step')
        for i,row in enumerate(rows):
            api.require(row['dt_s']>0 and t+row['dt_s']==row['time_s'],'exact clock')
            if enabled:
                proof=rec['sweep_certificates'][i]
                if proof['certified']:
                    audit_proof(proof,geometry,x,orientation,row['velocity_generalized'],row['dt_s'],a,b);counts['certified']+=1
                else:
                    counts['legacy']+=1
                    value=job.candidate.REFERENCE(geometry,np.array(x),np.array(orientation),np.array(row['velocity_generalized']),a,b,row['dt_s'])
                    api.require(value==proof['reference_gap_m'] and value>=-1e-5*b,'unchanged fallback decision')
            t=row['time_s'];x=row['position_m'];orientation=row['orientation']
        api.require(t==result['time_s']==state['t'] and len(rows)==result['steps']-before['state']['steps'],'step accounting')
        api.require(x==state['x'] and rows[-1]['velocity_generalized']==state['q'],'physical endpoint')
        counts['steps']+=len(rows);return rec
    for factor in d['factors_relative_to_old_fine']:
        pair=[]
        for variant in ['old','certificate']:
            spec,binding,cp=job.setup(d,factor,variant);seed=copy.deepcopy(cp);rows=[];timings=[]
            for i,path in enumerate(sorted((job.RUN/f'factor_{factor}'/variant).glob('*.json.gz')),1):
                api.require(path.name==f'segment_{i:03d}.json.gz','ordered segments');before=cp['state']['t']
                rec=record(path,spec,binding,cp,variant=='certificate');rows+=rec['rows'];cp=rec['result']['checkpoint']
                timings.append({'steps':len(rec['rows']),'rate':rec['compute_call_wall_s']/(cp['state']['t']-before),'path':str(path)})
            api.require(rec['result']['status']=='present_at_horizon' and cp['state']['t']==d['horizon_s'],'exact horizon')
            pair.append({'factor':factor,'variant':variant,'spec':spec,'binding':binding,'seed':seed,'rows':rows,'result':rec['result'],'timings':timings})
        api.require(pair[0]['rows']==pair[1]['rows'],'all physical rows bitwise identical')
        # Reconstruct allowed diagnostic differences independently, not the runner helper.
        states=[copy.deepcopy(x['result']['checkpoint']['state']) for x in pair]
        for state in states:
            del state['minimum_gap']
            for history in state['history']:history[13]='gap_bound_diagnostic'
        api.require(states[0]==states[1],'only declared diagnostic fields differ')
        levels+=pair
    active=[x for x in levels if x['variant']=='certificate'];start=active[0]['seed']['state']['t'];comparisons=[]
    for level,expected in zip(active[:-1],r['comparisons']):
        values=metrics(level,active[-1],start,d['horizon_s'])
        api.require(all(np.isclose(v,expected['metrics'][k],rtol=1e-10,atol=1e-14) for k,v in values.items()),'independent refinement metrics')
        comparisons.append({'factor':level['factor'],'values':values,'passed':all(v<=d['limits'][k] for k,v in values.items())})
    lev=active[1];spec=copy.deepcopy(lev['spec']);spec['horizon_s']+=.001;spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
    binding=api.digest([d['binding'],'restart']);cp=parent.model.checkpoint(spec,binding,lev['result']['checkpoint'],True)
    full=record(job.RUN/'restart/full.json.gz',spec,binding,cp,True);a=record(job.RUN/'restart/first.json.gz',spec,binding,cp,True)
    b=record(job.RUN/'restart/last.json.gz',spec,binding,a['result']['checkpoint'],True)
    api.require(full['rows']==a['rows']+b['rows'] and full['result']['checkpoint']['state']==b['result']['checkpoint']['state'],'exact restart including diagnostics')
    api.require(seen=={str(x) for x in job.RUN.rglob('*.json.gz')}=={x for x in r['artifacts'] if x.endswith('.json.gz')},'complete inventory')
    api.require(counts['steps']==r['new_steps']<=d['budget']['maximum_new_steps'] and r['wall_s']<=d['budget']['wall_s'],'bounded work')
    verdict=all(x['passed'] for x in comparisons);api.require(verdict==r['passed'],'reproduced verdict')
    rates={str(x['factor']):max(t['rate'] for t in x['timings'] if t['steps']>=100) for x in active}
    report={'audit_integrity_passed':True,'integration_verified':verdict,'counts':counts,'raw_records':len(seen),
            'physical_rows_bitwise_identical':True,'only_declared_gap_diagnostics_changed':True,'exact_restart':True,
            'comparisons':comparisons,'candidate_rates_s_per_sim_s':rates,
            'speedups':{str(x['factor']):x['old_compute_s']/x['new_compute_s'] for x in r['pairs']},
            'minimum_gap_semantics':d['diagnostic_semantics'],'design_sha256':api.sha(job.DESIGN),'result_sha256':api.sha(job.OUT/'results.json'),
            'source_sha256':api.sha(__file__),'full_path_qualified':False,'campaign_launched':False}
    job.verify(d);OUT.mkdir(exist_ok=False);api.write(OUT/'results.json',report);api.write(OUT/'completion.json',{'integration_verified':verdict,'results_sha256':api.sha(OUT/'results.json')})
    print('CERTIFIED_AUDIT',verdict,'COUNTS',counts,'SPEEDUPS',report['speedups'],'RATES',rates,flush=True)


if __name__=='__main__':main()
