"""Independent byte-level and original numerical closure; no trajectory work."""
from pathlib import Path
import os, psutil
import qualify_fine_boundary_v1 as b
p=b.p;api,job,q=b.api,b.job,b.q
OUT=b.OUT.parent/'independent_closure_01'

def exact(a,c,label):
    api.require(p.storage.base.raw_bytes(a)==p.storage.base.raw_bytes(c),label)

def main():
    d=api.read(b.DESIGN);b.verify(d);a=api.read(p.AUTH)
    r=api.read(b.OUT/'results.json');api.require(r['passed'] and api.read(b.OUT/'completion.json')['results_sha256']==api.sha(b.OUT/'results.json'),'boundary completion seal');api.verify_mapping(r['artifacts'])
    for launch in (p.RUN/'launch.json',b.RUN/'launch.json'):
        oldpid=api.read(launch)['pid'];api.require(not psutil.pid_exists(oldpid),'owned diagnostic worker retired')
    case,initial=p.seed(d);exact(initial,api.read(b.RUN/'initial.json'),'exact independent seed')
    old=q.independent_file(p.held.FINE,api.sha(p.pre.job.DESIGN));serial=q.independent_file(p.RUN/'serial.json.xz',api.sha(p.DESIGN))
    failure=api.read(p.OUT/'failure.json');api.require(failure['known_new_steps']==3580 and not failure['unresolved'],'failed predecessor accounting retained')
    x=serial['result']['checkpoint']['state'];y=old['result']['checkpoint']['state'];pending=y['pending_trial']
    api.require(serial['result']['status']=='paused_checkpoint' and old['result']['status']=='incomplete_budget' and x['pending_trial'] is None,'different original legal stopping mechanisms')
    api.require(pending==d['observed_pending_trial'] and set(pending)=={'time_s','dt_s','attempt'} and pending['attempt']==0 and pending['time_s']==y['t'] and 0<pending['dt_s']<=case['spec']['horizon_s']-y['t'],'original valid uncommitted pending trial')
    exact(serial['rows'],old['rows'],'every original row canonical-byte exact')
    exact({k:v for k,v in x.items() if k!='pending_trial'},{k:v for k,v in y.items() if k!='pending_trial'},'every other original state/history field canonical-byte exact')
    records={};states={};audits=[];total=0
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
        geo=p.pre.prior.geometry()
        old_design=api.read(p.DESIGN);oldcase,oldinitial=p.seed(old_design)
        serial_audit=job.kernel.evaluate(serial,oldcase['spec'],job.binding(old_design,oldcase),oldinitial,geo,api.sha(p.DESIGN),d['minimum_gap_semantics'])
        account=api.read((p.RUN/'serial.json.xz').with_suffix('.accounting.json'))
        api.require(serial_audit['passed'] and len(serial['rows'])==account['accepted_steps']==3580 and account['raw_sha256']==api.sha(p.RUN/'serial.json.xz'),'original failed test healthy saved-prefix audit, not a test pass')
        for label in ('old_pending_baseline','old_pending_candidate','paused_candidate','split_a','split_b'):
            path=b.RUN/(label+'.json.xz')
            if label=='split_a':before=initial
            elif label=='split_b':before=records['split_a']['result']['checkpoint']
            else:before=b.rebind(d,case,(serial if label=='paused_candidate' else old)['result']['checkpoint'])
            prefix=states['split_a'] if label=='split_b' else None
            hist=records['split_a']['result']['history'] if prefix is not None else None;ref=prefix.reference() if prefix is not None else None
            rec=q.independent_file(path,api.sha(b.DESIGN),hist,ref);decoded,state=job.codec.read_record(path,api.sha(b.DESIGN),prefix)
            exact(rec,decoded,'independent decoder full canonical bytes')
            check=job.kernel.evaluate(rec,case['spec'],job.binding(d,case),before,geo,api.sha(b.DESIGN),d['minimum_gap_semantics'])
            launch=api.read(path.with_suffix('.launch.json'));account=api.read(path.with_suffix('.accounting.json'));count=len(rec['rows']);total+=count
            api.require(check['passed'] and not check['complete_observation'] and rec['result']['status']=='paused_checkpoint' and not rec['result']['rejected'],'original numerical and bounded observation gates')
            api.require(count==launch['reserved_steps']==account['accepted_steps']==d['calls'][label] and account['cumulative_steps']==total and launch['input_checkpoint_sha256']==api.digest(before) and account['raw_sha256']==api.sha(path),'complete hash/clock/step ancestry')
            records[label]=rec;states[label]=state
            if label.startswith('split_'):
                exact(rec['rows'],serial['rows'][:1790] if label=='split_a' else serial['rows'][1790:],'exact split rows')
                if label=='split_b':exact(rec['result']['checkpoint']['state'],serial['result']['checkpoint']['state'],'full exact split checkpoint')
            else:
                api.require(rec['rows'][0]['dt_s']==pending['dt_s'],'same pending or recomputed dt')
                exact(rec['rows'],records['old_pending_baseline']['rows'],'exact original/candidate next rows')
                exact(rec['result']['checkpoint']['state'],records['old_pending_baseline']['result']['checkpoint']['state'],'exact original/candidate full next checkpoint')
            audits.append({'label':label,'raw_sha256':api.sha(path),'audit':check,'logical_sha256':state.original_sha256})
    exact(records['split_a']['rows']+records['split_b']['rows'],serial['rows'],'complete serial/partition row identity')
    api.require(total==r['new_accepted_steps']==3676 and r['cumulative_recovery_steps']==53086,'exact recovery ledger')
    measured=api.read((p.RUN/'serial.json.xz').with_suffix('.audit.json'))
    former=api.read(p.ROOT/'stage197_evaluations/deadline_extension_20260926/continuation_01/results.json')
    prior=next(v for v in former['calls'] if v['label']=='conditional_fine')
    api.require(prior['steps']==measured['steps']==3580 and prior['simulated_seconds']==measured['simulated_seconds'],'same measured physical interval')
    scale=case['spec']['horizon_s']*a['runtime_and_storage_margin']/measured['simulated_seconds']/3600
    available=(job.policy.utc(a['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    owned=[{'pid':x.pid,'argv':x.info['cmdline']} for x in psutil.process_iter(['name','cmdline']) if x.pid!=os.getpid() and 'python' in (x.info['name'] or '').lower() and 'matdem_microplastic' in ' '.join(x.info['cmdline'] or []).lower()]
    api.require(not owned,'no remaining owned diagnostic workers')
    b.verify(d)
    result={'passed':True,'utc':job.utc().isoformat(),'source_sha256':api.sha(__file__),'boundary_protocol_sha256':api.sha(b.DESIGN),'boundary_result_sha256':api.sha(b.OUT/'results.json'),'old_fixed_cap_test_remains_failed':True,
        'failure_diagnosis':'Exact equality compared a deliberate step-cap stop to a time-budget stop with a legal unstarted attempt-0 pending trial; all other fields match. Independent original and optimized resumptions now match exactly.',
        'serial_audit':serial_audit,'boundary_audits':audits,'exact_original_rows':3580,'exact_partition_steps':3580,'exact_baseline_pending_candidate_paused_steps_each':32,
        'new_steps_in_this_closure':0,'stage198_new_accepted_steps':3580+total,'cumulative_recovery_steps':53086,'remaining_recovery_steps':46914,'unresolved_reservations':[],'owned_workers_remaining':owned,
        'measured_interval':{'steps':3580,'simulated_seconds':measured['simulated_seconds'],'old_compute_seconds':prior['compute_seconds'],'new_compute_seconds':measured['compute_seconds'],'old_transaction_seconds':prior['transaction_seconds'],'new_transaction_seconds':measured['transaction_seconds'],'compute_speedup':prior['compute_seconds']/measured['compute_seconds'],'transaction_speedup':prior['transaction_seconds']/measured['transaction_seconds']},
        'conservative_local_fine_scenario':{'compute_hours_with_margin':measured['compute_seconds']*scale,'transaction_hours_with_margin':measured['transaction_seconds']*scale,'runtime_margin':a['runtime_and_storage_margin'],'available_simulation_hours':available,'passed':measured['transaction_seconds']*scale<=available,'limitation':'Measured hard-contact-regime extrapolation, not a hard lower bound or whole-campaign prediction. Parallel late-history costs are not yet qualified.'},
        'full_six_case_resource_gate_passed':False,'production_authorized':False,'complete_observations':0,
        'next_gate':'Retain exact local optimizer/storage improvements. Do not spend further trajectory or full-stack budget until a bounded pure implementation improvement or explicit resource-policy decision can close the remaining conservative runtime gap. No silent relaxation.',
        'inputs':{str(x):api.sha(x) for x in (p.AUTH,p.DESIGN,b.DESIGN,p.OUT/'failure.json',b.OUT/'results.json',b.OUT/'completion.json',p.OUT.parent/'held_02/results.json',p.OUT.parent/'storage_01/results.json')}}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json'),'production_authorized':False})
    print('INDEPENDENT_BOUNDARY_PASS',total,'RECOVERY',53086,'RUNTIME_HOURS',result['conservative_local_fine_scenario'],'RESULT',api.sha(OUT/'results.json'),flush=True)

if __name__=='__main__':main()
