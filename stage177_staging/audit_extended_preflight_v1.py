"""Independent exact-byte, mechanics, clearance, dwell, restart and cost audit."""
from pathlib import Path
from collections import Counter
import copy,datetime,gzip,hashlib,json,lzma,math,shutil,sys,time,traceback
import numpy as np
import extended_optimized_preflight_v1 as job
from audit_certified_integration_v1 import audit_proof
from audit_fast_integration_v1 import physical
import audit_paired_deadline_campaign_v3 as stream_audit
api,parent,codec=job.api,job.parent,job.codec
OUT=job.OUT.parent/'independent_audit_01'


def independent_read(path,design_sha):
    path=Path(path);s=api.read(path.with_suffix('.seal.json'))
    api.require(s['format']==codec.FORMAT and s['design_sha256']==design_sha and s['compressed_bytes']==path.stat().st_size,'archive declaration')
    api.require(codec.file_sha(path)==s['compressed_sha256'],'compressed SHA256')
    h=hashlib.sha256();blocks=[];n=0
    with lzma.open(path,'rb') as f:
        for z in iter(lambda:f.read(1024**2),b''):
            n+=len(z);api.require(n<=s['uncompressed_bytes']<=codec.MAX_RAW,'bounded independent decompression');h.update(z);blocks.append(z)
    api.require(n==s['uncompressed_bytes'] and h.hexdigest()==s['uncompressed_sha256'],'original uncompressed evidence seal')
    rec=json.loads(b''.join(blocks));api.require(rec['design_sha256']==design_sha,'raw design binding');return rec


def restore_monitor(spec,state):
    m=stream_audit.make_monitor(spec);m.__dict__.update(copy.deepcopy(state['monitor']))
    if m.anchor is not None:m.anchor=np.asarray(m.anchor,float)
    m.contact_ids=tuple(m.contact_ids);m.load_bearing_ids=tuple(m.load_bearing_ids);return m


