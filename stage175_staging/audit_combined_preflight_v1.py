"""Read-only independent Stage175 raw/contact/clearance and resource audit."""
from pathlib import Path
import datetime,shutil,copy,math,sys
import numpy as np
import combined_cost_preflight_v1 as job
from audit_certified_integration_v1 import audit_proof
from audit_fast_integration_v1 import physical
api,parent=job.api,job.parent
OUT=job.OUT.parent/'independent_audit_01'


def main():
    d=api.read(job.DESIGN);job.verify(d);r=api.read(job.OUT/'results.json')
    api.require(not (job.OUT/'failure.json').exists(),'no failure marker')
    api.require(api.read(job.OUT/'completion.json')['results_sha256']==api.sha(job.OUT/'results.json'),'result seal')
    api.verify_mapping(r['artifacts']);parent.b.old.parent.configure()
    field,data,meta=api.fields.load(2,1.,6)
    geometry=job.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    seen=set();counts={'steps':0,'certified_sweeps':0,'legacy_sweeps':0,'early_contacts':0,'fallbacks':0}
    rates={};sizes={};cases=[];maxima=[0.,0.]
    for c in d['cases']:
        spec=c['spec'];binding=api.digest([d['binding'],c['id']]);effective=parent.model.binding_for(binding,True);cp=None
        if c['source']:
            src=parent.storage.read_record(Path(c['source']),c['source_design_sha256'])
            api.require(src['result']['checkpoint']['state_sha256']==c['initial_checkpoint_state_sha256'],'frozen source checkpoint')
            cp=parent.model.checkpoint(spec,binding,src['result']['checkpoint'],True)
        initial_t=cp['state']['t'] if cp else 0.;initial_steps=cp['state']['steps'] if cp else 0
        paths=sorted((job.RUN/c['id']).glob('*.json.gz'));api.require(len(paths)==d['blocks_per_case'],'all blocks present')
        c_rates=[];c_sizes=[]
        for i,path in enumerate(paths,1):
            api.require(path.name==f'segment_{i:03d}.json.gz' and str(path) not in seen,'ordered unique record');seen.add(str(path))
            rec=parent.storage.read_record(path,api.sha(job.DESIGN));rr=rec['result'];state=rr['checkpoint']['state'];rows=rec['rows']
            api.require(rec['spec']==spec and rec['input_checkpoint_sha256']==api.digest(cp),'frozen input binding')
            api.require(rec['effective_binding']==effective and rr['checkpoint']['contract']==parent.engine.prior.contracts.expected_contract(spec,effective),'configuration contract')
            api.require(rr['checkpoint']['state_sha256']==api.digest(state),'checkpoint state seal')
            api.require(rec['minimum_gap_semantics']==d['minimum_gap_semantics'],'gap bound semantics')
            api.require(rr['status']=='paused_checkpoint' and rr['rejected']==0 and parent.engine.prior.reference.independent_health(rr,spec)['passed'],'bounded status and original health gates')
            t=cp['state']['t'] if cp else 0.;before_t=t;step0=cp['state']['steps'] if cp else 0
            x=cp['state']['x'] if cp else spec['initial_state']['position_m'];orientation=cp['state']['p'] if cp else spec['initial_state']['orientation']
            a,b,_=spec['config']['prolate_semiaxes_m']
            api.require(len(rows)==len(rec['sweep_certificates'])==d['steps_per_block']==rec['step_cap'],'complete trace and proof coverage')
            for row,proof in zip(rows,rec['sweep_certificates']):
                api.require(row['dt_s']>0 and t+row['dt_s']==row['time_s'],'exact clock')
                api.require(np.isfinite(row['position_m']+row['orientation']+row['velocity_generalized']).all() and abs(np.linalg.norm(row['orientation'])-1)<1e-10,'finite physical state')
                if proof['certified']:
                    audit_proof(proof,geometry,x,orientation,row['velocity_generalized'],row['dt_s'],a,b);counts['certified_sweeps']+=1
                else:
                    val=job.candidate.REFERENCE(geometry,np.array(x),np.array(orientation),np.array(row['velocity_generalized']),a,b,row['dt_s'])
                    api.require(val==proof['reference_gap_m'] and val>=-1e-5*b,'independent original swept gate');counts['legacy_sweeps']+=1
                t=row['time_s'];x=row['position_m'];orientation=row['orientation']
            api.require(t==state['t']==rr['time_s']<spec['horizon_s'] and len(rows)==rr['steps']-step0,'exact step accounting; explicitly incomplete horizon')
            api.require(x==state['x'] and orientation==state['p'] and rows[-1]['velocity_generalized']==state['q'],'endpoint binding')
            api.require(len(rec['backend_calls'])==1 and rec['backend_calls'][0]['enabled'],'qualified rigid backend')
            for attempt in rec['early_attempts']:
                if attempt['accepted']:
                    values=physical(attempt);counts['early_contacts']+=1;maxima=[max(a,b) for a,b in zip(maxima,values)]
            api.require(len(rr['stage119_repair_calls'])==len(rec['repairs'])==0,'no unaudited fallback')
            tx=api.read(path.parent/f'transaction_{i:03d}.json')
            api.require(tx['record_sha256']==api.sha(path) and tx['record_path']==str(path),'transaction binding')
            api.require(tx['compute_s']==rec['compute_call_wall_s']<=tx['transaction_wall_s'] and tx['steps']==len(rows) and tx['simulated_s']==t-before_t and tx['compressed_bytes']==path.stat().st_size,'transaction costs and bytes')
            c_rates.append(tx['transaction_wall_s']/(t-before_t));c_sizes.append(path.stat().st_size/len(rows));counts['steps']+=len(rows);cp=rr['checkpoint']
        key=(c['shape'],c['factor']);rates[key]=max(rates.get(key,0.),max(c_rates));sizes[key]=max(sizes.get(key,0.),max(c_sizes))
        cases.append({'case':c['id'],'fresh':c['source'] is None,'initial_time_s':initial_t,'final_time_s':t,'new_steps':state['steps']-initial_steps,'max_record_bytes_per_step':max(c_sizes),'full_observation':False})
        print('AUDITED',c['id'],state['steps']-initial_steps,flush=True)
    api.require(seen=={str(p) for p in job.RUN.rglob('*.json.gz')}=={x for x in r['artifacts'] if x.endswith('.json.gz')},'complete inventory')
    api.require(counts['steps']==r['new_steps']==d['maximum_new_steps'],'total new steps')
    loads=[0.,0.,0.];schedule=[]
    for c in d['cases']:
        hours=c['spec']['horizon_s']*rates[c['shape'],c['factor']]*d['runtime_margin']/3600
        worker=min(range(3),key=lambda i:loads[i]);loads[worker]+=hours;schedule.append({'case':c['id'],'worker':worker,'hours':hours,'finish_hours':loads[worker]})
    makespan=max(loads)+1/6;api.require(makespan==r['projected_makespan_hours'],'independent time projection')
    now=datetime.datetime.now(datetime.timezone.utc);available=(datetime.datetime.fromisoformat(d['simulation_cutoff_utc'])-now).total_seconds()/3600
    # Frozen campaign step ceilings are a conservative storage boundary, not a prediction.
    old=api.read(parent.DESIGN);budgets=old['budget'];free=shutil.disk_usage(job.ROOT).free
    ceiling_rows=[]
    for c in d['cases']:
        # Stage167 assigns 20,000,000 fine or 10,000,000 selected steps plus 20,000 total reserve.
        n=20_000_000 if c['factor']==old['reference_factor'] else 10_000_000
        ceiling_rows.append({'case':c['id'],'max_steps':n,'bytes_per_step':sizes[c['shape'],c['factor']],'bytes':n*sizes[c['shape'],c['factor']]})
    api.require(sum(x['max_steps'] for x in ceiling_rows)+20_000==budgets['max_new_steps_total'],'frozen step ceiling independently accounted')
    ceiling_bytes=math.ceil(sum(x['bytes'] for x in ceiling_rows)+20_000*max(sizes.values()))
    report={'integration_verified':True,'counts':counts,'records':len(seen),'cases':cases,'max_contact_residual':maxima[0],'max_force_residual':maxima[1],
            'time_budget_passed':makespan<=available,'projected_makespan_hours':makespan,'available_hours':available,'schedule':schedule,
            'storage_assessment':{'basis':'maximum observed family compressed bytes/step times frozen global step ceilings, plus reserve steps; not a hard encoding upper bound',
                'rows':ceiling_rows,'projected_bytes_at_step_ceiling':ceiling_bytes,'free_bytes':free,'reserve_bytes':d['minimum_free_disk_bytes'],
                'fits_with_reserve':ceiling_bytes<=free-d['minimum_free_disk_bytes'],'further_storage_qualification_required':True},
            'campaign_ready':False,'campaign_launched':False,'full_path_qualified':False,'claim':d['claim'],
            'design_sha256':api.sha(job.DESIGN),'result_sha256':api.sha(job.OUT/'results.json'),'audit_source_sha256':api.sha(__file__),'evaluated_utc':now.isoformat()}
    job.verify(d);OUT.mkdir(exist_ok=False);api.write(OUT/'results.json',report);api.write(OUT/'completion.json',{'integration_verified':True,'results_sha256':api.sha(OUT/'results.json')})
    print('COMBINED_AUDIT',counts,'TIME_H',makespan,'STORAGE',report['storage_assessment'],flush=True)


if __name__=='__main__':main()
