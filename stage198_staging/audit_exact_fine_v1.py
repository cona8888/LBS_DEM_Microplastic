"""Independent raw/clock/gate/identity/accounting closure and measured forecast."""
from pathlib import Path
import os, psutil, time
import probe_exact_fine_v1 as p
job,api,q=p.job,p.api,p.q
OUT=p.OUT.parent/'independent_fine_01'

def main():
    d=api.read(p.DESIGN);p.verify(d);auth=api.read(p.AUTH)
    result=api.read(p.OUT/'results.json');api.require(result['passed'] and api.read(p.OUT/'completion.json')['results_sha256']==api.sha(p.OUT/'results.json'),'qualified result seal');api.verify_mapping(result['artifacts'])
    api.require(not psutil.pid_exists(api.read(p.RUN/'launch.json')['pid']),'owned trajectory process retired')
    case,initial=p.seed(d);oracle=q.independent_file(p.held.FINE,api.sha(p.pre.job.DESIGN));records={};states={};audits=[];total=0
    api.require(api.read(p.RUN/'initial.json')==initial,'independent original seed reconstruction')
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
        geo=p.pre.prior.geometry()
        for label in ('serial','split_a','split_b'):
            path=p.RUN/(label+'.json.xz');prefix=None if label!='split_b' else states['split_a'];before=initial if label!='split_b' else records['split_a']['result']['checkpoint']
            hist=None if prefix is None else records['split_a']['result']['history'];ref=None if prefix is None else prefix.reference()
            rec=q.independent_file(path,api.sha(p.DESIGN),hist,ref);decoded,state=job.codec.read_record(path,api.sha(p.DESIGN),prefix)
            api.require(p.storage.base.raw_bytes(rec)==p.storage.base.raw_bytes(decoded),'independent complete raw/history reconstruction')
            check=job.kernel.evaluate(rec,case['spec'],job.binding(d,case),before,geo,api.sha(p.DESIGN),d['minimum_gap_semantics'])
            launch=api.read(path.with_suffix('.launch.json'));account=api.read(path.with_suffix('.accounting.json'));count=len(rec['rows']);total+=count
            api.require(check['passed'] and not check['complete_observation'] and count==launch['reserved_steps']==account['accepted_steps']==d['calls'][label] and rec['result']['rejected']==0,'original complete bounded call numerics/accounting')
            api.require(launch['input_checkpoint_sha256']==api.digest(before) and account['raw_sha256']==api.sha(path),'ancestry and seal binding')
            expected=oracle['rows'] if label=='serial' else oracle['rows'][:1790] if label=='split_a' else oracle['rows'][1790:]
            api.require(rec['rows']==expected,'entire original fine trajectory exactly equal')
            if label!='split_a':api.require(rec['result']['checkpoint']['state']==oracle['result']['checkpoint']['state'],'entire original end state exactly equal')
            records[label]=rec;states[label]=state;audits.append({'label':label,'steps':count,'numerical':check,'raw_sha256':api.sha(path),'logical_sha256':state.original_sha256})
    api.require(total==7160==result['new_accepted_steps'] and records['split_a']['rows']+records['split_b']['rows']==records['serial']['rows'] and records['serial']['result']['checkpoint']==records['split_b']['result']['checkpoint'],'independent exact restart and total')
    measured=next(x for x in result['calls'] if x['label']=='serial');old=api.read(p.ROOT/'stage197_evaluations/deadline_extension_20260926/continuation_01/results.json');oldrow=next(x for x in old['calls'] if x['label']=='conditional_fine')
    api.require(measured['steps']==oldrow['steps'] and measured['simulated_seconds']==oldrow['simulated_seconds'],'matched measurement interval')
    available=(job.policy.utc(auth['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600;scale=case['spec']['horizon_s']*auth['runtime_and_storage_margin']/measured['simulated_seconds']/3600
    compute=measured['compute_seconds']*scale;transaction=measured['transaction_seconds']*scale
    r={'passed':True,'source_results_sha256':api.sha(p.OUT/'results.json'),'source_sha256':api.sha(__file__),'audits':audits,'new_trajectory_steps':0,'qualified_accepted_steps':7160,'cumulative_recovery_steps':52990,'remaining_recovery_step_allowance':47010,
        'exact_original_fine_rows_state_and_restart':True,'unresolved_reservations':[],'all_trajectory_workers_retired':True,
        'measured_compute_speedup':oldrow['compute_seconds']/measured['compute_seconds'],'measured_transaction_speedup':oldrow['transaction_seconds']/measured['transaction_seconds'],
        'fine_compute_hours_with_margin':compute,'fine_transaction_hours_with_margin':transaction,'available_simulation_hours':available,'local_fine_runtime_scenario_passed':transaction<=available,
        'full_six_case_resource_gate_passed':False,'production_authorized':False,'complete_observations':0,
        'claim':'Exact local numerical and storage verification. Matched-interval timings are measurements; horizon-scaled costs are conservative regime scenarios, not hard lower bounds or guaranteed completion.',
        'next_gate':'If local timing fits, qualify full six-worker stack and refreshed late-history/single-auditor resource scenario before fresh production. Otherwise report remaining runtime gap without relaxing checks.'}
    p.verify(d);job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
    print('INDEPENDENT_FINE_PASS','compute_hours',compute,'transaction_hours',transaction,'available',available,'compute_speedup',r['measured_compute_speedup'],'transaction_speedup',r['measured_transaction_speedup'],flush=True)

if __name__=='__main__':main()