def audit_record(path,spec,binding,before,geometry,d):
    started=time.perf_counter();rec=independent_read(path,api.sha(job.DESIGN));r=rec['result'];state=r['checkpoint']['state'];rows=rec['rows'];effective=parent.model.binding_for(binding,True)
    api.require(rec['spec']==spec and rec['input_checkpoint_sha256']==api.digest(before) and rec['effective_binding']==effective,'input and effective binding')
    api.require(r['checkpoint']['contract']==parent.engine.prior.contracts.expected_contract(spec,effective) and r['checkpoint']['state_sha256']==api.digest(state),'sealed checkpoint contract')
    api.require(r['status']=='paused_checkpoint' and r['rejected']==before['state']['rejected']==0,'bounded nonfailed, no rejects')
    api.require(parent.engine.prior.reference.independent_health(r,spec)['passed'],'unchanged health gates')
    api.require(rec['minimum_gap_semantics']==d['minimum_gap_semantics'],'explicit conservative gap diagnostic')
    api.require(len(rows)==rec['step_cap']==len(rec['sweep_certificates']),'complete trace/proof coverage')
    t=before['state']['t'];x=before['state']['x'];p=before['state']['p'];a,b,_=spec['config']['prolate_semiaxes_m']
    monitor=restore_monitor(spec,before['state']);first=before['state']['first_contact_dwell_time'];certified=0;legacy=0
    allowed=Counter((row['dt_s'],*row['velocity_generalized']) for row in rows)
    for row,proof in zip(rows,rec['sweep_certificates']):
        api.require(row['dt_s']>0 and t+row['dt_s']==row['time_s'],'accepted clock')
        api.require(np.isfinite(row['position_m']+row['orientation']+row['velocity_generalized']).all() and abs(np.linalg.norm(row['orientation'])-1)<=1e-10,'finite normalized state')
        if proof['certified']:
            audit_proof(proof,geometry,x,p,row['velocity_generalized'],row['dt_s'],a,b);certified+=1
        else:
            value=job.candidate.REFERENCE(geometry,np.array(x),np.array(p),np.array(row['velocity_generalized']),a,b,row['dt_s'])
            api.require(value==proof['reference_gap_m'] and value>=-1e-5*b,'original fallback swept gate');legacy+=1
        dwell=monitor.update(row['dt_s'],row['position_m'],row['velocity_generalized'],row['active_contact_ids'],row['supported_bearing_ids'])
        api.require(dwell==row['dwell'],'independent interval dwell replay')
        if first is None and dwell['persistent_contact_observed']:first=row['time_s']
        t=row['time_s'];x=row['position_m'];p=row['orientation']
    api.require(api.digest(monitor.__dict__)==api.digest(state['monitor']),'complete dwell monitor state')
    api.require(first==state['first_contact_dwell_time']==r['first_contact_dwell_time_s'],'first dwell event clock')
    api.require(rows[-1]['dwell']==state['last_trap_state']==r['trap_state'],'endpoint dwell identity')
    api.require(state['x']==x and state['p']==p and state['q']==rows[-1]['velocity_generalized'],'physical trace endpoint')
    api.require(t==r['time_s']==state['t']<spec['horizon_s'] and r['steps']==state['steps']==before['state']['steps']+len(rows),'exact steps/clock, incomplete observation')
    api.require(len(rec['backend_calls'])==1 and rec['backend_calls'][0]['enabled'],'rigid rotational backend')
    maxima=[0.,0.];early=0
    for attempt in rec['early_attempts']:
        if attempt['accepted']:
            key=(attempt['dt_s'],*attempt['velocity']);api.require(allowed[key]>0,'contact output belongs to observed accepted step');allowed[key]-=1
            values=physical(attempt);maxima=[max(a,b) for a,b in zip(maxima,values)];early+=1
    api.require(len(rec['repairs'])==len(r['stage119_repair_calls'])==0,'no unaudited fallback solver')
    tx=api.read(Path(path).with_suffix('.transaction.json'))
    api.require(tx['sha256']==api.sha(path) and tx['path']==str(path) and tx['steps']==len(rows),'transaction identity')
    api.require(tx['compute_s']==rec['compute_call_wall_s']<=tx['transaction_s'] and tx['simulated_s']==t-before['state']['t'],'transaction clock')
    api.require(tx['compressed_bytes']==Path(path).stat().st_size,'transaction size')
    return rec,{'path':str(path),'steps':len(rows),'certified':certified,'legacy':legacy,'early':early,
                'max_contact_residual':maxima[0],'max_force_residual':maxima[1],'audit_wall_s':time.perf_counter()-started,'transaction':tx}


