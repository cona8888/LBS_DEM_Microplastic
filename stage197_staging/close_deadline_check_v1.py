"""Smallest independent deadline falsification; no trajectory or new physics.

Keep measured-regime extrapolation distinct from a hard runtime lower bound.
No late-history fixtures or new campaign when compute-only scenario fails.
"""
from pathlib import Path
import os, psutil, shutil
import qualify_budget_continuation_v1 as q
job,api=q.job,q.api
OUT=q.OUT.parent/'deadline_check_01'

def main():
    p=api.read(q.DESIGN);q.verify(p);d=api.read(job.DESIGN);a=api.read(q.AUTH)
    audits=[q.OUT.parent/x/'results.json' for x in ('independent_continuation_01','independent_transport_01')]
    for path in audits:
        r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed independent audit')
    r=api.read(q.OUT/'results.json');api.require(r['passed'] and api.read(q.OUT/'completion.json')['results_sha256']==api.sha(q.OUT/'results.json'),'qualification result seal');api.verify_mapping(r['artifacts'])
    item=next(x for x in r['calls'] if x['label']=='conditional_fine');case=next(c for c in d['cases'] if c['id']==item['case'])
    h=case['spec']['horizon_s'];factor=a['runtime_and_storage_margin'];span=item['simulated_seconds']
    compute=item['compute_seconds']/span*h*factor/3600
    transaction=item['transaction_seconds']/span*h*factor/3600
    now=job.utc();available=(job.policy.utc(a['simulation_cutoff_utc'])-now).total_seconds()/3600
    api.require(compute>available,'measured-regime compute-only scenario already fails unchanged runtime margin')
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():
            api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'qualification and audit workers retired')
    actual=sum(api.read(x)['accepted_steps'] for x in q.RUN.glob('*.accounting.json'))
    launches=list(q.RUN.glob('*.launch.json'))
    api.require(len(launches)==6 and all(x.with_name(x.name.replace('.launch.json','.accounting.json')).exists() for x in launches),'all reservations resolved')
    api.require(actual==r['new_accepted_steps']==10404 and 35426+actual==45830,'exact cumulative recovery ledger')
    inputs=[q.AUTH,q.DESIGN,q.OUT/'results.json',q.OUT/'completion.json',*audits,Path(__file__)]
    result={'audit_passed':True,'production_ready':False,'runtime_scenario_passed':False,'simulation_cutoff_utc':a['simulation_cutoff_utc'],'final_audit_deadline_utc':a['final_audit_deadline_utc'],'checked_utc':now.isoformat(),
        'fine_case':case['id'],'horizon_s':h,'measurement':{k:item[k] for k in ('steps','simulated_seconds','compute_seconds','transaction_seconds','read_seconds','audit_seconds','status','raw_sha256')},
        'compute_only_hours_with_margin':compute,'transaction_hours_with_margin':transaction,'available_simulation_hours':available,'runtime_margin':factor,
        'additional_recovery_steps':actual,'cumulative_recovery_steps':45830,'unused_recovery_step_allowance':54170,'unresolved_reservations':[],
        'all_other_owned_workers_retired':True,'new_campaign_started':False,'heartbeat_created':False,'old_timing_test_results_unchanged':True,
        'source_based_adjudication':'Original Stage167 check permits incomplete_budget; Stage187 worker continues healthy positive-step segments. Stage196 exact-10000 timing tests remain failed, but their incomplete status alone is not a production numerical failure. Stage197 verifies local exact continuation and original numerical gates, not deadline fit.',
        'late_history_resource_test':'Deferred: compute-only scenario already fails, so avoid unnecessary zero-step stress and do not claim a complete six-case resource forecast.',
        'disk_free_bytes':{'C':shutil.disk_usage('C:/').free,'D':shutil.disk_usage('D:/').free},'minimum_free_disk_bytes':a['minimum_free_disk_bytes'],
        'claim':'Measured-regime conservative planning scenarios, not hard lower bounds, predictions that every future step has this cost, full fresh paired-path results, release measurements or empirical validation.',
        'next_gate':'Demonstrate an additional pure-implementation speedup including transaction costs, or explicitly revise the conservative resource planning policy/hardware. Original scientific criteria and observations remain unchanged.',
        'inputs':{str(x):api.sha(x) for x in inputs},'source_sha256':api.sha(__file__)}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'audit_passed':True,'results_sha256':api.sha(OUT/'results.json'),'production_ready':False})
    print('DEADLINE_CHECK','compute',compute,'transaction',transaction,'available',available,'steps',actual,flush=True)

if __name__=='__main__':main()