def main():
    started=time.perf_counter();d=api.read(job.DESIGN);job.verify(d);r=api.read(job.OUT/'results.json')
    api.require(not (job.OUT/'failure.json').exists() and api.read(job.OUT/'completion.json')['results_sha256']==api.sha(job.OUT/'results.json'),'terminal completion')
    api.verify_mapping(r['artifacts']);parent.b.old.parent.configure();field,data,meta=api.fields.load(2,1.,6)
    geometry=job.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    seen=set();summaries=[];cases=[];rates={};sizes={};audit_rates={}
    for c in d['cases']:
        src=parent.storage.read_record(Path(c['source']),c['source_design_sha256']);binding=api.digest([d['binding'],c['id']])
        api.require(src['result']['checkpoint']['state_sha256']==c['initial_checkpoint_state_sha256'],'immutable selected source')
        cp=parent.model.checkpoint(c['spec'],binding,src['result']['checkpoint'],True);initial=cp['state']['t'];folder=job.RUN/c['id']
        def audit(path,before):
            api.require(str(path) not in seen,'unique raw record');seen.add(str(path));rec,summary=audit_record(path,c['spec'],binding,before,geometry,d);summaries.append(summary);return rec,summary
        for i in range(1,d['blocks_per_case']+1):
            rec,s=audit(folder/f'segment_{i:03d}.json.xz',cp);cp=rec['result']['checkpoint'];tx=s['transaction'];key=c['shape'],c['factor']
            rates[key]=max(rates.get(key,0.),tx['transaction_s']/tx['simulated_s']);sizes[key]=max(sizes.get(key,0.),tx['compressed_bytes']/s['steps'])
            audit_rates[key]=max(audit_rates.get(key,0.),s['audit_wall_s']/tx['simulated_s'])
            print('AUDIT_BLOCK',c['id'],i,s['steps'],round(s['audit_wall_s'],3),flush=True)
        full,fs=audit(folder/'restart_full.json.xz',cp);first,ss=audit(folder/'restart_first.json.xz',cp);last,ls=audit(folder/'restart_last.json.xz',first['result']['checkpoint'])
        api.require(len(full['rows'])==d['restart_steps'] and [len(first['rows']),len(last['rows'])]==d['restart_split'],'restart lengths')
        api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'exact combined restart including diagnostic history')
        cases.append({'case':c['id'],'initial_time_s':initial,'window_stop_s':cp['state']['t'],'restart_exact':True,'full_observation':False})
        del rec,src,full,first,last
    api.require(seen=={str(p) for p in job.RUN.rglob('*.json.xz')}=={x for x in r['artifacts'] if x.endswith('.json.xz')},'all records accounted')
    totals={k:sum(x[k] for x in summaries) for k in ['steps','certified','legacy','early']}
    api.require(totals['steps']==r['new_steps']==d['maximum_new_steps'] and totals['steps']+d['prior_work_window_steps']<=d['work_window_step_ceiling'],'new and cumulative trajectory allowance')
    loads=[0.,0.,0.];bytes_total=20000*max(sizes.values());audit_seconds=0.;cost=[];old=api.read(parent.DESIGN)
    for c in d['cases']:
        key=c['shape'],c['factor'];hours=c['spec']['horizon_s']*rates[key]*1.3/3600
        worker=min(range(3),key=lambda i:loads[i]);loads[worker]+=hours
        ceiling=next(x['step_ceiling'] for x in old['cases'] if x['id']==c['id']);amount=ceiling*sizes[key];bytes_total+=amount
        audit_seconds+=c['spec']['horizon_s']*audit_rates[key]*1.3
        cost.append({'case':c['id'],'hours':hours,'worker':worker,'step_ceiling':ceiling,'bytes_at_ceiling':amount,'max_bytes_per_step':sizes[key]})
    now=datetime.datetime.now(datetime.timezone.utc);available=(datetime.datetime.fromisoformat(api.read(job.prior.DESIGN)['simulation_cutoff_utc'])-now).total_seconds()/3600
    free=shutil.disk_usage(job.ROOT).free;storage_with_margin=math.ceil(bytes_total*1.3)
    report={'integration_verified':True,'totals':totals,'records':len(seen),'cases':cases,'record_audits':summaries,'wall_s':time.perf_counter()-started,
            'max_contact_residual':max(x['max_contact_residual'] for x in summaries),'max_force_residual':max(x['max_force_residual'] for x in summaries),
            'cost':cost,'time_projection_hours':max(loads)+1/6,'available_hours':available,'time_budget_passed':max(loads)+1/6<=available,
            'storage_projection_bytes_with_30pct_margin':storage_with_margin,'free_bytes':free,'reserve_bytes':d['minimum_free_disk_bytes'],
            'storage_sample_projection_passed':storage_with_margin<=free-d['minimum_free_disk_bytes'],'cumulative_history_stress_still_required':True,
            'projected_serial_full_audit_hours':audit_seconds/3600,'full_path_qualified':False,'campaign_launched':False,'campaign_ready':False,
            'design_sha256':api.sha(job.DESIGN),'result_sha256':api.sha(job.OUT/'results.json'),'audit_source_sha256':api.sha(__file__),
            'claim':'Local conditional numerical evidence only. Resource projections do not bound unseen contact complexity or late-history growth.'}
    job.verify(d);OUT.mkdir(exist_ok=False);api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'integration_verified':True,'results_sha256':api.sha(OUT/'results.json')})
    print('EXTENDED_AUDIT',totals,'HOURS',report['time_projection_hours'],'STORAGE_GB',storage_with_margin/1e9,'AUDIT_H',audit_seconds/3600,flush=True)


if __name__=='__main__':main()
